# Atlas Unreal Agent — Current Development Handoff

**Updated:** August 24, 2026 — exact recovery failure binding hardening implemented
**Current focus:** Multi-operation production execution with failure containment, fresh-state recovery, and explicitly authorized replacement mutations
**Current branch:** `feat/unreal-composite-production-operation`

## Current state

The Unreal production boundary now has:

- deterministic composite planning;
- central capability validation;
- full-plan executor preflight before transport;
- semantic write-to-verifier binding;
- production Windows Named Pipe execution;
- independent post-write semantic verification;
- explicit failure reassessment;
- per-operation recovery disposition;
- replacement-only plan construction;
- separate plan-bound replacement authorization;
- an explicit end-to-end recovery coordinator;
- heterogeneous material/Niagara recovery coverage;
- Sequencer playback-range production planning and verification;
- deterministic Sequencer recovery reassessment/replacement coverage;
- a live Unreal Sequencer playback-range gate;
- a live Unreal Sequencer recovery reassessment gate;
- a live Unreal recovery-sequence gate;
- a live Unreal heterogeneous Niagara recovery gate;
- exact recovery-failure identity binding to the source plan operation.

## Composite production sequence

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

## Sequencer production sequence

```text
READ  inspect_sequencer_state
WRITE set_sequencer_playback_range
VERIFY verify_sequencer_playback_range
```

The Sequencer write path is semantically verified against the requested start/end frame range.

## Recovery sequence

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

Recovery reassessment is read-only and never silently retries the failed mutation. `already_applied` operations are not replaced; `replacement_required` operations produce a new plan that requires separate authorization; `manual_review` cannot be converted into an automatic mutation.

## Recovery failure identity hardening — IMPLEMENTED

Recovery reassessment now validates that the reported `UnrealPlanExecutionFailure` is bound to the exact source `UnrealTaskPlan` before any reassessment plan can be constructed.

The binding requires:

- `failure.intent_id` to equal `plan.intent_id`;
- `failure.operation_index` to reference an existing source operation;
- `failure.operation_name` to equal the operation at that exact index;
- `failure.operation_entity_ids` to equal the source operation's entity IDs.

This prevents a mismatched or forged failure record from changing the recovery boundary and causing reassessment of the wrong portion of a production plan.

Focused regression coverage now includes rejection of:

```text
foreign intent failure
mismatched operation name
mismatched entity identity
```

## Sequencer recovery hardening

The focused Sequencer recovery suite passes:

```text
python -m pytest tests/test_unreal_recovery_sequencer.py -vv -s

3 passed
```

It proves that:

- reassessment includes the required Sequencer read;
- a matching fresh playback range is classified as `already_applied`;
- a mismatched playback range produces a replacement-only Sequencer write/verify plan;
- replacement arguments preserve the exact requested frame range.

The live Sequencer recovery reassessment gate passes:

```text
python -m pytest tests/test_unreal_recovery_sequencer_real_integration.py -vv -s

2 passed
```

The live Sequencer production round-trip gate also passes:

```text
python -m pytest tests/test_unreal_sequencer_real_integration.py -vv -s

1 passed
```

## Live heterogeneous recovery gate — PASS

The disposable Unreal harness provides a narrowly scoped deterministic failure condition for the Niagara write operation. It is activated only by the dedicated integration-test authorization:

```text
real-heterogeneous-recovery-failure-auth
```

The harness rejects `apply_niagara_variant` before changing Niagara state when that authorization is presented. Normal Niagara writes use their ordinary authorization identifiers and are unaffected. The existing Named Pipe JSON wire protocol is unchanged.

The live gate passed:

```text
python -m pytest tests/test_unreal_heterogeneous_recovery_real_integration.py -vv -s

1 passed
```

It proves:

```text
live composite failure
       ↓
real fresh reassessment
       ↓
per-domain disposition
       ↓
replacement-only plan
       ↓
new exact authorization
       ↓
live Niagara replacement
       ↓
independent verification
       ↓
restore original state
```

The test also proves that earlier transform and material writes survive the failed Niagara operation and are not unnecessarily replaced.

## Other live gates

The live recovery sequence gate passes:

```text
python -m pytest tests/test_unreal_recovery_sequence_real_integration.py -vv -s
```

The live composite production gate passes:

```text
python -m pytest tests/test_unreal_composite_real_integration.py -vv -s
```

## Current regression gate

Run:

```powershell
python -m pytest tests/test_unreal_recovery_sequence.py tests/test_unreal_recovery_sequencer.py tests/test_unreal_recovery_mixed_domain.py tests/test_unreal_recovery_heterogeneous_domains.py tests/test_unreal_recovery_live_sequence.py tests/test_unreal_recovery_replacement.py tests/test_unreal_failure_reassessment.py tests/test_unreal_plan_executor.py tests/test_unreal_plan_authorization.py tests/test_unreal_recovery_sequence_real_integration.py tests/test_unreal_heterogeneous_recovery_real_integration.py -q
```

Then run the live integration gates independently when Unreal is running:

```powershell
python -m pytest tests/test_unreal_sequencer_real_integration.py -vv -s
python -m pytest tests/test_unreal_recovery_sequencer_real_integration.py -vv -s
python -m pytest tests/test_unreal_recovery_sequence_real_integration.py -vv -s
python -m pytest tests/test_unreal_composite_real_integration.py -vv -s
python -m pytest tests/test_unreal_heterogeneous_recovery_real_integration.py -vv -s
```

## Next development boundary

The real-Unreal heterogeneous recovery boundary is green, the Sequencer production round-trip is green, Sequencer recovery is covered deterministically plus by a live reassessment gate, and recovery failure identity is now bound to the exact source operation.

Priorities:

1. Preserve the live heterogeneous recovery test as a permanent regression boundary.
2. Preserve the live Sequencer production and recovery gates as permanent regression boundaries.
3. Preserve exact failure-to-plan identity binding in every recovery entry point.
4. Expand live recovery coverage to additional supported domains only when the harness can provide deterministic, non-invasive failure injection.
5. Preserve the exact recovery sequence: fresh reassessment → disposition → replacement-only plan → separate authorization → live replacement → independent verification.
6. Keep failure injection narrowly scoped to the disposable validation harness and isolated from ordinary production authorization paths.
7. Keep the Named Pipe wire protocol unchanged.
8. Keep Unreal development isolated from Blender and the action/workflow runner.

## Architectural invariants

- Atlas owns the Twin.
- Unreal Agent reasons/plans.
- Atlas authorizes.
- Unreal adapter executes.
- Unreal provides evidence.
- Atlas verifies semantic state independently.
- Verification evidence is marked verified only after independent proof.
- Failures require fresh evidence and explicit recovery.
- Recovery reassessment is read-only and never an implicit retry.
- Recovery disposition is informational/coordination state, not authorization.
- Replacement mutations require explicit plan-bound authorization.
- The Unreal Agent must never become a second autonomous authority separate from Atlas.
- Do not weaken fail-closed validation.
- Preserve stateless Unreal adapter behavior.
- Preserve independent evidence verification.
- Do not change the existing Named Pipe wire protocol.
- Keep Unreal and Blender development isolated.
- Do not modify the action/workflow runner.
