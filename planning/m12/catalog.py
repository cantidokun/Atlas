"""M12.2 versioned Unreal soccer-production semantic catalog.

Reuses the conceptual *shape* of the Blender `SoccerProductionWorkflowSpec`
(name, version, required parameters with kinds, fail-closed resolution) but
resolves to validated :class:`UnrealProductionTaskDefinition` objects built from
canonical fragment composition — never by copying Blender-specific semantics.

The catalog is a proposal-resolution surface only: it does not execute,
authorize, schedule, or recover.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple, cast

from planning.m12.composition import UnrealComposedTaskPlan, compose_fragments
from planning.m12.fragments import UnrealProductionFragment
from planning.m12.fragments_registry import canonical_fragment
from planning.m12.semantic_task import (
    UnrealProductionTaskDefinition,
    normalize_unreal_semantic_request,
)
from planning.m12.target_state import target_state_spec

# ---------------------------------------------------------------------------
# Catalog errors
# ---------------------------------------------------------------------------


class UnrealCatalogError(ValueError):
    """Base error for catalog resolution/validation failures."""


class UnknownCatalogTaskError(UnrealCatalogError, KeyError):
    """Unknown canonical task identifier."""


class UnsupportedCatalogVersionError(UnrealCatalogError):
    """Requested version not available for a catalog entry."""


class InvalidCatalogParametersError(UnrealCatalogError):
    """Proposal parameters do not satisfy the catalog entry contract."""


# ---------------------------------------------------------------------------
# Catalog entry spec (models the Blender SoccerProductionWorkflowSpec shape)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UnrealCatalogEntrySpec:
    """Stable descriptor for one versioned Unreal semantic catalog entry."""

    name: str
    objective: str
    task_class: str
    fragment_ids: Tuple[str, ...]
    required_parameters: Tuple[str, ...]
    parameter_kinds: Tuple[Tuple[str, str], ...]
    version: int = 1

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise UnrealCatalogError("catalog entry name must not be empty")
        if not self.objective.strip():
            raise UnrealCatalogError("catalog entry objective must not be empty")
        if not self.task_class.strip():
            raise UnrealCatalogError("catalog entry task_class must not be empty")
        if not self.fragment_ids:
            raise UnrealCatalogError("catalog entry must reference at least one fragment")
        _check_tokens(self.fragment_ids, "fragment_ids")
        if not self.required_parameters:
            raise UnrealCatalogError("catalog entry must declare required parameters")
        _check_tokens(self.required_parameters, "required_parameters")
        if len(set(self.required_parameters)) != len(self.required_parameters):
            raise UnrealCatalogError("catalog entry required parameters must be unique")
        if not self.parameter_kinds:
            raise UnrealCatalogError("catalog entry must declare parameter kinds")
        names = [n for n, _ in self.parameter_kinds]
        if len(names) != len(set(names)):
            raise UnrealCatalogError("catalog entry parameter kind names must be unique")
        if set(names) != set(self.required_parameters):
            raise UnrealCatalogError(
                "catalog entry parameter kinds must exactly match required parameters"
            )
        if not isinstance(self.version, int) or isinstance(self.version, bool) or self.version < 1:
            raise UnrealCatalogError("catalog entry version must be a positive integer")

    def snapshot(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "objective": self.objective,
            "task_class": self.task_class,
            "fragment_ids": list(self.fragment_ids),
            "required_parameters": list(self.required_parameters),
            "parameter_kinds": {name: kind for name, kind in self.parameter_kinds},
            "version": self.version,
        }


def _check_tokens(values: Tuple[str, ...], field: str) -> None:
    if not isinstance(values, tuple):
        raise UnrealCatalogError(f"{field} must be a tuple")
    if any(not isinstance(v, str) or not v.strip() for v in values):
        raise UnrealCatalogError(f"{field} must contain non-empty strings")
    if len(values) != len(set(values)):
        raise UnrealCatalogError(f"{field} must not contain duplicates")


# ---------------------------------------------------------------------------
# Canonical catalog entries
# ---------------------------------------------------------------------------

# scene-prepare: initialize the digital-twin scene.
_SCENE = UnrealCatalogEntrySpec(
    name="unreal.scene-prepare",
    objective="Prepare the soccer digital-twin scene for production.",
    task_class="scene-prepare",
    fragment_ids=("scene_setup",),
    required_parameters=("twin_id",),
    parameter_kinds=(("twin_id", "string"),),
    version=1,
)

# environment-configure: configure the field/environment representation.
_ENV = UnrealCatalogEntrySpec(
    name="unreal.environment-configure",
    objective="Configure the field/environment representation.",
    task_class="environment-configure",
    fragment_ids=("environment_setup",),
    required_parameters=("twin_id", "environment_style"),
    parameter_kinds=(("twin_id", "string"), ("environment_style", "string")),
    version=1,
)

# camera-configure: configure camera placement/framing.
_CAMERA = UnrealCatalogEntrySpec(
    name="unreal.camera-configure",
    objective="Configure camera placement/framing for production shots.",
    task_class="camera-configure",
    fragment_ids=("scene_setup", "camera_setup"),
    required_parameters=("twin_id", "camera_slots"),
    parameter_kinds=(("twin_id", "string"), ("camera_slots", "json")),
    version=1,
)

# lighting-configure: configure lighting.
_LIGHTING = UnrealCatalogEntrySpec(
    name="unreal.lighting-configure",
    objective="Configure lighting for the scene.",
    task_class="lighting-configure",
    fragment_ids=("scene_setup", "lighting_setup"),
    required_parameters=("twin_id", "lighting_rig"),
    parameter_kinds=(("twin_id", "string"), ("lighting_rig", "json")),
    version=1,
)

# sequence-configure: configure cinematic sequence/playback range.
_SEQUENCE = UnrealCatalogEntrySpec(
    name="unreal.sequence-configure",
    objective="Configure the cinematic sequence / playback range.",
    task_class="sequence-configure",
    fragment_ids=("scene_setup", "camera_setup", "sequence_setup"),
    required_parameters=("twin_id", "sequence_name", "frame_start", "frame_end"),
    parameter_kinds=(
        ("twin_id", "string"),
        ("sequence_name", "string"),
        ("frame_start", "int"),
        ("frame_end", "int"),
    ),
    version=1,
)

# render-execute / artifact-validate: render-bearing, declared but NOT
# expandable-to-actions here; composition supports them but compilation/render
# execution is deferred (M12.1 rejects render-bearing compile).
_RENDER = UnrealCatalogEntrySpec(
    name="unreal.render-execute",
    objective="Execute an authorized render through the existing render-job path.",
    task_class="render-execute",
    fragment_ids=("scene_setup", "camera_setup", "sequence_setup", "render_setup"),
    required_parameters=("twin_id", "sequence_name"),
    parameter_kinds=(("twin_id", "string"), ("sequence_name", "string")),
    version=1,
)

_ARTIFACT = UnrealCatalogEntrySpec(
    name="unreal.artifact-validate",
    objective="Wrap an existing artifact validation/verification step.",
    task_class="artifact-validate",
    fragment_ids=("scene_setup",),
    required_parameters=("twin_id", "artifact_ref"),
    parameter_kinds=(("twin_id", "string"), ("artifact_ref", "string")),
    version=1,
)

_CATALOG_ENTRIES: Tuple[UnrealCatalogEntrySpec, ...] = (
    _SCENE,
    _ENV,
    _CAMERA,
    _LIGHTING,
    _SEQUENCE,
    _RENDER,
    _ARTIFACT,
)

_CATALOG_VERSION = 1


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


class UnrealSoccerProductionCatalog:
    """Versioned resolver of canonical Unreal semantic production tasks.

    Deterministic: resolves a canonical task name + parameters (optionally a
    version) into a validated :class:`UnrealProductionTaskDefinition` built from
    canonical fragment composition. Fail-closed on unknown task, unsupported
    version, or invalid parameters. No implicit semantic substitution.
    """

    def __init__(
        self,
        entries: Tuple[UnrealCatalogEntrySpec, ...] = _CATALOG_ENTRIES,
        version: int = _CATALOG_VERSION,
    ):
        self._entries = tuple(entries)
        if not isinstance(version, int) or version < 1:
            raise UnrealCatalogError("catalog version must be a positive integer")
        self.version = version
        self._by_name: Dict[str, Tuple[UnrealCatalogEntrySpec, ...]] = {}
        for entry in self._entries:
            bucket = [
                existing
                for existing in self._entries
                if existing.name == entry.name
            ]
            self._by_name[entry.name] = tuple(bucket)

    # -- accessors -----------------------------------------------------------

    def available_task_names(self) -> Tuple[str, ...]:
        return tuple(sorted({e.name for e in self._entries}))

    def get_entry(
        self, name: str, version: Optional[int] = None
    ) -> UnrealCatalogEntrySpec:
        if not isinstance(name, str) or not name.strip():
            raise UnrealCatalogError("catalog task name must be a non-empty string")
        candidates = self._by_name.get(name)
        if not candidates:
            known = ", ".join(self.available_task_names())
            raise UnknownCatalogTaskError(f"unknown catalog task: {name!r} (known: {known})")
        if version is not None:
            if not isinstance(version, int) or isinstance(version, bool) or version < 1:
                raise UnrealCatalogError("catalog task version must be a positive integer")
            for candidate in candidates:
                if candidate.version == version:
                    return candidate
            raise UnsupportedCatalogVersionError(
                f"unsupported version for catalog task {name!r}: {version}"
            )
        # Deterministic: highest version when not specified.
        return max(candidates, key=lambda e: e.version)

    # -- resolution ----------------------------------------------------------

    def validate_parameters(
        self, name: str, parameters: Mapping[str, Any], version: Optional[int] = None
    ) -> UnrealCatalogEntrySpec:
        entry = self.get_entry(name, version=version)
        if not isinstance(parameters, dict):
            raise InvalidCatalogParametersError("parameters must be a dict-like mapping")
        missing = [p for p in entry.required_parameters if p not in parameters]
        if missing:
            raise InvalidCatalogParametersError(
                f"catalog task {name!r} missing required parameters: {missing}"
            )
        unexpected = sorted(set(parameters) - set(entry.required_parameters))
        if unexpected:
            raise InvalidCatalogParametersError(
                f"catalog task {name!r} received unexpected parameters: {unexpected}"
            )
        for param_name, kind in entry.parameter_kinds:
            value = parameters[param_name]
            if kind == "string":
                if not isinstance(value, str) or not value.strip():
                    raise InvalidCatalogParametersError(
                        f"catalog parameter {param_name} must be a non-empty string"
                    )
            elif kind == "int":
                if not isinstance(value, int) or isinstance(value, bool):
                    raise InvalidCatalogParametersError(
                        f"catalog parameter {param_name} must be an int"
                    )
            elif kind == "json":
                # JSON-serializable structured value (list/dict/int/float/str/bool/None).
                try:
                    json.dumps(value)
                except (TypeError, ValueError):
                    raise InvalidCatalogParametersError(
                        f"catalog parameter {param_name} must be JSON-serializable"
                    )
            else:
                raise UnrealCatalogError(
                    f"catalog contract declares unsupported parameter kind: {kind}"
                )
        return entry

    def resolve(
        self,
        name: str,
        parameters: Mapping[str, Any],
        *,
        digital_twin_id: str,
        provenance: Optional[Dict[str, Any]] = None,
        version: Optional[int] = None,
    ) -> UnrealProductionTaskDefinition:
        """Resolve a canonical task proposal into a validated semantic task.

        Uses M12.1 normalization (fail-closed) so the returned object is a
        fully-validated :class:`UnrealProductionTaskDefinition`. Provenance
        carries the catalog version + fragment identities (versioned).
        """
        entry = self.validate_parameters(name, parameters, version=version)
        fragments = tuple(canonical_fragment(fid) for fid in entry.fragment_ids)
        plan = compose_fragments(
            fragments,
            description=entry.objective,
        )
        composed_state = plan.target_state

        raw_request: Dict[str, Any] = {
            "canonical_task_id": entry.name,
            "task_class": entry.task_class,
            "digital_twin_id": digital_twin_id,
            "task_version": entry.version,
            "task_name": entry.name,
            "intent": entry.objective,
            "target_state": {
                "description": composed_state.description,
                "invariant_names": list(composed_state.invariant_names),
                "expects_render": entry.task_class in ("render-execute", "artifact-validate"),
            },
            "allowed_mutations": [entry.task_class],
            "dependencies": entry.fragment_ids,
            "evidence": [
                {
                    "tool": "unreal_inspect",
                    "arguments": {"capability": entry.task_class},
                    "name": f"inspect_{entry.task_class.replace('-', '_')}",
                }
            ],
            "actions": [
                {
                    "tool": "unreal_inspect",
                    "arguments": {"op": "inspect", "target": entry.task_class},
                    "name": f"inspect_{entry.task_class.replace('-', '_')}",
                }
            ],
            "allowed_action_tools": ["unreal_inspect"],
            "provenance": dict(provenance or {}),
            "metadata": {
                "catalog_version": self.version,
                "catalog_entry": entry.snapshot(),
                "fragments": list(plan.to_json_compatible()["fragments"]),
                "parameters": dict(parameters),
            },
        }
        return normalize_unreal_semantic_request(raw_request)

    # -- serialization -------------------------------------------------------

    def to_json_compatible(self) -> Dict[str, Any]:
        return {
            "catalog_version": self.version,
            "entries": [e.snapshot() for e in self._entries],
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.to_json_compatible(), sort_keys=True, separators=(",", ":")
        )


DEFAULT_UNREAL_CATALOG = UnrealSoccerProductionCatalog()

__all__ = [
    "UnrealCatalogError",
    "UnknownCatalogTaskError",
    "UnsupportedCatalogVersionError",
    "InvalidCatalogParametersError",
    "UnrealCatalogEntrySpec",
    "UnrealSoccerProductionCatalog",
    "DEFAULT_UNREAL_CATALOG",
]