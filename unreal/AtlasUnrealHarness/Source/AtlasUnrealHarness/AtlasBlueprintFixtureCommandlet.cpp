#include "AtlasBlueprintFixtureCommandlet.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "AssetToolsModule.h"
#include "Factories/BlueprintFactory.h"
#include "Engine/Blueprint.h"
#include "GameFramework/Actor.h"
#include "Misc/PackageName.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"

UAtlasBlueprintFixtureCommandlet::UAtlasBlueprintFixtureCommandlet()
{
    IsClient = false;
    IsEditor = true;
    IsServer = false;
    LogToConsole = true;
}

int32 UAtlasBlueprintFixtureCommandlet::Main(const FString& Params)
{
    static const FString PackageName = TEXT("/Game/AtlasTest/BP_AtlasTest");
    static const FString AssetName = TEXT("BP_AtlasTest");

    FAssetRegistryModule& AssetRegistryModule = FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry"));
    if (AssetRegistryModule.Get().GetAssetByObjectPath(FSoftObjectPath(PackageName + TEXT(".") + AssetName)).IsValid())
    {
        UE_LOG(LogTemp, Display, TEXT("Atlas Blueprint fixture already exists: %s"), *PackageName);
        return 0;
    }

    UBlueprintFactory* Factory = NewObject<UBlueprintFactory>();
    Factory->ParentClass = AActor::StaticClass();

    const FString PackagePath = FPackageName::GetLongPackagePath(PackageName);
    UBlueprint* Blueprint = Cast<UBlueprint>(
        FAssetToolsModule::GetModule().Get().CreateAsset(
            AssetName,
            PackagePath,
            UBlueprint::StaticClass(),
            Factory));

    if (!Blueprint)
    {
        UE_LOG(LogTemp, Error, TEXT("Failed to create Atlas Blueprint fixture: %s"), *PackageName);
        return 1;
    }

    AssetRegistryModule.Get().AssetCreated(Blueprint);
    Blueprint->MarkPackageDirty();

    UPackage* Package = Blueprint->GetOutermost();
    const FString Filename = FPackageName::LongPackageNameToFilename(
        PackageName,
        FPackageName::GetAssetPackageExtension());

    FSavePackageArgs SaveArgs;
    SaveArgs.TopLevelFlags = RF_Public | RF_Standalone;
    SaveArgs.Error = GError;

    if (!UPackage::SavePackage(Package, Blueprint, *Filename, SaveArgs))
    {
        UE_LOG(LogTemp, Error, TEXT("Failed to save Atlas Blueprint fixture: %s"), *Filename);
        return 1;
    }

    UE_LOG(LogTemp, Display, TEXT("Created Atlas Blueprint fixture: %s"), *PackageName);
    return 0;
}
