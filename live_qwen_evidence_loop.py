"""Small live harness for the read-only Qwen evidence loop."""

from typing import Any, Dict, List, Set

import requests

from qwen_evidence_loop import parse_evidence_proposal, execute_evidence_proposal
from qwen_evidence_feedback import build_evidence_message

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:8b"
ALLOWED_EVIDENCE_TOOLS: Set[str] = {
    "inspect_scene",
    "inspect_object_relationship",
}

SYSTEM_PROMPT = """You are Atlas planning assistant.
Return ONLY a JSON object with exactly these top-level fields:
{"evidence":[],"actions":[]}
Use evidence requests to inspect the Blender scene. Never include actions in this evidence-only round.
Do not add markdown, explanation, or other fields.
"""


def ask_qwen(messages: List[Dict[str, str]]) -> str:
    response = requests.post(
        OLLAMA_URL,
        json={"model": MODEL, "messages": messages, "stream": False},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["message"]["content"]


def main() -> None:
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Inspect goalpost_test.blend and request only the evidence you need."},
    ]

    print("--- ROUND 1 PLAN ---")
    raw_plan = ask_qwen(messages)
    print(raw_plan)

    proposal = parse_evidence_proposal(raw_plan, ALLOWED_EVIDENCE_TOOLS)
    if proposal is None:
        raise RuntimeError("Qwen did not produce a valid evidence-only proposal")

    execution = execute_evidence_proposal(proposal, ALLOWED_EVIDENCE_TOOLS)
    print("--- EVIDENCE ---")
    print(execution)

    evidence_message = build_evidence_message(execution["results"])
    messages.extend(
        [
            evidence_message,
            {
                "role": "user",
                "content": "Based only on ATLAS_VERIFIED_EVIDENCE, state whether more evidence is needed. If yes, return only JSON in the same evidence-only format. If no, return exactly: EVIDENCE_SUFFICIENT",
            },
        ]
    )

    print("--- ROUND 2 ---")
    raw_followup = ask_qwen(messages)
    print(raw_followup)

    if raw_followup.strip() == "EVIDENCE_SUFFICIENT":
        print("STATUS: EVIDENCE_SUFFICIENT")
        return

    followup = parse_evidence_proposal(raw_followup, ALLOWED_EVIDENCE_TOOLS)
    if followup is None:
        raise RuntimeError("Qwen follow-up was neither EVIDENCE_SUFFICIENT nor a valid evidence-only proposal")

    print("STATUS: MORE_EVIDENCE_REQUESTED")
    print(execute_evidence_proposal(followup, ALLOWED_EVIDENCE_TOOLS))


if __name__ == "__main__":
    main()
