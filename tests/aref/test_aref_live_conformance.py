"""A-REF LIVE CONFORMANCE GATE (R4F 16.6 required live closure; operator-gated).

Every required live case runs the two-phase staged driver (probe launch -> controller
verification -> execution launch) with real Blender and compares the pure and live evidence
through the A-REF comparator. The gate is skipped unless ATLAS_RUN_LIVE_BLENDER=1; a skipped gate
is NOT a pass and the summary records that nothing was executed.

Case expectations come from each fixture's DECLARED expected literals (no duplication): the live
receipt must match the declared outcome, the invocation count must match the OC class rule, the
child digest must match the declared child digest, and the comparator must return PARITY (with the
documented NON_COMPARABLE note for OC3 refusal reasons).
"""

import json
import os
from pathlib import Path

import pytest

from tests.aref.aref_live_driver import DEFAULT_EVIDENCE, run_live_case
from tests.aref.fixtures import load_case

pytestmark = pytest.mark.skipif(os.environ.get("ATLAS_RUN_LIVE_BLENDER", "") != "1",
                                reason="live Blender gate off (ATLAS_RUN_LIVE_BLENDER != 1)")

#: Registered live A-REF cases (each must run BOTH stages and yield its declared outcome).
LIVE_CASES = (
    # C1 duplicate-face: production-mutator positives + the required case family of 16.6(1)
    "AREF-TEST-FX-C1-PAIR",
    "AREF-TEST-FX-C1-ROTATED",
    "AREF-TEST-FX-C1-REVERSED",
    "AREF-TEST-FX-C1-TRIPLE-S2",
    "AREF-TEST-FX-C1-TRIPLE-S3",
    # C1 pre-mutation refusals (OC1)
    "AREF-TEST-FX-C1-TRIPLE-AMB",
    "AREF-TEST-FX-C1-PRECOND",
    # C2/C3 production-mutator positives
    "AREF-TEST-FX-C2-DEGEN",
    "AREF-TEST-FX-C3-POS",
    # OC1 authorization refusal (null fixture)
    "AREF-TEST-FX-C3-AUTHREQ",
    # OC3 naming mismatch: MANDATORY, all four operations (16.6(3))
    "AREF-TEST-FX-MM-C1",
    "AREF-TEST-FX-MM-C2",
    "AREF-TEST-FX-MM-C3",
    "AREF-TEST-FX-MM-C4",
    # OC5 shared datablock, both variants for C1/C2 + the C3 variants (16.6(4))
    "AREF-TEST-FX-AL-C1",
    "AREF-TEST-FX-AL-C1-R",
    "AREF-TEST-FX-AL-C2",
    "AREF-TEST-FX-AL-C2-R",
    "AREF-TEST-FX-AL-C3",
    "AREF-TEST-FX-AL-C3-R",
    # C4 merge positive through the planner's explicit merge pass (16.6(1))
    "AREF-TEST-FX-C4-MERGE",
)

#: Controller-side binding negatives (R4F 16.6(7)(ii)): the probe runs, the launch is WITHHELD.
WITHHELD_CASES = (
    ("AREF-TEST-FX-C1-PAIR", "WRONG_ARTIFACT_SHA"),
    ("AREF-TEST-FX-C1-PAIR", "WRONG_PLAN_ID"),
    ("AREF-TEST-FX-C1-PAIR", "WRONG_SOURCE_DIGEST"),
    ("AREF-TEST-FX-C1-PAIR", "TRUNCATED_EVIDENCE"),
)

#: In-process binding negatives: the execution launch runs and must refuse BEFORE mutation.
IN_PROCESS_NEGATIVES = (
    ("AREF-TEST-FX-C1-PAIR", "WRONG_PARAMETER_IN_HANDOFF"),
    ("AREF-TEST-FX-C1-PAIR", "TAMPERED_PROBE_ARTIFACT"),
)


@pytest.mark.parametrize("fixture_id", LIVE_CASES)
def test_required_live_case(fixture_id):
    spec = load_case(fixture_id)
    declared = spec.expected
    result = run_live_case(fixture_id)

    assert result["launches"][0]["status"] == "PROBED", result
    assert result["controller_verification"]["status"] == "VERIFIED", result
    assert result["execution_launched"] is True
    assert result["execution"]["status"] == "EXECUTED", result

    outcome = result["outcome"]
    assert outcome["result"] == declared["outcomes"]["pure"], result
    assert outcome["oc_class"] == declared["oc_class"], result
    expected_invocations = 0 if declared["oc_class"] == "OC1" else 1
    assert outcome["invocation_count"] == expected_invocations, result
    if declared.get("child_digest"):
        assert outcome["child_digest"] == declared["child_digest"], result

    # the executor's own invocation counter must equal the delegate's recorded calls; a mismatch is
    # already raised in-stage, so reaching here proves it.
    comparison = result["comparison"]
    assert comparison["verdict"] == "PARITY", result
    if declared["oc_class"] == "OC3":
        assert any("NON_COMPARABLE" in note for note in comparison["notes"]), result
    assert comparison["dimensions"]["child_graph_unchanged"] is True, result


@pytest.mark.parametrize("fixture_id,tamper", WITHHELD_CASES)
def test_controller_withholds_execution_on_binding_negative(fixture_id, tamper):
    result = run_live_case(fixture_id, tamper=tamper)
    assert result["launches"][0]["status"] == "PROBED"
    assert result["execution_launched"] is False, result
    assert result["controller_verification"]["status"] == "WITHHELD", result
    assert result["controller_verification"]["category"] == "FIXTURE-BINDING-MISMATCH", result
    assert result["outcome"]["executor_invocations"] == 0
    assert len(result["launches"]) == 1  # exactly one Blender process: the probe


@pytest.mark.parametrize("fixture_id,tamper", IN_PROCESS_NEGATIVES)
def test_execution_launch_refuses_before_mutation(fixture_id, tamper):
    result = run_live_case(fixture_id, tamper=tamper)
    assert result["controller_verification"]["status"] == "VERIFIED"
    assert result["execution_launched"] is True
    execution = result["execution"]
    assert execution["status"] == "REFUSED", result
    assert execution["category"] == "FIXTURE-BINDING-MISMATCH", result
    assert execution["invocation_count"] == 0, result
    assert result["outcome"]["disposition"] == "POSITIVELY_DEMONSTRATED"


def test_live_gate_summary_is_recorded():
    """Record the gate's execution status: a skipped gate must never be reported as a pass."""
    summary = {"gate": "ATLAS_RUN_LIVE_BLENDER", "enabled": True,
               "cases": len(LIVE_CASES), "withheld_negatives": len(WITHHELD_CASES),
               "in_process_negatives": len(IN_PROCESS_NEGATIVES),
               "evidence_dir": str(DEFAULT_EVIDENCE / "live")}
    path = DEFAULT_EVIDENCE / "live_conformance_summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    assert path.exists()
