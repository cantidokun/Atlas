"""Deterministic render configuration contract for the Unreal Agent."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Mapping

from planning.unreal_evidence_contract import (
    UnrealEvidence,
    validate_evidence_for_operation,
)
from planning.unreal_render_job_record import validate_canonical_atlas_job_id


def derive_isolated_output_directory(output_parent_directory: str, atlas_job_id: str) -> str:
    """Derive deterministic per-attempt isolated output directory: <parent>/<atlas_job_id>/."""
    if not isinstance(output_parent_directory, str) or not output_parent_directory.strip():
        raise ValueError("output_parent_directory must be a non-empty string")
    valid_job_id = validate_canonical_atlas_job_id(atlas_job_id)
    parent = output_parent_directory.strip().rstrip("/\\")
    # Determine separator convention from parent directory
    sep = "/" if "/" in parent or "\\" not in parent else "\\"
    return f"{parent}{sep}{valid_job_id}"


def compute_render_config_digest(config: UnrealRenderConfig | Mapping[str, Any]) -> str:
    """Compute deterministic SHA-256 over normalized render configuration."""
    if isinstance(config, UnrealRenderConfig):
        cfg_dict = {
            "end_frame": config.end_frame,
            "height": config.height,
            "output_directory": config.output_directory,
            "output_format": config.output_format,
            "start_frame": config.start_frame,
            "width": config.width,
        }
    elif isinstance(config, Mapping):
        norm = normalize_render_config(config)
        cfg_dict = {
            "end_frame": norm.end_frame,
            "height": norm.height,
            "output_directory": norm.output_directory,
            "output_format": norm.output_format,
            "start_frame": norm.start_frame,
            "width": norm.width,
        }
    else:
        raise TypeError("config must be an UnrealRenderConfig or Mapping")

    encoded = json.dumps(cfg_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compute_render_request_digest(
    *,
    sequence_asset_path: str,
    output_directory: str,
    config_digest: str,
    authorization_id: str,
    entity_ids: tuple[str, ...],
) -> str:
    """Compute deterministic SHA-256 over canonical submission request parameters."""
    if not isinstance(sequence_asset_path, str) or not sequence_asset_path.strip():
        raise ValueError("sequence_asset_path must be a non-empty string")
    if not isinstance(output_directory, str) or not output_directory.strip():
        raise ValueError("output_directory must be a non-empty string")
    if not isinstance(config_digest, str) or not config_digest.strip():
        raise ValueError("config_digest must be a non-empty string")
    if not isinstance(authorization_id, str) or not authorization_id.strip():
        raise ValueError("authorization_id must be a non-empty string")
    if not isinstance(entity_ids, (tuple, list)) or not entity_ids:
        raise ValueError("entity_ids must be a non-empty sequence")
    for eid in entity_ids:
        if not isinstance(eid, str) or not eid.strip():
            raise ValueError("entity_ids must contain non-empty strings")

    payload = {
        "authorization_id": authorization_id.strip(),
        "config_digest": config_digest.strip(),
        "entity_ids": sorted([e.strip() for e in entity_ids]),
        "output_directory": output_directory.strip(),
        "sequence_asset_path": sequence_asset_path.strip(),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class UnrealRenderConfig:
    """Minimal engine-neutral render configuration owned by Atlas."""

    width: int
    height: int
    start_frame: int
    end_frame: int
    output_directory: str
    output_format: str

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("render resolution must be positive")
        if self.end_frame < self.start_frame:
            raise ValueError("end_frame must be >= start_frame")
        if not self.output_directory.strip():
            raise ValueError("output_directory must not be empty")
        if not self.output_format.strip():
            raise ValueError("output_format must not be empty")


def normalize_render_config(value: Mapping[str, Any]) -> UnrealRenderConfig:
    """Fail-closed conversion of observed/declared render configuration."""
    if not isinstance(value, Mapping):
        raise TypeError("render configuration must be an object")
    required = {"width", "height", "start_frame", "end_frame", "output_directory", "output_format"}
    if set(value) != required:
        raise ValueError("render configuration does not match the required schema")
    ints = ("width", "height", "start_frame", "end_frame")
    for key in ints:
        if isinstance(value[key], bool) or not isinstance(value[key], int):
            raise TypeError(f"{key} must be an integer")
    if not isinstance(value["output_directory"], str) or not isinstance(value["output_format"], str):
        raise TypeError("output_directory and output_format must be strings")
    return UnrealRenderConfig(**dict(value))


def verify_render_config(evidence: UnrealEvidence, expected: Mapping[str, Any]) -> UnrealEvidence:
    """Independently verify fresh, verified Unreal render-state evidence."""
    if not isinstance(evidence, UnrealEvidence):
        raise TypeError("evidence must be a UnrealEvidence")
    if evidence.operation_name != "inspect_render_job":
        raise ValueError("render configuration verification requires inspect_render_job evidence")
    if not evidence.verified:
        raise ValueError("render configuration verification requires verified evidence")

    observed = evidence.observed_state
    state = None
    if isinstance(observed, Mapping):
        for entry in observed.values():
            if isinstance(entry, Mapping) and isinstance(entry.get("render"), Mapping):
                state = entry["render"]
                break
    if not isinstance(state, Mapping):
        raise ValueError("render evidence is missing render state")
    actual = normalize_render_config({
        "width": state.get("width"),
        "height": state.get("height"),
        "start_frame": state.get("start_frame"),
        "end_frame": state.get("end_frame"),
        "output_directory": state.get("output_directory"),
        "output_format": state.get("output_format"),
    })
    expected_config = normalize_render_config(expected)
    if actual != expected_config:
        raise ValueError(f"render state does not match expected configuration: expected={expected_config!r}, observed={actual!r}")
    return evidence
