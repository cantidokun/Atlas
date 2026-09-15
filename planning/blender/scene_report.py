"""Deterministic machine-readable SceneReport + finding model (kernel OUTPUT).

The report is the single stable, language-neutral output of the mesh/scene health kernel. It
carries:
- provenance (source scene id, an optional input digest, and the validator/profile version);
- a derived overall validation state (see :mod:`planning.blender.digital_twin_readiness`);
- a deterministic, ordered list of structured findings (stable codes, severity, affected ids,
  measured/expected, informational message).

All serialization is deterministic: findings are sorted by a stable key and the JSON form uses
sorted keys, so the same input always yields a byte-for-byte-equivalent canonical report. No prose
is the primary semantic signal — codes carry the meaning.
"""

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from planning.blender.finding_codes import FindingCode, FindingSeverity, finding_snapshot, severity_of

# Version of the validator/report contract. Bump when the schema or rules change in a way that
# is not backward-compatible; the profile/version string surfaces in the report and in readiness.
VALIDATOR_VERSION = "1"
REPORT_FORMAT_VERSION = "1"


@dataclass(frozen=True)
class Finding:
    """One immutable, deterministic finding produced by a kernel check."""

    code: FindingCode
    object_id: Optional[str] = None
    mesh_id: Optional[str] = None
    measured: Any = None
    expected: Any = None
    message: str = ""

    @property
    def severity(self) -> FindingSeverity:
        return severity_of(self.code)

    def snapshot(self) -> Dict[str, Any]:
        return finding_snapshot(
            code=self.code,
            severity=self.severity,
            object_id=self.object_id,
            mesh_id=self.mesh_id,
            measured=self.measured,
            expected=self.expected,
            message=self.message,
        )

    def sort_key(self) -> Tuple[str, str, str]:
        """Stable, language-neutral ordering key (code, then object, then mesh)."""
        return (
            self.code.value,
            self.object_id or "",
            self.mesh_id or "",
        )


def _findings_sorted(findings: Iterable[Finding]) -> Tuple[Finding, ...]:
    return tuple(sorted(findings, key=lambda f: f.sort_key()))


@dataclass(frozen=True)
class SceneReport:
    """Canonical output of the mesh/scene health kernel."""

    scene_id: str
    validation_state: str  # from planning.blender.digital_twin_readiness; already a stable term
    findings: Tuple[Finding, ...] = ()
    scene_metrics: Mapping[str, Any] = None  # type: ignore[assignment]
    profile_name: str = ""
    validator_version: str = VALIDATOR_VERSION
    input_digest: Optional[str] = None
    source_revision_id: Optional[str] = None

    def __post_init__(self) -> None:
        if type(self.scene_id) is not str or not self.scene_id.strip():
            raise ValueError("report.scene_id must be a non-empty string")
        if type(self.validation_state) is not str or not self.validation_state.strip():
            raise ValueError("report.validation_state must be a non-empty string")
        object.__setattr__(self, "findings", _findings_sorted(self.findings))
        if self.scene_metrics is None:
            object.__setattr__(self, "scene_metrics", {})
        if type(self.scene_metrics) is not dict:
            raise ValueError("report.scene_metrics must be a dict (or None)")

    # -- accessors ---------------------------------------------------------

    @property
    def errors(self) -> Tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity is FindingSeverity.ERROR)

    @property
    def warnings(self) -> Tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity is FindingSeverity.WARNING)

    def has_code(self, code: FindingCode) -> bool:
        return any(f.code is code for f in self.findings)

    def findings_for(self, *, object_id: Optional[str] = None, mesh_id: Optional[str] = None) -> Tuple[Finding, ...]:
        out = self.findings
        if object_id is not None:
            out = tuple(f for f in out if f.object_id == object_id)
        if mesh_id is not None:
            out = tuple(f for f in out if f.mesh_id == mesh_id)
        return out

    # -- deterministic serialization --------------------------------------

    def to_json_compatible(self) -> Dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "validator_version": self.validator_version,
            "report_format_version": REPORT_FORMAT_VERSION,
            "profile_name": self.profile_name,
            "validation_state": self.validation_state,
            "input_digest": self.input_digest,
            "source_revision_id": self.source_revision_id,
            "scene_metrics": dict(self.scene_metrics),
            "findings": [f.snapshot() for f in self.findings],
        }

    def canonical_json(self) -> str:
        payload = self.to_json_compatible()
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def compute_input_digest(values: Mapping[str, Any]) -> str:
    """Deterministic digest of the canonicalized scene INPUT for provenance binding."""
    payload = json.dumps(
        dict(values), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_report(
    *,
    scene_id: str,
    validation_state: str,
    findings: Iterable[Finding],
    scene_metrics: Optional[Mapping[str, Any]] = None,
    profile_name: str = "",
    input_digest: Optional[str] = None,
    source_revision_id: Optional[str] = None,
) -> SceneReport:
    return SceneReport(
        scene_id=scene_id,
        validation_state=validation_state,
        findings=findings,
        scene_metrics=dict(scene_metrics) if scene_metrics is not None else {},
        profile_name=profile_name,
        input_digest=input_digest,
        source_revision_id=source_revision_id,
    )