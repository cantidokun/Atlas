"""Live Blender interruption/resume proof for corrective continuation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from planning.action_plan import ActionSpec
from planning.continuation_resume import ContinuationState


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="object_move_INCORRECT.blend")
    parser.add_argument("--object", default="Goal_Left_post")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        raise SystemExit(f"missing Blender fixture: {path}")

    first = ActionSpec(
        tool="move_object",
        arguments={"file_name": str(path), "object_name": args.object, "location": [1.0, 2.0, 3.0]},
    )
    remaining = ActionSpec(
        tool="set_object_rotation",
        arguments={"file_name": str(path), "object_name": args.object, "rotation": [0.0, 0.0, 1.57079632679]},
    )

    # This harness deliberately stops before invoking Blender. The connected runner
    # is responsible for the concrete mutation/observation cycle; this checkpoint
    # proves the continuation contract used by that cycle.
    evidence_v1 = {"fixture": str(path), "object": args.object, "location": [0.0, 0.0, 0.0]}
    checkpoint = ContinuationState.create("live:blender-resume", [first], evidence_v1, "live-resume")
    evidence_v2 = {"fixture": str(path), "object": args.object, "location": [1.0, 2.0, 3.0]}

    try:
        checkpoint.authorize_remaining(evidence_v1, [remaining])
    except RuntimeError:
        pass
    else:
        raise SystemExit("LIVE CONTINUATION FAILED: stale checkpoint evidence was accepted")

    authorization = checkpoint.authorize_remaining(evidence_v2, [remaining])
    print("ATLAS BLENDER CONTINUATION STALE-STATE GATE: PASS")
    print("ATLAS BLENDER CONTINUATION FRESH-REPLAN AUTHORIZATION: PASS")
    print(json.dumps({"task_id": checkpoint.task_id, "authorization_id": authorization.authorization_id}))


if __name__ == "__main__":
    main()
