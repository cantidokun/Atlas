# M7 Case-B — Production Wiring + Real Quiescence / Job Object Provenance (Q4/Q8)

> **Review status (M7 containment-keeper implementation rung).** This design was submitted to an
> independent design gate and returned **DESIGN REVIEW CLEAR — SAFE TO IMPLEMENT**, accepting
> **OPTION 4 — CONTAINMENT-KEEPER-AS-RECOVERY-TRIGGER** as the target architecture. The gate also
> determined that the frozen S1 evidence is **permanently rehearsal/deterministic evidence only**: a
> NEW authorized live render will eventually be required for production Case-B proof.
>
> Four documentation corrections were mandated by that review and now land in the repository together
> with this rung's implementation (documentation first, implementation second):
>
> 1. Contract V1 **§9** — `JobObjectHandleValid` now includes provenance to the SAME containment Job
>    Object created for the attempt (launch provenance, retention, kernel configuration, kernel
>    counter consistency).
> 2. Contract V1 **§21 Case B** — Case B **requires the retained launch-object provenance** and can
>    NOT be satisfied by a synthetic/fresh Job Object.
> 3. `docs/design/M7_S1_ADOPTION_CASE_B_DESIGN.md` — the old statement that the frozen S1 evidence
>    could later be adopted is **removed/corrected** (§12, §13, closing recommendation): frozen S1
>    evidence remains valid render/rehearsal evidence, cannot satisfy future live §9 provenance,
>    cannot produce a production Case-B receipt, and a new authorized execution is required for live
>    proof.
> 4. Contract V1 **§10** — custody rule for the per-attempt nonce used to authenticate the launch
>    record (per attempt; supplied to the keeper through the authorized in-process launch boundary;
>    never persisted in plaintext; never reused; fail closed if custody/authentication fails), plus
>    the **Containment Launch Record** artifact definition.
>
> This document remains the design of record for the rung. Its own text below is unchanged; where it
> said the frozen S1 evidence could not be adopted, that is now a contract-level rule (Contract V1 §9
> `JobObjectHandleValid`, §21 Case B) and not merely an analysis.

Status: **DESIGN GATE OUTPUT — TARGET ARCHITECTURE DEFINED. Nothing implemented.**
Artifact state: uncommitted, untracked, not pushed. PR #131 untouched.
Mode: design-only, read-only audit of the repository plus one throwaway Win32 probe run outside the
repository (no Unreal, no render, no store mutation, no new authorization).
Revision audited: `d83fd75dd739e3a3aa269cee94d34f88a2011b2f`, tree
`cf53b79098a1106c099511daf976d172fda12c2c`, parent/`main` `748982713fb6042d875890cbd9999a3bbcbfb3aa`.
CI on that revision: green (Atlas Tests, Python 3.9 + 3.11, run 35661860799).

This document answers, for the Case-B durable-witness path: (A) production `journal_root` wiring, and
(B) real quiescence / Job Object provenance (Q4/Q8). It supersedes the prior scratch analysis; the
in-flight findings F-DG-1…F-DG-4 are incorporated and F-DG-1 now has a closure mechanism that was
validated empirically, not asserted.

Evidence classes used below, kept distinct:

* **READ** — statements derived from committed source/text (file:line given).
* **RUN** — statements from an executed probe; the exact output is reproduced.
* **DECIDED** — a design choice made here, with its cost and residual stated.
* **NOT PROVEN** — explicitly unverified; never to be read as a live claim.

---

## 1. Method, and the one thing that was proven by execution

The design hinges on a Windows fact: whether a Job Object can be shown to be *the* containment object
that contained a given render. Windows exposes no Job Object UUID, so this was tested rather than
assumed.

Probe (throwaway, outside the repo):
`C:\Users\Gavin's PC\AppData\Local\Temp\atlas_m7_design\probe_jobobject_identity.py`, run with the
system Python 3.11.16. It (i) builds a fresh never-used Job Object with `KILL_ON_JOB_CLOSE`,
(ii) builds a second Job Object, assigns a spawned process to it, (iii) hands each handle to the
**real repository predicate** `scripts/run_unreal_supervisor.py::evaluate_process_quiescence`, and
(iv) re-reads the kernel counters after the contained tree has drained.

Result (**RUN**):

```text
(A) fresh never-used job object      : {'active': 0, 'total': 0, 'terminated': 0, 'kill_on_close': True}
    spawned suspended child pid=22140
(B) launch job, child SUSPENDED (live): {'active': 1, 'total': 1, 'terminated': 0, 'kill_on_close': True}
(B) launch job + child running       : {'active': 2, 'total': 2, 'terminated': 0, 'kill_on_close': True}

REAL predicate with the FRESH job handle   : is_quiescent=True active=0
REAL predicate with the LAUNCH job (live)  : is_quiescent=False active=2

(B) launch job after child terminated : {'active': 0, 'total': 2, 'terminated': 0, 'kill_on_close': True}
(A) fresh job, unchanged              : {'active': 0, 'total': 0, 'terminated': 0, 'kill_on_close': True}

DISCRIMINATOR: fresh total=0 vs drained-launch total=2  -> distinguishable=True
```

Three conclusions, all load-bearing for this design:

