"""M9 — Live Recovery Readiness & Scenario Harness.

PRE-FLIGHT ONLY. This module deterministically models Contract V1 §33 Scenarios
1-8 against the *real* `UnrealRenderRecoveryCoordinator` using faked transport /
supervisor / receipt-store seams. It does NOT and cannot launch Unreal, run a live
render, kill/restart an engine, execute the M7 live Scenarios, run workflow/
action-runner tests, or touch Blender.

The harness's job is to SHOW what the coordinator will decide when the durable
record, engine journal, process/session condition, and artifact condition take a
given shape — so a human can authorize (or refuse) the corresponding live run with
predictable expectations. It is not a substitute for live validation.

Safety properties the harness itself enforces (mirrored in tests/m9):
- It never constructs an authorized render or submission (it only drives the
  RECOVERY path; submission requires UnrealRenderSubmissionService which is never
  invoked by the harness).
- It cannot resubmit an uncertain job (no path in the harness calls submit).
- It cannot synthesize success (evidence only becomes verified through
  verify_render_job_evidence on real disk bytes + HMAC).
- A receipt is created only via store.publish_verified_receipt, which requires
  verified evidence (Case B only).
- It cannot bypass quiescence (the coordinator's Case K gate runs first).
- It cannot bypass HMAC / attempt_ordinal verification (the M8 gates run inside
  _handle_finished_candidate before any artifact/evidence processing).
"""
from __future__ import annotations

import dataclasses
import enum
import pathlib
from typing import Any, Callable, Dict, List, Optional, Tuple

from planning.unreal_render_job_states import (
    RenderJobLifecycleState,
    RenderJobRecoveryStatus,
)


class ScenarioOutcome(str, enum.Enum):
    FORBIDDEN_RECEIPT = "FORBIDDEN_RECEIPT"
    FORBIDDEN_RETRY = "FORBIDDEN_RETRY"
    PERMITTED_RECEIPT = "PERMITTED_RECEIPT"
    EXPLICITLY_NO_RECEIPT = "EXPLICITLY_NO_RECEIPT"
    NO_SYNTHETIC_SUCCESS = "NO_SYNTHETIC_SUCCESS"


@dataclasses.dataclass(frozen=True)
class ScenarioSpec:
    """Declarative spec for one Contract V1 §33 live scenario (harness model).

    Fields describe the conditions the harness sets up and the EXACT reconciliation
    outcome Atlas is expected to produce. The harness asserts every field matches
    the real coordinator's decision.
    """

    scenario_id: str
    title: str
    description: str

    # Condition the harness establishes (model of the live world).
    initial_lifecycle: RenderJobLifecycleState
    engine_capable: bool  # transport reachable + assert_recovery_capable passes
    journal_condition: str  # COMPLETE | PARTIAL | UNREADABLE | NONE
    candidate_known_jobs: List[Dict[str, Any]]  # what reconcile returns
    disk_artifacts: bool  # whether output directory contains files
    quiescent: bool  # whether supervisor reports Job Object quiescence (if contained)

    # Expected outcome.
    expected_case: str
    expected_lifecycle_after: RenderJobLifecycleState
    expected_recovery_status_after: RenderJobRecoveryStatus
    receipt_permitted: bool
    retry_forbidden: bool
    status: str  # READY_FOR_LIVE | BLOCKED | NEEDS_HUMAN_INPUT | NOT_PROVEN

    # Reason this scenario is (or is not) deterministically harness-verifiable.
    harness_note: str


