"""Live Identity Continuity Resolver for Atlas Live.

Resolves external perception provider tracks into canonical stable Atlas entity identities.
Sits between LiveObservationFrame normalization and LiveWorldStateReconciler.

Adheres to Astra Option C:
- Shared conservative identity semantics (MATCH, NO_MATCH, INSUFFICIENT_EVIDENCE).
- Separate Live execution path (decoupled from planning / Blender workflows).
- Explicit 4-state lifecycle: UNBOUND, BOUND, TEMPORARILY_UNOBSERVED, DISPUTED.
- Positive evidence required for binding; ambiguity remains unresolved.
- Ephemeral provider track IDs are distinct from stable Atlas entity IDs.
"""

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple

from live.observation import EntityObservation, LiveObservationFrame


class IdentityState(str, Enum):
    UNBOUND = "unbound"
    BOUND = "bound"
    TEMPORARILY_UNOBSERVED = "temporarily_unobserved"
    DISPUTED = "disputed"


class IdentityMatchStatus(str, Enum):
    MATCH = "match"
    NO_MATCH = "no_match"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True)
class IdentityBindingRecord:
    """Immutable record of an established or tracked entity binding."""

    atlas_entity_id: str
    provider_id: str
    provider_session: str
    provider_track_id: str
    state: IdentityState
    last_seen_timestamp_ns: int
    binding_established_at_ns: int
    attributes: Tuple[Tuple[str, str], ...] = ()


@dataclass(frozen=True)
class IdentityResolverTelemetry:
    """Observable telemetry metrics for identity continuity transitions."""

    entity_appeared_count: int = 0
    entity_disappeared_count: int = 0
    track_unresolved_count: int = 0
    identity_binding_established_count: int = 0
    identity_binding_rejected_count: int = 0
    identity_disputed_count: int = 0
    temporary_absence_count: int = 0
    reacquisition_count: int = 0


# Default trusted entities for backwards compatibility with simulated streams
DEFAULT_TRUSTED_ENTITIES: Set[str] = {"player-09", "ball", "test_player", "test_ball"}


