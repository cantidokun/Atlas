# Unreal Agent — MRQ Artifact Attribution Implementation Record

**Date:** September 17, 2026
**Baseline (published):** `reconcile/unreal-autonomy-origin-20c6d10` = `6e63d1518905bba13d113c3d30766e688547fee6`
**Design input:** `docs/UNREAL_MRQ_ARTIFACT_ATTRIBUTION_DESIGN_REVIEW.md`
**Design gate verdict (as relayed by the operator):** `CLEAR WITH MINOR CONDITIONS`
**Status:** `MRQ artifact attribution — COMPLETE + LIVE-PROVEN` (committed in the milestone commit on top of
`6e63d15`): job identity guard is live-proven in a multi-submission single-editor session; foreign callback
artifacts are discarded; PNG artifacts must be contained within the authorized output directory; exact frame-set
verification remains active; Slice 3 queue consumption remains separate and unimplemented.
**Scope delivered:** Slice 1 (engine-side provenance guard) and Slice 2 (PNG artifact containment) only.

---

## 1. Slice 1 — attribution guard in the existing per-job callback

**File:** `unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Private/AtlasTransportServer.cpp`
(`Executor->OnIndividualJobWorkFinished().AddLambda(...)`, was lines 1385-1420)
**sha256 (post-change):** `62798b17070b9697760934148bd1748e165f9ab3af36696cc1a476f74462b56c`

The lambda previously resolved its registry entry by Atlas job id only and appended every rendered job's file
paths into it. It now:

1. returns immediately when the registry entry is unresolvable
   (`if(!Found || !Found->IsValid()) { return; }`) — fail closed, nothing recorded;
2. reads the identity the transport already stores — `UMoviePipelineExecutorJob* RegisteredJob=(*Found)->Job.Get();`
   — and the identity the engine supplies for this payload — `UMoviePipelineExecutorJob* PayloadJob=InOutputData.Job.Get();`
3. discards the payload unless `PayloadJob == RegisteredJob`, logging
   `ATLAS MRQ ATTRIBUTION: discarded per-job output data for job <atlas job id>: payload job is not the registered Atlas job`
   and returning **before any state or artifact write**;
4. otherwise behaves exactly as before (status/progress/success/failure plus the existing
   `ShotData[0]` pass loop with `AddUnique`), and with the artifact loop's indentation otherwise unchanged.

No new job identity field was invented: the comparison is against the exact `UMoviePipelineExecutorJob*` held in
`FRenderJobState::Job` (`unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Public/AtlasTransportServer.h`), and the frozen member set is asserted by test.
No path, file name, frame number, timing, queue position, or callback order is consulted.

`UnrealEditor-AtlasUnrealTransport.dll` was rebuilt from this source (Build.bat `AtlasUnrealHarnessEditor Win64
Development`, exit 0, 5 actions, 23.19 s; DLL 361,984 bytes at 2026-09-17 18:31:36, previously 360,960 bytes at
2026-09-16 22:19:09; sha256 `f4c895aa50e240d31c659761d05b9122eecc8d68f9946177d663fbaacbee8197`).

## 2. Slice 2 — PNG artifact containment against the AUTHORIZED directory

**File:** `planning/unreal_shot_continuity.py`
**sha256 (post-change):** `1afbbdce0ab9a3ba2c6364c73bdcc89bd1c0b843f18fdad6091361c0da9773a3`

Two public helpers were added next to the existing contract helpers:

```text
canonicalize_artifact_path(value)   # mirrors canonicalize_output_directory: relative paths resolve against
                                    # UNREAL_PROJECT_ROOT, absolute paths resolve in place, backslashes -> "/"
                                    # (pure path arithmetic; no filesystem access)
is_inside_directory(path, directory) # path-SEGMENT containment: path.startswith(directory + "/")
```

and `verify_shot_continuity_completeness` now performs, for PNG only:

1. `output_files` must be a list/tuple (unchanged);
2. for every artifact: non-empty string (unchanged message), canonicalize the artifact;
3. canonicalize the **authorized** `expected.output_directory`;
4. require containment (`is_inside_directory`); anything outside raises
   `render job PNG artifact is outside the authorized output directory: artifact=... (canonical...), authorized_directory=...`;
