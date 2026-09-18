# Unreal Agent — MRQ Queue Isolation Design Review

**Date:** September 17, 2026
**Mode:** READ-ONLY ARCHITECTURE / DESIGN GATE — source audit + previously recorded measurements. No code, no
tests, no editor run, no live gate, no workflow/action-runner execution.
**Published baseline:** `reconcile/unreal-autonomy-origin-20c6d10` @
`4b61d8f48ee773563149f74230423ca12bbe781b` (MRQ artifact attribution Slice 1 + Slice 2 + Slice D, and MRQ
submission outcome propagation, are all COMPLETE + LIVE-PROVEN).
**Question:** is an Atlas-owned private Movie Render Queue instance worth the additional lifecycle surface
compared with the now-correct shared queue semantics?
**Verdict:** **CLEAR WITH MINOR FINDINGS** (§12). Nothing is authorized by this document.

```text
Explicitly NOT done here: no production code, no tests, no editor session, no live gate, no queue mutation, no
private queue creation, no protocol/authorization/receipt/job-identity/continuity change, no Blender change.
Nothing committed.
```

---

## 0. The decision rule

Isolation should be adopted only if it removes a cost that is **not** removable inside the current semantics, and
only if the lifecycle surface it adds is smaller than that cost. So the review classifies every remaining queue
cost as exactly one of: **correctness risk**, **availability risk**, **efficiency cost**,
**operator-visibility cost**, or **hygiene**, and then asks what each candidate removes.

## 1. Where Atlas touches the queue today (audited surface)

```text
Atlas queue interactions live in exactly ONE function: FAtlasTransportServer::SubmitRender
  AtlasTransportServer.cpp:1216   UMoviePipelineQueue* Queue=QueueSubsystem->GetQueue();
  AtlasTransportServer.cpp:1229   Queue->AllocateNewJob(UMoviePipelineExecutorJob::StaticClass())
  AtlasTransportServer.cpp:1238   Job->SetSequence(FSoftObjectPath(SequenceAssetPath));
  AtlasTransportServer.cpp:1250   Job->Map = /Game/AtlasTest/Generated/AtlasRenderFixture  (explicit map)
  AtlasTransportServer.cpp:1261   Job->SetConfiguration(AtlasConfig)   -> Configuration->CopyFrom(preset snapshot)
  AtlasTransportServer.cpp:1245-1363  6 x Queue->DeleteJob(Job)  (pre-existing failure-cleanup paths)
  AtlasTransportServer.cpp:1525   QueueSubsystem->RenderQueueWithExecutorInstance(Executor)  (1-arg wrapper)
  AtlasTransportServer.cpp:1528   QueueSubsystem->GetActiveExecutor()  (Slice E identity observation)
Everything else about a render job is queue-independent:
  - the job's atlas identity is an engine-minted FGuid returned by the transport, and the registry is the only
    Atlas-side job state (Public/AtlasTransportServer.h:94-95, a static TMap on a non-UObject class)
  - inspect_render_job reads the registry only (AtlasTransportServer.cpp:1536-1610); it never consults a queue
  - receipts are issued from verified terminal evidence (planning/unreal_render_workflow.py:187-231)
  - ConfigureRender edits the shared PRESET ASSET, not a queue job (AtlasTransportServer.cpp:1097-1162)
```

Two structural facts make this migration cheaper than it looks, and one makes it more expensive than it looks:

```text
cheap      the job is built explicitly from the request (AllocateNewJob + SetSequence + Map + SetConfiguration),
           so it does not depend on the editor's queue contents or the current world. The mechanism change is
           effectively: allocate on OUR queue, then call the 2-argument
           RenderQueueInstanceWithExecutorInstance(InQueue, InExecutor) instead of the 1-arg wrapper that passes
           GetQueue() (MoviePipelineQueueSubsystem.cpp:143-145). Slice E's identity observation is unchanged.
expensive  FAtlasTransportServer is a plain FRunnable C++ class (Public/AtlasTransportServer.h:13), NOT a UObject.
           There is no UPROPERTY that can own an Atlas-created UMoviePipelineQueue, so ownership would have to be
           TStrongObjectPtr / AddToRoot held in a static, with an explicit release on every path - a new
           lifetime obligation and leak surface on the one object Atlas would newly own.
```

## 2. Measured cost inventory

All numbers below come from the three live gates already recorded in this repository.

