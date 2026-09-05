#pragma once

#include "CoreMinimal.h"
#include "HAL/CriticalSection.h"
#include "HAL/PlatformTime.h"
#include <atomic>

/**
 * Visual treatment categories matching the engine-neutral Atlas Live ProductionTreatment enum.
 */
enum class EAtlasLiveTreatment : uint8
{
    Unknown = 0,
    ImpactAccent,
    SpeedTrail,
    BallHighlight,
    PlayerCard,
    CinematicPunch,
    ImpactFrame
};

/**
 * Engine-agnostic Production Intent data payload.
 * Holds NO UObjects, Niagara systems, or Sequencer components.
 */
struct ATLASUNREALTRANSPORT_API FAtlasLiveProductionIntent
{
    FString IntentId;
    EAtlasLiveTreatment Treatment = EAtlasLiveTreatment::Unknown;
    FString SourceEventId;
    TArray<FString> TargetEntityIds;
    float Intensity = 0.0f;
    int32 DurationMs = 0;
    FVector Origin = FVector::ZeroVector;
    FVector Direction = FVector::ZeroVector;
    TMap<FString, FString> Parameters;

    // Cross-process and local monotonic telemetry timestamps
    int64 SourceTimestampNs = 0;   // Host / Decision layer generation timestamp (ns)
    int64 TransportSentAtNs = 0;   // Python transport send timestamp (ns)
    uint64 ReceiverCycles = 0;     // Receiver thread arrival time (FPlatformTime::Cycles64())
    uint64 ValidatedCycles = 0;    // Receiver thread validation/deserialization complete (Cycles64)
    uint64 EnqueuedCycles = 0;     // Time pushed into FAtlasLiveIngressQueue (Cycles64)
    uint64 DequeuedCycles = 0;     // Time popped from queue by GameThread (Cycles64)
    uint64 DispatchedCycles = 0;   // Time passed to effect dispatcher on GameThread (Cycles64)

    // Sequence tracking
    uint64 SequenceNumber = 0;
    FString SessionId;
};

/**
 * Enqueue outcome result codes.
 */
enum class EAtlasLiveEnqueueResult : uint8
{
    Success = 0,
    RejectedShutdown,
    RejectedDuplicate,
    RejectedOutOfOrder,
    RejectedMalformed,
    DroppedOverflow
};

/**
 * Telemetry snapshot for the ingress queue.
 */
struct FAtlasLiveQueueTelemetry
{
    int32 CurrentDepth = 0;
    int32 MaxCapacity = 0;
    float UtilizationRatio = 0.0f;
    bool bWarningThresholdExceeded = false;
    int64 TotalEnqueued = 0;
    int64 TotalDequeued = 0;
    int64 TotalDroppedOverflow = 0;
    int64 TotalRejectedDuplicate = 0;
    int64 TotalRejectedOutOfOrder = 0;
    int64 TotalRejectedMalformed = 0;
    double LastQueueWaitMs = 0.0;
    double LastDispatchDurationMs = 0.0;
};

/**
 * Thread-safe, bounded MPSC ingress queue for Atlas Live production intents.
 * 
 * Concurrency topology:
 * - Producers: 1..N transport / worker / simulation threads.
 * - Consumer: Exactly 1 GameThread (pumped via deterministic tick).
 *
 * Overflow policy:
 * - Drop Oldest (Head Eviction): When full, the oldest stale intent at the head is
 *   evicted to make room for fresh real-time intent, incrementing DropOverflow count.
 *
 * Sequence & Duplication policy:
 * - Sequence numbers must be strictly monotonic per SessionId.
 * - IntentIds are deduplicated over a sliding history window.
 * - Reconnection / new session resets sequence domains cleanly.
 */
class ATLASUNREALTRANSPORT_API FAtlasLiveIngressQueue
{
public:
    explicit FAtlasLiveIngressQueue(int32 InMaxCapacity = 128, int32 InDeduplicationWindowSize = 512, float InWarningRatio = 0.8f);
    ~FAtlasLiveIngressQueue();

    // Non-copyable
    FAtlasLiveIngressQueue(const FAtlasLiveIngressQueue&) = delete;
    FAtlasLiveIngressQueue& operator=(const FAtlasLiveIngressQueue&) = delete;

    /**
     * Enqueue a validated intent from any producer thread.
     * Non-blocking for the GameThread.
     */
    EAtlasLiveEnqueueResult Enqueue(FAtlasLiveProductionIntent InIntent);

    /**
     * Non-blocking dequeue of a single intent. MUST only be called from GameThread.
     * Returns true if an item was popped, false if queue is empty.
     */
    bool Dequeue(FAtlasLiveProductionIntent& OutIntent);

    /**
     * Batch dequeue up to MaxBatchSize items into OutIntents. MUST only be called from GameThread.
     * Returns the count of popped items.
     */
    int32 DequeueBatch(TArray<FAtlasLiveProductionIntent>& OutIntents, int32 MaxBatchSize = 32);

    /**
     * Record a malformed message rejection at the transport boundary before queueing.
     */
    void RecordMalformedRejection();

    /**
     * Reset the transport session sequence domain (e.g. upon transport client reconnect).
     */
    void ResetSession(const FString& NewSessionId);

    /**
     * Signal shutdown. Prevents new enqueues. Dequeue continues to drain cleanly.
     */
    void Shutdown();

    /**
     * Check if queue is shut down.
     */
    bool IsShutdown() const;

    /**
     * Get queue telemetry snapshot. Thread-safe.
     */
    FAtlasLiveQueueTelemetry GetTelemetry() const;

    /**
     * Current number of queued items.
     */
    int32 GetDepth() const;

    /**
     * Clear all queued items and reset state.
     */
    void Empty();

    /**
     * Helper to convert cycle delta to milliseconds using FPlatformTime::GetSecondsPerCycle64().
     */
    static double CyclesToMs(uint64 CyclesDelta);

private:
    const int32 MaxCapacity;
    const int32 DeduplicationWindowSize;
    const float WarningRatio;

    mutable FCriticalSection Mutex;

    // Ring/Array storage for FIFO queue
    TArray<FAtlasLiveProductionIntent> Buffer;
    int32 HeadIndex;
    int32 TailIndex;
    int32 Count;

    // Session and sequence tracking
    FString CurrentSessionId;
    uint64 LastSeenSequenceNumber;

    // Deduplication tracking: sliding window of recent Intent IDs
    TArray<FString> DeduplicationWindow;
    TSet<FString> DeduplicationSet;
    int32 DedupInsertIndex;

    // Shutdown state
    std::atomic<bool> bIsShutdown;

    // Telemetry counters
    std::atomic<int64> TotalEnqueuedCount;
    std::atomic<int64> TotalDequeuedCount;
    std::atomic<int64> TotalDroppedOverflowCount;
    std::atomic<int64> TotalRejectedDuplicateCount;
    std::atomic<int64> TotalRejectedOutOfOrderCount;
    std::atomic<int64> TotalRejectedMalformedCount;
    std::atomic<double> LastQueueWaitDurationMs;
    std::atomic<double> LastDispatchDurationMs;
};
