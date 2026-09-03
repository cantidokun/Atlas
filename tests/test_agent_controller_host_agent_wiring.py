"""Source-level regression for the agent-facing controller host wiring."""

import ast
from pathlib import Path


AGENT_PATH = Path(__file__).resolve().parents[1] / "agent.py"


def _load_agent_tree():
    return ast.parse(AGENT_PATH.read_text(encoding="utf-8"))


def test_agent_constructs_controller_from_host():
    tree = _load_agent_tree()

    host_imported = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "controller.agent_controller_host"
        and any(alias.name == "AgentControllerHost" for alias in node.names)
        for node in tree.body
    )
    assert host_imported

    host_constructed = any(
        isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "AgentControllerHost"
        and any(
            isinstance(target, ast.Name) and target.id == "agent_controller_host"
            for target in node.targets
        )
        for node in tree.body
    )
    assert host_constructed


def test_agent_reuses_host_runtime_and_loop_seams():
    tree = _load_agent_tree()
    assignments = {
        target.id: node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }

    runtime = assignments.get("agent_controller_runtime")
    assert isinstance(runtime, ast.Attribute)
    assert isinstance(runtime.value, ast.Name)
    assert runtime.value.id == "agent_controller_host"
    assert runtime.attr == "runtime"

    loop = assignments.get("agent_controller_loop")
    assert isinstance(loop, ast.Attribute)
    assert isinstance(loop.value, ast.Name)
    assert loop.value.id == "agent_controller_host"
    assert loop.attr == "loop"


def test_agent_does_not_directly_construct_entrypoint_runtime_or_loop():
    tree = _load_agent_tree()

    direct_runtime_constructs = []
    direct_loop_constructs = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id == "AtlasAgentEntrypointRuntime":
            direct_runtime_constructs.append(node)
        if isinstance(node.func, ast.Name) and node.func.id == "AgentControllerLoopAdapter":
            direct_loop_constructs.append(node)

    assert not direct_runtime_constructs
    assert not direct_loop_constructs
