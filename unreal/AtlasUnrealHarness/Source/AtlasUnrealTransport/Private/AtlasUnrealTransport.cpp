#include "AtlasUnrealTransport.h"
#include "AtlasTransportServer.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "LevelSequence.h"
#include "LevelSequenceActor.h"
#include "MovieScene.h"
#include "Modules/ModuleManager.h"
#include "GameFramework/Actor.h"

DEFINE_LOG_CATEGORY(LogAtlasTransport);

namespace
{
    const FName SequencerFixtureTag(TEXT("atlas_sequencer_fixture"));
    const FName SequencerFixtureActorName(TEXT("AtlasSequencerFixture"));
    constexpr int32 DefaultSequencerStartFrame = 0;
    constexpr int32 DefaultSequencerEndFrame = 100;
}

void FAtlasUnrealTransportModule::StartupModule()
{
    UE_LOG(LogAtlasTransport, Log, TEXT("AtlasUnrealTransport module starting up"));

    TransportServer = new FAtlasTransportServer();
    if (!TransportServer->StartServer())
    {
        UE_LOG(LogAtlasTransport, Error, TEXT("Failed to start Atlas transport server"));
        delete TransportServer;
        TransportServer = nullptr;
    }
    else
    {
        UE_LOG(LogAtlasTransport, Log, TEXT("Atlas transport server started successfully"));
    }

    // The transport module may load before the editor has finished constructing
    // its active world. Keep retrying until actors are initialized, then create
    // the deterministic fixture. Sequencer inspection itself remains read-only.
    SequencerFixtureTickerHandle = FTSTicker::GetCoreTicker().AddTicker(
        FTickerDelegate::CreateRaw(this, &FAtlasUnrealTransportModule::EnsureSequencerFixture),
        0.25f);
}

bool FAtlasUnrealTransportModule::EnsureSequencerFixture(float DeltaTime)
{
    if (!IsInGameThread() || !GEngine || IsEngineExitRequested())
    {
        return true;
    }

    UWorld* World = nullptr;
    for (const FWorldContext& Context : GEngine->GetWorldContexts())
    {
        UWorld* Candidate = Context.World();
        if (Candidate && IsValid(Candidate))
        {
            World = Candidate;
            break;
        }
    }

    if (!World)
    {
        return true;
    }

    // Do not attempt to spawn actors while the world is still being initialized.
    // The ticker will invoke us again once the editor world is ready.
    if (!World->AreActorsInitialized())
    {
        return true;
    }

    ALevelSequenceActor* FixtureActor = nullptr;

    // Reuse an existing fixture when possible. This also repairs a stale fixture
    // actor that survived a hot reload but lost its transient sequence object.
    for (TActorIterator<ALevelSequenceActor> It(World); It; ++It)
    {
        ALevelSequenceActor* ExistingActor = *It;
        if (ExistingActor &&
            IsValid(ExistingActor) &&
            ExistingActor->ActorHasTag(SequencerFixtureTag))
        {
            FixtureActor = ExistingActor;
            break;
        }
    }

    if (!FixtureActor)
    {
        FActorSpawnParameters SpawnParams;
        SpawnParams.Name = SequencerFixtureActorName;
        SpawnParams.NameMode = FActorSpawnParameters::ESpawnActorNameMode::Requested;
        SpawnParams.ObjectFlags |= RF_Transient;

        FixtureActor = World->SpawnActor<ALevelSequenceActor>(
            ALevelSequenceActor::StaticClass(),
            FTransform::Identity,
            SpawnParams);

        if (!FixtureActor)
        {
            UE_LOG(
                LogAtlasTransport,
                Warning,
                TEXT("Unable to create Atlas Sequencer fixture actor in world '%s'; will retry"),
                *World->GetName());
            return true;
        }

        FixtureActor->Tags.AddUnique(SequencerFixtureTag);
        FixtureActor->SetActorLabel(TEXT("Atlas Sequencer Fixture"));
    }

    ULevelSequence* Sequence = FixtureActor->GetSequence();
    if (!Sequence)
    {
        Sequence = NewObject<ULevelSequence>(
            FixtureActor,
            TEXT("AtlasSequencerFixtureSequence"),
            RF_Transient);

        if (!Sequence)
        {
            UE_LOG(
                LogAtlasTransport,
                Warning,
                TEXT("Unable to create Atlas Sequencer fixture sequence in world '%s'; will retry"),
                *World->GetName());
            return true;
        }

        Sequence->Initialize();
        FixtureActor->SetSequence(Sequence);
    }

    UMovieScene* MovieScene = Sequence->GetMovieScene();
    if (!MovieScene)
    {
        UE_LOG(
            LogAtlasTransport,
            Warning,
            TEXT("Atlas Sequencer fixture has no MovieScene in world '%s'; will retry"),
            *World->GetName());
        return true;
    }

    // Normalize the deterministic fixture range on every successful startup.
    // This makes hot reloads and editor restarts converge to the same baseline.
    MovieScene->SetPlaybackRange(
        TRange<FFrameNumber>(
            FFrameNumber(DefaultSequencerStartFrame),
            FFrameNumber(DefaultSequencerEndFrame)));

    FixtureActor->SetSequence(Sequence);
    FixtureActor->MarkPackageDirty();

    UE_LOG(
        LogAtlasTransport,
        Log,
        TEXT("Atlas Sequencer fixture ready in world '%s' with playback range %d-%d"),
        *World->GetName(),
        DefaultSequencerStartFrame,
        DefaultSequencerEndFrame);

    return false;
}

void FAtlasUnrealTransportModule::ShutdownModule()
{
    UE_LOG(LogAtlasTransport, Log, TEXT("AtlasUnrealTransport module shutting down"));

    if (SequencerFixtureTickerHandle.IsValid())
    {
        FTSTicker::GetCoreTicker().RemoveTicker(SequencerFixtureTickerHandle);
        SequencerFixtureTickerHandle.Reset();
    }

    if (TransportServer)
    {
        TransportServer->StopServer();
        delete TransportServer;
        TransportServer = nullptr;
    }

    UE_LOG(LogAtlasTransport, Log, TEXT("AtlasUnrealTransport module shutdown complete"));
}

IMPLEMENT_MODULE(FAtlasUnrealTransportModule, AtlasUnrealTransport)
