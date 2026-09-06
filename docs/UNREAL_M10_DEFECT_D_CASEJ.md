# M10 Remediation — Defect D (S4): Torn/Non-Terminal Witness misclassified as Case G

## Live defect (S4 s4b run, job 899e6a81)

A genuine S4 dual-restart (Atlas restart + Unreal restart) produced a torn
non-terminal witness journal:

- engine killed mid-render at phase `ACCEPTED(1)` only
  (`finished=False`, `status=submitted`, `phase=ACCEPTED`, `phase_sequence=1`,
  empty output manifest / output_files, empty output dir).

The restarted Atlas reconciled the torn job against the restarted Unreal engine
and the coordinator classified it:

    case:            Case G
    lifecycle:       SUBMITTED -> FAILED   (TERMINAL!)
    recovery:        NONE -> NONE
    failure_reason:  "Engine claims FINISHED but manifest and output_files are empty"
    receipt:         None

But the witness journal does NOT claim FINISHED (last phase is ACCEPTED,
non-terminal). Contract V1 §19 **Case J** governs torn/partial/unreadable
journals:

    ### Case J — Journal is unreadable or partial
    Treat as unknown, not absent.
    Enter bounded RECOVERY_PENDING; after the defined deadline/budget, terminate
    as RECOVERY_FAILED.

The S4 harness spec (`planning/unreal_live_scenario_harness.py`) requires for a
PARTIAL/torn job:

    expected_case                   = "Case J"
    expected_lifecycle_after        = SUBMITTED
    expected_recovery_status_after  = RECOVERY_PENDING
    receipt_permitted               = False
    retry_forbidden                 = True

The coordinator instead drove a torn, non-terminal job to TERMINAL FAILED — an
(Atlas-durable=FAILED) vs (engine-journal=non-terminal ACCEPTED) contradiction.
This is a recovery-rule classification defect.

## Root cause (precise)

`planning/unreal_render_recovery_coordinator.py`, dispatch in
`reconcile_single_job` (~line 404-407):

- A candidate that is NOT a live `in_memory_registry` entry was unconditionally
  routed to `_handle_finished_candidate(...)` (the "finished" terminal path).
- `_handle_finished_candidate` then hit its empty-manifest branch (~line 716-734),
  which ALWAYS transitions to terminal `FAILED` (Case G) with the message
  "Engine claims FINISHED but manifest and output_files are empty" — WITHOUT first
  checking that the recovered witness journal actually IS terminal/finished.

So a torn/non-terminal journal (which never reached FINISHED) was treated as a
"finished candidate" and terminally failed purely because artifact fields were
empty. The precedence error: the classifier assumes "not live in-memory ⇒
finished", which is false for a torn/persisted non-terminal witness.

## Contract rule being enforced

- **Case J** applies when the recovered witness journal is NON-TERMINAL
  (torn / interrupted / partial: `finished=False`, phase ACCEPTED or STARTED,
  status submitted/rendering). Outcome: **RECOVERY_PENDING**, non-terminal
  lifecycle, ambiguity incremented, NO receipt, NO retry, NO synthetic success.
- **Case G** applies ONLY to a genuinely TERMINAL FINISHED candidate
  (`finished=True` or phase FINISHED/FAILED) whose declared artifacts are
  missing/corrupt/empty. Outcome remains fail-closed terminal **FAILED**, no
  receipt. Case G semantics are unchanged.

## Production fix (smallest, targeted)

Added a terminality guard before the finished-candidate path, plus a small
`_candidate_is_terminal` helper:

- If the candidate is NOT terminal -> transition to
  `RECOVERY_PENDING` + increment ambiguity, classify **Case J**, no receipt, no
  retry, non-terminal lifecycle, journal left as evidence (unmodified).
- If the candidate IS terminal -> unchanged path to `_handle_finished_candidate`
  (Case B receipt / Case G artifact-fail / verify). Genuine Case G still fails
  closed.

Not changed: Atlas authority (single authority path kept), no second scheduler,
no auto-retry, no synthetic success, no journal rewrite, HMAC + phase-history
validation preserved, artifact-verification semantics preserved, corruption /
quarantine protections preserved. Case G semantics unchanged.

## Deterministic regression tests (new module)

`tests/m10/test_m10_case_j_torn_journal.py` — 9 tests:

- terminality rule: torn ACCEPTED/STARTED -> `_candidate_is_terminal` False;
  FINISHED/FAILED -> True.
- torn ACCEPTED at the S4 dual-restart boundary -> **Case J**, SUBMITTED
  (non-terminal), RECOVERY_PENDING, no receipt, no FAILED.
- torn STARTED -> Case J / RECOVERY_PENDING.
- no retry occurs (coordinator never issues submit/re-submit; no new attempt).
- no synthetic success; journal stays evidence, lifecycle not advanced to
  terminal.
- ambiguity incremented.
- genuine terminal FINISHED + empty manifest STILL Case G -> FAILED (unchanged).
- genuine terminal FINISHED + valid artifacts STILL Case B -> FINALIZED + receipt
  (normal success path preserved).

Focused run: **9 passed**.
Adjacent suites (m10 incl. these 9, m9, m8, m7, m6, coordinator): **263 passed**.
Full deterministic `pytest -m "not integration"`: **1198 passed**
(1189 baseline + 9 new, no regressions).

## Explicit confirmation

- NO live scenario was re-run during this remediation.
- NO live UnrealEditor was launched for this remediation (deterministic only).
- No workflow/action-runner tests run; Blender untouched.
- No production code weakened; no contract reinterpretation; Case G unchanged.
- Existing live S4 s4b evidence (job 899e6a81) preserved unchanged.