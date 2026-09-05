#include "AtlasLiveTcpListener.h"
#include "AtlasUnrealTransport.h"
#include "Common/TcpSocketBuilder.h"
#include "GenericPlatform/GenericPlatformMisc.h"
#include "HAL/PlatformTime.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Dom/JsonObject.h"

#if PLATFORM_WINDOWS
#include "Windows/AllowWindowsPlatformTypes.h"
#include <bcrypt.h>
#include "Windows/HideWindowsPlatformTypes.h"
#endif

namespace
{
    FString ComputeSha256Hex(const uint8* Data, int32 Length)
    {
#if PLATFORM_WINDOWS
        BCRYPT_ALG_HANDLE AlgHandle = NULL;
        BCRYPT_HASH_HANDLE HashHandle = NULL;
        NTSTATUS Status = BCryptOpenAlgorithmProvider(&AlgHandle, BCRYPT_SHA256_ALGORITHM, NULL, 0);
        if (!BCRYPT_SUCCESS(Status))
        {
            return FString();
        }

        Status = BCryptCreateHash(AlgHandle, &HashHandle, NULL, 0, NULL, 0, 0);
        if (!BCRYPT_SUCCESS(Status))
        {
            BCryptCloseAlgorithmProvider(AlgHandle, 0);
            return FString();
        }

        Status = BCryptHashData(HashHandle, (UCHAR*)Data, Length, 0);
        uint8 HashBytes[32] = {0};
        if (BCRYPT_SUCCESS(Status))
        {
            BCryptFinishHash(HashHandle, HashBytes, sizeof(HashBytes), 0);
        }

        BCryptDestroyHash(HashHandle);
        BCryptCloseAlgorithmProvider(AlgHandle, 0);

        return BytesToHex(HashBytes, sizeof(HashBytes)).ToLower();
#else
        return FString();
#endif
    }
}

FAtlasLiveTcpListener::FAtlasLiveTcpListener(
    TSharedPtr<FAtlasLiveIngressQueue> InQueue,
    int32 InListenPort,
    const FString& InBindAddress)
    : IngressQueue(InQueue)
    , DesiredPort(InListenPort)
    , BindAddressStr(InBindAddress)
    , BoundPort(0)
    , Thread(nullptr)
    , bStopRequested(false)
    , ListenSocket(nullptr)
    , ActiveClientSocket(nullptr)
    , ConnectionState(EAtlasLiveConnectionState::Disconnected)
    , TotalBytesReceivedCount(0)
    , TotalFramesReceivedCount(0)
    , TotalFramesRejectedCount(0)
    , TotalMalformedFramesCount(0)
    , TotalOversizedFramesCount(0)
    , TotalBadVersionFramesCount(0)
    , TotalDigestFailuresCount(0)
    , TotalDisconnectsCount(0)
    , TotalReconnectsCount(0)
    , LastFrameDecodeDurationMs(0.0)
    , CurrentSessionCounter(0)
{
}

FAtlasLiveTcpListener::~FAtlasLiveTcpListener()
{
    StopListener();
}

bool FAtlasLiveTcpListener::Start()
{
    if (Thread)
    {
        return true;
    }

    bStopRequested = false;
    Thread = FRunnableThread::Create(this, TEXT("AtlasLiveTcpListenerThread"), 128 * 1024, TPri_AboveNormal);
    return Thread != nullptr;
}

void FAtlasLiveTcpListener::StopListener()
{
    bStopRequested = true;
    CleanUpSockets();

    if (Thread)
    {
        Thread->WaitForCompletion();
        delete Thread;
        Thread = nullptr;
    }
}

bool FAtlasLiveTcpListener::Init()
{
    ISocketSubsystem* SocketSubsystem = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM);
    if (!SocketSubsystem)
    {
        return false;
    }

    FIPv4Address BindAddress;
    if (!FIPv4Address::Parse(BindAddressStr, BindAddress))
    {
        return false;
    }

    FIPv4Endpoint Endpoint(BindAddress, (uint16)DesiredPort);

    ListenSocket = FTcpSocketBuilder(TEXT("AtlasLiveTcpListenSocket"))
        .AsReusable()
        .BoundToEndpoint(Endpoint)
        .Listening(8);

    if (!ListenSocket)
    {
        return false;
    }

    int32 ActualPort = ListenSocket->GetPortNo();
    BoundPort.store(ActualPort, std::memory_order_relaxed);
    ConnectionState.store(EAtlasLiveConnectionState::Listening, std::memory_order_relaxed);

    return true;
}

