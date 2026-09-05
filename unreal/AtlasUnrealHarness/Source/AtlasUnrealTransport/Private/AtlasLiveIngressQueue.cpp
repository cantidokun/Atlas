#include "AtlasLiveIngressQueue.h"

FAtlasLiveIngressQueue::FAtlasLiveIngressQueue(int32 InMaxCapacity, int32 InDeduplicationWindowSize, float InWarningRatio)
    : MaxCapacity(FMath::Max(1, InMaxCapacity))
    , DeduplicationWindowSize(FMath::Max(1, InDeduplicationWindowSize))
    , WarningRatio(FMath::Clamp(InWarningRatio, 0.1f, 1.0f))
    , HeadIndex(0)
    , TailIndex(0)
    , Count(0)
    , CurrentSessionId(TEXT(""))
    , LastSeenSequenceNumber(0)
    , DedupInsertIndex(0)
    , bIsShutdown(false)
    , TotalEnqueuedCount(0)
    , TotalDequeuedCount(0)
    , TotalDroppedOverflowCount(0)
    , TotalRejectedDuplicateCount(0)
    , TotalRejectedOutOfOrderCount(0)
    , TotalRejectedMalformedCount(0)
    , LastQueueWaitDurationMs(0.0)
    , LastDispatchDurationMs(0.0)
{
    Buffer.SetNum(MaxCapacity);
    DeduplicationWindow.SetNum(DeduplicationWindowSize);
}

FAtlasLiveIngressQueue::~FAtlasLiveIngressQueue()
{
    Shutdown();
    Empty();
}

double FAtlasLiveIngressQueue::CyclesToMs(uint64 CyclesDelta)
{
    return (double)CyclesDelta * FPlatformTime::GetSecondsPerCycle64() * 1000.0;
}

EAtlasLiveEnqueueResult FAtlasLiveIngressQueue::Enqueue(FAtlasLiveProductionIntent InIntent)
{
    if (bIsShutdown.load(std::memory_order_relaxed))
    {
        return EAtlasLiveEnqueueResult::RejectedShutdown;
    }

    if (InIntent.IntentId.IsEmpty())
    {
        TotalRejectedMalformedCount.fetch_add(1, std::memory_order_relaxed);
        return EAtlasLiveEnqueueResult::RejectedMalformed;
    }

    // Monotonic timestamp of enqueue attempt on this process
    InIntent.EnqueuedCycles = FPlatformTime::Cycles64();

    FScopeLock Lock(&Mutex);

    if (bIsShutdown.load(std::memory_order_relaxed))
    {
        return EAtlasLiveEnqueueResult::RejectedShutdown;
    }

    // 1. Session & Sequence enforcement
    if (InIntent.SessionId != CurrentSessionId)
    {
        // Session switch / reconnect: re-anchor sequence numbering
        CurrentSessionId = InIntent.SessionId;
        LastSeenSequenceNumber = InIntent.SequenceNumber;
    }
    else
    {
        // Inside same session: sequence number must be strictly monotonic
        if (InIntent.SequenceNumber <= LastSeenSequenceNumber && InIntent.SequenceNumber != 0)
        {
            TotalRejectedOutOfOrderCount.fetch_add(1, std::memory_order_relaxed);
            return EAtlasLiveEnqueueResult::RejectedOutOfOrder;
        }
        LastSeenSequenceNumber = InIntent.SequenceNumber;
    }

    // 2. Deduplication check
    if (DeduplicationSet.Contains(InIntent.IntentId))
    {
        TotalRejectedDuplicateCount.fetch_add(1, std::memory_order_relaxed);
        return EAtlasLiveEnqueueResult::RejectedDuplicate;
    }

    // Add to sliding window deduplication set
    if (!DeduplicationWindow[DedupInsertIndex].IsEmpty())
    {
        DeduplicationSet.Remove(DeduplicationWindow[DedupInsertIndex]);
    }
    DeduplicationWindow[DedupInsertIndex] = InIntent.IntentId;
    DeduplicationSet.Add(InIntent.IntentId);
    DedupInsertIndex = (DedupInsertIndex + 1) % DeduplicationWindowSize;

    // 3. Bounded capacity & overflow policy (Drop Oldest / Head Eviction)
    bool bDidEvictOldest = false;
    if (Count >= MaxCapacity)
    {
        // Evict oldest item at HeadIndex
        HeadIndex = (HeadIndex + 1) % MaxCapacity;
        Count--;
        TotalDroppedOverflowCount.fetch_add(1, std::memory_order_relaxed);
        bDidEvictOldest = true;
    }

    // Insert at TailIndex
    Buffer[TailIndex] = MoveTemp(InIntent);
    TailIndex = (TailIndex + 1) % MaxCapacity;
    Count++;

    TotalEnqueuedCount.fetch_add(1, std::memory_order_relaxed);

    return bDidEvictOldest ? EAtlasLiveEnqueueResult::DroppedOverflow : EAtlasLiveEnqueueResult::Success;
}

