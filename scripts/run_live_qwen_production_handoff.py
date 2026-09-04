"""Live Qwen proposal-to-Atlas authorization handoff proof.

This harness contacts the local Ollama Qwen provider, crosses the proposal into
the canonical semantic task handoff, explicitly requests Atlas authorization,
and stops there. It deliberately never executes a tool or touches Blender.
"""

from __future__ import annotations

import argparse
import json

from qwen.ollama_provider import OllamaQwenProvider
from qwen.production_handoff import QwenProductionTaskHandoff


DEFAULT_OBJECTIVE = (
    "Prepare the soccer goal for a broadcast shot using file scene.blend and object Goal_Left_post. "
    "Set target_location to [0.25, 5.302, 0.0] and target_rotation to [0.0, 0.0, 15.0]."
)
DEFAULT_CONTEXT = (
    "Verified production inputs: file_name=scene.blend; object_name=Goal_Left_post; "
    "target_location=[0.25, 5.302, 0.0]; target_rotation=[0.0, 0.0, 15.0]. "
    "Use only the canonical Atlas catalog workflow and return its name and numeric version separately."
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Live Qwen proposal-to-Atlas authorization handoff proof")
    parser.add_argument("--objective", default=DEFAULT_OBJECTIVE)
    parser.add_argument("--context", default=DEFAULT_CONTEXT)
    parser.add_argument("--authorization-id", default="atlas-qwen-production-handoff-live")
    parser.add_argument("--url", default=None, help="Optional Ollama chat endpoint override.")
    parser.add_argument("--model", default=None, help="Optional Qwen model override.")
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    provider = OllamaQwenProvider(
        url=args.url or "http://localhost:11434/api/chat",
        model=args.model or "qwen3:8b",
        timeout=args.timeout,
    )
    proposal = provider.propose(args.objective, context=args.context)
    handoff = QwenProductionTaskHandoff.from_proposal(proposal)
    handoff.verify_integrity()
    action_plan, authorization = handoff.authorize(args.authorization_id)

    catalog = (handoff.semantic_task.metadata or {}).get("workflow_catalog", {})
    parameters = (handoff.semantic_task.metadata or {}).get("workflow_parameters", {})

    print("LIVE QWEN ATLAS AUTHORIZATION HANDOFF VERIFIED")
    print(f"workflow={catalog.get('name')}")
    print(f"workflow_version={catalog.get('version')}")
    print("proposal_validation=verified")
    print("semantic_task_compilation=verified")
    print("handoff_integrity=verified")
    print("catalog_provenance=verified")
    print("atlas_authorization_path=existing")
    print(f"authorization_id={authorization.authorization_id}")
    print(f"authorization_digest={authorization.plan_digest}")
    print(f"workflow_parameters={json.dumps(parameters, sort_keys=True)}")
    print(f"action_plan_authorized={action_plan.authorized}")
    print("qwen_authorization_issued=not_applicable")
    print("execution=not_attempted")
    print("blender_mutation=not_attempted")


if __name__ == "__main__":
    main()
