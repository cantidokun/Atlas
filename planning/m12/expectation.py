"""Atlas M12.6 R2-A refusal-only expectation machinery.

Normative authority: ``ATLAS_M12_6_R1_NORMATIVE_DESIGN_REV18.md``
(sha256 ``ec5eab43a4dbd3dc8e7c376133aff954a6c25a4283c3eb0d2bed31081ae2b41d``), treated as the sole contract for
M12.6 R2-A. Clause references in this module (``VII.4``, ``VIII.1``, ``XI.4``, ``XIV.3.1``, ``Part XV``, ...) name
that artifact.

Scope implemented here (R2-A only, Part XXIV):

* the closed Part XV classifier table and ``classify_failure_row`` (row-keyed, total, fail-closed; XIV.7.1);
* the stage/class homogeneity census and the within-stage precedence/aggregation rule (XIV.3.1);
* the state mapping for the eight closed vocabularies (XIV.3);
* Domain A digest machinery and the R2-A-reachable recipes of XI.4 (X.2 plan digest included);
* the closed registry, the (empty) reviewed production-target table and their reviewed-constant revalidation
  (V.4.9, V.5.1, VIII.1-VIII.3);
* the bounded structural preflight F1-F9 (VII.4);
* the Part IX expectation closed-schema classification, including the case-relative target-member typing rule;
* the resolver's S1-S4 decision set (rows 1, 3, 6, 9-14, 21, 22, 26, 27, 29-33, 36-44) and the verifier's
  expectation-side S1/S3 rows (4, 5, 7, 8, 14, 21, 28, 30, 39), combined by the union rule (XIV.7.3);
* the closed M12.6 result object (XIV.4.5) with the unresolved entry form (XIV.4.1) and the two entry recipes
  (XIV.4.3, XIV.4.4), so every refusal is structurally complete.

Explicitly NOT implemented here (R2-B; Part XXIV/XXIII): target population, positive semantic verification,
``SATISFIED``/``NOT_SATISFIED`` production, evaluation (S5/S6) as a decision, authority classes other than
``CODE_CONSTANT``, witnesses, and any caller-supplied authority.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from planning.m12.catalog import UnrealSoccerProductionCatalog
from planning.m12.execution_plan import (
    UnrealExecutionPlan,
    _canonical_sha256,
    compute_source_content_digest,
)
from planning.m12.fragments_registry import CANONICAL_UNREAL_FRAGMENTS
from planning.m12.semantic_task import UnrealProductionTaskDefinition
from planning.m12.task_classes import is_render_task_class
from planning.unreal_state_extraction import jcs

# --------------------------------------------------------------------------- VIII.1 constants

EXPECTATION_CONTRACT_REVISION = "m12.6-expectation-v1"
RESULT_SCHEMA_CONSTANT = "m12.6-result-v1"
EVIDENCE_SCHEMA_CONSTANT = "m12.6-evidence-identity-v1"
ENTRY_SCHEMA_CONSTANT = "m12.6-invariant-result-v1"
VERIFIER_REVISION = "m12.6-v1"
RESOLVER_REVISION = "m12.6-resolver-v1"
REGISTRY_REVISION = 1
TARGET_TABLE_REVISION = 1

VOCABULARY_ENTRY_SCHEMA = "m12.6-vocabulary-entry-v1"
DEFINITION_SCHEMA = "m12.6-definition-v1"
TARGET_SCHEMA = "m12.6-target-v1"
TARGET_TABLE_SCHEMA = "m12.6-target-table-v1"
REGISTRY_SCHEMA = "m12.6-registry-v1"

ORIGIN_STATUS = "NOT_ESTABLISHED"
TARGET_INPUTS_NOT_ESTABLISHED = "UNKNOWN_EVIDENCE_INSUFFICIENT"

# VII.4.2 bounded traversal
PREFLIGHT_DEPTH_LIMIT = 20
PREFLIGHT_NODE_BUDGET = 100_000
# XI.1 Domain A integer range
DOMAIN_A_INT_LIMIT = 2 ** 53 - 1

STAGES = ("S1", "S2", "S3", "S4", "S5", "S6")
_REASON_CLASSES = (
    "BINDING_ABSENT",
    "AUTHORITY_ABSENT",
    "EVIDENCE_INSUFFICIENT",
    "INTERNAL_FAILURE",
    "SATISFIED",
    "EVALUATED_MISMATCH",
)


class M126ContractError(ValueError):
    """A construction error under the R18 contract (never a refusal path)."""


class M126UnreadableAuthorityError(M126ContractError):
    """VII.5 unreadable-authority internal fault: no semantic result may be emitted."""


# --------------------------------------------------------------------------- Part XV closed matrix

#: The 42 declared rows: one condition, one token, one stage, one reason class (Part XV).
PART_XV_ROWS: Tuple[Tuple[int, str, str, str], ...] = (
    (1, "RESOLVER_INPUT_STRUCTURE_INVALID", "S1", "BINDING_ABSENT"),
    (2, "RESOLVER_INTERNAL_FAILURE", "", "INTERNAL_FAILURE"),
    (3, "EXPECTED_VALUE_UNAVAILABLE", "S4", "AUTHORITY_ABSENT"),
    (4, "EXPECTATION_IDENTITY_MISMATCH", "S3", "BINDING_ABSENT"),
    (5, "EXPECTATION_INCOMPLETE", "S3", "BINDING_ABSENT"),
    (6, "EXPECTED_VALUE_UNAVAILABLE", "S4", "AUTHORITY_ABSENT"),
    (7, "EXPECTATION_IDENTITY_MISMATCH", "S3", "BINDING_ABSENT"),
    (8, "EXPECTATION_DIGEST_MISMATCH", "S3", "BINDING_ABSENT"),
    (9, "REGISTRY_SOURCE_NOT_CANONICAL", "S2", "AUTHORITY_ABSENT"),
    (10, "PRODUCTION_TARGET_NOT_CANONICAL", "S2", "AUTHORITY_ABSENT"),
    (11, "EXPECTATION_DEFINITION_DUPLICATE", "S2", "AUTHORITY_ABSENT"),
    (12, "PRODUCTION_TARGET_MAPPING_DUPLICATE", "S2", "AUTHORITY_ABSENT"),
    (13, "IDENTITY_MISMATCH", "S3", "BINDING_ABSENT"),
    (14, "EXPECTATION_IDENTITY_MISMATCH", "S3", "BINDING_ABSENT"),
    (15, "OBSERVATION_IDENTITY_NOT_TRANSPORT_ROOTED", "S5", "EVIDENCE_INSUFFICIENT"),
    (16, "OBSERVATION_CORRELATION_MISMATCH", "S5", "EVIDENCE_INSUFFICIENT"),
    (17, "EXTRACTION_CONTRACT_REVISION_MISMATCH", "S5", "EVIDENCE_INSUFFICIENT"),
    (18, "OBSERVATION_SCOPE_DIVERGENCE", "S5", "EVIDENCE_INSUFFICIENT"),
    (19, "EXPECTATION_SCOPE_NOT_OBSERVED", "S5", "EVIDENCE_INSUFFICIENT"),
    (20, "CONTRADICTORY", "S5", "EVIDENCE_INSUFFICIENT"),
    (21, "EXPECTATION_IDENTITY_MISMATCH", "S3", "BINDING_ABSENT"),
    (22, "PRODUCTION_TARGET_NOT_ESTABLISHED", "S4", "AUTHORITY_ABSENT"),
    (23, "EXPECTED_VALUE_UNAVAILABLE", "S5", "EVIDENCE_INSUFFICIENT"),
    (24, "EXPECTATION_CONTRADICTORY", "S5", "EVIDENCE_INSUFFICIENT"),
    (25, "EXPECTED_VALUE_UNAVAILABLE", "S5", "EVIDENCE_INSUFFICIENT"),
    (26, "EXPECTATION_VOCABULARY_MISMATCH", "S3", "BINDING_ABSENT"),
    (27, "PLAN_STEP_NOT_CANONICAL", "S3", "BINDING_ABSENT"),
    (28, "RESOLVER_INPUT_STRUCTURE_INVALID", "S1", "BINDING_ABSENT"),
    (29, "PLAN_CONTENT_UNSUPPORTED", "S1", "BINDING_ABSENT"),
    (30, "EMPTY_REQUIRED_INVARIANT_SET", "S3", "BINDING_ABSENT"),
    (31, "PLAN_RENDER_CLASSIFICATION_MISMATCH", "S3", "BINDING_ABSENT"),
    (32, "RENDER_TASK_CORRESPONDENCE_NOT_DECIDED", "S4", "AUTHORITY_ABSENT"),
    (33, "REGISTRY_AUTHORITY_CLASS_NOT_ADMITTED", "S2", "AUTHORITY_ABSENT"),
    (36, "RENDER_EVIDENCE_NOT_INDEPENDENTLY_VERIFIED", "S4", "AUTHORITY_ABSENT"),
    (37, "RENDER_JOB_TWIN_MISMATCH", "S4", "AUTHORITY_ABSENT"),
    (38, "DEFINITION_SHAPE_INVALID", "S2", "AUTHORITY_ABSENT"),
    (39, "EXPECTATION_CONTENT_CONTRADICTORY", "S3", "BINDING_ABSENT"),
    (40, "INCOMPLETE_REQUIRED_INVARIANT_SET", "S3", "BINDING_ABSENT"),
    (41, "EXTRA_PLAN_VERIFICATION_REQUIREMENT", "S3", "BINDING_ABSENT"),
    (42, "REQUEST_DIGEST_AGREEMENT_NOT_ESTABLISHED", "S4", "AUTHORITY_ABSENT"),
    (43, "SEQUENCE_AGREEMENT_NOT_ESTABLISHED", "S4", "AUTHORITY_ABSENT"),
    (44, "RENDER_EVIDENCE_MISSING", "S4", "AUTHORITY_ABSENT"),
)

#: Identifiers 34 and 35 are retired (Part VI) and MUST NOT appear anywhere.
RETIRED_ROW_IDS = frozenset({34, 35})

_ROW_BY_ID: Mapping[int, Tuple[str, str, str]] = MappingProxyType(
    {row_id: (token, stage, reason_class) for row_id, token, stage, reason_class in PART_XV_ROWS}
)


def failure_token(row_id: int) -> str:
    """The single token of a Part XV row (XIV.7.1; unknown or retired identifiers fail closed)."""
    if row_id in RETIRED_ROW_IDS or row_id not in _ROW_BY_ID:
        raise M126ContractError(f"undeclared Part XV row identifier: {row_id!r}")
    token, _stage, _cls = _ROW_BY_ID[row_id]
    return token


def classify_failure_row(row_id: int) -> Tuple[str, str]:
    """``(stage, reason_class)`` for a Part XV row identifier.

    Sole row-keyed classifier (XIV.7.1): total over the declared identifiers, fail-closed for anything else,
    including the retired identifiers 34/35. No code-keyed mapping exists.
    """
    if row_id in RETIRED_ROW_IDS or row_id not in _ROW_BY_ID:
        raise M126ContractError(f"undeclared Part XV row identifier: {row_id!r}")
    token, stage, reason_class = _ROW_BY_ID[row_id]
    return stage, reason_class


def row_census() -> Tuple[int, int]:
    """``(row count, distinct token count)`` — the declared census (42 rows / 35 tokens)."""
    return len(PART_XV_ROWS), len({row[1] for row in PART_XV_ROWS})


def emittable_tokens() -> frozenset:
    return frozenset(row[1] for row in PART_XV_ROWS)


def assert_stage_class_homogeneity() -> None:
    """XIV.3.1 clause 2: every stage is reason-class homogeneous; one token per row."""
    per_stage: Dict[str, set] = {}
    for row_id, token, stage, reason_class in PART_XV_ROWS:
        if row_id in RETIRED_ROW_IDS:
            raise M126ContractError("a retired identifier is declared in the matrix")
        per_stage.setdefault(stage, set()).add(reason_class)
    for stage, classes in per_stage.items():
        if stage and len(classes) > 1:
            raise M126ContractError(f"stage {stage} is not reason-class homogeneous: {sorted(classes)}")


def stage_reason_class(stage: str) -> str:
    """The single reason class of a stage (XIV.3.1 clause 2), computed from the matrix itself."""
    classes = {row[3] for row in PART_XV_ROWS if row[2] == stage}
    if len(classes) != 1:
        raise M126ContractError(f"stage {stage} has no single reason class: {sorted(classes)}")
    return classes.pop()


@dataclass(frozen=True)
class DecisiveOutcome:
    """The decisive outcome of XIV.3.1: first failing stage, primary row, primary code, aggregated codes."""

    stage: Optional[str]
    primary_row: Optional[int]
    primary_code: Optional[str]
    failure_codes: Tuple[str, ...]
    reason_class: str

    @property
    def deciding_stage(self) -> Optional[str]:
        return None if self.reason_class == "INTERNAL_FAILURE" else self.stage


def decisive_outcome(applicable_rows: Sequence[int]) -> DecisiveOutcome:
    """XIV.3.1 clauses 1-3 over a set of applicable Part XV row identifiers."""
    rows = sorted(set(applicable_rows))
    if not rows:
        raise M126ContractError("a decisive outcome requires at least one applicable row")
    for row_id in rows:
        classify_failure_row(row_id)  # fail-closed for undeclared/retired identifiers
    stages = [classify_failure_row(row_id)[0] for row_id in rows]
    first_stage = min((stage for stage in stages if stage), key=STAGES.index)
    in_stage = [row_id for row_id in rows if classify_failure_row(row_id)[0] == first_stage]
    primary_row = min(in_stage)
    codes = tuple(sorted({failure_token(row_id) for row_id in in_stage}))
    return DecisiveOutcome(
        stage=first_stage,
        primary_row=primary_row,
        primary_code=failure_token(primary_row),
        failure_codes=codes,
        reason_class=stage_reason_class(first_stage),
    )


def internal_fault_outcome() -> DecisiveOutcome:
    """Row 2: the representable internal fault (not stage-attributable)."""
    return DecisiveOutcome(
        stage=None,
        primary_row=2,
        primary_code=failure_token(2),
        failure_codes=(failure_token(2),),
        reason_class="INTERNAL_FAILURE",
    )


def map_states(stage: Optional[str], reason_class: str) -> Tuple[str, str]:
    """``(semantic_state, overall_state)`` from the mapping of XIV.3 (the only derivation that exists)."""
    if reason_class == "INTERNAL_FAILURE":
        return "UNKNOWN", "UNKNOWN"
    if reason_class in {"BINDING_ABSENT", "AUTHORITY_ABSENT"}:
        return "NOT_ESTABLISHED", "NOT_ESTABLISHED"
    if reason_class == "EVIDENCE_INSUFFICIENT":
        return "UNKNOWN", "UNKNOWN"
    if reason_class == "SATISFIED":
        return "SATISFIED", "SATISFIED"
    if reason_class == "EVALUATED_MISMATCH":
        return "NOT_SATISFIED", "NOT_SATISFIED"
    raise M126ContractError(f"no state mapping exists for reason class {reason_class!r}")


# XV row 22 is aggregate-only in R2-A but MUST NOT be claimed as unreachable: V.4.9 ships the lookup and the
# refusal token against an empty reviewed table, and the S4 aggregate reports it.

# --------------------------------------------------------------------------- Domain A (XI.1) and the recipes

def _domain_a_bytes(value: Any) -> bytes:
    """Domain A canonical bytes (XI.1): ``unreal_state_extraction.jcs`` only, no third implementation."""
    return jcs.canonicalize(value).encode("utf-8")


def domain_a_digest(value: Any) -> str:
    return hashlib.sha256(_domain_a_bytes(value)).hexdigest()


def compute_plan_content_digest(plan: UnrealExecutionPlan) -> str:
    """X.2: the full canonical plan document through M12.3's Domain-B canonicalizer (one call site)."""
    return _canonical_sha256(plan.to_json_compatible(), "execution_plan")


