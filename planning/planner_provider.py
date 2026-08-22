"""Model-agnostic boundary between model output and Atlas planning primitives.

The planner/provider boundary deliberately knows nothing about Qwen, Ollama, or
any other model runtime. Providers translate their model-specific output into a
validated :class:`TaskPlanProposal`; the downstream Atlas planning and execution
layers consume that stable proposal type only.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional, Set

from planning.task_planner import TaskPlanProposal


class PlannerProviderError(ValueError):
    """Raised when a provider cannot produce a valid Atlas planning proposal."""


class PlannerProvider(ABC):
    """Stable provider contract for model-produced task plans."""

    @abstractmethod
    def build_proposal(
        self,
        model_output: Any,
        *,
        allowed_tools: Optional[Set[str]] = None,
    ) -> Optional[TaskPlanProposal]:
        """Translate provider-specific model output into a validated proposal.

        Returning ``None`` means the provider output did not contain an
        admissible plan. Providers must not authorize or execute actions.
        """
        raise NotImplementedError
