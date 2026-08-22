"""Live Qwen-driven Blender marker task using the generic TaskRuntimeSession."""
from typing import Any, Dict, List

from planning.marker_task import marker_task_definition
from planning.task_runtime import TaskRuntimeSession


def _reduce_marker_evidence(evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
    state: Dict[str, Any] = {}
    for result in evidence:
        state.update(result)
    return state


def run_marker_session(file_name: str, execute, authorize) -> TaskRuntimeSession:
    task = marker_task_definition(file_name)
    session = TaskRuntimeSession(task, execute, _reduce_marker_evidence)
    session.acquire_initial_evidence()
    state = session.evaluate_target()
    if not state.satisfied:
        authorize(session.task)
        session.authorize(f"live:marker-creation:{file_name}")
        session.execute_authorized_action()
    final = session.acquire_post_action_evidence()
    verification = session.verify_post_action(final)
    if task.verify_after_action and not verification.satisfied:
        raise RuntimeError(f"Independent marker verification failed: {verification.failed}")
    session.finalize()
    if not session.complete:
        raise RuntimeError(f"Marker task did not complete: {session.snapshot()}")
    return session
