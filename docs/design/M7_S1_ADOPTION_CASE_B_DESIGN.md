# M7 S1 — Case B Adoption Contract (Design Brief)

Status: DESIGN GATE OUTPUT — no implementation performed, no PR, no merge, no second submission.
Pinned revision: `origin/main` = `748982713fb6042d875890cbd9999a3bbcbfb3aa`, tree `b851438bdc1d7a03507b72776fa2116b94b5092e`
Evidence baseline: the single authorized M7 S1 live submission of 2026-09-21 (see §3).

---

## 1. Problem statement

The M7 S1 live render succeeded end to end, but the recovery coordinator could not adopt the
result: no receipt exists and the durable record is stuck. The failure is not in rendering,
evidence verification, or hashing — it is that the **adoption path requires a live engine RPC at a
moment when the contract requires the engine to be gone.**

Contract V1 §9 (`docs/ATLAS_UNREAL_CROSS_PROCESS_RECOVERY_CONTRACT_V1.md:266-284`) establishes two
deployment modes. In `CONTAINED_JOB_OBJECT`:

```text
Quiescence requires:
  JobObjectHandleValid == TRUE AND QueryInformationJobObject(BasicAccounting).ActiveProcesses == 0

Only when ActiveProcesses == 0 is confirmed may recovery inspect or adopt terminal disk artifacts.
```

Unreal is launched *inside that same Job Object* (§9.272-274). Therefore a satisfied quiescence
predicate means the engine process is dead, and an engine RPC cannot succeed. Conversely, while the
engine is alive the job is non-empty, so quiescence is false. **`ActiveProcesses == 0` (adoption
precondition) and "engine reachable" (current implementation precondition) cannot both hold.**

This document determines how Case B can be reached in the real contained deployment without
weakening the quiescence invariant, and whether the M9 S1 scenario model is faithful.

---

## 2. Current state machine (as implemented)

`planning/unreal_render_recovery_coordinator.py::reconcile_single_job` (line 260) executes, under a
per-job claim (`store.acquire_job_claim`, line 268):

| # | Step | Code | Notes |
|---|---|---|---|
| 1 | Receipt-first probe | 273-285 | `_probe_receipt_first`; 8-field identity match; repair without re-execution |
| 1b | Deadline exhaustion | 287-295 | unresolved + expired → `EXHAUSTED`/`RECOVERY_FAILED` |
| 2 | **Engine capability/session handshake** | 297-315 | `adapter.assert_recovery_capable(record.authorization_id)`; on `UnrealAdapterError` → `WAITING_FOR_ENGINE` |
| 3 | **Catalog inspection (engine RPC)** | 317-335 | `_query_catalog` (line 540) issues the `reconcile_render_jobs` operation; `journal_status` PARTIAL/UNREADABLE → Case J; CONFLICT → Case H (344-360) |
| 4 | Identity matching | 394-409 | `_check_candidate_bindings` (594) → Case E/F |
| 5 | Live-match branch | 415-430 | `state_source == in_memory_registry` and not finished → Case A |
| 6 | Torn/non-terminal witness | 435-455 | → Case J |
| 7 | Terminal candidate | 463 → `_handle_finished_candidate` (696) | quiescence gate first (707-724) → Case K; ordinal (726-743); HMAC (745-787); artifact 4-point (789-834); bind+verify (836-859); receipt issue (862-872) + store-gated publication (874-880) → Case B (888) |
| 8 | No engine evidence | 652-694 | Case C (no artifacts) / Case D (`ORPHANED_ARTIFACTS_PRESENT`, non-mutating) |

Observed live on the S1 run (exactly the two mutually exclusive branches):

```text
engine contained + alive (job active 6)   -> reconcile #1 = "Case K (Quiescence Blocked)"
                                             recovery WAITING_FOR_ENGINE_QUIESCENCE, no repair
engine terminated, job active 0           -> reconcile #2/#3 = "WAITING_FOR_ENGINE"
final durable record: lifecycle SUBMITTED, recovery WAITING_FOR_ENGINE, receipt_reference null
```

Case B was never reached, so **the §9.279 precondition was never violated — the implementation
failed closed, correctly, at the wrong gate.**

---

## 3. Exact F-S1-1 contradiction

**F-S1-1 (BLOCKER).** Step 2 (`coordinator:299`) makes engine reachability a *precondition* of the
terminal-adoption path, and Step 3 (`coordinator:318`) sources the witness and `journal_status` from
an engine RPC. Both are unsatisfiable exactly when the contract permits adoption (§9.279). The two
gates are therefore mutually exclusive by construction:

| live configuration | §9 quiescence (job ActiveProcesses == 0) | engine reachable (Step 2) | resulting decision |
|---|---|---|---|
| engine contained, alive (observed: 6) | **false** | true | `Case K (Quiescence Blocked)` — hold |
| engine terminated, contained drain to 0 (observed: 0/9) | **true** | **false** | `WAITING_FOR_ENGINE` — hold |

Reconcile #3 was executed with a valid Job Object handle reporting **exactly 0 active processes**
(i.e. the §9 predicate satisfied) and still returned `WAITING_FOR_ENGINE` — proving the block is the
Step-2 precondition, not the quiescence gate.

