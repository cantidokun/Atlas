using UnrealBuildTool;

public class AtlasUnrealHarness : ModuleRules
{
    public AtlasUnrealHarness(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(
            new string[]
            {
                "Core",
                "CoreUObject",
                "Engine"
            }
        );

        PrivateDependencyModuleNames.AddRange(
            new string[]
            {
                "AssetRegistry",
                "AssetTools",
                "Json",
                "JsonUtilities",
                "UnrealEd",
                "MovieRenderPipelineCore",
                "MovieRenderPipelineRenderPasses"
            }
        );
    }
}
