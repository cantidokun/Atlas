#include "AtlasRenderFixtureCommandlet.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "MoviePipelinePrimaryConfig.h"
#include "MoviePipelineOutputSetting.h"
#include "MoviePipelineImageSequenceOutput.h"
#include "MoviePipelineDeferredPasses.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"

UAtlasRenderFixtureCommandlet::UAtlasRenderFixtureCommandlet()
{
    IsClient = false;
    IsEditor = true;
    LogToConsole = true;
}

int32 UAtlasRenderFixtureCommandlet::Main(const FString& Params)
{
    const FString PackageName = TEXT("/Game/AtlasTest/AtlasRenderConfig");
    const FString AssetName = TEXT("AtlasRenderConfig");
    const FString PackageFilename = FPackageName::LongPackageNameToFilename(
        PackageName,
        FPackageName::GetAssetPackageExtension());

    UPackage* Package = CreatePackage(*PackageName);
    if (!Package)
    {
        UE_LOG(LogTemp, Error, TEXT("Failed to create render fixture package: %s"), *PackageName);
        return 1;
    }

    UMoviePipelinePrimaryConfig* Config = LoadObject<UMoviePipelinePrimaryConfig>(Package, *AssetName);
    if (!Config)
    {
        Config = NewObject<UMoviePipelinePrimaryConfig>(Package, *AssetName, RF_Public | RF_Standalone);
    }
    if (!Config)
    {
        UE_LOG(LogTemp, Error, TEXT("Failed to create render fixture config asset"));
        return 1;
    }

    UMoviePipelineOutputSetting* OutputSetting = Cast<UMoviePipelineOutputSetting>(
        Config->FindOrAddSettingByClass(UMoviePipelineOutputSetting::StaticClass(), false, true));
    if (!OutputSetting)
    {
        UE_LOG(LogTemp, Error, TEXT("Failed to create MoviePipelineOutputSetting"));
        return 1;
    }

    OutputSetting->OutputResolution = FIntPoint(1920, 1080);
    OutputSetting->bUseCustomPlaybackRange = true;
    OutputSetting->CustomStartFrame = 1;
    OutputSetting->CustomEndFrame = 120;
    OutputSetting->OutputDirectory.Path =
        FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("AtlasRenderOutput"));
    OutputSetting->FileNameFormat = TEXT("AtlasRender_{frame_number}");

    UMoviePipelineDeferredPassBase* DeferredPass =
        Cast<UMoviePipelineDeferredPassBase>(
            Config->FindOrAddSettingByClass(
                UMoviePipelineDeferredPassBase::StaticClass(),
                false,
                true));

    if (!DeferredPass)
    {
        UE_LOG(LogTemp, Error, TEXT("Failed to create deferred render pass"));
        return 1;
    }

    UMoviePipelineImageSequenceOutput_PNG* PngOutput = Cast<UMoviePipelineImageSequenceOutput_PNG>(
        Config->FindOrAddSettingByClass(UMoviePipelineImageSequenceOutput_PNG::StaticClass(), false, true));
    if (!PngOutput)
    {
        UE_LOG(LogTemp, Error, TEXT("Failed to create PNG output setting"));
        return 1;
    }

    Package->MarkPackageDirty();

    FSavePackageArgs SaveArgs;
    SaveArgs.TopLevelFlags = RF_Public | RF_Standalone;
    SaveArgs.SaveFlags = SAVE_None;
    if (!UPackage::SavePackage(Package, Config, *PackageFilename, SaveArgs))
    {
        UE_LOG(LogTemp, Error, TEXT("Failed to save render fixture package: %s"), *PackageFilename);
        return 1;
    }

    UE_LOG(LogTemp, Display, TEXT("Atlas render fixture ready: %s.%s"), *PackageName, *AssetName);
    return 0;
}