def compute_evidence_identity(entry: "InvariantVerificationResult") -> str:
    """XIV.4.3: the closed 16-member evidence-identity recipe (Domain A)."""
    return domain_a_digest({
        "schema": EVIDENCE_SCHEMA_CONSTANT,
        "invariant_name": entry.invariant_name,
        "definition_id": entry.definition_id,
        "definition_revision": entry.definition_revision,
        "definition_digest": entry.definition_digest,
        "authority_class": entry.authority_class,
        "comparison": entry.comparison,
        "admissible_value_type": entry.admissible_value_type,
        "subject_scope": None if entry.subject_scope is None else list(entry.subject_scope),
        "observed_path_patterns": None if entry.observed_path_patterns is None else list(entry.observed_path_patterns),
        "value_state": entry.value_state,
        "resolved_observables": [
            {"concrete_path": item.concrete_path, "value": item.value} for item in entry.resolved_observables
        ],
        "observation_bound": entry.observation_bound,
        "observation_request_id": None if entry.observation_identity is None else entry.observation_identity["request_identity"],
        "observation_scope": None if entry.observation_identity is None else list(entry.observation_identity["scope_entity_ids"]),
        "canonical_state_digest": None if entry.observation_identity is None else entry.observation_identity["canonical_state_digest"],
    })


