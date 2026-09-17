# Unreal Agent - Shot-Level Production Continuity Closeout

**Date:** September 16/17, 2026
**Branch:** `reconcile/unreal-autonomy-origin-20c6d10` (local)
**Pre-continuity baseline:** `86467ac` (shot continuity design gate, 8 passed)
**Design input:** `docs/UNREAL_SHOT_CONTINUITY_DESIGN_REVIEW.md` (CLEAR WITH MINOR FINDINGS)
**Architecture decision applied:** keep Atlas frame semantics inclusive, fix the Unreal boundary mapping

## STATUS

```
LIVE CLEAR  - implementation, deterministic gate, and live UE 5.6.1 gate all pass
BRANCH PUBLICATION BLOCKED - remote branch diverged (parallel implementation of the same milestone)
```

## Commits (local)

| Commit | Change |
| --- | --- |
| `534af75` | bind shot continuity to the authorized production intent |
| `aa07d5d` | enforce shot continuity at the production render boundary |
| `e1dcb79` | translate the authorized inclusive frame range into the MRQ boundary |
| `d1f6915` | record the continuity contract, boundary translation, and live gate (docs) |
| `d6c4566` | read fixture variants through the frozen evidence contract (test fixture fix) |

Docs: `docs/UNREAL_SHOT_CONTINUITY_IMPLEMENTATION.md`, `DEVELOPMENT_LOG.md` milestone entry.

## Frozen invariants -> implementation

1. Sequence asset path exact and authorization-bound: `UnrealProductionSpec.sequence_asset_path`
   -> `UnrealProductionPlan.continuity` -> `UnrealPlanAuthorization.continuity_digest` ->
   submitted by `UnrealProductionWorkflow.run()`, which rejects a differing declared path.
2. Sequencer and render ranges identical: enforced structurally at plan construction
   (`_validate_plan_continuity`).
3. Final evidence reports the authorized sequence path: verified from fresh evidence.
4. Final evidence reports the effective frame range: `FRenderJobState` captures the effective
   MRQ range at submission and `inspect_render_job` returns the Atlas semantic inclusive
   `start_frame`/`end_frame` plus `end_frame_exclusive`.
5. Final evidence reports output directory and format: compared after the shared canonicalization.
6. PNG frame-count coverage: `unique output files == end_frame - start_frame + 1`, PNG only.
7. Job ID exact and authorization-bound: unchanged, re-verified in the live gates.
8. Fresh evidence only: no echoed write argument is compared; missing fields fail closed.
9. Recovery fail-closed and explicit: unchanged; production failure blocks submission and no
   mutation is retried.
10. No new transport operation, no second authority, no entity cache, no workflow engine.

## Boundary translation (the one architectural correction)

Measured live before the fix: authorized inclusive `1-2` -> 1 artifact; `1-5` -> 4 artifacts.
The MRQ effective range is half-open. After the fix (`CustomStartFrame = Atlas start`,
`CustomEndFrame = Atlas end + 1`):

```
authorized 1-2 -> MRQ [1,3) -> 2 artifacts
authorized 1-5 -> MRQ [1,6) -> 5 artifacts
```

The translation rule is owned by the language-agnostic contract
(`UnrealShotContinuity.end_frame_exclusive`) and the verifier requires the engine's reported
boundary to correspond to the authorized inclusive range.

## Evidence ledger

### Deterministic

| Suite | Result |
| --- | --- |
| `tests/test_unreal_shot_continuity.py` | 43 passed, 1 skipped |
| `tests/test_unreal_shot_continuity_design_gate.py` | 8 passed |
| Consolidated affected Unreal regression (36 modules: continuity, gates, planning boundary, operation, render workflow, render-job verification, receipts, authorization, recovery, controller/host, capability) | 295 passed, 1 skipped |
| Continuity-area selection (25 modules) | 242 passed, 1 skipped |
| Canonical controller/host suite | 160 passed, 2 deselected |
| Blast-radius sweep (180 files, `-m "not integration"`) | 1067 passed, 6 skipped |

The two skips are the single-frame case in the incomplete-coverage matrix and one pre-existing
environment skip.

### Live UE 5.6.1 (each in a fresh editor session)

