# Unreal Agent - Shot Continuity Reconciliation (local vs remote)

**Date:** September 17, 2026
**Temporary branch:** `reconcile/shot-continuity-merged` (created from the remote tip `2e3d8e8`; nothing pushed)
**Remote tip:** `2e3d8e8` (8 commits, parallel continuity implementation)
**Local head:** `0e11d2b` (7 commits, LIVE CLEAR)
**Common checkpoint:** `86467ac`
**Constraint honoured:** no force push, no rebase discarding either side, no mechanical conflict resolution, no receipt change made merely to remove a conflict.

## Reconciliation method

The temporary branch was created from the remote tip, then every conflicting artifact was
resolved by an explicit semantic decision (recorded below), not by taking one side's diff
wholesale. Two capabilities were taken *from* the remote implementation and are new to the local
tree: the artifact frame-set rule and its adversarial test cases. Everything the remote carries
that the local architecture rejects is enumerated under "Rejected from remote" with the reason.

## Semantic diff and decisions

| Area | Remote change | Local change | Decision | Rationale |
| --- | --- | --- | --- | --- |
| `unreal_shot_continuity.py` | new module: `UnrealShotContinuity` record with `from_production_plan(plan, sequence_asset_path)`, `verify_job_state`, `verify_artifacts`; rewrites declared values in `__post_init__` | new module: `UnrealShotContinuity` record with `continuity_digest`, `end_frame_exclusive`, `snapshot`, plus `verify_shot_continuity_identity` / `verify_shot_continuity_completeness` | **keep local** | Add/add collision. Local keeps the declared values (no silent rewriting), carries an identity digest bound into authorization, owns the inclusive-to-half-open boundary rule, and is the live-proven verifier. |
| `unreal_render_continuity.py` (remote only) | second verifier taking five expected values as kwargs, with its own envelope resolution and directory canonicalization, PNG required for every format | did not exist | **not retained; its frame-set rule folded into the local completeness verifier** | Evaluated for reuse as required. As written it is a second continuity authority with a weaker derivation (no authorization binding, no identity digest) and duplicate helper rules. The one genuinely stronger rule - exact artifact frame set - was adopted. |
| `unreal_production_workflow.py` | `_render_continuity()` + passes a continuity `Mapping` into `wait_for_completion` | continuity bound through `production.continuity` + authorization digest, authorized path submitted, final evidence re-verified | **keep local** | The remote extraction derives frames/output from the authorized plan (good) but takes the sequence identity from the runtime `run()` argument, which is the exact deficiency this milestone exists to close. Local derives all five values from the authorized production intent and rejects a differing declared path. |
| `unreal_render_workflow.py` | `continuity: Optional[Mapping]` kwarg forwarded to the continuity verifier | `expected_continuity: Optional[UnrealShotContinuity]` kwarg verified before receipt issuance | **keep local** | A typed contract beats an untyped mapping; the continuity record carries its own validation and identity. |
| `unreal_render_job_verifier.py` | gains `expected_continuity` and calls continuity methods from inside the job verifier | extracts `resolve_render_job_state` so every consumer resolves evidence one way; verifier stays continuity-free | **keep local verifier shape; adopt the artifact rule elsewhere** | Job identity/fresh-evidence responsibilities stay in the job verifier; continuity stays a separate verification step. Avoids duplicating continuity authority inside a frozen module. The remote module's `expected_continuity: UnrealShotContinuity = None` default is also mistyped. |
| `unreal_render_receipt.py` | optional continuity fields; `receipt_digest` mixes them with empty placeholders; conditional snapshot; two accepted snapshot shapes | unchanged | **keep local (baseline receipt)** | See the receipt comparison below. |
| `unreal_render_receipt_store.py` | accepts two envelopes; `save()` writes `**receipt.snapshot()` | unchanged | **keep local (baseline store)** | Follows from the receipt decision. |
| `UnrealPlanAuthorization` | untouched | optional `continuity_digest` binding, fail-closed `matches(..., continuity_digest=...)`, legacy digests unchanged | **keep local** | No competing remote change; this is what makes the sequence identity authorization-bound. |
| `UnrealProductionSpec` / `UnrealProductionPlan` | untouched | spec declares `sequence_asset_path`; plan carries `continuity` and refuses to construct unless it agrees with the plan's own `configure_render` / `set_sequencer_playback_range` operations | **keep local** | The remote sequence identity has no declarative home, so its authority cannot be checked. |
| Unreal transport (C++) | untouched | effective MRQ range captured at submission, semantic inclusive `start_frame`/`end_frame` plus `end_frame_exclusive` exposed; inclusive end translated to `CustomEndFrame = end + 1` | **keep local** | The remote has no transport change, so its verifier cannot be satisfied by a real engine read (see below). |
| Affected tests | new `tests/test_unreal_render_continuity.py` (deterministic, hand-supplies the frame fields) | continuity gate with 47 cases, design gate, live continuity gate, fixtures declaring the production sequence identity | **keep local; port the remote's adversarial artifact cases** | Their missing-frame, extra-frame and duplicate-frame cases are good coverage; they were rewritten against the local verifier. The remote file is removed with them (no orphan test for a removed module). |