bool FAtlasLiveIngressQueue::Dequeue(FAtlasLiveProductionIntent& OutIntent)
{
    FScopeLock Lock(&Mutex);

    if (Count == 0)
    {
        return false;
    }

    OutIntent = MoveTemp(Buffer[HeadIndex]);
    HeadIndex = (HeadIndex + 1) % MaxCapacity;
    Count--;

    uint64 NowCycles = FPlatformTime::Cycles64();
    OutIntent.DequeuedCycles = NowCycles;

    if (OutIntent.EnqueuedCycles > 0 && NowCycles >= OutIntent.EnqueuedCycles)
    {
        double WaitMs = CyclesToMs(NowCycles - OutIntent.EnqueuedCycles);
        LastQueueWaitDurationMs.store(WaitMs, std::memory_order_relaxed);
    }

    TotalDequeuedCount.fetch_add(1, std::memory_order_relaxed);
    return true;
}

int32 FAtlasLiveIngressQueue::DequeueBatch(TArray<FAtlasLiveProductionIntent>& OutIntents, int32 MaxBatchSize)
{
    if (MaxBatchSize <= 0)
    {
        return 0;
    }

    FScopeLock Lock(&Mutex);

    int32 ToPop = FMath::Min(Count, MaxBatchSize);
    if (ToPop == 0)
    {
        return 0;
    }

    OutIntents.Reserve(OutIntents.Num() + ToPop);
    uint64 NowCycles = FPlatformTime::Cycles64();

    for (int32 i = 0; i < ToPop; ++i)
    {
        FAtlasLiveProductionIntent Intent = MoveTemp(Buffer[HeadIndex]);
        HeadIndex = (HeadIndex + 1) % MaxCapacity;

        Intent.DequeuedCycles = NowCycles;
        if (Intent.EnqueuedCycles > 0 && NowCycles >= Intent.EnqueuedCycles)
        {
            double WaitMs = CyclesToMs(NowCycles - Intent.EnqueuedCycles);
            LastQueueWaitDurationMs.store(WaitMs, std::memory_order_relaxed);
        }

        OutIntents.Add(MoveTemp(Intent));
    }

    Count -= ToPop;
    TotalDequeuedCount.fetch_add(ToPop, std::memory_order_relaxed);
    return ToPop;
}

void FAtlasLiveIngressQueue::RecordMalformedRejection()
{
    TotalRejectedMalformedCount.fetch_add(1, std::memory_order_relaxed);
}

void FAtlasLiveIngressQueue::ResetSession(const FString& NewSessionId)
{
    FScopeLock Lock(&Mutex);
    CurrentSessionId = NewSessionId;
    LastSeenSequenceNumber = 0;
}

void FAtlasLiveIngressQueue::Shutdown()
{
    bIsShutdown.store(true, std::memory_order_release);
}

bool FAtlasLiveIngressQueue::IsShutdown() const
{
    return bIsShutdown.load(std::memory_order_acquire);
}

FAtlasLiveQueueTelemetry FAtlasLiveIngressQueue::GetTelemetry() const
{
    FScopeLock Lock(&Mutex);
    FAtlasLiveQueueTelemetry Telemetry;
    Telemetry.CurrentDepth = Count;
    Telemetry.MaxCapacity = MaxCapacity;
    Telemetry.UtilizationRatio = (float)Count / (float)MaxCapacity;
    Telemetry.bWarningThresholdExceeded = (Telemetry.UtilizationRatio >= WarningRatio);
    Telemetry.TotalEnqueued = TotalEnqueuedCount.load(std::memory_order_relaxed);
    Telemetry.TotalDequeued = TotalDequeuedCount.load(std::memory_order_relaxed);
    Telemetry.TotalDroppedOverflow = TotalDroppedOverflowCount.load(std::memory_order_relaxed);
    Telemetry.TotalRejectedDuplicate = TotalRejectedDuplicateCount.load(std::memory_order_relaxed);
    Telemetry.TotalRejectedOutOfOrder = TotalRejectedOutOfOrderCount.load(std::memory_order_relaxed);
    Telemetry.TotalRejectedMalformed = TotalRejectedMalformedCount.load(std::memory_order_relaxed);
    Telemetry.LastQueueWaitMs = LastQueueWaitDurationMs.load(std::memory_order_relaxed);
    Telemetry.LastDispatchDurationMs = LastDispatchDurationMs.load(std::memory_order_relaxed);
    return Telemetry;
}

int32 FAtlasLiveIngressQueue::GetDepth() const
{
    FScopeLock Lock(&Mutex);
    return Count;
}

void FAtlasLiveIngressQueue::Empty()
{
    FScopeLock Lock(&Mutex);
    HeadIndex = 0;
    TailIndex = 0;
    Count = 0;
    DeduplicationSet.Empty();
    for (int32 i = 0; i < DeduplicationWindowSize; ++i)
    {
        DeduplicationWindow[i].Empty();
    }
    DedupInsertIndex = 0;
}
