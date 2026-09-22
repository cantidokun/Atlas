# Atlas End-of-Night Handoff — September 21, 2026

> **Authoritative restart point for the next session.** Active workstream: **Unreal M7 Case-B durable-witness adoption.**
> Historical dated handoffs remain archival and must not be rewritten.
>
> **STATUS: IMPLEMENTATION REMEDIATION COMPLETE — AWAITING INDEPENDENT THIRD-PARTY REVIEW**
> **NEXT ACTION: AUTHOR-INDEPENDENT THIRD-PARTY REVIEW OF THE UNCOMMITTED DIFF**

## 1. Exact working state

| Item | Value |
| --- | --- |
| Worktree | `C:\Users\Gavin's PC\AppData\Local\Temp\atlas_m7_caseb` |
| Branch | `fix/unreal-m7-case-b-durable-witness` |
| Pinned base / current main | `748982713fb6042d875890cbd9999a3bbcbfb3aa` |
| Pinned tree | `b851438bdc1d7a03507b72776fa2116b94b5092e` |
| Commit state | **UNCOMMITTED and UNPUSHED.** No commit, no push, no PR, no merge. |
| Working-tree surface | 5 modified + 4 new paths (below); preserved intentionally |

The branch head equals the pinned main SHA exactly (no commits were made on this branch yet); the
entire implementation exists only as working-tree changes plus untracked new files.

Changed paths (9): `planning/unreal_render_recovery_coordinator.py`,
`planning/unreal_live_scenario_harness.py`, `tests/m9/test_m9_scenario_harness.py`,
`docs/LIVE_EXECUTION_CHECKLIST.md`, `docs/UNREAL_M7_HARDENING.md` (tracked diff **+928 / −405**);
new: `planning/unreal_witness_journal.py`, `tests/m9/test_m9_durable_witness_adoption.py`,
`tests/m9/test_m9_durable_witness_remediation.py`, `docs/design/M7_S1_ADOPTION_CASE_B_DESIGN.md`.
Plus this handoff and the status-document updates recorded in §8.

## 2. Exact M7 status

`EXACT-MAIN ARM GATE CLEAR` was re-established on the pinned main with 10/10 fail-closed SHA/tree
checkpoints, Phase A (11 gates, zero engine RPC) and Phase B capability negotiation green, and a
successful UE 5.6 build (`Target is up to date`, identical DLL hashes).

**S1 was submitted exactly once and the render itself succeeded:**

- engine accepted the submission; durable journal written by the engine;
- lifecycle `FINISHED`, `success=true`, `progress=1`;
- **24 PNG artifacts**, all 1280×720, IEND-complete, 16,170 B each (388,080 B total);
- **24/24 manifest sha256 + size match**, 0 mismatches;
- independent verification through the production path
  (`_bind_record_identity_to_observation` → `verify_render_job_evidence(...,
  evidence_source_class="ENGINE_JOURNAL_ATTESTED")`) = **`verified = true`**.

**Adoption was blocked (F-S1-1) and remains the open problem:** the engine is simultaneously the
liveness bearer and a member of the Job Object whose quiescence adoption requires, so reconcile
returned **Case K (`WAITING_FOR_ENGINE_QUIESCENCE`, no receipt)** while the engine lived, then
`WAITING_FOR_ENGINE` after it drained. **No receipt for the S1 job exists.**
F-S1-2 was named and confirmed: the M9 harness modelled the impossible
`engine_capable=True` + `quiescent=True` combination for a contained engine.

Contract resolution (design gate, verdict `DESIGN GATE CLEAR — CASE B CONTRACT DEFINED`,
`docs/design/M7_S1_ADOPTION_CASE_B_DESIGN.md`):

- **OPTION A (worker-scoped quiescence) — REJECTED.** §9 fixes the quiescence index as the launch
  Job Object, so a worker-scoped proof would be vacuous.
- **OPTION B (durable / journal-attested Case-B adoption) — the target contract.** §21 Case B is
  defined over a prior-session `ENGINE_JOURNAL_ATTESTED` journal; the engine's own catalog is
  itself a disk scan of the same directory, so reading it Atlas-side adds no authority.
- §9 quiescence is **not** weakened: `ActiveProcesses == 0` is established **before** any witness
  acquisition or terminal-artifact inspection.

## 3. Frozen S1 evidence status

The S1 evidence is **FROZEN and must not be regenerated or replaced**. It is the target evidence
for later adoption:

- record `atlas-render-job-d046bf30-ba5f-440a-9ce1-cbc7e2e11f67`;
- engine-minted `unreal_job_id F7BA777C-40EC-74F4-0F92-2BA361FF0DF8`;
- attempt ordinal `1`; `request_digest 98fd3d2d…d76fc4`; `config_digest 7ec95840…6a893ea`;
  `authoritative_digest 65efb0e2…5e2dcac2`;
