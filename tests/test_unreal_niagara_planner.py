from planning.unreal_agent import UnrealTaskIntent, UnrealCapability, UnrealOperationKind
from planning.unreal_task_planner import UnrealTaskPlanner


def test_niagara_variant_plan_is_ordered_and_fail_closed():
    intent = UnrealTaskIntent("niagara-1", "apply spark effect", ("FIELD_SURFACE",))
    plan = UnrealTaskPlanner().plan_niagara_variant(intent, {"name": "sparks"})
    assert [op.name for op in plan.operations] == [
        "inspect_target_actors", "inspect_niagara_state", "apply_niagara_variant", "verify_niagara_variant"
    ]
    assert plan.operations[2].capability is UnrealCapability.NIAGARA
    assert plan.operations[2].kind is UnrealOperationKind.WRITE
    assert plan.operations[2].arguments["niagara_variant"] == {"name": "sparks"}


def test_niagara_variant_rejects_extra_fields():
    intent = UnrealTaskIntent("niagara-2", "apply", ("FIELD_SURFACE",))
    try:
        UnrealTaskPlanner().plan_niagara_variant(intent, {"name": "sparks", "enabled": True})
    except ValueError as exc:
        assert "exactly name" in str(exc)
    else:
        raise AssertionError("expected fail-closed Niagara schema validation")
