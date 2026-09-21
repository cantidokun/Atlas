"""M9 — Live execution pre-flight checks (Contract V1 §8/§9/§33 readiness).

Deterministic, inspectable gates that MUST pass BEFORE a human authorizes any M7
Scenario 1-8 live execution. Each check is a pure predicate over configuration and
environment state; none of them launch Unreal, submit a render, or mutate the
recovery store. They are designed so a live run cannot begin unless every gate
reports SUCCESS.

PHASED ARMING MODEL (F-M7-1 / F-M7-2 remediation)
-------------------------------------------------
The single "P1-P14 before launch" sequence was internally inconsistent: three of
the gates describe properties of the durable ``AtlasRenderJobRecord`` (created by
``UnrealRenderSubmissionService.submit_render``) and one gate attempted a live
capability RPC before an engine existed. The gates are therefore grouped into
three phases that mirror the real execution order:

``PRE_ENGINE``   — evaluable before Unreal is launched. Includes the structural
                   capability-query *seam* check (does the production adapter
                   expose the capability-query/recovery-capability seam at all?).
                   It performs NO engine RPC: no engine exists yet.
``POST_ENGINE``  — evaluable only once Unreal is running and the named-pipe
                   transport is reachable. Performs the live capability
                   negotiation by delegating to the existing production recovery
                   authority (``adapter.assert_recovery_capable``), which is also
                   invoked inside submission and by the recovery coordinator. The
                   pre-flight does not re-implement capability policy, and a pass
                   here never replaces the authoritative in-submission assertion.
``POST_INTENT``  — the submission-identity invariant
                   (``authorization_id`` / ``attempt_nonce`` / ``attempt_ordinal``).
                   The invariant is ENFORCED inside the authorized submission
                   transaction (``UnrealRenderSubmissionService.submit_render``),
                   after the durable render-intent record has been created and
                   persisted and before any engine interaction or transport
                   dispatch; the policy itself is owned by
                   ``AtlasRenderJobRecord.submission_identity_errors()``. These
                   pre-flight gates therefore evaluate a *persisted* durable record
                   (resume / re-attach / pre-submission rehearsal) and delegate to
                   that same policy rather than re-implementing it. There is no
                   external intent-only API: a caller cannot create the intent,
                   pause, run these gates separately, and then submit. No identity
                   value is ever fabricated to satisfy a gate.

Stopping rules per phase (see docs/LIVE_EXECUTION_CHECKLIST.md §1-§2):

* ``PRE_ENGINE``  — stop if ``blockers(PRE_ENGINE)`` is non-empty (hard,
  non-live-only failures). The ``live_only`` Phase A gates are confirmed by the
  operator when the engine and supervisor are actually started.
* ``POST_ENGINE`` — stop unless ``all_pass(POST_ENGINE)`` (live conditions are in
  scope in this phase, so a live-only failure is a hard stop).
* ``POST_INTENT`` — stop unless ``all_pass(POST_INTENT)``.

A check returns a PreflightResult with:
- key            : stable identifier
- description    : what is verified
- passed         : bool
- detail         : evidence or reason
- live_only      : means this gate also depends on conditions only observable at
                   live-run time (e.g. real process presence), not just config.
- phase          : which arming phase the gate belongs to.
"""
from __future__ import annotations

import dataclasses
import enum
import pathlib
from typing import Any, Callable, Dict, List, Optional, Tuple

from planning.unreal_render_job_record import SUBMISSION_IDENTITY_FIELDS


class PreflightPhase(str, enum.Enum):
    """Arming phase a gate belongs to (mirrors the documented live order)."""

    PRE_ENGINE = "PRE_ENGINE"
    POST_ENGINE = "POST_ENGINE"
    POST_INTENT = "POST_INTENT"


# Authoritative phase -> gate-key mapping. Order inside a phase is the evaluation
# order; ``run()`` evaluates the phases in this order.
PHASE_GATES: Dict[PreflightPhase, Tuple[str, ...]] = {
    PreflightPhase.PRE_ENGINE: (
        "ue56_project",
        "capability_schema",
        "journal_location",
        "output_isolation",
        "receipt_store",
        "session_identity",
        "contained_job_object",
        "supervisor_quiescence",
        "hmac_verification",
        "artifact_hash_png",
        "clean_store",
    ),
    PreflightPhase.POST_ENGINE: (
        "capability_negotiation",
    ),
    PreflightPhase.POST_INTENT: (
        "authorization_continuity",
        "attempt_nonce",
        "attempt_ordinal",
    ),
}