def compute_invariant_result_digest(entry: "InvariantVerificationResult") -> str:
    """XIV.4.4: the entry's full declared member set minus ``invariant_result_digest`` (Domain A)."""
    return domain_a_digest(entry.canonical_input())


# --------------------------------------------------------------------------- closed tables (Part VIII)

@dataclass(frozen=True)
class EntryVocabulary:
    entry_name: str
    entry_version: int
    task_class: str
    fragment_ids: Tuple[str, ...]
    invariant_names: Tuple[str, ...]
    parameter_names: Tuple[str, ...]
    parameter_kinds: Tuple[Tuple[str, str], ...]

    def projection(self) -> Dict[str, Any]:
        return {
            "schema": VOCABULARY_ENTRY_SCHEMA,
            "entry_name": self.entry_name,
            "entry_version": self.entry_version,
            "task_class": self.task_class,
            "fragment_ids": list(self.fragment_ids),
            "invariant_names": list(self.invariant_names),
            "parameter_names": list(self.parameter_names),
            "parameter_kinds": {name: kind for name, kind in self.parameter_kinds},
        }

    @property
    def vocabulary_digest(self) -> str:
        return domain_a_digest(self.projection())


@dataclass(frozen=True)
class SemanticInvariantDefinition:
    """VIII.2 definition schema. R2-A ships the schema with no entry (every definition is ``DEFERRED``)."""

    invariant_name: str
    definition_revision: int
    definition_status: str
    authority_class: str
    observable_paths: Tuple[str, ...]
    subject_scope: Tuple[str, ...]
    comparison: str
    admissible_value_type: str
    expected_value_source: str
    expected_value: Any
    target_binding: str
    missing_behavior: str
    unsupported_behavior: str
    witness_positive: Optional[Tuple[str, str, Optional[str], str]]
    witness_negative: Optional[Tuple[str, str, Optional[str], str]]
    witness_lossy: Optional[Tuple[str, str, Optional[str], str]]
    non_claim: str


@dataclass(frozen=True)
class ProductionTargetSpec:
    production_target_id: str
    target_revision: int
    world_package_path: str
    persistent_level_package_path: str
    required_entity_ids: Tuple[str, ...]
    required_entity_classes: Tuple[Tuple[str, str], ...]
    planned_sequence_asset_path: Optional[str]
    source_reference: str
    non_claim: str

    def projection(self) -> Dict[str, Any]:
        return {
            "schema": TARGET_SCHEMA,
            "production_target_id": self.production_target_id,
            "target_revision": self.target_revision,
            "world_package_path": self.world_package_path,
            "persistent_level_package_path": self.persistent_level_package_path,
            "required_entity_ids": list(self.required_entity_ids),
            "required_entity_classes": [list(pair) for pair in self.required_entity_classes],
            "planned_sequence_asset_path": self.planned_sequence_asset_path,
            "source_reference": self.source_reference,
            "non_claim": self.non_claim,
        }

    @property
    def target_digest(self) -> str:
        return domain_a_digest(self.projection())

    def declared_members(self) -> Dict[str, Any]:
        members = dict(self.projection())
        members.pop("schema")
        members["target_digest"] = self.target_digest
        return members


@dataclass(frozen=True)
class TaskTargetMapping:
    entry_name: str
    entry_version: int
    task_class: str
    production_target_id: str

    def declared_members(self) -> Dict[str, Any]:
        return {
            "entry_name": self.entry_name,
            "entry_version": self.entry_version,
            "task_class": self.task_class,
            "production_target_id": self.production_target_id,
        }


def _build_vocabulary() -> Tuple[EntryVocabulary, ...]:
    catalog = UnrealSoccerProductionCatalog()
    fragments = {f.canonical_id: f for f in CANONICAL_UNREAL_FRAGMENTS}
    entries = []
    for name in catalog.available_task_names():
        for version in sorted({e.version for e in catalog._by_name.get(name, ())}):
            spec = catalog.get_entry(name, version=version)
            invariants = tuple(sorted({
                inv
                for fragment_id in spec.fragment_ids
                for inv in fragments[fragment_id].contributed_invariant_names()
            }))
            entries.append(EntryVocabulary(
                entry_name=spec.name,
                entry_version=spec.version,
                task_class=spec.task_class,
                fragment_ids=tuple(spec.fragment_ids),
                invariant_names=invariants,
                parameter_names=tuple(spec.required_parameters),
                parameter_kinds=tuple(spec.parameter_kinds),
            ))
    return tuple(sorted(entries, key=lambda e: (e.entry_name, e.entry_version)))


EXPECTATION_VOCABULARY: Tuple[EntryVocabulary, ...] = _build_vocabulary()
SEMANTIC_INVARIANT_DEFINITIONS: Tuple[SemanticInvariantDefinition, ...] = ()
PRODUCTION_TARGETS: Tuple[ProductionTargetSpec, ...] = ()
PRODUCTION_TARGET_BY_TASK: Tuple[TaskTargetMapping, ...] = ()
REGISTERED_COUNT = sum(1 for d in SEMANTIC_INVARIANT_DEFINITIONS if d.definition_status == "REGISTERED")


def _definition_members(definition: SemanticInvariantDefinition) -> Dict[str, Any]:
    return {
        "invariant_name": definition.invariant_name,
        "definition_revision": definition.definition_revision,
        "definition_status": definition.definition_status,
        "authority_class": definition.authority_class,
        "observable_paths": list(definition.observable_paths),
        "subject_scope": list(definition.subject_scope),
        "comparison": definition.comparison,
        "admissible_value_type": definition.admissible_value_type,
        "expected_value_source": definition.expected_value_source,
        "expected_value": definition.expected_value,
        "target_binding": definition.target_binding,
        "missing_behavior": definition.missing_behavior,
        "unsupported_behavior": definition.unsupported_behavior,
        "witness_positive": None if definition.witness_positive is None else list(definition.witness_positive),
        "witness_negative": None if definition.witness_negative is None else list(definition.witness_negative),
        "witness_lossy": None if definition.witness_lossy is None else list(definition.witness_lossy),
        "non_claim": definition.non_claim,
    }


def definition_digest(definition: SemanticInvariantDefinition) -> str:
    """XI.4: ``{schema, P_def}`` — the declared member set minus ``definition_digest`` (no self-hash)."""
    return domain_a_digest({"schema": DEFINITION_SCHEMA, **_definition_members(definition)})


def _registry_projection(
    definitions: Sequence[SemanticInvariantDefinition] = SEMANTIC_INVARIANT_DEFINITIONS,
    vocabulary: Sequence[EntryVocabulary] = EXPECTATION_VOCABULARY,
    targets: Sequence[ProductionTargetSpec] = PRODUCTION_TARGETS,
    mappings: Sequence[TaskTargetMapping] = PRODUCTION_TARGET_BY_TASK,
) -> Dict[str, Any]:
    return {
        "schema": REGISTRY_SCHEMA,
        "vocabulary": [
            {**entry.projection(), "schema": None, "vocabulary_digest": entry.vocabulary_digest}
            for entry in sorted(vocabulary, key=lambda e: (e.entry_name, e.entry_version))
        ],
        "definitions": [
            {**_definition_members(d), "definition_digest": definition_digest(d)}
            for d in sorted(definitions, key=lambda d: d.invariant_name)
        ],
        "mappings": [
            m.declared_members()
            for m in sorted(mappings, key=lambda m: (m.entry_name, m.entry_version, m.task_class))
        ],
        "targets": [
            t.declared_members() for t in sorted(targets, key=lambda t: t.production_target_id)
        ],
        "registered_count": sum(1 for d in definitions if d.definition_status == "REGISTERED"),
    }