**Secondary finding F-S1-4 (ordering).** §9.279 states adoption may occur *only after*
`ActiveProcesses == 0` is confirmed, yet the implementation performs two engine RPCs (Steps 2 and 3)
*before* the first quiescence evaluation (`coordinator:708`). Inspection therefore precedes the
adoption precondition today. The target contract makes the quiescence gate the first post-receipt
check.

**S1 factual baseline (frozen evidence).**

```text
exactly one submission, no duplicate, acceptance_unknown=false
atlas_job_id   atlas-render-job-d046bf30-ba5f-440a-9ce1-cbc7e2e11f67
unreal_job_id  F7BA777C-40EC-74F4-0F92-2BA361FF0DF8 (engine-minted)
authorization  auth-m7-live-748982713fb6042d875890cbd9999a3bbcbfb3aa-retry2 (bound)
attempt_ordinal 1, attempt_nonce present (64 hex, never printed/persisted outside the record)
digests        request 98fd3d2d…, config 7ec95840…, authoritative 65efb0e2…
render         status finished, success=true, 24 PNG, all 1280x720, all IEND-complete
manifest       24 entries {path, sha256, size}; 24/24 re-hashed and size-matched on disk, 0 mismatches
journal        <ProjectDir>/AtlasWitnessJournal/<atlas_job_id>__<unreal_job_id>.json, schema 2,
               phases ACCEPTED(1) -> STARTED(2) -> FINISHED(3), entry_digest 58b9301b…
containment    total 9 contained; drain 6 -> 1 -> 0; job destroyed on last handle close
repo           no implementation change; no commit
```

A read-only **Case B dry-run** (`%LOCALAPPDATA%\Temp\atlas_m7_armgate2\s1\case_b_dryrun.json`)
executed the coordinator's *own* check functions in production order, substituting only the witness
source (durable journal file instead of the catalog RPC):

```text
S1 receipt-first probe (none present)                    PASS
S2 §9 quiescence (handle valid AND ActiveProcesses == 0) PASS  (recorded live)
S3 durable journal set present (1 file)                  PASS
S4 journal_schema_version == 2                           PASS
S5 bound to (atlas_job_id, unreal_job_id)                PASS
S6 terminal candidate (phase FINISHED, finished=true)    PASS
S7 identity/sequence/config bindings                     FAIL -> PASS after normalization (see below)
S8 attempt_ordinal binding (1 == 1)                      PASS
S9 M8 HMAC-SHA256 witness attestation                    PASS
S10 four-point artifact stability + hashes (24/24)       PASS
S11 independent evidence verification (ENGINE_JOURNAL_ATTESTED) PASS (verified=true)
S12 receipt issue + store-gated publication              NOT EXECUTED (deliberate)
```

S7's single failure is a **field-name gap, not a binding failure**: `_check_candidate_bindings`
(`coordinator:602`) reads `candidate.get("job_id")` — the engine-catalog field name — while the
durable journal entry carries `unreal_job_id`. The coordinator's own normalizer already carries both
names (`coordinator:627-630`), and feeding the normalized candidate back to the same check returns
`None` (no mismatch), with `bound["job_id"] == record.unreal_job_id`. So **the durable witness
satisfies every adoption check the coordinator performs, including the M8 HMAC, once the witness
candidate is normalized.** S9 passing is decisive: the durable journal is not merely a log, it is an
Atlas-keyed-attested witness.

---

## 4. Existing invariants that MUST NOT be weakened

