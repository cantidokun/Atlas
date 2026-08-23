from live_qwen_multi_object_corrective import OBJECT_A, OBJECT_B, TARGET, plan


def test_live_plan_repairs_one_property_at_a_time_in_stable_object_order():
    bad = {
        OBJECT_A: {"location": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0]},
        OBJECT_B: dict(TARGET[OBJECT_B]),
    }

    first = plan(bad)
    assert first[0].tool == "move_object"
    assert first[0].arguments["object_name"] == OBJECT_A

    after_move = dict(bad)
    after_move[OBJECT_A] = {"location": TARGET[OBJECT_A]["location"], "rotation": bad[OBJECT_A]["rotation"]}
    second = plan(after_move)
    assert second[0].tool == "set_object_rotation"
    assert second[0].arguments["object_name"] == OBJECT_A

    interrupted = {key: dict(value) for key, value in TARGET.items()}
    interrupted[OBJECT_B] = {"location": [99.0, 0.0, 0.0], "rotation": [0.0, 0.0, 99.0]}
    third = plan(interrupted)
    assert third[0].tool == "move_object"
    assert third[0].arguments["object_name"] == OBJECT_B

    repaired_location = dict(interrupted)
    repaired_location[OBJECT_B] = {
        "location": TARGET[OBJECT_B]["location"],
        "rotation": interrupted[OBJECT_B]["rotation"],
    }
    fourth = plan(repaired_location)
    assert fourth[0].tool == "set_object_rotation"
    assert fourth[0].arguments["object_name"] == OBJECT_B

    assert plan(TARGET) == []
