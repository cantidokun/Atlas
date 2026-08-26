"""Live production proof for registry-backed durable continuation."""
from __future__ import annotations

import json

from action_plan import ActionSpec
from planning.digital_twin_identity import DigitalTwinIdentity
from planning.digital_twin_registry import DigitalTwinRegistry
from planning.digital_twin_revision import DigitalTwinRevision, RevisionKind
from planning.production_checkpoint_lifecycle import ProductionCheckpointLifecycle
from planning.production_operation_lifecycle import ProductionOperationState
from planning.production_registry_resume_lifecycle import ProductionRegistryResumeLifecycle


def _registry_and_revision():
    identity = DigitalTwinIdentity(twin_id="live-twin", entity_type="soccer_field", anchors=())
    registry = DigitalTwinRegistry()
    registry.register_identity(identity)
    revision = DigitalTwinRevision(
        twin_id="live-twin",
        revision_id="r1",
        sequence=1,
        kind=RevisionKind.RECONSTRUCTION,
        source_revision_id=None,
        source_fingerprint=identity.stable_fingerprint(),
    )
    registry.register_revision(revision)
    return registry, revision


def _checkpoint(registry, revision):
    return ProductionCheckpointLifecycle(registry).create_checkpoint(
        "live-task",
        revision,
        (),
        {"revision": "r1", "location": [0, 0, 0]},
        "authorization-1",
    )


def _run_case(verified: bool) -> dict:
    registry, revision = _registry_and_revision()
    checkpoint = _checkpoint(registry, revision)
    rehydrated_registry = DigitalTwinRegistry.from_snapshot(registry.snapshot())
    state = {"revision": "r1", "location": [1, 0, 0]}
    writes = []

    def observe():
        return dict(state)

    def execute(tool, arguments):
        writes.append({"tool": tool, "arguments": arguments})
        state["location"] = list(arguments["location"])
        return {"ok": True, "state": "ok"}

    lifecycle = ProductionRegistryResumeLifecycle(
        rehydrated_registry,
        checkpoint.snapshot(),
        revision,
        observe=observe,
        plan=lambda evidence: (
            []
            if evidence.get("location") == [2, 0, 0]
            else [
                ActionSpec(
                    tool="move_object",
                    arguments={"object_name": "Goal_Left_post", "location": [2, 0, 0]},
                )
            ]
        ),
        verify_final=lambda evidence: verified and evidence.get("location") == [2, 0, 0],
        executor=execute,
    )
    result = lifecycle.run()
    return {
        "state": result.state.value,
        "completed": result.completed,
        "writes": len(writes),
        "location": state["location"],
    }


def main() -> None:
    valid = _run_case(True)
    rejected = _run_case(False)
    output = {"registry_rehydrated_valid_case": valid, "registry_rehydrated_wrong_state_case": rejected}
    print("ATLAS LIVE PRODUCTION REGISTRY RESUME LIFECYCLE")
    print(json.dumps(output, indent=2, sort_keys=True))
    assert valid["state"] == ProductionOperationState.COMPLETED.value
    assert valid["completed"] is True
    assert valid["writes"] == 1
    assert rejected["state"] == ProductionOperationState.BLOCKED.value
    assert rejected["completed"] is False
    assert rejected["writes"] == 1
    print("ATLAS LIVE REGISTRY REHYDRATED COMPLETION GATE: PASS")
    print("ATLAS LIVE REGISTRY REHYDRATED WRONG-STATE BLOCK GATE: PASS")


if __name__ == "__main__":
    main()
