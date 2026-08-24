# Atlas Unreal Agent

## Current status

The Unreal Agent is no longer only a planned production boundary. The current development branch has a working, tested production/recovery architecture for controlled Unreal operations.

Current branch:

```text
feat/unreal-composite-production-operation
```

Latest verified implementation before this documentation-only closeout:

```text
dfd253a
```

## Operating model

The Unreal Agent follows the same Atlas authority model as the rest of the platform:

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

The Unreal Agent is not an independent autonomous authority. Atlas owns authorization, execution state, verification, and recovery boundaries.

## Production sequence

The composite production path is structured as ordered read/write/verify operations:

```text
READ  inspect_target_actors
WRITE set_actor_location
VERIFY verify_actor_location
WRITE set_actor_rotation
VERIFY verify_actor_rotation
WRITE set_actor_scale
VERIFY verify_actor_scale
READ  inspect_material_state
WRITE apply_material_variant
VERIFY verify_material_variant
READ  inspect_niagara_state
WRITE apply_niagara_variant
VERIFY verify_niagara_variant
```

Every supported production write is immediately followed by its matching semantic verifier.

## Sequencer

Sequencer production is independently planned and verified:

```text
READ  inspect_sequencer_state
WRITE set_sequencer_playback_range
VERIFY verify_sequencer_playback_range
```

The verification boundary checks the requested start/end frame range rather than treating successful command execution as proof.

## Recovery

Unreal recovery is explicitly non-retry-based:

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
Immediate semantic verification
       ↓
Verified recovery completion
```

Recovery dispositions are informational coordination state, not authorization.

- `already_applied` → do not replace the operation.
- `replacement_required` → construct a replacement-only plan and require separate authorization.
- `manual_review` → do not convert automatically into a mutation.

## Failure identity binding

Recovery reassessment is bound to the exact source operation before a replacement plan can be constructed.

The failure must match:

- source `intent_id`;
- valid source `operation_index`;
- source operation name at that index;
- source operation entity IDs.

This prevents a foreign, mismatched, or forged failure record from changing which portion of a production plan is reassessed.

Focused regression coverage rejects:

```text
foreign intent failure
mismatched operation name
mismatched entity identity
```

## Current focused regression

The latest focused recovery regression passed completely:

```powershell
python -m pytest tests/test_unreal_recovery_sequence.py -vv -s
```

Result:

```text
7 passed in 0.12s
```

The suite covers:

- one read per required state domain during reassessment;
- independent transform/material domain classification;
- replacement of only the mismatched material domain;
- requirement for new replacement authorization;
- rejection of failures from a different intent;
- rejection of mismatched operation names;
- rejection of mismatched entity identities.

## Existing live gates

The Unreal boundary also contains live integration gates for:

- composite production;
- Sequencer production;
- Sequencer recovery reassessment;
- recovery sequence execution;
- heterogeneous Niagara recovery.

These gates must remain permanent regression boundaries and should only be expanded with deterministic, non-invasive failure injection.

## Architecture invariants

- Atlas owns the canonical Digital Twin.
- Atlas authorizes Unreal mutations.
- Unreal executes within the authorized plan.
- Unreal supplies evidence; Atlas independently verifies it.
- Failed mutations require fresh evidence and explicit recovery.
- Recovery never silently retries a failed mutation.
- Replacement mutations require new plan-bound authorization.
- The Named Pipe wire protocol remains unchanged.
- Unreal development remains isolated from Blender development.
- The action/workflow runner is not part of the Unreal development boundary and must not be modified.
- Failure injection belongs only in the disposable validation harness.

## Next development boundary

Resume by preserving the current green recovery boundary first. Then expand live recovery coverage only into domains where deterministic failure injection can be provided safely.

Priority order:

1. preserve heterogeneous recovery;
2. preserve Sequencer production and recovery;
3. preserve exact failure-to-plan identity binding;
4. expand additional live domains conservatively;
5. keep the recovery sequence and authorization boundaries unchanged;
6. keep the Named Pipe protocol unchanged;
7. keep Unreal isolated from Blender and the action/workflow runner.

## End-of-session status — August 24, 2026

The current Unreal recovery milestone is green. Documentation has been updated and implementation work is intentionally stopped at this boundary until the next development session.