uint32 FAtlasLiveTcpListener::Run()
{
    while (!bStopRequested)
    {
        if (!ListenSocket)
        {
            FPlatformProcess::Sleep(0.01f);
            continue;
        }

        bool bHasPendingConnection = false;
        if (ListenSocket->WaitForPendingConnection(bHasPendingConnection, FTimespan::FromMilliseconds(50)) && bHasPendingConnection)
        {
            TSharedRef<FInternetAddr> RemoteAddr = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->CreateInternetAddr();
            FSocket* ClientSocket = ListenSocket->Accept(*RemoteAddr, TEXT("AtlasLiveClientSocket"));

            if (ClientSocket)
            {
                // Enforce TCP_NODELAY
                ClientSocket->SetNoDelay(true);
                ClientSocket->SetNonBlocking(false); // Blocking with timeouts on worker thread

                ConnectionState.store(EAtlasLiveConnectionState::Connected, std::memory_order_relaxed);
                CurrentSessionCounter++;
                if (CurrentSessionCounter > 1)
                {
                    TotalReconnectsCount.fetch_add(1, std::memory_order_relaxed);
                }

                FString SessionId = FString::Printf(TEXT("tcp-session-%d"), CurrentSessionCounter);
                if (IngressQueue.IsValid())
                {
                    IngressQueue->ResetSession(SessionId);
                }

                ActiveClientSocket = ClientSocket;
                ProcessClientStream(ClientSocket);
                ActiveClientSocket = nullptr;

                ClientSocket->Close();
                ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->DestroySocket(ClientSocket);

                ConnectionState.store(EAtlasLiveConnectionState::Listening, std::memory_order_relaxed);
                TotalDisconnectsCount.fetch_add(1, std::memory_order_relaxed);
            }
        }
    }

    ConnectionState.store(EAtlasLiveConnectionState::Disconnected, std::memory_order_relaxed);
    return 0;
}

void FAtlasLiveTcpListener::Stop()
{
    bStopRequested = true;
    CleanUpSockets();
}

void FAtlasLiveTcpListener::Exit()
{
    CleanUpSockets();
}

void FAtlasLiveTcpListener::CleanUpSockets()
{
    if (ActiveClientSocket)
    {
        ActiveClientSocket->Close();
    }
    if (ListenSocket)
    {
        ListenSocket->Close();
        ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM)->DestroySocket(ListenSocket);
        ListenSocket = nullptr;
    }
}

bool FAtlasLiveTcpListener::ReadExact(FSocket* Socket, uint8* OutBuffer, int32 BytesToRead, const FTimespan& Timeout)
{
    int32 TotalRead = 0;
    double StartSeconds = FPlatformTime::Seconds();

    while (TotalRead < BytesToRead && !bStopRequested)
    {
        int32 BytesReadThisChunk = 0;
        int32 Remainder = BytesToRead - TotalRead;
        bool bSuccess = Socket->Recv(OutBuffer + TotalRead, Remainder, BytesReadThisChunk);

        if (!bSuccess)
        {
            return false;
        }

        if (BytesReadThisChunk == 0)
        {
            // Socket gracefully closed by remote peer
            return false;
        }

        TotalRead += BytesReadThisChunk;
        TotalBytesReceivedCount.fetch_add(BytesReadThisChunk, std::memory_order_relaxed);

        if (TotalRead < BytesToRead)
        {
            double Elapsed = FPlatformTime::Seconds() - StartSeconds;
            if (Elapsed > Timeout.GetTotalSeconds())
            {
                return false;
            }
            FPlatformProcess::Sleep(0.0001f);
        }
    }

    return TotalRead == BytesToRead;
}

