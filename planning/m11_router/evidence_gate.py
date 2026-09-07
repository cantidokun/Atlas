"""Narrow evidence-gate interface for the M11 router.

Implements docs/ATLAS_M11_ADAPTIVE_MODEL_ROUTING_DESIGN.md §8 (evidence-based
confidence) and the router's post-execution gate.

The gate accepts only OBJECTIVE evidence (tests, build, static validation,
contract validation, diff checks). Free-form model claims can never satisfy the
gate. It returns a structured ``EvidenceGateResult`` indicating whether the
evidence is sufficient, insufficient, a failed gate, requires escalation, or is
terminal (needs human review).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional, Sequence


class EvidenceGateResultKind(str, object):
    # str-enum-like constants for serialization simplicity.
    SUFFICIENT = "SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"
    FAILED = "FAILED"
    ESCALATION_REQUIRED = "ESCALATION_REQUIRED"
    TERMINAL_HUMAN_REVIEW = "TERMINAL_HUMAN_REVIEW"


@dataclass(frozen=True)
class EvidenceGateResult:
    """Structured outcome of an evidence gate (immutable)."""

    outcome: str  # one of EvidenceGateResultKind
    tests_passed: Optional[int] = None
    tests_failed: Optional[int] = None
    build_result: Optional[str] = None
    static_result: Optional[str] = None
    contract_result: Optional[str] = None
    diff_checks: Mapping[str, bool] = field(default_factory=dict)
    blockers: tuple[str, ...] = ()

    @property
    def is_sufficient(self) -> bool:
        return self.outcome == EvidenceGateResultKind.SUFFICIENT

    @property
    def requires_escalation(self) -> bool:
        return self.outcome in (
            EvidenceGateResultKind.ESCALATION_REQUIRED,
            EvidenceGateResultKind.INSUFFICIENT,
            EvidenceGateResultKind.FAILED,
        )

    @property
    def is_terminal_human_review(self) -> bool:
        return self.outcome == EvidenceGateResultKind.TERMINAL_HUMAN_REVIEW


class EvidenceGate:
    """Deterministic evaluation of objective evidence.

    Implementations of the concrete signals (pytest, UBT, static checks, contract
    validator) are injected as callables returning booleans/counts. This interface
    does NOT orchestrate model execution (outside M11.1 scope).
    """

    def __init__(
        self,
        *,
        require_tests: bool = True,
        require_build: bool = False,
        require_static: bool = False,
        require_contract: bool = False,
        require_diff: bool = False,
        max_blockers_to_terminal: int = 3,
    ) -> None:
        self._require_tests = require_tests
        self._require_build = require_build
        self._require_static = require_static
        self._require_contract = require_contract
        self._require_diff = require_diff
        self._max_blockers = max_blockers_to_terminal

    def evaluate(
        self,
        *,
        tests_passed: Optional[int] = None,
        tests_failed: Optional[int] = 0,
        build_result: Optional[str] = None,
        static_result: Optional[str] = None,
        contract_result: Optional[str] = None,
        diff_checks: Optional[Mapping[str, bool]] = None,
    ) -> EvidenceGateResult:
        """Evaluate objective evidence and return a structured gate result.

        - ``tests_failed > 0`` when tests are required  -> FAILED.
        - A required build/static/contract signal that is None or not green
          -> INSUFFICIENT (escalation required).
        - Detection of unexplained unknowns escalates.
        - If enough distinct blockers accumulate -> TERMINAL_HUMAN_REVIEW.
        """
        blockers: list[str] = []
        tests_failed = tests_failed or 0
        if self._require_tests:
            if tests_failed and tests_failed > 0:
                blockers.append(f"{tests_failed} failing test(s)")
            if tests_passed is None:
                blockers.append("tests not run")

        if self._require_build and build_result is None:
            blockers.append("build not run")
        elif self._require_build and build_result != "PASS":
            blockers.append(f"build={build_result}")

        if self._require_static and static_result is None:
            blockers.append("static checks not run")
        elif self._require_static and static_result != "PASS":
            blockers.append(f"static={static_result}")

        if self._require_contract and contract_result is None:
            blockers.append("contract checks not run")
        elif self._require_contract and contract_result != "PASS":
            blockers.append(f"contract={contract_result}")

        if self._require_diff and diff_checks is not None:
            for name, ok in diff_checks.items():
                if not ok:
                    blockers.append(f"diff check failed: {name}")

        if blockers:
            if len(blockers) >= self._max_blockers or self._max_blockers == 0 and len(blockers) > 0:
                return EvidenceGateResult(
                    outcome=EvidenceGateResultKind.TERMINAL_HUMAN_REVIEW,
                    tests_passed=tests_passed,
                    tests_failed=tests_failed,
                    build_result=build_result,
                    static_result=static_result,
                    contract_result=contract_result,
                    diff_checks=dict(diff_checks or {}),
                    blockers=tuple(blockers),
                )
            return EvidenceGateResult(
                outcome=EvidenceGateResultKind.INSUFFICIENT,
                tests_passed=tests_passed,
                tests_failed=tests_failed,
                build_result=build_result,
                static_result=static_result,
                contract_result=contract_result,
                diff_checks=dict(diff_checks or {}),
                blockers=tuple(blockers),
            )

        # All required gates green (or no required gates, meaning the required set is empty).
        return EvidenceGateResult(
            outcome=EvidenceGateResultKind.SUFFICIENT,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            build_result=build_result,
            static_result=static_result,
            contract_result=contract_result or "PASS",
            diff_checks=dict(diff_checks or {}),
        )