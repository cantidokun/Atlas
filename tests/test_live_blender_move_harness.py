from pathlib import Path

from planning.blender_execution_receipt import BlenderExecutionReceipt
from planning.blender_result_contract import BlenderExecutionResult
from scripts.run_live_blender_move import run_live_move


class FakeBoundary:
    def __init__(self):
        self.calls = []
        self.location = [1.0, 2.0, 3.0]

    def execute_verified(self, tool, arguments):
        self.calls.append(("inspect", tool, dict(arguments)))
        return BlenderExecutionResult(
            tool=tool,
            ok=True,
            state="inspected",
            details={
                "objects": [
                    {"name": "Goal_Left_post", "location": list(self.location)}
                ]
            },
        )

    def execute_with_receipt(self, tool, arguments):
        self.calls.append(("write", tool, dict(arguments)))
        self.location = list(arguments["location"])
        result = BlenderExecutionResult(
            tool=tool,
            ok=True,
            state="moved",
            details={
                "object_name": arguments["object_name"],
                "location": list(self.location),
            },
        )
        receipt = BlenderExecutionReceipt.create(tool, arguments, result)
        return result, receipt


def test_live_harness_verifies_from_fresh_inspection_and_restores(monkeypatch, tmp_path):
    fixture = tmp_path / "atlas_live_mutation.blend"
    fixture.write_bytes(b"fixture")
    fake = FakeBoundary()

    monkeypatch.setattr(
        "scripts.run_live_blender_move.BlenderProcessExecutor",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        "scripts.run_live_blender_move.BlenderExecutionBoundary",
        lambda executor: fake,
    )

    run_live_move(
        str(fixture),
        "blender",
        "Goal_Left_post",
        0.25,
        "test-stage11",
    )

    assert fake.calls[0][0] == "inspect"
    assert fake.calls[1][0] == "write"
    assert fake.calls[1][2]["location"] == [1.25, 2.0, 3.0]
    assert fake.calls[2][0] == "inspect"
    assert fake.calls[3][0] == "write"
    assert fake.calls[3][2]["location"] == [1.0, 2.0, 3.0]
    assert fake.calls[4][0] == "inspect"


def test_live_harness_requires_fixture(tmp_path):
    missing = Path(tmp_path) / "missing.blend"
    try:
        run_live_move(
            str(missing),
            "blender",
            "Goal_Left_post",
            0.25,
            "test-stage11",
        )
    except FileNotFoundError as exc:
        assert "fixture not found" in str(exc)
    else:
        raise AssertionError("missing Blender fixture must fail closed")