1. **F-DG-1 is real and reachable, not theoretical.** Handing `evaluate_process_quiescence` a
   *fresh empty* Job Object returns `is_quiescent=True` **while a different Job Object still holds live
   processes**. The §9 precondition can therefore be satisfied by the wrong object, and the coordinator
   consumes that predicate directly (`planning/unreal_render_recovery_coordinator.py:176-184`).
   Synthesizing a new empty supervisor is exactly the attack the prior rung's frozen-S1 idea implies.
2. **A kernel-authoritative discriminator exists.** `JOBOBJECT_BASIC_ACCOUNTING_INFORMATION.TotalProcesses`
   is cumulative for the object's lifetime: `0` for a fresh object, `≥1` for one that ever contained a
   process. The field is already declared in the repository's struct
   (`scripts/run_unreal_supervisor.py:31`) but `query_active_processes()` returns only
   `ActiveProcesses` (`:127-142`), so the discriminator is available but unused.
3. **`TotalTerminatedProcesses` is not a usable "the tree died" signal** — it stayed `0` after the
   contained process was terminated externally; it counts processes reaped *by the job object*, not
   external terminations. Recorded so no future rung reaches for it.

`TotalProcesses ≥ 1` is **necessary but not sufficient** as an identity proof (a synthetic job that once
held a dummy process also reports ≥1). Section 5 defines the closure that makes it sufficient *in
combination* with an authenticated launch record, and names the residual honestly.

---

## 2. Current commit-validated state (what is true at `d83fd75d` today)

| Property | State today | Evidence |
|---|---|---|
| Durable-witness reader (B1–B4 + E3 remediation) | Present, committed, reviewed, CI-green | commit `d83fd75d` |
| Durable Case-B adoption logic | Implemented and deterministic-tested; zero-RPC proven | `planning/unreal_render_recovery_coordinator.py`; tests/m9 |
| `journal_root` production wiring | **Absent.** No non-test caller supplies it; Case B is inert in production | grep: no non-test constructor of the coordinator |
| Recovery entrypoint (production) | **Absent.** Ownership is a human runbook step | `docs/LIVE_EXECUTION_CHECKLIST.md:140` |
| Executable containment authority | **Absent.** `AtlasProcessSupervisor` has zero non-test instantiations; `scripts/run_unreal_supervisor.py` has no CLI/`main` | F-DG-2 |
| Job Object handle provenance binding | **Absent.** Predicate trusts any handle it is given | F-DG-1 (proven in §1) |
| Cross-restart quiescence | **Impossible.** Handle dies with the launcher; last close reaps the tree and destroys the object | `:144-148`; F-DG-3 |
| Open-by-name / terminate-and-wait primitives | **Absent** | `scripts/run_unreal_supervisor.py` |
| Real quiescence / Job Object reattachment (Q4/Q8) | **Not implemented, by declaration** | handoffs; `DEVELOPMENT_LOG.md:734` |
| Frozen S1 record (`atlas-render-job-d046bf30-…`) | Non-terminal, `WAITING_FOR_ENGINE`, no receipt, no lineage | handoff §3/§7 |
| Frozen S1 artifacts + journal (24 PNGs, schema 2, HMAC) | Intact; valid *render evidence* | handoff §3 |

This table is the whole justification for treating A and B as one problem: wiring `journal_root` at
`d83fd75d` would connect the recovery path to a containment that no repository code can create and
whose proof no code can bind.

---

## 3. Part A — production `journal_root` wiring

### 3.1 The brief's ten questions, answered