| # | Invariant | Source | Why it must survive |
|---|---|---|---|
| I1 | Quiescence = valid job handle AND `ActiveProcesses == 0` over the Job Object Unreal was launched in; adoption only after that | §9.272-279 | The whole cross-process recovery guarantee: Windows does not kill or re-parent descendants |
| I2 | Container must be `KILL_ON_JOB_CLOSE`, silent breakaway disabled, explicit breakaway disallowed | §9.274 | Without it the job's zero is not a proof of zero |
| I3 | `UNCONTAINED_ATTACHED` fails closed: no cross-process adoption, block until deadline then `RECOVERY_FAILED` | §9.281-284 | Otherwise adoption is unprovable |
| I4 | Attempt nonce is Atlas-generated (256-bit), persisted before transmission, never created by the engine | §10.306-313 | Witness anti-replay/anti-restore |
| I5 | Journal is a **witness**, not an authority system; Atlas identity/digests are record-authoritative | §10.288-290; `UNREAL_M7_HARDENING.md:99-110` | Prevents the engine from authorizing its own success |
| I6 | Journal path is Atlas-designated and durable, retains execution history, must not overwrite a prior execution identity | §10.292-304 | Enables Case B and Case H adjudication |
| I7 | Only engine-live or engine-journal-attested observations may enter the authoritative verifier | §20:700-702 | Evidence provenance |
| I8 | Case H (multiple materially different executions), Case J (partial/unreadable/torn), Case E/F (identity/config mismatch) all fail closed and do not overwrite history | §21:742-758; `coordinator:337-360,435-455` | Ambiguity is never resolved in favour of adoption |
| I9 | Exactly one immutable receipt, 8 identity fields, store-gated atomic publication with lease token + expected revision | §20:704-706; `coordinator:861-891` | No duplicate lineage, no re-execution |
| I10 | Case D non-mutation: never move/rename/delete/adopt unattributable artifacts | §21:726-740 | Artifacts stay untouched |
| I11 | No synthetic `finished`/`success`; no timeout inflation; a discovered defect is named, not masked | Project audit bar | Trust in the evidence chain |
| I12 | Duplicate-submission protection: store claim + in-transaction submission identity | `unreal_render_submission.py` (PR #130); `coordinator:268` | One authorization = one execution |

---

## 5. Option A analysis — scope quiescence to render-worker descendants

**Proposal.** Keep the engine alive as the liveness bearer; treat as authoritative-for-quiescence
only the render-worker/descendant processes whose termination is required for adoption; contain
`supervisor → engine host → render workers` in a hierarchy.

**Verdict: REJECTED — architecturally invalid.** It cannot be made valid without weakening I1.

1. **It changes the quiescence index, which I1 fixes.** §9.275-277 defines quiescence over *the Job
   Object Unreal was launched in*, and §9.279 gates inspection/adoption on that predicate. Re-scoping
   to a worker sub-job redefines the predicate from "the whole execution tree is gone" to "a subset
   Atlas selected is gone", i.e. exactly the weakening the brief forbids. A process that is not in
   the worker job is not counted — including the engine, which is the sole writer of both artifacts
   and the journal.
2. **It contradicts §9.268's own rationale.** The job exists because Windows does not terminate or
   re-parent descendants (`ShaderCompileWorker.exe`, `UnrealPak.exe`, `CrashReportClient.exe`,
   custom commandlets). §9.268 enumerates *helpers*, not render workers: the threat model is
   "anything spawned under this launch", so narrowing the set removes the containment's reason to
   exist. A worker-scoped job would also have to prove no breakaway occurred (§9.274), which the
   narrower job can no longer witness.
3. **In the S1 topology the worker-scoped proof is vacuous.** The authorized S1 render is an
   in-editor Movie Render Queue job; the producer of the artifacts is the engine process itself.
   S1 captured counts only (1 process immediately after the contained create, 6 after pipe-ready,
   total 9 contained), not the composition — so a worker-scoped predicate would, in the common case,
   aggregate zero processes and pass trivially while the actual writer is still alive. A proof that
   is vacuous whenever the deployable topology has no distinct workers is not a proof.
4. **It permits adoption while the producer is live.** With the engine alive there is no guarantee
   that the artifact set is final: the engine may still be writing, may re-run the job, or may serve a
   *different* attempt. §9.279's "only when `ActiveProcesses == 0`" exists precisely to exclude that
   window. Adopting inside it would be a genuine soundness regression, not a convenience.
5. **It is unnecessary.** Every fact Option A wants the live engine for is already durable, attested,
   and independently checkable (§6) — the live engine adds transport, not authority.

**Open question that cannot rescue Option A (recorded, not required):** the exact composition of the
contained process set was not captured in S1 (only counts). A bounded read-only probe in the
implementation rung can record the Job Object PID/name list at launch and at terminal. This is
useful for §12 evidence quality but does not change the verdict: even if a distinct render worker
existed, the engine remains a member of the launch job and the writer of the artifacts.

---

## 6. Option B analysis — journal-attested adoption

**Proposal.** After the durable render result exists, adoption no longer depends on a live engine
RPC. Adoption is authorized by: the durable terminal attested witness journal + the durable
authoritative record (identity, authorization, attempt, config, expected spec) + independent disk
hash verification + the §9 containment/quiescence proof.

**Verdict: ARCHITECTURALLY VALID — and it is what Contract V1 already specifies.** Not a relaxation;
a completion of a documented path that the implementation cannot currently reach.

### 6.1 The contract already defines Case B this way

* §21 Case B (`docs/…CONTRACT_V1.md:716`): *"Prior session journal contains an exact terminal
  FINISHED record for a bound `unreal_job_id`"* → *"Use `ENGINE_JOURNAL_ATTESTED` evidence, verify
  hashes against the recorded output manifest, then continue normal receipt/provenance
  verification."* "Prior session" is by definition not the current live session; the mandated
  evidence class is the **journal-attested** class, which is exactly what the S1 journal produced
  (S11 `verified=true`).
* §20 Step 8 (`:700-702`): only engine-live **or engine-journal-attested** observations may enter the
  authoritative verifier.
* §9.279 permits inspection/adoption precisely once `ActiveProcesses == 0` — the state where no RPC
  exists.
* §10 (`:288-304`) already mandates the durable journal at
  `<ProjectDir>/AtlasWitnessJournal/<atlas_job_id>__<unreal_job_id>.json`, retained as execution
  history, never overwriting a prior execution identity — and the S1 journal is at exactly that path
  with exactly that name.

### 6.2 The durable journal is not a new authority — the engine's catalog *is* that disk scan

`unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Private/AtlasTransportServer.cpp`:

* `GetJournalDirectory()` returns `FPaths::Combine(FPaths::ProjectDir(), "AtlasWitnessJournal")`
  (`:2422-2424`) — the same directory §10 mandates and the S1 run produced.
* The `reconcile_render_jobs` handler derives `journal_status` by **scanning that directory on
  disk** (`:2060-2085`), with a **second scan** for A/B stability (`:2199-2206`), `PARTIAL` on
  unreadable content, and `CONFLICT` when a second journal for the same `atlas_job_id` is a
  materially different execution (`:1947, 2016, 2043, 2172, 2270`).
* The engine writes the journal file to that directory (`:2631-2638`).

So today's Step 3 asks the engine to read a directory and return its contents. Reading the same
directory Atlas-side adds no *new* authority: the engine itself takes this evidence from disk.

**Correction (post third-party review — this paragraph previously claimed the two readers are
simply "the same source of truth").** That claim was overstated. The equivalence is bounded, and
the implementation now depends on the differences rather than assuming them away:

| Aspect | Engine scan (`AtlasTransportServer.cpp`) | Atlas durable reader (`planning/unreal_witness_journal.py`) |
| --- | --- | --- |
| Attribution scope | filters by `atlas_job_id` in the loaded JSON and returns a catalog for *all* jobs in one response | attributes per reconciled job: §10-logical-key filename match, or content match for a misnamed file (which fails closed); everything else is ignored and reported as `ignored_files` |
| Filename rules | does not enforce the §10 logical key — a badly named file is still scanned as content | enforces the key for *attribution*; a §10-key file whose content is bound to a different job, or a misnamed file claiming this job, is `PARTIAL` |
| Schema handling | reads whatever JSON parses; `journal_schema_version` is not required to be `2` | requires `journal_schema_version == 2`; anything else is `PARTIAL` for an attributable witness |
| Partial classification | `PARTIAL` when content is unreadable/unparseable | `PARTIAL` for unreadable/unparseable/**truncated**/**invalid-schema**/**misnamed**/**contradictory-or-absent identity** attributable witnesses |
| Stability | second scan, A/B compare over the whole directory | snapshot A/B compare of the *attributed* witness bytes only |
| Identity | mints/reports the engine's own `job_id` | requires one canonical engine identity: `unreal_job_id` authoritative, contradiction or absence → `PARTIAL` (never adopted) |
| Failure containment | an engine-side read error is reported in the response | a filesystem/parse failure on an attributable witness is classified in-state and can never abort the reconcile pass |

What remains true — and is the reason Option B is not a new authority — is that the *bytes* are
the same bytes, written by the engine, and their integrity is independently bound to Atlas's own
attempt nonce (HMAC-SHA256, verified against `record.attempt_nonce`) plus the §10 identity,
ordinal, authorization and manifest checks. Atlas's reader is a stricter filter over that same
evidence, not a second source of truth. Where it is stricter, it fails closed.

### 6.3 What replaces the post-render liveness probe, and why it remains authoritative

| Replaces | With | Authority argument |
|---|---|---|
| `assert_recovery_capable` (Step 2, liveness) | §9 quiescence (valid handle AND `ActiveProcesses == 0`) + presence of a durable terminal attestation for the bound pair | §9.279 is the contract's own precondition for inspection/adoption; the record's non-terminal state + quiescence + terminal witness is a complete state description |
| Engine catalog RPC (Step 3) | Durable journal set in the Atlas-designated root: parse, validate schema, resolve the bound pair, derive set status (`COMPLETE` / `PARTIAL` / `CONFLICT` / absent) | Identical source (the same directory) and identical semantics; HMAC-keyed by an Atlas-generated 256-bit nonce (§10.308-313) that the engine consumes only as an HMAC key and can never mint (I4) |
| Engine-witnessed session/process identity | `editor_session_id`, `process_id`, `process_creation_time_utc`, `state_source` from the journal entry | Engine-witnessed fields travel in the witness; already consumed by the coordinator's HMAC payload (`:773-774`) |
| A/B catalog stability snapshot (§20 Step 7) | Snapshot A = journal file bytes + parsed terminal record + manifest; disk hash verification; Snapshot B = re-read/re-derive; material change → `RECOVERY_PENDING` (Case J semantics preserved) | The stable-index requirement is preserved without a live engine; the journal file is the durable snapshot source |

Nothing in the Case B tail needs the engine: ordinal binding (`:726-743`), HMAC (`:745-787`),
artifact 4-point (`:789-834`), bind+verify (`:836-859`), receipt issue and store-gated publication
(`:861-891`) are all record+candidate+disk. The dry run exercised each of them on the real S1
evidence and passed (S8-S11).

### 6.4 Preserved fail-closed semantics (no silent weakening)

* Identity/authorization binding: unchanged — 8 receipt fields, `_check_candidate_bindings`, and the
  verifier's exact-equality identity checks all still run (`S5`, `S7`, `S11`).
* HMAC/ordinal: unchanged — a tampered, replayed, or cross-attempt journal fails `UNTRUSTED_WITNESS`
  (`:726-787`). The nonce is never minted by the engine (I4).
* Artifacts: unchanged — the four-point check (existence, PNG completeness, two-pass stat stability,
  SHA-256 vs manifest) still fails closed to Case G.
* Ambiguity: unchanged — absent witness → Case C/D; unparseable → Case J; >1 materially different
  execution for the bound pair → Case H; identity/config mismatch → Case E/F.
* Quiescence: unchanged and now *earlier* (F-S1-4 fixed), so adoption can never precede it.
* `UNCONTAINED_ATTACHED`: unchanged — `evaluate_process_quiescence` returns
  `is_quiescent=False` (`scripts/run_unreal_supervisor.py:157-163`), so Case B remains unreachable
  there, as §9.283 requires.
* No new execution path: Option B never submits, never re-renders, never reuses a nonce, never
  mutates artifacts.

### 6.5 Residual risks / new ambiguity (named, severable)

1. **Journal root becomes a trust-relevant directory** (it already is: the engine reads it to build
   its catalog). Control: the nonce-keyed HMAC makes forgery infeasible without the Atlas-held secret;
   the file is not self-authorizing (I5). Residual: an actor who can read the durable record can
   forge. Mitigation to specify in the implementation rung: canonical-path validation (the resolved
   journal file must live under the configured Atlas journal root; reject symlink/junction escapes)
   and record-store access hygiene. Not a new exposure relative to today's engine scan.
2. **Stale-witness acceptance** — prevented by ordinal + nonce + bound pair + terminal phase; a
   journal from another attempt/record fails closed.
3. **Reachability ambiguity when the engine is alive elsewhere** (uncontained or a different job) —
   fail-closed by I2/I3 and by requiring a *valid handle to the job the engine was launched in*;
   ownership of the handle is part of §12 evidence.
4. **Operator-dependent quiescence** — reaching `ActiveProcesses == 0` requires the engine to be shut
   down (or to exit). Autonomous recovery must be able to do this itself: the sanctioned mechanism is
   the supervisor's contained launch with `KILL_ON_JOB_CLOSE` (already true in the S1 run: last
   handle close reaped the tree). To specify: whether the supervisor exposes an explicit
   "drain/terminate then wait for 0" step for autonomous recovery (see §14 Q5).

