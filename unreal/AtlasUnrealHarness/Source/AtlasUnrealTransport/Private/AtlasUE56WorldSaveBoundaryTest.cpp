#include "Misc/AutomationTest.h"
#include "Factories/WorldFactory.h"
#include "FileHelpers.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "UObject/Package.h"
#include "Engine/World.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FAtlasUE56WorldSaveBoundaryTest,
    "Atlas.UnrealAgent.UE56.WorldCreationAndSaveBoundary",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FAtlasUE56WorldSaveBoundaryTest::RunTest(const FString& Parameters)
{
    const FString PackageName = TEXT("/Game/AtlasTest/Generated/AtlasUE56WorldCreationTest");
    const FString PackageFilename = FPackageName::LongPackageNameToFilename(
        PackageName,
        FPackageName::GetMapPackageExtension());

    if (!FPackageName::IsValidLongPackageName(PackageName))
    {
        AddError(TEXT("Generated test package name is not a valid Unreal long package name"));
        return false;
    }

    if (FPaths::FileExists(PackageFilename))
    {
        IFileManager::Get().Delete(*PackageFilename, false, true, true);
    }

    UPackage* Package = CreatePackage(*PackageName);
    TestNotNull(TEXT("CreatePackage returned a package"), Package);
    if (!Package)
    {
        return false;
    }

    Package->SetPackageFlags(PKG_NewlyCreated);

    UWorldFactory* Factory = NewObject<UWorldFactory>();
    TestNotNull(TEXT("UE 5.6 UWorldFactory was created"), Factory);
    if (!Factory)
    {
        return false;
    }

    Factory->WorldType = EWorldType::Editor;
    Factory->bCreateWorldPartition = false;
    Factory->bInformEngineOfWorld = true;

    const EObjectFlags WorldFlags = RF_Public | RF_Standalone;
    UWorld* World = Cast<UWorld>(Factory->FactoryCreateNew(
        UWorld::StaticClass(),
        Package,
        FName(TEXT("AtlasUE56WorldCreationTest")),
        WorldFlags,
        nullptr,
        GWarn));

    TestNotNull(TEXT("UWorldFactory::FactoryCreateNew returned a UWorld"), World);
    if (!World)
    {
        return false;
    }

    World->UpdateWorldComponents(true, true);
    FAssetRegistryModule::AssetCreated(World);
    Package->MarkPackageDirty();

    const bool bSaved = UEditorLoadingAndSavingUtils::SaveMap(World, PackageName);
    TestTrue(TEXT("UEditorLoadingAndSavingUtils::SaveMap saved the generated map"), bSaved);
    TestTrue(TEXT("Generated .umap exists on disk after SaveMap"), FPaths::FileExists(PackageFilename));

    if (bSaved && FPaths::FileExists(PackageFilename))
    {
        const FAssetData AssetData = FAssetRegistryModule::GetRegistry().GetAssetByObjectPath(
            FSoftObjectPath(World));
        TestTrue(TEXT("Saved world remains discoverable by the Asset Registry"), AssetData.IsValid());
    }

    if (FPaths::FileExists(PackageFilename))
    {
        IFileManager::Get().Delete(*PackageFilename, false, true, true);
    }

    return !HasAnyErrors();
}
