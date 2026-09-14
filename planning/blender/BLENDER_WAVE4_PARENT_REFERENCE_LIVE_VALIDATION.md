# Atlas Blender — Wave 4 Parent Reference Live Validation

## Status
**LIVE GATE READY — EXECUTION REQUIRED ON THE USER'S BLENDER HOST**

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

## Files

- `tests/parent_reference_live_script.py` — disposable headless Blender script.
- `tests/test_live_blender_parent_reference_gate.py` — pytest launcher and static safety gate.

## Expected environment

- Blender **4.4.3**
- Python/pytest available in the Atlas checkout

## Run

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

## Promotion gate

This evidence is necessary but is **not** by itself Wave 4 closure. Formal promotion still requires deterministic Wave 4 evidence plus an independent red-team review of the complete planner/executor implementation.
