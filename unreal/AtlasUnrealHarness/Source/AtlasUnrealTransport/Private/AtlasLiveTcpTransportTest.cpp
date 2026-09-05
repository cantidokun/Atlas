#include "Misc/AutomationTest.h"
#include "AtlasLiveIngressQueue.h"
#include "AtlasLiveTcpListener.h"
#include "AtlasLiveGameThreadPump.h"
#include "GenericPlatform/GenericPlatformMisc.h"
#include "Sockets.h"
#include "SocketSubsystem.h"
#include "Common/TcpSocketBuilder.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasLiveTcpTransportTest,
    "Atlas.Live.Transport.TcpIntegration",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

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

    class FMockDispatcher : public IAtlasLiveEffectDispatcher
    {
    public:
        TArray<FAtlasLiveProductionIntent> Dispatched;

        virtual bool DispatchIntent(const FAtlasLiveProductionIntent& Intent) override
        {
            Dispatched.Add(Intent);
            return true;
        }
    };

    TArray<uint8> BuildFrame(
        uint64 Seq,
        int64 SentAtNs,
        const FString& IntentId,
        uint8 ProtocolVersion = 1,
        bool bCorruptDigest = false)
    {
        // Construct canonical intent json
        FString IntentJson = FString::Printf(
            TEXT(R"({"direction":null,"duration_ms":200,"intensity":0.85,"intent_id":"%s","origin":null,"parameters":{"preset":"strike_flash_v1"},"source_event_id":"evt-%s","target_entity_ids":["player-09"],"timestamp_ns":1000000,"treatment":"impact_accent"})"),
            *IntentId, *IntentId);

        // Serialize through FJsonObject so key ordering is identical
        TSharedPtr<FJsonObject> IntentObj;
        TSharedRef<TJsonReader<>> TempReader = TJsonReaderFactory<>::Create(IntentJson);
        FJsonSerializer::Deserialize(TempReader, IntentObj);

        FString CanonicalIntentJson;
        TSharedRef<TJsonWriter<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>> CanonicalWriter =
            TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&CanonicalIntentJson);
        FJsonSerializer::Serialize(IntentObj.ToSharedRef(), CanonicalWriter);

        FString HeaderStr = FString::Printf(TEXT("%lld:%lld:"), Seq, SentAtNs);
        FTCHARToUTF8 HeaderUtf8(*HeaderStr);
        FTCHARToUTF8 IntentUtf8(*CanonicalIntentJson);

        TArray<uint8> DigestInput;
        DigestInput.Append((const uint8*)HeaderUtf8.Get(), HeaderUtf8.Length());
        DigestInput.Append((const uint8*)IntentUtf8.Get(), IntentUtf8.Length());

        FString Digest = ComputeSha256Hex(DigestInput.GetData(), DigestInput.Num());

        if (bCorruptDigest)
        {
            Digest = TEXT("0000000000000000000000000000000000000000000000000000000000000000");
        }

        FString EnvelopeJson = FString::Printf(
            TEXT(R"({"digest":"%s","intent":%s,"sent_at_ns":%lld,"sequence_number":%lld})"),
            *Digest, *CanonicalIntentJson, SentAtNs, Seq);

        FTCHARToUTF8 PayloadUtf8(*EnvelopeJson);
        uint32 PayloadLen = PayloadUtf8.Length();

        TArray<uint8> Frame;
        Frame.Add((PayloadLen >> 24) & 0xFF);
        Frame.Add((PayloadLen >> 16) & 0xFF);
        Frame.Add((PayloadLen >> 8) & 0xFF);
        Frame.Add(PayloadLen & 0xFF);
        Frame.Add(ProtocolVersion);
        Frame.Append((const uint8*)PayloadUtf8.Get(), PayloadLen);

        return Frame;
    }
}

