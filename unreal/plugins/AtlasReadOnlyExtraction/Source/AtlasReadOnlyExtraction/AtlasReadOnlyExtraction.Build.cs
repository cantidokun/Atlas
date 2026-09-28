// Copyright Epic Games, Inc. All Rights Reserved.
//
// Atlas U1 — portable read-only extraction plugin (build rules).
//
// The dependency set is the minimum the read-only extraction path actually compiles
// against. The Atlas validation harness module (unreal/AtlasUnrealHarness) additionally
// declares EditorStyle, EditorWidgets, ToolMenus, KismetCompiler, MovieRenderPipeline*
// and AssetRegistry for its fixture, blueprint, render and UI surfaces; none of those are
// needed here, and the write/render/fixture dependencies are deliberately absent so that
// no write-capable code path can be compiled into this plugin.
//
// Dependency minimality is asserted by tests/test_unreal_read_only_extraction_plugin.py
// and was confirmed by building the plugin against a host project that does not contain
// the harness (see the plugin README for the exact commands).

using UnrealBuildTool;

public class AtlasReadOnlyExtraction : ModuleRules
{
	public AtlasReadOnlyExtraction(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = ModuleRules.PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(
			new string[]
			{
				"Core",
				"CoreUObject",
				"Engine",
				// GEditor / the editor world context: the extraction core selects the world
				// itself through GEditor->GetEditorWorldContext() (extraction design §3.1.1).
				"UnrealEd",
				"LevelSequence",
				"MovieScene",
				"Json",
			});
	}
}
