# Atlas Wave 12 — DeepSeek Independent Review Handoff

**Checkpoint:** September 16, 2026 end-of-night
**Repository:** `cantidokun/Atlas`
**Branch:** `feat/blender-wave12-reference-integrity`
**PR:** #102 — Wave 12 — bounded parent-cycle repair
**Current reviewed HEAD:** `a2bfdb19071594669f93cb6b81c448b36caf9600`
**Base:** `main` at `fda85a994ec0669d8ee9d1ff1ab6d52e9bfec0d3`

## Purpose

This document is the authoritative handoff for the planned independent DeepSeek review of Wave 12. DeepSeek is being used as an **adversarial reviewer**, not as an Atlas execution or authorization authority.

The objective is to determine whether the final Wave 12 implementation satisfies its existing contract without silently broadening scope. The review must be independent of the implementation author and must inspect the current HEAD, not an earlier Wave 12 checkpoint.

## Current status

Wave 12 implementation and deterministic/live validation are complete. The PR remains **draft** because the independent-review gate has not yet been satisfied.

Verified gates:

- deterministic Wave 12 cycle/reference tests: PASS;
- adversarial fail-closed tests: PASS;
- combined topology + live Blender gate: PASS;
- full Wave 1–Wave 12 regression: PASS;
- real Blender 4.4.3 disposable boundary gate: PASS;
- final-head GitHub Actions run #1904: PASS on Python 3.9 and 3.11, with M13.7 passing on 3.11.

The live Blender gate used a disposable in-memory scene. It verified parent detachment, world-matrix preservation within measured float32 round-off, object/mesh identity preservation, object-set preservation, no frozen asset opened, and no save attempt.

## Files DeepSeek should inspect

Primary implementation and contract:

- `planning/blender/parent_cycle.py`
- `planning/blender/BLENDER_WAVE12_PARENT_CYCLE_REPAIR_DESIGN.md`
- `planning/blender/BLENDER_WAVE12_REFERENCE_INTEGRITY_CHECKPOINT.md`
- `planning/blender/README.md`

Wave 12 deterministic/adversarial validation:

- `tests/test_blender_wave12_parent_cycle.py`
- `tests/test_blender_wave12_cycle_topology_adversarial.py`
- `tests/test_blender_wave12_executor_fail_closed.py`
- `tests/test_blender_wave12_objectmodel_preservation.py`
- `tests/test_blender_wave12_scene_preservation.py`

Real Blender boundary:

- `tests/parent_cycle_live_script.py`
- `tests/test_live_blender_wave12_parent_cycle_gate.py`

The review may inspect the complete PR #102 diff and surrounding Wave 4 hierarchy code when necessary to establish compatibility and non-regression.

## Exact semantic boundary to audit

Wave 12 adds exactly one correction type:

`REPAIR_PARENT_CYCLE`

The permitted semantic mutation is exactly one selected parent edge:

```text
target_object_id = explicitly authorized target
expected_parent_id = exact current parent
new_parent_object_id = None
```

The implementation must not:

- infer a replacement parent;
- re-parent another object;
- normalize or reorder hierarchy;
- repair dangling parents (Wave 4 owns that case);
- mutate geometry, names, collections, units, mesh topology, or unrelated object state;
- delete objects;
- persist/save Blender state;
- add retry, rollback, recovery, receipt, workflow, or action-runner authority.

## Planner invariants

The planner must derive cycle membership from authoritative scene input. Caller-supplied cycle membership is not authoritative.

A plan must fail closed for:

- missing or invalid target;
- duplicate object identity;
- missing parent;
- expected-parent mismatch;
- dangling expected parent;
- no current target cycle;
- target not actually belonging to the detected cycle;
- unexpected parameters.

A non-cycle tail that eventually points into a cycle must not be classified as a cycle member.

## Authorization invariants

Authorization is closed over the exact fields:

- decision;
- correction type;
- correction id;
- plan id;
- source report digest;
- target object id;
- expected parent id.

The executor must independently validate the plan identifiers and authorization relationship and must recompute the fresh source digest before mutation.

The following substitutions must fail closed before the mutator is reached:

- stale source digest;
- target substitution;
- expected-parent substitution;
- correction-id substitution;
- plan-id substitution;
- correction-type substitution;
- unauthorized decision;
- unexpected authorization fields.

## Mutation and postcondition invariants

The mutator invocation must remain exactly:

```python
mutator(target_object_id, expected_parent_id, None)
```

The executor must prove after mutation that:

- the target parent is `None`;
- target local `location`, `rotation`, and `scale` are unchanged;
- every non-target object is unchanged;
- object identity/count are unchanged;
- scene-level state is unchanged;
- the selected cycle is gone;
- no new cycle exists elsewhere;
- output digest is valid;
- extraction/mutation/postcondition failures are contained fail-closed.