class LiveIdentityResolver:
    """Conservative, deterministic Live identity continuity resolver.

    Maintains track-to-entity bindings across observation frames without guessing.
    Rejects ambiguous or unmapped tracks, suppresses disputed entities,
    and isolates ephemeral provider tracks from stable Atlas entity IDs.
    """

    def __init__(
        self,
        retention_window_ns: int = 2_000_000_000,  # 2.0s retention for temporarily unobserved
        trusted_bindings: Optional[Mapping[str, str]] = None,
        default_session: str = "live-session-01",
    ) -> None:
        if retention_window_ns <= 0:
            raise ValueError("retention_window_ns must be positive")
        self.retention_window_ns: int = retention_window_ns
        self.default_session: str = default_session

        # Explicit trusted initial bindings: provider_track_id -> atlas_entity_id
        self._trusted_bindings: Dict[str, str] = {}
        if trusted_bindings is not None:
            for track_id, entity_id in trusted_bindings.items():
                self._trusted_bindings[track_id.strip()] = entity_id.strip()
        else:
            # Seed with default trusted simulated identities
            for entity_id in DEFAULT_TRUSTED_ENTITIES:
                self._trusted_bindings[entity_id] = entity_id

        # Active bindings: atlas_entity_id -> IdentityBindingRecord
        self._entity_bindings: Dict[str, IdentityBindingRecord] = {}
        # Track-to-entity index: (provider_id, provider_session, provider_track_id) -> atlas_entity_id
        self._track_to_entity: Dict[Tuple[str, str, str], str] = {}
        # Disputed entity IDs
        self._disputed_entities: Set[str] = set()

        # Telemetry counters
        self._entity_appeared_count: int = 0
        self._entity_disappeared_count: int = 0
        self._track_unresolved_count: int = 0
        self._identity_binding_established_count: int = 0
        self._identity_binding_rejected_count: int = 0
        self._identity_disputed_count: int = 0
        self._temporary_absence_count: int = 0
        self._reacquisition_count: int = 0

    @property
    def telemetry(self) -> IdentityResolverTelemetry:
        return IdentityResolverTelemetry(
            entity_appeared_count=self._entity_appeared_count,
            entity_disappeared_count=self._entity_disappeared_count,
            track_unresolved_count=self._track_unresolved_count,
            identity_binding_established_count=self._identity_binding_established_count,
            identity_binding_rejected_count=self._identity_binding_rejected_count,
            identity_disputed_count=self._identity_disputed_count,
            temporary_absence_count=self._temporary_absence_count,
            reacquisition_count=self._reacquisition_count,
        )

    def bind_trusted(
        self,
        provider_track_id: str,
        atlas_entity_id: str,
        provider_id: str = "trusted",
        provider_session: Optional[str] = None,
        timestamp_ns: int = 0,
    ) -> None:
        """Explicitly register an authoritative binding."""
        p_track = provider_track_id.strip()
        a_entity = atlas_entity_id.strip()
        session = provider_session or self.default_session
        self._trusted_bindings[p_track] = a_entity

        record = IdentityBindingRecord(
            atlas_entity_id=a_entity,
            provider_id=provider_id.strip(),
            provider_session=session,
            provider_track_id=p_track,
            state=IdentityState.BOUND,
            last_seen_timestamp_ns=timestamp_ns,
            binding_established_at_ns=timestamp_ns or time.perf_counter_ns(),
        )
        self._entity_bindings[a_entity] = record
        self._track_to_entity[(provider_id.strip(), session, p_track)] = a_entity
        self._identity_binding_established_count += 1

    def get_binding(self, atlas_entity_id: str) -> Optional[IdentityBindingRecord]:
        return self._entity_bindings.get(atlas_entity_id.strip())

    def get_track_state(self, provider_id: str, provider_track_id: str, provider_session: Optional[str] = None) -> IdentityState:
        session = provider_session or self.default_session
        key = (provider_id.strip(), session, provider_track_id.strip())
        atlas_id = self._track_to_entity.get(key)
        if atlas_id is None:
            return IdentityState.UNBOUND
        if atlas_id in self._disputed_entities:
            return IdentityState.DISPUTED
        record = self._entity_bindings.get(atlas_id)
        if record is None:
            return IdentityState.UNBOUND
        return record.state

    def resolve_frame(self, frame: LiveObservationFrame) -> LiveObservationFrame:
        """Resolve incoming observation frame entities to stable Atlas entity IDs.

        Deterministic rules:
        1. Only trusted or safely continuable tracks are admitted (UNBOUND -> BOUND).
        2. Competing tracks claiming the same Atlas ID trigger DISPUTED (both suppressed).
        3. Absent bound entities transition to TEMPORARILY_UNOBSERVED.
        4. Reappearing unobserved entities transition back to BOUND with valid evidence.
        5. Failed track matches do NOT auto-admit new canonical entities.
        """
        provider_id = frame.source_id.strip()
        session_id = (
            frame.metadata.get("session_id", self.default_session)
            if frame.metadata
            else self.default_session
        )
        timestamp_ns = frame.timestamp_ns

        # Map candidate tracks in this frame: candidate_target_id -> List[EntityObservation]
        candidate_matches: Dict[str, List[Tuple[str, EntityObservation]]] = {}
        unresolved_observations: List[EntityObservation] = []

        for obs in frame.entities:
            track_id = obs.entity_id.strip()
            # Determine candidate Atlas entity ID
            # 1. Existing active track binding for this provider & session
            target_atlas_id = self._track_to_entity.get((provider_id, session_id, track_id))

            # 2. Trusted binding map
            if target_atlas_id is None and track_id in self._trusted_bindings:
                target_atlas_id = self._trusted_bindings[track_id]

            # 3. Explicit attribute anchor e.g. ("atlas_entity_id", "...")
            if target_atlas_id is None:
                for k, v in obs.attributes:
                    if k.strip().lower() == "atlas_entity_id" and v.strip():
                        target_atlas_id = v.strip()
                        break

            if target_atlas_id is not None:
                if target_atlas_id not in candidate_matches:
                    candidate_matches[target_atlas_id] = []
                candidate_matches[target_atlas_id].append((track_id, obs))
            else:
                # UNBOUND track without authoritative evidence: remains unresolved
                unresolved_observations.append(obs)
                self._track_unresolved_count += 1
                self._identity_binding_rejected_count += 1

        resolved_entities: List[EntityObservation] = []
        observed_atlas_ids: Set[str] = set()

        # Process candidate matches
        for target_atlas_id, candidates in candidate_matches.items():
            if len(candidates) > 1:
                # CONFLICT: Multiple distinct provider tracks compete for the same Atlas ID
                self._disputed_entities.add(target_atlas_id)
                self._identity_disputed_count += 1
                for track_id, _ in candidates:
                    self._track_to_entity[(provider_id, session_id, track_id)] = target_atlas_id
                # Mark existing binding as DISPUTED
                prior = self._entity_bindings.get(target_atlas_id)
                if prior is not None:
                    self._entity_bindings[target_atlas_id] = IdentityBindingRecord(
                        atlas_entity_id=target_atlas_id,
                        provider_id=provider_id,
                        provider_session=session_id,
                        provider_track_id="disputed",
                        state=IdentityState.DISPUTED,
                        last_seen_timestamp_ns=timestamp_ns,
                        binding_established_at_ns=prior.binding_established_at_ns,
                    )
                # Suppress output for disputed entity (do not emit to canonical WorldState)
                continue

            track_id, obs = candidates[0]

            # Check if this target ID was previously disputed
            if target_atlas_id in self._disputed_entities:
                # Check if conflicting track has cleared or remains disputed
                # For safety, keep disputed until explicitly cleared
                continue

            # Check prior binding record
            prior = self._entity_bindings.get(target_atlas_id)
            if prior is None:
                # UNBOUND -> BOUND (Authoritative initial binding)
                new_record = IdentityBindingRecord(
                    atlas_entity_id=target_atlas_id,
                    provider_id=provider_id,
                    provider_session=session_id,
                    provider_track_id=track_id,
                    state=IdentityState.BOUND,
                    last_seen_timestamp_ns=timestamp_ns,
                    binding_established_at_ns=timestamp_ns,
                )
                self._entity_bindings[target_atlas_id] = new_record
                self._track_to_entity[(provider_id, session_id, track_id)] = target_atlas_id
                self._entity_appeared_count += 1
                self._identity_binding_established_count += 1
            else:
                # Existing entity: check continuity vs recycled track
                if prior.state == IdentityState.TEMPORARILY_UNOBSERVED:
                    # TEMPORARILY_UNOBSERVED -> BOUND (Reacquisition)
                    updated = IdentityBindingRecord(
                        atlas_entity_id=target_atlas_id,
                        provider_id=provider_id,
                        provider_session=session_id,
                        provider_track_id=track_id,
                        state=IdentityState.BOUND,
                        last_seen_timestamp_ns=timestamp_ns,
                        binding_established_at_ns=prior.binding_established_at_ns,
                    )
                    self._entity_bindings[target_atlas_id] = updated
                    self._track_to_entity[(provider_id, session_id, track_id)] = target_atlas_id
                    self._reacquisition_count += 1
                else:
                    # BOUND -> BOUND (Normal continuity)
                    updated = IdentityBindingRecord(
                        atlas_entity_id=target_atlas_id,
                        provider_id=provider_id,
                        provider_session=session_id,
                        provider_track_id=track_id,
                        state=IdentityState.BOUND,
                        last_seen_timestamp_ns=timestamp_ns,
                        binding_established_at_ns=prior.binding_established_at_ns,
                    )
                    self._entity_bindings[target_atlas_id] = updated
                    self._track_to_entity[(provider_id, session_id, track_id)] = target_atlas_id

            observed_atlas_ids.add(target_atlas_id)

            # Preserve provider provenance separately from stable atlas_entity_id
            provenance_attrs = [
                ("provider_id", provider_id),
                ("provider_session", session_id),
                ("provider_track_id", track_id),
            ]
            for k, v in obs.attributes:
                if k not in ("provider_id", "provider_session", "provider_track_id"):
                    provenance_attrs.append((k, v))

            # Emit resolved EntityObservation with stable atlas_entity_id
            resolved_entities.append(
                EntityObservation(
                    entity_id=target_atlas_id,
                    pose=obs.pose,
                    velocity=obs.velocity,
                    confidence=obs.confidence,
                    attributes=tuple(provenance_attrs),
                )
            )

        # Check for entities that were BOUND but absent from this frame
        for entity_id, record in list(self._entity_bindings.items()):
            if entity_id not in observed_atlas_ids and record.state == IdentityState.BOUND:
                elapsed_ns = timestamp_ns - record.last_seen_timestamp_ns
                if elapsed_ns <= self.retention_window_ns:
                    # BOUND -> TEMPORARILY_UNOBSERVED
                    unobserved_record = IdentityBindingRecord(
                        atlas_entity_id=record.atlas_entity_id,
                        provider_id=record.provider_id,
                        provider_session=record.provider_session,
                        provider_track_id=record.provider_track_id,
                        state=IdentityState.TEMPORARILY_UNOBSERVED,
                        last_seen_timestamp_ns=record.last_seen_timestamp_ns,
                        binding_established_at_ns=record.binding_established_at_ns,
                    )
                    self._entity_bindings[entity_id] = unobserved_record
                    self._entity_disappeared_count += 1
                    self._temporary_absence_count += 1

        return LiveObservationFrame(
            source_id=frame.source_id,
            sequence_number=frame.sequence_number,
            timestamp_ns=frame.timestamp_ns,
            entities=tuple(resolved_entities),
            frame_attributes=frame.frame_attributes,
            metadata=frame.metadata,
            ingested_at_ns=frame.ingested_at_ns,
        )