```text
amplification   every Accepted submission renders EVERY job retained in the editor queue.
                Slice D session: 4 accepted submissions -> "starting 1, 2, 3, 4 jobs"      = 10 job-renders (2.5x)
                Slice E session: 3 accepted submissions -> "starting 1, 3, 4 jobs"         =  8 job-renders (2.7x)
                the 1-24 job was re-rendered in every later pass (48 extra frames), and the
                rejected submission's orphan job added 2 more frames to each later pass
                formula: pass k renders sum(retained jobs); extra per submission ~= (k-1) * mean_frames
orphan job      a rejected submission leaves its allocated job in the queue (queue mutation frozen):
                measured 1 orphan job + 2 orphan PNGs in the rejected job's configured directory,
                discarded by Slice 1 (6 discards in that session), no receipt, not in any accepted evidence
failure         a queue-mate fatal error fails the WHOLE executor pass: MoviePipelineExecutor.h:216-234
coupling        broadcasts !bAnyJobHadFatalError, and Atlas's OnExecutorFinished lambda
(and            (AtlasTransportServer.cpp:1470-1491) writes bFinished/bFailed/Status/StatusMessage for OUR job
misdiagnosis)   from that pass-scoped flag. A valid Atlas render can therefore be reported as
                "Render executor finished with failure" because a foreign or orphan job failed. This is
                fail-closed (no receipt) but it is an availability loss plus a misleading diagnosis.
UI              the MRQ queue panel, the queue editor, the graph config panels and the active-render settings tab
                are all bound to Subsystem->GetQueue() (e.g.
                MovieRenderPipelineEditor/Private/Graph/SMovieGraphActiveRenderSettingsTabContent.cpp:324,688;
                Widgets/SMoviePipelineQueuePanel.cpp:97-99,324,518; Widgets/SMoviePipelineQueueEditor.cpp:529,2036-2038;
                Widgets/Graph/SMovieGraphConfigPanel.cpp:87-89) - i.e. the operator sees the shared queue,
                which is where an Atlas job currently appears.
Slice 1/D       6-15 "ATLAS MRQ ATTRIBUTION: discarded" lines per session: the identity guards are actively
                discarding foreign payloads, which is the proof that they, and not the queue layout, are what
                protects provenance today.
```

## 3. Private queue (candidate B) — the seventeen questions

Engine precedent: Epic's own Quick Render builds a transient private queue, instantiates the same
`UMoviePipelinePIEExecutor`, registers the same three callbacks and calls the two-argument subsystem entry point
(`MovieRenderPipelineEditor/Private/Graph/MovieGraphQuickRender.cpp:198-226`, queue created at `:315` via
`NewObject<UMoviePipelineQueue>(GetTransientPackage())`, released at `:364-366`), with the queue held by
`UPROPERTY(Transient) TObjectPtr<UMoviePipelineQueue> TemporaryQueue` on a UObject
(`Public/Graph/MovieGraphQuickRender.h:170-175`). The mechanism is therefore engine-supported and precedented.