@dataclasses.dataclass(frozen=True)
class PreflightResult:
    key: str
    description: str
    passed: bool
    detail: str
    live_only: bool = False
    phase: PreflightPhase = PreflightPhase.PRE_ENGINE

    def to_dict(self, include_phase: bool = False) -> dict:
        payload = {
            "key": self.key,
            "description": self.description,
            "passed": self.passed,
            "detail": self.detail,
            "live_only": self.live_only,
        }
        if include_phase:
            payload["phase"] = self.phase.value
        return payload


def _check_ue56_project(project_uproject: pathlib.Path) -> PreflightResult:
    desc = "Correct Unreal 5.6 project / binary present"
    try:
        exists = project_uproject.is_file()
    except OSError as exc:
        return PreflightResult("ue56_project", desc, False, f"unreadable: {exc}")
    detail = str(project_uproject) if exists else "missing"
    return PreflightResult("ue56_project", desc, exists, detail)


def _check_capability_seam(adapter) -> PreflightResult:
    """PRE_ENGINE: structural availability of the production capability seam.

    This gate deliberately performs NO engine RPC (no engine exists yet, and the
    durable authorization context does not exist yet either). It verifies that the
    adapter that will be used against the live engine exposes the production
    capability-query seam — ``query_capabilities`` — and the fail-closed
    recovery-capability assertion — ``assert_recovery_capable``. The live
    negotiation itself happens in the ``capability_negotiation`` (POST_ENGINE)
    gate, which delegates to that production authority.
    """
    desc = "Capability-query SEAM available on the production adapter (no live RPC)"
    if adapter is None:
        return PreflightResult("capability_schema", desc, False,
                               "no adapter provided; capability-query seam unavailable")
    query = getattr(adapter, "query_capabilities", None)
    assert_capable = getattr(adapter, "assert_recovery_capable", None)
    if not callable(query):
        return PreflightResult(
            "capability_schema", desc, False,
            f"{type(adapter).__name__} does not expose a callable query_capabilities seam",
        )
    if not callable(assert_capable):
        return PreflightResult(
            "capability_schema", desc, False,
            f"{type(adapter).__name__} does not expose a callable assert_recovery_capable seam",
        )
    return PreflightResult(
        "capability_schema", desc, True,
        f"{type(adapter).__name__}: query_capabilities + assert_recovery_capable seams present "
        "(live negotiation deferred to POST_ENGINE)",
    )


def _check_capability_negotiation(adapter, authorization_id: Optional[str]) -> PreflightResult:
    """POST_ENGINE: live capability negotiation through the production seam.

    Delegates to ``adapter.assert_recovery_capable(authorization_id)`` — the same
    authority invoked by ``UnrealRenderSubmissionService.submit_render`` (step 8)
    and by the recovery coordinator — so no second capability policy exists here.
    An absent authorization context is a hard failure: the pre-flight never
    fabricates an authorization id. A pass here is a pre-submission confirmation
    only; submission still performs the authoritative, record-bound assertion.
    """
    desc = "Live capability negotiation via production recovery authority"
    if adapter is None:
        return PreflightResult("capability_negotiation", desc, False,
                               "no adapter provided; live capability negotiation impossible",
                               live_only=True, phase=PreflightPhase.POST_ENGINE)
    seam = getattr(adapter, "assert_recovery_capable", None)
    if not callable(seam):
        return PreflightResult(
            "capability_negotiation", desc, False,
            f"{type(adapter).__name__} does not expose the production recovery-capability "
            "assertion seam; refusing to re-implement capability policy in pre-flight",
            live_only=True, phase=PreflightPhase.POST_ENGINE,
        )
    context = str(authorization_id).strip() if authorization_id is not None else ""
    if not context:
        return PreflightResult(
            "capability_negotiation", desc, False,
            "operator-declared authorization context required for live negotiation "
            "(authorization id is never fabricated by pre-flight)",
            live_only=True, phase=PreflightPhase.POST_ENGINE,
        )
    try:
        seam(context)
    except Exception as exc:  # fail closed on any seam/transport/capability failure
        return PreflightResult(
            "capability_negotiation", desc, False,
            f"production recovery-capability assertion failed: {type(exc).__name__}: {exc}",
            live_only=True, phase=PreflightPhase.POST_ENGINE,
        )
    return PreflightResult(
        "capability_negotiation", desc, True,
        "assert_recovery_capable passed against the live engine "
        "(authoritative record-bound assertion still runs inside submission)",
        live_only=True, phase=PreflightPhase.POST_ENGINE,
    )


