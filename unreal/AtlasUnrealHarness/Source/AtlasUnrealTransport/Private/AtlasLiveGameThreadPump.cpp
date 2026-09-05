#include "AtlasLiveGameThreadPump.h"
#include "AtlasUnrealTransport.h"
#include "HAL/PlatformTime.h"

FAtlasLiveGameThreadPump::FAtlasLiveGameThreadPump(
    TSharedPtr<FAtlasLiveIngressQueue> InQueue,
    TSharedPtr<IAtlasLiveEffectDispatcher> InDispatcher,
    int32 InMaxIntentsPerTick)
    : Queue(InQueue)
    , Dispatcher(InDispatcher)
    , MaxIntentsPerTick(FMath::Max(1, InMaxIntentsPerTick))
    , TotalDispatchedCount(0)
    , TotalFailedDispatchCount(0)
{
}

FAtlasLiveGameThreadPump::~FAtlasLiveGameThreadPump()
{
    Stop();
}

void FAtlasLiveGameThreadPump::Start()
{
    if (TickerHandle.IsValid())
    {
        return;
    }

    TickerHandle = FTSTicker::GetCoreTicker().AddTicker(
        FTickerDelegate::CreateRaw(this, &FAtlasLiveGameThreadPump::Tick),
        0.0f // Tick every frame
    );
}

void FAtlasLiveGameThreadPump::Stop()
{
    if (TickerHandle.IsValid())
    {
        FTSTicker::GetCoreTicker().RemoveTicker(TickerHandle);
        TickerHandle.Reset();
    }
}

void FAtlasLiveGameThreadPump::SetDispatcher(TSharedPtr<IAtlasLiveEffectDispatcher> InDispatcher)
{
    Dispatcher = InDispatcher;
}

bool FAtlasLiveGameThreadPump::Tick(float DeltaTime)
{
    if (!Queue.IsValid())
    {
        return true;
    }

    // Bounded batch dequeue to protect frame budget
    TArray<FAtlasLiveProductionIntent> Batch;
    int32 PoppedCount = Queue->DequeueBatch(Batch, MaxIntentsPerTick);

    if (PoppedCount == 0)
    {
        return true;
    }

    for (FAtlasLiveProductionIntent& Intent : Batch)
    {
        uint64 DispatchStartCycles = FPlatformTime::Cycles64();
        Intent.DispatchedCycles = DispatchStartCycles;

        bool bSuccess = false;
        if (Dispatcher.IsValid())
        {
            bSuccess = Dispatcher->DispatchIntent(Intent);
        }
        else
        {
            // Default acceptance if no dispatcher registered (e.g. testing / default live pump)
            bSuccess = true;
        }

        uint64 DispatchEndCycles = FPlatformTime::Cycles64();
        double DispatchDurationMs = FAtlasLiveIngressQueue::CyclesToMs(DispatchEndCycles - DispatchStartCycles);

        if (bSuccess)
        {
            TotalDispatchedCount++;
            UE_LOG(LogAtlasTransport, Display, TEXT("Atlas Live GameThread pumped and dispatched intent: %s, seq: %llu, duration: %.3f ms"),
                *Intent.IntentId, Intent.SequenceNumber, DispatchDurationMs);
        }
        else
        {
            TotalFailedDispatchCount++;
        }
    }

    return true;
}
