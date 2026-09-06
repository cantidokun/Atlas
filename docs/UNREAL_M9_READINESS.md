# Milestone 9 — Live Recovery Readiness & Scenario Harness (PRE-FLIGHT)

## Status

**PRE-FLIGHT ONLY. NO LIVE SCENARIO HAS BEEN EXECUTED.**

M9 prepares Atlas for the *first authorized* live execution of Contract V1 §33
Scenarios 1–8 without running any live scenario. It does NOT launch UnrealEditor,
does NOT run a live render, does NOT kill/restart Unreal, does NOT run the M7
Scenarios, does NOT run workflow/action-runner tests, and does NOT touch Blender.

## What M9 adds

1. **Deterministic scenario harness** (`planning/unreal_live_scenario_harness.py`)
   modeling Scenarios 1–8 as declarative specs (initial state, process/session
   condition, journal condition, artifact condition, quiescence, expected case,
   expected lifecycle/recovery_status, receipt/finalization/retry permissions).
   Every spec is driven through the REAL `UnrealRenderRecoveryCoordinator` with
   faked transport/supervisor seams; tests/m9 assert the declared outcome equals
   the coordinator's actual decision — so the harness is a faithful model of the
   implemented recovery path, not invented semantics.
2. **Pre-flight checks** (`planning/unreal_live_preflight.py`, `LivePreflight`)
   covering the P1–P14 gates: UE 5.6 project, capability schema, journal location,
   output isolation, receipt store, session identity, contained Job Object mode,
   supervisor/quiescence, authorization continuity, attempt_nonce handling,
   attempt_ordinal propagation, HMAC verification, artifact hashing/PNG, clean
   recovery-store state. `all_pass()` / `blockers()`.
3. **Live execution checklist** (`docs/LIVE_EXECUTION_CHECKLIST.md`): setup
   prerequisites, exact order of operations, evidence per gate, PASS/FAIL/STOP
   definitions, cleanup, and no-accidental-retry/resubmission rules.
4. **Safety-proof tests** (tests/m9): prove the harness cannot authorize a render,
   resubmit an uncertain job, synthesize success, mint a receipt without verified
   evidence, bypass quiescence, or bypass HMAC/attempt_ordinal verification.

## Scenario 1–8 readiness matrix

| Scenario | Contract Case | Preconditions | Harness Verified | Live Dependency | Stop Conditions | Status |
|----------|---------------|---------------|------------------|-----------------|------------------|--------|
| S1 Normal render | Case B | SUBMITTED + COMPLETE journal + FINISHED candidate + disk artifact + quiescent | Yes (Case B, FINALIZED, 1 receipt) | Real UE 5.6 MRQ renders the file + writes matching {path,size,sha256} manifest | Receipt missing or >1 | **READY_FOR_LIVE** |
| S2 Unreal restart during render | WAITING_FOR_ENGINE (engine down) | SUBMITTED + engine unreachable | Yes (engine-unavailable branch) | Real UE crash → exact journal state (ACCEPTED/STARTED) | Any receipt; any retry | **BLOCKED** (live sub-cases need real journal) |
| S3 Atlas restart during render | Case A (re-attach) | SUBMITTED + live in-flight candidate | Yes (Case A, RENDERING, no receipt) | Real in-flight engine state surviving Atlas restart | Duplicate submission; any receipt | **NOT_PROVEN** (needs live mid-render restart) |
| S4 Both restart during render | Case J | SUBMITTED + PARTIAL/unreadable journal | Yes (Case J, RECOVERY_PENDING, ambiguity++) | Real mid-render torn journal on disk | Any receipt; any retry | **BLOCKED** (needs real torn journal) |
| S5 Render finishes while Atlas down | Case B | SUBMITTED + preserved FINISHED journal + artifact + quiescent | Yes (Case B, FINALIZED, 1 receipt) | Real 5.6 journal survives in AtlasWitnessJournal/ across the outage | Receipt missing/duplicate | **READY_FOR_LIVE** |
| S6 Artifact, no engine evidence | Case D | SUBMITTED + artifact on disk + no journal | Yes (Case D, ORPHANED_ARTIFACTS_PRESENT, no receipt) | Real bare artifact bytes with no journal | Any receipt; synthetic terminal flags | **READY_FOR_LIVE** |
| S7 Missing artifact after terminal claim | Case G | SUBMITTED + FINISHED journal + artifact absent | Yes (Case G, FAILED, no receipt) | Real terminal journal with absent declared manifest path | Any receipt | **READY_FOR_LIVE** |
| S8 Ambiguous duplicate/stale identity | Case H | SUBMITTED + two journals same atlas_job_id | Yes (Case H, RECOVERY_FAILED, no receipt) | Real two journals for one job id on disk | Artifact adoption; any receipt | **BLOCKED** (needs real duplicate journals) |

