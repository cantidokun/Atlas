# Wave 12 — DeepSeek Review Current-Head Addendum

**Date:** September 16, 2026
**Repository:** `cantidokun/Atlas`
**Branch:** `feat/blender-wave12-reference-integrity`
**PR:** #102 — Wave 12 — bounded parent-cycle repair
**Current HEAD:** `3832dec191ff6737fc07699e8f183a212d43ddab`
**Wave 11 main baseline:** `fda85a994ec0669d8ee9d1ff1ab6d52e9bfec0d3`

## First independent red-team findings and remediation

The first DeepSeek review of the pre-remediation implementation identified two material findings: extractor-reported source digests were trusted without independent scene recomputation, and the global `_cycle_signatures()` implementation performed avoidable repeated indexing/walking.

Those findings were remediated before this current head. The executor now independently recomputes the source digest from the extracted authoritative scene, requires:

`extractor_report_digest == computed_scene_digest == plan.source_report_digest`

and independently recomputes and validates the post-mutation output digest. Global cycle inventory is now a single indexed functional-graph traversal with linear complexity.

## Second independent red-team result

Hermes performed a fresh adversarial review of exact HEAD `900754d01a89d7f4f40818d030099dbcdbb95430` without modifying the repository. It independently verified the previous digest-provenance and complexity findings as fixed.

The second review exercised 13 digest attacks, 22 authorization variants, 6 replay/stale-plan vectors, malformed structures, hostile Mapping inputs, 30,000 random functional graphs plus structured cycle topologies, and large-chain performance. It found no path to wrong-scene, wrong-target, wrong-parent, or unauthorized-edge mutation.

Two pre-remediation boundary defects were identified:

- **D1:** public planner/traversal calls could leak `TypeError` for malformed Mapping scenes such as unhashable object IDs, non-iterable object containers, or unhashable parent identifiers instead of returning declared failure codes.
- **D2:** hostile custom `Mapping` objects could raise through plan/params/authorization accessors before mutation instead of being converted into declared failure outcomes.

These were fixed on the current branch without changing Wave 12 authorization, provenance, cycle semantics, or mutation authority.

## Current remediation

`planning/blender/parent_cycle.py` now:

- validates scene object containers and object/parent identifier types at the indexing boundary;
- converts malformed planner inputs into declared `ParentCycleError` codes;
- contains hostile plan and authorization Mapping access failures;
- independently computes and validates source and output scene digests;
- exposes the canonical `scene_report_digest(scene_model)` contract for adapters;
- retains exact closed authorization and correction/plan identity recomputation;
- performs exactly one externally-reaching mutator call with `new_parent_object_id=None`;
- detects post-mutation scope violations without adding rollback authority;
- retains linear global cycle-signature traversal and existing postcondition/preservation checks.

## Contract qualification

Wave 12 deliberately has no rollback authority. The executor guarantees that its own code performs only the selected single-edge mutator call. A trusted/injected adapter mutator that performs additional changes cannot be undone by Wave 12; those changes are detected by fresh post-mutation extraction and cause a non-success result. Consumers must not interpret `POSTCONDITION_FAILED` as proof that the scene remained unchanged.

The canonical digest contract is now explicitly documented: adapters must provide the exact `scene_report_digest(scene_model)` value as the extractor report digest, and the executor independently recomputes the same digest before and after mutation.

## Regression hardening

Coverage now includes:

- stale/echoed source-digest attacks;
- malformed and non-lowercase digest rejection;
- authorization field closure and substitutions;
- stale-plan replay rejection;
- self/two-node/multi-node cycle behavior and tail discrimination;
- unrelated-cycle and second-cycle preservation;
- one-edge-only and non-target preservation checks with deep-copy snapshots;
- malformed pre/post-mutation scene containment;
- hostile plan/authorization Mapping containment;
- malformed object IDs, parent IDs, and scene containers;
- linear cycle-inventory regression;
- public canonical digest availability.

## Verified validation evidence

The immediately preceding remediation CI run for `900754d...` was green on both supported Python legs, with Python 3.11 also passing the M13.7 repository benchmark. The second independent review reproduced the relevant Python 3.9/3.11 regression counts and live Blender evidence at that reviewed head.

The live Blender 4.4.3 boundary evidence remains qualified exactly as intended: it proves the real detach primitive and world-pose preservation on an acyclic disposable relationship, not repair of a genuinely cyclic Blender scene. Measured matrix delta remains `1.1920928955078125e-07` against a `1e-6` acceptance threshold.

The temporary diagnostic workflow used for earlier evidence capture was removed and is absent from the current branch.

## Final validation gate

Current head `3832dec...` must complete the normal GitHub Actions regression after the boundary hardening. After that:

1. confirm Python 3.9 and 3.11 CI is green on the exact current head;
2. confirm M13.7 passes on Python 3.11;
3. rerun the live Blender 4.4.3 boundary gate on the current head;
4. perform one final independent red-team review of the exact current head;
5. reconcile any findings before PR #102 is considered ready for human merge review.

Do not weaken the contract or tests to satisfy a reviewer. Workflow/action-runner tests remain excluded unless explicitly authorized.
