from dataclasses import dataclass, field
from typing import Any, Dict, List

import pytest

from planning.unreal_agent import UnrealCapability, UnrealOperationKind
from planning.unreal_capability_registry import UnrealCapabilityRegistry
from planning.unreal_execution_boundary import UnrealExecutionBoundary
from planning.unreal_evidence_contract import UnrealEvidence


@dataclass
class RecordingAdapter:
    inspected: List[str] = field(default_factory=list)
    applied: List[str] = field(default_factory=list)
    verified: List[str] = field(default_factory=list)

    def inspect(self, operation, authorization_id):
        self.inspected.append(operation.name)
        return UnrealEvidence(
            operation_name=operation.name,
            entity_ids=operation.entity_ids,
            observed_state={"verified": False},
            verified=False,
            source="test",
        )

    def apply_authorized(self, operation, authorization_id):
        self.applied.append(operation.name)
        return UnrealEvidence(
            operation_name=operation.name,
            entity_ids=operation.entity_ids,
            observed_state={"verified": False},
            verified=False,
            source="test",
        )

    def verify(self, operation, authorization_id):
        self.verified.append(operation.name)
        return UnrealEvidence(
            operation_name=operation.name,
            entity_ids=operation.entity_ids,
            observed_state={"verified": False},
            verified=False,
            source="test",
        )


VERIFY_CASES = (
    (
        "verify_actor_location",
        {"expected_location": {"x": 1.0, "y": 2.0, "z": 3.0}},
    ),
    (
        "verify_actor_rotation",
        {"expected_rotation": {"pitch": 1.0, "yaw": 2.0, "roll": 3.0}},
    ),
    (
        "verify_actor_scale",
        {"expected_scale": {"x": 1.0, "y": 1.0, "z": 1.0}},
    ),
)


@pytest.mark.parametrize("tool,extra", VERIFY_CASES)
def test_actor_verification_tools_map_to_verify(tool: str, extra: Dict[str, Any]):
    boundary = UnrealExecutionBoundary(RecordingAdapter())
    operation, authorization_id = boundary.tool_to_operation(
        tool,
        {"entity_ids": ("FIELD_SURFACE",), "authorization_id": "auth-1", **extra},
    )

    assert authorization_id == "auth-1"
    assert operation.kind is UnrealOperationKind.VERIFY
    assert operation.entity_ids == ("FIELD_SURFACE",)


@pytest.mark.parametrize("tool,extra", VERIFY_CASES)
def test_actor_verification_tools_dispatch_to_verify_not_write(
    tool: str, extra: Dict[str, Any]
):
    adapter = RecordingAdapter()
    boundary = UnrealExecutionBoundary(adapter)

    result = boundary.execute(
        tool,
        {"entity_ids": ["FIELD_SURFACE"], "authorization_id": "auth-1", **extra},
    )

    assert result.operation_name == tool
    assert adapter.verified == [tool]
    assert adapter.applied == []
    assert adapter.inspected == []


def test_modify_actor_capability_explicitly_allows_verify():
    registry = UnrealCapabilityRegistry()
    spec = registry.validate(
        capability=UnrealCapability.MODIFY_ACTOR,
        kind=UnrealOperationKind.VERIFY,
    )
    assert UnrealOperationKind.VERIFY in spec.allowed_kinds
