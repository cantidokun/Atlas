"""A-REF harness-owned witness channel (R4F section 10.6).

The channel wraps every seam callable the harness injects — the pure extractor and pure mutator
on the pure path; the live extractor and the live production mutator (recording delegate,
R4F 16.5a) on the live path. It is harness code: the executor is invoked unchanged and remains
unaware of it.

Event spec (R4F 10.6, implemented verbatim): a PRE event carries (side, seam, invocation ordinal,
serialized-arguments digest); a RETURN event is recorded on normal return; a RAISE event carries
the original exception's QUALIFIED type name and message. The original exception is then
re-raised unchanged (bare raise; never converted, never swallowed, never re-created) so the
executor's own handling is exactly the production behaviour. Classification reads recorded
exception TYPES only, never message text.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Tuple

from tests.aref.aref_pure import EnvelopeRefusal


def _canonical_argument_value(v: Any) -> Any:
    """Deterministic JSON-able projection of one argument value (digest input only)."""
    if v is None or type(v) in (bool, int, float, str):
        return v
    if isinstance(v, (list, tuple)):
        return [_canonical_argument_value(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _canonical_argument_value(x) for k, x in sorted(v.items(), key=lambda kv: str(kv[0]))}
    state = getattr(v, "canonical_state", None)
    if callable(state):
        return {"__state__": _canonical_argument_value(state())}
    return {"__class__": f"{type(v).__module__}.{type(v).__qualname__}"}


def arguments_digest(args: Tuple[Any, ...], kwargs: dict) -> str:
    """Serialized-arguments digest (R4F 10.6 pre-event field)."""
    body = {"args": _canonical_argument_value(list(args)),
            "kwargs": _canonical_argument_value(dict(kwargs))}
    payload = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class WitnessEvent:
    side: str          # "pure" | "live"
    seam: str          # "extractor" | "mutator"
    ordinal: int
    kind: str          # "pre" | "return" | "raise"
    args_digest: Optional[str] = None          # pre-events: sha256 of the serialized arguments
    exception_type: Optional[str] = None       # raise-events: unqualified name (classification input)
    exception_qualified: Optional[str] = None  # raise-events: qualified type name (R4F 10.6)
    exception_message: Optional[str] = None    # raise-events: original message (R4F 10.6)
    witness_class: Optional[str] = None        # "ENVELOPE_REFUSAL" | "UNEXPECTED_FAULT"


@dataclass
class WitnessChannel:
    """Records pre/return/raise events per side; classifies raised exceptions mechanically."""

    events: List[WitnessEvent] = field(default_factory=list)
    _ordinals: dict = field(default_factory=dict)

    def _next_ordinal(self, side: str, seam: str) -> int:
        key = (side, seam)
        self._ordinals[key] = self._ordinals.get(key, 0) + 1
        return self._ordinals[key]

    def wrap(self, side: str, seam: str, fn: Callable[..., Any]) -> Callable[..., Any]:
        channel = self

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            ordinal = channel._next_ordinal(side, seam)
            digest = arguments_digest(args, kwargs)
            channel.events.append(WitnessEvent(side=side, seam=seam, ordinal=ordinal,
                                               kind="pre", args_digest=digest))
            try:
                result = fn(*args, **kwargs)
            except BaseException as exc:  # noqa: BLE001 - recorded, then re-raised unchanged
                exc_type = type(exc)
                if side == "pure" and isinstance(exc, EnvelopeRefusal):
                    witness_class = "ENVELOPE_REFUSAL"
                elif side == "live" and exc_type.__name__ == "BridgeRuntimeError":
                    witness_class = "ENVELOPE_REFUSAL"
                else:
                    witness_class = "UNEXPECTED_FAULT"
                channel.events.append(WitnessEvent(
                    side=side, seam=seam, ordinal=ordinal, kind="raise", args_digest=digest,
                    exception_type=exc_type.__name__,
                    exception_qualified=f"{exc_type.__module__}.{exc_type.__qualname__}",
                    exception_message=str(exc),
                    witness_class=witness_class))
                raise  # bare re-raise: the executor's own handling stays exactly production behaviour
            channel.events.append(WitnessEvent(side=side, seam=seam, ordinal=ordinal,
                                               kind="return", args_digest=digest))
            return result

        return wrapper

    @classmethod
    def from_trace(cls, trace) -> "WitnessChannel":
        """Rebuild a channel from a recorded trace (live evidence records carry traces)."""
        ch = cls()
        for ev in trace or []:
            ch.events.append(WitnessEvent(
                side=ev.get("side"), seam=ev.get("seam"), ordinal=ev.get("ordinal"),
                kind=ev.get("kind"), args_digest=ev.get("args_digest"),
                exception_type=ev.get("exception_type"),
                exception_qualified=ev.get("exception_qualified"),
                exception_message=ev.get("exception_message"),
                witness_class=ev.get("witness_class")))
        return ch

    # -- queries -------------------------------------------------------------------------------
    def raises(self, side: str, seam: Optional[str] = None) -> List[WitnessEvent]:
        return [e for e in self.events if e.side == side and e.kind == "raise"
                and (seam is None or e.seam == seam)]

    def has_unexpected_fault(self, side: str) -> bool:
        return any(e.witness_class == "UNEXPECTED_FAULT" for e in self.raises(side))

    def envelope_refusal_classes(self, side: str) -> List[str]:
        return [e.witness_class or "?" for e in self.raises(side) if e.seam == "mutator"]

    def trace(self) -> List[dict]:
        return [{"side": e.side, "seam": e.seam, "ordinal": e.ordinal, "kind": e.kind,
                 "args_digest": e.args_digest, "exception_type": e.exception_type,
                 "exception_qualified": e.exception_qualified,
                 "exception_message": e.exception_message, "witness_class": e.witness_class}
                for e in self.events]
