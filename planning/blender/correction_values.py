"""Canonical value grammar + immutability plumbing for the Cleanup/Correction planner.

A small, closed, language-neutral value model shared by the planner modules:

- Exact built-in scalars (``str``/``int``/``float``/``bool``/``None``) are accepted verbatim.
- ``tuple`` and ``list`` and ``dict``-with-exact-``str``-keys (JSON-native) are normalized to
  immutable ``tuple`` / frozen-``MappingProxy`` canonical values.
- Every sub-class, arbitrary mapping, arbitrary sequence, callable, and non-JSON type is REJECTED
  structurally (no protocol methods such as ``items()``/``__getitem__`` are ever invoked on
  attacker-controlled objects).

This mirrors the canonical-value discipline already established for the mesh/scene health kernel
(``planning/blender/scene_report._canonical_scalar`` / ``planning/m12/canonical_values``): the
planner must never let Python object identity, bpy objects, or executable code leak into a
``CorrectionPlan``.
"""
from __future__ import annotations

import math
from types import MappingProxyType

from typing import Any

from planning.blender.scene_report import REPORT_FORMAT_VERSION


class CorrectionPlannerError(ValueError):
    """Declared error for the cleanup/correction planner (all planner failures are this type or
    a subclass, so callers never see a raw ``KeyError``/``TypeError``/``AttributeError``)."""


class CorrectionInputError(CorrectionPlannerError):
    """Malformed ``SceneReport`` / finding / profile input to the planner (fail closed)."""


class CorrectionPlanError(CorrectionPlannerError):
    """A plan cannot be produced deterministically (e.g. dependency cycle / contradiction)."""


def _canonical_scalar(value: Any, *, label: str, _depth: int = 0) -> Any:
    """Return an immutable, JSON-native canonical value (deterministic, fail-closed).

    - ``None`` / exact ``str`` / exact ``int`` / exact ``float`` / exact ``bool`` -> as-is,
      EXCEPT non-finite floats (``NaN`` / ``+Inf`` / ``-Inf``) are REJECTED with
      ``CorrectionInputError`` (a plan must never carry a non-JSON-compliant number).
    - ``list`` / ``tuple`` -> immutable ``tuple`` of canonical values (JSON-identical).
    - ``dict`` with exact-``str`` keys -> ``{key: canonical}`` plain dict (immutability is the
      caller's contract; keys are exact built-in ``str``, values canonical).
    - Everything else (subclasses, mappings, sequences, callables, custom objects) -> raise
      ``CorrectionInputError``.

    No arbitrary protocol method is invoked: ``type(x) is`` exact-type checks only, and the value
    is re-walked so a hostile container cannot hide behavior in a nested element.
    """
    if value is None:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise CorrectionInputError(f"{label}: non-finite float (NaN/Inf) is not allowed")
        return value
    if type(value) in (str, int, bool):
        return value
    if type(value) is list:
        if _depth > 64:
            raise CorrectionInputError(f"{label}: nesting too deep")
        return tuple(_canonical_scalar(v, label=f"{label}[{i}]", _depth=_depth + 1)
                     for i, v in enumerate(value))
    if type(value) is tuple:
        if _depth > 64:
            raise CorrectionInputError(f"{label}: nesting too deep")
        return tuple(_canonical_scalar(v, label=f"{label}[{i}]", _depth=_depth + 1)
                     for i, v in enumerate(value))
    if type(value) is dict:
        if _depth > 64:
            raise CorrectionInputError(f"{label}: nesting too deep")
        out: dict = {}
        for k, v in value.items():
            if type(k) is not str:
                raise CorrectionInputError(f"{label}: dict keys must be exact built-in str")
            out[k] = _canonical_scalar(v, label=f"{label}.{k}", _depth=_depth + 1)
        return out
    raise CorrectionInputError(
        f"{label}: unsupported value type {type(value).__name__} "
        "(must be JSON-native built-in scalar/tuple/list/dict-with-str-keys)"
    )


def canonical_json_bytes(payload: Any) -> bytes:
    """Serialize a canonical (already-JSON-native) value to deterministic UTF-8 bytes.

    ``json.dumps`` with ``sort_keys=True``, no allow-nan, compact separators — the same
    serialization the kernel uses for ``SceneReport.canonical_json`` so digests are stable and
    language-neutral.
    """
    import json

    try:
        return json.dumps(
            _canonical_scalar(thaw_jsonable(payload), label="canonical"),  # re-normalize: no non-JSON form slips in
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CorrectionPlanError(f"cannot serialize canonical plan: {exc}") from exc


def freeze_canonical(value: Any, *, label: str = "value") -> Any:
    """Return an IMMUTABLE deep copy of a canonical value (D1 deep-freeze).

    - ``dict`` (with exact-``str`` keys) -> recursively frozen ``MappingProxyType``.
    - ``list``/``tuple`` -> recursively frozen ``tuple``.
    - scalars (already validated finite/JSON-native by ``_canonical_scalar``) returned as-is.

    The result is what a ``CorrectionProposal``/``CorrectionPlan`` stores, so a caller-held
    reference to the INPUT cannot mutate canonical content after construction, and the stored
    container itself cannot be mutated through its attributes (the dataclass is frozen at the
    top level AND deeply).
    """
    if value is None or type(value) in (str, int, float, bool):
        return value
    if type(value) is dict:
        return MappingProxyType(
            {k: freeze_canonical(v, label=f"{label}.{k}") for k, v in value.items()}
        )
    if type(value) in (list, tuple):
        return tuple(freeze_canonical(v, label=f"{label}[{i}]") for i, v in enumerate(value))
    raise CorrectionInputError(
        f"{label}: cannot freeze value of type {type(value).__name__}"
    )


def thaw_jsonable(value: Any) -> Any:
    """Reconstruct a JSON-NATIVE (and thus JSON-serializable) value from a frozen one.

    ``MappingProxyType`` -> ``dict``, ``tuple`` -> ``list`` (recursively, and recursing into plain
    ``dict``/proxies), scalars unchanged. Byte-for-byte identical to the JSON that
    ``_canonical_scalar`` produced (JSON compares a tuple and a same-element list identically), so
    freezing does not change plan identity/serialization.
    """
    if type(value) is MappingProxyType:
        return {k: thaw_jsonable(v) for k, v in value.items()}
    if type(value) is dict:
        return {k: thaw_jsonable(v) for k, v in value.items()}
    if type(value) is tuple:
        return [thaw_jsonable(v) for v in value]
    if type(value) is list:
        return [thaw_jsonable(v) for v in value]
    return value


def require_report_format_version(report_format_version: Any) -> None:
    """Fail closed unless the report format version is the one this planner understands.

    The planner consumes ``SceneReport``-shaped inputs at a specific ``REPORT_FORMAT_VERSION``.
    An unknown/future format must never silently produce a plan (provenance integrity).
    """
    if type(report_format_version) is not str:
        raise CorrectionInputError("report_format_version must be an exact built-in str")
    if report_format_version != REPORT_FORMAT_VERSION:
        raise CorrectionInputError(
            f"unsupported report format version {report_format_version!r} "
            f"(planner supports {REPORT_FORMAT_VERSION!r})"
        )