```text
1  ownership            Atlas would own the queue object. QuickRender can rely on a UPROPERTY because it is a
                        UObject; FAtlasTransportServer is not, so Atlas must root it explicitly
                        (TStrongObjectPtr member of a static // AddToRoot) and release it explicitly.
2  queue lifetime       transient, unsaved (the editor queue is UPROPERTY(Transient, Instanced) on the subsystem,
                        MoviePipelineQueueSubsystem.h:109-110; queue persistence is only the explicit SaveQueue).
                        Two designs: (a) one queue per submission -> bounded to a single job, (b) one queue per
                        session -> identical accumulation to today, minus visibility.
3  executor lifetime    the subsystem holds the executor in ActiveExecutor for the pass
                        (MoviePipelineQueueSubsystem.cpp:141-147) and nulls it in OnExecutorFinished; after that
                        the executor is unreferenced and GC-able. Atlas holds only TWeakObjectPtr (header:53-54),
                        which is exactly why Slice D/Slice 1 fail closed on an expired pointer.
4  GC safety            while a render runs, the executor's own UPROPERTY(Transient) TObjectPtr<UMoviePipelineQueue>
                        Queue (MoviePipelineLinearExecutor.h:54-55) keeps the private queue alive. Between
                        submissions nothing does, unless Atlas roots it - and a rooted queue that is never
                        released is a permanent leak (new failure surface, see also Q15).
5  sequencing           configure (preset asset, unchanged) -> allocate job on the private queue ->
                        RenderQueueInstanceWithExecutorInstance(PrivateQueue, Executor) -> immediate
                        GetActiveExecutor() identity observation, all inside the same game-thread request task
                        (unchanged Slice E contract). The only signature change is the 2-argument call.
6  editor restart       the queue and its jobs are transient and vanish with the process, exactly as today; the
                        registry is process-lifetime too, so an editor restart loses both consistently.
7  transport restart    the transport server is an in-editor FRunnable (module-owned). Restarting the pipe
                        server does NOT destroy the editor, so a rooted private queue would survive a client
                        disconnect and could hold stale jobs across reconnects - a state that today's design
                        does not have (today the queue belongs to the editor's subsystem and is inspectable by
                        the operator). Any such queue must be explicitly reset on transport start/stop.
8  accepted lookup      unchanged: inspect_render_job reads the registry by exact job id; the queue is never
                        consulted for evidence (AtlasTransportServer.cpp:1536-1610).
9  callback ownership   callbacks are registered per executor instance, so with a private queue the payload set
                        is exactly Atlas's own jobs. Slice 1's artifact guard and Slice D's start guard become
                        backstops rather than the load-bearing protection - they must stay regardless.
10 accumulation inside  per-submission queue: one job, no accumulation, no amplification, no orphan survival.
   the private queue    session-reused private queue: accumulation and amplification return in full, and they are
                        now INVISIBLE to the operator (strictly worse than today).
11 failed / rejected    with a per-submission queue the abandoned job dies with the queue: no orphan re-render,
                        no orphan PNGs in a directory Atlas no longer tracks. This is the cleanest measurable win.
12 visibility           Atlas renders disappear from the MRQ queue panel and from the active-render settings tab
                        (both read Subsystem->GetQueue(), anchors in §2). The operator can still see the
                        editor's own jobs, and the transport log still records the submission, but the render
                        itself is no longer inspectable through the MRQ UI. This is a real cost.
13 MRQ UI interaction   the UI does not break (QuickRender proves a private queue coexists with it), but it shows
                        a DIFFERENT queue than the one being rendered: jobs listed as "queued and not rendering"
                        may be exactly the jobs the operator believes are running, and vice versa. Cancellation
                        from the UI would not reach Atlas's executor; a cancellation contract would have to be
                        established (open question for any future gate).
14 receipts / evidence  unchanged by construction: job identity stays engine-minted per job, the registry stays
   / job identity       the only Atlas-side job state, verification stays evidence-based, receipts keep the same
                        fields and the same "fresh verified terminal evidence only" gate. Nothing in the receipt
                        path reads a queue.
15 recovery             unchanged contract (fail closed, no automatic retry, reassess from fresh evidence and
                        require a new authorization). New obligation: release the rooted queue on the failure
                        path too - a leak there would keep an abandoned job and its configuration alive.
16 does it remove       YES, three measured costs: amplification from retained/foreign/orphan jobs, orphan
   measurable cost?     re-render plus orphan artifacts after a rejection, and the queue-mate failure coupling /
                        misdiagnosis. NO for Atlas's own work (an accepted submission always renders its own job
                        once) and NO for anything in the evidence chain (already queue-independent).
17 second authority?    No. It isolates ENGINE EXECUTION STATE; it creates no second authorization, no second
                        identity source, and no second evidence authority. What it does create is a new
                        OWNERSHIP surface: one UObject that Atlas must create, root, and release, on a class that
                        is not a UObject and therefore has no GC-safety net.
```

## 4. Shared queue (candidate A) — the seven questions

```text
1 measured amplification      quantified in §2: 2.5x-2.7x job-renders per accepted submission in a 3-4 job
                              session; grows linearly with retained queue depth and with the frame counts of the
                              retained jobs. Bounded only by operator behaviour (the queue is visible and can be
                              cleared by hand in the MRQ UI).
2 rejected-job accumulation   measured: 1 orphan job per rejected submission + its PNGs in its own configured
                              directory. Fail-closed (Slice 1 discards the payload, no receipt exists), but the
                              engine still spends the frames.
3 non-Atlas jobs              rendered inside Atlas's pass; their artifacts and start events are discarded by
                              Slice 1 / Slice D; a fatal error in one of them fails Atlas's pass (F-coupling).
4 operator visibility         the strongest property of A: everything Atlas submits is visible, inspectable and
                              clearable in the MRQ UI, and the active-render tab shows the true job list.
5 correctness after guards    no false receipt, no mis-attributed artifact, no false success: proven by the
                              Slice 1/2, Slice D and Slice E live gates. The remaining defects are never of the
                              "wrong evidence accepted" class.
6 acceptable inefficiency?    Acceptable as the default ONLY because it is visible, bounded by operator control,
                              and costs nothing in evidence integrity - and because the alternative trades a
                              visible efficiency cost for an invisible lifecycle surface plus lost visibility.
                              It stops being acceptable if a trigger in §7 fires.
7 remaining failure modes     (i) queue-mate fatal error -> Atlas job reported failed with a misleading message
                              (availability + diagnosis, fail-closed);
                              (ii) long retained jobs delay Atlas's own job (latency, not incorrectness);
                              (iii) a rejected submission leaves an orphan that re-renders in later passes
                              (efficiency);
                              (iv) accumulation grows unboundedly across a long editor session (hygiene in memory,
                              efficiency in render time).
```

