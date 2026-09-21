"""M9 — Live Recovery Readiness & Scenario Harness.

PRE-FLIGHT ONLY. This module deterministically models Contract V1 §33 Scenarios
1-8 against the *real* `UnrealRenderRecoveryCoordinator` using faked transport /
supervisor / receipt-store seams. It does NOT and cannot launch Unreal, run a live
render, kill/restart an engine, execute the M7 live Scenarios, run workflow/
action-runner tests, or touch Blender.

The harness's job is to SHOW what the coordinator will decide when the durable
record, witness journal, process/session condition, and artifact condition take a
given shape — so a human can authorize (or refuse) the corresponding live run with
predictable expectations. It is not a substitute for live validation.

F-S1-2 containment fidelity (2026-09-21)
----------------------------------------
The model previously carried two INDEPENDENT booleans (`engine_capable`,
`quiescent`) and asserted `engine_capable=True AND quiescent=True` in five of the
eight scenarios. That combination is IMPOSSIBLE in the real contained deployment:

* Contract V1 §9.272-274 launches Unreal *inside* the Atlas Job Object;
* §9.275-279 defines quiescence as ``JobObjectHandleValid AND ActiveProcesses == 0``
  over that same Job Object;
* therefore ``quiescent=True`` implies the engine process has exited, and the named
  pipe it hosts has no server, so ``assert_recovery_capable`` must fail.

The model now declares ONE :class:`ContainmentState` and DERIVES both flags from it,
and :class:`ContainmentState` rejects the impossible combination outright. Case B is
therefore modelled the way Contract V1 §21:716 defines it — a PRIOR-SESSION journal
witness read from the durable Atlas-designated location, with zero engine RPCs — and
a separate explicit Case-K control models the contained-and-alive state that must
fail closed.

Safety properties the harness itself enforces (mirrored in tests/m9):
- It never constructs an authorized render or submission (it only drives the
  RECOVERY path; submission requires UnrealRenderSubmissionService which is never
  invoked by the harness).
- It cannot resubmit an uncertain job (no path in the harness calls submit).
- It cannot synthesize success (evidence only becomes verified through
  verify_render_job_evidence on real disk bytes + HMAC).
- A receipt is created only via store.publish_verified_receipt, which requires
  verified evidence (Case B only).
- It cannot bypass quiescence (the coordinator's §9 quiescence gate runs before any
  witness acquisition or terminal-artifact inspection).
- It cannot bypass HMAC / attempt_ordinal verification (the M8 gates run inside
  _adopt_terminal_candidate before any artifact/evidence processing).
- It cannot declare a containment state the live deployment cannot reach.
"""
from __future__ import annotations

import dataclasses
import enum
from typing import Any, Dict, List, Tuple

from planning.unreal_render_job_states import (
    RenderJobLifecycleState,
    RenderJobRecoveryStatus,
)

#: Deployment modes (Contract V1 §9).
DEPLOYMENT_MODE_CONTAINED = "CONTAINED_JOB_OBJECT"
DEPLOYMENT_MODE_UNCONTAINED = "UNCONTAINED_ATTACHED"


class ImpossibleContainmentStateError(ValueError):
    """Raised when a modelled containment state cannot occur in the live deployment."""


class ScenarioOutcome(str, enum.Enum):
    FORBIDDEN_RECEIPT = "FORBIDDEN_RECEIPT"
    FORBIDDEN_RETRY = "FORBIDDEN_RETRY"
    PERMITTED_RECEIPT = "PERMITTED_RECEIPT"
    EXPLICITLY_NO_RECEIPT = "EXPLICITLY_NO_RECEIPT"
    NO_SYNTHETIC_SUCCESS = "NO_SYNTHETIC_SUCCESS"


