"""A-REF plan-artifact tests (R4F 9.10; K2/K3 bounded-equivalence wording)."""

import copy
import json

import pytest

from planning.blender.correction_contract import CorrectionPlan

from tests.aref.aref_harness import load_plan_artifact
from tests.aref.aref_plan import (PlanBindingError, canonical_plan_bytes, check_plan_binding,
                                  construct_plan, keep_only_target, plan_artifact_digest,
                                  plan_identity, plan_to_raw, raw_to_plan, real_plan,
                                  repoint_face_ids, select_pair)
from tests.aref.aref_pure import build_graph, make_pure_extractor
from tests.aref.fixtures import load_case


def _plan_for(fixture_id):
    spec = load_case(fixture_id)
    graph = build_graph(spec)
    scene, report = make_pure_extractor(spec)(graph)
    return spec, real_plan(report)


def test_p1_artifact_roundtrip_is_identity_stable():
    spec, plan = _plan_for("AREF-TEST-FX-C1-PAIR")
    raw = plan_to_raw(plan)
    rebuilt = raw_to_plan(raw)
    assert isinstance(rebuilt, CorrectionPlan)
    assert rebuilt.plan_id == plan.plan_id
    assert plan_to_raw(rebuilt) == raw
    assert plan_artifact_digest(raw) == plan_artifact_digest(plan_to_raw(rebuilt))


def test_p3_keep_only_target_sets_pinned_literals():
    """K2: the pinned branch sets source_revision_id=None and planner_version='1' as literals."""
    spec, plan = _plan_for("AREF-TEST-FX-AL-C1")
    reduced = keep_only_target(plan, "REMOVE_DUPLICATE_FACE", ("atlas-target",))
    assert reduced.source_revision_id is None
    assert reduced.planner_version == "1"
    assert reduced.dependencies == ()
    assert len(reduced.corrections) == 1
    assert reduced.source_report_digest == plan.source_report_digest
    # the retained correction is VERBATIM
    kept = reduced.corrections[0]
    base = [c for c in plan.corrections if c.mesh_id == "atlas-target"][0]
    assert plan_to_raw(reduced)["corrections"][0] == plan_to_raw(plan)["corrections"][
        list(plan.corrections).index(base)]


def test_p2_selected_pair_copies_planner_values():
    spec, plan = _plan_for("AREF-TEST-FX-C1-TRIPLE-S2")
    reduced = select_pair(plan, "REMOVE_DUPLICATE_FACE", (0, 2))
    assert reduced.source_revision_id == plan.source_revision_id
    assert reduced.planner_version == plan.planner_version
    assert len(reduced.corrections) == 1
    assert tuple(reduced.corrections[0].parameters["face_ids"]) == (0, 2)


def test_select_pair_rejects_non_unique():
    spec, plan = _plan_for("AREF-TEST-FX-C1-TRIPLE-S2")
    with pytest.raises(PlanBindingError, match="not unique"):
        select_pair(plan, "REMOVE_DUPLICATE_FACE", (0, 9))


def test_repoint_recomputes_content_addressed_id():
    spec, plan = _plan_for("AREF-TEST-FX-C1-PAIR")
    base = plan.corrections[0]
    repointed = repoint_face_ids(plan, "REMOVE_DUPLICATE_FACE",
                                 tuple(base.parameters["face_ids"]), (2, 0))
    c = repointed.corrections[0]
    assert list(c.parameters["face_ids"]) == [2, 0]
    assert c.correction_id != base.correction_id  # recomputed over the changed parameters
    assert repointed.plan_id == plan_identity(repointed).plan_id  # self-committing


def test_generated_artifact_matches_declared_identity():
    for fixture_id in ("AREF-TEST-FX-C1-PAIR", "AREF-TEST-FX-AL-C1-R"):
        spec = load_case(fixture_id)
        raw = load_plan_artifact(fixture_id)
        plan = raw_to_plan(raw)
        checks = check_plan_binding(plan, raw, spec.expected["plan"])
        assert checks["artifact_sha256"] == spec.expected["plan"]["artifact_sha256"]


def test_tampered_artifact_digest_fails_closed():
    """A tampered correction breaks the plan's self-commit OR the declared binding: both fail closed."""
    from planning.blender.correction_values import CorrectionInputError

    spec = load_case("AREF-TEST-FX-C1-PAIR")
    raw = load_plan_artifact("AREF-TEST-FX-C1-PAIR")
    tampered = json.loads(json.dumps(raw))
    tampered["corrections"][0]["parameters"]["face_ids"] = [0, 1]
    with pytest.raises((PlanBindingError, CorrectionInputError)):
        plan = raw_to_plan(tampered)  # self-commit check rejects inconsistent contents
        check_plan_binding(plan, tampered, spec.expected["plan"])
    # variant: contents re-committed (new plan_id) still fails the DECLARED identity binding
    tampered2 = json.loads(json.dumps(raw))
    tampered2["corrections"][0]["parameters"]["face_ids"] = [0, 1]
    tampered2["plan_id"] = ""  # force contract recompute on reconstruction
    plan2 = raw_to_plan(tampered2)
    with pytest.raises(PlanBindingError):
        check_plan_binding(plan2, tampered2, spec.expected["plan"])


def test_construction_rules_are_the_only_derivations():
    spec, plan = _plan_for("AREF-TEST-FX-C1-TRIPLE-S2")
    with pytest.raises(PlanBindingError, match="unsupported construction rule"):
        construct_plan(plan, "P9", "REMOVE_DUPLICATE_FACE", {})
