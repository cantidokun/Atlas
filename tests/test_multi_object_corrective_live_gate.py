from live_qwen_multi_object_corrective import TARGET, TARGETS, plan


def test_live_gate_plan_converges_on_all_object_properties():
    evidence = {
        name: {"location": list(target.location), "rotation": list(target.rotation_degrees)}
        for name, target in ((target.object_name, target) for target in TARGETS)
    }
    assert evidence == TARGET
    assert plan(evidence) == []


def test_live_gate_plan_repairs_interrupted_second_object():
    evidence = {
        TARGETS[0].object_name: {"location": [1.0, 0.0, 0.0], "rotation": [0.0, 0.0, 45.0]},
        TARGETS[1].object_name: {"location": [99.0, 0.0, 0.0], "rotation": [0.0, 0.0, 99.0]},
    }
    action = plan(evidence)[0]
    assert action.arguments["object_name"] == TARGETS[1].object_name
    assert action.tool == "move_object"
