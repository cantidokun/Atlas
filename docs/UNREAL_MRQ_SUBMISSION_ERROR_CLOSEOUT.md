# Unreal Agent — MRQ Submission Outcome Propagation Closeout

**Date:** September 17, 2026
**Milestone:** `MRQ submission outcome propagation — COMPLETE + LIVE-PROVEN`
**Design gate:** `CLEAR WITH MINOR FINDINGS` (`docs/UNREAL_MRQ_SUBMISSION_ERROR_DESIGN_REVIEW.md`, relayed by the
operator)
**Baseline:** `reconcile/unreal-autonomy-origin-20c6d10` @ `9e2c893f1db6b79c77caea3fb4595a6217d3ef1f`
**Status:** deterministic green + one clean live UE 5.6.1 session green; ready to commit and publish.

```text
  - the submission call and its acceptance observation happen in one game-thread task
  - acceptance is proven by GetActiveExecutor() == the exact supplied executor
  - a refused submission is reported immediately as a typed failure, not as a 300 s poll timeout
  - an unprovable outcome fails closed as ambiguous
  - a rejected submission exposes no pollable job, produces no receipt, and is never retried
  - queue consumption unimplemented
  - private queue migration unimplemented
  - automatic retry prohibited
  - exact job identity unchanged
  - receipts only from fresh verified terminal evidence
```

## What the milestone closed

A render submission made while another render was already active was refused by the engine
(`UMoviePipelineQueueSubsystem::RenderQueueInstanceWithExecutorInstance` ->
`ensureMsgf(!IsRendering())` -> `KismetExecutionMessage("Render already in progress.")` -> `return`), but the
transport had already deferred the start into a discarded `AsyncTask`, registered the job as `"submitted"` and
returned a success response. Atlas therefore polled a job that would never start until its 300 s timeout and
reported a slow render. Measured before the fix: the refusal was invisible, the entry stayed `"submitted"`
forever, and no receipt was ever issued (fail-closed, but with the wrong diagnosis and the full timeout cost).

The slice makes the submission establish its outcome before Atlas treats the job as accepted.

## Delivered

```text
unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Private/AtlasTransportServer.cpp   +67 / -9
    inline submission call + immediate GetActiveExecutor() identity observation in the same game-thread task
    accepted  -> unchanged response (existing job identity, status, polling)
    rejected  -> operation fails with a typed message; no job identity exposed; registry entry removed
    ambiguous -> fail closed with a typed message
tests/test_unreal_mrq_submission_outcome_contract.py                          18 deterministic tests (NEW)
tests/test_unreal_mrq_submission_outcome_real_integration.py                  2 live tests (NEW)
```

No planning/ module, Blender file, protocol field, receipt/evidence contract, queue operation, timeout value or
continuity rule was changed. `git diff --name-only` for the slice is one transport source file plus the two new
test modules and documentation.

## Verification summary

```text
focused set (new slice + attribution + continuity + workflow + verifier + receipt + executor + adapter)
                                                                  185 passed, 1 skipped
broad sweep, identical selection as previous milestones            1216 passed, 7 skipped
                                                                   (baseline 9e2c893: 1198 passed, 7 skipped; +18)
baseline RED proof (throwaway worktree at 9e2c893)                 8 of 18 FAIL - all transport-outcome
                                                                   assertions; the 10 that pass at baseline are
                                                                   the unchanged invariants + existing plumbing
live UE 5.6.1, ONE fresh session (log 20:10:33)                    2 passed in 22.80 s, four submission attempts
  A accepted while idle          job CE3199F4-...  (1-24), job reached its own "rendering" state
  B attempted while rendering    REJECTED in 1.50 s with a typed, non-timeout error
  C no receipt for B             the rejected submission's receipt file was never created
  D multi-job queue              accepted job 2B55DA72-... -> exactly 2 PNGs in its own directory
  E same range twice             accepted job 6DA54FB0-... -> exactly 2 PNGs, disjoint from D's artifacts
  F accepted jobs unchanged      exact job identity, continuity completeness, coherent receipts
engine log corroboration           1x "Render already in progress." (the engine's own refusal)
                                   1x "ATLAS MRQ SUBMISSION: rejected; another executor is active"
                                   3x "starting N jobs" (1, 3, 4) for FOUR submission attempts
                                   3x executor finishes; 6x Slice 1 attribution discards
DLL provenance                     source blob 1d7d33fd... (20:05:12) -> build 20:05:35 -> DLL 20:05:34,
                                   364,544 bytes, sha256 4b7dc0a8a604570600c664710adcc3088b4b78556892fc8a6409734718fc46a5
                                   session loaded 0.348 MB (previous slice's binary was 0.345 MB)
tracked fixtures                   all four byte-identical to baseline before and after the gate; editor killed;
                                   pipe released; disposable output directories removed
```

