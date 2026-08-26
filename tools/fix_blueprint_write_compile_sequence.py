"""Patch UnrealPlanExecutor for Blueprint mutation -> compile -> verify plans."""

from pathlib import Path

TARGET = Path("planning/unreal_plan_executor.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one {label} anchor, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")

    old_expected = '''        return {"set_actor_location":"verify_actor_location","set_actor_rotation":"verify_actor_rotation","set_actor_scale":"verify_actor_scale","apply_material_variant":"verify_material_variant","apply_niagara_variant":"verify_niagara_variant","set_sequencer_playback_range":"verify_sequencer_playback_range"}.get(write_operation.name)'''
    new_expected = '''        return {"set_actor_location":"verify_actor_location","set_actor_rotation":"verify_actor_rotation","set_actor_scale":"verify_actor_scale","apply_material_variant":"verify_material_variant","apply_niagara_variant":"verify_niagara_variant","set_sequencer_playback_range":"verify_sequencer_playback_range","compile_blueprint":"verify_blueprint_state"}.get(write_operation.name)'''
    if old_expected in text:
        text = replace_once(text, old_expected, new_expected, "expected verifier map")

    old_shape = '''    @classmethod
    def _validate_execution_shape(cls, plan):
        for index, operation in enumerate(plan.operations):
            if operation.kind is not UnrealOperationKind.WRITE: continue
            if index + 1 >= len(plan.operations): raise UnrealPlanExecutionError(f"Write operation {index} ('{operation.name}') must be followed by verification")
            verification=plan.operations[index+1]
            if verification.kind is not UnrealOperationKind.VERIFY: raise UnrealPlanExecutionError(f"Write operation {index} ('{operation.name}') must be immediately followed by verification")
            if tuple(verification.entity_ids)!=tuple(operation.entity_ids): raise UnrealPlanExecutionError(f"Write operation {index} ('{operation.name}') and verification must target the same entities")
            expected=cls._expected_verifier(operation)
            if expected is not None and verification.name!=expected: raise UnrealPlanExecutionError(f"Write operation {index} ('{operation.name}') must be followed by '{expected}', not '{verification.name}'")
'''
    new_shape = '''    @classmethod
    def _validate_execution_shape(cls, plan):
        for index, operation in enumerate(plan.operations):
            if operation.kind is not UnrealOperationKind.WRITE:
                continue
            if index + 1 >= len(plan.operations):
                raise UnrealPlanExecutionError(f"Write operation {index} ('{operation.name}') must be followed by verification")
            verification = plan.operations[index + 1]

            # Blueprint metadata is intentionally staged through compilation:
            # inspect -> set metadata -> compile -> verify. The metadata write
            # is not independently verifiable until the compiled Blueprint has
            # been saved by the compile operation.
            if operation.name == "set_blueprint_metadata":
                if verification.name != "compile_blueprint" or verification.kind is not UnrealOperationKind.WRITE:
                    raise UnrealPlanExecutionError(
                        f"Write operation {index} ('{operation.name}') must be followed by 'compile_blueprint'"
                    )
                if tuple(verification.entity_ids) != tuple(operation.entity_ids):
                    raise UnrealPlanExecutionError(
                        f"Write operation {index} ('{operation.name}') and compilation must target the same entities"
                    )
                continue

            if verification.kind is not UnrealOperationKind.VERIFY:
                raise UnrealPlanExecutionError(f"Write operation {index} ('{operation.name}') must be immediately followed by verification")
            if tuple(verification.entity_ids) != tuple(operation.entity_ids):
                raise UnrealPlanExecutionError(f"Write operation {index} ('{operation.name}') and verification must target the same entities")
            expected = cls._expected_verifier(operation)
            if expected is not None and verification.name != expected:
                raise UnrealPlanExecutionError(f"Write operation {index} ('{operation.name}') must be followed by '{expected}', not '{verification.name}'")
'''
    if old_shape in text:
        text = replace_once(text, old_shape, new_shape, "execution-shape validator")
    elif 'operation.name == "set_blueprint_metadata"' not in text:
        raise SystemExit("execution-shape validator anchor not found")

    TARGET.write_text(text, encoding="utf-8")
    print(f"Patched {TARGET}")


if __name__ == "__main__":
    main()