## 5. Queue consumption / deletion (candidate C) — analysed separately

```text
1 is deletion safe at every executor state?   NO.
   MoviePipelineLinearExecutorBase::StartPipelineByIndex does
     check(InPipelineIndex >= 0 && InPipelineIndex < Queue->GetJobs().Num());   (MoviePipelineLinearExecutor.cpp:48)
   and OnIndividualPipelineFinished re-reads the LIVE array size
     const bool bNoMoreJobs = CurrentPipelineIndex >= Queue->GetJobs().Num() - 1;   (:81)
   so removing a job while any executor is iterating that queue can trip a fatal check in Development, or
   skip/mis-index the remaining jobs and therefore mis-sequence completion. Atlas cannot observe whether some
   other executor is mid-pass on the same queue (the subsystem exposes IsRendering()/GetActiveExecutor() but not
   "who is iterating"). Deletion is therefore conditional on state Atlas does not own.
2 are consumed-state semantics useful locally?  PARTIALLY - and this corrects the earlier queue-lifecycle
   review, which treated consumption as a remote/UI-only concept. The local linear executor DOES honour it:
     if (Queue->GetJobs()[CurrentPipelineIndex]->IsConsumed()) { OnIndividualPipelineFinished(nullptr); return; }
                                                                     (MoviePipelineLinearExecutor.cpp:58-64)
   with the engine's own comment that consumed jobs are skipped so remote-submitted jobs are not overridden.
   Two consequences: (a) marking retained completed Atlas jobs consumed WOULD remove their re-render work;
   (b) a job that is consumed BEFORE its own submission would be skipped silently, with NO per-job callback -
   Atlas would see "submitted" until the timeout, i.e. it would recreate exactly the silent-failure class that
   Slice E just removed. Consumption is therefore only safe on jobs already terminal in Atlas's registry.
3 does consumption solve anything private isolation does not?
   It removes the amplification (item 5 of §2) but NOT the orphan case: the rejected submission's job has no
   registry entry (Slice E removes it deliberately), so Atlas holds no handle to consume; cleaning it would
   require new Atlas state (an "allocated but unaccepted" registry) or deleting it at rejection time.
   It also does not remove the foreign-job failure coupling, and it mutates operator-visible state:
   MoviePipelineQueue.cpp:345 sets Consumed=false on allocation (so consumption must be applied by Atlas), and
   the MRQ UI filters consumed jobs out of its renderable/labelled lists
   (SMoviePipelineQueuePanel.cpp:324,518; MovieRenderPipelineEditorUtils.cpp:47;
   SMoviePipelineQueueEditor.cpp:529,220),
   i.e. consuming Atlas's finished jobs would make them disappear from the operator's queue view.
4 does it mutate non-owned state under any failure path?  YES by construction - the jobs are the editor's queue
   contents, and the mutation is visible to the operator. It also cannot be undone safely (SetConsumed(false) is
   an editor-UI action today), and it is exactly the "queue mutation" the frozen constraints forbid.
```

## 6. Candidate verdicts

