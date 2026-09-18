# Unreal Agent — MRQ Queue Hygiene / Artifact Attribution Design Review

**Date:** September 17, 2026
**Mode:** DESIGN REVIEW ONLY (READ-ONLY audit of source + tests; documentation output only)
**Published baseline:** `reconcile/unreal-autonomy-origin-20c6d10` = `6e63d1518905bba13d113c3d30766e688547fee6`
**Review status:** `CLEAR WITH MINOR CONDITIONS` (design gate verdict, relayed by the operator 2026-09-17).
**SUPERSEDED (September 17, 2026 — implementation round):** Slice 1 and Slice 2 are now IMPLEMENTED and LIVE
CLEAR — see `docs/UNREAL_MRQ_ARTIFACT_ATTRIBUTION_IMPLEMENTATION.md` and
`docs/UNREAL_MRQ_ARTIFACT_ATTRIBUTION_CLOSEOUT.md`. Slice 3 (queue consumption/deletion) was NOT implemented.
This document remains the design record; as originally recorded at review time, no production code, contract,
test, asset, or transport change had then been made and no Unreal editor had been launched.

**MRQ artifact attribution — COMPLETE + LIVE-PROVEN** (final outcome of this design): the job identity guard is
live-proven in a multi-submission single-editor session; foreign callback artifacts are discarded; PNG artifacts
must be contained within the authorized output directory; exact frame-set verification remains active; Slice 3
queue consumption remains separate and unimplemented.

**Scope declaration**

```text
do-not-touch : planning/**, tests/**, unreal/**, Blender checkout (Desktop/Atlas)
do-not-commit: nothing committed by this task
do-not-edit  : any document other than this file and the next-architecture-review/handoff status docs
ran          : source reads (C++ transport + engine MovieRenderPipeline plugin headers/sources), grep over
               tests/**, git/state inspection, and one read-only design-support probe outside the repo
               (%TEMP%/atlas_probe_attribution_hole.py) driving the REAL continuity verifier with constructed
               evidence. No pytest suite, no workflow/action-runner test, and no Unreal editor were used. Claims
               are source-level unless marked as measured (live engine logs, or that probe).
```

---

## 0. Answer to the critical architectural question

**Can artifact attribution become intrinsically tied to the exact submitted MRQ job without relying on
"fresh editor session + empty queue" as an operator precondition? — YES.**

The engine already supplies the missing identity, and the Atlas transport already stores it. The
`OnIndividualJobWorkFinished` payload (`FMoviePipelineOutputData`) carries the exact job the data belongs
to (`InOutputData.Job`, set from `UMoviePipeline::GetCurrentJob()`), and the transport already holds the
job it allocated (`FRenderJobState::Job`, assigned before the executor is started) — but the callback
loops over the payload's file paths and records them into the registry entry keyed only by the
Atlas-generated job id, never comparing the two identities.

**Smallest existing-boundary change that provides the property:** an identity guard inside the existing
`OnIndividualJobWorkFinished` lambda (compare `InOutputData.Job` against the registry entry's stored
`Job`; record nothing when they differ). No new transport operation, no protocol/argument change, no new
authority, no new abstraction, no Python contract change. One complementary evidence-boundary rule (PNG
artifact containment within the *authorized* output directory) is recommended as the fail-closed backstop
that makes any residual misattribution observable instead of silent.

---

## 1. Current implementation boundary (measured from source)

### 1.1 Transport (C++) — `unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/`

* Operation dispatch: `AtlasTransportServer.cpp:536-537` — `submit_render` → `SubmitRender`,
  `inspect_render_job` → `InspectRenderJob`. No other render operation exists; the wire protocol is
  unchanged by anything proposed here.
