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

import dataclasses
import hashlib
import math
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Dict, Mapping, MutableMapping, MutableSequence, MutableSet, Optional, Sequence, Tuple

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
) -> FrozenSet[int]:
    """VIII.3/V.5: in-call revalidation of the same objects; the FULL applicable S2 row set (XIV.3.1 clause 3).

    Every independently applicable integrity condition is reported, never just the first one encountered: the
    caller unions the rows and the primary code is the lowest-numbered applicable row. An empty set means the
    supplied tables satisfy every declared integrity condition.
    """
    rows = set()
    seen_names = set()
    for definition in definitions:
        if definition.definition_status == "REGISTERED" and definition.invariant_name in seen_names:
            rows.add(11)  # one invariant name may be REGISTERED once only
        seen_names.add(definition.invariant_name)
        if definition.authority_class not in {"CODE_CONSTANT"}:
            rows.add(33)  # the only admitted authority class
        if (
            not definition.observable_paths
            or not definition.subject_scope
            or list(definition.observable_paths) != sorted(set(definition.observable_paths))
            or list(definition.subject_scope) != sorted(set(definition.subject_scope))
        ):
            rows.add(38)  # definition path/scope shape and grammar
    target_ids = {t.production_target_id for t in targets}
    for mapping in mappings:
        if mapping.production_target_id not in target_ids:
            rows.add(10)  # a mapping that references a nonexistent target
    seen_triples = set()
    for mapping in mappings:
        triple = (mapping.entry_name, mapping.entry_version, mapping.task_class)
        if triple in seen_triples:
            rows.add(12)  # one selector triple may be mapped once only
        seen_triples.add(triple)
    if registry_digest(definitions, EXPECTATION_VOCABULARY, targets, mappings) != REGISTRY_SOURCE_DIGEST:
        rows.add(9)  # the reviewed registry does not recompute to its committed digest
    if target_table_digest(targets) != TARGET_TABLE_DIGEST:
        rows.add(10)  # the reviewed target table is stale or non-canonical
    return frozenset(rows)


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


_DECLARED_SCHEMA_CACHE: Dict[str, Any] = {}


#: Declared scalar domains (VII.4.1 check 3). `catalog_version` is deliberately absent: III.2 forbids M12.6
#: from consuming it semantically, so this machinery neither reads nor validates it.
_DECLARED_SCALAR_DOMAINS: Dict[str, Dict[str, str]] = {
    "task": {
        "canonical_task_id": "nonempty_str",
        "task_class": "nonempty_str",
        "digital_twin_id": "nonempty_str",
        "task_version": "int>=1",
    },
    "plan": {
        "plan_id": "nonempty_str",
        "source_task_id": "nonempty_str",
        "digital_twin_id": "nonempty_str",
        "source_task_version": "int>=1",
        "source_content_digest": "hex64",
    },
}

#: Declared member names that are opaque to this machinery: `catalog_version` (III.2) is never read by name.
_OPAQUE_MEMBERS = frozenset({"catalog_version"})

_DECLARED_OBJECT_FIELDS: Dict[str, FrozenSet[str]] = {}


def declared_object_fields(kind: str) -> FrozenSet[str]:
    """The declared attribute set of the supplied object class (VII.4.1 check 2, the object side)."""
    if kind not in _DECLARED_OBJECT_FIELDS:
        cls = UnrealProductionTaskDefinition if kind == "task" else UnrealExecutionPlan
        _DECLARED_OBJECT_FIELDS[kind] = frozenset(field.name for field in dataclasses.fields(cls))
    return _DECLARED_OBJECT_FIELDS[kind]


def _domain_ok(domain: str, value: Any) -> bool:
    if domain == "nonempty_str":
        return isinstance(value, str) and bool(value.strip())
    if domain == "int>=1":
        return isinstance(value, int) and not isinstance(value, bool) and value >= 1
    if domain == "hex64":
        return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{64}", value))
    raise M126ContractError(f"undeclared scalar domain: {domain!r}")


def preflight_object(obj: Any, kind: str) -> Optional[str]:
    """VII.4.1 checks 1-3 on the supplied **object** (VII.4: before any canonicalization).

    This runs before any serializer, canonicalizer or ``deepcopy`` call and inspects the object itself: the
    exact expected type (F1), the closed attribute set - no undeclared attribute and no missing declared
    attribute (F2) - and the declared scalar types and domains (F3). An inspection that raises is attributed
    to the supplied input as F4 (VII.4.2) and never becomes an internal failure.
    """
    expected_class = UnrealProductionTaskDefinition if kind == "task" else UnrealExecutionPlan
    if type(obj) is not expected_class:
        return "F1"
    categories: set = set()
    declared = declared_object_fields(kind)
    try:
        attributes = dict(vars(obj))
        has_instance_dict = True
    except TypeError:
        attributes = {field.name: getattr(obj, field.name, None) for field in dataclasses.fields(expected_class)}
        has_instance_dict = False
    except Exception:
        return "F4"
    if has_instance_dict:
        actual = frozenset(attributes)
        if declared - actual or actual - declared:
            categories.add("F2")  # an added runtime attribute, or a declared attribute that is missing
    for member, domain in _DECLARED_SCALAR_DOMAINS[kind].items():
        if member in attributes and not _domain_ok(domain, attributes[member]):
            categories.add("F3")
    if not categories:
        return None
    return min(categories, key=CATEGORY_ORDER.index)


