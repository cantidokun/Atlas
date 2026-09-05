#include "Misc/AutomationTest.h"
#include "AtlasLiveIngressQueue.h"
#include "AtlasLiveGameThreadPump.h"
#include "HAL/Runnable.h"
#include "HAL/RunnableThread.h"
#include "HAL/PlatformProcess.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasLiveIngressQueueTest,
    "Atlas.Live.IngressQueue.BoundaryVerification",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

namespace
{
    FAtlasLiveProductionIntent MakeTestIntent(
        const FString& InIntentId,
        uint64 InSeq,
        const FString& InSessionId = TEXT("session-1"),
        EAtlasLiveTreatment InTreatment = EAtlasLiveTreatment::ImpactAccent)
    {
        FAtlasLiveProductionIntent Intent;
        Intent.IntentId = InIntentId;
        Intent.SequenceNumber = InSeq;
        Intent.SessionId = InSessionId;
        Intent.Treatment = InTreatment;
        Intent.SourceEventId = FString::Printf(TEXT("evt-%s"), *InIntentId);
        Intent.TargetEntityIds.Add(TEXT("player-09"));
        Intent.Intensity = 0.8f;
        Intent.DurationMs = 200;
        Intent.SourceTimestampNs = 1000000;
        Intent.TransportSentAtNs = 1000500;
        return Intent;
    }

    class FTestEffectDispatcher : public IAtlasLiveEffectDispatcher
    {
    public:
        TArray<FAtlasLiveProductionIntent> DispatchedIntents;

        virtual bool DispatchIntent(const FAtlasLiveProductionIntent& Intent) override
        {
            DispatchedIntents.Add(Intent);
            return true;
        }
    };

    class FProducerRunnable : public FRunnable
    {
    public:
        FAtlasLiveIngressQueue& TargetQueue;
        int32 ProducerId;
        int32 IntentsToProduce;
        int32 EnqueuedSuccessfully;

        FProducerRunnable(FAtlasLiveIngressQueue& InQueue, int32 InId, int32 InCount)
            : TargetQueue(InQueue)
            , ProducerId(InId)
            , IntentsToProduce(InCount)
            , EnqueuedSuccessfully(0)
        {
        }

        virtual uint32 Run() override
        {
            FString Session = FString::Printf(TEXT("prod-session-%d"), ProducerId);
            for (int32 i = 1; i <= IntentsToProduce; ++i)
            {
                FString IntentId = FString::Printf(TEXT("intent-p%d-%04d"), ProducerId, i);
                FAtlasLiveProductionIntent Intent = MakeTestIntent(IntentId, (uint64)i, Session);
                EAtlasLiveEnqueueResult Result = TargetQueue.Enqueue(Intent);
                if (Result == EAtlasLiveEnqueueResult::Success || Result == EAtlasLiveEnqueueResult::DroppedOverflow)
                {
                    EnqueuedSuccessfully++;
                }
            }
            return 0;
        }
    };
}

