"""Run the existing Atlas agent with deterministic controller takeover.

This is a thin compatibility entrypoint. It loads the existing ``agent.py``
source, finds its existing reasoning loop, and inserts the controller hook at
the point immediately before the model is asked to reason.

The existing evidence ledger, tool executor, final validator, and Qwen/Ollama
loop remain in ``agent.py``. The controller only takes over when the current
assessment has entered the explicitly authorized midpoint workflow and a
mandatory action remains.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
AGENT_PATH = ROOT / "agent.py"


HOOK_SOURCE = r'''
# ============================================================
# CONTROLLER TAKEOVER
# ============================================================
# Python may temporarily own the mandatory modification sequence.
# Qwen remains responsible for normal reasoning and all non-controller work.
_controller_forced = controller_integration.before_model_tool_execution()

if (
    _controller_forced is not None
    and _controller_forced.get("kind") != "complete"
):
    _controller_result = controller_integration.execute_forced_action(
        lambda tool_name, tool_arguments: TOOLS[tool_name](**tool_arguments)
    )

    _controller_tool = _controller_result.get("tool")
    _controller_arguments = _controller_result.get("arguments", {})
    _controller_result_payload = _controller_result.get("result", {})
    _controller_call_id = "atlas-controller-" + str(step)

    # Add a synthetic assistant tool request so the following tool result
    # remains valid conversation history for Ollama/Qwen.
    messages.append(
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": _controller_call_id,
                    "type": "function",
                    "function": {
                        "name": _controller_tool,
                        "arguments": _controller_arguments,
                    },
                }
            ],
        }
    )

    messages.append(
        {
            "role": "tool",
            "content": json.dumps(_controller_result_payload),
        }
    )

    messages.append(
        {
            "role": "system",
            "content": (
                "ATLAS CONTROLLER UPDATE:\n"
                "Python executed the mandatory controller action. "
                "Treat the following result as authoritative evidence.\n\n"
                + json.dumps(_controller_result_payload, indent=2)
                + "\n\nATLAS EVIDENCE LEDGER:\n"
                + json.dumps(evidence_ledger, indent=2)
            ),
        }
    )

    # A completed controller task has authoritative BEFORE, TARGET and
    # independently verified AFTER state. Do not spend another Qwen reasoning
    # cycle trying to rediscover a final answer that Python can construct from
    # the verified evidence. This is a deterministic recovery path for
    # controller-owned modifications; normal non-controller tasks still use
    # the Qwen final-answer validator in agent.py.
    if controller_integration.complete:
        from controller_finalization import build_midpoint_final_answer

        _controller_final_answer = build_midpoint_final_answer(
            evidence_ledger,
            tool_execution_history,
        )

        if _controller_final_answer is not None:
            print("\n========== ATLAS FINAL RESPONSE ==========\n")
            print(_controller_final_answer)
            raise SystemExit(0)

    continue
'''


def _controller_hook_nodes() -> list[ast.stmt]:
    """Parse the hook source into AST nodes for insertion into agent.py."""
    return ast.parse(HOOK_SOURCE).body


def build_controller_enabled_source(agent_source: str) -> str:
    """Return agent.py source with one controller hook inserted.

    The transformation is intentionally strict: exactly one top-level
    reasoning loop must contain the existing ``requests.post`` model call.
    If the expected structure is not found, execution stops instead of
    silently running an unmodified agent.
    """
    tree = ast.parse(agent_source, filename=str(AGENT_PATH))

    import_node = ast.ImportFrom(
        module="controller_integration",
        names=[ast.alias(name="AgentControllerIntegration", asname=None)],
        level=0,
    )
    tree.body.insert(0, import_node)

    # Find the existing module-level reasoning loop.
    candidate_loops = []
    for node in tree.body:
        if not isinstance(node, ast.For):
            continue

        source = ast.unparse(node)
        if "requests.post" in source and "OLLAMA_URL" in source:
            candidate_loops.append(node)

    if len(candidate_loops) != 1:
        raise RuntimeError(
            "Atlas controller entrypoint expected exactly one model reasoning "
            f"loop, found {len(candidate_loops)}."
        )

    loop = candidate_loops[0]

    # The agent already creates evidence_ledger and tool_execution_history at
    # module scope. Create the controller beside that existing state.
    state_inserted = False
    for index, node in enumerate(tree.body):
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "tool_execution_history"
                for target in node.targets
            )
        ):
            initialization = ast.parse(
                "controller_integration = AgentControllerIntegration("
                "file_name='goalpost_test.blend', "
                "task_text=CURRENT_TASK, "
                "evidence_ledger=evidence_ledger, "
                "tool_execution_history=tool_execution_history"
                ")"
            ).body[0]
            tree.body.insert(index + 1, initialization)
            state_inserted = True
            break

    if not state_inserted:
        raise RuntimeError(
            "Could not find tool_execution_history initialization in agent.py."
        )

    # Insert the hook before the first existing statement in the reasoning
    # loop. The hook runs before requests.post, allowing Python to take over
    # before Qwen gets another chance to choose a mandatory action.
    loop.body[0:0] = _controller_hook_nodes()

    ast.fix_missing_locations(tree)
    return ast.unparse(tree) + "\n"


def main() -> None:
    source = AGENT_PATH.read_text(encoding="utf-8")
    transformed = build_controller_enabled_source(source)

    namespace = {
        "__name__": "__main__",
        "__file__": str(AGENT_PATH),
    }

    exec(compile(transformed, str(AGENT_PATH), "exec"), namespace)


if __name__ == "__main__":
    main()
