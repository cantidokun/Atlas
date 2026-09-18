# Unreal Agent - Remote Shot-Continuity Implementation Evaluation

**Date:** September 17, 2026
**Local head:** `0e11d2b` (6 commits, LIVE CLEAR)
**Evaluated ref:** `origin/reconcile/unreal-autonomy-origin-20c6d10` (8 commits, merge base `86467ac`)
**Method:** read-only comparison of the remote implementation against the local, live-proven contract. No merge, rebase, or force push was performed.

## Summary verdict per item

| Remote item | Verdict |
| --- | --- |
| `unreal_render_continuity.py` (generic final-evidence verifier) | REJECT as a second verifier; ADOPT its exact-frame-set artifact rule into the local contract |
| Receipt extensions | REJECT - no integrity the evidence digest does not already provide, and it destabilizes receipt identity |
| `_render_continuity()` extraction | INSUFFICIENT - frames/output derive from the authorized plan, but the sequence identity comes from the runtime argument |
| Render-job verifier changes | REJECT the continuity parameter (duplicates continuity authority in a frozen module); ADOPT the artifact-rule strengthening |

## 1. `unreal_render_continuity.py` vs the local `UnrealShotContinuity`

Field set is identical (sequence asset path, inclusive start/end, output directory, output format), but the two contracts differ on five axes.

| Axis | Remote (`unreal_shot_continuity.py` + `unreal_render_continuity.py`) | Local (`planning/unreal_shot_continuity.py`) |
| --- | --- | --- |
| Sequence identity source | `UnrealShotContinuity.from_production_plan(plan, sequence_asset_path)` - the path is a caller argument (`unreal_shot_continuity.py:60-89`) | `UnrealProductionSpec.sequence_asset_path` -> `UnrealProductionPlan.continuity`, declared in the production intent |
| Authorization binding | None; no identity digest, no relationship to `UnrealPlanAuthorization` | `continuity_digest` bound into the receipt via `UnrealPlanAuthorization.issue(..., continuity_digest=...)`; required by `UnrealProductionWorkflow.run()` |
| Boundary semantics | None; the verifier assumes the engine reports an inclusive `end_frame` | `end_frame_exclusive` + verifier requires the engine boundary to correspond to the authorized inclusive range |
| Declared vs normalized values | `__post_init__` rewrites the record (strips the path, lowercases the format, makes the directory absolute, `unreal_shot_continuity.py:52-54`) | stores the declared values and canonicalizes only for comparison, so the record stays the authorized declaration |
| Shared rules | re-implements the render-job envelope resolution and directory canonicalization (`unreal_render_continuity.py:21-45`) - a third and second copy of each | one `resolve_render_job_state` and one `canonicalize_output_directory`, used by every consumer |

**Artifact rule - the one place the remote is stronger.** `unreal_render_continuity.py:48-52, 121-145` parses the frame number out of each artifact filename and requires `observed_frames == set(range(start, end + 1))`, rejecting duplicates and naming missing/extra frames. It also resolves relative paths against the canonical output directory and requires existence and non-zero size for absolute paths (`:132-133`).

The local rule is `unique(output_files) == end_frame - start_frame + 1`. That leaves a real hole: an authorized `1-5` job whose artifacts are frames `{1, 2, 3, 4, 6}` has five unique files and satisfies the count rule although frame 5 is missing. This is a genuine coverage gap, not a style difference.

Remote weaknesses in the same function: it requires PNG unconditionally (`unreal_shot_continuity.py:125-128`, `unreal_render_continuity.py:130-131`), so non-PNG output cannot be verified at all, whereas the design review freezes the frame rule to the PNG boundary while keeping existence validation for other formats.

**Recommendation:** keep the local contract authoritative; adopt the exact-frame-set rule (PNG only) into the local completeness verifier; do not introduce `unreal_render_continuity.py` as a second continuity verifier. The two modules collide on `UnrealShotContinuity` (add/add), so reconciliation must delete one of them, and the surviving name must carry the local semantics.

## 2. Receipt extensions - do continuity fields belong in receipt identity?

Remote shape (`planning/unreal_render_receipt.py` diff): optional `start_frame`, `end_frame`, `output_directory`, `output_format`; the four values are mixed into `receipt_digest` with empty-string placeholders when absent; `snapshot()` gains the fields conditionally; `from_snapshot` accepts two shapes; the store accepts two envelopes.

Findings:

1. **The fields duplicate the evidence digest, not the authorization.** `issue()` copies the values out of `state` (`unreal_render_receipt.py` diff, the `continuity_keys.issubset(state)` branch), i.e. the very same `observed_state` that `evidence_digest` already hashes. Nothing new is integrity-protected.
2. **They do not bind authorization.** The receipt never sees the authorized values; it sees what the engine reported. A receipt carrying `start_frame=1, end_frame=2` is therefore not evidence that `1-2` was authorized - only that the engine reported it, which the evidence digest already covers.
3. **They change base receipt identity.** Because the four placeholders are hashed, the `receipt_digest` of an *unchanged* base receipt changes for any fixed (job_id, sequence, evidence_digest). Every previously persisted base receipt stops matching a receipt re-issued by the new code, and the store must carry two envelope shapes plus a version branch.
   Measured (`_canonical_material` with a fixed identity, local helper):

   ```
   3-part material (local, unchanged) : 932398cc3457c7e47ced8f1e2445b126
   7-part material (remote shape)     : f691ef5a6b67427bd5ddd78298034afa
   identical                          : False
   ```
