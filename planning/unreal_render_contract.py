"""Deterministic render configuration contract for the Unreal Agent."""

from dataclasses import dataclass
from typing import Mapping, Any


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
