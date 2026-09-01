"""Deterministic render configuration contract for the Unreal Agent."""

from pathlib import Path

from dataclasses import dataclass, replace
from typing import Mapping, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UNREAL_PROJECT_ROOT = PROJECT_ROOT / "unreal" / "AtlasUnrealHarness"


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


def verify_render_config(evidence, expected):
    """Independently verify fresh Unreal render-state evidence.

    Production Unreal evidence is keyed by entity id. Render state belongs
    inside that entity's state envelope, so verification must resolve the
    render state from each requested entity rather than assuming a root-level
    ``render`` field.
    """
    observed = evidence.observed_state
    if not isinstance(observed, Mapping):
        raise ValueError("render evidence is missing observed state")

    for entity_id in evidence.entity_ids:
        entity_state = observed.get(entity_id)
        if not isinstance(entity_state, Mapping):
            raise ValueError(f"render evidence is missing state for entity '{entity_id}'")
        state = entity_state.get("render")
        if not isinstance(state, Mapping):
            raise ValueError(f"render evidence is missing render state for entity '{entity_id}'")

        actual = normalize_render_config({
            "width": state.get("width"),
            "height": state.get("height"),
            "start_frame": state.get("start_frame"),
            "end_frame": state.get("end_frame"),
            "output_directory": state.get("output_directory"),
            "output_format": state.get("output_format"),
        })
        expected_config = normalize_render_config(expected)

        def canonicalize_output_directory(value: str) -> str:
            path = Path(value.strip())
            if not path.is_absolute():
                path = UNREAL_PROJECT_ROOT / path
            return str(path.resolve()).replace("\\", "/").rstrip("/")

        actual = replace(
            actual,
            output_directory=canonicalize_output_directory(actual.output_directory),
        )
        expected_config = replace(
            expected_config,
            output_directory=canonicalize_output_directory(
                expected_config.output_directory
            ),
        )

        if actual != expected_config:
            raise ValueError(
                f"render state does not match expected configuration for entity '{entity_id}': "
                f"expected={expected_config!r}, observed={actual!r}"
            )

    return replace(evidence, verified=True)
