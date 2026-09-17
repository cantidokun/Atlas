# Unreal Agent — MRQ Artifact Attribution Closeout

**Date:** September 17, 2026
**Milestone:** MRQ queue hygiene / artifact attribution — Slice 1 + Slice 2, then Slice D (start-callback identity)
**Design gate:** `CLEAR WITH MINOR CONDITIONS` (relayed by the operator); queue-lifecycle review `CLEAR WITH MINOR FINDINGS`
**Status:** `MRQ artifact attribution — COMPLETE + LIVE-PROVEN` — deterministic green + both live UE 5.6.1 gates
green, architecture gate CLEAR, committed in the milestone commit on top of `6e63d15` (Slice 1 + Slice 2, published
as `8ecf7db`); **Slice D added on top of that** — deterministic green + a one-session live gate with a
pre-populated multi-job queue.

```text
  - job identity guard is live-proven in a multi-submission single-editor session
  - foreign callback artifacts are discarded
  - PNG artifacts must be contained within the authorized output directory
  - exact frame-set verification remains active
  - Slice 3 queue consumption remains separate and unimplemented
  - Slice D: monitoring state is job-scoped - a foreign queued job cannot overwrite the new Atlas job's
    Status / StatusMessage / Progress (added after the queue-lifecycle review)
```

## What the milestone closed

An MRQ submission renders every job already present in the editor's queue, and the per-job callback for the new
job was identity-blind, so a later submission could absorb earlier jobs' artifact paths into its own evidence -
including the same-range case, where the artifact list looked correct and was hashed into the receipt. That
operator dependency ("fresh editor session + empty queue") is now removed at the attribution boundary.

```text
callback job identity == Atlas registered job identity   => artifact ownership MAY be recorded
otherwise                                                => no artifact ownership is recorded
observed PNG artifact must live inside the AUTHORIZED output directory
```

## Delivered

| Slice | Change | File | sha256 |
| --- | --- | --- | --- |
| 1 | identity guard in `OnIndividualJobWorkFinished` | `unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Private/AtlasTransportServer.cpp` | `62798b17070b9697760934148bd1748e165f9ab3af36696cc1a476f74462b56c` |
| 2 | PNG containment against the authorized directory | `planning/unreal_shot_continuity.py` | `1afbbdce0ab9a3ba2c6364c73bdcc89bd1c0b843f18fdad6091361c0da9773a3` |
| 2 | fixture alignment (declared directory now holds the artifacts) | `tests/test_unreal_shot_continuity.py` | `e45b633abceca8e33193b482ee3ad255103b0c49d5ab180c7fef24e5d9c8dafc` |
| 1+2 | deterministic attribution contract (new, 14 tests) | `tests/test_unreal_mrq_attribution_contract.py` | `ef3125eb3eb2296afc9edcf5528f333c4f5f644e4788a1ce3f13133a68ed30bd` |
| 1+2 | same-session live gate (new, 2 tests) | `tests/test_unreal_mrq_attribution_real_integration.py` | `06f05a3817168f32b9085a924f4776345fb917fae64c658b6d8ac325100c84aa` |
| 1 | rebuilt transport DLL (functional proof of the loaded guard) | `unreal/AtlasUnrealHarness/Binaries/Win64/UnrealEditor-AtlasUnrealTransport.dll` | `f4c895aa50e240d31c659761d05b9122eecc8d68f9946177d663fbaacbee8197` |

Diffstat (`git diff --stat -- planning/ tests/ unreal/`): 3 files changed, 133 insertions, 44 deletions
(`planning/unreal_shot_continuity.py` +65, `tests/test_unreal_shot_continuity.py` +47/-, `AtlasTransportServer.cpp` +65/-).

## Verification summary

