#pragma once

#include "CoreMinimal.h"
#include "AtlasLiveIngressQueue.h"
#include "Containers/Ticker.h"

/**
 * Interface for downstream effect dispatchers invoked on the GameThread.
 */
class ATLASUNREALTRANSPORT_API IAtlasLiveEffectDispatcher
{
public:
    virtual ~IAtlasLiveEffectDispatcher() = default;

    /**
     * Dispatch an accepted production intent on the GameThread.
     * Must be non-blocking. Returns true if dispatched successfully.
     */
    virtual bool DispatchIntent(const FAtlasLiveProductionIntent& Intent) = 0;
};

/**
 * Deterministic GameThread pump delegate.
 *
 * Runs on the Unreal GameThread via FTSTicker::GetCoreTicker().
 * Features:
 * - NEVER blocks waiting for network or worker threads.
 * - Pops up to MaxIntentsPerTick per frame (bounded work budget to protect frame time).
 * - Records dequeue timestamp, dispatch timestamp, and dispatch execution duration telemetry.
 * - Passes intents to an engine-agnostic IAtlasLiveEffectDispatcher.
 */
class ATLASUNREALTRANSPORT_API FAtlasLiveGameThreadPump
{
public:
    FAtlasLiveGameThreadPump(
        TSharedPtr<FAtlasLiveIngressQueue> InQueue,
        TSharedPtr<IAtlasLiveEffectDispatcher> InDispatcher = nullptr,
        int32 InMaxIntentsPerTick = 16);

    ~FAtlasLiveGameThreadPump();

    // Non-copyable
    FAtlasLiveGameThreadPump(const FAtlasLiveGameThreadPump&) = delete;
    FAtlasLiveGameThreadPump& operator=(const FAtlasLiveGameThreadPump&) = delete;

    /**
     * Start the FTSTicker delegate to pump the queue once per frame on the GameThread.
     */
    void Start();

    /**
     * Stop the ticker delegate.
     */
    void Stop();

    /**
     * Deterministic pump execution. Can be called manually in unit tests or by FTSTicker.
     * Returns true if ticker should continue.
     */
    bool Tick(float DeltaTime);

    /**
     * Set or replace the effect dispatcher.
     */
    void SetDispatcher(TSharedPtr<IAtlasLiveEffectDispatcher> InDispatcher);

    /**
     * Get count of successfully dispatched intents.
     */
    int64 GetTotalDispatchedCount() const { return TotalDispatchedCount; }

    /**
     * Get count of failed dispatches.
     */
    int64 GetTotalFailedDispatchCount() const { return TotalFailedDispatchCount; }

    /**
     * Check if ticker is active.
     */
    bool IsActive() const { return TickerHandle.IsValid(); }

private:
    TSharedPtr<FAtlasLiveIngressQueue> Queue;
    TSharedPtr<IAtlasLiveEffectDispatcher> Dispatcher;
    const int32 MaxIntentsPerTick;

    FTSTicker::FDelegateHandle TickerHandle;

    int64 TotalDispatchedCount;
    int64 TotalFailedDispatchCount;
};