# The eight Contract V1 §33 scenarios. `expected_*` fields are the authoritative
# mapping; `candidate_known_jobs`/`disk_artifacts`/`quiescent` are the harness
# conditions that deterministically produce them. The harness executes each against
# the real coordinator and asserts the outcomes below.
SCENARIOS: Tuple[ScenarioSpec, ...] = (
    ScenarioSpec(
        scenario_id="S1",
        title="Normal render",
        description="submit -> render -> finish -> verify -> receipt -> provenance",
        initial_lifecycle=RenderJobLifecycleState.SUBMITTED,
        engine_capable=True,
        journal_condition="COMPLETE",
        candidate_known_jobs=[],
        disk_artifacts=True,
        quiescent=True,
        expected_case="Case B",
        expected_lifecycle_after=RenderJobLifecycleState.FINALIZED,
        expected_recovery_status_after=RenderJobRecoveryStatus.RESOLVED,
        receipt_permitted=True,
        retry_forbidden=True,
        status="READY_FOR_LIVE",
        harness_note="Fully deterministic. Valid FINISHED journal + matching disk "
        "artifact + quiescence + HMAC/attempt_ordinal pass -> Case B receipt. "
        "Live dependency: real UE MRQ must actually render the file and write the "
        "matching {path,size,sha256} manifest.",
    ),
    ScenarioSpec(
        scenario_id="S2",
        title="Unreal restart during render",
        description="Kill Unreal during a multi-frame render.",
        initial_lifecycle=RenderJobLifecycleState.SUBMITTED,
        engine_capable=False,
        journal_condition="NONE",
        candidate_known_jobs=[],
        disk_artifacts=False,
        quiescent=False,
        expected_case="WAITING_FOR_ENGINE",
        expected_lifecycle_after=RenderJobLifecycleState.SUBMITTED,
        expected_recovery_status_after=RenderJobRecoveryStatus.WAITING_FOR_ENGINE,
        receipt_permitted=False,
        retry_forbidden=True,
        status="BLOCKED",
        harness_note="Deterministic only up to the transport/engine-down branch "
        "(WAITING_FOR_ENGINE). The live sub-cases (crash mid-ACCEDED vs mid-STARTED "
        "vs mid-FINISHED) differ in whether a retained partial journal exists; "
        "requires a live restart to observe. Harness models the engine-unavailable "
        "precondition; exact journal-state-dependent branches need live evidence.",
    ),
    ScenarioSpec(
        scenario_id="S3",
        title="Atlas restart during render",
        description="Unreal continues rendering while Atlas restarts.",
        initial_lifecycle=RenderJobLifecycleState.SUBMITTED,
        engine_capable=True,
        journal_condition="COMPLETE",
        candidate_known_jobs=[],  # live, not yet terminal -> Case A handled below
        disk_artifacts=False,
        quiescent=False,
        expected_case="Case A",
        expected_lifecycle_after=RenderJobLifecycleState.RENDERING,
        expected_recovery_status_after=RenderJobRecoveryStatus.NONE,
        receipt_permitted=False,
        retry_forbidden=True,
        status="NOT_PROVEN",
        harness_note="Requires a live in-flight (non-terminal) engine state that "
        "survives Atlas restart. The deterministic model asserts the coordinator "
        "re-attaches to an existing journal without duplicate submission, but the "
        "'no duplicate execution' guarantee needs a live mid-render restart.",
    ),
    ScenarioSpec(
        scenario_id="S4",
        title="Both restart during render",
        description="Kill both processes mid-render.",
        initial_lifecycle=RenderJobLifecycleState.SUBMITTED,
        engine_capable=True,
        journal_condition="PARTIAL",
        candidate_known_jobs=[],
        disk_artifacts=False,
        quiescent=True,
        expected_case="Case J",
        expected_lifecycle_after=RenderJobLifecycleState.SUBMITTED,
        expected_recovery_status_after=RenderJobRecoveryStatus.RECOVERY_PENDING,
        receipt_permitted=False,
        retry_forbidden=True,
        status="BLOCKED",
        harness_note="Deterministic for the PARTIAL/unreadable-journal branch "
        "(Case J -> RECOVERY_PENDING, ambiguity increment, no receipt). The exact "
        "mid-render journal torn state ('which phases were durably flushed') is a "
        "live observation; harness models the fail-closed decision.",
    ),
    ScenarioSpec(
        scenario_id="S5",
        title="Render finishes while Atlas is unavailable",
        description="Preserved terminal Unreal attestation allows later verification.",
        initial_lifecycle=RenderJobLifecycleState.SUBMITTED,
        engine_capable=True,
        journal_condition="COMPLETE",
        candidate_known_jobs=[],  # FINISHED journal + artifact, Atlas was down
        disk_artifacts=True,
        quiescent=True,
        expected_case="Case B",
        expected_lifecycle_after=RenderJobLifecycleState.FINALIZED,
        expected_recovery_status_after=RenderJobRecoveryStatus.RESOLVED,
        receipt_permitted=True,
        retry_forbidden=True,
        status="READY_FOR_LIVE",
        harness_note="Deterministic: a preserved FINISHED journal attestation + "
        "matching disk artifact + quiescence + HMAC -> Case B receipt on later "
        "reconcile. Live dependency: the UE 5.6 journal must actually survive in "
        "<ProjectDir>/AtlasWitnessJournal/ across the Atlas outage.",
    ),
    ScenarioSpec(
        scenario_id="S6",
        title="Artifact exists but no attributable engine terminal evidence",
        description="ORPHANED_ARTIFACTS_PRESENT; no receipt, no production lineage.",
        initial_lifecycle=RenderJobLifecycleState.SUBMITTED,
        engine_capable=True,
        journal_condition="NONE",
        candidate_known_jobs=[],
        disk_artifacts=True,
        quiescent=True,
        expected_case="Case D",
        expected_lifecycle_after=RenderJobLifecycleState.ORPHANED_ARTIFACTS_PRESENT,
        expected_recovery_status_after=RenderJobRecoveryStatus.NONE,
        receipt_permitted=False,
        retry_forbidden=True,
        status="READY_FOR_LIVE",
        harness_note="Deterministic and strict: bare artifacts with zero engine "
        "witness -> ORPHANED_ARTIFACTS_PRESENT, strictly non-mutating, no receipt, "
        "no synthetic terminal flags. Live dependency: real artifact bytes on disk "
        "with no journal entry.",
    ),
    ScenarioSpec(
        scenario_id="S7",
        title="Missing artifact after terminal engine claim",
        description="FAILED; receipt issuance blocked.",
        initial_lifecycle=RenderJobLifecycleState.SUBMITTED,
        engine_capable=True,
        journal_condition="COMPLETE",
        candidate_known_jobs=[],  # FINISHED claim, but artifact missing on disk
        disk_artifacts=False,
        quiescent=True,
        expected_case="Case G",
        expected_lifecycle_after=RenderJobLifecycleState.FAILED,
        expected_recovery_status_after=RenderJobRecoveryStatus.NONE,
        receipt_permitted=False,
        retry_forbidden=True,
        status="READY_FOR_LIVE",
        harness_note="Deterministic: engine attests FINISHED with a manifest whose "
        "declared output file is absent on disk -> Case G FAILED, receipt blocked. "
        "Live dependency: a terminal journal whose manifest path is not on disk.",
    ),
    ScenarioSpec(
        scenario_id="S8",
        title="Ambiguous duplicate/stale execution identity",
        description="RECOVERY_FAILED; no artifact adoption.",
        initial_lifecycle=RenderJobLifecycleState.SUBMITTED,
        engine_capable=True,
        journal_condition="COMPLETE",
        candidate_known_jobs=[],  # two candidate journal entries same atlas_job_id
        disk_artifacts=True,
        quiescent=True,
        expected_case="Case H",
        expected_lifecycle_after=RenderJobLifecycleState.RECOVERY_FAILED,
        expected_recovery_status_after=RenderJobRecoveryStatus.NONE,
        receipt_permitted=False,
        retry_forbidden=True,
        status="BLOCKED",
        harness_note="Deterministic for the duplicate-claim branch: two Unreal "
        "executions for one atlas_job_id -> Case H RECOVERY_FAILED, no adoption. "
        "Live dependency: actually producing two journals for the same job id to "
        "observe the real conflict on disk.",
    ),
)


