#include "AtlasLiveEffectRegistry.h"
#include "AtlasUnrealTransport.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Editor.h"
#include "GameFramework/Actor.h"
#include "HAL/PlatformTime.h"

FAtlasLiveEffectRegistry::FAtlasLiveEffectRegistry(double InDefaultDeadlineMs)
    : DeadlineMs(InDefaultDeadlineMs)
{
    TickerHandle = FTSTicker::GetCoreTicker().AddTicker(
        FTickerDelegate::CreateRaw(this, &FAtlasLiveEffectRegistry::TickActiveEffects),
        0.0f // Tick each frame
    );
}

FAtlasLiveEffectRegistry::~FAtlasLiveEffectRegistry()
{
    if (TickerHandle.IsValid())
    {
        FTSTicker::GetCoreTicker().RemoveTicker(TickerHandle);
        TickerHandle.Reset();
    }
    CleanupAllActiveEffects();
}

FString FAtlasLiveEffectRegistry::MakeHandlerKey(EAtlasLiveTreatment Treatment, const FString& PresetName)
{
    return FString::Printf(TEXT("%d:%s"), (int32)Treatment, *PresetName.ToLower());
}

void FAtlasLiveEffectRegistry::RegisterHandler(
    EAtlasLiveTreatment Treatment,
    const FString& PresetName,
    TSharedPtr<IAtlasLiveEffectHandler> Handler)
{
    if (!Handler.IsValid())
    {
        return;
    }

    FString Key = MakeHandlerKey(Treatment, PresetName);
    Handlers.Add(Key, Handler);
}

TSharedPtr<IAtlasLiveEffectHandler> FAtlasLiveEffectRegistry::FindHandler(
    EAtlasLiveTreatment Treatment,
    const FString& PresetName)
{
    Telemetry.TotalEffectLookups++;

    // 1. Exact match on Treatment + Preset
    if (!PresetName.IsEmpty())
    {
        FString Key = MakeHandlerKey(Treatment, PresetName);
        if (TSharedPtr<IAtlasLiveEffectHandler>* Found = Handlers.Find(Key))
        {
            return *Found;
        }
    }

    // 2. Default fallback for Treatment
    FString DefaultKey = MakeHandlerKey(Treatment, TEXT(""));
    if (TSharedPtr<IAtlasLiveEffectHandler>* DefaultFound = Handlers.Find(DefaultKey))
    {
        return *DefaultFound;
    }

    return nullptr;
}

AActor* FAtlasLiveEffectRegistry::FindTargetActor(const FString& EntityId)
{
    if (!IsInGameThread() || !GEngine || IsEngineExitRequested())
    {
        return nullptr;
    }

    UWorld* World = nullptr;
    if (GEditor)
    {
        World = GEditor->GetEditorWorldContext().World();
    }
    if (!World && GEngine->GetWorldContexts().Num() > 0)
    {
        World = GEngine->GetWorldContexts()[0].World();
    }

    if (!World || !IsValid(World))
    {
        return nullptr;
    }

    const FString TagToFind = FString::Printf(TEXT("atlas_entity:%s"), *EntityId);
    const FName TagName(*TagToFind);

    for (TActorIterator<AActor> It(World); It; ++It)
    {
        AActor* Actor = *It;
        if (Actor && IsValid(Actor) && Actor->Tags.Contains(TagName))
        {
            return Actor;
        }
    }

    return nullptr;
}