## Receipt comparison (required written decision)

**A. Existing evidence-bound receipt (adopted).** `job_id`, `sequence_asset_path`,
`evidence_digest`, derived `receipt_digest`; issued only after the authorized continuity has been
verified against fresh evidence; `matches()` re-issues from the evidence and compares.

**B. Extended receipt containing continuity fields (remote).** Adds optional `start_frame`,
`end_frame`, `output_directory`, `output_format`; mixes them into `receipt_digest` with
empty-string placeholders; conditional snapshot; two accepted snapshot shapes; store accepts two
envelopes.

**Does B provide a security or integrity property A does not already provide? No.**

1. The four fields are copied from the same `observed_state` that `evidence_digest` already
   hashes. B duplicating evidence does not add integrity; it re-states hashed data in the clear.
2. B does not bind authorization. It records what the engine reported, never the authorized
   values, so it cannot prove that the continuity check ran or passed. If proof of verification is
   ever wanted, the correct artifact is the *authorized* `continuity_digest` (already bound into
   `UnrealPlanAuthorization.continuity_digest`) recorded as provenance - not as receipt identity.
3. B weakens receipt identity stability. Measured with the unchanged canonical encoder:

   ```
   material (job_id, sequence, evidence_digest)                      -> 932398cc3457c7e47ced8f1e2445b126
   same material + 4 empty placeholders (remote shape)               -> f691ef5a6b67427bd5ddd78298034afa
   identical                                                         -> False
   ```

   Every previously persisted base receipt stops matching a receipt re-issued by B, and the store
   grows a shape/version branch for no integrity gain.
4. B makes identity shape-dependent: the extension appears only when the engine state happens to
   carry the fields.

**Decision: adopt A; do not adopt the receipt expansion.** This is a documented contract decision,
not a conflict-elimination convenience: B was rejected on integrity grounds, independent of the
merge. If Luna wants durable proof-of-verification, the proposed minimal form is a new
explicitly-versioned `continuity_digest` provenance field in the store envelope, leaving
`receipt_digest` untouched.

## Adopted from remote

* Exact artifact frame-set rule: one unique artifact per authorized frame, frame number parsed
  from the artifact name, duplicate frames rejected, missing/extra frames named in the error.
  The local count rule alone would accept `{1,2,3,4,6}` for an authorized `1-5`; that hole is now
  closed. Implemented PNG-only, preserving the frozen "do not generalise the frame rule" boundary.
* The remote's adversarial artifact cases (missing frame, extra frame, duplicate frame, artifact
  without a frame number), ported to the local verifier's API.

## Rejected from remote

