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
#include "AssetRegistry/AssetRegistryModule.h"
#include "UObject/SavePackage.h"
#include "Misc/PackageName.h"
#include "HAL/FileManager.h"
#include "Factories/WorldFactory.h"
#include "FileHelpers.h"

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

    const FString RenderFixturePackageName =
        TEXT("/Game/AtlasTest/Generated/AtlasRenderFixture");

    const FString RenderFixtureObjectPath =
        TEXT("/Game/AtlasTest/Generated/AtlasRenderFixture.AtlasRenderFixture");

    bool EnsurePersistentRenderFixture(FString& OutMapPath, FString& OutError)
    {
        OutMapPath = RenderFixturePackageName;

        if (UWorld* ExistingWorld =
                LoadObject<UWorld>(nullptr, *RenderFixtureObjectPath))
        {
            if (IsValid(ExistingWorld))
            {
                return true;
            }
        }

        UPackage* Package = CreatePackage(*RenderFixturePackageName);
        if (!Package)
        {
            OutError = FString::Printf(
                TEXT("Unable to create persistent render fixture package '%s'"),
                *RenderFixturePackageName);
            return false;
        }

        UWorldFactory* Factory = NewObject<UWorldFactory>();
        if (!Factory)
        {
            OutError = TEXT("Unable to create UWorldFactory for persistent render fixture");
            return false;
        }

        Factory->WorldType = EWorldType::Editor;
        Factory->bCreateWorldPartition = false;
        Factory->bInformEngineOfWorld = true;

        UWorld* World = Cast<UWorld>(
            Factory->FactoryCreateNew(
                UWorld::StaticClass(),
                Package,
                FName(TEXT("AtlasRenderFixture")),
                RF_Public | RF_Standalone,
                nullptr,
                GWarn));

        if (!World)
        {
            OutError = TEXT("UWorldFactory failed to create persistent render fixture world");
            return false;
        }

        AActor* FieldFixtureActor = World->SpawnActor<AActor>(
            AActor::StaticClass(),
            FTransform::Identity);

        if (!FieldFixtureActor)
        {
            OutError = TEXT("Unable to create persistent FIELD_SURFACE fixture actor");
            return false;
        }

        USceneComponent* RootComponent = NewObject<USceneComponent>(
            FieldFixtureActor,
            TEXT("AtlasFieldSurfaceFixtureRoot"));

        if (!RootComponent)
        {
            FieldFixtureActor->Destroy();
            OutError = TEXT("Unable to create persistent FIELD_SURFACE root component");
            return false;
        }

        FieldFixtureActor->SetRootComponent(RootComponent);
        RootComponent->RegisterComponent();
        FieldFixtureActor->Tags.AddUnique(FieldFixtureTag);
        FieldFixtureActor->SetActorLabel(TEXT("Atlas Field Surface Fixture"));

        World->UpdateWorldComponents(true, true);
        Package->MarkPackageDirty();

        const FString PackageFilename =
            FPackageName::LongPackageNameToFilename(
                RenderFixturePackageName,
                FPackageName::GetMapPackageExtension());

        IFileManager::Get().MakeDirectory(
            *FPaths::GetPath(PackageFilename),
            true);

        if (!UEditorLoadingAndSavingUtils::SaveMap(World, RenderFixturePackageName))
        {
            OutError = FString::Printf(
                TEXT("Failed to save persistent Atlas render fixture map '%s'"),
                *RenderFixturePackageName);
            return false;
        }

        if (!FPaths::FileExists(PackageFilename))
        {
            OutError = FString::Printf(
                TEXT("Persistent Atlas render fixture map was not written to '%s'"),
                *PackageFilename);
            return false;
        }

        UE_LOG(
            LogAtlasTransport,
            Log,
            TEXT("Persistent Atlas render fixture ready: %s"),
            *RenderFixturePackageName);

        return true;
    }

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

    FString RenderFixtureMapPath;
    FString RenderFixtureError;
    if (!EnsurePersistentRenderFixture(
            RenderFixtureMapPath,
            RenderFixtureError))
    {
        UE_LOG(
            LogAtlasTransport,
            Warning,
            TEXT("Persistent Atlas render fixture is not ready: %s"),
            *RenderFixtureError);
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
        const FString SequencePackageName =
            TEXT("/Game/AtlasTest/AtlasSequencerFixtureSequence");

        const FString SequenceObjectPath =
            TEXT("/Game/AtlasTest/AtlasSequencerFixtureSequence.AtlasSequencerFixtureSequence");

        Sequence = LoadObject<ULevelSequence>(
            nullptr,
            *SequenceObjectPath);

        if (!Sequence)
        {
            UPackage* SequencePackage =
                CreatePackage(*SequencePackageName);

            if (!SequencePackage)
            {
                UE_LOG(
                    LogAtlasTransport,
                    Warning,
                    TEXT("Unable to create Atlas Sequencer fixture package '%s'"),
                    *SequencePackageName);
                return true;
            }

            Sequence = NewObject<ULevelSequence>(
                SequencePackage,
                SequencerFixtureSequenceName,
                RF_Public | RF_Standalone);

            if (!Sequence)
            {
                UE_LOG(
                    LogAtlasTransport,
                    Warning,
                    TEXT("Unable to create Atlas Sequencer fixture sequence '%s'"),
                    *SequencePackageName);
                return true;
            }

            Sequence->Initialize();

            FAssetRegistryModule::AssetCreated(Sequence);
            SequencePackage->MarkPackageDirty();

            const FString PackageFilename =
                FPackageName::LongPackageNameToFilename(
                    SequencePackageName,
                    FPackageName::GetAssetPackageExtension());

            FSavePackageArgs SaveArgs;
            SaveArgs.TopLevelFlags = RF_Public | RF_Standalone;
            SaveArgs.SaveFlags = SAVE_None;

            if (!UPackage::SavePackage(
                    SequencePackage,
                    Sequence,
                    *PackageFilename,
                    SaveArgs))
            {
                UE_LOG(
                    LogAtlasTransport,
                    Warning,
                    TEXT("Unable to save Atlas Sequencer fixture sequence to '%s'"),
                    *PackageFilename);
                return true;
            }
        }

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
