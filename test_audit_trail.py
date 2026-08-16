from audit_trail import AuditTrail


def test_audit_trail_records_complete_lifecycle_in_order():
    audit = AuditTrail()
    audit.record_qwen_proposal('{"bad":true}', 1, False, "schema mismatch")
    audit.record_qwen_proposal('{"evidence":[],"actions":[]}', 2, True)
    audit.record_evidence(
        {"tool": "inspect_scene"},
        {"scene": "Scene", "total_objects": 6},
    )
    audit.record_authorization(True, action_count=2)
    audit.record_action(
        0,
        {"tool": "move_object", "object_name": "Goal_Left_post"},
        {"status": "moved"},
        True,
    )
    audit.record_action(
        1,
        {"tool": "move_object", "object_name": "Goal_Right_Post"},
        {"status": "moved"},
        True,
    )
    audit.record_verification({"midpoint": [0.0, 0.0, 0.0]}, True)

    snapshot = audit.snapshot()
    assert snapshot["event_count"] == 7
    assert [event["stage"] for event in snapshot["events"]] == [
        "qwen_proposal",
        "qwen_proposal",
        "evidence",
        "authorization",
        "execution",
        "execution",
        "verification",
    ]
    assert [event["index"] for event in snapshot["events"]] == list(range(7))
    assert snapshot["events"][0]["status"] == "rejected"
    assert snapshot["events"][-1]["status"] == "success"


def test_audit_trail_preserves_rejection_reason_and_write_boundary():
    audit = AuditTrail()
    audit.record_qwen_proposal("malformed", 1, False, "Every planned tool must have a name.")
    audit.record_authorization(False, reason="write authorization disabled")

    events = audit.snapshot()["events"]
    assert events[0]["reason"] == "Every planned tool must have a name."
    assert events[1]["status"] == "refused"
    assert events[1]["reason"] == "write authorization disabled"
