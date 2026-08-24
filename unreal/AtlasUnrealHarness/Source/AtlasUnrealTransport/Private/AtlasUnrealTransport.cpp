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

    // The transport module can load before the editor has established its active
    // world. Defer fixture creation until a valid world exists so Sequencer
    // inspection remains a read-only operation and never creates missing state.
    SequencerFixtureTickerHandle = FTSTicker::GetCoreTicker().AddTicker(
        FTickerDelegate::CreateRaw(this, &FAtlasUnrealTransportModule::EnsureSequencerFixture),
        0.25f);
}

bool FAtlasUnrealTransportModule::EnsureSequencerFixture(float DeltaTime)
{
    if (!IsInGameThread())
    {
        return true;
    }

    if (!GEngine || IsEngineExitRequested())
    {
        return true;
    }

    UWorld* World = nullptr;
    for (const FWorldContext& Context : GEngine->GetWorldContexts())
    {
        if (Context.World() && IsValid(Context.World()))
        {
            World = Context.World();
            break;
        }
    }

    if (!World)
    {
        return true;
    }

    for (TActorIterator<ALevelSequenceActor> It(World); It; ++It)
    {
        ALevelSequenceActor* ExistingActor = *It;
        if (ExistingActor && IsValid(ExistingActor) && ExistingActor->ActorHasTag(SequencerFixtureTag) && ExistingActor->GetSequence())
        {
            ULevelSequence* ExistingSequence = ExistingActor->GetSequence();
            if (ExistingSequence && ExistingSequence->GetMovieScene())
            {
                return false;
            }
        }
    }

    FActorSpawnParameters SpawnParams;
    SpawnParams.Name = SequencerFixtureActorName;
    SpawnParams.NameMode = FActorSpawnParameters::ESpawnActorNameMode::Requested;
    SpawnParams.ObjectFlags |= RF_Transient;

    ALevelSequenceActor* SequenceActor = World->SpawnActor<ALevelSequenceActor>(
        ALevelSequenceActor::StaticClass(),
        FTransform::Identity,
        SpawnParams);

    if (!SequenceActor)
    {
        UE_LOG(LogAtlasTransport, Warning, TEXT("Unable to create Atlas Sequencer fixture actor; will retry"));
        return true;
    }

    SequenceActor->Tags.AddUnique(SequencerFixtureTag);
    SequenceActor->SetActorLabel(TEXT("Atlas Sequencer Fixture"));

    ULevelSequence* Sequence = NewObject<ULevelSequence>(
        SequenceActor,
        TEXT("AtlasSequencerFixtureSequence"),
        RF_Transient);

    if (!Sequence)
    {
        SequenceActor->Destroy();
        UE_LOG(LogAtlasTransport, Warning, TEXT("Unable to create Atlas Sequencer fixture sequence; will retry"));
        return true;
    }

    Sequence->Initialize();
    UMovieScene* MovieScene = Sequence->GetMovieScene();
    if (!MovieScene)
    {
        SequenceActor->Destroy();
        UE_LOG(LogAtlasTransport, Warning, TEXT("Unable to initialize Atlas Sequencer fixture MovieScene; will retry"));
        return true;
    }

    MovieScene->SetPlaybackRange(
        TRange<FFrameNumber>(
            FFrameNumber(DefaultSequencerStartFrame),
            FFrameNumber(DefaultSequencerEndFrame)));

    SequenceActor->SetSequence(Sequence);
    SequenceActor->MarkPackageDirty();

    UE_LOG(
        LogAtlasTransport,
        Log,
        TEXT("Created deterministic Atlas Sequencer fixture in world '%s' with playback range %d-%d"),
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
