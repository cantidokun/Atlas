#include "AtlasRuntimeRenderBridge.h"

#include "MoviePipelineQueue.h"
#include "MoviePipelineQueueEngineSubsystem.h"
#include "MoviePipelineExecutorBase.h"
#include "MoviePipelineExecutorJob.h"
#include "MoviePipelinePrimaryConfig.h"
#include "MoviePipelineMasterConfig.h"

bool UAtlasRuntimeRenderBridge::SubmitRender(const FString& JobId, const FString& PresetPath, FString& Error)
{
    Error.Reset();
    if (JobId.IsEmpty())
    {
        Error = TEXT("JobId is required");
        return false;
    }
    if (Jobs.Contains(JobId))
    {
        Error = TEXT("Job already exists");
        return false;
    }

    UWorld* World = GetWorld();
    if (!World)
    {
        Error = TEXT("World is unavailable");
        return false;
    }

    UMoviePipelineQueueEngineSubsystem* QueueSubsystem =
        World->GetSubsystem<UMoviePipelineQueueEngineSubsystem>();
    if (!QueueSubsystem)
    {
        Error = TEXT("Movie Pipeline Queue subsystem is unavailable");
        return false;
    }

    UMoviePipelineQueue* Queue = QueueSubsystem->GetQueue();
    if (!Queue)
    {
        Error = TEXT("Movie Pipeline queue is unavailable");
        return false;
    }

    UMoviePipelineExecutorJob* Job = Queue->AllocateJob<UMoviePipelineExecutorJob>();
    if (!Job)
    {
        Error = TEXT("Unable to allocate render job");
        return false;
    }

    Job->JobName = JobId;
    ConfigureJob(Job, PresetPath);

    FAtlasRenderJobState Pending;
    Pending.JobId = JobId;
    Pending.Status = TEXT("queued");
    Jobs.Add(JobId, Pending);

    UMoviePipelineExecutorBase* Executor = QueueSubsystem->RenderJobWithExecutor(
        UMoviePipelineExecutorBase::StaticClass());
    if (!Executor)
    {
        Jobs.Remove(JobId);
        Error = TEXT("Unable to create Movie Pipeline executor");
        return false;
    }

    Executors.Add(Executor, JobId);
    Jobs[JobId].Status = TEXT("running");
    Executor->OnExecutorFinished().AddUObject(this, &UAtlasRuntimeRenderBridge::OnRenderFinished);
    return true;
}

void UAtlasRuntimeRenderBridge::ConfigureJob(UMoviePipelineExecutorJob* Job, const FString& PresetPath) const
{
    if (!Job || PresetPath.IsEmpty())
    {
        return;
    }

    if (UMoviePipelinePrimaryConfig* Config = LoadObject<UMoviePipelinePrimaryConfig>(nullptr, *PresetPath))
    {
        Job->SetConfiguration(Config);
    }
}

void UAtlasRuntimeRenderBridge::OnRenderFinished(UMoviePipelineExecutorBase* Executor, bool bSuccess)
{
    const FString* JobId = Executors.Find(Executor);
    if (!JobId)
    {
        return;
    }

    if (FAtlasRenderJobState* State = Jobs.Find(*JobId))
    {
        State->Status = bSuccess ? TEXT("completed") : TEXT("failed");
        if (!bSuccess)
        {
            State->Error = TEXT("Movie Pipeline executor reported failure");
        }
    }

    Executors.Remove(Executor);
}

bool UAtlasRuntimeRenderBridge::InspectRenderJob(const FString& JobId, FAtlasRenderJobState& State) const
{
    const FAtlasRenderJobState* Found = Jobs.Find(JobId);
    if (!Found)
    {
        State = FAtlasRenderJobState();
        return false;
    }

    State = *Found;
    return true;
}