| Gate | Command | Result |
| --- | --- | --- |
| Production workflow | `tests/test_unreal_production_workflow_real_integration.py` | 1 passed in 9.78 s |
| Controller production path | `tests/test_agent_controller_production_real_integration.py` | 1 passed in 10.47 s |
| Final continuity run | `tests/test_unreal_shot_continuity_real_integration.py` | 1 passed in 9.95 s |
| Full-range continuity diagnostic | authorized `1-5` | evidence `1 5`, identity continuity PASS, 5 artifacts `AtlasRender_0001..0005`, receipt matches evidence and persisted |

Live outcome detail (final continuity run): sequence asset path
`/Game/AtlasTest/AtlasSequencerFixtureSequence`, effective frames `1 2`, output directory
`.../Saved/AtlasShotContinuityOutput`, output format `png`, exact job id, `unique png files: 2`,
receipt digest produced, receipt persisted and equal to the in-memory receipt.

### Fixture state

All four tracked Unreal fixtures are byte-identical to their committed baseline after every live
run:

```
34be88da...  AtlasRenderConfig.uasset
48d14bd9...  AtlasSequencerFixtureSequence.uasset
db15ec03...  BP_AtlasTest.uasset
e25394d2...  Generated/AtlasRenderFixture.umap
```

Editor sessions stopped, the Named Pipe released, probe output directories removed.

## Test-fix classification

| Fix | Classification | Evidence |
| --- | --- | --- |
| `_variant` reader in `tests/test_unreal_production_workflow_real_integration.py` now accepts `Mapping` | test fixture mismatch | reproduced identically at baseline `86467ac` in a clean worktree (`material.variant missing from Unreal evidence`) |
| New determinism fixtures for the frame-count and boundary matrices | contract gap (new invariant coverage) | the design gate only modelled the count formula; the boundary rule did not exist before this milestone |
| Fixtures updated to declare the production sequence identity | test fixture mismatch | production contract now requires it; production code was not weakened |

## Known residual defects (reported, not fixed tonight)

1. **MRQ queue attribution.** A submission renders every job already present in the Movie Render
   Pipeline queue, and the new executor's per-job callback attributes each queue job's artifacts
   to the newly submitted job. Measured: rerunning a live gate without a fresh editor session
   reported `observed unique_output_files=24` for an authorized `1-2` job - the 24 artifacts of the
   previous job. Live gates must therefore start from a fresh editor session. Recommended
   follow-up (needs an architecture decision, submission semantics change): clear or delete
   completed queue jobs per submission, or key output collection to the executor job identity.
2. **PNG-only completeness**, by design.
3. **Sibling Mapping readers.** `tests/test_unreal_composite_real_integration.py`,
   `tests/test_unreal_heterogeneous_recovery_real_integration.py` and
   `tests/test_unreal_material_variant_real_integration.py` share the same `dict`-vs-`Mapping`
   evidence-reader defect. They were not modified (their gates were not run tonight) and will fail
   live the same way until fixed.
4. `unreal_render_workflow._job_state` still resolves the render-job envelope with its own rule
   rather than the shared `resolve_render_job_state` helper (identical semantics, different
   messages).

## Branch publication

`git push origin HEAD:reconcile/unreal-autonomy-origin-20c6d10` was **rejected**:
the remote branch is 8 commits ahead of the merge base `86467ac` with a parallel implementation of
this same milestone - including a new `planning/unreal_shot_continuity.py`, a new
`planning/unreal_render_continuity.py`, and **extended render-receipt fields**
(`planning/unreal_render_receipt.py`, `unreal_render_receipt_store.py`) that this milestone
deliberately did not add.

Overlapping files (both sides edited, i.e. conflict surface):
`planning/unreal_production_workflow.py`, `planning/unreal_render_job_verifier.py`,
`planning/unreal_render_workflow.py`, `planning/unreal_shot_continuity.py` (add/add).

Only the local side carries: the effective-frame-range transport extension, the
inclusive-to-half-open boundary translation, the C++ evidence fields, and the live continuity
gate. Only the remote side carries: the extended receipt structure.

No merge, rebase, or force push was performed. Publication requires an explicit reconciliation
decision (which continuity contract wins, and whether the receipt structure changes).