| # | candidate | verdict | reasoning |
|---|-----------|---------|-----------|
| A | keep current shared MRQ queue semantics permanently | **ACCEPT as the default** | Nothing that remains is a correctness or evidence risk; the costs are availability, efficiency and (positively) visibility. It is the only option that keeps Atlas renders inspectable and clearable by the operator, and it requires no new object ownership. |
| B | Atlas-owned private queue via `RenderQueueInstanceWithExecutorInstance` | **DEFER, engine-proven, with written entry criteria and triggers (§7, §8)** | It removes three measured costs (amplification, orphan re-render/artifacts, queue-mate failure coupling), and the mechanism change is one call + one queue allocation. But it adds an Atlas-owned, non-UObject-held UObject with rooting/release obligations, removes operator visibility, and diverges the MRQ UI from the rendered queue. Worth doing only against a measured trigger, under its own gate. |
| C | consume/delete Atlas-owned jobs | **REJECT for now** | Deletion is not safe at every executor state (`check()` + live `Num()`), consumption recreates the silent-skip hazard if mis-timed and mutates operator-visible engine state, and neither removes the foreign-job coupling. It cannot even clean the orphan case it is most often proposed for, without new Atlas state. |
| D | hybrids | **ACCEPT only in the form "A now, B later if a trigger fires"** | B + C is redundant: a per-submission private queue is bounded by construction, so there is nothing to consume. A + C buys amplification reduction at the cost of mutating the operator's queue and keeping the foreign coupling - the worst trade of the three. |

## 7. Recommendation

```text
recommendation   Keep the shared MRQ queue semantics (A) as the permanent default. Do NOT migrate to a private
                 queue now, and do NOT implement consumption/deletion. Record the triggers below; if any fires,
                 open a dedicated design gate for B (with C still excluded).

trigger T1       measured amplification becomes material in real production: retained queue depth >= 5 in a
                 working session, or per-submission re-render work exceeding the new job's own work (observable
                 from the existing "MoviePipelineLinearExecutorBase starting job [i/N]" lines and the
                 "starting N jobs" counts already used in the live gates).
trigger T2       operator workflow needs per-render isolation (e.g. cancellation of one Atlas render, or the
                 queue panel becoming unusable because Atlas jobs flood it).
trigger T3       a queue-mate fatal error repeatedly fails healthy Atlas submissions (availability loss, not
                 hypothetical: the pass-scoped failure coupling is source-confirmed).
trigger T4       the queue-mate misdiagnosis starts appearing in production reports as "our render failed" when
                 Atlas's own job succeeded (diagnosis quality).
also record      the residual misdiagnosis itself is a finding worth fixing independently of isolation IF a
                 future slice can bound it without queue mutation; this review does not authorize that work.
```

## 8. Entry criteria if B is ever opened

```text
1  ownership: exact owner of the queue object, its rooting mechanism on a non-UObject holder, and an explicit
   release on success, rejection, engine error and transport stop; a leak check must be part of the evidence.
2  lifetime: per-submission (bounded) versus session-reused (accumulating, invisible) - decided in writing,
   because session-reused is strictly worse than today's shared queue.
3  sequencing: the two-argument RenderQueueInstanceWithExecutorInstance call plus the unchanged Slice E identity
   observation, in one game-thread task.
4  UI consequence: the divergence between the rendered queue and the MRQ queue panel / active-render tab is
   documented and accepted, and the cancellation story is established.
5  invariants: job identity stays engine-minted and single-sourced; the registry stays the only Atlas-side job
   state; receipts keep their fields and their fresh-verified-termination gate; no protocol or authorization
   change; Slice 1 and Slice D guards stay in place as backstops.
6  evidence: a live gate proving zero amplification for a fresh submission against a non-empty editor queue,
   no orphan job or artifacts after a rejection, callbacks still job-scoped, exact identity and continuity
   unchanged, and the documented operator-visible behaviour.
```

## 9. Test strategy for any future implementation (NOT authorized, NOT written)

```text
deterministic   queue-ownership lifecycle: created, rooted, released on each path; a rejected submission leaves
                no Atlas-owned object and no job; the accepted path passes the private queue explicitly while the
                editor queue is untouched (a violation detector for "no mutation of the editor queue"); registry,
                identity, receipt and continuity contracts asserted unchanged.
live            one editor session with a NON-empty editor queue: submit an Atlas render and prove the pass
                renders ONLY Atlas's own job (no amplification), that a rejected submission leaves no orphan job
                or artifacts, that the editor's queue contents are byte-for-byte unchanged, and that the UI
                divergence behaves as documented. DLL provenance as in the previous slices.
```

## 10. Frozen invariants preserved (nothing in this list changes)

Named Pipe protocol and its operation/argument/response field sets; authorization model and sequence binding;
engine-minted exact render-job identity; receipt architecture and the "fresh verified terminal evidence" gate;
`UnrealShotContinuity` as the single continuity authority; inclusive Atlas frame semantics and the single MRQ
end-frame translation; shot continuity and PNG containment/frame-set verification; MRQ artifact attribution
(Slice 1 + Slice D); submission outcome propagation (Slice E); no queue mutation; no automatic mutation retry; no
entity discovery/cache; no distributed rendering; no generic workflow engine; no model-derived authority;
Blender untouched.