* `planning/unreal_render_continuity.py` as a second verifier (its rule was adopted, the module
  and its independent authority were not).
* Receipt and store expansion (integrity analysis above).
* `expected_continuity` inside `verify_render_job_completion` (duplicate continuity authority in a
  frozen module, mistyped default).
* Continuity-by-kwargs-mapping and sequence identity from the runtime argument.
* Record normalization that rewrites declared values, and PNG-only artifact policy for
  non-PNG output formats.

## Required outcomes checklist

| # | Outcome | Where it is satisfied |
| --- | --- | --- |
| 1 | Atlas inclusive frame semantics preserved | `UnrealShotContinuity` (inclusive start/end), `expected_frame_count` |
| 2 | Live-proven MRQ boundary translation preserved | `AtlasTransportServer.cpp` `CustomEndFrame = Atlas end + 1`, `UnrealShotContinuity.end_frame_exclusive` |
| 3 | Fresh effective frame evidence incl. raw engine boundary | `FRenderJobState` + `inspect_render_job` `start_frame` / `end_frame` / `end_frame_exclusive`, verified by `verify_shot_continuity_identity` |
| 4 | Exact sequence identity bound to the authorized intent | `UnrealProductionSpec.sequence_asset_path` -> `UnrealProductionPlan.continuity` -> `UnrealPlanAuthorization.continuity_digest`; workflow rejects a differing declared path |
| 5 | `unreal_render_continuity.py` evaluated for reuse | evaluated; not retained as a verifier, its frame-set rule folded into the local completeness verifier |
| 6 | Receipt expansion not automatically adopted | written A/B comparison above; A adopted, B rejected on integrity grounds |
| 7 | Live-proven PNG completeness preserved and strengthened | `observed frame set == authorized inclusive frame set` (frame-set rule) plus the count guard |
| 8 | Exact job-ID binding preserved | unchanged `expected_job_id` path in `verify_render_job_completion` and the executor |
| 9 | Fail-closed recovery preserved | production recovery modules untouched; no mutation retry, new authorization required |
| 10 | No Named Pipe protocol change, no new orchestration authority | transport request schema unchanged (response fields additive); no new authority, no entity cache, no workflow engine |

## Deterministic verification on the reconciled tree

```
focused reconciled suite (23 modules)                     213 passed, 1 skipped
canonical controller/host suite                           160 passed, 2 deselected
consolidated affected Unreal suite (36 modules)           298 passed, 1 skipped
broad non-integration sweep (180 files)                  1070 passed, 6 skipped
```

Test-expectation updates on this tree (classification: test expectation update, intent unchanged):
the legacy duplicate-artifact case now asserts the more specific duplicate-frame guard, which
fires before the count guard after the frame-set rule was adopted.

## Not done (deliberately)

* Nothing pushed; the temporary branch is local only.
* No live UE gate was run on the reconciled tree: the instruction defers it until reconciliation
  is complete, deterministic suites are green, and the receipt decision is documented. All three
  conditions are now met, so the live continuity gate is the next step after Luna's review.
* No merge into `reconcile/unreal-autonomy-origin-20c6d10` and no change to the remote branch.

## Recommended merged contract for review

1. Keep the local continuity contract as the single continuity authority, including the
   authorization digest binding and the boundary translation.
2. Keep the local receipt (A); treat continuity-verified issuance as the gate, not as new receipt
   identity. If provenance is wanted, add a versioned `continuity_digest` field to the store
   envelope as a separate decision.
3. Delete `planning/unreal_render_continuity.py` and `tests/test_unreal_render_continuity.py`;
   their useful rule and cases now live in the local verifier and its tests (done on this branch).
4. Keep `verify_render_job_completion` continuity-free with `resolve_render_job_state` as the
   single envelope rule.
5. Re-run the live continuity gate (fresh editor session) on the reconciled tree before publishing,
   then publish by fast-forwarding the shared branch to the reconciled result - subject to Luna's
   approval.
