#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "AtlasRuntimeRenderBridge.generated.h"

USTRUCT(BlueprintType)
struct FAtlasRenderJobState
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly)
    FString JobId;

    UPROPERTY(BlueprintReadOnly)
    FString Status;

    UPROPERTY(BlueprintReadOnly)
    FString Error;
};

UCLASS()
class ATLASUNREALHARNESS_API UAtlasRuntimeRenderBridge : public UWorldSubsystem
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintCallable, Category="Atlas|Render")
    bool SubmitRender(const FString& JobId, const FString& PresetPath, FString& Error);

    UFUNCTION(BlueprintCallable, Category="Atlas|Render")
    bool InspectRenderJob(const FString& JobId, FAtlasRenderJobState& State) const;

private:
    void OnRenderFinished(class UMoviePipelineExecutorBase* Executor, bool bSuccess);
    void ConfigureJob(class UMoviePipelineExecutorJob* Job, const FString& PresetPath) const;

    TMap<FString, FAtlasRenderJobState> Jobs;
    TMap<TWeakObjectPtr<class UMoviePipelineExecutorBase>, FString> Executors;
};
