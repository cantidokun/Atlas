"""Regression tests for classified capability identity stability."""

import pytest

from controller.agent_process_runtime import AtlasAgentProcessRuntime
from controller.agent_task_request import AgentTaskRequest


def test_execute_classified_rejects_capability_change_after_classification():
    process = AtlasAgentProcessRuntime()
    first_handler = type("FirstHandler", (), {"execute": lambda self, request: "first"})()
    second_handler = type("SecondHandler", (), {"execute": lambda self, request: "second"})()

    dispatcher = process.runtime.registry.dispatcher
    dispatcher.register(
        "first_capability",
        lambda request: request.normalized_capability == "task",
        first_handler,
    )

    classified = process.classify(AgentTaskRequest("task"))
    assert classified.route.selection.name == "first_capability"

    dispatcher.register(
        "second_capability",
        lambda request: request.normalized_capability == "task",
        second_handler,
    )

    with pytest.raises(ValueError, match="classified capability changed"):
        process.execute_classified(classified)