def _declared_schema(kind: str) -> Any:
    """The declared schema of a task/plan projection, captured from its own M12.1/M12.3 producer.

    The schema is a code-level constant derived from the canonical producers (never from caller input):
    for every declared member it records the declared value class and, for the closed nested containers,
    the declared member sets of their elements. Built lazily to avoid an import cycle.
    """
    if kind not in _DECLARED_SCHEMA_CACHE:
        from planning.m12 import DEFAULT_UNREAL_CATALOG, generate_execution_plan

        task = DEFAULT_UNREAL_CATALOG.resolve(
            "unreal.sequence-configure",
            {"twin_id": "twin-1", "sequence_name": "main", "frame_start": 1, "frame_end": 24},
            digital_twin_id="twin-1",
        )
        plan = generate_execution_plan(task)
        document = task.to_json_compatible() if kind == "task" else plan.to_json_compatible()
        _DECLARED_SCHEMA_CACHE[kind] = (tuple(sorted(document)), _shape_of(document))
    return _DECLARED_SCHEMA_CACHE[kind]


def _value_class(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, str):
        return "hex64" if re.fullmatch(r"[0-9a-f]{64}", value) else "str"
    if isinstance(value, Mapping):
        return "mapping"
    if isinstance(value, (list, tuple)):
        return "sequence"
    if value is None:
        return "none"
    if isinstance(value, float):
        return "float"
    return type(value).__name__


