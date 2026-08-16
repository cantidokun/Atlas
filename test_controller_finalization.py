from controller_finalization import build_midpoint_final_answer


def _relationship(left, right, midpoint, distance=10.466, symmetric=False):
    return {
        "object_a": {"name": "Goal_Left_post", "location": left},
        "object_b": {"name": "Goal_Right_Post", "location": right},
        "midpoint": midpoint,
        "distance": distance,
        "symmetric_about_origin": symmetric,
    }


def _ledger(*results):
    return [
        {
            "tool": "inspect_object_relationship",
            "arguments": {},
            "result": result,
            "successful": True,
        }
        for result in results
    ]


def _move_history():
    return [
        {"tool": "move_object", "successful": True, "result": {"status": "moved"}},
        {"tool": "move_object", "successful": True, "result": {"status": "moved"}},
    ]


def test_builds_complete_state_aware_report():
    answer = build_midpoint_final_answer(
        _ledger(
            _relationship([0.0, 5.302, 0.0], [0.0, -5.164, 0.0], [0.0, 0.069, 0.0]),
            _relationship([0.0, 5.233, 0.0], [0.0, -5.233, 0.0], [0.0, 0.0, 0.0], symmetric=True),
        ),
        _move_history(),
    )

    assert answer is not None
    assert "INITIAL MEASURED STATE" in answer
    assert "[0.000, 5.302, 0.000]" in answer
    assert "[0.000, -5.164, 0.000]" in answer
    assert "[0.000, 0.069, 0.000]" in answer
    assert "CALCULATED TARGET STATE" in answer
    assert "[0.000, 5.233, 0.000]" in answer
    assert "[0.000, -5.233, 0.000]" in answer
    assert "- Positional adjustment: [0.000, -0.069, 0.000]" in answer
    assert "FINAL VERIFIED STATE" in answer
    assert "[0.000, 0.000, 0.000]" in answer
    assert "verified" in answer.lower()


def test_final_report_never_emits_negative_zero():
    answer = build_midpoint_final_answer(
        _ledger(
            _relationship([0.0, 5.302, 0.0], [0.0, -5.164, 0.0], [0.0, 0.069, 0.0]),
            _relationship([0.0, 5.233, 0.0], [0.0, -5.233, 0.0], [-0.0, -0.0, -0.0], symmetric=True),
        ),
        _move_history(),
    )

    assert answer is not None
    assert "-0.000" not in answer


def test_does_not_finalize_without_post_write_verification():
    answer = build_midpoint_final_answer(
        _ledger(
            _relationship([0.0, 5.302, 0.0], [0.0, -5.164, 0.0], [0.0, 0.069, 0.0]),
        ),
        _move_history(),
    )

    assert answer is None


def test_does_not_finalize_when_final_midpoint_is_wrong():
    answer = build_midpoint_final_answer(
        _ledger(
            _relationship([0.0, 5.302, 0.0], [0.0, -5.164, 0.0], [0.0, 0.069, 0.0]),
            _relationship([0.0, 5.233, 0.0], [0.0, -5.164, 0.0], [0.0, 0.0345, 0.0]),
        ),
        _move_history(),
    )

    assert answer is None