@dataclasses.dataclass(frozen=True)
class ContainmentState:
    """The single declared process/containment condition of a modelled scenario.

    ``quiescent`` and ``engine_capable`` are DERIVED, never declared independently,
    because the live deployment cannot decouple them (Contract V1 §9):

    * Unreal is launched inside the Atlas Job Object (§9.272-274);
    * quiescence is that Job Object's ``ActiveProcesses == 0`` (§9.275-279);
    * the transport is a named pipe served BY the engine process, so a live engine
      implies a non-empty Job Object whenever the engine is contained.

    F-S1-2: declaring ``live_engine_present=True`` together with
    ``job_active_processes == 0`` under ``CONTAINED_JOB_OBJECT`` is rejected.
    """

    deployment_mode: str = DEPLOYMENT_MODE_CONTAINED
    live_engine_present: bool = False
    job_active_processes: int = 0

    def __post_init__(self) -> None:
        mode = str(self.deployment_mode).upper().strip()
        if mode not in (DEPLOYMENT_MODE_CONTAINED, DEPLOYMENT_MODE_UNCONTAINED):
            raise ImpossibleContainmentStateError(f"unknown deployment mode {self.deployment_mode!r}")
        if self.job_active_processes < 0:
            raise ImpossibleContainmentStateError("job_active_processes cannot be negative")
        if mode == DEPLOYMENT_MODE_CONTAINED and self.live_engine_present and self.job_active_processes == 0:
            raise ImpossibleContainmentStateError(
                "impossible contained state: the engine is inside the quiescence Job "
                "Object, so a live engine cannot coexist with ActiveProcesses == 0 "
                "(engine_capable=True AND quiescent=True is unreachable)"
            )

    @property
    def quiescent(self) -> bool:
        """Contract V1 §9 process quiescence predicate (contained mode only)."""
        return (
            self.deployment_mode.upper().strip() == DEPLOYMENT_MODE_CONTAINED
            and self.job_active_processes == 0
        )

    @property
    def engine_capable(self) -> bool:
        """Transport reachable + ``assert_recovery_capable`` passes.

        A live engine that still has the Job Object empty is impossible in the
        contained deployment (see :class:`ContainmentState`), so reachability implies
        non-quiescence here. Mode UNCONTAINED_ATTACHED attaches to an engine outside
        the Job Object and always fails closed for adoption (§9.281-284).
        """
        if not self.live_engine_present:
            return False
        return not self.quiescent


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
    containment: ContainmentState  # derived engine_capable / quiescent (F-S1-2)
    journal_condition: str  # DURABLE witness set: COMPLETE | PARTIAL | UNREADABLE | NONE
    live_catalog_journal_status: str  # engine catalog journal_status when reachable
    candidate_known_jobs: List[Dict[str, Any]]  # what the live catalog returns
    disk_artifacts: bool  # whether output directory contains files

    # Expected outcome.
    expected_case: str
    expected_lifecycle_after: RenderJobLifecycleState
    expected_recovery_status_after: RenderJobRecoveryStatus
    receipt_permitted: bool
    retry_forbidden: bool
    status: str  # READY_FOR_LIVE | BLOCKED | NEEDS_HUMAN_INPUT | NOT_PROVEN
    engine_rpcs_expected: int  # 0 for the durable-witness adoption path

    # Reason this scenario is (or is not) deterministically harness-verifiable.
    harness_note: str

    @property
    def engine_capable(self) -> bool:
        """Derived (F-S1-2): never declared independently of containment."""
        return self.containment.engine_capable

    @property
    def quiescent(self) -> bool:
        """Derived (F-S1-2): never declared independently of containment."""
        return self.containment.quiescent

    @property
    def uses_durable_witness(self) -> bool:
        """Case B is defined over a PRIOR-SESSION durable journal witness."""
        return self.journal_condition == "COMPLETE" and self.expected_case == "Case B"


#: Contained + alive: the engine is inside the Job Object that must be empty.
ENGINE_ALIVE_CONTAINED = ContainmentState(
    deployment_mode=DEPLOYMENT_MODE_CONTAINED, live_engine_present=True, job_active_processes=6)
#: Engine exited / never attached and the Job Object has drained to zero: the only
#: state in which Contract V1 §9.279 permits inspection or adoption.
ENGINE_GONE_DRAINED = ContainmentState(
    deployment_mode=DEPLOYMENT_MODE_CONTAINED, live_engine_present=False, job_active_processes=0)

