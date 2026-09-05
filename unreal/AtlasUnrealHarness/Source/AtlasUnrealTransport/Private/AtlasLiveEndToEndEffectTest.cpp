#include "Misc/AutomationTest.h"
#include "AtlasLiveEffectRegistry.h"
#include "AtlasLiveImpactAccentHandler.h"
#include "AtlasLiveIngressQueue.h"
#include "AtlasLiveGameThreadPump.h"
#include "AtlasLiveTcpListener.h"
#include "Common/TcpSocketBuilder.h"
#include "Engine/World.h"
#include "Editor.h"
#include "GameFramework/Actor.h"
#include "Components/PointLightComponent.h"
#include "SocketSubsystem.h"

#if PLATFORM_WINDOWS
#include "Windows/AllowWindowsPlatformTypes.h"
#include <bcrypt.h>
#include "Windows/HideWindowsPlatformTypes.h"
#endif

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasLiveEndToEndEffectTest,
    "Atlas.Live.Integration.EndToEndVisualEffectProof",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

namespace
{
    FString ComputeSha256HexLocal(const uint8* Data, int32 Length)
    {
#if PLATFORM_WINDOWS
        BCRYPT_ALG_HANDLE AlgHandle = NULL;
        BCRYPT_HASH_HANDLE HashHandle = NULL;
        NTSTATUS Status = BCryptOpenAlgorithmProvider(&AlgHandle, BCRYPT_SHA256_ALGORITHM, NULL, 0);
        if (!BCRYPT_SUCCESS(Status)) return FString();
        Status = BCryptCreateHash(AlgHandle, &HashHandle, NULL, 0, NULL, 0, 0);
        if (!BCRYPT_SUCCESS(Status)) { BCryptCloseAlgorithmProvider(AlgHandle, 0); return FString(); }
        Status = BCryptHashData(HashHandle, (UCHAR*)Data, Length, 0);
        uint8 HashBytes[32] = {0};
        if (BCRYPT_SUCCESS(Status)) BCryptFinishHash(HashHandle, HashBytes, sizeof(HashBytes), 0);
        BCryptDestroyHash(HashHandle);
        BCryptCloseAlgorithmProvider(AlgHandle, 0);
        return BytesToHex(HashBytes, sizeof(HashBytes)).ToLower();
#else
        return FString();
#endif
    }

    TArray<uint8> BuildStrikeFrame(uint64 Seq, int64 SentAtNs, const FString& IntentId, const FString& TargetEntity)
    {
        // Canonical origin in meters: (1.0m, 0.0m, 0.15m) -> converts to (100.0cm, 0.0cm, 15.0cm) in Unreal
        FString IntentJson = FString::Printf(
            TEXT(R"({"direction":{"x":1.0,"y":0.0,"z":0.0},"duration_ms":200,"intensity":0.9,"intent_id":"%s","origin":{"x":1.0,"y":0.0,"z":0.15},"parameters":{"preset":"strike_flash_v1"},"source_event_id":"evt-%s","target_entity_ids":["%s"],"timestamp_ns":1000000,"treatment":"impact_accent"})"),
            *IntentId, *IntentId, *TargetEntity);

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

        FString Digest = ComputeSha256HexLocal(DigestInput.GetData(), DigestInput.Num());

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
        Frame.Add(1); // Protocol version 1
        Frame.Append((const uint8*)PayloadUtf8.Get(), PayloadLen);

        return Frame;
    }
}