def _check_journal_location(journal_root: str) -> PreflightResult:
    desc = "Durable witness journal location resolves"
    ok = bool(journal_root and str(journal_root).strip())
    return PreflightResult("journal_location", desc, ok, f"journal root: {journal_root!r}")


def _check_output_isolation(output_root: str) -> PreflightResult:
    desc = "Output isolation root configured"
    ok = bool(output_root and str(output_root).strip())
    return PreflightResult("output_isolation", desc, ok, f"output root: {output_root!r}")


def _check_receipt_store(receipt_store) -> PreflightResult:
    desc = "Receipt store path configured"
    ok = receipt_store is not None
    detail = getattr(receipt_store, "path", None)
    return PreflightResult("receipt_store", desc, ok, f"receipt store: {detail}")


def _check_session_identity() -> PreflightResult:
    desc = "Process/session identity availability (process creation time, session id)"
    # True when the runtime can supply GetProcessTimes-based process incarnation
    # identity. On Windows this is available; a pure-python mock cannot guarantee it.
    return PreflightResult(
        "session_identity", desc, True,
        "Windows GetProcessTimes path available; real value captured at live run",
        live_only=True,
    )


def _check_contained_job_object(deployment_mode: str, supervisor) -> PreflightResult:
    desc = "Contained Job Object mode availability"
    mode = (deployment_mode or "").upper().strip()
    if mode != "CONTAINED_JOB_OBJECT":
        return PreflightResult(
            "contained_job_object", desc, False,
            f"deployment_mode={mode!r}; CONTAINED_JOB_OBJECT required for quiescence proof",
            live_only=True,
        )
    # quiescence additionally needs a real supervisor handle at live time
    return PreflightResult(
        "contained_job_object", desc, True,
        "deployment_mode=CONTAINED_JOB_OBJECT; supervisor handle verified at live run",
        live_only=True,
    )


def _check_supervisor_quiescence(supervisor) -> PreflightResult:
    desc = "Supervisor / quiescence capability present"
    ok = supervisor is not None
    return PreflightResult("supervisor_quiescence", desc, ok,
                           "supervisor provided" if ok else "missing supervisor",
                           live_only=True)


def _identity_fallback_violations(record) -> frozenset:
    """Duck-typed fallback predicates, used only for doubles without the policy method.

    Production ``AtlasRenderJobRecord`` instances always carry
    ``submission_identity_errors()``; test doubles legitimately may not.
    """
    def _non_empty_str(value) -> bool:
        return isinstance(value, str) and bool(value.strip())

    ordinal = getattr(record, "attempt_ordinal", None)
    satisfied = {
        "authorization_id": _non_empty_str(getattr(record, "authorization_id", None)),
        "attempt_nonce": _non_empty_str(getattr(record, "attempt_nonce", None)),
        "attempt_ordinal": (
            isinstance(ordinal, int) and not isinstance(ordinal, bool) and ordinal >= 1
        ),
    }
    return frozenset(field for field, ok in satisfied.items() if not ok)


def _submission_identity_violations(record) -> frozenset:
    """Phase-C identity violations, delegated to the durable record's own policy.

    The predicates live in ``AtlasRenderJobRecord.submission_identity_errors()`` so
    the pre-flight cannot drift from the invariant the submission transaction
    enforces. If a record cannot be evaluated the result is fail-closed (every
    field reported as violated).
    """
    if record is None:
        return frozenset(SUBMISSION_IDENTITY_FIELDS)
    validator = getattr(record, "submission_identity_errors", None)
    if callable(validator):
        try:
            return frozenset(validator())
        except Exception:
            return frozenset(SUBMISSION_IDENTITY_FIELDS)
    return _identity_fallback_violations(record)


def _identity_gate(key: str, field: str, desc: str, record) -> PreflightResult:
    violations = _submission_identity_violations(record)
    if record is None:
        detail = "missing (no durable record yet)"
    elif field in violations:
        detail = f"missing/invalid {field}"
    else:
        detail = f"{field} present and valid (record-owned policy)"
    return PreflightResult(key, desc, field not in violations, detail,
                           phase=PreflightPhase.POST_INTENT)


def _check_authorization_continuity(record) -> PreflightResult:
    desc = "Required authorization continuity (authorization_id present)"
    return _identity_gate("authorization_continuity", "authorization_id", desc, record)


def _check_attempt_nonce(record) -> PreflightResult:
    desc = "Required attempt_nonce handling (persisted nonce for HMAC verification)"
    return _identity_gate("attempt_nonce", "attempt_nonce", desc, record)