## 11. Findings register

```text
F1  CORRECTNESS: none remaining. Evidence, receipts, artifact attribution, start monitoring, identity binding and
    submission outcomes are all job-identity bound and live-proven; the queue layout cannot currently produce a
    false Atlas receipt. This is the answer to "are the remaining costs correctness risks": NO.
F2  AVAILABILITY: pass-scoped failure coupling. A fatal error in any queue-mate (foreign job, or the orphan left
    by a rejected submission) fails the whole pass and marks Atlas's job failed with the message "Render executor
    finished with failure" (MoviePipelineExecutor.h:216-234 -> AtlasTransportServer.cpp:1470-1491). Fail-closed,
    but a valid render can be lost and the diagnosis names the wrong job.
F3  EFFICIENCY: measured amplification 2.5x-2.7x job-renders per accepted submission in 3-4 job sessions, growing
    with retained depth and retained frame counts; plus the orphan job's frames in every later pass.
F4  EFFICIENCY/HYGIENE: rejected submissions leave one allocated job in the queue (measured: 1 job, 2 orphan
    PNGs), because queue mutation is frozen; the registry entry is removed, so Atlas has no handle to it.
F5  VISIBILITY: the shared queue is the ONLY place an operator can see, inspect and clear Atlas's jobs; isolation
    would remove that (queue panel and active-render tab both read Subsystem->GetQueue()).
F6  CORRECTION to the earlier queue-lifecycle review: the LOCAL linear executor does honour IsConsumed()
    (MoviePipelineLinearExecutor.cpp:58-64), so consumption has real local effect - but skipping a consumed job
    fires no per-job callback, so consuming a job before submission would recreate the silent-timeout failure
    class that Slice E removed.
F7  LIFECYCLE: FAtlasTransportServer is not a UObject, so any Atlas-owned queue needs explicit rooting/release;
    a session-reused private queue would also survive pipe restarts and hide accumulation from the operator.
F8  ONSET CONDITIONS: the review's recommendation is conditional by design (triggers T1-T4). If any fires, the
    isolation gate must be reopened rather than the default silently retained.
```

**Verdict: `CLEAR WITH MINOR FINDINGS`.**

The question is answerable from the sources and the recorded measurements: after the three identity-bound slices,
**no remaining queue cost is a correctness risk**. The residual costs are availability (pass-scoped failure
coupling and its misleading diagnosis, findings F2/F7-adjacent), efficiency (measured amplification and orphan
re-render, F3/F4), operator visibility (F5 - a property of the shared queue, not a defect), and hygiene
(unbounded in-memory accumulation). A private queue is engine-supported and would remove three of those measured
costs, but it adds an Atlas-owned UObject lifecycle on a non-UObject holder, removes operator visibility, and
diverges the MRQ UI from the rendered queue; consumption/deletion is unsafe at every executor state and mutates
operator-visible engine state without removing the foreign-job coupling. The recommendation is therefore to keep
the shared queue semantics as the permanent default and to revisit isolation only against written triggers. This
document **authorizes no implementation**.

---

*Evidence classes: (a) UE 5.6.1 engine sources with file:line anchors
(`MovieRenderPipelineCore/Public/MoviePipelineLinearExecutor.h`, `.../Private/MoviePipelineLinearExecutor.cpp`,
`MovieRenderPipelineCore/Public/MoviePipelineExecutor.h`, `MovieRenderPipelineCore/Public/MoviePipelineQueue.h`,
`.../Private/MoviePipelineQueue.cpp`, `MovieRenderPipelineEditor/Public/MoviePipelineQueueSubsystem.h`,
`.../Private/MoviePipelineQueueSubsystem.cpp`, `.../Private/Graph/MovieGraphQuickRender.cpp`,
`.../Public/Graph/MovieGraphQuickRender.h`, `.../Private/Graph/SMovieGraphActiveRenderSettingsTabContent.cpp`,
`.../Private/Widgets/SMoviePipelineQueuePanel.cpp`, `.../Private/Widgets/SMoviePipelineQueueEditor.cpp`,
`.../Private/Widgets/Graph/SMovieGraphConfigPanel.cpp`, `.../Private/MovieRenderPipelineEditorUtils.cpp`); (b) this repository's transport and planning sources at `4b61d8f`;
(c) live-gate measurements recorded for Slice 1/2, Slice D and Slice E. No engine was run for this review, and
nothing is asserted that the sources or the recorded measurements do not show.*
