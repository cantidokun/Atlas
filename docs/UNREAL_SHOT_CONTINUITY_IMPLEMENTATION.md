# Unreal Agent - Shot-Level Production Continuity Implementation

**Date:** September 16, 2026
**Branch:** `reconcile/unreal-autonomy-origin-20c6d10`
**Design input:** `docs/UNREAL_SHOT_CONTINUITY_DESIGN_REVIEW.md` (CLEAR WITH MINOR FINDINGS)
**Implementation commits:** `534af75` (contract + authorization binding), `aa07d5d` (boundary enforcement + deterministic gate)

## What this slice implements

The frozen continuity invariants are now expressed once, at the production
level, and verified against fresh engine evidence:

| Requirement | Implementation |
| --- | --- |
| 1. Sequence asset continuity | `UnrealProductionSpec.sequence_asset_path` -> `UnrealProductionPlan.continuity` -> bound by the existing `UnrealPlanAuthorization` receipt; `UnrealProductionWorkflow.run()` submits the authorized value and rejects a declared path that differs |
| 2. Effective render frame range in job evidence | `FRenderJobState` gains the effective frame range, captured from the job's effective MRQ configuration at submission and returned by `inspect_render_job` as the Atlas semantic inclusive `start_frame`/`end_frame` plus the raw `end_frame_exclusive` boundary |
| 3. Final continuity verification | `planning/unreal_shot_continuity.py::verify_shot_continuity_identity` compares authorized sequence path, effective frame range, output directory, output format, and the inclusive-to-half-open boundary against fresh job evidence at the verification boundary |
| 4. PNG artifact completeness | `verify_shot_continuity_completeness` additionally requires `unique(output_files) == end_frame - start_frame + 1` for the PNG image-sequence boundary only |
| 5. Receipt / result continuity | `UnrealRenderReceipt` is unchanged (`job_id`, `sequence_asset_path`, `evidence_digest` + derived `receipt_digest`) and is issued only from continuity-verified evidence |
| 6. Failure / recovery | Unchanged: production failure blocks submission, no mutation is retried, and coverage/replacement plans require their own separate authorizations |

## Contract decisions

### The continuity record is declared once and checked against the plan

`UnrealProductionPlan.__post_init__` requires its `continuity` to agree with the
plan's own `configure_render` and `set_sequencer_playback_range` operations.
A plan whose declared continuity disagrees with its operations cannot be
constructed, so the authorized frame range, output directory, and output format
keep a single declarative source and the existing Sequencer/render range
identity rule is structural rather than reviewed.

### Authorization binding without a second authority

The sequence asset path cannot be carried inside an operation argument: every
Unreal operation argument set is pinned by the capability registry, and adding
an argument would change the Named Pipe request schema. The existing
`UnrealPlanAuthorization` receipt was therefore extended with an optional
`continuity_digest`:

* `matches(plan)` keeps its current meaning and digest, so plan-only receipts,
  recovery receipts, and the raw plan executor are unchanged.
* `matches(plan, continuity_digest=...)` additionally requires the receipt to
  bind that exact continuity, and fails closed when it does not.
* `authorize_production_plan` is the production issuer and always binds the
  continuity; `UnrealProductionWorkflow.run()` always requires the binding.

This is an extension of the single existing authorization authority, not a
second one. It is strictly stronger than the previous state: a plan-only
receipt can no longer authorize a shot submission at all.

### No echoed write arguments

Every value compared at the final boundary is read from fresh
`inspect_render_job` evidence. Missing fields fail closed: evidence that does
not expose an effective `start_frame`/`end_frame` is rejected rather than
treated as agreement.

### Output directory comparison

`canonicalize_output_directory` was promoted from a nested function inside
`verify_render_config` to one module-level rule in `planning/unreal_render_contract.py`
(behaviour unchanged), so render-state verification and job-evidence
verification reduce Atlas-relative and Unreal-absolute directories to the same
canonical form.

### Receipt structure