bool FAtlasLiveIngressQueueTest::RunTest(const FString& Parameters)
{
    // -------------------------------------------------------------
    // Test 1: FIFO sequence enforcement and monotonic ordering
    // -------------------------------------------------------------
    {
        FAtlasLiveIngressQueue Queue(10);
        EAtlasLiveEnqueueResult Res1 = Queue.Enqueue(MakeTestIntent(TEXT("id-1"), 1));
        EAtlasLiveEnqueueResult Res2 = Queue.Enqueue(MakeTestIntent(TEXT("id-2"), 2));
        EAtlasLiveEnqueueResult ResOutOfOrder = Queue.Enqueue(MakeTestIntent(TEXT("id-3"), 2)); // Re-used sequence
        EAtlasLiveEnqueueResult ResLowerSeq = Queue.Enqueue(MakeTestIntent(TEXT("id-4"), 1));   // Lower sequence

        TestEqual(TEXT("First intent accepted"), Res1, EAtlasLiveEnqueueResult::Success);
        TestEqual(TEXT("Second intent accepted"), Res2, EAtlasLiveEnqueueResult::Success);
        TestEqual(TEXT("Duplicate sequence rejected out-of-order"), ResOutOfOrder, EAtlasLiveEnqueueResult::RejectedOutOfOrder);
        TestEqual(TEXT("Lower sequence rejected out-of-order"), ResLowerSeq, EAtlasLiveEnqueueResult::RejectedOutOfOrder);

        FAtlasLiveProductionIntent Out1;
        FAtlasLiveProductionIntent Out2;
        TestTrue(TEXT("Dequeue first item"), Queue.Dequeue(Out1));
        TestEqual(TEXT("First item ID matches FIFO"), Out1.IntentId, FString(TEXT("id-1")));
        TestTrue(TEXT("Dequeue second item"), Queue.Dequeue(Out2));
        TestEqual(TEXT("Second item ID matches FIFO"), Out2.IntentId, FString(TEXT("id-2")));
        TestFalse(TEXT("Queue is now empty"), Queue.Dequeue(Out1));
    }

    // -------------------------------------------------------------
    // Test 2: Duplicate Intent ID rejection
    // -------------------------------------------------------------
    {
        FAtlasLiveIngressQueue Queue(10);
        EAtlasLiveEnqueueResult Res1 = Queue.Enqueue(MakeTestIntent(TEXT("duplicate-id"), 1));
        EAtlasLiveEnqueueResult Res2 = Queue.Enqueue(MakeTestIntent(TEXT("duplicate-id"), 2));

        TestEqual(TEXT("Original ID accepted"), Res1, EAtlasLiveEnqueueResult::Success);
        TestEqual(TEXT("Same ID rejected as duplicate"), Res2, EAtlasLiveEnqueueResult::RejectedDuplicate);

        FAtlasLiveQueueTelemetry Telemetry = Queue.GetTelemetry();
        TestEqual(TEXT("Duplicate counter incremented"), Telemetry.TotalRejectedDuplicate, (int64)1);
    }

    // -------------------------------------------------------------
    // Test 3: Malformed message rejection
    // -------------------------------------------------------------
    {
        FAtlasLiveIngressQueue Queue(10);
        FAtlasLiveProductionIntent MalformedIntent = MakeTestIntent(TEXT(""), 1);
        EAtlasLiveEnqueueResult Res = Queue.Enqueue(MalformedIntent);

        TestEqual(TEXT("Empty IntentId rejected as malformed"), Res, EAtlasLiveEnqueueResult::RejectedMalformed);
        TestEqual(TEXT("Queue remains empty on malformed intent"), Queue.GetDepth(), 0);

        Queue.RecordMalformedRejection();
        TestEqual(TEXT("Malformed counter incremented"), Queue.GetTelemetry().TotalRejectedMalformed, (int64)2);
    }

    // -------------------------------------------------------------
    // Test 4: Bounded Capacity & Deterministic Overflow (Drop Oldest)
    // -------------------------------------------------------------
    {
        const int32 Capacity = 3;
        FAtlasLiveIngressQueue Queue(Capacity);

        EAtlasLiveEnqueueResult R1 = Queue.Enqueue(MakeTestIntent(TEXT("item-1"), 1));
        EAtlasLiveEnqueueResult R2 = Queue.Enqueue(MakeTestIntent(TEXT("item-2"), 2));
        EAtlasLiveEnqueueResult R3 = Queue.Enqueue(MakeTestIntent(TEXT("item-3"), 3));

        TestEqual(TEXT("Item 1 enqueued"), R1, EAtlasLiveEnqueueResult::Success);
        TestEqual(TEXT("Item 2 enqueued"), R2, EAtlasLiveEnqueueResult::Success);
        TestEqual(TEXT("Item 3 enqueued"), R3, EAtlasLiveEnqueueResult::Success);
        TestEqual(TEXT("Queue depth at max capacity"), Queue.GetDepth(), Capacity);

        // 4th item forces eviction of oldest ("item-1")
        EAtlasLiveEnqueueResult R4 = Queue.Enqueue(MakeTestIntent(TEXT("item-4"), 4));
        TestEqual(TEXT("Overflow returns DroppedOverflow"), R4, EAtlasLiveEnqueueResult::DroppedOverflow);
        TestEqual(TEXT("Queue depth stays bounded"), Queue.GetDepth(), Capacity);

        FAtlasLiveProductionIntent Popped;
        TestTrue(TEXT("Dequeue returns head"), Queue.Dequeue(Popped));
        TestEqual(TEXT("Oldest item-1 was dropped; head is now item-2"), Popped.IntentId, FString(TEXT("item-2")));

        TestTrue(TEXT("Dequeue returns item-3"), Queue.Dequeue(Popped));
        TestEqual(TEXT("Next is item-3"), Popped.IntentId, FString(TEXT("item-3")));

        TestTrue(TEXT("Dequeue returns item-4"), Queue.Dequeue(Popped));
        TestEqual(TEXT("Last is newest item-4"), Popped.IntentId, FString(TEXT("item-4")));

        TestFalse(TEXT("Queue is now empty"), Queue.Dequeue(Popped));
    }

    // -------------------------------------------------------------
    // Test 5: Reconnect / Session Reset
    // -------------------------------------------------------------
    {
        FAtlasLiveIngressQueue Queue(10);
        Queue.Enqueue(MakeTestIntent(TEXT("session1-1"), 100, TEXT("session-1")));
        Queue.Enqueue(MakeTestIntent(TEXT("session1-2"), 101, TEXT("session-1")));

        // New session resets sequence numbers back to 1
        EAtlasLiveEnqueueResult ResNewSession = Queue.Enqueue(MakeTestIntent(TEXT("session2-1"), 1, TEXT("session-2")));
        TestEqual(TEXT("New session with sequence 1 accepted without out-of-order error"), ResNewSession, EAtlasLiveEnqueueResult::Success);

        TestEqual(TEXT("Total queued depth is 3"), Queue.GetDepth(), 3);
    }

    // -------------------------------------------------------------
    // Test 6: Non-blocking Shutdown Behavior
    // -------------------------------------------------------------
    {
        FAtlasLiveIngressQueue Queue(10);
        Queue.Enqueue(MakeTestIntent(TEXT("before-shutdown"), 1));

        Queue.Shutdown();
        TestTrue(TEXT("Queue reports shutdown"), Queue.IsShutdown());

        EAtlasLiveEnqueueResult PostShutdownResult = Queue.Enqueue(MakeTestIntent(TEXT("after-shutdown"), 2));
        TestEqual(TEXT("Enqueue rejected after shutdown"), PostShutdownResult, EAtlasLiveEnqueueResult::RejectedShutdown);

        FAtlasLiveProductionIntent DrainIntent;
        TestTrue(TEXT("Existing items can still be drained cleanly after shutdown"), Queue.Dequeue(DrainIntent));
        TestEqual(TEXT("Drained item matches"), DrainIntent.IntentId, FString(TEXT("before-shutdown")));
    }

    // -------------------------------------------------------------
    // Test 7: Deterministic GameThread Pump & Batch Draining
    // -------------------------------------------------------------
    {
        TSharedPtr<FAtlasLiveIngressQueue> Queue = MakeShared<FAtlasLiveIngressQueue>(20);
        TSharedPtr<FTestEffectDispatcher> Dispatcher = MakeShared<FTestEffectDispatcher>();
        const int32 MaxBatch = 4;
        FAtlasLiveGameThreadPump Pump(Queue, Dispatcher, MaxBatch);

        // Push 10 intents
        for (int32 i = 1; i <= 10; ++i)
        {
            Queue->Enqueue(MakeTestIntent(FString::Printf(TEXT("batch-%d"), i), (uint64)i));
        }

        TestEqual(TEXT("Queue depth before tick is 10"), Queue->GetDepth(), 10);

        // Tick 1: should pop exactly MaxBatch (4)
        Pump.Tick(0.016f);
        TestEqual(TEXT("Queue depth after tick 1 is 6"), Queue->GetDepth(), 6);
        TestEqual(TEXT("Dispatcher received 4 intents"), Dispatcher->DispatchedIntents.Num(), 4);
        TestEqual(TEXT("First dispatched item is batch-1"), Dispatcher->DispatchedIntents[0].IntentId, FString(TEXT("batch-1")));
        TestEqual(TEXT("Fourth dispatched item is batch-4"), Dispatcher->DispatchedIntents[3].IntentId, FString(TEXT("batch-4")));

        // Tick 2: should pop next 4 (batch-5 to batch-8)
        Pump.Tick(0.016f);
        TestEqual(TEXT("Queue depth after tick 2 is 2"), Queue->GetDepth(), 2);
        TestEqual(TEXT("Dispatcher total is 8"), Dispatcher->DispatchedIntents.Num(), 8);

        // Tick 3: should pop remaining 2
        Pump.Tick(0.016f);
        TestEqual(TEXT("Queue depth after tick 3 is 0"), Queue->GetDepth(), 0);
        TestEqual(TEXT("Dispatcher total is 10"), Dispatcher->DispatchedIntents.Num(), 10);
        TestEqual(TEXT("Tenth dispatched item is batch-10"), Dispatcher->DispatchedIntents[9].IntentId, FString(TEXT("batch-10")));

        // Verify timestamps populated
        TestTrue(TEXT("EnqueuedCycles was recorded"), Dispatcher->DispatchedIntents[0].EnqueuedCycles > 0);
        TestTrue(TEXT("DequeuedCycles was recorded"), Dispatcher->DispatchedIntents[0].DequeuedCycles > 0);
        TestTrue(TEXT("DispatchedCycles was recorded"), Dispatcher->DispatchedIntents[0].DispatchedCycles > 0);
        TestTrue(TEXT("Dequeued >= Enqueued"), Dispatcher->DispatchedIntents[0].DequeuedCycles >= Dispatcher->DispatchedIntents[0].EnqueuedCycles);
    }

    // -------------------------------------------------------------
    // Test 8: Multi-Threaded Concurrent Producers (MPSC Validation)
    // -------------------------------------------------------------
    {
        const int32 ThreadCount = 4;
        const int32 IntentsPerThread = 50;
        const int32 TotalIntents = ThreadCount * IntentsPerThread;

        FAtlasLiveIngressQueue Queue(TotalIntents * 2); // Plenty of capacity to avoid overflow in this test

        TArray<FProducerRunnable*> Runnables;
        TArray<FRunnableThread*> Threads;

        for (int32 i = 0; i < ThreadCount; ++i)
        {
            FProducerRunnable* Runnable = new FProducerRunnable(Queue, i + 1, IntentsPerThread);
            Runnables.Add(Runnable);
            FString ThreadName = FString::Printf(TEXT("AtlasTestProducerThread_%d"), i + 1);
            FRunnableThread* Thread = FRunnableThread::Create(Runnable, *ThreadName);
            Threads.Add(Thread);
        }

        // Wait for all producer threads to complete
        for (FRunnableThread* Thread : Threads)
        {
            Thread->WaitForCompletion();
            delete Thread;
        }

        int32 TotalSuccessful = 0;
        for (FProducerRunnable* Runnable : Runnables)
        {
            TotalSuccessful += Runnable->EnqueuedSuccessfully;
            delete Runnable;
        }

        TestEqual(TEXT("All concurrent producer threads succeeded"), TotalSuccessful, TotalIntents);
        TestEqual(TEXT("Queue depth equals total enqueued from all threads"), Queue.GetDepth(), TotalIntents);

        // Drain on consumer side
        TArray<FAtlasLiveProductionIntent> Drained;
        int32 Popped = Queue.DequeueBatch(Drained, TotalIntents * 2);
        TestEqual(TEXT("All items drained successfully from MPSC queue"), Popped, TotalIntents);
        TestEqual(TEXT("Queue is completely drained"), Queue.GetDepth(), 0);
    }

    return !HasAnyErrors();
}