def _strip_projection_schema(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: _strip_projection_schema(v) for k, v in value.items() if not (k == "schema" and v is None)}
    if isinstance(value, list):
        return [_strip_projection_schema(v) for v in value]
    return value


def registry_digest(
    definitions: Sequence[SemanticInvariantDefinition] = SEMANTIC_INVARIANT_DEFINITIONS,
    vocabulary: Sequence[EntryVocabulary] = EXPECTATION_VOCABULARY,
    targets: Sequence[ProductionTargetSpec] = PRODUCTION_TARGETS,
    mappings: Sequence[TaskTargetMapping] = PRODUCTION_TARGET_BY_TASK,
) -> str:
    """XI.4 ``registry_digest`` over ``P_reg`` (VIII.2)."""
    return domain_a_digest(_strip_projection_schema(
        _registry_projection(definitions, vocabulary, targets, mappings)
    ))


def target_table_digest(targets: Sequence[ProductionTargetSpec] = PRODUCTION_TARGETS) -> str:
    """XI.4 ``target_table_digest``: ``{schema, targets:[...including target_digest...]}``."""
    return domain_a_digest({
        "schema": TARGET_TABLE_SCHEMA,
        "targets": [t.declared_members() for t in sorted(targets, key=lambda t: t.production_target_id)],
    })


#: Reviewed constants, recomputed from the same objects the consumers read (VIII.3 condition 3/5).
REGISTRY_SOURCE_DIGEST = registry_digest()
TARGET_TABLE_DIGEST = target_table_digest()


def revalidate_authority(
    definitions: Sequence[SemanticInvariantDefinition] = SEMANTIC_INVARIANT_DEFINITIONS,
    targets: Sequence[ProductionTargetSpec] = PRODUCTION_TARGETS,
    mappings: Sequence[TaskTargetMapping] = PRODUCTION_TARGET_BY_TASK,
) -> Optional[int]:
    """VIII.3/V.5: in-call revalidation; returns the applicable S2 row identifier or ``None``."""
    seen_names = set()
    for definition in definitions:
        if definition.definition_status == "REGISTERED" and definition.invariant_name in seen_names:
            return 11
        seen_names.add(definition.invariant_name)
        if definition.authority_class not in {"CODE_CONSTANT"}:
            return 33
        if (
            not definition.observable_paths
            or not definition.subject_scope
            or list(definition.observable_paths) != sorted(set(definition.observable_paths))
            or list(definition.subject_scope) != sorted(set(definition.subject_scope))
        ):
            return 38
    for mapping in mappings:
        if mapping.production_target_id not in {t.production_target_id for t in targets}:
            return 10
    seen_triples = set()
    for mapping in mappings:
        triple = (mapping.entry_name, mapping.entry_version, mapping.task_class)
        if triple in seen_triples:
            return 12
        seen_triples.add(triple)
    if registry_digest(definitions, EXPECTATION_VOCABULARY, targets, mappings) != REGISTRY_SOURCE_DIGEST:
        return 9
    if target_table_digest(targets) != TARGET_TABLE_DIGEST:
        return 10
    return None


def registry_revision() -> int:
    return REGISTRY_REVISION


def target_table_revision() -> int:
    return TARGET_TABLE_REVISION


def production_target_status() -> Mapping[str, Any]:
    """V.6: the reviewed target table is empty in R2-A, so no target value exists."""
    return MappingProxyType({
        "table_entries": len(PRODUCTION_TARGETS),
        "mappings": len(PRODUCTION_TARGET_BY_TASK),
        "target_table_digest": TARGET_TABLE_DIGEST,
        "authoritative_reviewed_target_artifact": False,
    })


# --------------------------------------------------------------------------- VII.4 bounded structural preflight

CATEGORY_ORDER: Tuple[str, ...] = ("F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9")


@dataclass(frozen=True)
class StructuralRefusal:
    """A preflight refusal: one F category, carried by row 1 (task/plan) or row 28 (expectation value content)."""

    category: str
    row: int

    def __post_init__(self) -> None:
        if self.category not in CATEGORY_ORDER:
            raise M126ContractError(f"undeclared F category: {self.category!r}")
        if self.row not in (1, 28):
            raise M126ContractError("a structural refusal is carried by row 1 or row 28 only")


def _is_lone_surrogate(value: str) -> bool:
    try:
        value.encode("utf-8")
        return False
    except UnicodeEncodeError:
        return True


def _int_to_decimal_ok(value: int) -> bool:
    try:
        str(value)
        return True
    except (ValueError, MemoryError):
        return False


def _walk(value: Any, stats: Dict[str, Any], depth: int = 0, expectation_side: bool = False) -> Optional[str]:
    """One uniform, name-blind, value-neutral traversal (VII.4.2). Returns the first category found."""
    stats["nodes"] += 1
    if stats["nodes"] > PREFLIGHT_NODE_BUDGET:
        return "F6"
    if depth > PREFLIGHT_DEPTH_LIMIT:
        return "F6"
    if id(value) in stats["path"] and isinstance(value, (dict, list, tuple)):
        return "F6"  # a cycle caught by the bound (VII.4.2)
    if isinstance(value, (dict, list, tuple)):
        stats["path"].add(id(value))
        try:
            if isinstance(value, Mapping):
                for key, item in value.items():
                    if not isinstance(key, str):
                        return "F4"
                    found = _walk(key, stats, depth + 1, expectation_side) or _walk(
                        item, stats, depth + 1, expectation_side)
                    if found:
                        return found
            else:
                for item in value:
                    found = _walk(item, stats, depth + 1, expectation_side)
                    if found:
                        return found
        finally:
            stats["path"].discard(id(value))
        return None
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        return "F7" if _is_lone_surrogate(value) else None
    if isinstance(value, int):
        return None if _int_to_decimal_ok(value) else "F8"
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return "F5"
        # Domain A refuses floats (XI.1) -> an expectation-side float is a value-content structural failure
        # (XIV.5). Domain B accepts floats by declaration (XI.2), so a task/plan float passes the preflight and
        # is refused later by the single float-policy condition of X.3 (row 29).
        return "F4" if expectation_side else None
    return "F4"


def preflight_document(document: Any, *, expectation_side: bool = False) -> Optional[StructuralRefusal]:
    """F1-F9 over one supplied document (VII.4.1); the lowest-numbered applicable category wins."""
    row = 28 if expectation_side else 1
    if not isinstance(document, Mapping):
        return StructuralRefusal("F1", row)
    found = []
    try:
        for category, present in (
            ("F4", None),
            ("F5", None),
            ("F6", None),
            ("F7", None),
            ("F8", None),
        ):
            pass
        stats = {"nodes": 0, "path": set()}
        observed = _walk(document, stats, 0, expectation_side)
        if observed:
            found.append(observed)
    except Exception:
        # any exception raised while inspecting supplied content is attributed to the supplied input (VII.4.2)
        found.append("F4")
    if not found:
        return None
    return StructuralRefusal(min(found, key=CATEGORY_ORDER.index), row)


def plan_contains_float(document: Any) -> bool:
    """X.3: a structurally valid plan document whose Domain-B projection contains a float."""
    stack = [document]
    while stack:
        node = stack.pop()
        if isinstance(node, float):
            return True
        if isinstance(node, Mapping):
            stack.extend(node.values())
        elif isinstance(node, (list, tuple)):
            stack.extend(node)
    return False


# --------------------------------------------------------------------------- Part IX expectation schema

#: The Part IX declared member set (23 members), used for closed-schema classification only.
EXPECTATION_MEMBERS: Tuple[str, ...] = (
    "expectation_contract_revision",
    "resolver_revision",
    "registry_revision",
    "registry_digest",
    "target_table_revision",
    "target_table_digest",
    "production_target_id",
    "target_revision",
    "target_digest",
    "task_identity",
    "task_version",
    "digital_twin_id",
    "catalog_entry_name",
    "catalog_entry_version",
    "vocabulary_digest",
    "source_content_digest",
    "plan_id",
    "plan_content_digest",
    "render_task",
    "required_invariant_names",
    "invariant_expectations",
    "origin_status",
    "expectation_digest",
)