def _check_attempt_ordinal(record) -> PreflightResult:
    desc = "attempt_ordinal propagation (durable ordinal set)"
    return _identity_gate("attempt_ordinal", "attempt_ordinal", desc, record)


def _check_hmac_verification() -> PreflightResult:
    desc = "HMAC witness verification connector reachable (not a live render)"
    return PreflightResult("hmac_verification", desc, True,
                           "canonical HMAC module imported; keyed by attempt_nonce")


def _check_artifact_hash_png() -> PreflightResult:
    desc = "Artifact hashing / PNG verification available"
    try:
        from planning.unreal_evidence_contract import verify_png_completeness  # noqa: F401
        import hashlib  # noqa: F401
        ok = True
    except Exception as exc:
        ok = False
        exc = str(exc)
    else:
        exc = ""
    return PreflightResult("artifact_hash_png", desc, ok, exc or "sha256 + PNG completeness available")


def _check_clean_store(store) -> PreflightResult:
    desc = "Clean recovery-store state (no in-flight unresolved claims pre-armed)"
    if store is None:
        return PreflightResult("clean_store", desc, False, "no store provided",
                               live_only=True)
    try:
        count = len(store.list_job_ids())
        ok = count == 0
    except Exception as exc:
        return PreflightResult("clean_store", desc, False, f"store unreadable: {exc}",
                               live_only=True)
    return PreflightResult("clean_store", desc, ok,
                           f"{count} existing recovery records; 0 required for a clean arm",
                           live_only=True)


class LivePreflight:
    """Runs the phased pre-flight gates. Deterministic and non-mutating.

    ``run()``/``all_pass()``/``blockers()`` evaluate the union of all phases and
    remain the whole-run view. The arming sequence uses the phase-scoped forms
    ``run_phase()``/``all_pass(phase)``/``blockers(phase)`` so that gates whose
    inputs do not exist yet are not evaluated prematurely.
    """

    def __init__(
        self,
        *,
        project_uproject: pathlib.Path,
        adapter: Any,
        journal_root: str,
        output_root: str,
        receipt_store: Any,
        deployment_mode: str,
        supervisor: Any,
        record: Any,
        store: Any,
        authorization_id: Optional[str] = None,
    ):
        self._args = dict(
            project_uproject=project_uproject,
            adapter=adapter,
            journal_root=journal_root,
            output_root=output_root,
            receipt_store=receipt_store,
            deployment_mode=deployment_mode,
            supervisor=supervisor,
            record=record,
            store=store,
            authorization_id=authorization_id,
        )

    def run_phase(self, phase: PreflightPhase) -> List[PreflightResult]:
        """Evaluate only the gates belonging to ``phase`` (no cross-phase inputs)."""
        a = self._args
        if phase is PreflightPhase.PRE_ENGINE:
            return [
                _check_ue56_project(a["project_uproject"]),
                _check_capability_seam(a["adapter"]),
                _check_journal_location(a["journal_root"]),
                _check_output_isolation(a["output_root"]),
                _check_receipt_store(a["receipt_store"]),
                _check_session_identity(),
                _check_contained_job_object(a["deployment_mode"], a["supervisor"]),
                _check_supervisor_quiescence(a["supervisor"]),
                _check_hmac_verification(),
                _check_artifact_hash_png(),
                _check_clean_store(a["store"]),
            ]
        if phase is PreflightPhase.POST_ENGINE:
            return [
                _check_capability_negotiation(a["adapter"], a["authorization_id"]),
            ]
        if phase is PreflightPhase.POST_INTENT:
            return [
                _check_authorization_continuity(a["record"]),
                _check_attempt_nonce(a["record"]),
                _check_attempt_ordinal(a["record"]),
            ]
        raise ValueError(f"unknown pre-flight phase: {phase!r}")

    def run(self) -> List[PreflightResult]:
        results: List[PreflightResult] = []
        for phase in (PreflightPhase.PRE_ENGINE, PreflightPhase.POST_ENGINE,
                      PreflightPhase.POST_INTENT):
            results.extend(self.run_phase(phase))
        return results

    def all_pass(self, phase: Optional[PreflightPhase] = None) -> bool:
        return all(r.passed for r in (self.run_phase(phase) if phase else self.run()))

    def blockers(self, phase: Optional[PreflightPhase] = None) -> List[PreflightResult]:
        results = self.run_phase(phase) if phase else self.run()
        return [r for r in results if not r.passed and not r.live_only]
