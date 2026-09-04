#include "CoreMinimal.h"
#include "Engine/World.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
#include "LevelSequence.h"
#include "LevelSequenceActor.h"
#include "Editor.h"
#include "Containers/Ticker.h"

namespace AtlasSequencerIntegrationFixture
{
    static const FName FixtureTag(TEXT("atlas_sequencer_integration_fixture"));

    static bool EnsureFixture(float)
    {
        if (!GEditor || !GEngine || IsEngineExitRequested())
        {
            return true;
        }

        UWorld* World = GEditor->GetEditorWorldContext().World();
        if (!World || !IsValid(World) || World->IsGameWorld())
        {
            return true;
        }

        for (TActorIterator<ALevelSequenceActor> It(World); It; ++It)
        {
            ALevelSequenceActor* Actor = *It;
            if (Actor && IsValid(Actor) && Actor->Tags.Contains(FixtureTag) && Actor->GetSequence() && Actor->GetSequence()->GetMovieScene())
            {
                return true;
            }
        }

        FActorSpawnParameters SpawnParams;
        SpawnParams.Name = TEXT("AtlasSequencerIntegrationSequenceActor");
        SpawnParams.NameMode = FActorSpawnParameters::ESpawnActorNameMode::Requested;
        SpawnParams.ObjectFlags |= RF_Transient;

        ALevelSequenceActor* SequenceActor = World->SpawnActor<ALevelSequenceActor>(SpawnParams);
        if (!SequenceActor)
        {
            return true;
        }

        SequenceActor->Tags.Add(FixtureTag);
        SequenceActor->SetActorLabel(TEXT("Atlas Sequencer Integration Sequence"));

        ULevelSequence* Sequence = NewObject<ULevelSequence>(GetTransientPackage(), NAME_None, RF_Transient);
        if (!Sequence)
        {
            SequenceActor->Destroy();
            return true;
        }

        Sequence->Initialize();
        if (UMovieScene* MovieScene = Sequence->GetMovieScene())
        {
            MovieScene->SetPlaybackRange(0, 100);
        }
        SequenceActor->SetSequence(Sequence);

        UE_LOG(LogTemp, Log, TEXT("Atlas Sequencer integration fixture created in active editor world."));
        return true;
    }

    struct FStartup
    {
        FStartup()
        {
            FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateStatic(&EnsureFixture), 0.25f);
        }
    };

    static FStartup Startup;
}
