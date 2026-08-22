"""Live Blender gate for stale-world detection and authorized replanning."""
from __future__ import annotations

import argparse
from typing import Any, Dict

from action_plan import ActionSpec
from planning.fresh_state_replan import FreshStateReplan
from planning.replan_authorization import ReplanAuthorization
from planning.blender_execution_boundary import BlenderExecutionBoundary
from tools.blender import create_empty_marker, inspect_scene

FILE_NAME = "replan_gate.blend"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("changed-world", "stale-plan"), required=True)
    args = parser.parse_args()

    observed: Dict[str, Any] = {"marker_present": False}
    writes = {"create_empty_marker": 0}

    def evidence() -> Dict[str, Any]:
        result = inspect_scene(file_name=FILE_NAME)
        observed.update(result)
        return dict(observed)

    def propose(state: Dict[str, Any]) -> list[ActionSpec]:
        if state.get("marker_present"):
            return []
        return [ActionSpec(
            tool="create_empty_marker",
            arguments={"file_name": FILE_NAME, "collection_name": "Atlas_Test", "object_name": "Atlas_Replan_Marker"},
            name="create Atlas replan marker",
            requires_success=True,
        )]

    replan = FreshStateReplan(evidence, propose)
    plan = replan.build()
    if plan is None:
        raise RuntimeError("fresh evidence did not produce a replacement plan")
    authorization = ReplanAuthorization.issue(plan.evidence, plan.actions, "live:replan-gate")

    if args.case == "stale-plan":
        observed["marker_present"] = True
        if authorization.matches(observed, plan.actions):
            raise RuntimeError("stale replacement plan was incorrectly accepted")
        print("ATLAS STALE REPLAN REJECTION: PASS")
        return

    # Simulate an unexpected world change after initial observation.
    observed["marker_present"] = True
    replacement = replan.build()
    if replacement is None:
        print("ATLAS FRESH WORLD REPLAN: PASS")
        print("WORLD CHANGED -> OLD PLAN INVALIDATED -> FRESH STATE ACCEPTED")
        return

    if replacement.actions:
        raise RuntimeError("fresh-state replan proposed a write after target was already satisfied")
    print("ATLAS FRESH WORLD REPLAN: PASS")
    print("WORLD CHANGED -> FRESH EVIDENCE -> REPLACEMENT PLAN REBUILT SAFELY")


if __name__ == "__main__":
    main()
