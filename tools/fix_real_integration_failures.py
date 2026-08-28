"""Apply the remaining real Unreal integration fixes locally.

This script is intentionally deterministic and fail-closed: it refuses to edit files
when the expected source anchors are not present exactly once.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CPP = ROOT / "unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Private/AtlasTransportServer.cpp"
BLUEPRINT_TEST = ROOT / "tests/test_unreal_blueprint_real_integration.py"
RENDER_TEST = ROOT / "tests/test_unreal_render_real_integration.py"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one patch anchor in {path}, found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def patch_cpp() -> None:
    replace_once(
        CPP,
        '''    if(Blueprint->GeneratedClass) State->SetStringField(TEXT("generated_class"),Blueprint->GeneratedClass->GetPathName());
    else State->SetStringField(TEXT("generated_class"),TEXT(""));
    O=State;
''',
        '''    if(Blueprint->GeneratedClass) State->SetStringField(TEXT("generated_class"),Blueprint->GeneratedClass->GetPathName());
    else State->SetStringField(TEXT("generated_class"),TEXT(""));

    TSharedPtr<FJsonObject> Metadata = MakeShareable(new FJsonObject);
    if (TMap<FName, FString>* MetadataValues = FMetaData::GetMapForObject(Blueprint))
    {
        for (const TPair<FName, FString>& Pair : *MetadataValues)
        {
            Metadata->SetStringField(Pair.Key.ToString(), Pair.Value);
        }
    }
    State->SetObjectField(TEXT("metadata"), Metadata);
    O=State;
''',
    )


def patch_blueprint_test() -> None:
    # The production WRITE operation already returns fresh inspected Blueprint state.
    # The real integration test should therefore be able to assert metadata on that
    # evidence as well as after compilation and on a subsequent fresh READ.
    # No test-side workaround is required once the transport exposes metadata.
    return


def patch_render_test() -> None:
    replace_once(
        RENDER_TEST,
        'from planning.unreal_task_planner import UnrealTaskPlanner\n',
        'from planning.unreal_task_planner import UnrealTaskPlan, UnrealTaskPlanner\n',
    )
    replace_once(
        RENDER_TEST,
        '''        fresh = executor.execute(
            planner.plan_render_configuration(_intent("real-render-fresh-inspection"), CONFIG)[:1] and
            __import__("planning.unreal_task_planner", fromlist=["UnrealTaskPlan"]).UnrealTaskPlan(
                "real-render-fresh-inspection",
                (plan.operations[0],),
            ),
            "real-render-fresh-auth",
        )
''',
        '''        fresh_plan = UnrealTaskPlan(
            "real-render-fresh-inspection",
            (plan.operations[0],),
        )
        fresh = executor.execute(fresh_plan, "real-render-fresh-auth")
''',
    )


def main() -> None:
    patch_cpp()
    patch_blueprint_test()
    patch_render_test()
    print("Applied real Unreal integration fixes.")


if __name__ == "__main__":
    main()
