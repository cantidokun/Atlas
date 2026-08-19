"""Production authorization gate bridging ActionPlan authorization to UnrealPlanExecutor.

This gate deterministically converts a ``UnrealTaskPlan`` into the generic
``ActionPlan`` / ``ActionAuthorization`` mechanism, validates authorization
before any operation reaches the Unreal adapter, and delegates execution to
the existing ``UnrealPlanExecutor``.

Design invariants
-----------------
- The gate never executes without a valid, matching ``ActionAuthorization``.
- Conversion from ``UnrealOperation`` to ``ActionSpec`` is deterministic and
  lossless for authorization-digest purposes.
- Post-authorization mutation of the operation list is detected and rejected.
- The gate does not modify ``UnrealPlanExecutor`` behaviour; it only guards
  access to it.
"""

from typing import List, Optional

from planning.action_authorization import ActionAuthorization
from planning.action_plan import ActionPlan, ActionSpec
from planning.unreal_agent import UnrealOperation
from planning.unreal_plan_executor import (
    UnrealPlanExecutionError,
    UnrealPlanExecutionResult,
    UnrealPlanExecutor,
)
from planning.unreal_task_planner import UnrealTaskPlan


class UnrealAuthorizationGateError(RuntimeError):
    """Raised when the authorization gate rejects execution."""


def operation_to_action_spec(operation: UnrealOperation) -> ActionSpec:
    """Deterministically convert one ``UnrealOperation`` to an ``ActionSpec``.

    The mapping is intentionally simple and reversible so that the
    authorization digest is stable across identical operation sequences.
    """
    return ActionSpec(
        tool=operation.capability.value,
        arguments=dict(operation.arguments),
        name=operation.name,
        requires_success=True,
    )


def task_plan_to_action_specs(plan: UnrealTaskPlan) -> List[ActionSpec]:
    """Convert every operation in a ``UnrealTaskPlan`` to ``ActionSpec`` list."""
    return [operation_to_action_spec(op) for op in plan.operations]


class UnrealAuthorizedExecutionGate:
    """Guard that requires valid ``ActionAuthorization`` before executing a plan.

    Typical usage::

        gate = UnrealAuthorizedExecutionGate(executor)
        gate.load_plan(task_plan)
        gate.authorize("auth-id-001")
        result = gate.execute()
    """

    def __init__(self, executor: UnrealPlanExecutor) -> None:
        if not isinstance(executor, UnrealPlanExecutor):
            raise TypeError("executor must be a UnrealPlanExecutor instance")
        self._executor = executor
        self._task_plan: Optional[UnrealTaskPlan] = None
        self._action_plan: Optional[ActionPlan] = None
        self._authorized_digest: Optional[str] = None

    # ------------------------------------------------------------------
    # Plan loading
    # ------------------------------------------------------------------

    def load_plan(self, task_plan: UnrealTaskPlan) -> ActionPlan:
        """Convert and store a ``UnrealTaskPlan`` as an ``ActionPlan``.

        Returns the ``ActionPlan`` so callers can inspect it before
        authorizing.  Any previously loaded plan is replaced.
        """
        if not isinstance(task_plan, UnrealTaskPlan):
            raise TypeError("task_plan must be a UnrealTaskPlan instance")
        if not task_plan.operations:
            raise UnrealAuthorizationGateError(
                "Cannot load an empty task plan"
            )
        specs = task_plan_to_action_specs(task_plan)
        self._task_plan = task_plan
        self._action_plan = ActionPlan(actions=specs)
        self._authorized_digest = None
        return self._action_plan

    # ------------------------------------------------------------------
    # Authorization
    # ------------------------------------------------------------------

    def authorize(self, authorization_id: str) -> ActionAuthorization:
        """Issue and install authorization for the currently loaded plan.

        Raises
        ------
        UnrealAuthorizationGateError
            If no plan is loaded or the authorization ID is invalid.
        """
        if self._action_plan is None or self._task_plan is None:
            raise UnrealAuthorizationGateError(
                "No task plan loaded — call load_plan() first"
            )
        if not isinstance(authorization_id, str) or not authorization_id.strip():
            raise UnrealAuthorizationGateError(
                "authorization_id must be a non-empty string"
            )
        auth = self._action_plan.authorize_with_id(authorization_id)
        self._authorized_digest = auth.plan_digest
        return auth

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _verify_plan_integrity(self) -> None:
        """Detect post-authorization mutation of the operation list."""
        if self._task_plan is None or self._action_plan is None:
            raise UnrealAuthorizationGateError(
                "No task plan loaded — call load_plan() first"
            )
        current_specs = task_plan_to_action_specs(self._task_plan)
        if self._action_plan.authorization is None:
            raise UnrealAuthorizationGateError(
                "Plan is not authorized — call authorize() first"
            )
        if not self._action_plan.authorization.matches(current_specs):
            raise UnrealAuthorizationGateError(
                "Plan integrity check failed — operations were mutated after authorization"
            )

    def execute(self) -> UnrealPlanExecutionResult:
        """Execute the authorized plan through ``UnrealPlanExecutor``.

        Raises
        ------
        UnrealAuthorizationGateError
            If authorization is missing, invalid, or the plan was mutated.
        UnrealPlanExecutionError
            Propagated from the executor on transport/adapter failures.
        """
        if self._task_plan is None or self._action_plan is None:
            raise UnrealAuthorizationGateError(
                "No task plan loaded — call load_plan() first"
            )
        # Integrity check first: detects foreign/mismatched receipts before
        # the generic ``authorized`` property can mask them as "not authorized".
        self._verify_plan_integrity()
        if not self._action_plan.authorized:
            raise UnrealAuthorizationGateError(
                "Plan is not authorized — call authorize() first"
            )

        authorization_id = self._action_plan.authorization_id
        if authorization_id is None or not authorization_id.strip():
            raise UnrealAuthorizationGateError(
                "authorization_id resolved to empty after authorization"
            )

        return self._executor.execute(self._task_plan, authorization_id=authorization_id)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def is_authorized(self) -> bool:
        """Return whether the gate currently holds a valid authorization."""
        if self._action_plan is None:
            return False
        return self._action_plan.authorized

    @property
    def action_plan(self) -> Optional[ActionPlan]:
        return self._action_plan

    @property
    def task_plan(self) -> Optional[UnrealTaskPlan]:
        return self._task_plan