4. **Identity becomes non-uniform.** Continuity fields are attached only `if continuity_keys.issubset(state)`, so a receipt may or may not carry them depending on what the engine reported.
5. **The local form already proves the same facts at the correct boundary.** `UnrealRenderReceipt` is unchanged (`job_id`, `sequence_asset_path`, `evidence_digest` + derived `receipt_digest`), and it is issued only after `verify_shot_continuity_completeness` has compared authorized values with fresh evidence; `matches()` re-verifies by re-issuing from the evidence.

Verdict: **REJECT** the receipt extension - no concrete integrity gap is closed, and the cost is a receipt-identity compatibility break plus schema surface.

If durable proof-of-verification is wanted later, the minimal correct artifact is provenance, not identity: record the *authorized* `UnrealShotContinuity.continuity_digest` (already bound into `UnrealPlanAuthorization.continuity_digest`) alongside the receipt in the store envelope as an explicitly versioned field, leaving `receipt_digest` untouched. That decision is not required by any frozen invariant and is not implemented.

## 3. `_render_continuity()` audit

`UnrealProductionWorkflow._render_continuity(production, sequence_asset_path)` (remote `planning/unreal_production_workflow.py`):

* Frames, output directory, and output format: **derived from the authorized production plan** - they are read from the plan's own `configure_render` operation and the function fails closed when that operation or a field is missing. Good.
* Sequence asset path: **NOT derived from the plan** - `"expected_sequence_asset_path": sequence_asset_path`, the value passed into `run()`. `run()` still takes `sequence_asset_path` as an input and there is no continuity identity in the production authorization.

Consequence: the remote check proves the engine echoed the submitted path (design-review invariant 3), but it does not bind the path to the authorized production intent (invariant 1), and a caller can satisfy it with any self-consistent path. This is the exact deficiency the design review opened the milestone for, so the extraction is **insufficient for our architecture**; the local binding (`UnrealProductionSpec.sequence_asset_path` -> `continuity_digest`, plus the workflow's rejection of a differing declared path) supersedes it.

Nothing here needs preserving beyond the plan-derived frames/output idea, which the local plan carries structurally: `UnrealProductionPlan.__post_init__` refuses to exist unless its continuity record agrees with its own `configure_render` and `set_sequencer_playback_range` operations.

## 4. Render-job verifier changes

Remote `verify_render_job_completion` gains `expected_continuity: UnrealShotContinuity = None` and calls `verify_job_state` + `verify_artifacts`, and its docstring is rewritten.

* **Reject:** importing the continuity authority into this module. `unreal_render_job_verifier.py` owns render-job identity and fresh-evidence semantics; making it continuity-aware duplicates continuity authority and couples two boundaries (also visible in the remote render workflow, which now passes a `Mapping` of continuity kwargs into `wait_for_completion`). The parameter default is also mistyped (`= None` on a non-Optional annotation).
* **Reject:** the removed envelope-resolution comment/logic stays inline in the remote copy; the local tree resolved that by extracting `resolve_render_job_state` for every consumer.
* **Adopt:** the artifact-rule strengthening (exact frame set, duplicate rejection, relative-path resolution, existence/size, missing/extra diagnostics) - implemented inside the local continuity completeness step, PNG only.
* Nothing in the remote changes weakens exact job identity, so the local identity guarantees (`expected_job_id` binding, `inspect_render_job` verification) are unaffected either way.

## Verdict on the parallel implementation

The remote 8 commits implement the *same contract intent* with a weaker authority model and no engine-side evidence:

* no transport change, so `inspect_render_job` still does not report the effective frame range on the remote side; its verifier requires `start_frame`/`end_frame` in the evidence, which only its deterministic fixtures supply. No live gate was added (`git diff --name-only 86467ac..<remote>` contains no `*real_integration*` file).
  Verified against the baseline transport: `git diff --name-only 86467ac..<remote> -- unreal/` is empty, and the baseline `InspectRenderJob` payload contains exactly `job_id, status, status_message, progress, success, finished, failed, sequence_asset_path, output_directory, output_format, output_files` with zero occurrences of `start_frame`. Therefore a real engine read on that branch cannot satisfy `verify_render_job_continuity`, which raises "final render evidence must contain an integer start_frame" (`unreal_render_continuity.py:89-94`). Its deterministic tests pass only because their fixtures hand-supply the fields the engine does not emit.
* the sequence identity check is bound to a runtime argument, not to authorization;
* the receipt is extended without adding integrity.

Recommended reconciliation (needs the architect's decision, not performed here):

1. Keep the local continuity contract, authorization binding, boundary translation, transport evidence fields, and live gate.
2. Drop `planning/unreal_render_continuity.py`; fold its frame-set artifact rule into `verify_shot_continuity_completeness` (PNG only) and add its deterministic negative cases (missing frame, extra frame, duplicate frame, non-PNG artifact) to `tests/test_unreal_shot_continuity.py`.
3. Revert the receipt/store extensions; if proof-of-verification is wanted, add `continuity_digest` provenance to the store envelope as a separate versioned field.
4. Keep `verify_render_job_completion` free of continuity parameters; keep `resolve_render_job_state` as the single envelope rule.
5. Require a live UE 5.6.1 gate on whatever reconciliation lands, because the remote side has none.
