"""Deterministic live-gate harness for multi-step corrective recovery."""
from __future__ import annotations

from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.multi_step_corrective_executor import MultiStepCorrectiveExecutor


def run_gate(executor_factory, mutate_external_state):
    """Run a two-step correction while forcing an external state change between steps.

    The caller supplies a real Blender-backed executor factory and external mutation.
    The harness deliberately keeps the environment authoritative between every step.
    """
    executor = executor_factory()
    first = executor.execute_all(max_steps=1)
    if not first:
        raise RuntimeError("multi-step gate produced no first corrective receipt")

    mutate_external_state()

    second = executor.execute_all(max_steps=1)
    if not second:
        raise RuntimeError("multi-step gate failed to recover after external change")
    return first + second