def _shape_of(value: Any) -> Any:
    """A recursive shape description: declared member classes, and the declared schema of closed containers."""
    if isinstance(value, Mapping):
        return {key: _shape_of(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        element_shapes = [_shape_of(item) for item in value]
        if element_shapes and all(isinstance(shape, Mapping) for shape in element_shapes):
            keys = set()
            for shape in element_shapes:
                keys |= set(shape)
            required = set(element_shapes[0])
            for shape in element_shapes[1:]:
                required &= set(shape)
            merged = {}
            for key in sorted(keys):
                merged[key] = next((shape[key] for shape in element_shapes if key in shape), "none")
            return {"__element_schema__": merged, "__required__": sorted(required)}
        return {"__element_classes__": sorted({_value_class(item) for item in value})}
    return _value_class(value)


_TYPE_CHECKS = {
    "str": lambda v: isinstance(v, str),
    "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "bool": lambda v: isinstance(v, bool),
    "hex64": lambda v: isinstance(v, str) and bool(re.fullmatch(r"[0-9a-f]{64}", v)),
}

#: Declared members whose value is a free-form bag: their key sets are not part of the declared schema.
_FREE_FORM_MEMBERS = {"metadata", "provenance", "arguments"}

#: The declared closed nested containers: their elements' declared member sets are enforced (F2).
_CLOSED_CONTAINERS = {"target_state", "steps", "actions", "evidence"}

#: The non-empty sequence constraints the M12.1/M12.3 producers actually impose (F9). Neither the task's
#: `allowed_mutations` nor its `dependencies` is required to be non-empty: those sequences are permitted empty.
_F9_NON_EMPTY = {
    ("plan", "steps"),  # a plan without steps is refused by the producer schema
}

#: The duplicate-element constraints of the closed schema: these sequences are emitted from sets.
_F9_UNIQUE = {
    ("task", "allowed_mutations"),
    ("task", "dependencies"),
    ("task", "allowed_action_tools"),
    ("plan", "steps"),
}


def _class_matches(declared: str, value: Any) -> bool:
    check = _TYPE_CHECKS.get(declared)
    if check is not None:
        return bool(check(value))
    if declared == "none":
        return value is None
    if declared == "mapping":
        return isinstance(value, Mapping)
    if declared == "sequence":
        return isinstance(value, (list, tuple))
    if declared == "float":
        return isinstance(value, float)
    return True


def _validate_document(value: Any, shape: Any, categories: set, member: Optional[str] = None) -> None:
    """Recursively validate a projection against a declared shape (VII.4.1 checks 2 and 3).

    A shape that is a plain Mapping declares a closed container: its member set must match exactly. A
    free-form bag (metadata/provenance/arguments) and any other nested mapping is only required to be a
    mapping; the declared members it does carry are still type-checked. A ``{"__element_schema__": ...}``
    shape declares the member set of every element of a sequence.
    """
    if isinstance(shape, Mapping) and "__element_schema__" in shape:
        element_schema = shape["__element_schema__"]
        required = set(shape.get("__required__", element_schema))
        if not isinstance(value, (list, tuple)):
            categories.add("F3")
            return
        for element in value:
            if not isinstance(element, Mapping):
                categories.add("F3")
                continue
            if set(element) - set(element_schema) or required - set(element):
                categories.add("F2")  # an undeclared member, or a member every element declares
                continue
            for nested_member, nested_shape in element_schema.items():
                if nested_member not in element:
                    continue
                _validate_document(element[nested_member], nested_shape, categories, nested_member)
        return
    if isinstance(shape, Mapping) and "__element_classes__" in shape:
        if not isinstance(value, (list, tuple)):
            categories.add("F3")
            return
        declared_classes = shape["__element_classes__"]
        if not declared_classes:
            return  # the declared element set was empty: no element constraint is declared
        for element in value:
            if not any(_class_matches(declared, element) for declared in declared_classes):
                categories.add("F3")
        return
    if isinstance(shape, Mapping):
        if not isinstance(value, Mapping):
            categories.add("F3")
            return
        if member in _CLOSED_CONTAINERS and set(value) != set(shape):
            categories.add("F2")
            return
        for nested_member, nested_shape in shape.items():
            if nested_member not in value:
                continue
            _validate_document(value[nested_member], nested_shape, categories, nested_member)
        return
    if member in _OPAQUE_MEMBERS:
        return  # opaque member: never read by name, never validated (III.2)
    if not _class_matches(shape, value):
        categories.add("F3")


def validate_declared_schema(document: Mapping[str, Any], kind: str) -> Optional[str]:
    """F2/F3/F9 against the declared task/plan schema (VII.4.1 checks 2, 3 and 9).

    Returns the lowest-numbered applicable category, or ``None`` when the document satisfies the declared
    schema. Nested closed containers are validated against their declared member sets (VII.4.1.1).
    """
    if kind not in {"task", "plan"}:
        raise M126ContractError(f"undeclared object class: {kind!r}")
    if not isinstance(document, Mapping):
        return "F1"
    declared_keys, shape = _declared_schema(kind)
    categories: set = set()

    # ---- F2: the declared member set equals the document's key set (no missing, no undeclared member)
    if set(document) != set(declared_keys):
        categories.add("F2")
    for member, declared_shape in shape.items():
        if member not in document or member in _OPAQUE_MEMBERS:
            continue
        _validate_document(document[member], declared_shape, categories, member)
    for member, domain in _DECLARED_SCALAR_DOMAINS[kind].items():
        if member in document and not _domain_ok(domain, document[member]):
            categories.add("F3")  # task_version/source_task_version >= 1, digest members 64-hex

    # ---- F9: non-empty / duplicate-element constraints where the declared schema requires them
    for k, member in _F9_NON_EMPTY:
        if k != kind or member not in document:
            continue
        value = document[member]
        if isinstance(value, (list, tuple)) and not value:
            categories.add("F9")
    for k, member in _F9_UNIQUE:
        if k != kind or member not in document:
            continue
        value = document[member]
        if isinstance(value, (list, tuple)) and len(set(map(str, value))) != len(value):
            categories.add("F9")
    steps = document.get("steps")
    if kind == "plan" and isinstance(steps, (list, tuple)):
        for step in steps:
            if isinstance(step, Mapping):
                requirements = step.get("verification_requirements")
                if isinstance(requirements, (list, tuple)) and len(set(map(str, requirements))) != len(requirements):
                    categories.add("F9")
    target_state = document.get("target_state")
    if kind == "task" and isinstance(target_state, Mapping):
        names = target_state.get("invariant_names")
        if isinstance(names, (list, tuple)) and len(set(map(str, names))) != len(names):
            categories.add("F9")

    if not categories:
        return None
    return min(categories, key=CATEGORY_ORDER.index)


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
    wrong_types = _declared_member_type_errors(claim)
    null_targets = sorted(name for name in TARGET_MEMBERS if name in keys and claim[name] is None)

    # ---- limb 1 (row 5): the Part IX presence conditions. A declared non-nullable member supplied as null
    #      (or absent, or of the wrong declared type) is a presence violation; rows 4/7 are not additionally
    #      applicable to THAT condition (Part IX exclusivity, per XIV.3.1 clause 3).
    schema_defect = bool(missing or undeclared or wrong_types or null_targets)
    if schema_defect:
        rows.add(5)
        if missing or undeclared:
            detail["incomplete"] = {"missing": missing, "undeclared": undeclared}
        if wrong_types:
            detail["member_type_errors"] = wrong_types
        if null_targets:
            detail["null_target_members"] = null_targets

    # ---- limb 2 (rows 5/30): the required-set limbs, each on its own predicate. Never suppressed.
    names = claim.get("required_invariant_names")
    entries = claim.get("invariant_expectations")
    if isinstance(names, (list, tuple)):
        if len(names) == 0:
            rows.add(30)  # expectation-side occurrence of row 30 (verifier-owned operand)
            detail["empty_required_set"] = True
        name_set = [str(n) for n in names]
        if sorted(name_set) != name_set:
            rows.add(5)
            detail["required_names_unsorted"] = True
    if isinstance(names, (list, tuple)) and isinstance(entries, (list, tuple)):
        if len(names) != len(entries):
            rows.add(5)
            detail["count_mismatch"] = {"names": len(names), "entries": len(entries)}
        entry_names = [str(e.get("invariant_name")) for e in entries if isinstance(e, Mapping)]
        if sorted(entry_names) != entry_names:
            rows.add(5)  # invariant_expectations is sorted by invariant_name
        if names and sorted(str(n) for n in names) != sorted(entry_names):
            rows.add(5)
            detail["name_mismatch"] = True

    # ---- limb 3 (row 39): the expectation object's own contradictions. Never suppressed.
    if claim.get("origin_status", ORIGIN_STATUS) != ORIGIN_STATUS:
        rows.add(39)
        detail["origin_status"] = claim.get("origin_status")
    for member, allowed in _CLOSED_VOCAB.items():
        if member in claim and claim[member] not in allowed:
            rows.add(39)
            detail[member] = claim[member]

    # ---- limb 4 (row 8): the supplied-artifact digest. Evaluated only when every declared member is present
    #      with its declared type, so no comparison is ever fabricated against an absent member (B7).
    type_errors = {name: kind for name, kind in wrong_types.items() if name not in null_targets}
    complete = not missing and not undeclared and not type_errors
    if complete and isinstance(claim.get("expectation_digest"), str):
        if compute_expectation_digest(claim) != claim["expectation_digest"]:
            rows.add(8)
            detail["digest_mismatch"] = True

    # ---- limb 5 (rows 4/7): identity recomputation, demanded whenever the supplied expectation is
    #      schema-valid (XXIV.1(ii)) and never added to a condition row 5 classifies.
    if not schema_defect:
        rows.update({4, 7})
        detail["identity"] = "not-recomputable-in-r2a"

    # ---- limb 6 (rows 14/21): stale-source checks, each gated on its own prerequisites being present (B7).
    if complete and task is not None and plan is not None:
        if isinstance(claim.get("source_content_digest"), str) and \
                claim["source_content_digest"] != compute_source_content_digest(task):
            rows.add(21)
            detail["stale_source"] = True
        if isinstance(claim.get("plan_content_digest"), str) and \
                claim["plan_content_digest"] != compute_plan_content_digest(plan):
            rows.update({14, 21})
            detail["stale_plan"] = True

    return ExpectationClassification(frozenset(rows), not schema_defect, bool(null_targets),
                                     MappingProxyType(detail))


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


#: The declared member types of the 39-member result (XIV.4.5). `?T` is a nullable member; the two declared
#: non-semantic members are nullable by declaration.
_RESULT_MEMBER_TYPES: Dict[str, str] = {
    "schema": "str", "verifier_revision": "str", "expectation_contract_revision": "str", "resolver_revision": "str",
    "registry_revision": "int", "registry_digest": "hex64",
    "target_table_revision": "int", "target_table_digest": "hex64",
    "production_target_id": "?str", "target_revision": "?int", "target_digest": "?hex64",
    "task_identity": "?str", "task_version": "?int", "digital_twin_id": "?str",
    "catalog_entry_name": "?str", "catalog_entry_version": "?int", "vocabulary_digest": "?hex64",
    "plan_id": "?str", "source_content_digest": "?hex64", "plan_content_digest": "?hex64",
    "render_task": "?bool", "required_invariant_names": "seq_str",
    "expectation_identity": "?str", "expectation_digest": "?hex64",
    "observation_identity": "?str", "observation_digests": "seq_str",
    "render_job_identity": "?str", "render_attempt_identity": "?int", "render_evidence_identity": "?hex64",
    "evidence_trust_basis": "trust_basis", "invariant_results": "entries",
    "semantic_state": "str", "render_state": "str", "overall_state": "str",
    "outcome_reason_class": "str", "failure_codes": "seq_str", "origin_status": "str",
    "deciding_stage": "?str", "primary_failure_code": "?str",
}
if set(_RESULT_MEMBER_TYPES) != set(RESULT_MEMBERS):  # fail-closed: no member may escape type validation
    raise M126ContractError("the declared member-type map does not cover the closed result schema")

#: The declared vocabularies of the closed two-member trust basis (XIV.4.6).
_TRUST_BASIS_MEMBERS = ("semantic_observation", "render_evidence")
_TRUST_BASIS_VOCABULARY = {
    "semantic_observation": frozenset({"NOT_ESTABLISHED", "ESTABLISHED", "NOT_APPLICABLE"}),
    "render_evidence": frozenset({"NOT_APPLICABLE", "NOT_ESTABLISHED", "DURABLE_RECORD_BACKED"}),
}

#: The module-private construction token (XIV.1): only the verifier builds a result. A caller that supplies its
#: own row set and members cannot forge one, and every derived field is recomputed from the rows regardless.
_RESULT_CONSTRUCTION_TOKEN = object()


def _member_type_ok(declared: str, value: Any) -> bool:
    if declared.startswith("?"):
        if value is None:
            return True
        return _member_type_ok(declared[1:], value)
    if declared == "str":
        return isinstance(value, str)
    if declared == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if declared == "bool":
        return isinstance(value, bool)
    if declared == "hex64":
        return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{64}", value))
    if declared == "seq_str":
        return isinstance(value, (list, tuple)) and all(isinstance(item, str) for item in value)
    if declared == "mapping":
        return isinstance(value, Mapping)
    if declared == "entries":
        return isinstance(value, (list, tuple)) and all(
            isinstance(entry, InvariantVerificationResult) for entry in value
        )
    if declared == "trust_basis":
        if not isinstance(value, Mapping) or set(value) != set(_TRUST_BASIS_MEMBERS):
            return False
        return all(value[name] in _TRUST_BASIS_VOCABULARY[name] for name in _TRUST_BASIS_MEMBERS)
    raise M126ContractError(f"undeclared member type: {declared!r}")


def _validate_member_types(members: Mapping[str, Any]) -> None:
    """XIV.4.5/XIV.1: every declared member's type and nullability is validated at construction."""
    for name, declared in _RESULT_MEMBER_TYPES.items():
        if not _member_type_ok(declared, members[name]):
            raise M126ContractError(
                f"result member {name!r} violates its declared type ({declared}): {type(members[name]).__name__}"
            )


@dataclass(frozen=True)
class M126Result:
    """The closed 39-member M12.6 result (XIV.4.5) plus its derived ``result_digest``."""

    members: Mapping[str, Any]
    applicable_rows: Tuple[int, ...] = ()
    _construction_token: Any = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        raise TypeError("M126Result is sealed")

    def __post_init__(self) -> None:
        if self._construction_token is not _RESULT_CONSTRUCTION_TOKEN:
            raise M126ContractError(
                "M126Result is constructed by the verifier only (XIV.1 trusted construction): a caller-supplied "
                "member mapping and row set cannot be forged into a result"
            )
        missing = [name for name in RESULT_MEMBERS if name not in self.members]
        extra = sorted(set(self.members) - set(RESULT_MEMBERS))
        if missing or extra:
            raise M126ContractError(f"result member set mismatch: missing={missing} extra={extra}")
        if not self.applicable_rows:
            raise M126ContractError(
                "the applicable row set is required: every derived field is defined by the rows (XIV.2/XIV.3.1)"
            )
        # Nested canonical members are made immutable: a silently mutable nested structure could otherwise
        # invalidate an already-constructed result or its digest (XIV.4.5/XIV.4.6).
        frozen: Dict[str, Any] = dict(self.members)
        for name in ("required_invariant_names", "observation_digests", "failure_codes", "invariant_results"):
            frozen[name] = tuple(frozen[name])
        basis = frozen.get("evidence_trust_basis")
        if isinstance(basis, Mapping):
            frozen["evidence_trust_basis"] = MappingProxyType(dict(basis))
        object.__setattr__(self, "members", MappingProxyType(frozen))
        object.__setattr__(self, "applicable_rows", tuple(sorted(set(self.applicable_rows))))
        _validate_member_types(self.members)
        self._validate_coherence()
        self._enforce_derived_fields()
        validate_r2a_conformance(self.members)
        self._assert_immutable()

    def _enforce_derived_fields(self) -> None:
        """XIV.2/XIV.3/XIV.3.1: the derived fields are functions of the applicable rows, never of the caller.

        Recomputing them here rejects an inconsistent stage/class mapping, a primary code that is not the
        lowest-numbered applicable row, a fabricated tuple and an invalid failure-code union.
        """
        rows = tuple(self.applicable_rows)
        if set(rows) == {2}:
            outcome = internal_fault_outcome()
        else:
            outcome = decisive_outcome(rows)
        m = self.members
        expected = {
            "deciding_stage": outcome.deciding_stage,
            "primary_failure_code": outcome.primary_code,
            "failure_codes": outcome.failure_codes,
            "outcome_reason_class": outcome.reason_class,
        }
        for name, value in expected.items():
            if m[name] != value:
                raise M126ContractError(
                    f"{name} is defined by the applicable rows {list(rows)}: expected {value!r}, got {m[name]!r}"
                )
        semantic_state, overall_state = map_states(outcome.deciding_stage, outcome.reason_class)
        if (m["semantic_state"], m["overall_state"]) != (semantic_state, overall_state):
            raise M126ContractError(
                "semantic_state/overall_state must equal the mapping of the deciding stage and reason class"
            )

    def _assert_immutable(self) -> None:
        """Every canonical member is an immutable structure: no post-construction mutation can slip through."""
        for name, value in self.members.items():
            if isinstance(value, (MutableMapping, MutableSequence, MutableSet)):
                raise M126ContractError(f"canonical member {name!r} is a mutable structure")

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
        """XIV.4.5: the closed canonical object; array members serialize as JSON arrays.

        Coherence is enforced again here, on the members as they stand now: serialization and the digest
        derived from it must never be taken from a result that has drifted since construction.
        """
        self._assert_immutable()
        _validate_member_types(self.members)
        self._validate_coherence()
        self._enforce_derived_fields()
        validate_r2a_conformance(self.members)
        arrays = {"required_invariant_names", "observation_digests", "failure_codes"}
        return {
            # nested mappings are materialized as plain JSON objects for serialization while the result's
            # own members stay immutable (no post-construction mutation can reach the serialized form)
            **{name: (list(self.members[name]) if name in arrays
                      else (dict(self.members[name]) if isinstance(self.members[name], Mapping)
                            else self.members[name]))
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
    """V.4: ``(entry_name, entry_version, task_class)`` derived from the task's closed selector.

    An object of the wrong class has no closed selector: no triple can be derived from it, and the refusal
    that applies is the structural one (row 1).
    """
    if type(task) is not UnrealProductionTaskDefinition:
        return ("", 0, "")
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


def mapping_reference_status(
    triple: Tuple[str, int, str],
    mappings: Sequence[TaskTargetMapping] = PRODUCTION_TARGET_BY_TASK,
    targets: Sequence[ProductionTargetSpec] = PRODUCTION_TARGETS,
) -> str:
    """V.4 clause 3 / VIII.3: the selector's mapping-reference integrity (an S2 condition).

    Returns ``"none"`` (no mapping row matches the triple: a coverage question for S4), ``"ok"``,
    ``"duplicate"`` (two or more rows match) or ``"dangling"`` (the matching row references a target that
    does not exist). A dangling reference is an authority-integrity refusal, never a coverage miss.
    """
    matches = [m for m in mappings if (m.entry_name, m.entry_version, m.task_class) == triple]
    if not matches:
        return "none"
    if len(matches) > 1:
        return "duplicate"
    if matches[0].production_target_id not in {t.production_target_id for t in targets}:
        return "dangling"
    return "ok"


def _declared_pair_vocabulary(task: UnrealProductionTaskDefinition) -> Optional[EntryVocabulary]:
    for entry in EXPECTATION_VOCABULARY:
        if entry.entry_name == task.canonical_task_id and entry.entry_version == task.task_version:
            return entry
    return None


def _domain_a_representable(compute: Any) -> Optional[str]:
    """XIV.4.6.2 clause 6: a member is non-null only if its value is representable in Domain A.

    A malformed projection that Domain A cannot canonicalize leaves the member null; the fault that would
    otherwise surface is attributed to the supplied input, which keeps its own S1 row (VII.4.2).
    """
    try:
        value = compute()
    except Exception:
        return None
    return value if isinstance(value, str) else None


def _task_derived_members(task: UnrealProductionTaskDefinition) -> Dict[str, Any]:
    """P1-P6 and the plan-side of the pair: per-member establishment predicates (XIV.4.6.2)."""
    members: Dict[str, Any] = {}
    if type(task) is not UnrealProductionTaskDefinition:
        # an object of the wrong class derives nothing: the refusal is the structural one (row 1, F1)
        return {name: None for name in ("task_identity", "task_version", "digital_twin_id",
                                       "catalog_entry_name", "catalog_entry_version", "vocabulary_digest")}
    members["task_identity"] = task.canonical_task_id if isinstance(task.canonical_task_id, str) and task.canonical_task_id.strip() else None
    version = task.task_version
    members["task_version"] = version if (isinstance(version, int) and not isinstance(version, bool)
                                          and version >= 1 and abs(version) <= DOMAIN_A_INT_LIMIT) else None
    twin = task.digital_twin_id
    members["digital_twin_id"] = twin if isinstance(twin, str) and twin.strip() else None
    entry = _declared_pair_vocabulary(task)
    members["catalog_entry_name"] = task.canonical_task_id if entry is not None else None
    entry_version = task.task_version
    entry_version_eligible = (isinstance(entry_version, int) and not isinstance(entry_version, bool)
                              and entry_version >= 1 and abs(entry_version) <= DOMAIN_A_INT_LIMIT)
    members["catalog_entry_version"] = entry_version if (entry is not None and entry_version_eligible) else None
    members["vocabulary_digest"] = entry.vocabulary_digest if entry is not None else None
    return members


def _plan_derived_members(plan: UnrealExecutionPlan) -> Dict[str, Any]:
    members: Dict[str, Any] = {}
    if type(plan) is not UnrealExecutionPlan:
        return {"plan_id": None}
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

    # ---- S1: the structural preflight (VII.4). XIV.3.1 clause 3: every independently applicable S1
    #      component is evaluated and unioned; no component short-circuits another, and the primary code is
    #      the lowest-numbered applicable row.
    #      VII.4: the object-level checks run FIRST and invent no serializer, canonicalizer or deepcopy call;
    #      the declared-schema comparison and the content traversal follow, and every exception raised while
    #      inspecting supplied content is attributed to that content as F4 (VII.4.2).
    details: Dict[str, Any] = {}
    valid: Dict[str, bool] = {}
    documents: Dict[str, Any] = {}
    for kind, candidate in (("task", task), ("plan", plan)):
        category = preflight_object(candidate, kind)
        if category is not None:
            rows.add(1)
            details[kind] = {"category": category}
            valid[kind] = False
        else:
            valid[kind] = True

    for kind, candidate in (("task", task), ("plan", plan)):
        if not valid[kind]:
            continue
        try:
            document = candidate.to_json_compatible()
        except Exception:
            # an exception raised while inspecting supplied content is attributed to the supplied input (F4)
            rows.add(1)
            details[kind] = {"category": "F4"}
            valid[kind] = False
            continue
        documents[kind] = document
        refusal = preflight_document(document)
        if refusal is not None:
            rows.add(refusal.row)
            details[kind] = {"category": refusal.category}
            valid[kind] = False
            continue
        category = validate_declared_schema(document, kind)
        if category is not None:
            rows.add(1)
            details[kind] = {"category": category}
            valid[kind] = False

    # X.2 item 5: only a STRUCTURALLY VALID plan reaches the float policy. A plan that fails the object-level
    # or declared-schema checks is refused as RESOLVER_INPUT_STRUCTURE_INVALID and row 29 MUST NOT be added.
    if valid.get("plan") and plan_contains_float(documents.get("plan")):
        rows.add(29)
        details["float_policy"] = "PLAN_CONTENT_UNSUPPORTED"
    if details:
        derived["preflight"] = details

    # ---- S2: authority-table integrity (in-call revalidation of the same objects) and the reference
    #      integrity of this selector's mapping (VIII.3). Every applicable S2 row is unioned.
    if not rows:
        rows |= revalidate_authority()
        reference_status = mapping_reference_status(_selector_triple(task))
        if reference_status in {"dangling", "duplicate"}:
            rows.add(10)  # a mapping that references a nonexistent/duplicate target is an integrity refusal
            derived["mapping_reference"] = reference_status

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
            render_outcome = _verify_render_evidence(render_evidence, task)
            if render_outcome.verified:
                # independently verified evidence: neither row 36 nor row 44, and the three render identity
                # members are established (XIV.4.6), so the render trust basis becomes DURABLE_RECORD_BACKED.
                members["render_job_identity"] = render_outcome.render_job_identity
                members["render_attempt_identity"] = render_outcome.render_attempt_identity
                members["render_evidence_identity"] = render_outcome.render_evidence_identity
            elif render_outcome.supplied:
                rows.add(36)  # M5 refused or failed to verify the supplied evidence
            else:
                rows.add(44)  # no render evidence is available for a render-bearing task
            if render_outcome.twin_mismatch:
                rows.add(37)

    derived.update(members)
    derived["selector_triple"] = triple
    derived["target"] = target
    return Resolution(frozenset(rows), target, triple, MappingProxyType(derived))


@dataclass(frozen=True)
class RenderEvidenceOutcome:
    """Render-evidence disposition: which evidence rows apply and the verified identity members."""

    verified: bool
    twin_mismatch: bool
    supplied: bool
    render_job_identity: Optional[str] = None
    render_attempt_identity: Optional[int] = None
    render_evidence_identity: Optional[str] = None


#: The real M5/durable-record type names, recognized by name so that M12.6 imports no M4-M10 module
#: (Part XVII.5). The caller hands over the already-verified objects; M12.6 never calls M5.
_M5_EVIDENCE_TYPE_NAMES = frozenset({"UnrealEvidence"})
_M5_DURABLE_RECORD_TYPE_NAMES = frozenset({"AtlasRenderJobRecord"})


def _type_names(value: Any) -> FrozenSet[str]:
    return frozenset(cls.__name__ for cls in type(value).__mro__)


def _is_m5_evidence(value: Any) -> bool:
    return value is not None and bool(_type_names(value) & _M5_EVIDENCE_TYPE_NAMES)


def _is_m5_durable_record(value: Any) -> bool:
    return value is not None and bool(_type_names(value) & _M5_DURABLE_RECORD_TYPE_NAMES)


def _verify_render_evidence(render_evidence: Any, task: UnrealProductionTaskDefinition) -> RenderEvidenceOutcome:
    """Part XVII / XIV.3.1 / XIV.4.6: the evidence-dependent render rows and the verified identity members.

    The caller (the permitted M5-to-M12.6 handoff) supplies the objects M5 already produced: the real
    ``UnrealEvidence`` and the real ``AtlasRenderJobRecord``. M12.6 calls neither M5 nor the record module - it
    imports no M4-M10 authority module at all (XVII.5) - and reads the declared members of those real types:

      * ``evidence.verified is True``  -> M5 verified the evidence (the M5 signal, read from the real contract)
      * no evidence / no durable record -> row 44 (missing) or row 36 (M5 did not verify)
      * ``record.canonical_digital_twin_id != task.digital_twin_id`` -> row 37 additionally applicable
      * verified -> neither row 36 nor row 44; the three render identity members are established from the
        durable record (``atlas_job_id``, ``attempt_ordinal``) and the M12.5 evidence recipe

    Every shape that cannot be established is a refusal (fail-closed): a mapping, a shadow object or an
    unverified evidence object is row 36, never a silent success.
    """
    if render_evidence is None:
        return RenderEvidenceOutcome(verified=False, twin_mismatch=False, supplied=False)

    evidence = getattr(render_evidence, "evidence", None)
    record = getattr(render_evidence, "record", None)
    if evidence is None and record is None:
        # the carrier itself may be the evidence object (the single-object handoff form)
        if _is_m5_evidence(render_evidence):
            evidence = render_evidence
        else:
            return RenderEvidenceOutcome(verified=False, twin_mismatch=False, supplied=True)

    if not _is_m5_evidence(evidence) or not _is_m5_durable_record(record):
        # the handoff must carry the real frozen M5 types: anything else cannot establish the render dimension
        return RenderEvidenceOutcome(verified=False, twin_mismatch=False, supplied=True)

    if getattr(evidence, "verified", False) is not True:
        return RenderEvidenceOutcome(verified=False, twin_mismatch=False, supplied=True)

    record_twin = getattr(record, "canonical_digital_twin_id", None)
    job_identity = getattr(record, "atlas_job_id", None)
    attempt_identity = getattr(record, "attempt_ordinal", None)
    if not isinstance(job_identity, str) or not job_identity.strip():
        return RenderEvidenceOutcome(verified=False, twin_mismatch=False, supplied=True)
    if not isinstance(attempt_identity, int) or isinstance(attempt_identity, bool) or attempt_identity < 1:
        return RenderEvidenceOutcome(verified=False, twin_mismatch=False, supplied=True)

    evidence_identity = _domain_a_representable(lambda: compute_evidence_identity_from_evidence(evidence))
    if evidence_identity is None:
        return RenderEvidenceOutcome(verified=False, twin_mismatch=False, supplied=True)

    return RenderEvidenceOutcome(
        verified=True,
        twin_mismatch=bool(record_twin is not None and record_twin != task.digital_twin_id),
        supplied=True,
        render_job_identity=job_identity,
        render_attempt_identity=attempt_identity,
        render_evidence_identity=evidence_identity,
    )


def _json_materialize(value: Any, depth: int = 0) -> Any:
    """Materialize an object graph into Domain-A structures (mappings as objects, sequences as arrays).

    The real M5/durable-record types store immutable mapping views; Domain A canonicalization requires plain
    mapping/sequence structures. This is a projection of the value, not a semantic read of it.
    """
    if depth > PREFLIGHT_DEPTH_LIMIT:
        raise M126ContractError("evidence projection exceeds the declared depth bound")
    if isinstance(value, Mapping):
        return {str(key): _json_materialize(item, depth + 1) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_materialize(item, depth + 1) for item in value]
    return value


def compute_evidence_identity_from_evidence(evidence: Any) -> str:
    """XIV.4.6 / X.2 recipe for the render evidence identity, over the M5 evidence's declared members."""
    return domain_a_digest({
        "operation_name": evidence.operation_name,
        "entity_ids": tuple(evidence.entity_ids),
        "observed_state": _json_materialize(evidence.observed_state),
        "source": evidence.source,
    })


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

    try:
        return _verify_semantic_target_r2a_impl(
            task, plan, expectation,
            render_evidence=render_evidence, runtime_mapping_digest=runtime_mapping_digest,
        )
    except (M126UnreadableAuthorityError, M126ContractError):
        raise
    except Exception:
        # A fault that cannot be classified is the representable internal failure (row 2, VII.5): malformed
        # required input never escapes this boundary as an uncaught exception.
        return express_fault_result(fault_injected=True)


def _verify_semantic_target_r2a_impl(
    task: UnrealProductionTaskDefinition,
    plan: UnrealExecutionPlan,
    expectation: Any = None,
    *,
    render_evidence: Any = None,
    runtime_mapping_digest: Optional[str] = None,
) -> M126Result:
    resolution = resolve(task, plan, expectation, render_evidence=render_evidence)
    rows = set(resolution.applicable_rows)

    # verifier-owned expectation-side classification (S1 row 28 / S3 rows 4, 5, 7, 8, 14, 21, 30, 39)
    if expectation is not None:
        classification = classify_supplied_expectation(expectation, task=task, plan=plan)
        rows |= set(classification.rows)

    outcome = decisive_outcome(sorted(rows))
    members: Dict[str, Any] = {}

    derived = resolution.derived
    try:
        required_names = tuple(sorted(task.target_state.to_invariant_names()))
    except Exception:
        required_names = ()
    if type(task) is not UnrealProductionTaskDefinition:
        render_task = None  # the task class is unreadable: the render dimension is not decided
    else:
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
    members["source_content_digest"] = _domain_a_representable(lambda: compute_source_content_digest(task))
    members["plan_content_digest"] = _domain_a_representable(lambda: compute_plan_content_digest(plan))
    members["render_task"] = render_task
    members["required_invariant_names"] = required_names
    members["expectation_identity"] = None   # no expectation identity is established in R2-A (Part IX)
    members["expectation_digest"] = None
    members["observation_identity"] = None
    members["observation_digests"] = ()
    members["render_job_identity"] = derived.get("render_job_identity")
    members["render_attempt_identity"] = derived.get("render_attempt_identity")
    members["render_evidence_identity"] = derived.get("render_evidence_identity")
    render_evidentiary_basis = (
        members["render_job_identity"] is not None
        and members["render_attempt_identity"] is not None
        and members["render_evidence_identity"] is not None
    )
    members["evidence_trust_basis"] = {
        "semantic_observation": "NOT_ESTABLISHED",
        "render_evidence": (
            "NOT_APPLICABLE" if render_task is False
            else ("DURABLE_RECORD_BACKED" if render_evidentiary_basis else "NOT_ESTABLISHED")
        ),
    }
    members["invariant_results"] = tuple(unresolved_entry(name) for name in required_names)
    semantic_state, overall_state = map_states(outcome.deciding_stage, outcome.reason_class)
    members["semantic_state"] = semantic_state
    members["render_state"] = ("NOT_DECIDED" if render_task is None
                               else ("NOT_REQUIRED" if render_task is False else "NOT_VERIFIED"))
    members["overall_state"] = overall_state
    members["outcome_reason_class"] = outcome.reason_class
    members["failure_codes"] = outcome.failure_codes
    members["origin_status"] = ORIGIN_STATUS
    members["deciding_stage"] = outcome.deciding_stage
    members["primary_failure_code"] = outcome.primary_code

    return M126Result(members=members, applicable_rows=tuple(sorted(rows)),
                      _construction_token=_RESULT_CONSTRUCTION_TOKEN)


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
    return M126Result(members=members, applicable_rows=(2,),
                      _construction_token=_RESULT_CONSTRUCTION_TOKEN)