#: The three target members are declared non-nullable for an admitted expectation (Part IX).
TARGET_MEMBERS: Tuple[str, ...] = ("production_target_id", "target_revision", "target_digest")

_CLOSED_VOCAB = {
    "comparison": {"EQUALS", "SET_EQUALS", "CONTAINS_ALL", "EXACTLY_ONE", "SUBSET_OF"},
    "admissible_value_type": {"STR", "INT", "BOOL", "STR_SET"},
    "target_binding": {"PRODUCTION_TARGET", "NONE"},
    "expected_value_source": {"TARGET_FIELD", "CODE_CONSTANT"},
    "definition_status": {"REGISTERED", "DEFERRED"},
    "authority_class": {"CODE_CONSTANT"},
}


def compute_expectation_digest(claim: Mapping[str, Any]) -> str:
    """XI.4 ``expectation_digest``: the declared Part IX member set minus ``expectation_digest`` (Domain A)."""
    members = {name: claim[name] for name in EXPECTATION_MEMBERS if name != "expectation_digest"}
    return domain_a_digest(members)


_EXPECTATION_TYPE_MAP = {
    "expectation_contract_revision": "str",
    "resolver_revision": "str",
    "registry_revision": "int",
    "registry_digest": "hex",
    "target_table_revision": "int",
    "target_table_digest": "hex",
    "production_target_id": "str",
    "target_revision": "int",
    "target_digest": "hex",
    "task_identity": "str",
    "task_version": "int",
    "digital_twin_id": "str",
    "catalog_entry_name": "str",
    "catalog_entry_version": "int",
    "vocabulary_digest": "hex",
    "source_content_digest": "hex",
    "plan_id": "str",
    "plan_content_digest": "hex",
    "render_task": "bool",
    "required_invariant_names": "str_sequence",
    "invariant_expectations": "sequence",
    "origin_status": "str",
    "expectation_digest": "hex",
}

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _declared_member_type_errors(claim: Mapping[str, Any]) -> Dict[str, str]:
    """Part IX declared member types: a wrong-typed declared member is a closed-schema violation (row 5)."""
    errors: Dict[str, str] = {}
    for member, kind in _EXPECTATION_TYPE_MAP.items():
        if member not in claim:
            continue
        value = claim[member]
        if kind == "str":
            ok = isinstance(value, str)
        elif kind == "int":
            ok = isinstance(value, int) and not isinstance(value, bool)
        elif kind == "bool":
            ok = isinstance(value, bool)
        elif kind == "hex":
            ok = isinstance(value, str) and bool(_HEX64.match(value))
        elif kind == "str_sequence":
            ok = isinstance(value, (list, tuple)) and all(isinstance(v, str) for v in value)
        else:  # sequence of entries
            ok = isinstance(value, (list, tuple)) and all(isinstance(v, Mapping) for v in value)
        if not ok:
            errors[member] = type(value).__name__
    return errors


@dataclass(frozen=True)
class ExpectationClassification:
    """The verifier-owned classification of a supplied expectation object (untrusted input)."""

    rows: frozenset
    schema_valid: bool
    target_members_null: bool
    detail: Mapping[str, Any]

    @property
    def admissible(self) -> bool:
        """No expectation is admissible in R2-A (Part IX no-expectation rule)."""
        return False


def classify_supplied_expectation(
    claim: Any,
    *,
    task: Optional[UnrealProductionTaskDefinition] = None,
    plan: Optional[UnrealExecutionPlan] = None,
) -> ExpectationClassification:
    """Part IX rejection rules over a supplied object, as the verifier's S1/S3 classification.

    A supplied object is never admitted in R2-A (Part IX's R2-A no-expectation rule); it is classified only.
    """
    if not isinstance(claim, Mapping):
        return ExpectationClassification(frozenset({5}), False, False, {"reason": "not-a-mapping"})

    structural = preflight_document(claim, expectation_side=True)
    if structural is not None:
        return ExpectationClassification(frozenset({structural.row}), False, False,
                                        {"category": structural.category})

    rows = set()
    detail: Dict[str, Any] = {}
    keys = set(claim)
    missing = [name for name in EXPECTATION_MEMBERS if name not in keys]
    undeclared = sorted(keys - set(EXPECTATION_MEMBERS))
    null_targets = sorted(name for name in TARGET_MEMBERS if claim.get(name, None) is None and name in keys)
    if missing or undeclared:
        rows.add(5)
        detail["incomplete"] = {"missing": missing, "undeclared": undeclared}
    if null_targets:
        # A declared non-nullable member supplied as null is a presence violation; row 5 is its only row and
        # rows 4/7 are not additionally applicable (Part IX exclusivity).
        rows.add(5)
        detail["null_target_members"] = null_targets
    if not rows:
        wrong_types = _declared_member_type_errors(claim)
        if wrong_types:
            rows.add(5)
            detail["member_type_errors"] = wrong_types
    if not rows:
        names = claim.get("required_invariant_names")
        entries = claim.get("invariant_expectations")
        if isinstance(names, (list, tuple)) and isinstance(entries, (list, tuple)):
            if len(names) == 0:
                rows.add(30)
                detail["empty_required_set"] = True
            if len(names) != len(entries):
                rows.add(5)
                detail["count_mismatch"] = {"names": len(names), "entries": len(entries)}
            name_set = [str(n) for n in names]
            entry_names = [str(e.get("invariant_name")) for e in entries if isinstance(e, Mapping)]
            if sorted(name_set) != name_set:
                rows.add(5)
            if sorted(entry_names) != entry_names:
                rows.add(5)  # invariant_expectations must be sorted by name
            if sorted(name_set) != sorted(entry_names) and name_set:
                rows.add(5)
                detail["name_mismatch"] = True
        if claim.get("origin_status", ORIGIN_STATUS) != ORIGIN_STATUS:
            rows.add(39)
            detail["origin_status"] = claim.get("origin_status")
        for member, allowed in _CLOSED_VOCAB.items():
            if member in claim and claim[member] not in allowed:
                rows.add(39)
                detail[member] = claim[member]

    if not rows:
        # Schema-valid: identity recomputation decides. In R2-A the reviewed target table is empty, so no
        # non-null target identity can be established and no expectation is admissible -> at least one of rows
        # 4/7 applies (XXIV.1 (ii)); both carry the same token, so the committed tuple is identical.
        rows.update({4, 7})
        detail["identity"] = "not-recomputable-in-r2a"
        if "expectation_digest" in claim and compute_expectation_digest(claim) != claim["expectation_digest"]:
            rows.add(8)
            detail["digest_mismatch"] = True
        if task is not None and plan is not None:
            if claim.get("source_content_digest") not in (None, compute_source_content_digest(task)):
                rows.add(21)
            derived_plan_digest = compute_plan_content_digest(plan)
            if claim.get("plan_content_digest") not in (None, derived_plan_digest):
                rows.update({14, 21})
    return ExpectationClassification(frozenset(rows), not rows, bool(null_targets), MappingProxyType(detail))


# --------------------------------------------------------------------------- result contract (XIV.4.1 / XIV.4.5)

@dataclass(frozen=True)
class ResolvedObservable:
    concrete_path: str
    value: Any


