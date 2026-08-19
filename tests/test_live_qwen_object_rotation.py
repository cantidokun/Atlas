from action_plan import ActionSpec
from evidence_plan import EvidenceRequest
from live_qwen_object_rotation import CORRECT_FILE, TARGET_OBJECT, TARGET_ROTATION, task_definition


def test_live_rotation_task_definition_uses_typed_evidence_request():
    definition = task_definition(CORRECT_FILE)

    assert len(definition.evidence) == 1
    assert isinstance(definition.evidence[0], EvidenceRequest)
    assert definition.evidence[0] == EvidenceRequest(
        "inspect_object_transform",
        {"file_name": CORRECT_FILE, "object_name": TARGET_OBJECT},
        "inspect_object_transform",
    )


def test_live_rotation_task_definition_remains_typed_and_deterministic():
    definition = task_definition(CORRECT_FILE)

    assert definition.actions == (
        ActionSpec(
            "set_object_rotation",
            {
                "file_name": CORRECT_FILE,
                "object_name": TARGET_OBJECT,
                "rotation_degrees": TARGET_ROTATION,
            },
            "set_object_rotation",
        ),
    )
    assert definition.allowed_action_tools == {"set_object_rotation"}
    assert definition.allow_writes is True
    assert definition.verify_after_action is True
