from __future__ import annotations

from planning.blender.parent_cycle import (
    CYCLE_CORRECTION_TYPE,
    _scene_digest,
    execute_repair_parent_cycle,
    plan_parent_cycle_correction,
)


def _scene():
    return {
        "objects": [
            {"object_id": "a", "parent_object_id": "b", "name": "a"},
            {"object_id": "b", "parent_object_id": "a", "name": "b"},
        ]
    }


def _auth(plan):
    return {
        "decision": "APPROVED",
        "correction_type": CYCLE_CORRECTION_TYPE,
        "correction_id": plan["correction_id"],
        "plan_id": plan["plan_id"],
        "source_report_digest": plan["source_report_digest"],
        "target_object_id": "a",
        "expected_parent_id": "b",
    }


def test_mutator_exception_is_explicit_non_success():
    scene = _scene()
    digest = _scene_digest(scene)
    plan = plan_parent_cycle_correction(scene, digest, target_object_id="a", expected_parent_id="b")
    calls = []

    def mutate(*args):
        calls.append(args)
        raise RuntimeError("simulated mutator failure")

    result = execute_repair_parent_cycle(plan, _auth(plan), extractor=lambda: (scene, _scene_digest(scene)), mutator=mutate)
    assert result.outcome == "MUTATION_FAILED"
    assert result.failure_code == "MUTATOR_EXCEPTION"
    assert calls == [("a", "b", None)]
    assert scene["objects"][0]["parent_object_id"] == "b"


def test_pre_mutation_extractor_exception_is_explicit_non_success():
    scene = _scene()
    digest = _scene_digest(scene)
    plan = plan_parent_cycle_correction(scene, digest, target_object_id="a", expected_parent_id="b")
    calls = []

    def extract():
        raise RuntimeError("simulated extraction failure")

    result = execute_repair_parent_cycle(plan, _auth(plan), extractor=extract, mutator=lambda *args: calls.append(args))
    assert result.outcome == "MUTATION_FAILED"
    assert result.failure_code == "EXTRACTION_FAILED"
    assert result.source_report_digest == digest
    assert calls == []


def test_post_mutation_extractor_exception_is_explicit_non_success():
    scene = _scene()
    digest = _scene_digest(scene)
    plan = plan_parent_cycle_correction(scene, digest, target_object_id="a", expected_parent_id="b")
    calls = []
    extraction_count = 0

    def extract():
        nonlocal extraction_count
        extraction_count += 1
        if extraction_count == 1:
            return scene, _scene_digest(scene)
        raise RuntimeError("simulated post-mutation extraction failure")

    def mutate(*args):
        calls.append(args)
        scene["objects"][0]["parent_object_id"] = None

    result = execute_repair_parent_cycle(plan, _auth(plan), extractor=extract, mutator=mutate)
    assert result.outcome == "MUTATION_FAILED"
    assert result.failure_code == "POST_EXTRACTION_FAILED"
    assert result.source_report_digest == digest
    assert calls == [("a", "b", None)]


def test_invalid_output_digest_is_not_reported_as_success():
    scene = _scene()
    digest = _scene_digest(scene)
    plan = plan_parent_cycle_correction(scene, digest, target_object_id="a", expected_parent_id="b")

    def mutate(*args):
        scene["objects"][0]["parent_object_id"] = None

    result = execute_repair_parent_cycle(
        plan,
        _auth(plan),
        extractor=lambda: (scene, None if scene["objects"][0]["parent_object_id"] is None else digest),
        mutator=mutate,
    )
    assert result.outcome == "POSTCONDITION_FAILED"
    assert result.failure_code == "OUTPUT_DIGEST_INVALID"
    assert result.output_report_digest is None