1. **Who owns recovery execution today?** Nobody, in code. The only constructors of
   `UnrealRenderRecoveryCoordinator` are tests (tests/m6/fault_fixtures.py:313, m7–m10 fixtures,
   tests/m9/*) and the M9 scenario harness (`planning/unreal_live_scenario_harness.py`). Production
   ownership is an operator instruction (`docs/LIVE_EXECUTION_CHECKLIST.md:140`). **READ**
2. **When does recovery execute?** Only when a human runs it. No scheduler, daemon, timer or
   engine-exit hook exists. `_expired_deadline` bounds waiting but never triggers a pass
   (`planning/unreal_render_recovery_coordinator.py:192-224`). **READ**
3. **What process should construct the coordinator?** A thin composition root. Not the preflight —
   its declared invariant is pure-predicate validation with no mutation
   (`planning/unreal_live_preflight.py:4-7`); it stays the precondition authority. Not the historical
   autonomy/controller-bridge modules (forbidden, and they are not on the Case-B path). Not the M12
   planner path — `docs/UNREAL_M12_SEMANTIC_SOCCER_DESIGN.md:88-100` asserts the existing
   planner/executor/adapter/coordinator "remain the single execution/authority path", but nothing there
   constructs the coordinator either. **DECIDED**: `scripts/run_unreal_recovery.py` as composition root,
   assembling only, deciding nothing — and see §4: it obtains its quiescence handle from the containment
   keeper, it never creates one.
4. **How is `AtlasRenderJobStore` located?** Explicit root argument; layout
   `root/{jobs,locks,quarantine,receipts}` (`planning/unreal_render_job_store.py:64-75`). There is no
   canonical production root: the only non-test caller uses a relative `.atlas_render_store`
   (`execute_unreal_stage17_live_proof.py:51`). **DECIDED**: one declared store root, single-sourced
   with the submission path, asserted (job count + target `atlas_job_id` present) and recorded in the
   invocation evidence. A second, independently defaulted root would make every job look absent →
   Case C/D, no receipt: fail-closed but silent.
5. **How is `UnrealAdapterProduction` created?** `create_production_adapter()` →
   `UnrealAdapterProduction(create_named_pipe_transport())` on `\\.\pipe\AtlasUnrealTransport`
   (`planning/unreal_adapter_production.py:165-167`). It raises at construction without Windows+pywin32,
   so the entrypoint must either construct it (live path) or explicitly accept a non-constructible
   adapter on the durable-only path. **READ**
6. **How is `UnrealRenderReceiptStore` located?** Derived, never configured:
   `store.receipts_dir / f"{atlas_job_id}__{attempt_ordinal}.json"`
   (`planning/unreal_render_job_store.py:69`; tests/m6/test_m6_04_receipt_crash_fencing.py:97).
   **DECIDED**: no new receipt-store configuration is introduced.
7. **How should `<ProjectDir>/AtlasWitnessJournal` be resolved?** Derived from the configured
   `.uproject` (ProjectDir = the uproject's directory), matching the engine's
   `FPaths::Combine(FPaths::ProjectDir(), "AtlasWitnessJournal")`
   (`docs/design/M7_S1_ADOPTION_CASE_B_DESIGN.md:227`). One shared resolver, canonicalised, rejecting
   symlink/junction escape and anything under `Saved/`. **DECIDED**: production must not accept an
   operator-supplied arbitrary root — an arbitrary root is a trust-relevant directory
   (`docs/design/M7_S1_ADOPTION_CASE_B_DESIGN.md:291-296`). Today nothing derives it; the preflight's
   A3/A7/A8 gates are `live_only` operator confirmations (`docs/LIVE_EXECUTION_CHECKLIST.md:43,47-48`).
8. **What supervisor/quiescence authority is passed?** The handle to the Job Object the engine was
   launched in, obtained from the containment keeper that created it, bound to a durable launch
   identity. A locally created Job Object is refused by construction. §5 defines the binding.
9. **What must remain alive across an Atlas restart?** The durable record, journal and artifacts
   (already durable) **and** a live handle to the launch job. The latter does not exist today; §4 is
   about who keeps it.
10. **What evidence must be captured for the recovery invocation?** The existing §12 set
    (`docs/design/M7_S1_ADOPTION_CASE_B_DESIGN.md:486-503`) plus invocation provenance: resolved store
    root, derived canonical journal root, uproject path, adapter `source_tag`, deployment mode,
    handle/job identity and launch-record digest, `coordinator_id` + `lease_token`, per-job decision
    results, and the preflight phase results as preconditions. §8 gives the full package.

### 3.2 Production call chain (required deliverable)

```text
operator / launcher
  -> containment keeper  (repository-owned, executable; §9 authority; survives an Atlas restart;
                          owns the Job Object handle; holds it until the job drains)
       -> Job Object (KILL_ON_JOB_CLOSE; breakaway disabled; launch identity recorded durably)
            -> engine launches inside the object (create-suspended -> assign -> resume)
       -> at the instant ActiveProcesses == 0:
            -> scripts/run_unreal_recovery.py      (composition root; assembles, decides nothing)
                 -> store root          -> AtlasRenderJobStore
                 -> .uproject           -> journal_root (derived, canonicalised)
                 -> store.receipts_dir  -> UnrealRenderReceiptStore
                 -> create_production_adapter()
                 -> supervisor handle   <- the keeper's own handle, bound to the launch record
            -> UnrealRenderRecoveryCoordinator.reconcile_*   (unchanged, fail-closed)
            -> verified evidence -> preflight phase results -> receipt (store-gated, exactly once)
            -> invocation evidence written; handle released only after the pass completes
```

### 3.3 Part A findings

* **F-DG-2 — no executable containment authority exists.** `AtlasProcessSupervisor` has zero non-test
  constructions; `scripts/run_unreal_supervisor.py` has no CLI. The runbook instructs an operator to
  start the engine contained "via the supervisor" as a human operation
  (`docs/LIVE_EXECUTION_CHECKLIST.md:114`), and the containment/quiescence gates are `live_only`
  operator confirmations (`:47-48`). The S1 run demonstrates containment *behaviour*; it does not
  establish a reproducible containment *authority*. Wiring recovery first would wrap a containment
  nothing can run.
* **F-DG-4 — documentation precision.** (i) "Job Objects are created unnamed" is true in practice but
  imprecise in code: `job_name` is accepted and passed to `CreateJobObjectW`
  (`scripts/run_unreal_supervisor.py:84-95`), and no production caller passes one; the code also then
  calls `SetInformationJobObject`, so an open-existing path must be added distinctly rather than
  reusing the create path. (ii) "Q8" has **no numbered definition anywhere in the repository** — the
  design doc defines Q1–Q7 (`docs/design/M7_S1_ADOPTION_CASE_B_DESIGN.md:531-548`); Q4/Q8 exists only
  as shorthand in handoffs and `DEVELOPMENT_LOG.md:734`. This document defines it as the reattachment
  question of §4, which is the only reading consistent with its usage.

---

## 4. Part B — Q4/Q8: real quiescence and Job Object provenance

### 4.1 The decisive constraint (F-DG-3)

A Job Object **name does not keep the object alive**. The object exists only while at least one handle
is open; when the last handle closes, `KILL_ON_JOB_CLOSE` reaps the tree and the object is destroyed —
after which the name no longer resolves and no counter survives. Therefore:

* `OpenJobObjectW` reattach is possible **only while another process still holds a handle**;
* reattach can never resurrect a destroyed job (so Q8-as-"reattach after the launcher exits" is
  infeasible);
* **retention is the mechanism; reattach is only a transport primitive.**

Today's implementation reaches quiescence by *destroying* the container (`close()`, `:144-148`); the S1
run observed 6 → 1 → 0 before that close.

### 4.2 Options, evaluated explicitly

**OPTION 1 — long-lived supervisor / handle retention.**
A keeper process outlives Atlas, holds the handle, and does not close it while a job is non-terminal.
* Preserves: `KILL_ON_JOB_CLOSE` provenance (keeper death still reaps the tree); the §9 predicate
  unchanged (the handle is the launch job's); zero-RPC adoption; exactly-once receipt.
* Costs: one new long-lived component plus a channel to it. That channel is a **trust surface** — it can
  misreport the count — so it must be authenticated and must hold no receipt/store/authority capability.
* Residual (named): keeper crash while a job is non-terminal ⇒ tree reaped, handle gone ⇒ quiescence
  unprovable ⇒ fail closed to `WAITING_FOR_ENGINE` → `EXHAUSTED`. A job whose tree is provably gone can
  still become unadoptable. Accepted explicitly, never silently.
* Verdict: **necessary component**, insufficient alone (it answers provenance, not autonomy).

**OPTION 2 — named Job Object + `OpenJobObjectW` / terminate-and-wait primitives.**
* Valuable as primitives, **invalid standalone** (§4.1).
* Buys: (i) an open path so a recovery client can query the keeper's job without owning the launch;
  (ii) Q4's answer — `TerminateJobObject` + poll to `ActiveProcesses == 0` lets recovery reach
  quiescence *itself*, an operation that only ever reduces liveness and can mint no authority.
* Obligation if used as proof: the opened object must be shown to be the launch object — a name is not
  provenance, since a name can be recreated — which folds into F-DG-1.
* Verdict: **adopt as transport + autonomy primitive**, never as the identity proof.

**OPTION 3 — durable quiescence attestation.**
Persist a signed "`ActiveProcesses == 0` at time T, for this attempt" record and let a later pass accept
it.
* Admissible only as a *supplementary* witness with an explicit anti-replay and no-further-execution
  argument.
* As a replacement for the §9 predicate it converts a live kernel observation into a stored claim, and
  after a reboot nothing proves no further execution began; it re-opens the class already rejected as
  Option A on 12 criteria (`docs/design/M7_S1_ADOPTION_CASE_B_DESIGN.md:310-329`).
* Verdict: **out of scope** for this target architecture (no reboot-survival requirement has been
  stated). Re-openable only with an explicit contract decision.

**OPTION 4 — containment-keeper-as-recovery-trigger (inline adoption at the drain edge). [RECOMMENDED]**
One repository-owned, executable process that (1) launches the engine inside the Job Object
(create-suspended → assign → resume, per the F-ARM2-1 wording), (2) records the launch identity durably
(§5), (3) retains the handle until the tree drains, (4) at the instant it observes
`ActiveProcesses == 0` runs the recovery pass **in-process with its own live handle**, (5) writes the
invocation evidence, and only then (6) releases the handle.
* Why it is the smallest *sufficient* architecture: quiescence never has to survive an Atlas restart,
  because the reconcile happens inside the process lifetime that owns the proof. Q4 is answered by
  construction (the keeper both reaches and observes zero); Q8's reattachment requirement is dissolved
  rather than solved, and open-by-name remains available as transport for a future recovery *client*
  variant.
* Preserves every invariant: §9 predicate and mode table unchanged; the handle is the launch job's;
  adoption stays zero-RPC from the durable witness; receipt stays exactly-once via the existing
  store-gated publication; no new adoption, receipt or execution authority anywhere.
* Costs: the keeper becomes a trusted component in the §9 chain (§5 residual), and it must be
  repository-owned and executable (F-DG-2 closure) rather than an operator convention.
* **Option 4b (variant, if Atlas must drive recovery itself):** keeper retains the handle and exposes
  an authenticated `{query_active_processes, terminate_and_wait, launch_record_digest}` surface; the
  Atlas-side recovery client obtains an authenticated handle *lease* from it. This adds the same trust
  surface with a wider attack surface (IPC + lease), and is strictly more work than 4 for the same
  soundness. Recorded, not recommended.

**Refused (not re-litigated here):** worker-scoped / relaxed quiescence (already rejected on 12 criteria;
re-opens Q1); engine self-attestation as the sole quiescence proof; PID- or parent-death-based reasoning
(§9.268); any variant that can adopt while the engine may still be live; and "synthesizing a new
supervisor" to stand in for a lost launch object (§1 conclusion 1).

### 4.3 Where the trust boundary moves

Under Option 4 the §9 proof becomes: *the kernel says this retained object is empty, the object is
provably `KILL_ON_JOB_CLOSE`, and the object is provably the one the durable launch record created for
this attempt.* The first two are kernel facts; the third is an authenticated assertion by the keeper plus
counter consistency (§5). This is the honest price of making Case B executable at all: §9's guarantee
requires some component to hold a handle, and that component therefore becomes part of the trust chain.

---

## 5. F-DG-1 closure — proving the queried Job Object IS the render's containment object

**Requirement.** Quiescence for attempt `(atlas_job_id, attempt_ordinal)` must be attributable to the
Job Object created for *that* attempt, and no other.

**Closure (four conjuncts; all must hold).**

1. **Durable launch record, written before any engine process exists.** The keeper, immediately after
   `CreateJobObjectW` + `SetInformationJobObject` and *before* resuming the suspended engine, writes a
   launch record bound to the attempt: `atlas_job_id`, `attempt_ordinal`, the Job Object name, the
   expected engine session identity, the launch composition (engine PID + process creation time, plus
   the worker composition if recorded — Q7), and a digest authenticated with the Atlas-held
   `attempt_nonce` key (HMAC, same discipline as the journal `entry_digest`; the nonce itself is never
   serialized, §10 secret-handling invariant). The record is the *identity claim* for the object.
2. **Handle provenance.** The queried handle is the one the keeper created and retained — never a
   handle to a locally created object. In the Option-4b variant this is enforced by the keeper's
   authenticated lease; under Option 4 it holds by construction (same process, no second object path).
   A fresh `AtlasProcessSupervisor` is refused as a quiescence source, permanently.
3. **Kernel counter consistency.** The object must report `KILL_ON_JOB_CLOSE` set with breakaway
   disabled (proving the containment configuration of §9.274) **and**
   `TotalProcesses ≥ recorded launch composition ≥ 1` (proving this object has actually contained the
   render's process tree — the discriminator validated in §1), **and** `ActiveProcesses == 0`.
   A fresh never-used object fails on `TotalProcesses == 0`.
4. **Attempt binding.** The launch record's authenticated digest, the durable render record, and the
   durable witness journal being adopted must agree on `atlas_job_id`, `attempt_ordinal`, and the
   journal's HMAC identity. Any disagreement fails closed (existing Case E/F/H semantics).

**Why each conjunct is needed** (this is where a weaker design would be vacuous): (3) alone is
defeated by a synthetic job that once held a dummy process; (1)+(2) alone rest on an unauthenticated
assertion; (4) alone proves nothing about containment. Together they make "this object contained *this*
attempt's tree and is now empty" the only accepted reading.

**Residual, named and not hidden.** Windows provides no kernel-level Job Object instance identity, so
the third conjunct is an *attribution* proof, not a cryptographic one: a hostile or compromised
containment keeper could construct an object that satisfies (1)–(4) while different processes are still
running elsewhere. Therefore:

* the keeper must be repository-owned, started only by the authorized launcher, and must expose no
  capability other than the ones above;
* the keeper's control/data channel must be authenticated and local-only;
* this residual is a **trust decision owned by the operator**: accepting an authenticated containment
  authority into the §9 chain is what makes Case B executable. If that trust is refused, no sound
  model exists under §9 as written and the gate verdict becomes BLOCKED by definition (see §13).

**Deterministic control for this closure:** the deciding test is not that the launch object passes, but
that a fresh empty object **fails** — the deliberately lossy control that the §1 probe already exhibits
against the real predicate.

---

## 6. Authority chain (required deliverable)

| # | Link | What binds it | Where it is verified |
|---|---|---|---|
| 1 | **Containment authority** (keeper) | Repository-owned executable, launched by the authorized launcher; no other capability | F-DG-2 closure; §4.2 Option 4 |
| 2 | → **Job Object** | `CreateJobObjectW` + `KILL_ON_JOB_CLOSE`, breakaway disabled; handle retained, never closed while the job is non-terminal | §9.272-274; `scripts/run_unreal_supervisor.py:84-116` |
| 3 | → **Launch identity** | Durable launch record written before engine resume, HMAC-bound to the attempt nonce; composition recorded | §5 conjunct 1 (new artifact) |
| 4 | → **Durable journal** | Engine writes `<ProjectDir>/AtlasWitnessJournal/<atlas_job_id>__<unreal_job_id>.json`; per-phase HMAC `entry_digest` keyed by the Atlas-held nonce | §10.288-340 |
| 5 | → **Quiescence** | Retained handle + `KILL_ON_JOB_CLOSE` + `TotalProcesses ≥ recorded composition` + `ActiveProcesses == 0`, attributed to the attempt via the launch record | §5 conjuncts 2–4 (new) |
| 6 | → **Recovery coordinator** | Constructed by the composition root with the keeper's handle; quiescence established **before** witness acquisition | coordinator `:176-184`, `:337-359` |
| 7 | → **Case B adoption** | Durable witness (schema 2, terminal phase, bound pair, ordinal, HMAC) + artifacts re-hashed vs manifest; zero engine RPC | §21:716-718; tests/m9 |
| 8 | → **Receipt** | 8-field identity match, store-gated single publication with lease token + expected revision | §17; `store.publish_verified_receipt` |

The chain has exactly one new link (3) and one new component (1). No existing link's authority moves.

---

## 7. Frozen S1 — can the ORIGINAL evidence still satisfy the real §9 proof without another render?

**NO.** Stated plainly, with the reasons:

1. **The proof's subject no longer exists.** §9's predicate is a live observation over a valid handle to
   the launch Job Object. That object was destroyed when its last handle closed — `KILL_ON_JOB_CLOSE`
   reaped the tree and the object's counters and name died with it (F-DG-3). The 24 PNGs, the schema-2
   journal and the durable record survive; the object does not.
2. **A new empty object cannot substitute.** Synthesizing a supervisor/Job Object now yields
   `ActiveProcesses == 0` and — as §1 proved against the real predicate — `is_quiescent=True` **with no
   relationship to the S1 render**. That is the F-DG-1 vacuity attack in its purest form: it would let
   Atlas adopt 24 artifacts on the strength of an object that never contained anything.
3. **The historical observation is not admissible as an attestation either.** During the S1 run a valid
   handle did report exactly 0 active processes, but it was an ad-hoc operator-held handle whose object
   identity was never recorded (Q7: "S1 captured counts only"), so there is no durable, authenticated,
   attempt-bound evidence of it. Reconstructing it after the fact would be exactly Option 3, introduced
   retroactively and without its own proof obligations — refused.
4. **PID/death-based reasoning is barred.** §9.268 exists precisely because parent death and stale PIDs
   do not prove descendant quiescence. "No UnrealEditor is running now" is not a §9 proof.

Consequences, and what is still true of the frozen evidence:

* The frozen S1 record **cannot reach `FINALIZED` and cannot produce a receipt**. Left alone it fails
  closed on its execution deadline → `EXHAUSTED` / `RECOVERY_FAILED`, no receipt — a legitimate
  terminal closure, not an adoption. (Its deadline state should be confirmed by reading the actual
  durable record before any decision; **NOT PROVEN** here.)
* The 24 artifacts and the journal remain valid **render evidence** and remain the harness's ground
  truth for shape/hashing; they will never become **production lineage**, because a receipt binds to its
  own attempt's identity and a new render produces new artifacts.
* A new render is therefore required for a receipt on this scene — and it must run under the §4/§5
  architecture to be adoptable at all. That is a **separate live authorization**, which this design
  explicitly does not create.
* This contradicts the earlier recommendation in
  `docs/design/M7_S1_ADOPTION_CASE_B_DESIGN.md:486-503` ("the adoption step can be re-gated on the
  existing frozen S1 evidence"). That recommendation is not implementable under §9 as written, for
  reason 1 alone. It should be corrected in whatever rung is authorized to touch that document.

---

## 8. Minimum evidence package for a future live Case-B adoption

Beyond the existing §12 set (pinned revision/tree at every checkpoint; containment; the adoption
decision with `case_classified` and both recovery statuses; zero-RPC send count; exactly one receipt
with all 8 identity fields and `receipt_digest`; the record transition with non-null `receipt_reference`
and no `failure_reason`; independent 24/24 manifest re-hash; artifact non-mutation before/after; and a
deliberately lossy negative control that must FAIL closed), a live Case-B gate must add:

1. **Containment authority identity** — keeper binary/source revision, launch command line, launcher
   principal, and the deployment mode declaration.
2. **Launch record** — the durable, HMAC-bound record of §5 conjunct 1, with its digest.
3. **Object provenance evidence** — the queried object's `KILL_ON_JOB_CLOSE` flag state,
   `TotalProcesses`, `ActiveProcesses` (and the recorded launch composition) read **immediately before**
   the reconcile, plus the fact that the same handle was retained across the drain (no re-creation).
4. **Timing/ordering proof** — evidence that quiescence was evaluated before any witness acquisition or
   artifact inspection (the F-S1-4 ordering), e.g. ordered step log or span markers.
5. **Preflight precondition record** — the phase results (`PRE_ENGINE` / `POST_ENGINE` / `POST_INTENT`)
   that armed the run.
6. **Invocation provenance** — resolved store root, derived canonical journal root, uproject path,
   adapter `source_tag`, `coordinator_id`, `lease_token`, and the per-job decision results.
7. **Negative controls, per property** (the deciding evidence is the control failing, not the positive
   passing): (a) fresh empty object → quiescence refused; (b) launch record digest mismatch → refused;
   (c) `TotalProcesses` below the recorded composition → refused; (d) non-zero `ActiveProcesses` →
   Case K, no adoption, artifacts byte-identical; (e) handle released/re-created → refused.

---

## 9. Deterministic tests for the chosen architecture

No engine, no live run. Each row names the property and the failing control that makes it decisive.

| # | Test | Must prove | Deciding control (must FAIL) |
|---|---|---|---|
| 1 | Object-provenance binding | quiescence accepted only for the attempts' own launch record | a *fresh empty* Job Object handle → `is_quiescent=False` (today it returns True — §1) |
| 2 | Counter consistency | `TotalProcesses < recorded composition` is refused | synthetic object that held a dummy process but whose recorded composition is larger |
| 3 | Launch-record authentication | tampered/replayed/missing launch record → refused | digest tamper; replay from another attempt ordinal |
| 4 | Configuration proof | missing `KILL_ON_JOB_CLOSE` (or breakaway enabled) → refused | object created without the limit flag |
| 5 | Keeper-triggered adoption | drain observed → reconcile runs in-process with the live handle → Case B + exactly 1 receipt | keeper that hands a re-created object → refused |
| 6 | Zero-RPC non-vacuity | transport send count == 0 on the durable path; adapter that raises on any access still yields Case B | explosion adapter with a *non*-quiescent object → no adoption (Case K) |
| 7 | Ordering (F-S1-4) | quiescence evaluated before witness acquisition and before any artifact inspection | non-empty object + terminal journal → Case K, zero inspection calls |
| 8 | Handle retention semantics | the pass fails closed when no launch handle exists | no keeper → `WAITING_FOR_ENGINE`, no adoption, no receipt |
| 9 | Keeper-death path | keeper death ⇒ no quiescence ⇒ fail closed; never adoption | simulated keeper exit with a non-terminal job |
| 10 | Journal-root derivation | resolver derives from `.uproject`, canonicalises, rejects escape | symlink/junction pointing outside the root; a root under `Saved/` |
| 11 | Store-root single-sourcing | recovery sees the same store as submission | a mismatched store root → no adoption, decision recorded (Case C/D), no receipt |
| 12 | Mode table | `UNCONTAINED_ATTACHED` never yields Case B | uncontained mode with a perfect journal |
| 13 | Exactly-once under keeper retries | repeated triggers publish exactly one receipt | second trigger after publication → repair-from-receipt, no second receipt |
| 14 | Exhaustion | keeper absent + expired deadline → `EXHAUSTED`/`RECOVERY_FAILED`, no receipt | overdue non-terminal record |

---

## 10. Failure / recovery matrix

| Event | Job Object | Handle | Expected outcome | Receipt | Notes |
|---|---|---|---|---|---|
| Render completes, engine exits, keeper alive | drained, intact | still held | **Case B** → `FINALIZED` | exactly 1 | the target path |
| Render completes, engine exits, keeper crashes before drain is observed | destroyed (last close reaped tree) | gone | fail closed → `WAITING_FOR_ENGINE` → deadline → `EXHAUSTED` | 0 | named residual of Option 4 |
| Atlas restarts mid-render | intact | held by keeper (not Atlas) | render continues; keeper adopts at drain | 1 | §33 Scenario 3/5 satisfied without Atlas keeping state |
| Both restart mid-render | destroyed when keeper dies | gone | fail closed, ambiguous/incomplete | 0 | §33 Scenario 4 |
| Engine crashes mid-render | intact (stragglers reaped on close) | held | non-terminal journal → Case J / fail closed per classification | 0 | no synthetic success |
| Engine alive, journal terminal | intact, non-empty | held | **Case K** hold; no inspection, no adoption | 0 | F-S1-4 ordering |
| Journal unreadable/malformed/truncated | any | any | `PARTIAL` → Case J; whole pass still completes | 0 | B1 |
| Stray/foreign/legacy journal present | any | any | ignored; healthy live job unaffected | 0 | B2 |
| Contradictory `job_id`/`unreal_job_id` | any | any | reader rejects (PARTIAL), never COMPLETE/adoptable | 0 | B3 |
| Durable terminal FAILED witness | intact, empty | held | Case G FAILED offline, zero RPC | 0 | B4 |
| Artifacts missing/hash-mismatched after terminal claim | intact, empty | held | Case G | 0 | §21 |
| Terminal claim + artifacts present but engine journal absent | intact, empty | held | Case C/D (`ORPHANED_ARTIFACTS_PRESENT`), never VERIFIED/FINALIZED, artifacts untouched | 0 | §21 Case D non-mutation |
| Two materially different executions for one atlas_job_id | any | any | Case H → `RECOVERY_FAILED` | 0 | duplicate protection |
| Fresh empty object offered as proof | — | fresh | **refused** (F-DG-1 control) | 0 | prevents adoption under a live engine |
| Launch record digest mismatch / absent | any | held | refused, fail closed | 0 | §5 |
| Deadline expires unresolved | any | any | `EXHAUSTED` → `RECOVERY_FAILED`; no retry | 0 | §23 |
| Receipt already published, keeper retriggers | any | any | receipt-first repair; no re-execution, no second receipt | 1 | §20 Step 2 |
| Second concurrent job in the same job object | non-empty for job B | held | conservative hold for both (one object per session) | 0 until drained | deliberate, no soundness loss |

---

## 11. Contract impact

| Section | Impact | Nature |
|---|---|---|
| **§9** (Unreal Process Identity; `266-284`) | Predicate, mode table and `KILL_ON_JOB_CLOSE` requirement are **unchanged**. The enclosing clause `JobObjectHandleValid == TRUE` gains a defined meaning it currently lacks: *a retained handle to the launch object, provably the attempt's own, with counter consistency*. Required additions: handle provenance + launch identity + the fresh-object refusal. | Clarification + binding; no weakening |
| **§10** (Engine Journal; `288-340`) | Journal format, path, HMAC and nonce handling **unchanged**. The launch record of §5 is a **new durable artifact**; place it beside the record/store (not in the journal directory) and treat it as identity evidence, never as authority. | Additive |
| **§20** (Reconciliation Algorithm; `631-706`) | Step ordering unchanged. Step 4 (capability handshake) becomes reachable only on the live branch; the durable branch continues with zero engine interaction. Quiescence evaluation must remain ahead of Steps 5-8 (already implemented). | No change to the algorithm; one precondition made explicit |
| **§21** (Recovery Cases; `710-786`) | Case B definition unchanged, and now actually reachable in a contained deployment. Add an explicit clause that **Case B is unreachable without a retained launch-object handle** (today implicit, and the source of the frozen-S1 deadlock). Case A / C / D / G / H / J / K unchanged. | Clarification |
| **§23** (Recovery Budgets and Deadlines; `828-845`) | Unchanged and still load-bearing: keeper absence or destruction must **not** burn the ambiguity budget any faster (transport/containment unavailability is not execution failure). Deadline exhaustion stays the terminal fail-closed route for a job that can no longer be proven quiescent. | No change; explicitly relied upon |
| **§33** (Required Live UE 5.6 Validation; `1054-1098`) | Scenarios 1, 3 and 5 become executable as written only under the keeper architecture (they all require adoption after the engine's tree is gone). Scenario 1's expected "`FINALIZED` with one verified lineage" currently cannot be met by the frozen S1 evidence (§7). | Enabling; Scenario 1 re-run required under a new authorization |
| §5/§6/§17/§19/§27/§29/§34/§37 | Untouched: record/store layout, receipt identity and single publication, wire contract, capability handshake, concurrency, acceptance criteria and final invariants are neither modified nor re-interpreted by this design. | None |

---

## 12. Future live-ready state (item 10, second half)

The repository becomes live-ready for Case B when **all** of the following hold:

1. A repository-owned executable containment keeper exists (F-DG-2 closed): launches contained, records
   the launch identity, retains the handle, triggers the recovery pass at the drain edge, releases the
   handle only after the pass completes.
2. Handle provenance binding exists (F-DG-1 closed): fresh/foreign objects refused; `KILL_ON_JOB_CLOSE`
   and counter consistency asserted; launch record authenticated and attempt-bound.
3. The composition root exists and single-sources store root, derived `journal_root`, receipt store and
   adapter, recording the §8 evidence package.
4. The deterministic controls of §9 pass, each with its failing control demonstrated.
5. A **separate** live authorization exists for a contained render whose adoption is gated end-to-end,
   with the §8 negative controls captured in the same rung.
6. The frozen S1 record has been adjudicated (expected `EXHAUSTED`/`RECOVERY_FAILED`, no receipt) rather
   than left ambiguous, and its artifacts are documented as evidence-of-render, never lineage.

Until 1–4 exist, production Case B remains **inert by design** — which is the current, safe state.

---

## 13. Verdict

**DESIGN GATE CLEAR — TARGET ARCHITECTURE DEFINED**

* **Target architecture:** containment-keeper-as-recovery-trigger (Option 4) — a repository-owned
  executable that launches contained, records a durable attempt-bound launch identity, retains the Job
  Object handle, and runs the recovery pass in-process the instant the kernel reports
  `ActiveProcesses == 0`, with open-by-name / terminate-and-wait adopted as transport and autonomy
  primitives (Option 2) and durable attestation held out of scope (Option 3).
* **F-DG-1 closed** by four conjuncts (durable launch record; handle provenance; `KILL_ON_JOB_CLOSE` +
  `TotalProcesses ≥ recorded composition` + `ActiveProcesses == 0`; attempt binding), empirically shown
  to discriminate a fresh empty object from a drained launch object against the real predicate (§1), with
  the attribution residual named and the fresh-object refusal installed as the deciding control.
* **F-DG-2** closed by making the containment keeper repository-owned and executable.
* **F-DG-3** honoured: retention is the mechanism, reattach only its transport; a destroyed object is
  never treated as recoverable.
* **Frozen S1: NO** — the original evidence can no longer satisfy the real §9 proof, the lost Job Object
  provenance cannot be reconstructed, and synthesizing a new empty supervisor as a substitute is refused
  as the F-DG-1 attack. The S1 artifacts remain render evidence only; a receipt for that scene requires a
  new authorization and a new render under this architecture.
* **The one decision this leaves to the operator:** accept an authenticated, repository-owned containment
  authority as a link in the §9 trust chain (its residual is named in §5). If that trust is refused, no
  sound model exists under §9 as written, and this verdict must be read as BLOCKED accordingly.
* **Nothing here is implemented, and nothing here authorizes a live action.** The next rung — if
  authorized — is deterministic implementation of §4/§5/§9 plus the composition root; the live gate is a
  separate authorization after that.

---

## Post-red-team clarification (non-blocking cleanup, added after review)

The independent red-team review of the implementation returned **THIRD-PARTY CLEAR — SAFE TO
COMMIT** with three non-blocking cleanup items. Two of them touched code paths described here;
this section records the clarifications rather than editing the frozen text above.

1. **Durable invocation evidence.** The drain-edge path now *persists* its invocation evidence
   (the composition root's writer, invoked by the keeper's default recovery trigger, writing
   `<store root>/containment/recovery_invocation_<UTC>.json`). §3.2's "invocation evidence
   written; handle released only after the pass completes" is therefore literal, and a failed
   evidence write surfaces as a failure rather than a success. The keeper acquires no
   classification, receipt or submission authority by doing so: the writer belongs to the
   composition root and the receipt path remains store-gated.
2. **Containment-dir record resolution.** Where a coordinator is constructed with
   `containment_launch_record=None` and `containment_dir` supplied, the attempt's authoritative
   launch record is now resolved and authenticated from the durable containment store *before*
   quiescence and engine-incarnation validation, so that path performs the same identity checks
   as the keeper path instead of skipping them. Fail-closed behaviour is unchanged: a missing,
   malformed or unauthenticated record still yields no provenance and no adoption.
3. **Keeper failure after quiescence, before the trigger completes.** Expected **design
   residual**: the object dies with the last handle, the attempt's provenance is unrecoverable,
   and the job fails closed to deadline exhaustion (`EXHAUSTED` / `RECOVERY_FAILED`), with the
   receipt-first probe still repairing a pass that had already published. No fresh Job Object
   may be substituted and no durable attestation may stand in for the lost object. This is
   named here so it is read as intended behaviour rather than as an anomaly to work around.
