from live_blender_corrective_runtime_gate import TARGETS, plan


def test_generalized_gate_converges_on_target_state():
    evidence = {
        target.object_name: {
            "location": list(target.location),
            "rotation": list(target.rotation_degrees),
        }
        for target in TARGETS
    }
    assert plan(evidence) == []


def test_generalized_gate_detects_external_corruption():
    evidence = {
        TARGETS[0].object_name: {"location": [1.0, 0.0, 0.0], "rotation": [0.0, 0.0, 45.0]},
        TARGETS[1].object_name: {"location": [99.0, 0.0, 0.0], "rotation": [0.0, 0.0, 99.0]},
    }
    actions = plan(evidence)
    assert actions
    assert actions[0].arguments["object_name"] == TARGETS[1].object_name
