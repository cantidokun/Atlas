"""Tests for agent-originated Unreal production recovery requests."""

from controller.agent_entrypoint_contract import AgentControllerHandoff
from controller.agent_entrypoint_runtime import AtlasAgentEntrypointRuntime
from controller.agent_process_runtime import AtlasAgentProcessRuntime
from planning.agent_controller_production_request import AgentControllerProductionRequest
from planning.unreal_plan_authorization import UnrealPlanAuthorization
from planning.unreal_production_controller_integration import UnrealProductionControllerIntegration
from planning.unreal_production_runtime_adapter import UnrealProductionRuntimeAdapter
from planning.unreal_plan_executor import UnrealPlanExecutor
from planning.unreal_adapter_production import UnrealAdapterProduction
from tests.test_unreal_heterogeneous_production import ProductionTransport, _spec
from planning.unreal_production_operation import build_unreal_production_plan
from planning.unreal_production_planning_boundary import authorize_production_plan
from planning.unreal_production_recovery import build_production_reassessment_plan, issue_production_replacement_authorization
from planning.unreal_task_planner import UnrealTaskIntent

TARGET = "FIELD_SURFACE"


class RecordingIntegration(UnrealProductionControllerIntegration):
    def __init__(self):
        super().__init__(UnrealProductionRuntimeAdapter(UnrealPlanExecutor(UnrealAdapterProduction(ProductionTransport(fail_at=20), "agent-recovery-test"))))
        self.actions = []

    def start(self, authorized):
        self.actions.append("start")
        return super().start(authorized)

    def reassess(self, authorization):
        self.actions.append("reassess")
        return super().reassess(authorization)

    def resume(self, authorization):
        self.actions.append("resume_recovery")
        return super().resume(authorization)


def _runtime(integration):
    process = AtlasAgentProcessRuntime(unreal_production=integration)
    return AtlasAgentEntrypointRuntime(process)


def _intent(suffix):
    return UnrealTaskIntent(f"production-roundtrip-{suffix}", "full heterogeneous production", (TARGET,))


def test_agent_recovery_action_uses_fresh_reassessment_authorization():
    integration = RecordingIntegration()
    entrypoint = _runtime(integration)
    request = AgentControllerProductionRequest(entrypoint)
    production = build_unreal_production_plan(_intent("agent-recovery"), _spec())
    authorized = authorize_production_plan(production, "production-auth")

    started = request.submit(AgentControllerHandoff.from_fields(
        capability="production", provider="unreal", target_entity_ids=(TARGET,),
        intent_id="agent-recovery", context={"production": True, "authorized_production": authorized},
    ))
    assert started.snapshot.state == "awaiting_reassessment"

    reassessment_plan = build_production_reassessment_plan(production, started.snapshot.failure)
    reassessment_auth = UnrealPlanAuthorization.issue(reassessment_plan, "reassessment-auth")
    reassessed = request.submit(AgentControllerHandoff.from_fields(
        capability="production", provider="unreal", target_entity_ids=(TARGET,),
        intent_id="agent-recovery", context={
            "production": True, "recovery_action": "reassess",
            "reassessment_authorization": reassessment_auth,
        },
    ))
    assert reassessed.snapshot.state == "awaiting_replacement"
    assert integration.actions == ["start", "reassess"]


def test_agent_recovery_requires_separate_replacement_authorization():
    integration = RecordingIntegration()
    entrypoint = _runtime(integration)
    request = AgentControllerProductionRequest(entrypoint)
    production = build_unreal_production_plan(_intent("agent-recovery-auth"), _spec())
    started = request.submit(AgentControllerHandoff.from_fields(
        capability="production", provider="unreal", target_entity_ids=(TARGET,),
        intent_id="agent-recovery-auth", context={"production": True, "authorized_production": authorize_production_plan(production, "production-auth")},
    ))
    reassessment_plan = build_production_reassessment_plan(production, started.snapshot.failure)
    reassessed = request.submit(AgentControllerHandoff.from_fields(
        capability="production", provider="unreal", target_entity_ids=(TARGET,),
        intent_id="agent-recovery-auth", context={"production": True, "recovery_action": "reassess", "reassessment_authorization": UnrealPlanAuthorization.issue(reassessment_plan, "reassessment-auth")},
    ))
    replacement_plan = reassessed.snapshot.recovery.replacement_plan
    replacement_auth = issue_production_replacement_authorization(replacement_plan, "replacement-auth")
    integration._runtime._bridge._executor._adapter._transport.fail_at = 999
    resumed = request.submit(AgentControllerHandoff.from_fields(
        capability="production", provider="unreal", target_entity_ids=(TARGET,),
        intent_id="agent-recovery-auth", context={"production": True, "recovery_action": "resume_recovery", "replacement_authorization": replacement_auth},
    ))
    assert resumed.snapshot.state == "recovery_complete"
    assert integration.actions == ["start", "reassess", "resume_recovery"]