bool FAtlasLiveTcpTransportTest::RunTest(const FString& Parameters)
{
    // -------------------------------------------------------------
    // 1. Envelope parsing and digest verification unit test
    // -------------------------------------------------------------
    {
        TArray<uint8> ValidFrame = BuildFrame(1, 1000, TEXT("unit-1"));
        const uint8* PayloadBytes = ValidFrame.GetData() + 5;
        int32 PayloadLen = ValidFrame.Num() - 5;

        FAtlasLiveProductionIntent ParsedIntent;
        FString Error;
        bool bParsed = FAtlasLiveTcpListener::ParseAndValidateEnvelope(PayloadBytes, PayloadLen, ParsedIntent, Error);
        if (!bParsed)
        {
            AddError(FString::Printf(TEXT("Envelope parse error: %s"), *Error));
        }
        TestTrue(TEXT("Valid envelope parsed and verified"), bParsed);
        TestEqual(TEXT("Parsed Intent ID matches"), ParsedIntent.IntentId, FString(TEXT("unit-1")));
        TestEqual(TEXT("Parsed sequence number matches"), ParsedIntent.SequenceNumber, (uint64)1);
        TestEqual(TEXT("Parsed treatment matches"), ParsedIntent.Treatment, EAtlasLiveTreatment::ImpactAccent);

        // Corrupted digest
        TArray<uint8> CorruptFrame = BuildFrame(2, 1000, TEXT("unit-corrupt"), 1, true);
        bParsed = FAtlasLiveTcpListener::ParseAndValidateEnvelope(CorruptFrame.GetData() + 5, CorruptFrame.Num() - 5, ParsedIntent, Error);
        TestFalse(TEXT("Corrupted digest rejected"), bParsed);
        TestTrue(TEXT("Digest error message populated"), Error.Contains(TEXT("Digest mismatch")));
    }

    // -------------------------------------------------------------
    // 2. Real localhost TCP Listener Integration Test
    // -------------------------------------------------------------
    {
        TSharedPtr<FAtlasLiveIngressQueue> Queue = MakeShared<FAtlasLiveIngressQueue>(64);
        TSharedPtr<FMockDispatcher> Dispatcher = MakeShared<FMockDispatcher>();
        FAtlasLiveGameThreadPump Pump(Queue, Dispatcher, 16);

        // Bind dynamic port on 127.0.0.1
        TSharedPtr<FAtlasLiveTcpListener> Listener = MakeShared<FAtlasLiveTcpListener>(Queue, 0, TEXT("127.0.0.1"));
        TestTrue(TEXT("TCP Listener starts"), Listener->Start());

        // Wait up to 500ms for listener thread to initialize and bind port
        int32 Port = 0;
        for (int32 WaitIdx = 0; WaitIdx < 50; ++WaitIdx)
        {
            Port = Listener->GetBoundPort();
            if (Port > 0)
            {
                break;
            }
            FPlatformProcess::Sleep(0.01f);
        }
        TestTrue(TEXT("Port bound > 0"), Port > 0);

        // Create client socket and connect
        ISocketSubsystem* SocketSubsystem = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM);
        TSharedRef<FInternetAddr> TargetAddr = SocketSubsystem->CreateInternetAddr();
        bool bIsValidIp = false;
        TargetAddr->SetIp(TEXT("127.0.0.1"), bIsValidIp);
        TargetAddr->SetPort(Port);

        FSocket* ClientSocket = FTcpSocketBuilder(TEXT("AtlasTestClientSocket"))
            .AsBlocking()
            .Build();

        TestTrue(TEXT("Client socket created"), ClientSocket != nullptr);
        bool bConnected = ClientSocket->Connect(*TargetAddr);
        TestTrue(TEXT("Client socket connected to listener"), bConnected);

        // Allow listener to accept connection
        FPlatformProcess::Sleep(0.05f);
        TestEqual(TEXT("Listener reports Connected state"), Listener->GetConnectionState(), EAtlasLiveConnectionState::Connected);

        // A. Send valid frame
        TArray<uint8> Frame1 = BuildFrame(1, 1000, TEXT("net-1"));
        int32 BytesSent = 0;
        ClientSocket->Send(Frame1.GetData(), Frame1.Num(), BytesSent);
        TestEqual(TEXT("Sent full frame 1"), BytesSent, Frame1.Num());

        // Wait for receiver thread to process
        for (int32 WaitIdx = 0; WaitIdx < 50; ++WaitIdx)
        {
            if (Queue->GetDepth() > 0)
            {
                break;
            }
            FPlatformProcess::Sleep(0.01f);
        }

        // Pump GameThread
        Pump.Tick(0.016f);
        TestEqual(TEXT("Queue depth 0 after pump"), Queue->GetDepth(), 0);
        TestEqual(TEXT("Dispatcher received 1 intent"), Dispatcher->Dispatched.Num(), 1);
        if (Dispatcher->Dispatched.Num() > 0)
        {
            TestEqual(TEXT("Dispatched Intent ID is net-1"), Dispatcher->Dispatched[0].IntentId, FString(TEXT("net-1")));
        }

        // B. Send partial frame then complete frame in chunks
        TArray<uint8> Frame2 = BuildFrame(2, 2000, TEXT("net-2"));
        int32 HalfLen = Frame2.Num() / 2;
        ClientSocket->Send(Frame2.GetData(), HalfLen, BytesSent);
        FPlatformProcess::Sleep(0.02f);
        Pump.Tick(0.016f);
        TestEqual(TEXT("Dispatcher still has 1 while partial frame in flight"), Dispatcher->Dispatched.Num(), 1);

        ClientSocket->Send(Frame2.GetData() + HalfLen, Frame2.Num() - HalfLen, BytesSent);
        for (int32 WaitIdx = 0; WaitIdx < 50; ++WaitIdx)
        {
            if (Queue->GetDepth() > 0)
            {
                break;
            }
            FPlatformProcess::Sleep(0.01f);
        }
        Pump.Tick(0.016f);
        TestEqual(TEXT("Dispatcher has 2 after second chunk delivered"), Dispatcher->Dispatched.Num(), 2);
        if (Dispatcher->Dispatched.Num() > 1)
        {
            TestEqual(TEXT("Dispatched Intent ID is net-2"), Dispatcher->Dispatched[1].IntentId, FString(TEXT("net-2")));
        }

        // C. Send multiple frames in a single TCP send
        TArray<uint8> MultiFrames;
        TArray<uint8> Frame3 = BuildFrame(3, 3000, TEXT("net-3"));
        TArray<uint8> Frame4 = BuildFrame(4, 4000, TEXT("net-4"));
        MultiFrames.Append(Frame3);
        MultiFrames.Append(Frame4);
        ClientSocket->Send(MultiFrames.GetData(), MultiFrames.Num(), BytesSent);

        for (int32 WaitIdx = 0; WaitIdx < 50; ++WaitIdx)
        {
            if (Queue->GetDepth() >= 2)
            {
                break;
            }
            FPlatformProcess::Sleep(0.01f);
        }
        Pump.Tick(0.016f);
        TestEqual(TEXT("Dispatcher received both frames from concatenated buffer"), Dispatcher->Dispatched.Num(), 4);
        if (Dispatcher->Dispatched.Num() >= 4)
        {
            TestEqual(TEXT("Intent 3 is net-3"), Dispatcher->Dispatched[2].IntentId, FString(TEXT("net-3")));
            TestEqual(TEXT("Intent 4 is net-4"), Dispatcher->Dispatched[3].IntentId, FString(TEXT("net-4")));
        }

        // Reconnect and Session Reset
        ClientSocket->Close();
        SocketSubsystem->DestroySocket(ClientSocket);
        FPlatformProcess::Sleep(0.05f);

        TestEqual(TEXT("Disconnect recorded in telemetry"), Listener->GetTelemetry().TotalDisconnects, (int64)1);

        // Connect a new client socket
        FSocket* ClientSocket2 = FTcpSocketBuilder(TEXT("AtlasTestClientSocket2"))
            .AsBlocking()
            .Build();
        TestTrue(TEXT("Reconnecting client socket connects"), ClientSocket2->Connect(*TargetAddr));
        FPlatformProcess::Sleep(0.05f);

        // Sequence resets to 1 in new session
        TArray<uint8> FrameNewSession = BuildFrame(1, 5000, TEXT("new-session-1"));
        ClientSocket2->Send(FrameNewSession.GetData(), FrameNewSession.Num(), BytesSent);
        for (int32 WaitIdx = 0; WaitIdx < 50; ++WaitIdx)
        {
            if (Queue->GetDepth() > 0)
            {
                break;
            }
            FPlatformProcess::Sleep(0.01f);
        }

        Pump.Tick(0.016f);
        TestEqual(TEXT("Dispatcher received intent from reconnected session"), Dispatcher->Dispatched.Num(), 5);
        if (Dispatcher->Dispatched.Num() >= 5)
        {
            TestEqual(TEXT("Intent ID matches new session"), Dispatcher->Dispatched[4].IntentId, FString(TEXT("new-session-1")));
        }

        ClientSocket2->Close();
        SocketSubsystem->DestroySocket(ClientSocket2);

        // Verify telemetry on listener
        FAtlasLiveTcpTelemetry Telemetry = Listener->GetTelemetry();
        TestTrue(TEXT("Telemetry TotalBytesReceived > 0"), Telemetry.TotalBytesReceived > 0);
        TestTrue(TEXT("Telemetry TotalFramesReceived >= 5"), Telemetry.TotalFramesReceived >= 5);
        TestEqual(TEXT("Telemetry TotalReconnects == 1"), Telemetry.TotalReconnects, (int64)1);

        // Stop listener
        Listener->StopListener();
    }

    return !HasAnyErrors();
}