5. then the existing checks run unchanged: `unique` accumulation, frame-number parse (frame-number-less artifacts
   still fail), duplicate-frame rejection, count guard, and the exact
   `observed_frames == set(range(start, end + 1))` frame-set equality.

The acceptance condition is therefore exactly: authorized frame set equality **and** one unique artifact per
authorized frame **and** every artifact inside the authorized output directory, with missing/extra/duplicate/
frame-number-less artifacts still failing. Exact frame-set verification was not replaced. No filesystem
enumeration, `mtime` discovery, or new artifact authority was introduced; containment is compared against the
authorization-bound value, never against the observed `output_directory` field. Non-PNG formats keep the previous
behavior (existence/non-empty validation only), preserving the frozen PNG scoping of the frame rule.

**Rule-order note (authorization overrode the design):** the design's §5.2 froze `count → duplicate → containment →
frame-set`. The authorization explicitly ordered containment *before* the frame checks
("1. validate … 5. reject anything outside it 6. then perform the existing exact frame-number/frame-set checks").
The implemented order is `string → canonicalize → containment → (existing) duplicate/frame-number → count →
frame-set`, which satisfies the authorization and keeps every existing expectation meaningful once fixtures model
a single directory (see §4).

## 3. Deterministic test matrix — required cases and where they live

`tests/test_unreal_mrq_attribution_contract.py` (**NEW**, sha256 `ef3125eb3eb2296afc9edcf5528f333c4f5f644e4788a1ce3f13133a68ed30bd`, 14 tests)

| Required deterministic case | Test | Result |
| --- | --- | --- |
| matching callback Job records artifacts | `test_attribution_guard_compares_the_payload_job_with_the_registered_job`, `test_attribution_guard_returns_before_any_artifact_is_recorded` | pass |
| foreign callback Job records NO artifacts | `test_attribution_guard_returns_before_any_artifact_is_recorded`, `test_attribution_guard_fails_closed_when_the_registry_entry_is_unresolvable` | pass |
| foreign callback Job with identical frame numbers cannot pass | `test_foreign_job_artifacts_with_identical_frame_numbers_cannot_pass` | pass |
| correct frame set in FOREIGN directory fails | `test_correct_frame_set_in_a_foreign_directory_fails` | pass |
| correct frame set in authorized directory passes | `test_artifacts_inside_the_authorized_directory_pass` | pass |
| sibling-directory prefix collision fails | `test_sibling_directory_prefix_collision_fails` | pass |
| path normalization/canonicalization stays deterministic | `test_canonicalization_is_deterministic_across_equivalent_spellings`, `test_relative_artifact_paths_resolve_against_the_project_root` | pass |
| missing/duplicate/extra/frame-number-less remain green | `test_frame_semantics_still_fail_inside_the_authorized_directory` + existing continuity cases | pass |
| existing non-PNG behavior unchanged | `test_non_png_formats_keep_the_existing_behavior` | pass |
| no second job identity source | `test_transport_introduces_no_second_job_identity_source` (frozen `FRenderJobState` member set; exactly one `FGuid::NewGuid()`) | pass |
| no ownership inference from path/timing/order | `test_attribution_guard_does_not_infer_ownership_from_paths_or_timing` (guard region must not mention `OutputDirectory`, `FilePaths`, `FDateTime`, `GetJobs()`, `Queue`, `Index`) | pass |
| measured pollution shape (24 artifacts from an earlier job) | `test_measured_pollution_shape_fails_closed` | pass |

**Fidelity split, stated plainly.** The transport is C++ and has no deterministic harness in this repository, so
the engine-side guard is pinned by source-level assertions (the convention this repo already uses for modules that
cannot be imported) plus the live gate; there is no deterministic test that executes the C++ guard. The
boundary-level tests above are what make a Slice 1 regression fail closed at the evidence boundary.

**RED proof at the baseline** (throwaway worktree at `6e63d15`, no worktree mutation of the review tree):
`payload job read` FAIL, `registered job read` FAIL, `identity comparison present` FAIL, `guard before artifact
recording` FAIL, `foreign-directory artifacts with the authorized frame set were ACCEPTED` FAIL (hole open),
`canonicalize_artifact_path exists` FAIL, `is_inside_directory exists` FAIL. The new test module cannot even
import at the baseline (it imports the helpers the slice adds).

### Fixture alignment (classified: test-fixture update, intent unchanged)

`tests/test_unreal_shot_continuity.py` (sha256 `e45b633abceca8e33193b482ee3ad255103b0c49d5ab180c7fef24e5d9c8dafc`):
the PNG-continuity fixtures previously declared `Saved/AtlasProductionOutput` while writing artifacts into
`tmp_path`. Ten test blocks now authorize and declare `str(tmp_path)` so the declared directory holds the
artifacts, matching the real engine relationship the new rule verifies. The `_job_evidence` docstring records
that invariant. No expectation was weakened: the same tests still assert the same errors
(`PNG frame coverage mismatch`, `duplicate frame 1`, `frame set mismatch`, `does not expose a frame number`).

## 4. Deterministic results

```text
focused MRQ continuity/auth/receipt set (17 modules, incl. the new module)   207 passed, 1 skipped
tests/test_unreal_mrq_attribution_contract.py (new)                           14 passed
consolidated affected Unreal suite (36 modules)                              291 passed, 2 skipped   (unchanged)
canonical controller/host suite (13 modules)                                 160 passed, 2 deselected (unchanged)
broad scoped sweep (180 files, -m "not integration")                        1137 passed, 6 skipped
   baseline of the same sweep was 1123 passed, 6 skipped -> +14 = exactly the new module