void FAtlasLiveTcpListener::ProcessClientStream(FSocket* ClientSocket)
{
    uint8 HeaderBuffer[HeaderLength];
    TArray<uint8> PayloadBuffer;

    while (!bStopRequested)
    {
        // 1. Read 5-byte header: [uint32 payload_len][uint8 protocol_version]
        // Timeout 100ms per attempt to check bStopRequested
        if (!ReadExact(ClientSocket, HeaderBuffer, HeaderLength, FTimespan::FromMilliseconds(100)))
        {
            // Socket disconnected or stop requested
            break;
        }

        uint64 RecvCycles = FPlatformTime::Cycles64();

        // Big-endian uint32 payload length
        uint32 PayloadLen = ((uint32)HeaderBuffer[0] << 24) |
                            ((uint32)HeaderBuffer[1] << 16) |
                            ((uint32)HeaderBuffer[2] << 8) |
                            ((uint32)HeaderBuffer[3]);

        uint8 ProtocolVersion = HeaderBuffer[4];

        // Bounds checks
        if (PayloadLen == 0 || PayloadLen > MaxAllowedPayloadLength)
        {
            TotalOversizedFramesCount.fetch_add(1, std::memory_order_relaxed);
            TotalFramesRejectedCount.fetch_add(1, std::memory_order_relaxed);
            if (IngressQueue.IsValid())
            {
                IngressQueue->RecordMalformedRejection();
            }
            break; // Protocol violation -> drop connection
        }

        if (ProtocolVersion != CurrentProtocolVersion)
        {
            TotalBadVersionFramesCount.fetch_add(1, std::memory_order_relaxed);
            TotalFramesRejectedCount.fetch_add(1, std::memory_order_relaxed);
            if (IngressQueue.IsValid())
            {
                IngressQueue->RecordMalformedRejection();
            }
            break; // Protocol violation -> drop connection
        }

        // 2. Read exact payload bytes
        PayloadBuffer.SetNumUninitialized(PayloadLen);
        if (!ReadExact(ClientSocket, PayloadBuffer.GetData(), (int32)PayloadLen, FTimespan::FromSeconds(2.0)))
        {
            break; // Incomplete payload / disconnect
        }

        uint64 DecodeStartCycles = FPlatformTime::Cycles64();

        // 3. Deserialize & Validate envelope
        FAtlasLiveProductionIntent Intent;
        FString ErrorMsg;
        bool bValid = ParseAndValidateEnvelope(PayloadBuffer.GetData(), (int32)PayloadLen, Intent, ErrorMsg);

        uint64 DecodeEndCycles = FPlatformTime::Cycles64();
        double DecodeMs = FAtlasLiveIngressQueue::CyclesToMs(DecodeEndCycles - DecodeStartCycles);
        LastFrameDecodeDurationMs.store(DecodeMs, std::memory_order_relaxed);

        if (!bValid)
        {
            TotalMalformedFramesCount.fetch_add(1, std::memory_order_relaxed);
            TotalFramesRejectedCount.fetch_add(1, std::memory_order_relaxed);
            if (IngressQueue.IsValid())
            {
                IngressQueue->RecordMalformedRejection();
            }
            continue; // Continue reading stream unless framing was destroyed
        }

        TotalFramesReceivedCount.fetch_add(1, std::memory_order_relaxed);

        UE_LOG(LogAtlasTransport, Display, TEXT("Atlas Live TCP received and enqueued intent: %s, seq: %llu"),
            *Intent.IntentId, Intent.SequenceNumber);

        // Record timing
        Intent.ReceiverCycles = RecvCycles;
        Intent.ValidatedCycles = DecodeEndCycles;
        Intent.SessionId = FString::Printf(TEXT("tcp-session-%d"), CurrentSessionCounter);

        // 4. Enqueue into thread-safe ingress queue (NON-BLOCKING)
        if (IngressQueue.IsValid())
        {
            IngressQueue->Enqueue(MoveTemp(Intent));
        }
    }
}