Status legend: **READY_FOR_LIVE** = harness-verified case/outcome + only the real UE
runtime remains unproven; **BLOCKED** = the live outcome depends on journal/session
states only observable by actually running the restart, so readiness cannot be
certified from the harness alone; **NOT_PROVEN** = requires an in-flight live state.

## Remaining live dependencies (for the authorized run)

- Real UE 5.6 editor process hosting `AtlasTransportServer` (present at
  `C:/Program Files/Epic Games/UE_5.6`).
- Real MRQ render that produces the declared output bytes + {path,size,sha256}.
- Real durable journal persistence in `<ProjectDir>/AtlasWitnessJournal/`.
- Real Windows process-incarnation identity (GetProcessTimes).
- Real contained Job Object quiescence hold + supervisor accounting.
- Real authorized submission through `UnrealRenderSubmissionService` + clean store.

## Live-transition-boundary audit (what is safe deterministically but still unproven)

The deterministic tests exercise the coordinator's full decision logic via faked
transport/supervisor seams. The following are SAFE deterministically but NOT yet
proven against the real UE 5.6 editor/process runtime:

1. **`UnrealAdapterProduction.get_capabilities()` / named-pipe transport against a
   real editor process.** In tests a MagicMock stands in; the actual Windows named
   pipe (`\\.\pipe\AtlasUnrealTransport`) handshake with a real 5.6 process is
   unproven in this milestone (only exercised by a prior stage-17 live proof, not
   the recovery path).
2. **`evaluate_process_quiescence` with a REAL Job Object.** Tests use a
   `MagicMock(spec=AtlasProcessSupervisor)` whose `query_active_processes()` is
   scripted. The real `AtlasProcessSupervisor` binding (`CreateJobObject`,
   `AssignProcessToJobObject`, `QueryInformationJobObject`) against a real UE
   process tree is unproven — the Job Object is the central "contained descent"
   quiescence proof and requires a live hold.
3. **Windows `GetProcessTimes` process incarnation identity.** Tests model the
   origin fields as constants. The real capture of `process_creation_time_utc` from
   a live UE process, and the coordinator's equality check against the durable
   record, are unproven at runtime.
4. **The journal's durable atomic write + `FlushFileBuffers` + rename** against a
   real filesystem under load (mid-render kill) is only compile-verified; the exact
   torn-journal bytes after a hard `kill -9` are a live observation (S2/S4).
5. **C++ automation tests** (`AtlasUE56RenderJobBoundaryTest.cpp`, the M8
   `FAtlasUE56JournalAttestationVectorTest`) are **compile-verified only**; they are
   never executed under the editor in this milestone. Their runtime assertions are
   mirrored in Python (tests/m8, tests/m9) but the native execution is itself
   unproven until a live `UnrealEditor-Cmd.exe -ExecCmds=Automation RunTests` run.
6. **Actually rendering a file** (S1/S5) — the real MRQ output bytes feeding
   `verify_png_completeness` and the HMAC'd manifest are unproven for the recovery
   path; prior Stage-17 proof covers a different (non-restart) path.
7. **Deadline enforcement against a real clock/session** — injectable `now_utc` is
   deterministic in tests; the real wall-clock expiry path is untested live.

None of these gaps is a deterministic-test gap; each is a genuine live-only
prerequisite. That is exactly why S2/S3/S4/S8 are BLOCKED and why the live run must
be human-authorized per §33.

## Deterministic validation (final tree)

- `tests/m9/`: 34 (24 scenario-harness + 10 pre-flight/safety).
- `tests/m6/`: 79, `tests/m7/`: 59, `tests/m8/`: 19.
- Core Unreal recovery/evidence/submission/receipt suites: 129.
- Full `pytest -m "not integration"`: 1141 passed.
- No C++ changes in M9 → UBT not required (no rebuild performed).

## Explicit confirmation

- **UnrealEditor was NOT launched.**
- **No M7 Scenarios 1–8 were executed.**
- **No live Unreal render, kill/restart, workflow/action-runner test, or Blender**
  was performed.
- The harness and pre-flight checks are deterministic and non-mutating; they only
  model what the coordinator will decide (and prove they cannot side-effect a real
  render or store).