```

Exact commands:

```bash
.venv/Scripts/python.exe -m pytest tests/test_unreal_mrq_attribution_contract.py tests/test_unreal_shot_continuity.py \
  tests/test_unreal_shot_continuity_design_gate.py tests/test_unreal_render_job_semantic_verification.py \
  tests/test_unreal_render_job_execution.py tests/test_unreal_render_receipt.py tests/test_unreal_render_receipt_store.py \
  tests/test_unreal_plan_authorization.py tests/test_unreal_compound_plan_authorization.py tests/test_unreal_production_workflow.py \
  tests/test_unreal_render_workflow.py tests/test_unreal_render_contract.py tests/test_unreal_evidence_contract.py \
  tests/test_unreal_render_state_verification.py tests/test_unreal_render_production_boundary.py \
  tests/test_unreal_production_operation.py tests/test_unreal_production_planning_boundary.py -m "not integration" -q
.venv/Scripts/python.exe -m pytest $(ls tests/*.py | grep -vE "real_integration|_live_|workflow|action_runner" | tr '\n' ' ') -m "not integration" -q
```

## 5. Live UE 5.6.1 gates

### 5.1 Same-session attribution gate (the milestone's gate) — PASSED

`tests/test_unreal_mrq_attribution_real_integration.py` (**NEW**,
sha256 `06f05a3817168f32b9085a924f4776345fb917fae64c658b6d8ac325100c84aa`)

```text
.venv/Scripts/python.exe -m pytest tests/test_unreal_mrq_attribution_real_integration.py -m integration -q -s
2 passed in 26.18s          (ONE editor session, FOUR submissions, no fresh-editor workaround anywhere)
```

**Test A — two submissions, different ranges, different directories, one session:**

```text
first  job 0D13E9FD-47CA-CC67-8B6B-5BBB9E9F966C  authorized 1-2  -> exactly AtlasMrqAttributionFirst/AtlasRender_0001..0002.png
second job DC03C579-4687-BFF0-1F4C-6BA845621288  authorized 1-5  -> exactly AtlasMrqAttributionSecond/AtlasRender_0001..0005.png
first job state unchanged after the second render: True   (fresh job-addressed read; the assertion that failed before)
second job inherited zero first-job paths: asserted
exact job identity: evidence job_id == result job_id == receipt job_id, and != first job id
fresh evidence: verified True; verify_shot_continuity_completeness(fresh evidence, authorized continuity) returned the evidence
receipt coherence: receipt.matches(fresh evidence) is True
```

**Test B — the mandatory same-range case (two submissions, both authorized 1-2, different directories, one session):**

```text
third  job 2F73D3CF-4878-566B-FB36-B888E6018431 -> exactly AtlasMrqAttributionSameRangeA/AtlasRender_0001..0002.png
fourth job F9FFD0CD-4022-02E9-CEAC-419882B2C548 -> exactly AtlasMrqAttributionSameRangeB/AtlasRender_0001..0002.png
same-range job inherited zero earlier-job paths: asserted
third job state unchanged after the fourth render: asserted (fresh job-addressed read)
identity + continuity + receipt coherence: asserted
```

**Engine-log corroboration (same session, `Saved/Logs/AtlasUnrealHarness.log`):**

```text
line 1212  [22:32:58] MoviePipelineLinearExecutorBase starting 1 jobs.   (submission 1)
line 1525  [22:33:03] MoviePipelineLinearExecutorBase starting 2 jobs.   (submission 2 - queue still held job 1)
line 2090  [22:33:08] MoviePipelineLinearExecutorBase starting 3 jobs.   (submission 3 - mandatory same-range case)
line 2850  [22:33:14] MoviePipelineLinearExecutorBase starting 4 jobs.   (submission 4)
6 x "ATLAS MRQ ATTRIBUTION: discarded per-job output data for job <id>: payload job is not the registered
       Atlas job"  (1 + 2 + 3 = exactly the N-1 foreign payloads each submission produced)
6 x LogSavePackage: Moving output files for package: /Game/AtlasTest/AtlasRenderConfig  (4 writes + 2 restores)
```

The four `starting N jobs` lines are the direct proof that the fresh-session/empty-queue precondition was
genuinely removed: each later submission re-rendered every earlier job, and the guard discarded exactly those
foreign payloads. **No second failure mode surfaced**; nothing was broadened beyond Slice 1 + Slice 2.

### 5.2 Existing continuity live gate (regression, own fresh session) — PASSED

```text
.venv/Scripts/python.exe -m pytest tests/test_unreal_shot_continuity_real_integration.py -m integration -q -s
1 passed in 9.60s
job id F6CF6CCE-4016-25FE-D95B-01A318870502 | frames 1-2 | unique png files 2 | receipt 946ce5faf4b7f4fe8cd49698f263cdb55c6a8718c506e16cad86b01ed6a3d948
```

This run also proves Slice 2 holds on real engine paths: the engine's absolute artifact paths are contained by
the authorized `Saved/AtlasShotContinuityOutput` directory, so the new rule does not reject genuine evidence.
That session logged exactly one submission and zero guard discards (nothing foreign to discard).

### 5.3 Fixture and process state

```text
34be88daf66ba88b0515fece8e67570ce28ffa5db8b3d6672cee902cb39ca59f  AtlasRenderConfig.uasset
48d14bd9acf7c236f6549c2d5d0e02ff65fa40796bdfac5de5a3d2eb27839020  AtlasSequencerFixtureSequence.uasset
db15ec03c624fe1ad4f38b17e3b86f0064393111a384346f375bac30a63cdb7a  BP_AtlasTest.uasset
e25394d260b3b521d558a2331163f2695fa7f8bdaf9208dde105f639566895ce  Generated/AtlasRenderFixture.umap
```

All four byte-identical to the recorded baseline before and after both live gates. `git status --porcelain unreal/`
shows only the intended C++ source modification. Both editors were force-killed (no save-on-exit: the
render-config save count was unchanged after each kill), the pipe re-probed `PIPE_ABSENT`, and the produced
output directories are disposable; the two same-range directories were removed by the gate's own cleanup.

## 6. Non-claims and disclosed limitations

1. **The C++ guard has no deterministic execution cover** in this repository; its executable evidence is the
   same-session live gate plus source inspection. The source-level assertions pin shape, not behavior.
2. **`OnIndividualJobStarted` remains identity-blind** (`AtlasTransportServer.cpp:1369-1383`): a foreign job
   starting still writes `Status="rendering"`/`Progress` into the new job's state. Those are monitoring fields -
   they are not part of artifact ownership, the acceptance condition, or the receipt - and the authorization for
   this milestone named only `OnIndividualJobWorkFinished`, so it was left untouched and is reported here as a
   residual finding (candidate for the same guard in a later slice, with its own gate).
3. **`ShotData[0]`-only artifact collection is unchanged.** Multi-shot sequences are outside the frozen
   single-range contract; the design deliberately did not generalise them, and this implementation did not either.
4. **Movie Render Graph caveat carried from the design:** under MRG the payload `Job` is documented to point at a
   duplicated job, in which case the guard fails closed (no artifacts → no receipt). The harness uses the legacy
   primary-config pipeline, so this is a future-mode risk, not a current one.
5. **No commit, no push, no branch update** was performed by this task; the published baseline is unchanged.
6. **Rule order deviates from the design text** (containment before the frame checks), as authorized; recorded in
   §2.
