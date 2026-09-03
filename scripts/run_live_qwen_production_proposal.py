"""Live Qwen-to-catalog proposal smoke test.

This harness contacts the local Ollama Qwen provider, validates the model output,
resolves it through the trusted soccer-production catalog, and prints the
resulting semantic task contract. It deliberately stops before authorization,
persistence, execution, or recovery so the live proof cannot mutate Blender.
"""

from __future__ import annotations

import argparse
import json

from qwen.ollama_provider import OllamaQwenProvider
from qwen.production_proposal import compile_qwen_production_proposal


def main() -> None:
    parser = argparse.ArgumentParser(description="Live Qwen proposal-only Atlas smoke test")
    parser.add_argument(
        "--objective",
        default="Prepare the soccer goal for a broadcast shot.",
        help="Semantic soccer-production objective supplied to Qwen.",
    )
    parser.add_argument(
        "--context",
        default="Use the trusted Atlas soccer-production workflow catalog; do not invent a workflow.",
        help="Optional verified context supplied to Qwen.",
    )
    parser.add_argument("--url", default=None, help="Optional Ollama chat endpoint override.")
    parser.add_argument("--model", default=None, help="Optional Qwen model override.")
    parser.add_argument("--timeout", type=float, default=120.0, help="HTTP timeout in seconds.")
    args = parser.parse_args()

    provider = OllamaQwenProvider(
        url=args.url or "http://localhost:11434/api/chat",
        model=args.model or "qwen3:8b",
        timeout=args.timeout,
    )
    proposal = provider.propose(args.objective, context=args.context)
    task = compile_qwen_production_proposal(proposal.snapshot())

    metadata = task.metadata or {}
    catalog = metadata.get("workflow_catalog", {})
    parameters = metadata.get("workflow_parameters", {})

    print("LIVE QWEN PRODUCTION PROPOSAL VERIFIED")
    print(f"workflow={catalog.get('name')}")
    print(f"workflow_version={catalog.get('version')}")
    print(f"workflow_parameter_contract=verified")
    print(f"proposal_validation=verified")
    print(f"catalog_resolution=verified")
    print(f"semantic_task_compilation=verified")
    print(f"workflow_parameters={json.dumps(parameters, sort_keys=True)}")
    print(f"execution_authorization=not_requested")
    print(f"execution=not_attempted")
    print(f"blender_mutation=not_attempted")


if __name__ == "__main__":
    main()