def scenario_by_id(scenario_id: str) -> ScenarioSpec:
    for spec in SCENARIOS:
        if spec.scenario_id == scenario_id:
            return spec
    raise KeyError(f"unknown scenario: {scenario_id!r}")


# The harness MODEL of what the coordinator will decide for each scenario, keyed by
# the conditions above. `expected_case` must equal the coordinator's actual
# case_classified when the conditions are driven through a real coordinator. This
# table is asserted by tests/m9 (single source of truth shared with the checklist).
SCENARIO_EXPECTED_IMPACT: Dict[str, Dict[str, Any]] = {
    "S1": {"receipt": True,  "finalize": True,  "retry": False, "case": "Case B"},
    "S2": {"receipt": False, "finalize": False, "retry": False, "case": "WAITING_FOR_ENGINE"},
    "S3": {"receipt": False, "finalize": False, "retry": False, "case": "Case A"},
    "S4": {"receipt": False, "finalize": False, "retry": False, "case": "Case J"},
    "S5": {"receipt": True,  "finalize": True,  "retry": False, "case": "Case B"},
    "S6": {"receipt": False, "finalize": False, "retry": False, "case": "Case D"},
    "S7": {"receipt": False, "finalize": False, "retry": False, "case": "Case G"},
    "S8": {"receipt": False, "finalize": False, "retry": False, "case": "Case H"},
}