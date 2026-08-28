from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXECUTOR = ROOT / "planning/unreal_plan_executor.py"
RENDER = ROOT / "planning/unreal_render_contract.py"
CPP = ROOT / "unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Private/AtlasTransportServer.cpp"
FIX = ROOT / "tools/apply_unreal_render_executor_fix.py"


def replace_once(path, old, new):
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Could not find patch anchor in {path}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    EXECUTOR,
    'def _execute_one(self,operation,authorization_id,*,expected_location=None,expected_rotation=None,expected_scale=None,expected_material_variant=None,expected_niagara_variant=None,expected_start_frame=None,expected_end_frame=None):',
    'def _execute_one(self,operation,authorization_id,*,expected_location=None,expected_rotation=None,expected_scale=None,expected_material_variant=None,expected_niagara_variant=None,expected_start_frame=None,expected_end_frame=None,expected_render_config=None):',
)
replace_once(
    EXECUTOR,
    '            if expected_start_frame is not None and expected_end_frame is not None: evidence=verify_sequencer_playback_range(evidence,expected_start_frame,expected_end_frame)\n',
    '            if expected_start_frame is not None and expected_end_frame is not None: evidence=verify_sequencer_playback_range(evidence,expected_start_frame,expected_end_frame)\n            if expected_render_config is not None: evidence=verify_render_config(evidence,expected_render_config)\n',
)
replace_once(
    EXECUTOR,
    'expected_start_frame=expected.get("start_frame"),expected_end_frame=expected.get("end_frame"))',
    'expected_start_frame=expected.get("start_frame"),expected_end_frame=expected.get("end_frame"),expected_render_config=expected.get("render_config"))',
)
replace_once(
    EXECUTOR,
    '        if write_operation.name=="configure_render": return {key:a[key] for key in ("width","height","start_frame","end_frame","output_directory","output_format")}\n',
    '        if write_operation.name=="configure_render": return {"render_config": {key:a[key] for key in ("width","height","start_frame","end_frame","output_directory","output_format")}}\n',
)

replace_once(
    RENDER,
    '    state = observed.get("render") if isinstance(observed, Mapping) else None\n',
    '    state = None\n    if isinstance(observed, Mapping):\n        for entry in observed.values():\n            if isinstance(entry, Mapping) and isinstance(entry.get("render"), Mapping):\n                state = entry["render"]\n                break\n',
)

# Persist the real MRQ config asset after mutation so a subsequent independent load sees the change.
replace_once(
    CPP,
    '    Config->MarkPackageDirty();\n    if(!Config->GetOutermost()->IsDirty()) Config->GetOutermost()->MarkPackageDirty();\n    return InspectRenderState(R,O,E);',
    '''    Config->MarkPackageDirty();
    UPackage* Package=Config->GetOutermost();
    if(!Package){E=TEXT("Render config package unavailable");return false;}
    Package->MarkPackageDirty();
    const FString PackageFilename=FPackageName::LongPackageNameToFilename(Package->GetName(),FPackageName::GetAssetPackageExtension());
    FSavePackageArgs SaveArgs; SaveArgs.TopLevelFlags=RF_Public|RF_Standalone; SaveArgs.SaveFlags=SAVE_None;
    if(!UPackage::SavePackage(Package,Config,*PackageFilename,SaveArgs)){E=TEXT("Failed to save Unreal render configuration asset");return false;}
    return InspectRenderState(R,O,E);''',
)

print("Applied Unreal render executor/evidence persistence fixes.")