# The §33 scenarios. `expected_*` fields are the authoritative mapping; the
# containment/journal/artifact conditions are what deterministically produce them.
# The harness executes each against the real coordinator and asserts the outcomes.
SCENARIOS: Tuple[ScenarioSpec, ...] = (
    ScenarioSpec(
        scenario_id="S1",
        title="Normal render (durable prior-session Case B)",
        description="submit -> render -> finish -> engine exits -> verify -> receipt -> provenance",
        initial_lifecycle=RenderJobLifecycleState.SUBMITTED,
        containment=ENGINE_GONE_DRAINED,
        journal_condition="COMPLETE",
        live_catalog_journal_status="COMPLETE",
        candidate_known_jobs=[],
        disk_artifacts=True,
        expected_case="Case B",
        expected_lifecycle_after=RenderJobLifecycleState.FINALIZED,
        expected_recovery_status_after=RenderJobRecoveryStatus.RESOLVED,
        receipt_permitted=True,
        retry_forbidden=True,
        status="READY_FOR_LIVE",
        engine_rpcs_expected=0,
        harness_note="Faithful to the live deployment: the engine is gone (Job Object "
        "drained to 0), so adoption is served from the durable §10 witness journal "
        "with ZERO engine RPCs (asserted). This is the shape the 2026-09-21 live S1 "
        "run actually reached after the engine was terminated. Live dependency: real "
        "UE MRQ must render the files and write the matching {path,size,sha256} "
        "manifest into the witness journal.",
    ),
    ScenarioSpec(
        scenario_id="S1-K",
        title="Case K control — engine contained and alive with terminal artifacts",
        description="terminal journal + artifacts exist, but the engine still occupies the Job Object",
        initial_lifecycle=RenderJobLifecycleState.SUBMITTED,
        containment=ENGINE_ALIVE_CONTAINED,
        journal_condition="COMPLETE",
        live_catalog_journal_status="COMPLETE",
        candidate_known_jobs=[],
        disk_artifacts=True,
        expected_case="Case K (Quiescence Blocked)",
        expected_lifecycle_after=RenderJobLifecycleState.SUBMITTED,
        expected_recovery_status_after=RenderJobRecoveryStatus.WAITING_FOR_ENGINE_QUIESCENCE,
        receipt_permitted=False,
        retry_forbidden=True,
        status="READY_FOR_LIVE",
        engine_rpcs_expected=0,
        harness_note="NEGATIVE CONTROL for Contract V1 §9.279. The durable witness and "
        "the artifacts exist, but ActiveProcesses != 0, so recovery MUST NOT inspect or "
        "adopt them: no receipt, no artifact processing, and zero engine RPCs (the "
        "durable witness is read first). This is exactly the state the live 2026-09-21 "
        "S1 reconcile sampled while the engine was still contained.",
    ),
    ScenarioSpec(
        scenario_id="S2",
        title="Unreal restart during render",
        description="Kill Unreal during a multi-frame render.",
        initial_lifecycle=RenderJobLifecycleState.SUBMITTED,
        containment=ENGINE_GONE_DRAINED,
        journal_condition="NONE",
        live_catalog_journal_status="NONE",
        candidate_known_jobs=[],
        disk_artifacts=False,
        expected_case="WAITING_FOR_ENGINE",
        expected_lifecycle_after=RenderJobLifecycleState.SUBMITTED,
        expected_recovery_status_after=RenderJobRecoveryStatus.WAITING_FOR_ENGINE,
        receipt_permitted=False,
        retry_forbidden=True,
        status="BLOCKED",
        engine_rpcs_expected=1,
        harness_note="Deterministic only up to the engine-down branch: with NO durable "
        "witness and NO artifacts there is nothing to adopt and the engine is "
        "unreachable -> WAITING_FOR_ENGINE hold. The live sub-cases (crash mid-ACCEPTED "
        "vs mid-STARTED vs mid-FINISHED) differ in whether a retained partial journal "
        "exists; a retained partial journal is modelled by S4 (Case J).",
    ),
    ScenarioSpec(
        scenario_id="S3",
        title="Atlas restart during render",
        description="Unreal continues rendering while Atlas restarts.",
        initial_lifecycle=RenderJobLifecycleState.SUBMITTED,
        containment=ENGINE_ALIVE_CONTAINED,
        journal_condition="NONE",
        live_catalog_journal_status="COMPLETE",
        candidate_known_jobs=[],  # live, not yet terminal -> Case A (built by the driver)
        disk_artifacts=False,
        expected_case="Case A",
        expected_lifecycle_after=RenderJobLifecycleState.RENDERING,
        expected_recovery_status_after=RenderJobRecoveryStatus.NONE,
        receipt_permitted=False,
        retry_forbidden=True,
        status="NOT_PROVEN",
        engine_rpcs_expected=1,
        harness_note="The LIVE transport path stays available while the engine is "
        "active (engine reachable, job non-quiescent) and re-attaches to an existing "
        "in-flight execution without adopting artifacts and without a duplicate "
        "submission. The 'no duplicate execution' guarantee needs a live mid-render "
        "restart.",
    ),
    ScenarioSpec(
        scenario_id="S4",
        title="Both restart during render",
        description="Kill both processes mid-render.",
        initial_lifecycle=RenderJobLifecycleState.SUBMITTED,
        containment=ENGINE_GONE_DRAINED,
        journal_condition="PARTIAL",
        live_catalog_journal_status="PARTIAL",
        candidate_known_jobs=[],
        disk_artifacts=False,
        expected_case="Case J",
        expected_lifecycle_after=RenderJobLifecycleState.SUBMITTED,
        expected_recovery_status_after=RenderJobRecoveryStatus.RECOVERY_PENDING,
        receipt_permitted=False,
        retry_forbidden=True,
        status="BLOCKED",
        engine_rpcs_expected=0,
        harness_note="Deterministic for the torn/unparseable DURABLE witness branch: a "
        "partial journal on disk is classified Case J -> RECOVERY_PENDING (ambiguity "
        "increment, no receipt, no adoption, no engine RPC). The exact mid-render "
        "flushed-phase state remains a live observation.",
    ),
    ScenarioSpec(
        scenario_id="S5",
        title="Render finishes while Atlas is unavailable (canonical prior-session Case B)",
        description="Preserved terminal Unreal attestation allows later verification.",
        initial_lifecycle=RenderJobLifecycleState.SUBMITTED,
        containment=ENGINE_GONE_DRAINED,
        journal_condition="COMPLETE",
        live_catalog_journal_status="NONE",
        candidate_known_jobs=[],  # FINISHED journal + artifact, Atlas was down
        disk_artifacts=True,
        expected_case="Case B",
        expected_lifecycle_after=RenderJobLifecycleState.FINALIZED,
        expected_recovery_status_after=RenderJobRecoveryStatus.RESOLVED,
        receipt_permitted=True,
        retry_forbidden=True,
        status="READY_FOR_LIVE",
        engine_rpcs_expected=0,
        harness_note="Canonical Case B per Contract V1 §21:716 ('PRIOR session journal "
        "contains an exact terminal FINISHED record'): the engine is gone, the durable "
        "journal carries the HMAC-attested terminal witness, artifacts are on disk -> "
        "Case B receipt with zero engine RPCs. Live dependency: the UE 5.6 journal must "
        "actually survive in <ProjectDir>/AtlasWitnessJournal/ across the Atlas outage.",
    ),
    ScenarioSpec(
        scenario_id="S6",
        title="Artifact exists but no attributable engine terminal evidence",
        description="ORPHANED_ARTIFACTS_PRESENT; no receipt, no production lineage.",
        initial_lifecycle=RenderJobLifecycleState.SUBMITTED,
        containment=ENGINE_ALIVE_CONTAINED,
        journal_condition="NONE",
        live_catalog_journal_status="COMPLETE",
        candidate_known_jobs=[],
        disk_artifacts=True,
        expected_case="Case D",
        expected_lifecycle_after=RenderJobLifecycleState.ORPHANED_ARTIFACTS_PRESENT,
        expected_recovery_status_after=RenderJobRecoveryStatus.NONE,
        receipt_permitted=False,
        retry_forbidden=True,
        status="READY_FOR_LIVE",
        engine_rpcs_expected=1,
        harness_note="Deterministic and strict: bare artifacts with zero engine witness "
        "-> ORPHANED_ARTIFACTS_PRESENT, strictly non-mutating, no receipt, no synthetic "
        "terminal flags. This is NOT an adoption path (nothing is inspected for adoption "
        "and nothing is mutated), so it does not require §9 quiescence; the live catalog "
        "supplies the 'zero engine witness' fact.",
    ),
    ScenarioSpec(
        scenario_id="S7",
        title="Missing artifact after terminal engine claim",
        description="FAILED; receipt issuance blocked.",
        initial_lifecycle=RenderJobLifecycleState.SUBMITTED,
        containment=ENGINE_GONE_DRAINED,
        journal_condition="COMPLETE",
        live_catalog_journal_status="COMPLETE",
        candidate_known_jobs=[],  # FINISHED claim, but artifact missing on disk
        disk_artifacts=False,
        expected_case="Case G",
        expected_lifecycle_after=RenderJobLifecycleState.FAILED,
        expected_recovery_status_after=RenderJobRecoveryStatus.NONE,
        receipt_permitted=False,
        retry_forbidden=True,
        status="READY_FOR_LIVE",
        engine_rpcs_expected=0,
        harness_note="Deterministic: the terminal attested witness declares a manifest "
        "whose output file is absent on disk -> Case G FAILED, receipt blocked. Reached "
        "through the durable path (quiescence satisfied), so zero engine RPCs.",
    ),
    ScenarioSpec(
        scenario_id="S8",
        title="Ambiguous duplicate/stale execution identity",
        description="RECOVERY_FAILED; no artifact adoption.",
        initial_lifecycle=RenderJobLifecycleState.SUBMITTED,
        containment=ENGINE_ALIVE_CONTAINED,
        journal_condition="NONE",
        live_catalog_journal_status="COMPLETE",
        candidate_known_jobs=[],  # two candidate journal entries same atlas_job_id
        disk_artifacts=True,
        expected_case="Case H",
        expected_lifecycle_after=RenderJobLifecycleState.RECOVERY_FAILED,
        expected_recovery_status_after=RenderJobRecoveryStatus.NONE,
        receipt_permitted=False,
        retry_forbidden=True,
        status="BLOCKED",
        engine_rpcs_expected=1,
        harness_note="Deterministic for the duplicate-claim branch: two Unreal executions "
        "for one atlas_job_id -> Case H RECOVERY_FAILED, no adoption. The equivalent "
        "durable-set conflict (two materially different journals on disk) is covered by "
        "the durable-witness suite. Live dependency: actually producing two journals for "
        "the same job id to observe the real conflict on disk.",
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
    "S1": {"receipt": True, "finalize": True, "retry": False, "case": "Case B"},
    "S1-K": {"receipt": False, "finalize": False, "retry": False,
             "case": "Case K (Quiescence Blocked)"},
    "S2": {"receipt": False, "finalize": False, "retry": False, "case": "WAITING_FOR_ENGINE"},
    "S3": {"receipt": False, "finalize": False, "retry": False, "case": "Case A"},
    "S4": {"receipt": False, "finalize": False, "retry": False, "case": "Case J"},
    "S5": {"receipt": True, "finalize": True, "retry": False, "case": "Case B"},
    "S6": {"receipt": False, "finalize": False, "retry": False, "case": "Case D"},
    "S7": {"receipt": False, "finalize": False, "retry": False, "case": "Case G"},
    "S8": {"receipt": False, "finalize": False, "retry": False, "case": "Case H"},
}


def assert_reachable_containment(spec: ScenarioSpec) -> None:
    """Re-assert F-S1-2 at scenario level (belt-and-braces for callers).

    Raises :class:`ImpossibleContainmentStateError` if a scenario declares an
    unreachable combination (a live contained engine with an empty Job Object, or
    adoption of terminal artifacts without quiescence).
    """
    if spec.containment.engine_capable and spec.containment.quiescent:
        raise ImpossibleContainmentStateError(
            f"{spec.scenario_id}: engine_capable AND quiescent cannot both hold"
        )
    adopting = spec.expected_case in ("Case B", "Case G", "Case E/F")
    if adopting and not spec.quiescent:
        raise ImpossibleContainmentStateError(
            f"{spec.scenario_id}: terminal-artifact adoption requires §9 quiescence"
        )
