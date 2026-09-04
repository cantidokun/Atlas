"""Live proof harness for Unreal production-artifact lineage.

This harness deliberately consumes an already verified Unreal render receipt and
its matching immutable evidence. It does not submit a render, execute Unreal,
authorize work, or implement job recovery. The caller supplies the verified
receipt/evidence JSON produced by the existing Unreal render boundary.

The harness constructs the provenance-only ProductionArtifactManifest, persists
it through ProductionArtifactStore, reloads it, independently verifies exact
receipt/evidence lineage, and reports the resulting digest identities.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from planning.production_artifact import (
    ProductionArtifactManifest,
    verify_unreal_render_lineage,
)
from planning.production_artifact_store import ProductionArtifactStore
from planning.unreal_evidence_contract import UnrealEvidence
from planning.unreal_render_receipt import UnrealRenderReceipt


EVIDENCE_FIELDS = {"operation_name", "entity_ids", "observed_state", "source", "verified"}
RECEIPT_FIELDS = {"job_id", "sequence_asset_path", "evidence_digest"}


def _load_object(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError) as exc:
        raise RuntimeError("failed to load Unreal proof input JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("Unreal proof input must be a JSON object")
    return payload


def _require_fields(payload: Dict[str, Any], fields: set[str], label: str) -> None:
    if set(payload) != fields:
        raise ValueError(f"{label} fields are invalid")


def _load_evidence(path: Path) -> UnrealEvidence:
    payload = _load_object(path)
    _require_fields(payload, EVIDENCE_FIELDS, "Unreal evidence")
    return UnrealEvidence(
        operation_name=payload["operation_name"],
        entity_ids=payload["entity_ids"],
        observed_state=payload["observed_state"],
        source=payload["source"],
        verified=payload["verified"],
    )


def _load_receipt(path: Path) -> UnrealRenderReceipt:
    payload = _load_object(path)
    _require_fields(payload, RECEIPT_FIELDS, "Unreal render receipt")
    return UnrealRenderReceipt(
        job_id=payload["job_id"],
        sequence_asset_path=payload["sequence_asset_path"],
        evidence_digest=payload["evidence_digest"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, type=Path, help="JSON snapshot of verified UnrealEvidence")
    parser.add_argument("--receipt", required=True, type=Path, help="JSON snapshot of matching UnrealRenderReceipt")
    parser.add_argument("--artifact-id", required=True, help="Stable production artifact identifier")
    parser.add_argument("--canonical-digital-twin-id", required=True, help="Canonical Atlas Digital Twin identifier")
    parser.add_argument("--artifact-path", required=True, help="Exact output path observed in verified evidence")
    parser.add_argument("--representation-type", default="unreal-render")
    parser.add_argument("--engine-version", default="5.6")
    parser.add_argument("--output", type=Path, default=Path("unreal-production-artifact-proof.json"))
    args = parser.parse_args()

    evidence = _load_evidence(args.evidence)
    receipt = _load_receipt(args.receipt)
    manifest = ProductionArtifactManifest.from_unreal_render_receipt(
        artifact_id=args.artifact_id,
        canonical_digital_twin_id=args.canonical_digital_twin_id,
        representation_type=args.representation_type,
        artifact_path=args.artifact_path,
        render_receipt=receipt,
        render_evidence=evidence,
        engine_version=args.engine_version,
    )

    store = ProductionArtifactStore(str(args.output))
    store.save(manifest)
    reloaded = store.load()
    verify_unreal_render_lineage(reloaded, receipt, evidence)

    proof = {
        "artifact_id": reloaded.artifact_id,
        "artifact_path": reloaded.artifact_path,
        "canonical_digital_twin_id": reloaded.canonical_digital_twin_id,
        "engine": reloaded.engine,
        "engine_version": reloaded.engine_version,
        "manifest_digest": reloaded.digest(),
        "render_receipt_digest": receipt.receipt_digest,
        "render_evidence_digest": receipt.evidence_digest,
    }
    print("ATLAS LIVE UNREAL PRODUCTION ARTIFACT PROOF: PASS")
    print("VERIFIED UNREAL RENDER EVIDENCE -> IMMUTABLE RECEIPT -> PROVENANCE MANIFEST -> DURABLE STORE -> RELOAD -> EXACT LINEAGE VERIFIED")
    print(json.dumps(proof, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
