from live_blender_corrective_runtime_gate import OBJECT_A, OBJECT_B, TARGETS, plan


def _state(a=(1.0, 0.0, 0.0), ar=(0.0, 0.0, 45.0), b=(-1.0, 0.0, 0.0), br=(0.0, 0.0, -45.0)):
    return {
        OBJECT_A: {"location": list(a), "rotation": list(ar)},
        OBJECT_B: {"location": list(b), "rotation": list(br)},
    }


def test_live_gate_target_state_is_converged():
    assert plan(_state()) == []


def test_live_gate_detects_interruption_target():
    actions = plan(_state(b=(99.0, 0.0, 0.0), br=(0.0, 0.0, 99.0)))
    assert len(actions) == 1
    assert actions[0].arguments["object_name"] == OBJECT_B
