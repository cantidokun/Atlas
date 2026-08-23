from planning.transform_correction_plan import TransformTarget, plan_transform_correction


def test_planner_repairs_location_before_rotation_then_converges():
    targets = [TransformTarget("A", (1.0, 0.0, 0.0), (0.0, 0.0, 45.0))]
    evidence = {"A": {"location": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0]}}

    first = plan_transform_correction(evidence, targets, "fixture.blend")
    assert first[0].tool == "move_object"

    evidence["A"]["location"] = [1.0, 0.0, 0.0]
    second = plan_transform_correction(evidence, targets, "fixture.blend")
    assert second[0].tool == "set_object_rotation"

    evidence["A"]["rotation"] = [0.0, 0.0, 45.00005]
    assert plan_transform_correction(evidence, targets, "fixture.blend") == []


def test_planner_restarts_from_first_wrong_object_after_external_change():
    targets = [
        TransformTarget("A", (1.0, 0.0, 0.0), (0.0, 0.0, 45.0)),
        TransformTarget("B", (-1.0, 0.0, 0.0), (0.0, 0.0, -45.0)),
    ]
    evidence = {
        "A": {"location": [1.0, 0.0, 0.0], "rotation": [0.0, 0.0, 45.0]},
        "B": {"location": [99.0, 0.0, 0.0], "rotation": [0.0, 0.0, 99.0]},
    }

    action = plan_transform_correction(evidence, targets, "fixture.blend")[0]
    assert action.tool == "move_object"
    assert action.arguments["object_name"] == "B"


def test_negative_tolerance_is_rejected():
    targets = [TransformTarget("A", (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))]
    evidence = {"A": {"location": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0]}}

    try:
        plan_transform_correction(evidence, targets, "fixture.blend", tolerance=-1.0)
    except ValueError as exc:
        assert "tolerance" in str(exc)
    else:
        raise AssertionError("negative tolerance was accepted")