The receipt was left unchanged deliberately. The design review's requirement is
that continuity comes from fresh evidence at the verification boundary; the
receipt is an evidence-bound identity artifact, not a second verification
authority. Adding range/format fields to the receipt would duplicate state that
the evidence digest already covers.

### Frame-range boundary translation (inclusive Atlas -> half-open engine)

Atlas frame ranges are inclusive: an authorized range of `1-24` means 24 frames.
The first live gate proved that the Movie Render Pipeline effective range is
half-open `[start, end_exclusive)`, so the same configuration rendered one frame
fewer than authorized (`1-2` produced a single artifact, `1-5` produced four).

The architecture decision is to keep Atlas semantics inclusive and translate at
the Unreal boundary:

```
Atlas start_frame .. end_frame (inclusive)
        |  boundary translation
        v
MRQ CustomStartFrame = Atlas start_frame
MRQ CustomEndFrame   = Atlas end_frame + 1
```

- `configure_render` performs the translation when it writes the MRQ
  configuration.
- `inspect_render_state` and `inspect_render_job` convert back, so the Atlas
  semantic `start_frame`/`end_frame` pair keeps its existing inclusive meaning
  and the raw engine boundary stays observable as `end_frame_exclusive`.
- `UnrealShotContinuity.end_frame_exclusive` owns the translation rule in the
  language-agnostic contract, and the verifier requires the engine's reported
  boundary to correspond to the authorized inclusive range.
- `SubmitRender` fails closed when the effective configuration has no explicit
  custom playback range: "effective frame range" would otherwise have to be
  reported as `0-0`, a fiction the continuity check could not distinguish from a
  real authorized range.

The sequencer playback-range read/write pair was deliberately left unchanged: it
is self-consistent, and the live runs showed the MRQ custom range governs the
rendered frame set.

## Live UE 5.6.1 gate

`tests/test_unreal_shot_continuity_real_integration.py` (real engine, real Named
Pipe transport, real MRQ):

```
authorized range        : 1-2
fresh evidence range    : effective frames 1 2
unique png artifacts    : 2
job identity            : exact
receipt                 : issued, persisted, evidence-bound
result                  : 1 passed in 9.51 s
```

Diagnostic full-range run against the same live boundary (authorized `1-5`):

```
fresh evidence range    : 1 5
identity continuity     : PASS (path, range, directory, format, boundary)
unique artifacts        : 5 (AtlasRender_0001..0005) == authorized inclusive count 5
receipt                 : matches evidence, persisted
```

All four tracked Unreal fixtures are byte-identical to their committed baseline
after the gate.

## Not implemented (explicitly out of scope)

* Frame-count completeness for non-PNG formats (no format-specific contract).
* Distributed or multi-job render orchestration.
* Any new transport operation, entity cache, or Atlas-side workflow engine.
* Binding the trusted controller context's declared sequence path at context
  construction; the reconciliation happens at the workflow boundary, before any
  mutation or submission.

## Deterministic verification

```
tests/test_unreal_shot_continuity.py                        43 passed, 1 skipped
tests/test_unreal_shot_continuity_design_gate.py                         8 passed
continuity-area selection (25 modules)                     242 passed, 1 skipped
canonical controller/host suite                            160 passed, 2 deselected
blast-radius sweep (180 files, -m "not integration")      1067 passed, 6 skipped
```

The skipped case is the single-frame range in the "incomplete coverage per
authorized range" matrix, which has no strictly smaller valid frame range.

## Remaining risk

- PNG frame-count completeness only; other formats keep existence validation.
- The MRQ queue accumulates submitted jobs across submissions within one editor
  session, and a new executor's per-job callback can attribute another queue
  job's artifacts to the newly submitted job. The live gate therefore starts
  from a fresh editor session. Queue hygiene is a separate boundary question and
  was not changed here.
- The trusted controller context's declared sequence path is reconciled at the
  workflow boundary (before any mutation or submission) rather than at context
  construction.
