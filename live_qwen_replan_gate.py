"""Live Blender gate for stale-world detection and authorized replanning."""
from __future__ import annotations

import argparse
from typing import Any, Dict, List

from action_plan import ActionSpec
from planning.fresh_state_replan import FreshStateReplan
from planning.replan_authorization import ReplanAuthorization
from tools.blender import create_empty_marker, inspect_scene

FILE_NAME = "replan_gate.blend"
MARKER = "Atlas_Replan_Marker"


def marker_present(state: Dict[str, Any]) -> bool:
    return any(obj.get("name") == MARKER for obj in state.get("objects", []))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("changed-world", "stale-plan"), required=True)
    args = parser.parse_args()

    writes = {"create_empty_marker": 0}

    def evidence() -> Dict[str, Any]:
        state = inspect_scene(file_name=FILE_NAME)
        return {
            "scene": state.get("scene"),
            "total_objects": state.get("total_objects"),
            "objects": state.get("objects", []),
            "marker_present": marker_present(state),
        }

    def propose(state: Dict[str, Any]) -> List[ActionSpec]:
        if state.get("marker_present"):
            return []
        return [ActionSpec(
            tool="create_empty_marker",
            arguments={
                "file_name": FILE_NAME,
                "collection_name": "Atlas_Test",
                "object_name": MARKER,
            },
            name="create Atlas replan marker",
            requires_success=True,
        )]

    plan = FreshStateReplan.create(evidence, propose, "live:replan-gate")
    authorization = plan.authorization

    if args.case == "stale-plan":
        # Unexpected external change: create the target after the old plan was bound.
        create_empty_marker(
            file_name=FILE_NAME,
            collection_name="Atlas_Test",
            object_name=MARKER,
        )
        fresh = evidence()
        try:
            plan.validate_before_execution(fresh, plan.actions)
        except RuntimeError:
            print("ATLAS STALE REPLAN REJECTION: PASS")
            return
        raise RuntimeError("stale replacement plan was incorrectly accepted")

    # Unexpected external change occurs after the initial observation.
    create_empty_marker(
        file_name=FILE_NAME,
        collection_name="Atlas_Test",
        object_name=MARKER,
    )
    replacement = FreshStateReplan.create(evidence, propose, "live:replan-gate-replacement")
    if replacement.actions:
        raise RuntimeError("fresh-state replan proposed a write after target was already satisfied")
    print("ATLAS FRESH WORLD REPLAN: PASS")
    print("WORLD CHANGED -> FRESH EVIDENCE -> REPLACEMENT PLAN HAS ZERO WRITE ACTIONS")


if __name__ == "__main__":
    main()
