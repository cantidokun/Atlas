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

The Python side contains:

- Blueprint capability argument schemas
- explicit Unreal asset-path validation
- Blueprint compile planning
- production-adapter verification routing
- independent Blueprint evidence verification
- focused Blueprint planner/verifier tests
- a real Unreal Blueprint integration gate

The Unreal transport implements the corresponding Blueprint operations, and the transport build dependency includes the Blueprint compiler module.

## Real Blueprint fixture

The Unreal harness now contains a deterministic editor commandlet that creates and saves the real integration fixture:

```text
/Game/AtlasTest/BP_AtlasTest.BP_AtlasTest
```

The resulting `.uasset` is generated under the harness Content tree rather than requiring manual Blueprint authoring in the editor.

The harness builds successfully under UE 5.6, and the live integration gate has passed:

```text
python -m pytest tests/test_unreal_blueprint_real_integration.py -q

1 passed in 0.76s
```

This proves the complete production path:

```text
Python planner/executor
        ↓
production adapter
        ↓
Named Pipe
        ↓
Unreal Blueprint transport
        ↓
real UE Blueprint asset
        ↓
compile
        ↓
evidence
        ↓
independent verification
```

## Blueprint failure-path hardening — IN PROGRESS

The real Blueprint integration suite now also covers the missing-asset boundary. A nonexistent Blueprint must fail through the executor with operation context and the requested asset path rather than being treated as a successful no-op.

The current test change is committed but still needs to be pulled and run against the live UE 5.6 editor/transport.

Validation command:

```powershell
python -m pytest tests/test_unreal_blueprint_real_integration.py -q
```

Expected result after pulling the latest commit and with the fixture/transport available:

```text
2 passed
```

## Blueprint architectural rule

Compilation is the first Blueprint slice. Do not jump directly to arbitrary graph mutation.

The next development sequence is:

1. harden missing/invalid asset failure semantics
2. prove controlled Blueprint mutation through the production boundary
3. independently verify the mutation
4. prove Blueprint failure/recovery semantics
5. freeze the Blueprint production contract
6. expand authoring incrementally into component authoring, variable authoring, node creation, pin/graph connections, and controlled graph verification

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
