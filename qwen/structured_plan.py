"""Shared Ollama JSON-schema constraint for Atlas task-plan proposals."""


TASK_PLAN_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["evidence", "actions"],
    "properties": {
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["tool", "arguments", "name"],
                "properties": {
                    "tool": {"type": "string"},
                    "arguments": {"type": "object"},
                    "name": {"type": "string"},
                },
            },
        },
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["tool", "arguments", "name"],
                "properties": {
                    "tool": {"type": "string"},
                    "arguments": {"type": "object"},
                    "name": {"type": "string"},
                },
            },
        },
    },
}
