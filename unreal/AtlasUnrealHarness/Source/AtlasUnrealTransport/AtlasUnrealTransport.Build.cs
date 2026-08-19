using UnrealBuildTool;

public class AtlasUnrealTransport : ModuleRules
{
    public AtlasUnrealTransport(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new string[] {
            "Core",
            "CoreUObject",
            "Engine",
            "UnrealEd",
            "EditorStyle",
            "EditorWidgets",
            "ToolMenus"
        });

        PrivateDependencyModuleNames.AddRange(new string[] {
            "Slate",
            "SlateCore",
            "Json",
            "JsonUtilities",
            "ApplicationCore"
        });

        if (Target.Platform == UnrealTargetPlatform.Win64)
        {
            PublicSystemLibraries.Add("kernel32.lib");
        }
    }
}
