"""Regression coverage for entrypoint-owned controller context lifecycle."""

from controller.agent_controller_host import AgentControllerHost
from controller.agent_controller_loop import AgentControllerLoopAdapter
from controller.agent_entrypoint_runtime import AtlasAgentEntrypointRuntime


def test_default_entrypoint_runtime_owns_one_execution_context():
    runtime = AtlasAgentEntrypointRuntime()
    loop = AgentControllerLoopAdapter(runtime)

    assert runtime.execution_context is loop.execution_context


def test_host_and_runtime_share_the_same_execution_context():
    host = AgentControllerHost()

    assert host.execution_context is host.runtime.execution_context
    assert host.execution_context is host.loop.execution_context


def test_host_reuses_supplied_runtime_context_identity():
    runtime = AtlasAgentEntrypointRuntime()
    host = AgentControllerHost(runtime=runtime)

    assert host.runtime is runtime
    assert host.execution_context is runtime.execution_context
    assert host.loop.execution_context is runtime.execution_context
