"""Deterministic render configuration contract for the Unreal Agent."""

from dataclasses import dataclass
from typing import Any, Mapping

from planning.unreal_evidence_contract import UnrealEvidence


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
