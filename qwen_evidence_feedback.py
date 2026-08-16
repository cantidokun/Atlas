"""Build a bounded Qwen context from verified Atlas evidence."""

import json
from typing import Any, Dict, List


def build_evidence_message(results: List[Dict[str, Any]]) -> Dict[str, str]:
    """Create a model message containing only returned tool evidence.

    The evidence is serialized as data. It does not authorize any new tool call.
    """
    if not isinstance(results, list):
        raise ValueError("Evidence results must be a list")

    safe_results = []
    for item in results:
        if not isinstance(item, dict):
            raise ValueError("Each evidence result must be an object")
        if "tool" not in item or "result" not in item:
            raise ValueError("Each evidence result requires tool and result")
        safe_results.append({"tool": item["tool"], "result": item["result"]})

    return {
        "role": "user",
        "content": (
            "ATLAS_VERIFIED_EVIDENCE:\n" +
            json.dumps(safe_results, sort_keys=True, separators=(",", ":")) +
            "\n\nInterpret this evidence. Do not claim facts not present in it. "
            "If more evidence is needed, propose it rather than inventing it."
        ),
    }


def evidence_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Return a small deterministic summary for runtime logging."""
    return {
        "evidence_count": len(results),
        "tools": [item.get("tool") for item in results],
    }
