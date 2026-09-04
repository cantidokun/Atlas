using UnrealBuildTool;

public class AtlasUnrealHarnessEditorTarget : TargetRules
{
    public AtlasUnrealHarnessEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V5;
        ExtraModuleNames.Add("AtlasUnrealHarness");
    }
}