bool FAtlasLiveTcpListener::ParseAndValidateEnvelope(
    const uint8* PayloadBytes,
    int32 PayloadLength,
    FAtlasLiveProductionIntent& OutIntent,
    FString& OutError)
{
    if (!PayloadBytes || PayloadLength <= 0)
    {
        OutError = TEXT("Empty payload bytes");
        return false;
    }

    // Convert UTF-8 bytes to FString
    FUTF8ToTCHAR Converter((const ANSICHAR*)PayloadBytes, PayloadLength);
    FString JsonString(Converter.Length(), Converter.Get());

    TSharedPtr<FJsonObject> JsonEnvelope;
    TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonString);
    if (!FJsonSerializer::Deserialize(Reader, JsonEnvelope) || !JsonEnvelope.IsValid())
    {
        OutError = TEXT("JSON deserialization failed");
        return false;
    }

    // Required envelope fields: sequence_number, sent_at_ns, digest, intent
    int64 SeqNum = 0;
    if (!JsonEnvelope->TryGetNumberField(TEXT("sequence_number"), SeqNum) || SeqNum < 1)
    {
        OutError = TEXT("Missing or invalid sequence_number");
        return false;
    }

    int64 SentAtNs = 0;
    if (!JsonEnvelope->TryGetNumberField(TEXT("sent_at_ns"), SentAtNs) || SentAtNs < 0)
    {
        OutError = TEXT("Missing or invalid sent_at_ns");
        return false;
    }

    FString DigestStr;
    if (!JsonEnvelope->TryGetStringField(TEXT("digest"), DigestStr) || DigestStr.IsEmpty())
    {
        OutError = TEXT("Missing or invalid digest");
        return false;
    }

    const TSharedPtr<FJsonObject>* IntentObjectPtr = nullptr;
    if (!JsonEnvelope->TryGetObjectField(TEXT("intent"), IntentObjectPtr) || !IntentObjectPtr || !(*IntentObjectPtr).IsValid())
    {
        OutError = TEXT("Missing or invalid intent object");
        return false;
    }
    TSharedPtr<FJsonObject> IntentObject = *IntentObjectPtr;

    // Verify SHA-256 Digest:
    // Python computes:
    // payload_bytes = json.dumps(intent.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    // header = f"{sequence_number}:{sent_at_ns}:".encode("utf-8")
    // digest = hashlib.sha256(header + payload_bytes).hexdigest()
    FString HeaderStr = FString::Printf(TEXT("%lld:%lld:"), SeqNum, SentAtNs);
    FTCHARToUTF8 HeaderUtf8(*HeaderStr);

    FString IntentJson;
    TSharedRef<TJsonWriter<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>> Writer =
        TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&IntentJson);
    FJsonSerializer::Serialize(IntentObject.ToSharedRef(), Writer);

    FTCHARToUTF8 IntentUtf8(*IntentJson);

    TArray<uint8> DigestInput;
    DigestInput.Append((const uint8*)HeaderUtf8.Get(), HeaderUtf8.Length());
    DigestInput.Append((const uint8*)IntentUtf8.Get(), IntentUtf8.Length());

    FString ExpectedDigest = ComputeSha256Hex(DigestInput.GetData(), DigestInput.Num());

    if (DigestStr.ToLower() != ExpectedDigest)
    {
        OutError = FString::Printf(TEXT("Digest mismatch: received %s != computed %s"), *DigestStr, *ExpectedDigest);
        return false;
    }

    // Populate OutIntent from IntentObject
    FString IntentId;
    if (!IntentObject->TryGetStringField(TEXT("intent_id"), IntentId) || IntentId.IsEmpty())
    {
        OutError = TEXT("Missing or empty intent_id");
        return false;
    }

    FString TreatmentStr;
    IntentObject->TryGetStringField(TEXT("treatment"), TreatmentStr);
    EAtlasLiveTreatment Treatment = EAtlasLiveTreatment::Unknown;
    if (TreatmentStr == TEXT("impact_accent")) Treatment = EAtlasLiveTreatment::ImpactAccent;
    else if (TreatmentStr == TEXT("speed_trail")) Treatment = EAtlasLiveTreatment::SpeedTrail;
    else if (TreatmentStr == TEXT("ball_highlight")) Treatment = EAtlasLiveTreatment::BallHighlight;
    else if (TreatmentStr == TEXT("player_card")) Treatment = EAtlasLiveTreatment::PlayerCard;
    else if (TreatmentStr == TEXT("cinematic_punch")) Treatment = EAtlasLiveTreatment::CinematicPunch;
    else if (TreatmentStr == TEXT("impact_frame")) Treatment = EAtlasLiveTreatment::ImpactFrame;

    FString SourceEventId;
    IntentObject->TryGetStringField(TEXT("source_event_id"), SourceEventId);

    TArray<FString> TargetEntityIds;
    const TArray<TSharedPtr<FJsonValue>>* EntitiesArray = nullptr;
    if (IntentObject->TryGetArrayField(TEXT("target_entity_ids"), EntitiesArray) && EntitiesArray)
    {
        for (const auto& Val : *EntitiesArray)
        {
            TargetEntityIds.Add(Val->AsString());
        }
    }

    double Intensity = 0.0;
    IntentObject->TryGetNumberField(TEXT("intensity"), Intensity);

    int32 DurationMs = 0;
    IntentObject->TryGetNumberField(TEXT("duration_ms"), DurationMs);

    int64 TimestampNs = 0;
    IntentObject->TryGetNumberField(TEXT("timestamp_ns"), TimestampNs);

    // In Unreal Engine, 1 unit = 1 centimeter (UU).
    // Atlas canonical spatial units are meters.
    // Convert canonical meters to Unreal centimeters:
    constexpr double MetersToCm = 100.0;

    FVector Origin = FVector::ZeroVector;
    const TSharedPtr<FJsonObject>* OriginObj = nullptr;
    if (IntentObject->TryGetObjectField(TEXT("origin"), OriginObj) && OriginObj && (*OriginObj).IsValid())
    {
        double X = 0.0, Y = 0.0, Z = 0.0;
        (*OriginObj)->TryGetNumberField(TEXT("x"), X);
        (*OriginObj)->TryGetNumberField(TEXT("y"), Y);
        (*OriginObj)->TryGetNumberField(TEXT("z"), Z);
        Origin = FVector(X * MetersToCm, Y * MetersToCm, Z * MetersToCm);
    }

    FVector Direction = FVector::ZeroVector;
    const TSharedPtr<FJsonObject>* DirObj = nullptr;
    if (IntentObject->TryGetObjectField(TEXT("direction"), DirObj) && DirObj && (*DirObj).IsValid())
    {
        double X = 0, Y = 0, Z = 0;
        (*DirObj)->TryGetNumberField(TEXT("x"), X);
        (*DirObj)->TryGetNumberField(TEXT("y"), Y);
        (*DirObj)->TryGetNumberField(TEXT("z"), Z);
        Direction = FVector(X, Y, Z);
    }

    TMap<FString, FString> Parameters;
    const TSharedPtr<FJsonObject>* ParamsObj = nullptr;
    if (IntentObject->TryGetObjectField(TEXT("parameters"), ParamsObj) && ParamsObj && (*ParamsObj).IsValid())
    {
        for (const auto& Pair : (*ParamsObj)->Values)
        {
            Parameters.Add(Pair.Key, Pair.Value->AsString());
        }
    }

    OutIntent.IntentId = IntentId;
    OutIntent.Treatment = Treatment;
    OutIntent.SourceEventId = SourceEventId;
    OutIntent.TargetEntityIds = TargetEntityIds;
    OutIntent.Intensity = (float)Intensity;
    OutIntent.DurationMs = DurationMs;
    OutIntent.Origin = Origin;
    OutIntent.Direction = Direction;
    OutIntent.Parameters = Parameters;
    OutIntent.SourceTimestampNs = TimestampNs;
    OutIntent.TransportSentAtNs = SentAtNs;
    OutIntent.SequenceNumber = (uint64)SeqNum;

    return true;
}