bool FAtlasLiveEndToEndEffectTest::RunTest(const FString& Parameters)
{
    UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
    TestNotNull(TEXT("Editor world available"), World);
    if (!World)
    {
        return false;
    }

    // 1. Get or create target Ball fixture in World
    AActor* BallActor = FAtlasLiveEffectRegistry::FindTargetActor(TEXT("ball"));
    if (!BallActor)
    {
        FActorSpawnParameters SpawnParams;
        SpawnParams.ObjectFlags |= RF_Transient;
        BallActor = World->SpawnActor<AActor>(AActor::StaticClass(), FTransform(FVector(100.0f, 0.0f, 15.0f)), SpawnParams);
        USceneComponent* BallRoot = NewObject<USceneComponent>(BallActor, TEXT("LiveProofBallRoot"));
        BallActor->SetRootComponent(BallRoot);
        BallRoot->RegisterComponent();
        BallActor->Tags.AddUnique(FName(TEXT("atlas_entity:ball")));
    }
    TestNotNull(TEXT("Target Ball actor available"), BallActor);
    if (!BallActor)
    {
        return false;
    }

    // 2. Set up Live pipeline: Queue -> Registry -> Pump -> TCP Listener
    TSharedPtr<FAtlasLiveIngressQueue> Queue = MakeShared<FAtlasLiveIngressQueue>(64);
    TSharedPtr<FAtlasLiveEffectRegistry> Registry = MakeShared<FAtlasLiveEffectRegistry>(500.0);
    TSharedPtr<FAtlasLiveImpactAccentHandler> ImpactHandler = MakeShared<FAtlasLiveImpactAccentHandler>();
    Registry->RegisterHandler(EAtlasLiveTreatment::ImpactAccent, TEXT("strike_flash_v1"), ImpactHandler);
    Registry->RegisterHandler(EAtlasLiveTreatment::ImpactAccent, TEXT(""), ImpactHandler);

    FAtlasLiveGameThreadPump Pump(Queue, Registry, 16);

    TSharedPtr<FAtlasLiveTcpListener> Listener = MakeShared<FAtlasLiveTcpListener>(Queue, 0, TEXT("127.0.0.1"));
    TestTrue(TEXT("Live TCP Listener started"), Listener->Start());

    int32 Port = 0;
    for (int32 WaitIdx = 0; WaitIdx < 50; ++WaitIdx)
    {
        Port = Listener->GetBoundPort();
        if (Port > 0) break;
        FPlatformProcess::Sleep(0.01f);
    }
    TestTrue(TEXT("TCP Listener bound port > 0"), Port > 0);

    // 3. Connect client TCP socket
    ISocketSubsystem* SocketSubsystem = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM);
    TSharedRef<FInternetAddr> TargetAddr = SocketSubsystem->CreateInternetAddr();
    bool bIsValidIp = false;
    TargetAddr->SetIp(TEXT("127.0.0.1"), bIsValidIp);
    TargetAddr->SetPort(Port);

    FSocket* ClientSocket = FTcpSocketBuilder(TEXT("AtlasLiveProofClient"))
        .AsBlocking()
        .Build();
    TestTrue(TEXT("Client socket connects to listener"), ClientSocket->Connect(*TargetAddr));

    FPlatformProcess::Sleep(0.05f);

    // 4. Send BALL_STRIKE -> IMPACT_ACCENT intent over TCP
    TArray<uint8> StrikeFrame = BuildStrikeFrame(1, 1000000, TEXT("intent-strike-proof-01"), TEXT("ball"));
    int32 BytesSent = 0;
    ClientSocket->Send(StrikeFrame.GetData(), StrikeFrame.Num(), BytesSent);
    TestEqual(TEXT("Sent full strike frame over TCP"), BytesSent, StrikeFrame.Num());

    // Wait for TCP receiver thread to parse, validate, and enqueue
    for (int32 WaitIdx = 0; WaitIdx < 50; ++WaitIdx)
    {
        if (Queue->GetDepth() > 0) break;
        FPlatformProcess::Sleep(0.01f);
    }
    TestEqual(TEXT("Queue depth is 1 after TCP receive"), Queue->GetDepth(), 1);

    // 5. GameThread Pump ticks: dequeues and dispatches to registry
    Pump.Tick(0.016f);
    TestEqual(TEXT("Queue depth 0 after GameThread pump"), Queue->GetDepth(), 0);

    // 6. VERIFY REAL EFFECT ON TARGET ACTOR:
    // A. Actor has active tag: atlas_vfx_active:impact_accent:intent-strike-proof-01
    TestTrue(TEXT("Target Ball actor has active impact accent tag"),
        FAtlasLiveImpactAccentHandler::HasActiveImpactAccent(BallActor));
    TestEqual(TEXT("Active intent ID on Ball matches"),
        FAtlasLiveImpactAccentHandler::GetActiveImpactIntentId(BallActor),
        FString(TEXT("intent-strike-proof-01")));

    // B. PointLightComponent is attached to Ball
    TArray<UActorComponent*> AttachedLights = BallActor->GetComponentsByTag(
        UPointLightComponent::StaticClass(),
        FAtlasLiveImpactAccentHandler::ImpactAccentComponentTag);
    TestEqual(TEXT("Exactly 1 transient impact light component attached to Ball"), AttachedLights.Num(), 1);

    if (AttachedLights.Num() > 0)
    {
        UPointLightComponent* Light = Cast<UPointLightComponent>(AttachedLights[0]);
        TestNotNull(TEXT("Light component is valid UPointLightComponent"), Light);
        if (Light)
        {
            TestTrue(TEXT("Light intensity is active (> 0)"), Light->Intensity > 0.0f);
        }
    }

    // 7. VERIFY CLEANUP:
    // Tick registry with delta time exceeding duration (200ms)
    FPlatformProcess::Sleep(0.25f);
    Registry->TickActiveEffects(0.25f);

    TestFalse(TEXT("Target Ball actor no longer has active impact accent tag after expiration"),
        FAtlasLiveImpactAccentHandler::HasActiveImpactAccent(BallActor));

    TArray<UActorComponent*> PostCleanupLights = BallActor->GetComponentsByTag(
        UPointLightComponent::StaticClass(),
        FAtlasLiveImpactAccentHandler::ImpactAccentComponentTag);
    TestEqual(TEXT("Light component destroyed on Ball actor after expiration"), PostCleanupLights.Num(), 0);

    // Clean up
    ClientSocket->Close();
    SocketSubsystem->DestroySocket(ClientSocket);
    Listener->StopListener();

    return !HasAnyErrors();
}