---

## 7. Comparison matrix

| Criterion | Option A (worker-scoped quiescence) | Option B (journal-attested adoption) |
|---|---|---|
| 1. Invariant preserved | None of I1-I12 as written; I1's predicate is redefined | I1-I12 all preserved; I1 now enforced *before* inspection (fixes F-S1-4) |
| 2. Invariant changed | I1 quiescence index (whole tree → worker subset); §9.279 adoption precondition effectively weakened | None. Contract §21 Case B, §20 Step 8, §9.279, §10 are already written this way; only the *witness source* changes |
| 3. Authority source | Atlas-chosen process subset + live engine RPC | Durable record (identity/auth/attempt/config/topology) + durable HMAC-attested witness + disk bytes |
| 4. Recovery semantics | Adoption possible while the producer is live → soundness regression; crash windows unprovable | Adoption only after the tree is gone; recovery becomes *more* available in the state where it is provably safe (today it deadlocks) |
| 5. Crash semantics | Atlas crash during a live adoption leaves a live engine whose later writes are unproven against an adopted receipt | Atlas crash before receipt publication is now recoverable: the durable witness + record persist; the receipt-first probe (`:273-285`) still precedes adoption, so no double publication; a crash after publication repairs from the receipt without re-execution |
| 6. Duplicate-submission protection | Unchanged (claim + in-transaction identity) but adoption may race a second engine execution | Unchanged and strictly safer: quiescence proves no execution remains, so no second execution can be racing adoption |
| 7. Receipt-finalization proof | Cannot be proven without adopting under a live producer | Same proof as today's Case B tail: verified evidence → `UnrealRenderReceipt.issue` → `store.publish_verified_receipt` (lease token + expected revision) → exactly one immutable receipt, 8 identity fields |
| 8. Containment proof | Weaker by construction (subset job) | Unchanged §9 predicate over the launch job; S1 already demonstrates 6 → 1 → 0 and job destruction on last handle close |
| 9. Evidence required | Live RPC evidence + redefined quiescence evidence | Durable journal file (schema, bound pair, terminal phase, ordinal, HMAC `entry_digest`), manifest re-hashed on disk, verified evidence class `ENGINE_JOURNAL_ATTESTED`, valid handle + `ActiveProcesses == 0`, zero-RPC proof for the adoption step |
| 10. Implementation surface | New containment hierarchy, new breakaway/ownership model, engine-side changes to spawn and report a worker job; redefinition in contract §9 | 1 new reader/validator module (mirrors the engine's disk scan), a small coordinator reorder + witness-source split, one candidate-normalization mapping, runbook/doc updates. No engine C++ change required |
| 11. Test surface | New hierarchy fixtures + engine-side tests + contract re-definition tests | Deterministic cases over the durable witness set + zero-RPC assertion + existing Case B/C/D/E/F/H/J/K suites retained |
| 12. Risks / new ambiguity | Vacuous in the common topology; adoption racing a live writer; silent-breakaway blind spot; contract redefinition ripples through every quiescence test | Journal-directory trust boundary (mitigated by nonce-keyed HMAC + path validation); no new ambiguity class beyond today's, since Case C/D/H/J adjudication is reproduced over the durable set |

**Conclusion of the comparison: A is invalid; B is valid.** Not "both", not "neither": the contract
already contains B's semantics, and A requires rewriting an invariant that exists for the exact
failure mode it would reintroduce.

---

## 8. F-S1-2 harness analysis

**Claim under test.** `planning/unreal_live_scenario_harness.py` models §33 scenarios with two
independently settable booleans (`:63` `engine_capable` = "transport reachable +
`assert_recovery_capable` passes"; `:67` `quiescent` = "supervisor reports Job Object quiescence (if
contained)"). S1 declares `engine_capable=True, quiescent=True` (`:87-105`); S4, S5, S6, S7 declare
the same pair (`:151-241`). The M9 harness stub forces quiescence with a fabricated handle
(`tests/m9/test_m9_scenario_harness.py:132`: `sv.job_handle = 4242`) and raises when
`engine_capable=False` (`:225`).

**Demonstration that the pair is unreachable under the production containment model.**

1. §9.272-274: Unreal is launched inside the Atlas Job Object; quiescence is that job's
   `ActiveProcesses == 0`.
2. Therefore `quiescent=True` ⟹ zero processes in the launch job ⟹ the engine process has exited.
3. The transport is a named pipe server hosted *by the engine process*
   (`\\.\pipe\AtlasUnrealTransport`). With the engine gone there is no server, so
   `assert_recovery_capable` must fail.
4. Therefore `engine_capable` must be `False` whenever `quiescent` is `True` under
   `CONTAINED_JOB_OBJECT`. The reachable set is `{(T,F), (F,F), (F,T)}`; `(T,T)` is impossible.
5. The live S1 run exhibits the two reachable boundary states: `(T,F)` → Case K hold, and
   `(F,T)` → WAITING_FOR_ENGINE hold. No live path produced `(T,T)`.

**Finding.** F-S1-2 is confirmed: the harness asserts an impossible live combination in 5 of the 8
§33 scenarios, so `engine_capable=True AND quiescent=True` scenarios never proved live reachability
of the Case B adoption path. This is the "fixture supplies what reality cannot" class: the harness's
green result is real for the *adoption logic* it exercises, but it silently assumed a deployment
state that containment forbids — which is exactly why the deadlock was invisible until the first
live run.

**Smallest correction to the test model (design only; faithful to Option B).**

Replace the two independent booleans with one declared containment state, and derive the flags:

```text
ContainmentState:
    deployment_mode: CONTAINED_JOB_OBJECT | UNCONTAINED_ATTACHED
    live_engine_present: bool          # engine process exists
    job_active_processes: int          # QueryInformationJobObject BasicAccounting

derived:
    quiescent     = (deployment_mode == CONTAINED_JOB_OBJECT and job_active_processes == 0)
    engine_capable = live_engine_present and (not quiescent)     # pipe server requires a live engine
```

and enforce the invariant as a harness-level assertion (a scenario that declares
`live_engine_present=True` with `job_active_processes == 0` for `CONTAINED_JOB_OBJECT` is rejected as
unreachable, with the reason printed). Consequences:

* **S1 (Case B) becomes faithful**: engine gone, `job_active_processes=0`, terminal durable journal →
  Case B from the journal-attested witness, with an added non-vacuity assertion that the coordinator
  performs **zero transport sends** during adoption (a raising transport makes this observable).
* **A new explicit scenario** (engine contained + alive + terminal journal, e.g. S1-K) asserts
  `Case K (Quiescence Blocked)` and no receipt — the invariant the deadlock currently protects.
* **S5 (render completes during an Atlas outage)** becomes the canonical Case B scenario, since it is
  the natural "prior session journal" case.
* S4/S6/S7 are re-declared under the corrected model (each keeps its intended semantics: quiescence
  blocked / attested-witness failure modes / etc.), and the existing Case C/D/E/F/H/J/K expectations
  are retained unchanged.

This keeps the intended Case B semantics (exactly one receipt, 8-field identity,
`ENGINE_JOURNAL_ATTESTED` evidence) and stops the model from asserting an impossible state.

---

## 9. Proposed target contract

**T1 — Adoption ordering (fixes F-S1-4).** Post-receipt, post-deadline ordering is:
(1) §9 quiescence gate → (2) witness acquisition → (3) identity/ordinal/HMAC/artifact verification →
(4) store-gated receipt publication. No engine interaction may precede the quiescence gate on the
adoption path.

**T2 — Two witness sources, one adoption path.**

```text
if engine reachable (same session, compatible schema):
        live catalog candidate          -> Case A (unchanged semantics)
else if quiescence satisfied AND a terminal FINISHED witness exists for the bound pair:
        durable journal witness         -> Case B (ENGINE_JOURNAL_ATTESTED)
else:
        Case C / Case D / Case J (unchanged)
```

The live catalog becomes an *enrichment*: when both a live catalog candidate and a durable witness
exist, they must agree on the bound identity and manifest; disagreement is Case H (fail closed).

**T3 — Durable witness set semantics (mirrors the engine scan).** Root =
`<ProjectDir>/AtlasWitnessJournal` (Atlas-designated, §10). Set status: no file for the bound pair →
Case C/D path; unparseable/truncated/partial → Case J; more than one *materially different*
execution claiming the same `atlas_job_id` → Case H; exactly one bound terminal record → adoptable.

**T4 — Witness normalization.** A durable journal entry is normalized to the coordinator's
candidate shape before the existing checks run (`unreal_job_id` → `job_id`, both names carried, as
`_bind_record_identity_to_observation` already does at `coordinator:627-630`). The normalization is
declared, tested, and must not synthesize any engine-witnessed field.

**T5 — Snapshot stability (§20 Step 7 without a live engine).** Snapshot A = journal file identity
(path, size, mtime, content digests) + parsed terminal record + manifest; then disk hashing; then
Snapshot B = re-derivation. A material change → `RECOVERY_PENDING` (Case J semantics).

**T6 — Unchanged.** I1-I12 in full, including §9's predicate and mode table, receipt identity and
single-publication, Case D non-mutation, Case H/J/E/F/G fail-closed behaviour, and the rule that
nothing may create synthetic success.

---

## 10. Required implementation changes (bounded — NOT performed here)

1. **New module** `planning/unreal_witness_journal_store.py` (name at implementer's discretion):
   resolve the Atlas journal root; enumerate candidates for a bound `(atlas_job_id, unreal_job_id)`;
   parse and validate schema (`journal_schema_version`), bound identity, terminal phase; expose the
   set status (absent / complete / partial-unreadable / conflict); canonical-path validation against
   the configured root; snapshot A/B derivation (T5). No HMAC logic here (it lives in
   `planning/unreal_journal_attestation.py` and is already used by the coordinator).
2. **`planning/unreal_render_recovery_coordinator.py`**: move the quiescence gate ahead of witness
   acquisition (T1); split Step 2/3 into "live witness attempt" + "durable witness fallback"
   (T2/T3); normalize the durable candidate (T4); leave ordinal/HMAC/artifact/verify/receipt code
   paths byte-for-byte equivalent in behaviour.
3. **`docs/LIVE_EXECUTION_CHECKLIST.md`**: state that reaching Case B requires the engine to be shut
   down and the Job Object to report 0 active processes before reconcile (the operator step the
   current runbook leaves implicit), and record F-ARM2-1 (create-suspended → assign → resume
   containment wording) while in the file.
4. **`docs/UNREAL_M7_HARDENING.md`** (or a new M7 addendum): document the durable witness source and
   the ordering change; note that Case B is a prior-session path by contract definition.
5. **No engine C++ change** is required: the journal is already written to the §10 path and the
   engine's own catalog is that disk scan.
6. **No changes** to `unreal_render_job_record.py`, `unreal_render_job_store.py`,
   `unreal_render_receipt*.py`, `unreal_evidence_contract.py`, `unreal_render_submission.py`,
   `unreal_live_preflight.py` (Phase A/B/C), or any Blender/Temporal module.

---

## 11. Required deterministic tests

New/updated tests (deterministic, no engine):

| # | Test | Must prove |
|---|---|---|
| 1 | Durable-witness Case B | quiescence satisfied + one terminal attested journal → Case B, `FINALIZED`, receipt published, `ENGINE_JOURNAL_ATTESTED` evidence |
| 2 | Zero-RPC adoption (non-vacuity) | during the Case B path the transport records **0** sends; a transport that raises on any call still yields Case B |
| 3 | Ordinal binding | journal ordinal ≠ record ordinal → `UNTRUSTED_WITNESS`, no receipt |
| 4 | HMAC binding | tampered `entry_digest`, replayed journal from another attempt, and wrong nonce → fail closed |
| 5 | Normalization fidelity | a journal entry carrying only `unreal_job_id` passes the binding check after normalization; a journal whose bound `unreal_job_id` differs → Case E/F |
| 6 | Ambiguity | two materially different journals for one `atlas_job_id` → Case H; truncated/unparseable journal → Case J; no journal and no artifacts → Case C; artifacts only → Case D (non-mutating) |
| 7 | Ordering (F-S1-4) | with a non-empty job the coordinator performs **no** inspection RPC and returns Case K; quiescence is evaluated before any witness query |
| 8 | Snapshot stability | a journal rewrite between snapshot A and B → `RECOVERY_PENDING`, no receipt |
| 9 | Mode table | `UNCONTAINED_ATTACHED` → never Case B (fail closed) |
| 10 | Single publication | double reconcile → exactly one receipt; receipt-first repair on restart issues no second execution/receipt |
| 11 | Deadline exhaustion | unresolved + expired → `EXHAUSTED`/`RECOVERY_FAILED`; the durable path must not resurrect it |
| 12 | Harness fidelity (F-S1-2) | the corrected scenario model rejects `(live_engine_present=True, job_active_processes=0)` for `CONTAINED_JOB_OBJECT`; the corrected S1 scenario asserts zero-RPC Case B; the Case K scenario still holds |

---

## 12. Required exact-live evidence

Recommended minimal path (operator decision; **no second render is required or authorized by this
document**): the adoption step can be re-gated on the *existing* frozen S1 evidence, because the
durable record is non-terminal, the witness is terminal/attested, and the artifacts are verified —
i.e. exactly the state §20's algorithm is written for.

| Item | Capture |
|---|---|
| Pinned revision | HEAD/tree at every checkpoint (`74898271…` / `b851438b…`) |
| Containment | valid handle to the launch job + `ActiveProcesses == 0` immediately before reconcile; job destroyed on last handle close |
| Adoption | the reconcile decision (`Case B`), with `case_classified` and both recovery statuses |
| Zero-RPC proof | transport send count == 0 during the adoption step |
| Receipt | exactly one receipt file; all 8 identity fields; `receipt_digest`; `attempt_ordinal` |
| Record | lifecycle/recovery transition to the finalized state; `receipt_reference` non-null; no `failure_reason` |
| Assets | 24/24 manifest re-hash (independent), journal schema 2 + `entry_digest` match, `ENGINE_JOURNAL_ATTESTED` evidence snapshot |
| Non-mutation | artifact hashes unchanged before/after adoption; no artifact moved/renamed/deleted |
| Negative control | a deliberately lossy control in the same rung (e.g. quiescence not satisfied, or a tampered manifest) must FAIL closed — the decisive proof is the positive case passing *and* the control failing |

Then, separately, S2-S8 remain as specified by the M7 gate (each with its own authorization), and the
record-only red-team review runs against the durable records, not the narrative.

---

## 13. Migration / recovery implications

* **Stuck records:** records parked in `WAITING_FOR_ENGINE` with a durable terminal attested witness
  and artifacts verified on disk become adoptable by the next reconcile, with the same checks and
  exactly one receipt. S1's record is the first such record; without this change it can never reach
  `FINALIZED`.
* **No re-execution:** adoption never submits; the nonce is not reused; the authorization remains
  bound to the original attempt.
* **Idempotence:** the receipt-first probe runs before adoption, so re-running reconcile after a
  crash repairs from the receipt instead of issuing a second one.
* **Terminal states stay terminal:** `RECOVERY_FAILED`, `EXHAUSTED`, `ORPHANED_ARTIFACTS_PRESENT`,
  `RECORD_CORRUPT` are not resurrected by the durable path (Case D's non-mutation invariant
  untouched).
* **Operator semantics change:** reaching Case B now *requires* the engine to be down and the launch
  job to report 0 — the runbook must say so explicitly (today it is implicit and was the source of
  F-ARM2-1 confusion).
* **Backward compatibility:** journals written before this change are readable (schema 2 is current;
  missing `attempt_ordinal`/`entry_digest` still fails closed as `UNSUPPORTED_LEGACY_WITNESS`).

---

## 14. Open questions

* **Q1** — Must the engine host ever be contained in a *different* job than the one whose quiescence
  Atlas checks? (If someone proposes this again, it re-opens Option A and must be refused per §5.)
* **Q2** — When the engine is reachable *and* the job is non-empty with a terminal journal, should
  Atlas ever adopt? (Proposed: no — Case K holds, as today.)
* **Q3** — What is the required hardening level for the journal directory (canonical-path/ACL
  validation against symlink or junction escape) before this path is considered final?
* **Q4** — Autonomous recovery must be able to reach `ActiveProcesses == 0` itself: does the
  supervisor need an explicit "terminate tree and wait for 0" step, or is handing the engine's exit
  to the operator acceptable for M7? (S1's containment already reaped 9 → 0 on last handle close.)
* **Q5** — Should the live catalog and the durable witness be cross-checked whenever both exist
  (T2's "must agree" rule), and is disagreement Case H or a new case?
* **Q6** — The S1 artifacts are 24 byte-identical frames. The contract requires 24 enumerated frames,
  not distinct content, so this is not a verification defect — but if per-frame variation is wanted as
  live evidence, that is a separate fixture/scenario item (not adoption).
* **Q7** — Should the contained process composition (names/PIDs) be recorded at launch as standing
  evidence, given S1 captured counts only?

---

## 15. Explicit implementation authorization boundary

This document authorizes **nothing**. A separate, explicit implementation authorization is required,
and when granted it may touch only:

* **Allowed:** a new durable-witness reader module under `planning/`; the witness
  acquisition/ordering/normalization changes inside
  `planning/unreal_render_recovery_coordinator.py`; the M9 harness model
  (`planning/unreal_live_scenario_harness.py` + `tests/m9/test_m9_scenario_harness.py`) for the
  F-S1-2 correction; the named test files for §11; `docs/LIVE_EXECUTION_CHECKLIST.md` and
  `docs/UNREAL_M7_HARDENING.md` (or an M7 addendum).
* **Forbidden:** weakening or redefining the §9 quiescence predicate; changing the receipt 8-field
  identity set or single-publication protocol; creating any synthetic success; modifying
  `unreal_render_submission.py` / job record / job store / receipt store / evidence contract
  semantics; any Blender or Temporal module; PR #105; the historical Unreal authority modules
  (`unreal_autonomous_execution_loop.py`, `unreal_authorized_execution_gate.py`,
  `unreal_production_autonomous_loop.py`, `unreal_production_controller_bridge.py`,
  `atlas_dev_controller/`); any engine C++ behaviour; any commit, PR, or merge without an explicit
  instruction.
* **Live actions:** adopting S1's frozen evidence, or any further S1/S2-S8 run, requires its own
  explicit operator authorization. No live action is implied by this design.

---

## Verdict

**DESIGN GATE CLEAR — CASE B CONTRACT DEFINED**

* **Option A (worker-scoped quiescence): REJECTED** — it redefines the §9 quiescence predicate,
  removes the containment's rationale (§9.268), is vacuous for the S1 in-editor render topology, and
  would permit adoption while the artifact producer is still live.
* **Option B (journal-attested adoption): VALID** — it is the contract's own Case B
  (§21:716-718 + §20:700-702 + §9:279 + §10:288-313), it does not weaken any invariant, and it is
  live-grounded: the durable journal exists at the §10 path, its HMAC verifies against the durable
  record's nonce, and the coordinator's own adoption checks pass on it (11/11 after normalization),
  stopping only at the deliberate non-execution of receipt publication.
* **F-S1-2: CONFIRMED** — `engine_capable=True AND quiescent=True` under `CONTAINED_JOB_OBJECT` is
  impossible (quiescence ⟹ engine exited ⟹ no pipe server), and 5 of 8 §33 scenarios assert that
  pair; the corrected containment-derived model is specified in §8.

**Recommended next exact implementation task (do not start without authorization):**
Implement Option B as one bounded rung — add the durable witness reader, reorder the quiescence gate
ahead of witness acquisition, add the live-catalog/durable-witness split with candidate
normalization, correct the M9 scenario model per §8, and add exactly the tests in §11 — then, under a
separate live authorization, re-gate S1's *adoption* step on the frozen evidence (no second render)
and capture the §12 evidence with its negative control.
