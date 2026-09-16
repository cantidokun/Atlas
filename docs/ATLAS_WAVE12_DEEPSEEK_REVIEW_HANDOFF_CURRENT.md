# Wave 12 — DeepSeek Review Current-Head Addendum

**Date:** September 16, 2026
**Repository:** `cantidokun/Atlas`
**Branch:** `feat/blender-wave12-reference-integrity`
**PR:** #102 — Wave 12 — bounded parent-cycle repair
**Wave 11 main baseline:** `fda85a994ec0669d8ee9d1ff1ab6d52e9bfec0d3`
**Code-remediation baseline:** `7b8947e152bb14566de7b1ebf5fa0c945ec373ed`

## First independent red-team findings and remediation

The first DeepSeek review of the pre-remediation implementation identified two material findings: extractor-reported source digests were trusted without independent scene recomputation, and the global `_cycle_signatures()` implementation performed avoidable repeated indexing/walking.

Those findings were remediated before the current code-remediation baseline. The executor independently recomputes the source digest from the extracted authoritative scene, requires:

`extractor_report_digest == computed_scene_digest == plan.source_report_digest`

and independently recomputes and validates the post-mutation output digest. Global cycle inventory is now a single indexed functional-graph traversal with linear complexity.

## Second independent red-team result

Hermes performed an independent adversarial review of exact HEAD `900754d01a89d7f4f40818d030099dbcdbb95430` and independently verified that the digest-provenance and cycle-complexity findings were genuinely closed.

The review exercised digest attacks, authorization variants, replay/stale-plan vectors, malformed structures, hostile Mapping inputs, randomized functional graphs, target-position sweeps, postcondition corruption, mutation-boundary injections, and Python 3.9/3.11 compatibility.

It found no path to wrong-scene, wrong-target, wrong-parent, or unauthorized-edge mutation.

## D1 / D2 boundary remediation

The second review identified two fail-closed boundary defects:

- **D1:** public planner/traversal calls could leak raw exceptions for malformed Mapping/object field access.
- **D2:** hostile custom `Mapping` objects could raise through plan/params/authorization accessors before mutation.

D2 was closed in the executor boundary. D1 was substantially closed by hardening the indexing pass, but a final red-team probe found one residual stateful-accessor case where a parent field succeeded during indexing and raised on a later planner read.

That residual defect was closed in the code-remediation baseline by containing the complete public planner path and the public cycle-query path. The implementation now converts unexpected planner/traversal exceptions into declared `ParentCycleError` / `SCENE_VALIDATION_FAILED` outcomes while preserving existing intentional failure codes.

## Current Wave 12 implementation

`planning/blender/parent_cycle.py` now:

- validates scene object containers and object/parent identifier types at the indexing boundary;
- contains the complete public planner/traversal boundary so stateful field-access failures cannot escape as raw exceptions;
- contains hostile plan and authorization Mapping access failures;
- independently computes and validates source and output scene digests;
- exposes the canonical `scene_report_digest(scene_model)` contract for adapters;
- retains exact closed authorization and correction/plan identity recomputation;
- performs exactly one externally-reaching mutator call with `new_parent_object_id=None`;
- detects post-mutation scope violations without adding rollback authority;
- retains linear global cycle-signature traversal and existing postcondition/preservation checks.

## Contract qualification

Wave 12 deliberately has no rollback authority. The executor guarantees that its own code performs only the selected single-edge mutator call. A trusted/injected adapter mutator that performs additional changes cannot be undone by Wave 12; those changes are detected by fresh post-mutation extraction and cause a non-success result. Consumers must not interpret `POSTCONDITION_FAILED` as proof that the scene remained unchanged.

The canonical digest contract is explicitly documented: adapters must provide the exact `scene_report_digest(scene_model)` value as the extractor report digest, and the executor independently recomputes the same digest before and after mutation.

## Regression hardening

Coverage includes:

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
- stateful parent-accessor failure after initial indexing;
- linear cycle-inventory regression;
- public canonical digest availability.

## Verified validation evidence

The exact code-remediation baseline passed the focused Wave 12 regression added for the residual C1 case. The temporary patch runner verified the focused planner/cycle-query hardening and then removed itself from the branch.

The earlier exact-head GitHub Actions run on `36470610712f0dc8a31ea0452e44797e37562969` was green on Python 3.9 and 3.11, with Python 3.11 also passing the M13.7 repository benchmark. The final full-suite CI must be re-run on the post-C1-remediation head.

The live Blender 4.4.3 boundary evidence remains qualified exactly as intended: it proves the real detach primitive and world-pose preservation on an acyclic disposable relationship, not repair of a genuinely cyclic Blender scene. Measured matrix delta remains `1.1920928955078125e-07` against a `1e-6` acceptance threshold.

No temporary Wave 12 diagnostic or patch workflow remains on the branch after remediation.

## Final validation gate

Before PR #102 is considered ready for human merge review:

1. confirm Python 3.9 and 3.11 CI is green on the final documentation/code head;
2. confirm M13.7 passes on Python 3.11;
3. rerun the live Blender 4.4.3 boundary gate on the final head;
4. perform one final independent red-team review of the exact final head;
5. reconcile every finding before changing the PR out of draft.

Do not weaken the contract or tests to satisfy a reviewer. Workflow/action-runner tests remain excluded unless explicitly authorized.