- journal `<worktree>\unreal\AtlasUnrealHarness\AtlasWitnessJournal\`,
  `journal_schema_version 2`, `entry_digest 58b9301b467afb3604ce40e7123f55d80101a4ca98f65525bf209acb829e33ca`,
  phases ACCEPTED(1) → STARTED(2) → FINISHED(3), 24 manifest entries;
- authorization identity: bound as declared at the S1 gate record (value deliberately not
  reproduced in documents);
- 24 PNGs under the isolated M7 gate output root; no receipt.

## 4. B1–B4 remediation status — all FIXED in the working tree

| Blocker | Resolution |
| --- | --- |
| **B1** unreadable journal aborts reconcile | Every filesystem/parse touch in the reader is wrapped; an attributable-but-bad witness is classified `PARTIAL` → Case J. Proven for unreadable bytes (`PermissionError`), malformed, truncated, JSON-array bodies, and a §10-named file with no `atlas_job_id`; `reconcile_all_non_terminal_jobs` completes with an unreadable witness. **BAD JOURNAL ≠ PROCESS-WIDE ABORT.** |
| **B2** stray/retained/badly-named journal misroutes healthy live jobs | Reader rule changed, not a test expectation: candidates are **attributed first** (only files whose §10 logical-key filename names this `atlas_job_id`, or — for misnamed files — whose content does). Everything else is ignored and reported. Proven: foreign valid journal (other `atlas_job_id`), retained legacy schema-1 journal, unparseable unrelated JSON, badly-named junk → all ignored, healthy engine-attached job stays **Case A** with the live catalog consulted. Same `atlas_job_id` with a *different* `unreal_job_id` is **not** junk: it is scoped to this job and fails closed as **Case E/F**. |
| **B3** contradictory `job_id`/`unreal_job_id` adopted | `unreal_job_id` is authoritative for journals, `job_id` for the live catalog. Both present and different → `PARTIAL`, never `COMPLETE`/adoptable; neither present → `PARTIAL`. No "pick one and continue"; the identity resolver is shared by the reader, the binding check and the observation binder. All five combinations have explicit tests. |
| **B4** durable terminal FAILED not adjudicated offline | A durable **terminal** witness (FINISHED *or* FAILED) is adjudicated through the same adoption tail; FAILED fails closed to **Case G / FAILED, no receipt**, with zero engine RPCs and no new failure taxonomy. Proven with engine down, engine raising on any access, FAILED-with-manifest, and FAILED-with-non-quiescence (→ Case K). |

## 5. E3 documentation status — FIXED

- `docs/LIVE_EXECUTION_CHECKLIST.md` §7 no longer instructs deleting journal files; it now defines
  retention (never delete/truncate/rename/archive a journal while the job is non-terminal; another
  job's journal or junk must not be deleted either; archival only for terminal records with explicit
  operator authorization; archive artifacts only after adoption).
- The containment/M9 model text was corrected: a contained engine makes `engine_capable=True` and
  `quiescent=True` mutually exclusive; the real ordering (render → durable terminal journal →
  engine exit → `ActiveProcesses == 0` → Case B from the durable witness) is documented, with a
  table separating live engine evidence / durable witness / quiescence proof / verification /
  receipt.
- `docs/UNREAL_M7_HARDENING.md` gained a "Durable-witness adoption (Case B)" section: witness
  sources, the `journal_root` opt-in and the absence of production wiring, §9-first ordering, the
  fail-closed reader contract, the journal lifecycle assumption, and the explicit deferral of
  Q4/Q8/Q5.
- `docs/design/M7_S1_ADOPTION_CASE_B_DESIGN.md` §6.2 was corrected: the durable reader is a
  **stricter filter over the same bytes**, not an identical reader — with a bounded comparison table
  (attribution scope, filename rules, schema handling, PARTIAL classification, snapshot stability,
  identity, failure containment).

## 6. Exact validation results (this revision)

Deterministic (no Blender-gated tests included):

```
env -u ATLAS_RUN_LIVE_BLENDER pytest -q tests/m7 tests/m8 tests/m9 tests/m10
  -> 266 passed, 0 failed, 0 skipped, 2.84 s        (was 241 before remediation)

env -u ATLAS_RUN_LIVE_BLENDER pytest -q -m "not integration"
  -> 4350 passed, 0 failed, 136 skipped, 13.07 s    (was 4325 / 136)