```text
focused MRQ continuity/auth/receipt set (17 modules)      207 passed, 1 skipped
new deterministic attribution contract                      14 passed
consolidated affected Unreal suite (36 modules)            291 passed, 2 skipped   (unchanged from baseline)
canonical controller/host suite (13 modules)               160 passed, 2 deselected (unchanged from baseline)
broad scoped sweep (180 files)                            1137 passed, 6 skipped  (baseline 1123 + 14 new)
Slice D deterministic contract                             7 passed; red proof at e64c3e3: 5 of 7 FAIL
Slice D affected sweep, identical selection               1198 passed, 7 skipped vs baseline 1191 passed,
                                                           7 skipped (= +7 new tests; 2 pre-existing live-only
                                                           modules error identically at baseline when no editor
                                                           is running - not a Slice D regression)
Slice D live gate, ONE session, pre-populated queue       2 passed in 35.22 s (12/12 and 8/8 mid-render state
                                                           reads "submitted"; own transition to "rendering";
                                                           exact 10/5/2/2 artifacts; receipts coherent;
                                                           same-range case isolated; fixtures byte-identical)
baseline RED proof (worktree at 6e63d15)                   all guard assertions FAIL; foreign-directory
                                                           artifacts with the authorized frame set ACCEPTED

live, ONE editor session, FOUR submissions:
  tests/test_unreal_mrq_attribution_real_integration.py    2 passed in 26.18 s
  engine log: starting 1 -> 2 -> 3 -> 4 jobs; 6 guard discards (1+2+3 = N-1 per submission)
live regression, own fresh session:
  tests/test_unreal_shot_continuity_real_integration.py    1 passed in 9.60 s (1-2 -> 2 PNGs, exact job id,
                                                           receipt issued; proves containment accepts real paths)
tracked fixtures: all four byte-identical to baseline; no save-on-exit; pipe released; editors killed
```

## Frozen invariants preserved (nothing in this list changed)

Named Pipe protocol; request/argument schemas (`submit_render`, `inspect_render_job`, `verify_render_job`
key sets unchanged); authorization model and exact job-ID binding; `UnrealShotContinuity` as the single
continuity authority; inclusive Atlas frame semantics and the single MRQ end-frame translation; exact PNG
frame-set verification; receipt architecture (`job_id, sequence_asset_path, evidence_digest`); fresh-evidence
verification; fail-closed recovery with no automatic mutation retry; no entity cache/discovery; no distributed
rendering; no generic workflow engine; Blender untouched.

## Deliberately NOT done

1. **Slice 3** (delete/consume Atlas's own completed queue jobs) — not implemented, as instructed.
2. No queue clearing, no transport/protocol change, no new operation or response field, no new persistence for the
   render-job registry, no artifact discovery, no multi-shot collection, no receipt change.
3. Nothing committed, pushed, merged, rebased, or reset; the published baseline `6e63d15` is untouched.

## Residual findings to carry (reported, not fixed)

1. ~~**`OnIndividualJobStarted` is still identity-blind**~~ — **FIXED by Slice D.** A foreign job's start used to
   write `Status="rendering"` and `Progress` into the newest job's state. Slice D gates every monitoring-state
   write on `InJob == FRenderJobState::Job` and fails closed on an unresolved/expired registry entry; the
   one-session live gate proved the property while a foreign queued job was rendering. See §7 of the
   implementation record.
2. **`ShotData[0]`-only collection** remains (multi-shot sequences stay outside the frozen contract).
3. **MRG payload-identity caveat** (design §4): under Movie Render Graph the payload job may be a duplicate, so
   the guard fails closed rather than mis-attributing. Not exercised by this harness.
4. **The C++ guard has no deterministic execution cover** in this repository — live gate + source-level
   assertions only; recorded as a limitation of the evidence, not as a proven-absent risk.
5. `unreal_render_workflow._job_state` still duplicates `resolve_render_job_state` (pre-existing, untouched).

## Next

`docs/UNREAL_NEXT_ARCHITECTURE_REVIEW.md` carries the next review. The immediate candidate is **concurrent
submission rejection / error propagation** (finding F2 of the queue-lifecycle review): a submission made while
another render is active is refused by the subsystem's `ensureMsgf(!IsRendering())`, the transport cannot surface
that refusal, and the caller observes a poll timeout. It is deliberate that this was **not** fixed inside the
Slice D work and that no timeout change or synthetic success was used to hide it. Still unimplemented and
unauthorized: Slice 3 queue consumption, and the Atlas-owned private queue instance.