bool FAtlasLiveEffectRegistry::DispatchIntent(const FAtlasLiveProductionIntent& Intent)
{
    check(IsInGameThread());

    uint64 StartCycles = FPlatformTime::Cycles64();
    Telemetry.TotalDispatches++;

    // 1. Check Visual Deadline
    // Missing receiver timing must not silently disable deadline safety.
    // If ReceiverCycles == 0, treat as missing timing and reject conservatively.
    if (Intent.ReceiverCycles == 0)
    {
        Telemetry.TotalExpiredDeadlineCount++;
        UE_LOG(LogAtlasTransport, Warning,
            TEXT("Atlas Live: Intent %s missing ReceiverCycles (ReceiverCycles == 0), rejected conservatively for deadline safety"),
            *Intent.IntentId);
        return false;
    }
    else
    {
        double ElapsedSinceRecvMs = FAtlasLiveIngressQueue::CyclesToMs(StartCycles - Intent.ReceiverCycles);
        if (ElapsedSinceRecvMs > DeadlineMs)
        {
            Telemetry.TotalExpiredDeadlineCount++;
            UE_LOG(LogAtlasTransport, Warning,
                TEXT("Atlas Live: Intent %s expired visual deadline (%.2f ms > %.2f ms), dropped"),
                *Intent.IntentId, ElapsedSinceRecvMs, DeadlineMs);
            return false;
        }
    }

    // 2. Lookup Preset Handler
    FString PresetName;
    if (const FString* PresetVal = Intent.Parameters.Find(TEXT("preset")))
    {
        PresetName = *PresetVal;
    }

    TSharedPtr<IAtlasLiveEffectHandler> Handler = FindHandler(Intent.Treatment, PresetName);
    if (!Handler.IsValid())
    {
        Telemetry.TotalMissingPreset++;
        UE_LOG(LogAtlasTransport, Warning,
            TEXT("Atlas Live: No registered handler for treatment %d, preset '%s' (Intent: %s)"),
            (int32)Intent.Treatment, *PresetName, *Intent.IntentId);
        return false;
    }

    // 3. Resolve Target Actor
    if (Intent.TargetEntityIds.Num() == 0)
    {
        Telemetry.TotalMissingTarget++;
        UE_LOG(LogAtlasTransport, Warning, TEXT("Atlas Live: Intent %s has empty target_entity_ids"), *Intent.IntentId);
        return false;
    }

    // For ball strike / impact accent, primary target is first entity ID
    FString TargetEntityId = Intent.TargetEntityIds[0];
    AActor* TargetActor = FindTargetActor(TargetEntityId);
    if (!TargetActor || !IsValid(TargetActor))
    {
        // Try fallback to secondary entities if available
        for (int32 i = 1; i < Intent.TargetEntityIds.Num(); ++i)
        {
            TargetActor = FindTargetActor(Intent.TargetEntityIds[i]);
            if (TargetActor && IsValid(TargetActor))
            {
                TargetEntityId = Intent.TargetEntityIds[i];
                break;
            }
        }
    }

    if (!TargetActor || !IsValid(TargetActor))
    {
        Telemetry.TotalMissingTarget++;
        UE_LOG(LogAtlasTransport, Warning,
            TEXT("Atlas Live: Target actor not found in world for entity '%s' (Intent: %s)"),
            *TargetEntityId, *Intent.IntentId);
        return false;
    }

    // 4. Handle Existing Active Effect Preemption
    for (int32 i = ActiveEffects.Num() - 1; i >= 0; --i)
    {
        if (ActiveEffects[i].TargetActor.Get() == TargetActor)
        {
            // Preempt existing effect on this actor
            if (ActiveEffects[i].Handler.IsValid())
            {
                ActiveEffects[i].Handler->Cleanup(TargetActor);
            }
            ActiveEffects.RemoveAt(i);
            Telemetry.TotalEffectCleanups++;
            break;
        }
    }

    // 5. Execute Effect on Target Actor
    float DurationSec = (Intent.DurationMs > 0) ? (Intent.DurationMs / 1000.0f) : 0.2f;
    bool bSuccess = Handler->Execute(TargetActor, Intent, DurationSec);

    uint64 EndCycles = FPlatformTime::Cycles64();
    Telemetry.LastDispatchDurationMs = FAtlasLiveIngressQueue::CyclesToMs(EndCycles - StartCycles);

    if (bSuccess)
    {
        Telemetry.TotalEffectActivations++;

        FActiveEffectRecord Record;
        Record.TargetActor = TargetActor;
        Record.EntityId = TargetEntityId;
        Record.IntentId = Intent.IntentId;
        Record.Treatment = Intent.Treatment;
        Record.PresetName = PresetName;
        Record.Handler = Handler;
        Record.ExpirationTimeSeconds = FPlatformTime::Seconds() + DurationSec;

        ActiveEffects.Add(MoveTemp(Record));
        Telemetry.TotalActiveEffects = ActiveEffects.Num();

        UE_LOG(LogAtlasTransport, Display,
            TEXT("Atlas Live Effect Activated: %s on %s ('%s'), duration: %.2fs, dispatch time: %.3f ms"),
            *Intent.IntentId, *TargetActor->GetName(), *TargetEntityId, DurationSec, Telemetry.LastDispatchDurationMs);
        return true;
    }

    Telemetry.TotalFailedExecutionCount++;
    return false;
}

bool FAtlasLiveEffectRegistry::TickActiveEffects(float DeltaTime)
{
    if (ActiveEffects.Num() == 0)
    {
        return true;
    }

    double NowSeconds = FPlatformTime::Seconds();

    for (int32 i = ActiveEffects.Num() - 1; i >= 0; --i)
    {
        FActiveEffectRecord& Record = ActiveEffects[i];
        if (NowSeconds >= Record.ExpirationTimeSeconds || !Record.TargetActor.IsValid())
        {
            if (AActor* Actor = Record.TargetActor.Get())
            {
                if (Record.Handler.IsValid())
                {
                    Record.Handler->Cleanup(Actor);
                }
            }
            ActiveEffects.RemoveAt(i);
            Telemetry.TotalEffectCleanups++;
        }
    }

    Telemetry.TotalActiveEffects = ActiveEffects.Num();
    return true;
}

void FAtlasLiveEffectRegistry::CleanupAllActiveEffects()
{
    for (FActiveEffectRecord& Record : ActiveEffects)
    {
        if (AActor* Actor = Record.TargetActor.Get())
        {
            if (Record.Handler.IsValid())
            {
                Record.Handler->Cleanup(Actor);
            }
        }
        Telemetry.TotalEffectCleanups++;
    }
    ActiveEffects.Empty();
    Telemetry.TotalActiveEffects = 0;
}