@dataclass(frozen=True)
class InvariantVerificationResult:
    """XIV.4.1 — the closed 19-member entry schema."""

    schema: str
    invariant_name: str
    definition_id: Optional[str]
    definition_revision: Optional[int]
    definition_digest: Optional[str]
    authority_class: Optional[str]
    subject_scope: Optional[Tuple[str, ...]]
    expected_value_identity: Optional[str]
    comparison: Optional[str]
    admissible_value_type: Optional[str]
    observed_path_patterns: Optional[Tuple[str, ...]]
    value_state: str
    resolved_observables: Tuple[ResolvedObservable, ...]
    observation_bound: bool
    observation_identity: Optional[Mapping[str, Any]]
    invariant_state: str
    mismatch_reason: Optional[str]
    evidence_identity: str
    invariant_result_digest: str

    def __init_subclass__(cls, **kwargs: Any) -> None:
        raise TypeError("InvariantVerificationResult is sealed")

    def __post_init__(self) -> None:
        if self.schema != ENTRY_SCHEMA_CONSTANT:
            raise M126ContractError("entry schema constant mismatch")
        if self.value_state not in {"PRESENT", "PRESENT_NULL", "ABSENT"}:
            raise M126ContractError("invalid value_state")
        if self.invariant_state not in {"SATISFIED", "NOT_SATISFIED", "UNKNOWN", "MISSING"}:
            raise M126ContractError("invalid invariant_state")
        if self.value_state == "ABSENT" and self.resolved_observables:
            raise M126ContractError("value_state ABSENT requires an empty resolved_observables tuple")
        if self.value_state != "ABSENT" and not self.resolved_observables:
            raise M126ContractError("value_state other than ABSENT requires a non-empty resolved_observables tuple")
        if self.observation_bound != (self.observation_identity is not None):
            raise M126ContractError("observation_identity is null iff observation_bound is false")
        if not isinstance(self.mismatch_reason, type(None)) and self.mismatch_reason is not None:
            raise M126ContractError("mismatch_reason MUST be null under this revision (XIV.4.7)")

    def canonical_input(self) -> Dict[str, Any]:
        """The entry's declared member set minus ``invariant_result_digest`` (XIV.4.4)."""
        return {
            "schema": self.schema,
            "invariant_name": self.invariant_name,
            "definition_id": self.definition_id,
            "definition_revision": self.definition_revision,
            "definition_digest": self.definition_digest,
            "authority_class": self.authority_class,
            "subject_scope": None if self.subject_scope is None else list(self.subject_scope),
            "expected_value_identity": self.expected_value_identity,
            "comparison": self.comparison,
            "admissible_value_type": self.admissible_value_type,
            "observed_path_patterns": None if self.observed_path_patterns is None else list(self.observed_path_patterns),
            "value_state": self.value_state,
            "resolved_observables": [
                {"concrete_path": item.concrete_path, "value": item.value} for item in self.resolved_observables
            ],
            "observation_bound": self.observation_bound,
            "observation_identity": None if self.observation_identity is None else dict(self.observation_identity),
            "invariant_state": self.invariant_state,
            "mismatch_reason": self.mismatch_reason,
            "evidence_identity": self.evidence_identity,
        }

    @property
    def resolved(self) -> bool:
        return self.definition_id is not None


def unresolved_entry(invariant_name: str) -> InvariantVerificationResult:
    """XIV.4.1's unresolved entry form — the only entry form R2-A can produce (no definition is REGISTERED)."""
    placeholder = InvariantVerificationResult(
        schema=ENTRY_SCHEMA_CONSTANT,
        invariant_name=invariant_name,
        definition_id=None,
        definition_revision=None,
        definition_digest=None,
        authority_class=None,
        subject_scope=None,
        expected_value_identity=None,
        comparison=None,
        admissible_value_type=None,
        observed_path_patterns=None,
        value_state="ABSENT",
        resolved_observables=(),
        observation_bound=False,
        observation_identity=None,
        invariant_state="UNKNOWN",
        mismatch_reason=None,
        evidence_identity="",
        invariant_result_digest="",
    )
    evidence = compute_evidence_identity(placeholder)
    complete = InvariantVerificationResult(
        **{**{f: getattr(placeholder, f) for f in placeholder.__dataclass_fields__},
           "evidence_identity": evidence,
           "invariant_result_digest": ""}
    )
    digest = compute_invariant_result_digest(complete)
    return InvariantVerificationResult(
        **{**{f: getattr(complete, f) for f in complete.__dataclass_fields__},
           "invariant_result_digest": digest}
    )


RESULT_MEMBERS: Tuple[str, ...] = (
    "schema", "verifier_revision", "expectation_contract_revision", "resolver_revision",
    "registry_revision", "registry_digest", "target_table_revision", "target_table_digest",
    "production_target_id", "target_revision", "target_digest",
    "task_identity", "task_version", "digital_twin_id", "catalog_entry_name", "catalog_entry_version",
    "vocabulary_digest", "plan_id", "source_content_digest", "plan_content_digest", "render_task",
    "required_invariant_names", "expectation_identity", "expectation_digest",
    "observation_identity", "observation_digests", "render_job_identity", "render_attempt_identity",
    "render_evidence_identity", "evidence_trust_basis", "invariant_results",
    "semantic_state", "render_state", "overall_state", "outcome_reason_class", "failure_codes",
    "origin_status", "deciding_stage", "primary_failure_code",
)

R2A_UNREACHABLE_STATES = {
    "semantic_state": {"SATISFIED", "NOT_SATISFIED"},
    "overall_state": {"SATISFIED", "NOT_SATISFIED"},
    "invariant_state": {"SATISFIED", "NOT_SATISFIED", "MISSING"},
    "outcome_reason_class": {"SATISFIED", "EVALUATED_MISMATCH", "EVIDENCE_INSUFFICIENT"},
    "deciding_stage": {"S5", "S6"},
    "render_state": {"VERIFIED"},
}

R2A_UNREACHABLE_TOKENS = frozenset(
    # Tokens that appear ONLY on S5 rows. A token is a row VALUE, not a key: `EXPECTED_VALUE_UNAVAILABLE` is
    # carried by rows 3/6 (S4) and 23/25 (S5) and is disambiguated by the deciding stage (XIV.3), so the
    # stage-level check below — not the token set — is what forbids an S5 decision in R2-A.
    token for token in {row[1] for row in PART_XV_ROWS}
    if all(row[2] == "S5" for row in PART_XV_ROWS if row[1] == token)
)


@dataclass(frozen=True)
class M126Result:
    """The closed 39-member M12.6 result (XIV.4.5) plus its derived ``result_digest``."""

    members: Mapping[str, Any]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        raise TypeError("M126Result is sealed")

    def __post_init__(self) -> None:
        missing = [name for name in RESULT_MEMBERS if name not in self.members]
        extra = sorted(set(self.members) - set(RESULT_MEMBERS))
        if missing or extra:
            raise M126ContractError(f"result member set mismatch: missing={missing} extra={extra}")
        object.__setattr__(self, "members", MappingProxyType(dict(self.members)))
        self._validate_coherence()
        validate_r2a_conformance(self.members)

    def _validate_coherence(self) -> None:
        """XIV.2/XIV.4.5 structural coherence, evaluated at construction."""
        m = self.members
        if m["schema"] != RESULT_SCHEMA_CONSTANT or m["verifier_revision"] != VERIFIER_REVISION:
            raise M126ContractError("result schema/verifier constant mismatch")
        if m["expectation_contract_revision"] != EXPECTATION_CONTRACT_REVISION:
            raise M126ContractError("expectation contract revision mismatch")
        if m["resolver_revision"] != RESOLVER_REVISION:
            raise M126ContractError("resolver revision mismatch")
        if m["origin_status"] != ORIGIN_STATUS:
            raise M126ContractError("origin_status is the fixed constant")
        triplet = [m["production_target_id"], m["target_revision"], m["target_digest"]]
        if any(value is not None for value in triplet) and any(value is None for value in triplet):
            raise M126ContractError("the target triple is simultaneously non-null or null")
        if m["deciding_stage"] is None and m["outcome_reason_class"] != "INTERNAL_FAILURE":
            raise M126ContractError("deciding_stage is null only for SATISFIED or a row-2 fault")
        codes = tuple(m["failure_codes"])
        if list(codes) != sorted(set(codes)):
            raise M126ContractError("failure_codes must be sorted and unique")
        if not set(codes) <= emittable_tokens():
            raise M126ContractError("failure_codes contains a token outside Part XV")
        if m["primary_failure_code"] is None and codes:
            raise M126ContractError("primary_failure_code is null while failure_codes is non-empty")
        if m["primary_failure_code"] is not None and m["primary_failure_code"] not in codes:
            raise M126ContractError("primary_failure_code must be a member of failure_codes")
        entries = tuple(m["invariant_results"])
        if len(entries) != len(m["required_invariant_names"]):
            raise M126ContractError("one entry per required name (XIV.4.1.1)")
        if [e.invariant_name for e in entries] != list(m["required_invariant_names"]):
            raise M126ContractError("entries are in canonical order and preserve every required name")
        if m["render_task"] is None and m["render_state"] != "NOT_DECIDED":
            raise M126ContractError("render_task null requires render_state NOT_DECIDED")
        if m["render_task"] is False and m["render_state"] != "NOT_REQUIRED":
            raise M126ContractError("a non-render task is NOT_REQUIRED")
        if (m["expectation_identity"] is None) != (m["expectation_digest"] is None):
            raise M126ContractError("expectation_identity/expectation_digest move as a pair")
        if m["expectation_identity"] is not None and m["deciding_stage"] not in {"S4", "S5", "S6"}:
            raise M126ContractError("an expectation identity is established only on an S4/S5/S6 outcome")

    def canonical_dict(self) -> Dict[str, Any]:
        """XIV.4.5: the closed canonical object; array members serialize as JSON arrays."""
        arrays = {"required_invariant_names", "observation_digests", "failure_codes"}
        return {
            **{name: (list(self.members[name]) if name in arrays else self.members[name])
               for name in RESULT_MEMBERS if name != "invariant_results"},
            "invariant_results": [entry.canonical_input() | {"invariant_result_digest": entry.invariant_result_digest}
                                  for entry in self.members["invariant_results"]],
        }

    @property
    def result_digest(self) -> str:
        return domain_a_digest(self.canonical_dict())

    def __getitem__(self, name: str) -> Any:
        raise M126ContractError("no mapping-style access: one declared access path per member (XIV.7.5)")