FAtlasLiveTcpTelemetry FAtlasLiveTcpListener::GetTelemetry() const
{
    FAtlasLiveTcpTelemetry Telemetry;
    Telemetry.ConnectionState = ConnectionState.load(std::memory_order_relaxed);
    Telemetry.BoundPort = BoundPort;
    Telemetry.TotalBytesReceived = TotalBytesReceivedCount.load(std::memory_order_relaxed);
    Telemetry.TotalFramesReceived = TotalFramesReceivedCount.load(std::memory_order_relaxed);
    Telemetry.TotalFramesRejected = TotalFramesRejectedCount.load(std::memory_order_relaxed);
    Telemetry.TotalMalformedFrames = TotalMalformedFramesCount.load(std::memory_order_relaxed);
    Telemetry.TotalOversizedFrames = TotalOversizedFramesCount.load(std::memory_order_relaxed);
    Telemetry.TotalBadVersionFrames = TotalBadVersionFramesCount.load(std::memory_order_relaxed);
    Telemetry.TotalDigestFailures = TotalDigestFailuresCount.load(std::memory_order_relaxed);
    Telemetry.TotalDisconnects = TotalDisconnectsCount.load(std::memory_order_relaxed);
    Telemetry.TotalReconnects = TotalReconnectsCount.load(std::memory_order_relaxed);
    Telemetry.LastFrameDecodeDurationMs = LastFrameDecodeDurationMs.load(std::memory_order_relaxed);
    return Telemetry;
}
