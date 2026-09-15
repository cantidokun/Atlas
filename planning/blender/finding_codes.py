"""Central, deterministic finding-code vocabulary for the Blender mesh/scene health kernel.

Stable language-neutral identifiers for every check the kernel can emit. These codes are the
primary semantic signal of a :class:`~planning.blender.scene_report.SceneReport`; human prose is
only a secondary, informational label and never carries the semantic meaning.

Codes are namespaced with a stable prefix (``MESH_`` / ``SCENE_`` / ``OBJECT_`` /
``DIGITAL_TWIN_``) and are documented centrally here. Do not invent ad-hoc string codes in
callers.

Severity is fixed per code (a check either passes or produces a finding of one severity); the
``SoccerFieldValidationProfile`` may additionally mark which codes are READY-blocking.
"""

from dataclasses import dataclass
from enum import Enum, unique
from typing import Any, Dict, Mapping, Optional, Tuple


@unique
class FindingSeverity(str, Enum):
    """Deterministic severity for a single finding."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    def __str__(self) -> str:  # deterministic serialization
        return self.value


@unique
class FindingCode(str, Enum):
    """Every machine-readable finding code the kernel can emit."""

    # --- mesh topology ---
    MESH_INVALID_INDEX = "MESH_INVALID_INDEX"  # face references a vertex index out of range
    MESH_DUPLICATE_VERTEX = "MESH_DUPLICATE_VERTEX"  # coincident vertices (>= tolerance)
    MESH_DUPLICATE_FACE = "MESH_DUPLICATE_FACE"  # two faces with the same vertex set + winding
    MESH_DEGENERATE_FACE = "MESH_DEGENERATE_FACE"  # zero area / repeated index / degenerate
    MESH_NON_MANIFOLD_EDGE = "MESH_NON_MANIFOLD_EDGE"  # an edge shared by != 2 faces
    MESH_WINDING_INCONSISTENT = "MESH_WINDING_INCONSISTENT"  # face orientation is conflicting
    MESH_NORMAL_INCONSISTENT = "MESH_NORMAL_INCONSISTENT"  # declared normal disagrees with geom
    MESH_SCALE_OUT_OF_RANGE = "MESH_SCALE_OUT_OF_RANGE"  # bounds fall outside the profile envelope

    # --- scene / organization ---
    SCENE_UNIT_INVALID = "SCENE_UNIT_INVALID"  # declared unit not allowed by the profile
    SCENE_ORIGIN_INVALID = "SCENE_ORIGIN_INVALID"  # coordinate frame / origin implausible
    SCENE_BOUNDS_EMPTY = "SCENE_BOUNDS_EMPTY"  # scene contains no measurable geometry

    # --- object / naming / hierarchy ---
    OBJECT_ID_DUPLICATE = "OBJECT_ID_DUPLICATE"  # duplicate stable object identifier
    OBJECT_NAME_INVALID = "OBJECT_NAME_INVALID"  # violates the naming convention
    OBJECT_HIERARCHY_INVALID = "OBJECT_HIERARCHY_INVALID"  # cycle / unknown parent / depth
    OBJECT_BOUNDS_OVERLAP = "OBJECT_BOUNDS_OVERLAP"  # object AABB overlaps (policy dependent)
    OBJECT_TRANSFORM_INVALID = "OBJECT_TRANSFORM_INVALID"  # transform contains non-finite values
    OBJECT_COLLECTION_INVALID = "OBJECT_COLLECTION_INVALID"  # collection/path disallowed

    # --- digital-twin readiness (derived from the kernel findings, not a hidden check) ---
    DIGITAL_TWIN_READINESS_FAILED = "DIGITAL_TWIN_READINESS_FAILED"

    def __str__(self) -> str:  # deterministic serialization
        return self.value


# Fixed severity per code (checks are deterministic: same code => same severity).
_SEVERITY_BY_CODE: Dict[FindingCode, FindingSeverity] = {
    FindingCode.MESH_INVALID_INDEX: FindingSeverity.ERROR,
    FindingCode.MESH_DUPLICATE_VERTEX: FindingSeverity.WARNING,
    FindingCode.MESH_DUPLICATE_FACE: FindingSeverity.WARNING,
    FindingCode.MESH_DEGENERATE_FACE: FindingSeverity.ERROR,
    FindingCode.MESH_NON_MANIFOLD_EDGE: FindingSeverity.WARNING,
    FindingCode.MESH_WINDING_INCONSISTENT: FindingSeverity.ERROR,
    FindingCode.MESH_NORMAL_INCONSISTENT: FindingSeverity.ERROR,
    FindingCode.MESH_SCALE_OUT_OF_RANGE: FindingSeverity.ERROR,
    FindingCode.SCENE_UNIT_INVALID: FindingSeverity.ERROR,
    FindingCode.SCENE_ORIGIN_INVALID: FindingSeverity.WARNING,
    FindingCode.SCENE_BOUNDS_EMPTY: FindingSeverity.ERROR,
    FindingCode.OBJECT_ID_DUPLICATE: FindingSeverity.ERROR,
    FindingCode.OBJECT_NAME_INVALID: FindingSeverity.ERROR,
    FindingCode.OBJECT_HIERARCHY_INVALID: FindingSeverity.ERROR,
    FindingCode.OBJECT_BOUNDS_OVERLAP: FindingSeverity.WARNING,
    FindingCode.OBJECT_TRANSFORM_INVALID: FindingSeverity.ERROR,
    FindingCode.OBJECT_COLLECTION_INVALID: FindingSeverity.ERROR,
    FindingCode.DIGITAL_TWIN_READINESS_FAILED: FindingSeverity.ERROR,
}

# Codes the ``<soccer-field>`` profile treats as NOT_READY-blocking by default. The kernel
# itself is profile-agnostic; this is only the default for ``default_soccer_field_profile()``.
DEFAULT_READY_BLOCKING_CODES: Tuple[FindingCode, ...] = tuple(
    code for code, sev in _SEVERITY_BY_CODE.items() if sev is FindingSeverity.ERROR
)


@dataclass(frozen=True)
class SeverityTable:
    """Expose the fixed severity mapping for callers/tests in a regular, ordered shape."""

    rows: Tuple[Tuple[FindingCode, FindingSeverity], ...] = ()

    @staticmethod
    def at(code: FindingCode) -> FindingSeverity:
        return _SEVERITY_BY_CODE[code]


def severity_of(code: FindingCode) -> FindingSeverity:
    """Return the fixed severity for a finding code (raises ``KeyError`` on unknown)."""
    try:
        return _SEVERITY_BY_CODE[code]
    except KeyError:
        raise KeyError(f"unknown finding code: {code!r}") from None


def parse_finding_code(value: Any) -> FindingCode:
    """Resolve a raw/str value to a FindingCode, failing closed on unknown/foreign values."""
    if isinstance(value, FindingCode):
        return value
    if type(value) is str:
        try:
            return FindingCode(value)
        except ValueError:
            raise ValueError(f"unknown finding code: {value!r}") from None
    raise TypeError("finding code must be a FindingCode or exact built-in str")


# ---------------------------------------------------------------------------
# Canonical JSON round-trip helpers (deterministic, sort-agnostic, language-neutral).
# Kept local; the kernel never depends on bpy or on any engine.
# ---------------------------------------------------------------------------


def _canonical_scalar(value: Any, *, label: str) -> Any:
    """Return a stable JSON-native representation of a value (closed canonical grammar).

    Accepts exact built-in scalars AND canonical JSON-native containers (dict with exact-str
    keys, list) so structured ``measured``/``expected`` values (e.g. envelope bounds, world
    coords) are representable in a finding. Subclasses and non-JSON types are rejected, and no
    caller-controlled behavior is invoked.
    """
    if value is None or type(value) in (str, int, float, bool):
        return value
    if type(value) is list:
        return [_canonical_scalar(v, label=f"{label}[{i}]") for i, v in enumerate(value)]
    if type(value) is tuple:
        return [_canonical_scalar(v, label=f"{label}[{i}]") for i, v in enumerate(value)]
    if type(value) is dict:
        out: Dict[str, Any] = {}
        for k, v in value.items():
            if type(k) is not str:
                raise TypeError(f"{label}: dict keys must be exact built-in str")
            out[k] = _canonical_scalar(v, label=f"{label}.{k}")
        return out
    raise TypeError(f"{label}: unsupported value type {type(value).__name__}")


def code_to_json(code: FindingCode) -> str:
    return code.value


def severity_to_json(sev: FindingSeverity) -> str:
    return sev.value


def finding_snapshot(
    *,
    code: FindingCode,
    severity: Optional[FindingSeverity] = None,
    object_id: Optional[str] = None,
    mesh_id: Optional[str] = None,
    measured: Any = None,
    expected: Any = None,
    message: str = "",
) -> Dict[str, Any]:
    """Deterministic machine-readable snapshot of one finding (no prose as primary signal)."""
    sev = severity if severity is not None else severity_of(code)
    out: Dict[str, Any] = {
        "code": code_to_json(code),
        "severity": severity_to_json(sev),
    }
    for key, val in (("object_id", object_id), ("mesh_id", mesh_id)):
        if val is not None:
            out[key] = _canonical_scalar(val, label=key)
    if measured is not None:
        out["measured"] = _canonical_scalar(measured, label="measured")
    if expected is not None:
        out["expected"] = _canonical_scalar(expected, label="expected")
    # Message is explicitly informational-only (never the semantic signal).
    out["message"] = message if type(message) is str else ""
    return out