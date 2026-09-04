"""Live proof harness for Blender production-artifact lineage.

This harness deliberately crosses the existing real Blender adapter boundary. It
performs one constrained Blender write, obtains an immutable execution receipt,
performs a fresh independent inspection, builds a production artifact manifest,
persists it durably, reloads it, and verifies the exact receipt/evidence lineage.

It does not add authorization or execution behavior to the manifest/store.
Authorization remains the caller's responsibility, consistent with the existing
BlenderExecutionBoundary contract.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from typing import Any, Dict

from planning.blender_execution_boundary import BlenderExecutionBoundary
from planning.production_artifact import (
    ProductionArtifactManifest,
    verify_blender_closed_loop_lineage,
)
from planning.production_artifact_store import ProductionArtifactStore
from tools.blender import inspect_scene, move_object


DEFAULT_OBJECT = "Goal_Left_post"
DEFAULT_FILE = "parent_task_INCORRECT.blend"
DEFAULT_LOCATION = (0.5, 5.233, 0.0)


def execute_real_blender(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch a validated boundary call to the existing real Blender adapter."""
    if tool == "move_object":
        result = move_object(**arguments)
    elif tool == "inspect_scene":
        result = inspect_scene(**arguments)
    else:
        raise RuntimeError(f"Unexpected live Blender proof tool: {tool}")

    if not isinstance(result, dict):
        raise TypeError("Blender adapter must return an object")

    status = result.get("status")
    success = "error" not in result and status not in {"error", "failed", "object_not_found"}
    return {
        "ok": success,
        "state": "succeeded" if success else str(status or "failed"),
        "details": dict(result),
    }


def observed_location(result: Any, object_name: str):
    """Extract the requested object's location from fresh scene evidence."""
    objects = result.details.get("objects")
    if not isinstance(objects, list):
        raise RuntimeError(f"Scene inspection did not return an object list: {result.details}")
    for obj in objects:
        if isinstance(obj, dict) and obj.get("name") == object_name:
            location = obj.get("location")
            if isinstance(location, (list, tuple)) and len(location) == 3:
                return list(location)
            break
    raise RuntimeError(f"Object {object_name!r} was not independently observed: {result.details}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default=DEFAULT_FILE, help="Atlas Desktop .blend fixture filename")
    parser.add_argument("--object", default=DEFAULT_OBJECT, help="Object to move and independently inspect")
    parser.add_argument(
        "--location",
        nargs=3,
        type=float,
        default=list(DEFAULT_LOCATION),
        metavar=("X", "Y", "Z"),
        help="Target object location",
    )
    parser.add_argument(
        "--artifact-id",
        default="atlas-blender-live-proof-001",
        help="Stable identifier for the produced lineage record",
    )
    parser.add_argument(
        "--canonical-digital-twin-id",
        default="atlas-soccer-digital-twin-proof",
        help="Canonical Digital Twin identifier bound by the manifest",
    )
    parser.add_argument(
        "--artifact-path",
        default=DEFAULT_FILE,
        help="Path recorded as the produced Blender representation",
    )
    args = parser.parse_args()

    target_location = list(args.location)
    operation_arguments = {
        "file_name": args.file,
        "object_name": args.object,
        "location": target_location,
    }
    inspection_arguments = {"file_name": args.file}

    boundary = BlenderExecutionBoundary(execute_real_blender)
    closed_loop = boundary.execute_with_persistence(
        "move_object",
        operation_arguments,
        "inspect_scene",
        inspection_arguments,
        expected_state=target_location,
        observed_state=lambda result: observed_location(result, args.object),
    )

    with tempfile.TemporaryDirectory(prefix="atlas-live-artifact-proof-") as directory:
        store_path = os.path.join(directory, "production-artifact.json")
        store = ProductionArtifactStore(store_path)
        manifest = ProductionArtifactManifest.from_blender_closed_loop(
            artifact_id=args.artifact_id,
            canonical_digital_twin_id=args.canonical_digital_twin_id,
            representation_type="blender_scene",
            artifact_path=args.artifact_path,
            operation_receipt=closed_loop.operation_receipt,
            persistence_evidence=closed_loop.persistence_evidence,
            workflow_provenance={
                "proof": "live_blender_production_artifact",
                "source": "existing_blender_adapter",
            },
            engine="Blender",
            metadata={"object_name": args.object, "target_location": target_location},
        )
        persisted = store.save(manifest)
        reloaded = store.load(manifest.artifact_id)

        verify_blender_closed_loop_lineage(
            reloaded,
            closed_loop.operation_receipt,
            closed_loop.persistence_evidence,
        )

        if persisted.digest != reloaded.digest():
            raise RuntimeError("Persisted and reloaded manifest digests differ")
        if reloaded.canonical_digital_twin_id != args.canonical_digital_twin_id:
            raise RuntimeError("Canonical Digital Twin binding changed during persistence")
        if reloaded.artifact_path != args.artifact_path:
            raise RuntimeError("Artifact path changed during persistence")

        proof = {
            "artifact_id": reloaded.artifact_id,
            "manifest_digest": reloaded.digest(),
            "canonical_digital_twin_id": reloaded.canonical_digital_twin_id,
            "artifact_path": reloaded.artifact_path,
            "operation_receipt_digest": closed_loop.operation_receipt.digest(),
            "persistence_evidence_digest": closed_loop.persistence_evidence.digest(),
            "observed_location": observed_location(closed_loop.inspection_result, args.object),
        }

    print("ATLAS LIVE BLENDER PRODUCTION ARTIFACT PROOF: PASS")
    print("REAL BLENDER WRITE -> FRESH SCENE INSPECTION -> IMMUTABLE RECEIPT/EVIDENCE -> DURABLE MANIFEST -> RELOAD -> EXACT LINEAGE VERIFIED")
    print(json.dumps(proof, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
