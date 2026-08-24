# Atlas Development Handoff — Unreal Production Boundary

**Updated:** August 24, 2026 — end-of-session handoff
**Branch:** `feat/unreal-composite-production-operation`
**Current verified HEAD before documentation update:** `dfd253a`

## Session result

The Unreal production/recovery boundary is green for the current milestone.

The branch was fast-forwarded from `43383ec` to `dfd253a` and added:

- hardened Unreal recovery-sequence planning;
- focused regression coverage for recovery reassessment and replacement;
- exact failure-to-plan identity binding;
- rejection of foreign intent failures;
- rejection of mismatched operation names;
- rejection of mismatched entity identities.

Focused regression run completed locally:

```text
python -m pytest tests/test_unreal_recovery_sequence.py -vv -s

7 passed in 0.12s
```

## Verified recovery boundary

The recovery architecture now follows:

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

Recovery never silently retries the failed mutation.

`already_applied` operations are not replaced.

`replacement_required` operations generate a new replacement-only plan and require separate authorization.

`manual_review` remains non-automatic.

## Failure identity binding

Before recovery reassessment can construct a replacement plan, the failure must be bound to the exact source plan operation.

The binding requires:

- `failure.intent_id == plan.intent_id`;
- `failure.operation_index` to identify an existing source operation;
- `failure.operation_name` to match the operation at that index;
- `failure.operation_entity_ids` to match the source operation entity IDs.

This prevents an unrelated or forged failure record from changing the recovery boundary.

Focused regression coverage proves rejection of:

```text
foreign intent failure
mismatched operation name
mismatched entity identity
```

## Existing Unreal production boundary

The Unreal Agent currently has verified coverage for:

- deterministic composite planning;
- capability validation;
- full-plan executor preflight;
- semantic write-to-verifier binding;
- Windows Named Pipe execution;
- independent post-write semantic verification;
- explicit failure reassessment;
- per-operation recovery disposition;
- replacement-only plan construction;
- plan-bound replacement authorization;
- recovery coordination;
- heterogeneous material/Niagara recovery;
- Sequencer playback-range production planning and verification;
- deterministic Sequencer recovery reassessment/replacement;
- live Sequencer production and recovery gates;
- live heterogeneous Niagara recovery;
- exact source-operation failure identity binding.

## Architectural invariants

- Atlas owns the canonical Digital Twin.
- Unreal Agent reasons and plans within the authorized boundary.
- Atlas authorizes mutations.
- The Unreal adapter executes.
- Unreal provides evidence.
- Atlas independently verifies semantic state.
- Verification evidence is only trusted after independent proof.
- Failures require fresh evidence and explicit recovery.
- Recovery reassessment is read-only.
- Recovery disposition is not authorization.
- Replacement mutations require explicit plan-bound authorization.
- The Unreal Agent is never a second autonomous authority separate from Atlas.
- Validation remains fail-closed.
- The Unreal adapter remains stateless.
- The existing Named Pipe wire protocol must remain unchanged.
- Unreal and Blender development remain isolated.
- The action/workflow runner must not be modified.

## Next session

Resume from the current branch and preserve the green recovery boundary.

Priority order:

1. Preserve the live heterogeneous recovery gate.
2. Preserve the live Sequencer production and recovery gates.
3. Preserve exact failure-to-plan identity binding at every recovery entry point.
4. Expand live recovery only where deterministic, non-invasive failure injection is available.
5. Preserve the exact recovery sequence: fresh reassessment → disposition → replacement-only plan → separate authorization → live replacement → independent verification.
6. Keep failure injection isolated to the disposable validation harness.
7. Keep the Named Pipe protocol unchanged.
8. Keep Unreal development isolated from Blender and the action/workflow runner.

## Stop point

No further Unreal implementation work is required for this session. The repository documentation has been updated to record the current verified state, and development should resume from this handoff rather than reopening already-validated recovery behavior.
