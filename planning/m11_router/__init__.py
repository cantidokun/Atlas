"""M11 adaptive development-model router (core).

Development-tooling only. This package NEVER becomes Atlas production or
recovery authority: it selects model tiers, escalates on evidence, and records
dev telemetry. It holds no pathway to authorization, scheduling, submission,
receipts, or production recovery, and its persistence is confined to a dedicated
``m11_router`` namespace. See docs/ATLAS_M11_ADAPTIVE_MODEL_ROUTING_DESIGN.md.
"""

from planning.m11_router.model_profile import (
    ModelProfile,
    ModelTier,
    ProfileLoadError,
    load_profiles,
    tier_index,
    tier_max,
)
from planning.m11_router.risk import (
    RISK_DIMENSIONS,
    HARD_SELECTOR_DIMENSIONS,
    RiskAssessment,
    classify_task,
)
from planning.m11_router.routing import ModelSelection, NoCapableProfileError, RouterDecision, select_profile
from planning.m11_router.escalation import (
    EscalationController,
    EscalationPolicyError,
    EscalationState,
    EscalationTerminal,
    MAX_ESCALATIONS_PER_TASK,
    MAX_TIER,
)
from planning.m11_router.telemetry import AppendOnlyTelemetry, RouterTelemetryRecord, TelemetryValidationError
from planning.m11_router.evidence_gate import EvidenceGate, EvidenceGateResult, EvidenceGateResultKind
from planning.m11_router.escalation_packet import EscalationPacket
from planning.m11_router.router import ModelRouter
from planning.m11_router.hermes_integration import (
    M11FeatureConfig,
    ShadowRoutedExecutor,
    load_feature_config,
    FeatureConfigError,
    FeatureDisabledError,
)
from planning.m11_router.live_validation import (
    ControlledLiveValidator,
    LiveValidationResult,
)
__all__ = [
    "ModelProfile",
    "ModelTier",
    "ProfileLoadError",
    "load_profiles",
    "tier_index",
    "tier_max",
    "RISK_DIMENSIONS",
    "HARD_SELECTOR_DIMENSIONS",
    "RiskAssessment",
    "classify_task",
    "ModelSelection",
    "NoCapableProfileError",
    "RouterDecision",
    "select_profile",
    "EscalationController",
    "EscalationPolicyError",
    "EscalationState",
    "EscalationTerminal",
    "MAX_ESCALATIONS_PER_TASK",
    "MAX_TIER",
    "AppendOnlyTelemetry",
    "RouterTelemetryRecord",
    "TelemetryValidationError",
    "EvidenceGate",
    "EvidenceGateResult",
    "EvidenceGateResultKind",
    "EscalationPacket",
    "ModelRouter",
    "M11FeatureConfig",
    "ShadowRoutedExecutor",
    "load_feature_config",
    "FeatureConfigError",
    "FeatureDisabledError",
    "ControlledLiveValidator",
    "LiveValidationResult",
]