def validate_r2a_conformance(members: Mapping[str, Any]) -> None:
    """XXIV.1: no R2-B-only member may be produced by an R2-A result (fail-closed)."""
    for member, forbidden in R2A_UNREACHABLE_STATES.items():
        if member == "invariant_state":
            continue  # an entry member: validated in the entry loop below
        if members[member] in forbidden:
            raise M126ContractError(f"R2-A produced an R2-B-only {member}: {members[member]!r}")
    for code in members["failure_codes"]:
        if code in R2A_UNREACHABLE_TOKENS:
            raise M126ContractError(f"R2-A produced an S5-only token: {code!r}")
    for entry in members["invariant_results"]:
        if entry.invariant_state in R2A_UNREACHABLE_STATES["invariant_state"]:
            raise M126ContractError("R2-A produced an R2-B-only invariant_state")
        if entry.mismatch_reason is not None:
            raise M126ContractError("mismatch_reason MUST be null (XIV.4.7)")
    for key, value in members.items():
        if "INVALID_OBSERVATION" in str(value) or "MISSING_INVARIANT_INPUT" in str(value):
            raise M126ContractError("a retired token value appeared in an R2-A result")


# --------------------------------------------------------------------------- resolver (VII.1-VII.9, V.4, S1-S4)

@dataclass(frozen=True)
class Resolution:
    """The resolver's decision set: every applicable Part XV row it owns, plus the derived members."""

    applicable_rows: frozenset
    target: Optional[ProductionTargetSpec]
    selector_triple: Tuple[str, int, str]
    derived: Mapping[str, Any]


def _selector_triple(task: UnrealProductionTaskDefinition) -> Tuple[str, int, str]:
    """V.4: ``(entry_name, entry_version, task_class)`` derived from the task's closed selector."""
    return (task.canonical_task_id, task.task_version, task.task_class)


def lookup_production_target(
    triple: Tuple[str, int, str],
    mappings: Sequence[TaskTargetMapping] = PRODUCTION_TARGET_BY_TASK,
    targets: Sequence[ProductionTargetSpec] = PRODUCTION_TARGETS,
) -> Optional[ProductionTargetSpec]:
    """V.4 clause 3: single-valued partial lookup; a duplicate row refuses, a missing row resolves to ``None``."""
    matches = [m for m in mappings if (m.entry_name, m.entry_version, m.task_class) == triple]
    if len(matches) > 1:
        raise M126ContractError("PRODUCTION_TARGET_MAPPING_DUPLICATE")
    if not matches:
        return None
    for target in targets:
        if target.production_target_id == matches[0].production_target_id:
            return target
    return None


def _declared_pair_vocabulary(task: UnrealProductionTaskDefinition) -> Optional[EntryVocabulary]:
    for entry in EXPECTATION_VOCABULARY:
        if entry.entry_name == task.canonical_task_id and entry.entry_version == task.task_version:
            return entry
    return None


def _task_derived_members(task: UnrealProductionTaskDefinition) -> Dict[str, Any]:
    """P1-P6 and the plan-side of the pair: per-member establishment predicates (XIV.4.6.2)."""
    members: Dict[str, Any] = {}
    members["task_identity"] = task.canonical_task_id if isinstance(task.canonical_task_id, str) and task.canonical_task_id.strip() else None
    version = task.task_version
    members["task_version"] = version if (isinstance(version, int) and not isinstance(version, bool)
                                          and version >= 1 and abs(version) <= DOMAIN_A_INT_LIMIT) else None
    twin = task.digital_twin_id
    members["digital_twin_id"] = twin if isinstance(twin, str) and twin.strip() else None
    entry = _declared_pair_vocabulary(task)
    members["catalog_entry_name"] = task.canonical_task_id if entry is not None else None
    members["catalog_entry_version"] = task.task_version if entry is not None else None
    members["vocabulary_digest"] = entry.vocabulary_digest if entry is not None else None
    return members


def _plan_derived_members(plan: UnrealExecutionPlan) -> Dict[str, Any]:
    members: Dict[str, Any] = {}
    members["plan_id"] = plan.plan_id if isinstance(plan.plan_id, str) and plan.plan_id.strip() else None
    return members


def resolve(
    task: UnrealProductionTaskDefinition,
    plan: UnrealExecutionPlan,
    expectation: Any = None,
    *,
    render_evidence: Any = None,
) -> Resolution:
    """The resolver's S1-S4 evaluation (VII.9, XIV.7.3). R2-A produces refusals only."""
    rows = set()
    derived: Dict[str, Any] = {}

    # ---- S1: structural preflight of the supplied task/plan artifacts
    if type(task) is not UnrealProductionTaskDefinition or type(plan) is not UnrealExecutionPlan:
        rows.add(1)
        derived["preflight"] = {"category": "F1"}
    else:
        task_document = task.to_json_compatible()
        plan_document = plan.to_json_compatible()
        refusal = preflight_document(task_document)
        if refusal is not None:
            rows.add(refusal.row)
            derived["preflight"] = {"category": refusal.category}
        else:
            plan_refusal = preflight_document(plan_document)
            if plan_refusal is not None:
                rows.add(plan_refusal.row)
                derived["preflight"] = {"category": plan_refusal.category}
            elif plan_contains_float(plan_document):
                rows.add(29)  # X.3: the single float-policy condition
                derived["float_policy"] = "PLAN_CONTENT_UNSUPPORTED"

    # ---- S2: authority-table integrity (in-call revalidation of the same objects)
    if not rows:
        integrity_row = revalidate_authority()
        if integrity_row is not None:
            rows.add(integrity_row)

    members = _task_derived_members(task)
    members.update(_plan_derived_members(plan))
    triple = _selector_triple(task)

    # ---- S3: binding
    if not rows:
        if compute_source_content_digest(task) != plan.source_content_digest:
            rows.add(13)
        if plan.source_task_id != task.canonical_task_id or plan.source_task_version != task.task_version:
            rows.add(13)
        if plan.digital_twin_id != task.digital_twin_id:
            rows.add(13)
        carried_plan_digest = getattr(plan, "plan_content_digest", None)
        if carried_plan_digest is not None and carried_plan_digest != compute_plan_content_digest(plan):
            rows.add(14)

        entry = _declared_pair_vocabulary(task)
        required_names = tuple(task.target_state.to_invariant_names())
        vocabulary = frozenset(entry.invariant_names) if entry is not None else frozenset()
        if entry is None:
            rows.add(26)
        elif any(name not in vocabulary for name in required_names):
            rows.add(26)
        if entry is not None:
            members["catalog_entry_name"] = entry.entry_name
            members["catalog_entry_version"] = entry.entry_version
            members["vocabulary_digest"] = entry.vocabulary_digest

        fragment_ids = {f.canonical_id for f in CANONICAL_UNREAL_FRAGMENTS}
        if any(step.semantic_operation not in fragment_ids for step in plan.steps):
            rows.add(27)
        if not required_names:
            rows.add(30)  # task-side occurrence of row 30 (resolver-owned operand)
        if plan.render_plan != is_render_task_class(task.task_class):
            rows.add(31)
        carried = {req for step in plan.steps for req in step.verification_requirements}
        if set(required_names) - carried:
            rows.add(40)
        if carried - set(required_names):
            rows.add(41)

    # ---- S4: coverage for this input
    target: Optional[ProductionTargetSpec] = None
    if not rows:
        target = lookup_production_target(triple)
        registered = {d.invariant_name for d in SEMANTIC_INVARIANT_DEFINITIONS if d.definition_status == "REGISTERED"}
        required_names = tuple(task.target_state.to_invariant_names())
        coverable = bool(required_names) and set(required_names) <= registered
        if expectation is None and not coverable:
            rows.add(3)
        if any(name not in registered for name in required_names):
            rows.add(6)
        if target is None:
            rows.add(22)  # V.4 clause 3: no target row for the derived triple
        if is_render_task_class(task.task_class):
            rows.update({32, 42, 43})  # the v1 code-level render dimension applies to every render-bearing input
            verification = _verify_render_evidence(render_evidence, task)
            if verification is None:
                rows.add(44)
            else:
                rows.add(36)
            if verification == "twin-mismatch":
                rows.add(37)

    derived.update(members)
    derived["selector_triple"] = triple
    derived["target"] = target
    return Resolution(frozenset(rows), target, triple, MappingProxyType(derived))


