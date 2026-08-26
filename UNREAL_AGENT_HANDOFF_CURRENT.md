# Atlas Unreal Agent — Current Development Handoff

**Updated:** August 26, 2026
**Branch:** `feat/unreal-composite-production-operation`

## Verified checkpoint before Blueprint work

The Unreal recovery/composite development checkpoint passed:

```text
Focused Sequencer recovery:
10 passed

Live recovery/composite integration gates:
8 passed

Full repository regression:
743 passed, 5 skipped
```

The UE 5.6 Unreal harness was associated with the project and the branch was pushed with a clean working tree.

## Completed production boundaries

The Unreal Agent currently has production execution and independent verification for:

- Actor inspection and transforms
- Material variants
- Niagara variants
- Sequencer playback range
- Composite actor production plans
- Explicit authorized replacement
- Fresh-state recovery reassessment
- Heterogeneous recovery
- Windows Named Pipe transport
- Live Unreal integration gates

The recovery architecture is fail-closed:

```text
failure
  ↓
fresh read-only reassessment
  ↓
per-operation disposition
  ↓
replacement-only plan
  ↓
separate plan-bound authorization
  ↓
execution
  ↓
independent verification
```

A failed write is never silently retried.

## Sequencer boundary

```text
READ  inspect_sequencer_state
WRITE set_sequencer_playback_range
VERIFY verify_sequencer_playback_range
```

Sequencer production and recovery are covered by deterministic tests and live Unreal gates.

## Blueprint — CURRENT DEVELOPMENT

Blueprint is now the next production capability. The first slice is deliberately narrow:

```text
READ   inspect_blueprint_state
WRITE  compile_blueprint
VERIFY verify_blueprint_state
```

The Python side now contains:

- Blueprint capability argument schemas
- explicit Unreal asset-path validation
- Blueprint compile planning
- production-adapter verification routing
- independent Blueprint evidence verification
- focused Blueprint planner/verifier tests

The Unreal transport header now declares the corresponding Blueprint operations, and the transport build dependency includes the Blueprint compiler module.

## Local Blueprint transport migration

The C++ dispatcher still needs to be applied to the local Unreal source because it is the live editor boundary.

A deterministic migration script is committed at:

```text
tools/enable_blueprint_transport.py
```

Run from the repository root after pulling the current branch:

```powershell
python tools\enable_blueprint_transport.py
```

The script is intentionally fail-closed. It edits only known transport anchors and aborts if the dispatcher has drifted rather than guessing.

The implementation uses `UBlueprint::Status` for normalized compilation evidence and `FKismetEditorUtilities::CompileBlueprint` for the editor-side compile operation. Epic documents both APIs in the UE editor/runtime API reference. citeturn1search0turn0search0

## Blueprint validation sequence

After pulling and applying the transport migration:

```powershell
python -m pytest tests/test_unreal_blueprint.py tests/test_unreal_task_planner.py -q
```

Then rebuild/reload the Unreal harness and add/run the live Blueprint integration gate.

Finally:

```powershell
python -m pytest tests -q
```

The previous **743 passed / 5 skipped** result remains the regression baseline until the Blueprint transport is live and verified.

## Blueprint architectural rule

Compilation is the first Blueprint slice. Do not jump directly to arbitrary graph mutation.

Once compilation is proven end-to-end, expand Blueprint authoring incrementally into:

1. component authoring
2. variable authoring
3. node creation
4. pin/graph connections
5. controlled graph verification
6. Blueprint recovery

Each must use the same plan → authorization → execution → evidence → verification boundary.

## Next boundary after Blueprint

Once Blueprint is production-complete, build the Render production boundary:

```text
READ   inspect_render_state
WRITE  configure_render
VERIFY verify_render_state
```

Movie Render Queue execution should be layered on top only after deterministic render configuration verification exists.

## Architectural invariants

- Atlas owns the canonical Digital Twin.
- Atlas plans and authorizes.
- Unreal executes.
- Unreal provides evidence.
- Atlas independently verifies evidence.
- Verification is never satisfied by echoing requested write arguments.
- Recovery requires fresh evidence.
- Replacement requires a new exact authorization.
- The Unreal Agent does not become a second autonomous authority.
- Preserve the Named Pipe wire protocol.
- Keep Unreal isolated from Blender and the action/workflow runner.
- Do not weaken fail-closed validation.
- Preserve language-agnostic subsystem boundaries so performance-critical components can later be replaced incrementally with C++ implementations.