## Frozen invariants preserved (nothing in this list changed)

Named Pipe protocol and its operation/argument/response field sets (21 operations, 7 response fields - both
asserted by tests); authorization model and production-spec -> production-plan -> authorization sequence binding;
exact engine-minted render-job identity; receipt architecture (`job_id, sequence_asset_path, evidence_digest`)
and the "receipt only from fresh verified terminal evidence" gate; `UnrealShotContinuity` as the single
continuity authority; inclusive Atlas frame semantics and the single MRQ end-frame translation; shot continuity
and PNG containment/frame-set verification; MRQ artifact attribution (Slice 1 + Slice D); queue semantics (no
deletion, no consumption, no private queue instance); recovery fail-closed with no automatic mutation retry; no
entity discovery/cache; no distributed rendering; no generic workflow engine; no model-derived authority;
Blender untouched.

## Deliberately NOT done

1. **Queue consumption / deletion** — not implemented, as instructed.
2. **Private queue instance / queue isolation** — not implemented; it is the subject of the next review.
3. **Registry pruning** — no pruning was added; only the entry of a *rejected* submission is removed. Entries
   for accepted jobs are still retained for the life of the editor process (pre-existing).
4. **Timeout redesign** — the 300 s default is unchanged and was asserted unchanged; no sleep, backoff or
   elapsed-time inference was introduced anywhere in the submission path.
5. **No automatic retry** — a rejected or ambiguous submission is a terminal failure at `submit_render`; the
   tests assert exactly one submission attempt.
6. Nothing committed, pushed, merged, rebased or reset by the implementation task itself; publication follows
   the operator's gate.

## Residual findings to carry (reported, not fixed)

1. **A rejected submission leaves its allocated MRQ job in the queue** (queue mutation is frozen), so a later
   accepted submission renders it: measured `starting 3 jobs` and two orphan PNGs in the rejected job's
   configured directory. They are not evidence - no receipt, no Atlas job identity, and Slice 1 discarded the
   payload - and they never enter an accepted job's evidence.
2. **Engine mutual exclusion remains best-effort** (design-review finding F2): the PIE executor sets
   `bIsRendering` only in `OnPIEStartupFinished`, so a submission inside that window can still be accepted by
   the engine. The slice makes the outcome truthful; it does not make the exclusion sound.
3. **No deterministic execution cover for the C++** - source-shape assertions plus the live gate, as for
   Slice 1 and Slice D.
4. **The accepted-job registry entries are never pruned** (pre-existing).
5. `unreal_render_workflow._job_state` still duplicates `resolve_render_job_state` (pre-existing, untouched).
6. Live-test harness note: the second live test synchronises on the engine's executor-finished log line to wait
   for the editor to be idle again. That is a harness precondition only; no product code reads logs, and the
   acceptance decision is identity-based.

## Next

The next architecture review is **whether queue isolation / private queue instances provide enough operational
value to justify their larger lifecycle surface** (see `docs/UNREAL_NEXT_ARCHITECTURE_REVIEW.md`). It is a
read-only design gate; nothing has been started, and queue consumption plus the private-queue migration remain
unimplemented and unauthorized.
