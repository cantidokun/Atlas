"""Live production completion proof for the checkpointed autonomous runtime."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from planning.autonomous_runtime import AutonomousFutureRuntime
from planning.future_generator import FutureStep
from planning.production_autonomous_runtime_bridge import ProductionAutonomousRuntimeBridge
from planning.production_operation_lifecycle import ProductionOperationState
from planning.runtime_context import RuntimeContext
from planning.runtime_state import FutureRuntimeStateStore


def _runtime(state_path: Path) -> AutonomousFutureRuntime:
    steps = [
        FutureStep(0, "evidence.authoritative", "EVIDENCE", "Use authoritative evidence."),
        FutureStep(1, "target.evaluated", "TARGET", "Use the resolved target decision."),
        FutureStep(2, "action.production", "ACTION", "Execute the authorized production action.", {"tool": "set_object_rotation", "arguments": {"object_name": "Goal_Left_post", "rotation_degrees": [10.0, 20.0, 30.0]}}),
        FutureStep(3, "verification.pending", "VERIFICATION", "Verify the authoritative final state."),
        FutureStep(4, "complete", "COMPLETE", "Declare completion after verification."),
    ]
    context = RuntimeContext(
        stable_instructions="Execute only the authorized production future.",
        dynamic_state={"object_name": "Goal_Left_post", "target_rotation": [10.0, 20.0, 30.0]},
    )
    return AutonomousFutureRuntime(steps, FutureRuntimeStateStore(state_path), context)


def _run_case(verify_result: bool) -> dict:
    with tempfile.TemporaryDirectory(prefix="atlas-production-bridge-") as directory:
        runtime = _runtime(Path(directory) / "runtime.json")
        writes = []

        def execute(tool, arguments):
            writes.append({"tool": tool, "arguments": arguments})
            return {"ok": True, "tool": tool, "authoritative_state": {"rotation_degrees": [10.0, 20.0, 30.0]}}

        bridge = ProductionAutonomousRuntimeBridge(runtime, lambda snapshot: verify_result)
        result = bridge.run(
            execute,
            acknowledgements={
                "evidence.authoritative": {"fresh": True},
                "target.evaluated": {"satisfied": False},
            },
            verifications={"verification.pending": {"satisfied": True}},
        )
        return {
            "state": result.state.value,
            "completed": result.completed,
            "writes": len(writes),
            "reason": result.reason,
            "runtime_complete": result.snapshot.get("complete"),
            "runtime_blocked": result.snapshot.get("blocked"),
        }


def main() -> None:
    valid = _run_case(True)
    rejected = _run_case(False)
    output = {"valid_case": valid, "wrong_authoritative_state_case": rejected}
    print("ATLAS LIVE PRODUCTION AUTONOMOUS RUNTIME BRIDGE")
    print(json.dumps(output, indent=2, sort_keys=True))
    assert valid["state"] == ProductionOperationState.COMPLETED.value
    assert valid["completed"] is True
    assert valid["writes"] == 1
    assert rejected["state"] == ProductionOperationState.BLOCKED.value
    assert rejected["completed"] is False
    assert rejected["writes"] == 1
    print("ATLAS LIVE PRODUCTION COMPLETION VERIFIED-STATE GATE: PASS")
    print("ATLAS LIVE PRODUCTION COMPLETION WRONG-STATE BLOCK GATE: PASS")


if __name__ == "__main__":
    main()