Preservation snapshots must be deep-copied so aliasing cannot create false passes.

A malformed canonical cyclic graph has no well-defined world pose under the existing parent-chain engine. Therefore the canonical executor must **not** fabricate or claim pre-cycle world-pose preservation. World-pose preservation is instead proven at the real Blender boundary on a valid acyclic disposable relationship.

## Live Blender boundary

The live gate is intentionally narrower than canonical cycle repair because Blender's live object model does not provide a trustworthy illegal cyclic state for this proof.

The gate must remain:

- disposable/in-memory;
- non-persistent;
- no frozen `.blend` opened;
- no `.blend` saved;
- real Blender 4.4.3;
- actual parent-detach primitive;
- world-matrix preservation checked with tolerance appropriate to Blender float32 round-off;
- object and mesh identity preserved.

The final measured matrix delta was `1.1920928955078125e-07`; the gate accepts `<= 1e-6`.

## Known review history

Two design-level findings were incorporated during development:

1. World-pose preservation needed an explicit boundary requirement because parent detachment can otherwise alter world pose.
2. A canonical malformed parent cycle has no defined world pose, so the world-pose requirement was correctly isolated to the acyclic Blender primitive; canonical correctness remains graph/reference based.

Additional hardening included deep-copy preservation snapshots, cycle-tail discrimination, adversarial second-cycle detection, and robust parsing of the live-gate JSON payload.

The GitHub review submissions containing those findings were authored by `cantidokun`. They are valuable development evidence but **do not constitute the independent review required by the merge gate**.

## DeepSeek review questions

DeepSeek should answer each question with concrete evidence from the current HEAD:

1. Is the semantic mutation strictly one parent-edge detach?
2. Is every mutation target/parent pair cryptographically and structurally bound to the authorized plan?
3. Can stale source state, target substitution, or parent substitution reach the mutator?
4. Can caller-supplied cycle claims influence authoritative cycle determination?
5. Can a tail leading into a cycle be misclassified as a cycle member?
6. Can a self-cycle, two-node cycle, or longer cycle be incorrectly detected or repaired?
7. Can the executor accidentally remove more than one edge?
8. Can an unrelated pre-existing cycle be altered or rejected incorrectly?
9. Can a mutation that creates a second cycle escape postcondition detection?
10. Are preservation checks immune to object aliasing?
11. Are malformed scene/extractor/mutator failures contained fail-closed?
12. Are plan IDs, correction IDs, source digests, and authorization fields independently recomputed/validated?
13. Does any path introduce persistence, retry, rollback, recovery, receipt, workflow, or action-runner authority?
14. Does the implementation match the Wave 12 design document exactly where the design is normative?
15. Are the live Blender claims appropriately limited to what Blender 4.4.3 actually proves?
16. Is there any concrete production-code defect that blocks merge?
17. Are there any test gaps that are material enough to require another implementation change?

## Review output format requested

Return:

```text
DEEPSEEK_WAVE12_REVIEW
HEAD: a2bfdb19071594669f93cb6b81c448b36caf9600

STATUS: CLEAR | BLOCKED | CONDITIONAL

BLOCKERS:
- <concrete blocker, or NONE>

HIGH_RISK_FINDINGS:
- <finding, or NONE>

MEDIUM_RISK_FINDINGS:
- <finding, or NONE>

LOW_RISK_FINDINGS:
- <finding, or NONE>

CONTRACT_COVERAGE:
- one-edge mutation: PASS/FAIL
- authorization binding: PASS/FAIL
- stale-state rejection: PASS/FAIL
- cycle detection: PASS/FAIL
- tail discrimination: PASS/FAIL
- postcondition containment: PASS/FAIL
- preservation integrity: PASS/FAIL
- scope containment: PASS/FAIL
- live-boundary claims: PASS/FAIL

RECOMMENDED_ACTION:
- <specific next action>
```

Do not provide a numerical score or overall ranking. The purpose is adversarial defect discovery and contract verification.

## Merge discipline after review

Do not mark PR #102 ready merely because DeepSeek says `CLEAR`. Reconcile every finding against the source code, tests, and design contract first.

If DeepSeek identifies a concrete blocker, reproduce it deterministically where possible before modifying production code.

If DeepSeek is clear and all existing gates remain green, the remaining action is the human merge decision. Do not weaken the contract or tests to accommodate the reviewer.

Workflow/action-runner tests remain excluded unless explicitly authorized.

## Resume command

```powershell
git checkout feat/blender-wave12-reference-integrity
git pull origin feat/blender-wave12-reference-integrity
git rev-parse HEAD
```

Expected HEAD for the review packet at this checkpoint:

```text
a2bfdb19071594669f93cb6b81c448b36caf9600
```
