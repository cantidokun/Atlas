# Atlas Blender — Wave 4 Parent Reference Live Validation

## Status
**LIVE GATE CLEARED — FINAL WAVE 4 RED-TEAM REVIEW CLEARED**

This branch contains a self-contained, boundary-faithful live proof for Wave 4.

## Boundary decision
A genuine dangling `bpy.types.Object.parent` reference cannot normally be manufactured through Blender's live API: Blender maintains object-ID relationships and clears the relationship when a referenced parent is removed. Therefore the live proof does not fake a malformed canonical report inside Blender.

Instead, the live gate proves the engine-side primitive that Wave 4 depends on:

1. create a disposable child and parent in memory;
2. establish a non-trivial parent inverse and transforms;
3. execute `bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")`;
4. verify the child parent is cleared;
5. verify world transform and non-parent state are preserved;
6. verify object/mesh identity and object set are unchanged;
7. verify the parent datablock remains present;
8. verify no `.blend` file was opened or saved.

The canonical malformed-parent planner/executor remains a separate deterministic layer and is not silently replaced by this Blender primitive test.

## Live evidence

The authorized live Blender run was executed on the user's Blender 4.4.3 host with:

```powershell
$env:ATLAS_RUN_LIVE_BLENDER="1"
python -m pytest tests/test_live_blender_extraction_gate.py tests/test_live_blender_parent_reference_gate.py -q
```

Result:

```text
... [100%]
3 passed in 1.48s
```

This covers both the live extraction-to-SceneReport gate and the Wave-4 Blender parent-detach gate. The fixture uses the profile's permitted `Field` and `Goals` collections and remains disposable/in-memory; production extraction code and frozen assets were not modified.

## Files

- `tests/parent_reference_live_script.py` — disposable headless Blender script.
- `tests/test_live_blender_parent_reference_gate.py` — pytest launcher and static safety gate.
- `tests/test_live_blender_extraction_gate.py` — live extraction-to-report gate using the same disposable boundary.

## Expected environment

- Blender **4.4.3**
- Python/pytest available in the Atlas checkout

## Re-run

From the Atlas root in PowerShell:

```powershell
$env:ATLAS_RUN_LIVE_BLENDER="1"
python -m pytest tests/test_live_blender_parent_reference_gate.py -q
```

If Blender is not on `PATH`, point directly at the executable:

```powershell
$env:ATLAS_BLENDER_EXECUTABLE="C:\Path\To\blender.exe"
$env:ATLAS_RUN_LIVE_BLENDER="1"
python -m pytest tests/test_live_blender_parent_reference_gate.py -q
```

The gate runs Blender headlessly and uses only an in-memory disposable scene. It does not open `tests/assets/blender/atlas_transform_validation.blend` and does not save a file.

## Final promotion decision

Wave 4's final promotion gate is cleared on the basis of:

- deterministic planner/executor coverage;
- the permanent 500-case hostile corpus, with rejected hostile cases reaching zero mutation at the seam;
- postcondition adversarial coverage for unrelated-object mutation and object-identity-set changes;
- fresh source-digest binding before mutation;
- exactly-one mutation seam;
- live Blender detach and transform-preservation evidence;
- live extraction-to-report evidence;
- the explicit boundary limitation that genuine dangling `bpy.types.Object.parent` state is not manufacturable through the current Blender extraction boundary;
- preservation of the M5 render-evidence boundary and M12.5 frozen authority boundary.

The red-team review also records two intentional architectural limitations rather than treating them as hidden capabilities: the Wave-4 authorization check is binding-only (it does not authenticate the identity of the artifact author), and postcondition failure does not imply rollback because Wave 4 owns no recovery/rollback authority. Those responsibilities remain outside this correction module's authority boundary.
