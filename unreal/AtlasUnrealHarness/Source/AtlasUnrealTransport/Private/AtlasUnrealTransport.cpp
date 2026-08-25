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
#include "Components/SceneComponent.h"
#include "Editor.h"

DEFINE_LOG_CATEGORY(LogAtlasTransport);

namespace
{
    const FName FieldFixtureTag(TEXT("atlas_entity:FIELD_SURFACE"));
    const FName FieldFixtureActorName(TEXT("AtlasFieldSurfaceFixture"));
    const FName SequencerFixtureTag(TEXT("atlas_sequencer_fixture"));
    const FName SequencerFixtureActorName(TEXT("AtlasSequencerFixture"));
    const FName SequencerFixtureSequenceName(TEXT("AtlasSequencerFixtureSequence"));
    constexpr int32 DefaultSequencerStartFrame = 0;
    constexpr int32 DefaultSequencerEndFrame = 100;

    UWorld* GetActiveEditorWorld()
    {
        if (GEditor)
        {
            UWorld* EditorWorld = GEditor->GetEditorWorldContext().World();
            if (EditorWorld && IsValid(EditorWorld))
            {
                return EditorWorld;
            }
        }

        if (GEngine)
        {
            for (const FWorldContext& Context : GEngine->GetWorldContexts())
            {
                UWorld* Candidate = Context.World();
                if (Candidate && IsValid(Candidate))
                {
                    return Candidate;
                }
            }
        }

        return nullptr;
    }
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

    // The module can load before the editor world exists. Keep this ticker alive
    // until a valid editor world is available and all deterministic fixtures are
    // fully usable. The fixtures are transient and do not modify the user's level asset.
    SequencerFixtureTickerHandle = FTSTicker::GetCoreTicker().AddTicker(
        FTickerDelegate::CreateRaw(this, &FAtlasUnrealTransportModule::EnsureSequencerFixture),
        0.10f);
}

bool FAtlasUnrealTransportModule::EnsureSequencerFixture(float DeltaTime)
{
    if (!IsInGameThread() || !GEngine || IsEngineExitRequested())
    {
        return true;
    }

    UWorld* World = GetActiveEditorWorld();
    if (!World)
    {
        return true;
    }

    // Create the deterministic transform fixture used by the live production
    // integration gates. Reuse an existing tagged actor if the fixture already exists.
    AActor* FieldFixtureActor = nullptr;
    for (TActorIterator<AActor> It(World); It; ++It)
    {
        AActor* ExistingActor = *It;
        if (ExistingActor && IsValid(ExistingActor) && ExistingActor->ActorHasTag(FieldFixtureTag))
        {
            FieldFixtureActor = ExistingActor;
            break;
        }
    }

    if (!FieldFixtureActor)
    {
        FActorSpawnParameters SpawnParams;
        SpawnParams.Name = FieldFixtureActorName;
        SpawnParams.NameMode = FActorSpawnParameters::ESpawnActorNameMode::Requested;
        SpawnParams.ObjectFlags |= RF_Transient;

        FieldFixtureActor = World->SpawnActor<AActor>(
            AActor::StaticClass(),
            FTransform::Identity,
            SpawnParams);

        if (!FieldFixtureActor)
        {
            UE_LOG(
                LogAtlasTransport,
                Warning,
                TEXT("Unable to create Atlas FIELD_SURFACE fixture actor in world '%s'; will retry"),
                *World->GetName());
            return true;
        }

        USceneComponent* RootComponent = NewObject<USceneComponent>(
            FieldFixtureActor,
            TEXT("AtlasFieldSurfaceFixtureRoot"));
        if (!RootComponent)
        {
            FieldFixtureActor->Destroy();
            UE_LOG(
                LogAtlasTransport,
                Warning,
                TEXT("Unable to create Atlas FIELD_SURFACE fixture root component in world '%s'; will retry"),
                *World->GetName());
            return true;
        }

        FieldFixtureActor->SetRootComponent(RootComponent);
        RootComponent->RegisterComponent();
        FieldFixtureActor->Tags.AddUnique(FieldFixtureTag);
        FieldFixtureActor->SetActorLabel(TEXT("Atlas Field Surface Fixture"));
    }

    if (!FieldFixtureActor->HasValidRootComponent())
    {
        UE_LOG(
            LogAtlasTransport,
            Warning,
            TEXT("Atlas FIELD_SURFACE fixture actor has no valid root component in world '%s'; will retry"),
            *World->GetName());
        return true;
    }

    // Create or reuse the deterministic Sequencer fixture used by the live gates.
    ALevelSequenceActor* FixtureActor = nullptr;

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
            SequencerFixtureSequenceName,
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

    if (FixtureActor->GetSequence() != Sequence)
    {
        FixtureActor->SetSequence(Sequence);
        if (FixtureActor->GetSequence() != Sequence)
        {
            UE_LOG(
                LogAtlasTransport,
                Warning,
                TEXT("Atlas Sequencer fixture actor could not retain its sequence in world '%s'; will retry"),
                *World->GetName());
            return true;
        }
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

    MovieScene->SetPlaybackRange(
        TRange<FFrameNumber>(
            FFrameNumber(DefaultSequencerStartFrame),
            FFrameNumber(DefaultSequencerEndFrame)));

    FixtureActor->SetSequence(Sequence);
    FixtureActor->MarkPackageDirty();

    UE_LOG(
        LogAtlasTransport,
        Log,
        TEXT("Atlas Unreal fixtures ready in world '%s': field actor '%s', sequencer actor '%s', playback range %d-%d"),
        *World->GetName(),
        *FieldFixtureActor->GetName(),
        *FixtureActor->GetName(),
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