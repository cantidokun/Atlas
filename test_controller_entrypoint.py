"""Static tests for the controller-enabled Atlas entrypoint."""

import ast

from run_agent_with_controller import build_controller_enabled_source


def test_controller_hook_is_inserted_once():
    source = '''
import requests

CURRENT_TASK = "task"
evidence_ledger = []
tool_execution_history = []

for step in range(2):
    response = requests.post(OLLAMA_URL)
'''

    transformed = build_controller_enabled_source(source)

    assert transformed.count("before_model_tool_execution") == 1
    assert transformed.count("AgentControllerIntegration") == 2
    assert transformed.count("controller_integration =") == 1


def test_transformed_source_has_controller_before_model_call():
    source = '''
import requests

CURRENT_TASK = "task"
evidence_ledger = []
tool_execution_history = []

for step in range(2):
    response = requests.post(OLLAMA_URL)
'''

    transformed = build_controller_enabled_source(source)
    tree = ast.parse(transformed)

    loop = next(
        node for node in tree.body
        if isinstance(node, ast.For)
        and "requests.post" in ast.unparse(node)
    )

    hook_index = next(
        index for index, node in enumerate(loop.body)
        if "before_model_tool_execution" in ast.unparse(node)
    )
    post_index = next(
        index for index, node in enumerate(loop.body)
        if "requests.post" in ast.unparse(node)
    )

    assert hook_index < post_index


def test_completed_controller_has_deterministic_finalization_path():
    source = '''
import requests

CURRENT_TASK = "task"
evidence_ledger = []
tool_execution_history = []

for step in range(2):
    response = requests.post(OLLAMA_URL)
'''

    transformed = build_controller_enabled_source(source)

    assert "build_midpoint_final_answer" in transformed
    assert "controller_integration.complete" in transformed
    assert "raise SystemExit(0)" in transformed


def test_complete_signal_is_finalized_before_model_can_run_again():
    source = '''
import requests

CURRENT_TASK = "task"
evidence_ledger = []
tool_execution_history = []

for step in range(2):
    response = requests.post(OLLAMA_URL)
'''

    transformed = build_controller_enabled_source(source)
    tree = ast.parse(transformed)
    loop = next(
        node for node in tree.body
        if isinstance(node, ast.For)
        and "requests.post" in ast.unparse(node)
    )

    complete_index = next(
        index for index, node in enumerate(loop.body)
        if "controller_integration.complete" in ast.unparse(node)
    )
    post_index = next(
        index for index, node in enumerate(loop.body)
        if "requests.post" in ast.unparse(node)
    )
    continue_index = next(
        index for index, node in enumerate(loop.body)
        if isinstance(node, ast.Continue)
    )

    assert complete_index < post_index
    assert complete_index < continue_index


def test_unexpected_agent_shape_fails_closed():
    source = '''
CURRENT_TASK = "task"
evidence_ledger = []
tool_execution_history = []
'''

    try:
        build_controller_enabled_source(source)
    except RuntimeError as error:
        assert "expected exactly one model reasoning loop" in str(error)
    else:
        raise AssertionError("Expected controller entrypoint to fail closed")
