# Atlas Unreal Agent

## Current status

The Unreal Agent has a tested production/recovery architecture for controlled Unreal operations.

Current branch:

```text
feat/unreal-composite-production-operation
```

Before Blueprint development began, the local regression checkpoint was:

```text
743 passed, 5 skipped
```

The UE 5.6 Unreal harness is associated with the project.

## Operating model

```text
AI / Unreal Agent
    ↓
reason + plan
    ↓
Atlas validation + authorization
    ↓
Unreal adapter execution
    ↓
Unreal evidence
    ↓
independent Atlas semantic verification
```

The Unreal Agent is not an independent authorization authority.

## Production boundaries already proven

The current production path covers:

- Actor inspection and transforms
- Material variants
- Niagara variants
- Sequencer playback range
- Composite production plans
- Windows Named Pipe execution
- Independent semantic verification
- Fresh-state recovery
- Explicit replacement authorization
- Heterogeneous recovery

Every supported production write is paired with an immediate semantic verifier.

## Sequencer

```text
READ  inspect_sequencer_state
WRITE set_sequencer_playback_range
VERIFY verify_sequencer_playback_range
```

Sequencer verification compares fresh Unreal state with the requested frame range rather than trusting the write response.

## Recovery

```text
Production failure
       ↓
Fresh read-only reassessment
       ↓
Per-operation disposition
       ↓
Replacement-only plan
       ↓
Separate replacement authorization
       ↓
Ordered Unreal execution
       ↓
Independent verification
```

`already_applied` operations are not replayed. `replacement_required` operations require a new exact authorization. `manual_review` never becomes an automatic mutation.

Recovery failure identity is bound to the exact source intent, operation index, operation name, and entity IDs.

## Blueprint — current development target

Blueprint is the next production capability. The first slice is deliberately limited to compilation:

```text
READ   inspect_blueprint_state
WRITE  compile_blueprint
VERIFY verify_blueprint_state
```

The Python boundary now provides:

- Blueprint capability schemas
- explicit Unreal asset-path validation
- compile task planning
- production-adapter verification routing
- independent Blueprint evidence verification
- focused planner/verifier tests

Blueprint assets are addressed by explicit Unreal package paths, not actor tags.

The Unreal transport header and build dependency have been prepared for Blueprint compilation.

A deterministic local C++ transport migration is provided:

```powershell
python tools\enable_blueprint_transport.py
```

The script edits only known transport anchors and aborts if the dispatcher has drifted.

The Unreal implementation uses `UBlueprint::Status` for state evidence and `FKismetEditorUtilities::CompileBlueprint` for editor-side compilation. urlEpic UBlueprint APIhttps://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Engine/UBlueprint urlEpic CompileBlueprint APIhttps://dev.epicgames.com/documentation/unreal-engine/API/Editor/UnrealEd/Kismet2/FKismetEditorUtilities/CompileBlueprint?application_version=5.3

## Blueprint validation

After pulling the branch and applying the transport migration:

```powershell
python -m pytest tests/test_unreal_blueprint.py tests/test_unreal_task_planner.py -q
```

Then rebuild/reload Unreal and add/run the live Blueprint integration gate.

Finally:

```powershell
python -m pytest tests -q
```

The 743-pass checkpoint remains the regression baseline until Blueprint is live and verified.

## Next after Blueprint

After Blueprint reaches a complete production boundary, build Render:

```text
READ   inspect_render_state
WRITE  configure_render
VERIFY verify_render_state
```

Movie Render Queue execution should follow only after deterministic render configuration verification is established.

## Invariants

- Atlas owns the canonical Digital Twin.
- Atlas authorizes Unreal mutations.
- Unreal executes only within the authorized plan.
- Unreal supplies evidence; Atlas verifies independently.
- Failed mutations require fresh evidence and explicit recovery.
- Replacement mutations require new plan-bound authorization.
- The Named Pipe wire protocol remains stable.
- Unreal remains isolated from Blender and the action/workflow runner.
- Failure injection belongs only in the disposable validation harness.
- Do not weaken fail-closed validation.