* `SubmitRender` (`:1163-1487`):
  * requires exactly one `entity_id` and `arguments.sequence_asset_path` (`:1174-1192`);
  * loads the level sequence and the persistent MRQ configuration asset (`:1194-1261`);
  * **reads the effective range from the job's own configuration, never from the request**
    (`:1270-1330`): requires `bUseCustomPlaybackRange`, requires a non-empty range, and derives
    `EffectiveEndFrame = CustomEndFrame - 1` (the one-shot inclusive translation, `:1306-1317`);
  * allocates the job into the editor's **current** queue:
    `Queue->AllocateNewJob(UMoviePipelineExecutorJob::StaticClass())` (`:1228-1236`);
  * mints the job identity engine-side: `JobId = FGuid::NewGuid()` (`:1332-1333`);
  * creates `FRenderJobState`, fills the job-scoped values (sequence path, effective range, output
    directory read from the job's effective `UMoviePipelineOutputSetting`, output format) (`:1335-1356`);
  * creates the executor, stores `JobState->Executor` and **`JobState->Job = Job`** (`:1358-1368`);
  * registers three lambdas on that executor — all capturing **only `JobId`** (`:1369-1443`);
  * registers the state under the job id (`:1445-1448`);
  * asynchronously renders **the whole queue**:
    `QueueSubsystem->RenderQueueWithExecutorInstance(Executor)` (`:1451-1460`).
* `InspectRenderJob` (`:1488-1559`): requires `arguments.job_id`, looks the state up in the static
  `RenderJobRegistry` (mutex-guarded), fails closed with `Render job not found: <id>` when absent, and
  serializes the job-scoped fields plus `output_files`.

`FRenderJobState` (`Public/AtlasTransportServer.h:33-63`) already carries, per job:
`JobId, OperationName, SequenceAssetPath, Status, StatusMessage, Progress, OutputDirectory, OutputFormat,
StartFrame, EndFrame, EndFrameExclusive, OutputFiles, bSuccess, bFinished, bFailed, Executor, Job`.

### 1.2 The callback that owns artifact collection (the attribution boundary)

```text
AtlasTransportServer.cpp:1385-1420
Executor->OnIndividualJobWorkFinished().AddLambda(
    [JobId](FMoviePipelineOutputData InOutputData)
    {
        ... registry.Find(JobId) ...
        (*Found)->Status = "finished"; (*Found)->bFinished = true; (*Found)->bSuccess = InOutputData.bSuccess;
        if (InOutputData.bSuccess && InOutputData.ShotData.Num() > 0)
            for (pass in InOutputData.ShotData[0].RenderPassData)
                for (FilePath in pass.Value.FilePaths)
                    (*Found)->OutputFiles.AddUnique(FilePath);
    });
```

Measured properties of this boundary:

1. The payload's own job (`InOutputData.Job`) is **never compared** with `(*Found)->Job`
   (which is already stored at `:1368`). Identity is therefore not part of the collection rule.
2. The payload's executor (`InOutputData.Executor`) is likewise never compared with
   `(*Found)->Executor` (stored at `:1367`).
3. Only `ShotData[0]` is read; a multi-shot job's remaining shots are dropped by construction.
4. `AddUnique` **unions** across every callback invocation, so a second job's file list is appended to
   the first job's state rather than replacing it.

### 1.3 Engine-side facts that make the failure mode deterministic (UE 5.6.1, engine sources)

| Fact | Anchor |
| --- | --- |
| `AllocateNewJob` **adds** the new job to `Queue->Jobs` (jobs accumulate in the queue) | `MovieRenderPipelineCore/Private/MoviePipelineQueue.cpp:30-44` |
| The executor renders the queue it is given, logging `starting %d jobs` from `GetJobs().Num()` | `MovieRenderPipelineCore/Private/MoviePipelineLinearExecutor.cpp:41` |
| Jobs are skipped only when `!IsEnabled()` or `IsConsumed()` | `MoviePipelineLinearExecutor.cpp:52-62` |
| Nothing in the headless render path sets `Consumed` (`SetConsumed` is called only from editor UI code) — a completed job stays enabled and is **re-rendered** by later submissions | `MoviePipelineQueue.h:389,403,553,556`; grep: `SetConsumed` call sites are `SMoviePipelineQueueEditor.cpp:220` and `MoviePipelineQueue.cpp:345` only |
| The per-job callback payload is built per job with `Params.Job = GetCurrentJob()` | `MovieRenderPipelineCore/Private/MoviePipeline.cpp:1621-1629` |
| `UMoviePipelinePIEExecutor::OnIndividualJobFinishedImpl` broadcasts that payload unchanged to `OnIndividualJobWorkFinished()` | `MovieRenderPipelineEditor/Private/MoviePipelinePIEExecutor.cpp:466-476` |
| `FMoviePipelineOutputData` exposes `Job` (the job the data is for) and `ShotData[]` per-shot pass→file maps | `MovieRenderPipelineCore/Public/MovieRenderPipelineDataTypes.h:1348-1361, 1396-1418` |
| Caveat: the `Job` field is documented to point at the **duplicated** job under Movie Render Graph | same header, `:1415-1418` |
| The subsystem accepts an arbitrary queue instance: `RenderQueueInstanceWithExecutorInstance(InQueue, InExecutor)` → `ActiveExecutor->Execute(InQueue)` | `MovieRenderPipelineEditor/Private/MoviePipelineQueueSubsystem.cpp:118-141` |
| `UMoviePipelineLinearExecutorBase::Queue` is a GC-visible `TObjectPtr<UMoviePipelineQueue>` | `MovieRenderPipelineCore/Public/MoviePipelineLinearExecutor.h:55` |

**Consequence.** A queue that retains *N* jobs makes one submission render *N* jobs, and the newly
created executor's per-job callback fires *N* times while every invocation resolves to the *same* registry
entry — the new job. The artifact list of the new job therefore becomes the union of every rendered job's
files.

### 1.4 Python consumers of the collected artifacts

| Layer | Anchor | Behaviour |
| --- | --- | --- |
| Envelope resolution | `planning/unreal_render_job_verifier.py:12-44` (`resolve_render_job_state`) | one rule for `{job_id: …}` and `{entity: {render_job: …}}` |
| Job verification | `unreal_render_job_verifier.py:47-150` | non-empty `job_id`; **exact** `expected_job_id` match; `failed=True` rejects; unfinished must be in `{submitted,queued,rendering}`; finished requires `success is True` and non-empty `output_files`; **existence/emptiness is checked for ABSOLUTE paths only** |
| Identity binding | `planning/unreal_plan_executor.py:289-304` (`_authorized_job_id`) + `:331`, `:341`, `:344-351` | `verify_render_job` and `inspect_render_job` are dispatched with the operation's **own authorized `job_id`** (resolved from authorized `submit_render` evidence), and are the only flag-producers for render-job evidence |
| Polling + receipt | `unreal_render_workflow.py:162-245` | polls `inspect_render_job`, fails closed on `failed=True`, runs `verify_render_job_completion` then (when a continuity is authorized) `verify_shot_continuity_completeness`, issues the receipt only from the verified evidence, persists it |
| Continuity | `planning/unreal_shot_continuity.py:142-228` (identity) and `:231-294` (completeness) | sequence path, effective inclusive range, `end_frame_exclusive`, canonicalized output directory, normalized format; then PNG-only: unique count, duplicate-frame rejection, frame-number parse, and `observed frames == set(range(start, end+1))` |
| Receipt | `planning/unreal_render_receipt.py:87-137` | issued only from verified `inspect_render_job` evidence; `receipt_digest` covers `(job_id, sequence_asset_path, evidence_digest)`; `matches()` re-issues from evidence — i.e. **the artifact list participates in the evidence digest and therefore in the receipt** |
| Production result | `unreal_production_workflow.py:36-72, 168-186` | `verified_render` re-verifies job identity + continuity identity against the final evidence and requires `receipt.matches(final_evidence)` |

### 1.5 Measured attribution boundary from the existing tests

* Deterministic coverage of the *engine* side: **none.** The transport is C++ with no unit-test harness in
  this repo; every C++ behaviour is verified live only. This is a pre-existing, disclosed limitation that
  the design must not paper over.
* Deterministic coverage of the *surface* boundary: `output_files` is a **hand-supplied fixture input** in
  15 test files / 62 occurrences, e.g. `tests/test_unreal_render_job_semantic_verification.py:45,58`
  (`_render_job(..., output_files=())`), `tests/test_unreal_render_workflow.py`,
  `tests/test_unreal_shot_continuity.py`.
* No test asserts that artifacts belong to the job that produced them. In the canonical fixture the
  declared directory is a fixed `"Saved/AtlasRenderOutput"` while the artifact files are created in
  `tmp_path` (`_artifact(tmp_path)`, `tests/test_unreal_render_job_semantic_verification.py:67-70`), and
  the continuity PNG fixtures likewise place artifacts in `tmp_path` while declaring
  `OUTPUT_DIRECTORY` (`tests/test_unreal_shot_continuity.py:737-830`). The **path-ownership relation is
  therefore neither modelled nor tested** — exactly the relation that the engine defect violates.
* Job-identity coverage that DOES exist and must not regress: `test_unreal_render_job_semantic_verification.py`
  RJ1–RJ8 (40 of the module's 47 collected cases: exact/resolved identity binding, wrong-identity fail-closed, forged completion,
  blank/missing expectation rejection, active-status acceptance, receipt relationships, unchanged
  argument key sets) and the continuity module's recovery/authorization separation tests
  (`tests/test_unreal_shot_continuity.py:943-1020`).

---

## 2. Observed failure mode (measured on this machine, from the engine's own logs)

### 2.1 Queue accumulation is real, serial, and unmitigated

From the archived session `unreal/AtlasUnrealHarness/Saved/Logs/AtlasUnrealHarness-backup-2026.09.17-02.08.35.log`
(one editor session, three submissions, line numbers exact):

```text
1207  [02:07:02:359] ATLAS MRQ EFFECTIVE CONFIG: 640x360 frames=1-2 output=.../Saved/AtlasShotContinuityOutput
1208  [02:07:02:359] MoviePipelineLinearExecutorBase starting 1 jobs.
1541  [02:07:26:559] ATLAS MRQ EFFECTIVE CONFIG: 640x360 frames=1-2 output=.../Saved/AtlasShotContinuityProbe
1542  [02:07:26:559] MoviePipelineLinearExecutorBase starting 2 jobs.
2057  [02:08:17:809] ATLAS MRQ EFFECTIVE CONFIG: 640x360 frames=1-5 output=.../Saved/AtlasShotContinuityProbe
2058  [02:08:17:809] MoviePipelineLinearExecutorBase starting 3 jobs.
```

The third submission re-rendered the previous two jobs before rendering its own, and the per-job callback
for the new job observed all three jobs' outputs.

### 2.2 The resulting misattribution (measured live in the previous milestone)

* `observed unique_output_files=24` for an authorized `1-2` job: the 24 artifacts of an earlier
  (1–24) job were attributed to the new 2-frame job.
* A brand-new job's `output_files` pointed at an **earlier job's output directory** while the new job's own
  directory was still empty.

### 2.3 Why nothing caught it

* The count/frame-set rule caught the 24-vs-2 case, but only because the two ranges differed.
* **Symmetric case that would NOT be caught today:** two submissions in one session with the *same*
  authorized range (and for the recorded gate, the same authorized directory). The union of two
  identical frame sets equals the authorized frame set, both jobs report the same
  `sequence_asset_path`/range/directory/format, and every existing verifier passes — with artifacts that
  may be entirely the earlier job's. Under the frozen rules this is a **false accept**, not a false
  refusal, and the polluted artifact list is hashed into `evidence_digest`/`receipt_digest`
  (`unreal_render_receipt.py:118,127-137`), so the receipt would attest to artifacts the authorized job
  did not produce.

  **Measured, not argued** (design-support probe, no engine, no mutation): the real verifier

  ```text
  authorized inclusive frames : 1 2
  authorized directory        : Saved/AtlasShotContinuityOutput
  ACCEPTED  : artifacts in the authorized directory (frames 1-2)
  ACCEPTED  : artifacts in a FOREIGN directory, same frames 1-2
  ```

  i.e. `verify_shot_continuity_completeness` accepts an artifact list whose paths live outside the
  authorized output directory when the frame set matches. The containment rule of §5.2 closes exactly this
  acceptance path.
* The current mitigation is procedural: one submission per fresh editor session. That is an **operator
  precondition**, not a property of the system.

### 2.4 Fresh-session runs are clean and remain the baseline to preserve

Three fresh sessions at the publication gate (this machine, current logs), queue empty at session start
(0 `starting` lines), one submission each:

```text
1 passed in 6.60s  job 4D92AB93-4DE4-6A98-F40C-EDA1B3B7902D  frames 1-2  unique png 2  starting 1 jobs  [800,2400)
diag 1-5           job 8E0DFBD8-4F90-7DED-4EFF-D0A73E09E701  frames 1-5  unique files 5                [800,4800)
1 passed in 9.25s  job 3B6EEF00-450E-3DBF-C2CB-2B91AE2CBB04  frames 1-2  unique png 2  starting 1 jobs  [800,2400)
```

---

## 3. Trust and evidence implications

1. **Provenance is asserted, not established.** `output_files` is the engine's claim about what was
   written. The claim is currently correct only while the queue contains exactly the submitted job.
2. **Pollution is absorbed into the attested artifact.** The artifact list is part of `UnrealEvidence`
   and therefore of `evidence_digest`; a receipt issued from polluted evidence is internally consistent
   and verifies against its own evidence (`receipt.matches`), so no downstream check detects it.
3. **The blast radius is bounded by the frame-set rule, in one direction only.** Range-mismatched
   pollution fails closed; range-identical pollution passes.
4. **This is an evidence-fidelity defect, not an authority defect.** Job identity is engine-minted
   (`FGuid`, `:1332`) and authorization-bound at the executor (`unreal_plan_executor.py:289-304`); no
   model-derived or caller-derived value is involved, and no second authority is needed to fix it.
5. **The existing architecture already fails closed on absence.** Missing `output_files`, unparsable frame
   numbers, wrong counts, wrong frames, wrong directory/format/range/identity all reject before a receipt
   is issued. The gap is *substitution* of one job's artifacts for another's, not missing evidence.
6. **Related fidelity observations (reported, out of scope for this design):**
   * `JobState->OutputFormat` is a hardcoded literal `"png"` (`AtlasTransportServer.cpp:1355`), so the
     continuity format comparison can never fail on this engine build. It is a constant echo, not a
     measurement of the effective configuration.
   * `output_files` are never required to live in the job's own `OutputDirectory`; the directory is
     verified as a *job-state field* only.
   * `InspectRenderJob` reads session-local in-memory state (`RenderJobRegistry`): after an editor restart
     a previously issued job id fails closed with `Render job not found` (no cross-session persistence).

---

## 4. Candidate approaches

All candidates preserve: single continuity authority, inclusive Atlas semantics, one-shot MRQ boundary
translation, evidence-bound receipt, exact job-ID binding, fail-closed recovery, Named Pipe protocol.

### A. Queue hygiene — explicit removal/consumption of completed jobs

* **A1 (non-selective):** clear or delete *all* queue jobs before/after submission.
* **A2 (Atlas-owned only):** after completion, delete or mark consumed **only the job this transport
  allocated** (`FRenderJobState::Job`).

Evaluation:
* A2 is well-supported by the engine (`DeleteJob` already used on failure paths `:1245,1257,1280,1294,1301,1311`;
  `SetConsumed` skipped by the executor at `MoviePipelineLinearExecutor.cpp:58`) and removes real waste:
  the measured re-render of two previous jobs per submission, plus duplicate artifact writes into previous
  directories.
* **A alone cannot establish attribution.** Any other job present in the queue — a human's job, another
  Atlas job not yet consumed, or a job added between submission and render — still renders and still writes
  its file paths into the new job's state, because the collection rule remains identity-blind.
* A1 is rejected outright: it destroys queue entries Atlas did not create (a destructive mutation of
  shared editor state, and a fail-open hazard if it runs on a timeout path).
* A2 is retained **only as an optional, separately-gated efficiency/hygiene complement**, never as the
  correctness mechanism.

### B. Executor-owned artifact collection keyed to exact job identity (RECOMMENDED, minimal)

Change the existing `OnIndividualJobWorkFinished` lambda so that it records artifacts **only** for the job
the payload belongs to:

```text
[JobId](FMoviePipelineOutputData InOutputData)
    Found = Registry.Find(JobId); if (!Found || !Found->IsValid()) return;
    StoredJob = (*Found)->Job.Get();
    if (!StoredJob || InOutputData.Job != StoredJob) return;   // provenance guard: record nothing
    ... existing body (single ShotData[0] pass loop unchanged) ...
```

Properties:
* Uses only data the engine already provides (`InOutputData.Job`, `MoviePipeline.cpp:1621-1629`) and an
  identity the transport already holds (`JobState->Job`, `:1368`). No new API, argument, operation,
  response field, authority, or abstraction.
* Independent of the queue's contents: whether the executor renders 1 or N jobs, only the job's own
  payload contributes.
* Failure direction is fail-closed: if the identity never matches (e.g. the MRG duplicated-job caveat),
  `output_files` stays empty, `verify_render_job_completion` raises `render job completed successfully but
  produced no output_files`, the workflow raises, and no receipt is issued.
* Note (deliberately not part of B): `ShotData[0]`-only iteration remains a faithful-to-today choice;
  multi-shot sequences are outside the frozen single-range contract and are **not** silently generalised
  here.

### C. Engine-side per-job output attribution beyond the callback payload

* **C1 — derive artifacts from the job's effective output directory + file-name format + frame range**
  (i.e. Atlas recomputes what MRQ would have written). Rejected: it duplicates the engine's naming rules in
  Atlas (a second artifact-identity authority), can fabricate paths that were never written, and cannot
  disambiguate a directory shared by two jobs.
* **C2 — filesystem enumeration after completion** (list the directory, keep files whose mtime follows the
  submission). Rejected: time/`mtime` correlation is not identity, is racy under serial re-renders, and
  turns Atlas into an artifact-discovery authority — the same class of shortcut the architecture forbids
  for entities ("no entity discovery/cache"). It would also change the evidence model from "the engine
  reports what it wrote" to "Atlas guesses what exists".
* **C3 — the engine's own per-job data, used correctly** is precisely candidate B; the engine already
  attributes per job, so "C" reduces to B and needs no engine modification.

### D. Other minimal designs supported by the existing architecture

* **D1 — authorize-artifact containment (RECOMMENDED as the fail-closed backstop, separate slice).**
  In the existing PNG completeness verifier (`unreal_shot_continuity.py:231-294`), require every observed
  artifact path to resolve **inside the authorized output directory** (canonicalized with the existing
  `canonicalize_output_directory`, `unreal_render_contract.py:50-60`). PNG-only, mirroring the frozen
  scoping of the frame rule. This is defensive verification, not attribution: it makes any residual
  cross-job substitution fail closed, including the same-range case of §2.3.
* **D2 — additive queue observability** (`queue_job_count` on the existing `inspect_render_state`
  response). Converts the operator precondition into a *detectable* condition, but establishes no
  attribution property; adds surface. Deferred (not rejected): may be worth having later if a gate wants
  to attest "the queue was clean at submission".
* **D3 — render into an Atlas-owned private queue instance**
  (`QueueSubsystem->RenderQueueInstanceWithExecutorInstance(PrivateQueue, Executor)`,
  `MoviePipelineQueueSubsystem.cpp:118-141`). Structurally the strongest isolation: the executor's queue
  would contain exactly one job, so accumulation and pollution disappear and the editor's queue is left
  untouched. Not selected now: the behaviour is unproven (transient-queue lifetime is only *probably* safe
  because `LinearExecutor::Queue` is GC-visible; the MRQ UI panel would no longer show the render; the PIE
  executor's map-validity/unsaved-level checks would run against a non-current queue), and it changes where
  Atlas renders rather than how it attributes — a larger blast radius than B. **Requires a spike before it
  could be considered**, deferred.
* **D4 — temporarily disable non-owned queue jobs around submission and restore afterwards.** Rejected:
  mutates state Atlas does not own and can leave a user's queue disabled after a crash, timeout, or forced
  kill (a fail-open side effect). Exactly the shape of side effect the frozen constraints exist to prevent.

### Candidate comparison

| Candidate | Establishes attribution | New authority/primitive | Blast radius | Failure direction | Verdict |
| --- | --- | --- | --- | --- | --- |
| A1 clear whole queue | no | destructive queue mutation | high | fail-open | rejected |
| A2 consume/delete Atlas's own job | no (efficiency only) | engine queue mutation scoped to owned job | low-medium | neutral | optional complement, separately gated |
| B identity guard in the callback | **yes** | none | one lambda in the transport C++ | fail-closed | **recommended (primary)** |
| C1/C2 reconstruct or discover artifacts | no (fabricates/infers) | second artifact authority | medium-high | could fail-open | rejected |
| D1 authorized-directory containment (PNG) | no (detects substitution) | none | one verifier + fixtures | fail-closed | **recommended (backstop)** |
| D2 queue observability | no | additive response field | low | neutral | deferred |
| D3 Atlas-owned private queue | yes (by isolation) | new rendering surface, unproven | medium-high | unknown | deferred pending spike |
| D4 disable non-owned jobs | no | mutates non-owned state | medium | fail-open | rejected |

---

## 5. Recommended architecture (design only — nothing implemented)

**Attribution correctness is engine-side and identity-based; substitution detection is Atlas-side and
authorized-value-based. Both stay inside existing boundaries.**

### 5.1 Slice 1 (required) — provenance guard at the existing callback

* One guard in `AtlasTransportServer.cpp`'s `OnIndividualJobWorkFinished` lambda (§4 B). No signature,
  schema, protocol, operation, or response change. Rebuild of `UnrealEditor-AtlasUnrealTransport.dll`
  required.
* Invariants added: artifacts are recorded only for the exact job the payload belongs to; a mismatched or
  unresolvable job identity records nothing and leaves the job in its last reported state (fail-closed
  through the existing verifier).
* Optional additive log line on a rejected payload (Atlas registry job id + payload job sequence path),
  logging only — never evidence.

### 5.2 Slice 2 (required) — PNG artifact containment against the *authorized* directory

* In `verify_shot_continuity_completeness`, after count and duplicate checks and before frame-set
  equality: every artifact must canonicalize inside the **authorized** `output_directory`.
* Rule order frozen as: **count → frame-number/duplicate → containment → frame-set equality**, so a
  provenance failure is named as such rather than surfacing as a confusing frame-set mismatch.
* Scoped to PNG only, exactly like the frame rule; other formats keep existence/non-empty validation.
* No new argument, no authorization change, no new authority: the expectation is the already-authorized
  continuity value.

### 5.3 Slice 3 (optional, separately gated) — Atlas-owned job consumption

* After a job reaches a terminal state, mark **that** job consumed (or delete it) so later submissions in
  the same session stop re-rendering it (`A2`). Requires its own evidence (does the MRQ panel behave; does
  consumption interfere with a still-open poll) and its own gate. Not required for correctness.

### 5.4 Explicitly NOT part of this milestone

Queue clearing, transport/protocol changes, new operations or response fields, new persistence for the
render-job registry, artifact discovery/scanning, multi-shot artifact collection, distributed rendering,
receipt shape changes, `continuity_digest` provenance, and any change to shot continuity semantics.

---

## 6. Deterministic test strategy

**Owned limitation, stated up front:** the transport C++ has no deterministic harness in this repo. Slice 1
is therefore verified by (a) the live gate of §7, (b) source inspection in the independent review, and
(c) Slice 2, which makes a Slice-1 regression fail closed at the evidence boundary instead of silently
passing. No deterministic test in this milestone may claim to exercise Slice 1.

Slice 2 matrix (names frozen; each test asserts through the public verifier, not internals):

| ID | Case | Expected |
| --- | --- | --- |
| T1 | full authorized frame set, all artifacts inside the authorized directory | passes (returns evidence unchanged) |
| T2 | full authorized frame set, artifacts in a **different** directory | raises, naming the offending path and the authorized directory |
| T3 | mixed: some inside, some outside | raises on the first offending path |
| T4 | authorized directory declared relative, artifacts absolute inside it (and the reverse) | passes — canonicalization equivalence |
| T5 | authorized directory is a prefix-adjacent sibling (`.../AtlasShotContinuityOutput2`) | raises — no `startswith` false friend (path-segment boundary required) |
| T6 | non-PNG authorized format, artifacts elsewhere | passes — containment is PNG-scoped by design |
| T7 | missing frame inside the authorized directory | raises with the existing frame-set error (rule ordering) |
| T8 | duplicate frame numbers in distinct directories | raises with the existing duplicate-frame error (rule ordering) |
| N0 | **hole proof (RED first, frozen baseline):** the measured pollution shape — authorized `1-2`, artifacts from an earlier directory whose frames are also `{1,2}` — is asserted to **pass today** (`xfail`-style documented expectation or a baseline run recorded in the review) and to **fail** once T2's rule lands | documents the defect the slice closes |
| N1 | measured live pollution shape (24 files from an earlier directory for an authorized 1–2) | fails, and fails on the count guard first |
| N2 | `output_files` empty / non-list / non-string entries | unchanged rejections |

Suite-level guards (G):

* G1 the authorized argument key sets for `submit_render` / `inspect_render_job` / `verify_render_job`
  are unchanged (`unreal_tool_schema.py:37-39`; existing `test_rj8_render_job_allowed_key_sets_are_unchanged`).
* G2 the receipt contract is unchanged (`job_id, sequence_asset_path, evidence_digest`; `receipt_digest`
  derivation untouched; `test_unreal_render_receipt*.py` unmodified).
* G3 shot continuity's identity/boundary rules are unmodified (inclusive semantics, single translation,
  `end_frame_exclusive`); only the completeness verifier gains the containment rule.
* G4 `verify_render_job_completion` stays continuity-free and artifact-shape-only.
* G5 fail-closed recovery stays: `test_render_submission_failure_is_not_retried`,
  `test_recovery_does_not_reuse_the_production_continuity_authorization`,
  `test_recovery_authorization_is_separate_from_the_production_continuity` unmodified and green.
* G6 blast-radius sweep on the implementation tree, reported with exact counts. (Measured at publication:
  consolidated affected Unreal suite 291 passed/2 skipped; canonical controller/host 160 passed/2
  deselected; broad scoped sweep 1123 passed/6 skipped.)

**Fixture-alignment cost, measured (must be declared, not discovered mid-slice):** Slice 2 requires the
PNG fixtures to place artifacts inside their declared directory. `output_files` appears in 15 files/62
occurrences; the two files that build PNG artifact evidence against a fixed declared directory are
`tests/test_unreal_shot_continuity.py` (9 occurrences) and
`tests/test_unreal_render_job_semantic_verification.py` (15 occurrences, whose `_artifact(tmp_path)`
helper writes into a directory that is not the declared `Saved/AtlasRenderOutput`). Alignment is a
classified **test-fixture update (intent unchanged)**, the same classification used when the continuity
milestone's fixtures were updated to declare the production sequence identity — never a weakened gate. Any
fixture whose artifact list is intentionally foreign (T2/N1) must keep a deliberate out-of-directory path.

---

## 7. Live UE gate requirements (for the implementation milestone, not run here)

Reuse the proven procedure: `MSYS_NO_PATHCONV=1 UnrealEditor-Cmd.exe <uproject> /Game/AtlasTest/Generated/AtlasRenderFixture`,
rotation-safe readiness (poll-time log age + the `Atlas Unreal fixtures ready in world 'AtlasRenderFixture'` line + pipe probe), fixture hashes before/after,
forced kill, no save-on-exit.

* **Gate L1 — accumulation-independent attribution (the milestone's whole point).** ONE editor session,
  **two** submissions, **no** queue hygiene between them:
  1. submission A: authorized `1-2`, directory `Saved/AtlasAttributionA`;
  2. submission B: authorized `1-5`, directory `Saved/AtlasAttributionB`;
  3. assert B's final evidence `output_files` frame set is exactly `{1..5}` **and** every path is inside
     `AtlasAttributionB` (A's `AtlasRender_0001/0002.png` must not appear);
  4. assert A's registry state is unchanged after B's render (its `output_files` still exactly its own two
     files) — the assertion that fails today;
  5. assert the engine log shows `starting 2 jobs` for submission B (proof the precondition was really
     removed) while both jobs' evidence stays exact.
* **Gate L2 — same-range symmetric case.** One session, two submissions with the **same** authorized range
  and the **same** directory: B's evidence must equal the authorized frame set and containment must hold;
  document that the artifact *content* is indistinguishable and that the property being proven is
  job-scoped provenance + containment, not byte-level authorship.
* **Gate L3 — regression of the proven path.** The existing single-submission fresh-session gate
  (`tests/test_unreal_shot_continuity_real_integration.py`, authorized 1–2, 2 PNGs, exact identity/range/
  directory/format, exact job id, receipt issued+persisted, fixtures restored) must stay green in its own
  fresh session, plus the full-range `1-5` diagnostic (5 artifacts) in a further fresh session.
* **Gate L4 — fail-closed check.** With the DLL carrying Slice 1, drive a submission whose payload is
  rejected by the guard is not directly constructible from outside; therefore assert the *observable*
  fail-closed behaviour instead: a job whose artifacts are never attributed (simulated deterministically in
  T-suite; live only if a natural case appears) yields no receipt. Do **not** invent an engine-side fault
  injection for this.
* Requirements: DLL rebuilt from the reviewed source and its build time recorded; one fresh editor session
  per live point unless the point's purpose is same-session accumulation; the tracked fixture hashes
  (AtlasRenderConfig.uasset, AtlasSequencerFixtureSequence.uasset, BP_AtlasTest.uasset,
  AtlasRenderFixture.umap) recorded before/after; probe output directories removed; editor process killed
  and the pipe re-probed `PIPE_ABSENT`.
* Explicit non-claim to record in the gate report: the C++ guard is not deterministically covered; the
  live gate plus Slice 2's backstop are the only executable evidence for it.

---

## 8. Recovery and fail-closed implications

1. **No new authority, no new recovery path.** The guard changes which observations carry artifacts, not
   who may submit or verify. Recovery still requires a fresh exact authorization
   (`unreal_production_workflow.py:100-190`; `unreal_plan_executor.py:355-358`).
2. **No automatic retry.** A failed or empty attribution becomes `UnrealRenderWorkflowError` → production
   workflow failure → the existing fail-closed recovery semantics; `submit_render` is never re-issued
   inside the workflow (pinned by `test_render_submission_failure_is_not_retried`).
3. **Guard-rejects-everything is fail-closed, and visibly so.** If `InOutputData.Job` never matches
   (MRG caveat, engine change, or an Atlas regression), the job never reports artifacts, the poll times out
   or rejects on `no output_files`, and no receipt is written. The failure is loud, not silent.
4. **Containment failures are evidence rejections, not mutations.** A rejected evidence object cannot be
   used to issue a receipt, and the executor still records the failure in its ledger.
5. **Queue hygiene (Slice 3), if ever added, must not create a fail-open path.** It may only touch the job
   this transport allocated, must be idempotent, and must not run on a timeout/exception path in a way
   that could leave another queue entry altered.
6. **Residual risk to keep operational until Slice 1+2 are live-proven:** the fresh-editor-session +
   empty-queue procedure remains the required guard for any live continuity gate, and any live run that
   cannot prove a clean queue must be treated as unattributable evidence. This is the invariant that
   remains operational if the design is deferred or fails its gate.

---

## 9. Explicit frozen invariants

Architectural decisions carried forward (unchanged by this design):

1. `UnrealShotContinuity` remains the single continuity authority; no second continuity verifier
   (`unreal_render_continuity.py` stays deleted).
2. Atlas frame semantics remain **inclusive**; PNG completeness is `end_frame - start_frame + 1` with exact
   frame-set equality.
3. The inclusive→half-open translation happens **exactly once**, at the MRQ write boundary
   (`CustomEndFrame = Atlas end + 1`), with `end_frame_exclusive` as the engine-boundary diagnostic.
4. Production spec → production plan → authorization binding of sequence identity
   (`continuity_digest`) is unchanged.
5. `verify_render_job_completion` stays continuity-free; `resolve_render_job_state` stays the single
   envelope rule.
6. Exact job-ID binding stays mandatory on `verify_render_job` and `inspect_render_job`.
7. The receipt stays the existing evidence-bound shape (`job_id, sequence_asset_path, evidence_digest`);
   no receipt expansion and no `continuity_digest` provenance field.
8. No new transport primitive, no Named Pipe protocol/argument change, no second authorization authority,
   no model-derived authority, no entity discovery/cache, no generic workflow engine, no distributed
   rendering.
9. Recovery stays fail-closed with no automatic mutation retry.

New invariants this design would freeze (on approval):

10. **Artifact provenance is job-scoped by engine identity**: an artifact may only be recorded for the job
    the engine attributes it to; no identity match means *no* artifacts, never guessed artifacts.
11. **Observed PNG artifacts must lie within the authorized output directory** (path-segment containment
    after canonicalization), verified against the authorized continuity value, never against the observed
    directory field.
12. **Queue hygiene, if ever introduced, is restricted to Atlas-owned jobs** and can never delete, disable,
    or consume an entry Atlas did not allocate.
13. **No artifact discovery**: Atlas never lists, scans, or reconstructs the filesystem to decide what was
    rendered; the engine reports artifacts, Atlas verifies them.
14. **The fresh-session/empty-queue procedure remains mandatory** for any live gate until Gates L1–L3 pass
    on a released build, and the operator precondition is recorded as such wherever it is still required.

**Status of the new invariants after the implementation round (2026-09-17):** invariants 10 and 11 are in force
in code (Slice 1 guard; Slice 2 containment). Invariant 11's rule ORDER deviates from §5.2 by explicit
authorization: containment now runs BEFORE the frame-number/frame-set checks. Invariant 13 (no artifact
discovery) is respected by the implementation. Invariant 12 constrains Slice 3, which was not implemented.
Gate outcomes: L1 and L2 passed in ONE editor session
(`tests/test_unreal_mrq_attribution_real_integration.py`, 2 passed in 26.18 s, engine log
`starting 1 -> 2 -> 3 -> 4 jobs`, 6 guard discards) and L3 passed in its own session (1 passed in 9.60 s), so the
operator precondition is no longer load-bearing for attribution — it remains required practice for unattributable
pasts, not for correctness.

---

## 10. Review request

This document is a design proposal, not a cleared design. Requested independent review, blind to my
conclusions, against the audit list in the task (MRQ job lifecycle; `SubmitRender` identity creation; queue
state before/after submission; callback/event ownership; `InspectRenderJob` construction; job-ID binding and
authorization; artifact collection and normalization; receipt/evidence relations; interaction with shot
continuity; recovery under uncertain attribution), with the expected verdict token
(`CLEAR` / `CLEAR WITH MINOR FINDINGS` / `BLOCKED`) and a closure map per finding. Nothing is implemented
until that gate returns CLEAR or CLEAR WITH MINOR FINDINGS.
