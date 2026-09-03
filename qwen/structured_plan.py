"""Shared JSON-schema constraints for Atlas Qwen proposal outputs."""


PRODUCTION_PROPOSAL_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["workflow", "parameters"],
    "properties": {
        "workflow": {"type": "string", "minLength": 1},
        "version": {"type": ["integer", "null"], "minimum": 1},
        "parameters": {"type": "object"},
    },
}


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
                    "depends_on": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
    },
}


__all__ = ["PRODUCTION_PROPOSAL_JSON_SCHEMA", "TASK_PLAN_JSON_SCHEMA"]