```

Live-path differential against the pinned base coordinator (base loaded from
`git show 74898271:planning/unreal_render_recovery_coordinator.py`; script
`%LOCALAPPDATA%\Temp\rt_diff_livepath.py`):

```
journal_root UNSET : 12 scenarios -> 0 decision-level deltas
journal_root SET, no relevant witness : 4 scenarios -> identical to base
```

The 12 scenarios include both previously discovered **accidental** live-path semantic changes —
a live candidate with a different `authorization_id` (was Case E/F, now **Case A = base**) and a
live candidate carrying only `unreal_job_id` (was Case A, now **Case E/F = base**) — plus
A / C / D / E-F / G / H / J / WAITING_FOR_ENGINE, live Case B (adopted, 1 receipt) and Case K.

Rehearsal on **copies** of the frozen S1 evidence (script `%LOCALAPPDATA%\Temp\arm4_caseb_rehearsal.py`):
Case B reached, exactly 1 receipt, receipt-first repair on the second reconcile, and the frozen
original (store / journal / artifacts / non-terminal record / absent receipt) verified unchanged.

## 7. Live blockers (NOT commit-gate implementation defects)

1. **Production Case-B wiring is absent.** No non-test caller supplies `journal_root`; the
   preflight's `journal_location` gate only validates a path string. Live Case-B is therefore still
   **inert in production**: the capability is reachable only when a caller passes the §10 root.
2. **Real quiescence / Job Object recovery is absent.** The repository provides no
   `OpenJobObjectW` by name, no Job Object reattachment and no terminate-and-wait recovery API;
   job objects are created **unnamed**, and a fresh empty job would make the predicate vacuous. The
   S1 run proved in-session containment/quiescence behaviour, but the original Job Object cannot be
   re-established after the original launcher/handle is gone. **This remains the live-adoption
   blocker.** Q4/Q8 are explicitly not implemented.
3. Standing, non-blocking: F-ARM2-1 (containment runbook wording), F-ARM2-2 (probe log noise),
   F-S1-3 (stale `failure_reason` breadcrumb), Q5 (live catalog vs durable witness agreement),
   B5 (directory-count stability), F-RT-1/F-RT-3/F-RT-5 residual/F-RT-6.

## 8. Third-party review status

- Review 1 (`deepseek-v4-pro`) and review 2 (`deepseek-chat`), each run in a **separate Hermes
  process with no access to the author's context**, both returned **THIRD-PARTY BLOCKED** on the
  pre-remediation revision (B1–B4 + E3). That verdict stands for that revision.
- The remediation above answers those blockers, but **no independent review of the remediated diff
  has happened yet**: another independent model was unavailable at the end of this session.
- Independence limitation, recorded honestly: the two rounds are independent in model and context
  but **same provider** (OpenRouter credits were exhausted, so no cross-vendor reviewer was
  available).
- The author's own verdicts are **not** independent evidence and must be treated as claims to
  challenge.

## 9. Documentation updated tonight

`ATLAS_HANDOFF_CURRENT.md`, `ATLAS_HANDOFF_CONTEXT.txt`, `UNREAL_AGENT_HANDOFF_CURRENT.md`,
`README.md`, `DEVELOPMENT_LOG.md`, `docs/UNREAL_M9_READINESS.md` (dated status correction),
`docs/UNREAL_M6_TEST_STATUS.md` (dated one-line correction), plus this file.
`planning/blender/README.md` was inspected and left unchanged (already accurate: Blender track
maintained/frozen; Temporal implemented/merged).

## 10. Next session

**NEXT ACTION: AUTHOR-INDEPENDENT THIRD-PARTY REVIEW OF THE UNCOMMITTED DIFF**

1. Independent third-party review of the exact uncommitted diff (head
   `748982713fb6042d875890cbd9999a3bbcbfb3aa`, tree `b851438bdc1d7a03507b72776fa2116b94b5092e`),
   including `tests/m9/test_m9_durable_witness_remediation.py` and a re-run of
   `%LOCALAPPDATA%\Temp\rt_diff_livepath.py`.
2. If CLEAR → commit.
3. Run CI on the committed revision.
4. Complete production `journal_root` wiring.
5. Resolve/implement the required real quiescence / Job Object recovery mechanism.
6. Perform a **separate live adoption gate** against the frozen S1 evidence.
7. Do **not** render a second S1 unless a new authorization is explicitly required.

## 11. DO NOT (this pause)

- Do not modify implementation code or tests without a new authorized rung.
- Do not commit, push, create a PR, or merge.
- Do not run live Unreal, submit a render, or run Blender-gated tests.
- Do not implement Q4/Q8 (or any supervisor reattachment work) in this rung.
- Do not touch Temporal, PR #105, or historical Unreal authority paths
  (`planning/unreal_autonomous_execution_loop.py`, `planning/unreal_authorized_execution_gate.py`,
  `planning/unreal_production_autonomous_loop.py`,
  `planning/unreal_production_controller_bridge.py`, `atlas_dev_controller/`).
- Do not delete, move or regenerate the frozen S1 journal, artifacts, record or receipt state.
- Do not weaken the §9 quiescence invariant, identity binding, HMAC/coupling checks, artifact
  verification, duplicate protection, or receipt semantics.

## 12. Second render

**No second S1 render is authorized or needed at this point.** The existing frozen S1 render is
the target evidence for Case-B adoption; a re-render would invalidate the frozen evidence chain and
is not required to close this workstream.

## Other tracks (unchanged boundaries)

- **Blender track — CLOSED** for the current declared contract (Blender Extraction Fidelity v1
  CLEAR/frozen; PR #128 and PR #129 merged, the latter as `0b8b4ba6`). Reopen only for a concrete,
  independently evidenced correctness defect.
- **Temporal — frozen/closed** at its current approved boundary.
- Unreal **M11** frozen; **M12.1–M12.4** implemented, **M12.5** deferred; M13.8/token optimization
  paused.

## Resume one-liner

Resume by running the **author-independent third-party review of the uncommitted
`fix/unreal-m7-case-b-durable-witness` diff** at tree `b851438bdc1d7a03507b72776fa2116b94b5092e`;
commit only after that review returns CLEAR.
