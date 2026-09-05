#pragma once

#include "CoreMinimal.h"
#include "AtlasLiveIngressQueue.h"
#include "AtlasLiveGameThreadPump.h"
#include "Containers/Ticker.h"

class AActor;

/**
 * Result of attempting to dispatch an effect.
 */
enum class EAtlasLiveEffectResult : uint8
{
    Success = 0,
    MissingTarget,
    MissingPreset,
    ExpiredDeadline,
    FailedExecution
};

/**
 * Telemetry snapshot for the effect dispatcher and registry.
 */
struct FAtlasLiveEffectTelemetry
{
    int64 TotalEffectLookups = 0;
    int64 TotalDispatches = 0;
    int64 TotalMissingTarget = 0;
    int64 TotalMissingPreset = 0;
    int64 TotalExpiredDeadlineCount = 0;
    int64 TotalFailedExecutionCount = 0;
    int64 TotalEffectActivations = 0;
    int64 TotalEffectCleanups = 0;
    int64 TotalActiveEffects = 0;
    double LastDispatchDurationMs = 0.0;
};

/**
 * Interface for concrete effect handlers (e.g. Impact Accent, Niagara, Sequencer, Material Variant).
 * Executes strictly on the Unreal GameThread.
 */
class ATLASUNREALTRANSPORT_API IAtlasLiveEffectHandler
{
public:
    virtual ~IAtlasLiveEffectHandler() = default;

    /**
     * Executes the visual effect on TargetActor on the GameThread.
     * Returns true if execution succeeded.
     */
    virtual bool Execute(
        AActor* TargetActor,
        const FAtlasLiveProductionIntent& Intent,
        float MaxDurationSeconds) = 0;

    /**
     * Optional deterministic cleanup for an actor when an effect ends or is preempted.
     */
    virtual void Cleanup(AActor* TargetActor) {}
};

/**
 * Registry and dispatcher for Atlas Live visual effects.
 *
 * Implements IAtlasLiveEffectDispatcher.
 * Strictly runs on the Unreal GameThread.
 *
 * Capabilities:
 * - Maps (Treatment, PresetName) -> IAtlasLiveEffectHandler
 * - Finds target actors via "atlas_entity:<ENTITY_ID>" tags
 * - Enforces visual deadlines (rejects stale intents)
 * - Manages active effect lifetimes with deterministic per-frame FTSTicker decay and cleanup
 * - Collects latency and error telemetry
 */
class ATLASUNREALTRANSPORT_API FAtlasLiveEffectRegistry : public IAtlasLiveEffectDispatcher
{
public:
    FAtlasLiveEffectRegistry(double InDefaultDeadlineMs = 500.0);
    virtual ~FAtlasLiveEffectRegistry();

    // Non-copyable
    FAtlasLiveEffectRegistry(const FAtlasLiveEffectRegistry&) = delete;
    FAtlasLiveEffectRegistry& operator=(const FAtlasLiveEffectRegistry&) = delete;

    /**
     * Register an effect handler for a treatment category and optional preset name.
     * Pass empty PresetName to register a fallback default handler for that treatment.
     */
    void RegisterHandler(
        EAtlasLiveTreatment Treatment,
        const FString& PresetName,
        TSharedPtr<IAtlasLiveEffectHandler> Handler);

    /**
     * IAtlasLiveEffectDispatcher interface: executed by FAtlasLiveGameThreadPump on GameThread.
     */
    virtual bool DispatchIntent(const FAtlasLiveProductionIntent& Intent) override;

    /**
     * Tick active effect lifetimes and clean up expired transient components/tags.
     * Called automatically via FTSTicker on GameThread.
     */
    bool TickActiveEffects(float DeltaTime);

    /**
     * Find target actor in active editor/game world by Atlas entity ID.
     */
    static AActor* FindTargetActor(const FString& EntityId);

    /**
     * Get effect dispatcher telemetry snapshot.
     */
    FAtlasLiveEffectTelemetry GetTelemetry() const { return Telemetry; }

    /**
     * Set max visual latency deadline in milliseconds (intents older than this are dropped).
     */
    void SetDeadlineMs(double InDeadlineMs) { DeadlineMs = InDeadlineMs; }

    /**
     * Active tracked effect count.
     */
    int32 GetActiveEffectCount() const { return ActiveEffects.Num(); }

    /**
     * Force cleanup of all active tracked effects immediately.
     */
    void CleanupAllActiveEffects();

private:
    struct FActiveEffectRecord
    {
        TWeakObjectPtr<AActor> TargetActor;
        FString EntityId;
        FString IntentId;
        EAtlasLiveTreatment Treatment;
        FString PresetName;
        TSharedPtr<IAtlasLiveEffectHandler> Handler;
        double ExpirationTimeSeconds;
    };

    TMap<FString, TSharedPtr<IAtlasLiveEffectHandler>> Handlers;
    TArray<FActiveEffectRecord> ActiveEffects;
    double DeadlineMs;

    FTSTicker::FDelegateHandle TickerHandle;
    FAtlasLiveEffectTelemetry Telemetry;

    static FString MakeHandlerKey(EAtlasLiveTreatment Treatment, const FString& PresetName);
    TSharedPtr<IAtlasLiveEffectHandler> FindHandler(EAtlasLiveTreatment Treatment, const FString& PresetName);
};