def _verify_render_evidence(render_evidence: Any, task: UnrealProductionTaskDefinition) -> Optional[str]:
    """Part XVII / XIV.3.1: evidence-dependent render rows.

    Returns ``None`` when no evidence was supplied (row 44), ``"not-verified"`` when supplied evidence could not
    be independently verified (row 36) and ``"twin-mismatch"`` when the record's twin differs (row 37).
    R2-A implements no render verification of its own; independent verification is delegated to the unchanged
    M5 entry point, and any failure to verify is a refusal.
    """
    if render_evidence is None:
        return None
    try:
        from planning.unreal_evidence_contract import verify_render_job_evidence

        record = render_evidence
        record_twin = None
        for attribute in ("digital_twin_id", "twin_id"):
            record_twin = getattr(record, attribute, None)
            if record_twin is not None:
                break
        verify_render_job_evidence(record)
        if record_twin is not None and record_twin != task.digital_twin_id:
            return "twin-mismatch"
    except Exception:
        return "not-verified"
    return "verified"


# --------------------------------------------------------------------------- verifier + result construction

def verify_semantic_target_r2a(
    task: UnrealProductionTaskDefinition,
    plan: UnrealExecutionPlan,
    expectation: Any = None,
    *,
    render_evidence: Any = None,
    runtime_mapping_digest: Optional[str] = None,
) -> M126Result:
    """The M12.6 R2-A verdict boundary (XIV.7.3): one coherent result, refusal-only in R2-A.

    Returns the closed M12.6 result. The only non-result case in the contract is the unreadable-authority
    internal fault (VII.5), which raises :class:`M126UnreadableAuthorityError`.
    """
    if REGISTRY_SOURCE_DIGEST is None or TARGET_TABLE_DIGEST is None:
        raise M126UnreadableAuthorityError("authority constants are unreadable")

    resolution = resolve(task, plan, expectation, render_evidence=render_evidence)
    rows = set(resolution.applicable_rows)

    # verifier-owned expectation-side classification (S1 row 28 / S3 rows 4, 5, 7, 8, 14, 21, 30, 39)
    if expectation is not None:
        classification = classify_supplied_expectation(expectation, task=task, plan=plan)
        rows |= set(classification.rows)

    outcome = decisive_outcome(sorted(rows))
    members: Dict[str, Any] = {}

    derived = resolution.derived
    required_names = tuple(sorted(task.target_state.to_invariant_names()))
    render_task = is_render_task_class(task.task_class)

    members["schema"] = RESULT_SCHEMA_CONSTANT
    members["verifier_revision"] = VERIFIER_REVISION
    members["expectation_contract_revision"] = EXPECTATION_CONTRACT_REVISION
    members["resolver_revision"] = RESOLVER_REVISION
    members["registry_revision"] = REGISTRY_REVISION
    members["registry_digest"] = REGISTRY_SOURCE_DIGEST
    members["target_table_revision"] = TARGET_TABLE_REVISION
    members["target_table_digest"] = TARGET_TABLE_DIGEST
    members["production_target_id"] = None
    members["target_revision"] = None
    members["target_digest"] = None
    members["task_identity"] = derived.get("task_identity")
    members["task_version"] = derived.get("task_version")
    members["digital_twin_id"] = derived.get("digital_twin_id")
    members["catalog_entry_name"] = derived.get("catalog_entry_name")
    members["catalog_entry_version"] = derived.get("catalog_entry_version")
    members["vocabulary_digest"] = derived.get("vocabulary_digest")
    members["plan_id"] = derived.get("plan_id")
    members["source_content_digest"] = compute_source_content_digest(task)
    members["plan_content_digest"] = compute_plan_content_digest(plan)
    members["render_task"] = render_task
    members["required_invariant_names"] = required_names
    members["expectation_identity"] = None   # no expectation identity is established in R2-A (Part IX)
    members["expectation_digest"] = None
    members["observation_identity"] = None
    members["observation_digests"] = ()
    members["render_job_identity"] = None
    members["render_attempt_identity"] = None
    members["render_evidence_identity"] = None
    members["evidence_trust_basis"] = {
        "semantic_observation": "NOT_ESTABLISHED",
        "render_evidence": "NOT_APPLICABLE" if not render_task else "NOT_ESTABLISHED",
    }
    members["invariant_results"] = tuple(unresolved_entry(name) for name in required_names)
    semantic_state, overall_state = map_states(outcome.deciding_stage, outcome.reason_class)
    members["semantic_state"] = semantic_state
    members["render_state"] = "NOT_REQUIRED" if not render_task else "NOT_VERIFIED"
    members["overall_state"] = overall_state
    members["outcome_reason_class"] = outcome.reason_class
    members["failure_codes"] = outcome.failure_codes
    members["origin_status"] = ORIGIN_STATUS
    members["deciding_stage"] = outcome.deciding_stage
    members["primary_failure_code"] = outcome.primary_code

    return M126Result(members=members)


def express_fault_result(*, fault_injected: bool = False) -> M126Result:
    """Row 2 (representable internal fault, VII.5): all four code-level members stay non-null."""
    if not fault_injected:
        raise M126ContractError("row 2 is reachable by fault injection only")
    outcome = internal_fault_outcome()
    members = {
        "schema": RESULT_SCHEMA_CONSTANT,
        "verifier_revision": VERIFIER_REVISION,
        "expectation_contract_revision": EXPECTATION_CONTRACT_REVISION,
        "resolver_revision": RESOLVER_REVISION,
        "registry_revision": REGISTRY_REVISION,
        "registry_digest": REGISTRY_SOURCE_DIGEST,
        "target_table_revision": TARGET_TABLE_REVISION,
        "target_table_digest": TARGET_TABLE_DIGEST,
        "production_target_id": None,
        "target_revision": None,
        "target_digest": None,
        "task_identity": None,
        "task_version": None,
        "digital_twin_id": None,
        "catalog_entry_name": None,
        "catalog_entry_version": None,
        "vocabulary_digest": None,
        "plan_id": None,
        "source_content_digest": None,
        "plan_content_digest": None,
        "render_task": None,
        "required_invariant_names": (),
        "expectation_identity": None,
        "expectation_digest": None,
        "observation_identity": None,
        "observation_digests": (),
        "render_job_identity": None,
        "render_attempt_identity": None,
        "render_evidence_identity": None,
        "evidence_trust_basis": {
            "semantic_observation": "NOT_ESTABLISHED",
            "render_evidence": "NOT_ESTABLISHED",
        },
        "invariant_results": (),
        "semantic_state": "UNKNOWN",
        "render_state": "NOT_DECIDED",
        "overall_state": "UNKNOWN",
        "outcome_reason_class": "INTERNAL_FAILURE",
        "failure_codes": outcome.failure_codes,
        "origin_status": ORIGIN_STATUS,
        "deciding_stage": None,
        "primary_failure_code": outcome.primary_code,
    }
    return M126Result(members=members)
