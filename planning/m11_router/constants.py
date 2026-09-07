"""Shared constants for the M11 router, free of cross-module imports.

Holds the canonical task classes (design §4.1) so both the risk classifier and
the model-profile validator can reference them without a circular import.
"""

from __future__ import annotations

# Task classes (design §4.1).
TASK_CLASSES: tuple[str, ...] = (
    "doc",
    "test",
    "test.fix",
    "refactor",
    "api-boundary",
    "adapter",
    "contract",
    "recovery",
    "security-crypto",
    "concurrency",
    "docs",
)