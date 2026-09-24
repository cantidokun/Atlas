"""Atlas M12.6 R2-A semantic expectation resolution machinery.

R2-A is intentionally refusal-only:
- no registered production invariant;
- no production target values;
- empty target lookup table;
- no SATISFIED/NOT_SATISFIED evaluation path.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, is_dataclass, fields
from enum import Enum
from typing import Any, Mapping, Optional, Sequence, Tuple

from planning.m12.execution_plan import (
    UnrealExecutionPlan,
    compute_source_content_digest,
    _canonical_sha256,
)
from planning.m12.semantic_task import UnrealProductionTaskDefinition
from planning.m12.target_state import UnrealTargetStateSpec
from planning.m12.task_classes import is_render_task_class
from planning.unreal_state_extraction.jcs import canonical_bytes as domain_a_bytes


EXPECTATION_CONTRACT_REVISION = "m12.6-expectation-v1"
RESOLVER_REVISION = "m12.6-resolver-v1"
VERIFIER_REVISION = "m12.6-v1"
PREFLIGHT_NODE_BUDGET = 100_000
PREFLIGHT_MAX_DEPTH = 20

TOKEN_RESOLVER_INPUT_STRUCTURE_INVALID = "RESOLVER_INPUT_STRUCTURE_INVALID"
TOKEN_RESOLVER_INTERNAL_FAILURE = "RESOLVER_INTERNAL_FAILURE"
TOKEN_EXPECTED_VALUE_UNAVAILABLE = "EXPECTED_VALUE_UNAVAILABLE"
TOKEN_PRODUCTION_TARGET_NOT_ESTABLISHED = "PRODUCTION_TARGET_NOT_ESTABLISHED"
TOKEN_PRODUCTION_TARGET_MAPPING_DUPLICATE = "PRODUCTION_TARGET_MAPPING_DUPLICATE"
TOKEN_PRODUCTION_TARGET_NOT_CANONICAL = "PRODUCTION_TARGET_NOT_CANONICAL"
TOKEN_REGISTRY_SOURCE_NOT_CANONICAL = "REGISTRY_SOURCE_NOT_CANONICAL"
TOKEN_EXPECTATION_DEFINITION_DUPLICATE = "EXPECTATION_DEFINITION_DUPLICATE"
TOKEN_EXPECTATION_VOCABULARY_MISMATCH = "EXPECTATION_VOCABULARY_MISMATCH"
TOKEN_EXPECTATION_IDENTITY_MISMATCH = "EXPECTATION_IDENTITY_MISMATCH"
TOKEN_EXPECTATION_DIGEST_MISMATCH = "EXPECTATION_DIGEST_MISMATCH"
TOKEN_EXPECTATION_INCOMPLETE = "EXPECTATION_INCOMPLETE"
TOKEN_EMPTY_REQUIRED_INVARIANT_SET = "EMPTY_REQUIRED_INVARIANT_SET"
TOKEN_INCOMPLETE_REQUIRED_INVARIANT_SET = "INCOMPLETE_REQUIRED_INVARIANT_SET"
TOKEN_EXTRA_PLAN_VERIFICATION_REQUIREMENT = "EXTRA_PLAN_VERIFICATION_REQUIREMENT"
TOKEN_PLAN_STEP_NOT_CANONICAL = "PLAN_STEP_NOT_CANONICAL"
TOKEN_PLAN_RENDER_CLASSIFICATION_MISMATCH = "PLAN_RENDER_CLASSIFICATION_MISMATCH"
TOKEN_PLAN_CONTENT_UNSUPPORTED = "PLAN_CONTENT_UNSUPPORTED"
TOKEN_REGISTRY_AUTHORITY_CLASS_NOT_ADMITTED = "REGISTRY_AUTHORITY_CLASS_NOT_ADMITTED"

CLOSED_FAILURE_CODES = frozenset({
    TOKEN_RESOLVER_INPUT_STRUCTURE_INVALID,
    TOKEN_RESOLVER_INTERNAL_FAILURE,
    TOKEN_EXPECTED_VALUE_UNAVAILABLE,
    TOKEN_PRODUCTION_TARGET_NOT_ESTABLISHED,
    TOKEN_PRODUCTION_TARGET_MAPPING_DUPLICATE,
    TOKEN_PRODUCTION_TARGET_NOT_CANONICAL,
    TOKEN_REGISTRY_SOURCE_NOT_CANONICAL,
    TOKEN_EXPECTATION_DEFINITION_DUPLICATE,
    TOKEN_EXPECTATION_VOCABULARY_MISMATCH,
    TOKEN_EXPECTATION_IDENTITY_MISMATCH,
    TOKEN_EXPECTATION_DIGEST_MISMATCH,
    TOKEN_EXPECTATION_INCOMPLETE,
    TOKEN_EMPTY_REQUIRED_INVARIANT_SET,
    TOKEN_INCOMPLETE_REQUIRED_INVARIANT_SET,
    TOKEN_EXTRA_PLAN_VERIFICATION_REQUIREMENT,
    TOKEN_PLAN_STEP_NOT_CANONICAL,
    TOKEN_PLAN_RENDER_CLASSIFICATION_MISMATCH,
    TOKEN_PLAN_CONTENT_UNSUPPORTED,
    TOKEN_REGISTRY_AUTHORITY_CLASS_NOT_ADMITTED,
})

class ReasonClass(str, Enum):
    SATISFIED = "SATISFIED"
    EVALUATED_MISMATCH = "EVALUATED_MISMATCH"
    EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"
    BINDING_ABSENT = "BINDING_ABSENT"
    AUTHORITY_ABSENT = "AUTHORITY_ABSENT"
    INTERNAL_FAILURE = "INTERNAL_FAILURE"


class InvariantState(str, Enum):
    SATISFIED = "SATISFIED"
    NOT_SATISFIED = "NOT_SATISFIED"
    UNKNOWN = "UNKNOWN"
    MISSING = "MISSING"


class SemanticState(str, Enum):
    SATISFIED = "SATISFIED"
    NOT_SATISFIED = "NOT_SATISFIED"
    UNKNOWN = "UNKNOWN"
    INVALID_OBSERVATION = "INVALID_OBSERVATION"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"


class OverallState(str, Enum):
    SATISFIED = "SATISFIED"
    NOT_SATISFIED = "NOT_SATISFIED"
    UNKNOWN = "UNKNOWN"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"


@dataclass(frozen=True)
class EntryVocabulary:
    entry_name: str
    entry_version: int
    task_class: str
    fragment_ids: Tuple[str, ...]
    invariant_names: Tuple[str, ...]
    parameter_names: Tuple[str, ...]
    parameter_kinds: Tuple[Tuple[str, str], ...]
    vocabulary_digest: str = ""


@dataclass(frozen=True)
class WitnessRef:
    ref: str
    expected_state: str
    expected_code: Optional[str]
    dimension: str


@dataclass(frozen=True)
class SemanticInvariantDefinition:
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
    definition_digest: str
    witness_positive: Optional[WitnessRef]
    witness_negative: Optional[WitnessRef]
    witness_lossy: Optional[WitnessRef]
    non_claim: str


@dataclass(frozen=True)
class TaskTargetMapping:
    entry_name: str
    entry_version: int
    task_class: str
    production_target_id: str


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
    target_digest: str
    non_claim: str


@dataclass(frozen=True)
class ResolvedObservable:
    concrete_path: str
    value: Any


@dataclass(frozen=True)
class InvariantVerificationResult:
    invariant_name: str
    definition_id: str
    definition_revision: int
    definition_digest: str
    authority_class: str
    subject_scope: Tuple[str, ...]
    expected_value_identity: str
    comparison: str
    admissible_value_type: str
    observed_path_patterns: Tuple[str, ...]
    value_state: str
    resolved_observables: Tuple[ResolvedObservable, ...]
    observation_bound: bool
    observation_identity: Any
    invariant_state: str
    mismatch_reason: Optional[str]
    evidence_identity: str
    invariant_result_digest: str


class SemanticExpectationRefusal(ValueError):
    def __init__(
        self,
        *,
        primary_code: str,
        stage: int,
        reason_class: ReasonClass,
        failure_codes: Sequence[str],
        semantic_state: SemanticState = SemanticState.NOT_ESTABLISHED,
        overall_state: OverallState = OverallState.NOT_ESTABLISHED,
        invariant_states: Optional[Mapping[str, InvariantState]] = None,
        detail_category: Optional[str] = None,
    ) -> None:
        if primary_code not in CLOSED_FAILURE_CODES:
            raise ValueError(f"unknown refusal token: {primary_code}")
        self.primary_code = primary_code
        self.stage = stage
        self.reason_class = reason_class
        self.failure_codes = tuple(sorted(set(failure_codes)))
        self.semantic_state = semantic_state
        self.overall_state = overall_state
        self.invariant_states = dict(invariant_states or {})
        self.detail_category = detail_category
        super().__init__(primary_code)


# Closed v1 vocabulary copied from planning/m12/catalog.py.
EXPECTATION_VOCABULARY = (
    EntryVocabulary(
        "unreal.scene-prepare", 1, "scene-prepare",
        ("scene_setup",), ("scene_initialized",),
        ("twin_id",), (("twin_id", "string"),),
    ),
    EntryVocabulary(
        "unreal.environment-configure", 1, "environment-configure",
        ("environment_setup",), ("environment_configured",),
        ("twin_id", "environment_style"),
        (("twin_id", "string"), ("environment_style", "string")),
    ),
    EntryVocabulary(
        "unreal.camera-configure", 1, "camera-configure",
        ("scene_setup", "camera_setup"),
        ("scene_initialized", "cameras_configured"),
        ("twin_id", "camera_slots"),
        (("twin_id", "string"), ("camera_slots", "json")),
    ),
    EntryVocabulary(
        "unreal.lighting-configure", 1, "lighting-configure",
        ("scene_setup", "lighting_setup"),
        ("scene_initialized", "lighting_configured"),
        ("twin_id", "lighting_rig"),
        (("twin_id", "string"), ("lighting_rig", "json")),
    ),
    EntryVocabulary(
        "unreal.sequence-configure", 1, "sequence-configure",
        ("scene_setup", "camera_setup", "sequence_setup"),
        ("scene_initialized", "cameras_configured", "sequence_configured"),
        ("twin_id", "sequence_name", "frame_start", "frame_end"),
        (("twin_id", "string"), ("sequence_name", "string"),
         ("frame_start", "int"), ("frame_end", "int")),
    ),
    EntryVocabulary(
        "unreal.render-execute", 1, "render-execute",
        ("scene_setup", "camera_setup", "sequence_setup", "render_setup"),
        ("scene_initialized", "cameras_configured", "sequence_configured", "render_configured"),
        ("twin_id", "sequence_name"),
        (("twin_id", "string"), ("sequence_name", "string")),
    ),
    EntryVocabulary(
        "unreal.artifact-validate", 1, "artifact-validate",
        ("scene_setup",), ("scene_initialized",),
        ("twin_id", "artifact_ref"),
        (("twin_id", "string"), ("artifact_ref", "string")),
    ),
)

# R2-A deliberately has no production target authority.
PRODUCTION_TARGETS: Tuple[ProductionTargetSpec, ...] = ()
PRODUCTION_TARGET_BY_TASK: Tuple[TaskTargetMapping, ...] = ()

_REGISTERED = frozenset()
_EXPECTATION_NAMES = tuple(sorted({
    name for row in EXPECTATION_VOCABULARY for name in row.invariant_names
}))


def _domain_a_digest(value: Any) -> str:
    return hashlib.sha256(domain_a_bytes(value)).hexdigest()


def _safe_int(value: Any) -> bool:
    return type(value) is int

def _contains_finite_float(value: Any, *, seen: Optional[set[int]] = None) -> bool:
    if seen is None:
        seen = set()
    if isinstance(value, float):
        return True
    if value is None or isinstance(value, (str, bool, int)):
        return False
    if is_dataclass(value):
        object_id = id(value)
        if object_id in seen:
            return False
        seen.add(object_id)
        try:
            return any(
                _contains_finite_float(getattr(value, field.name), seen=seen)
                for field in fields(value)
            )
        finally:
            seen.remove(object_id)
    if isinstance(value, Mapping):
        object_id = id(value)
        if object_id in seen:
            return False
        seen.add(object_id)
        try:
            return any(
                _contains_finite_float(child, seen=seen)
                for child in value.values()
            )
        finally:
            seen.remove(object_id)
    if isinstance(value, (list, tuple)):
        return any(_contains_finite_float(child, seen=seen) for child in value)
    return False


def _aggregate_stage_rows(rows: Sequence[Tuple[int, str]]) -> Tuple[str, Tuple[str, ...]]:
    if not rows:
        raise ValueError("cannot aggregate an empty stage")
    ordered = sorted(rows, key=lambda item: item[0])
    primary = ordered[0][1]
    codes = tuple(sorted({code for _, code in ordered}))
    if primary not in codes:
        raise AssertionError("primary code missing from aggregate")
    return primary, codes



def _preflight_value(
    value: Any,
    *,
    path: str,
    depth: int,
    budget: list[int],
    seen: set[int],
) -> Optional[str]:
    if depth > PREFLIGHT_MAX_DEPTH:
        return "F6"
    budget[0] -= 1
    if budget[0] < 0:
        return "F6"

    if value is None or isinstance(value, (str, bool, int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            return "F5"
        if isinstance(value, str):
            try:
                value.encode("utf-8")
            except UnicodeEncodeError:
                return "F7"
        if _safe_int(value):
            try:
                str(value)
            except Exception:
                return "F8"
        return None

    if is_dataclass(value):
        obj_id = id(value)
        if obj_id in seen:
            return "F6"
        seen.add(obj_id)
        try:
            for field in fields(value):
                err = _preflight_value(
                    getattr(value, field.name),
                    path=f"{path}.{field.name}",
                    depth=depth + 1,
                    budget=budget,
                    seen=seen,
                )
                if err:
                    return err
        except Exception:
            return "F4"
        finally:
            seen.remove(obj_id)
        return None

    if isinstance(value, Mapping):
        obj_id = id(value)
        if obj_id in seen:
            return "F6"
        seen.add(obj_id)
        try:
            for key, child in value.items():
                if not isinstance(key, str):
                    return "F4"
                err = _preflight_value(
                    child, path=f"{path}.{key}", depth=depth + 1,
                    budget=budget, seen=seen,
                )
                if err:
                    return err
        except Exception:
            return "F4"
        finally:
            seen.remove(obj_id)
        return None

    if isinstance(value, (list, tuple, frozenset)):
        obj_id = id(value)
        if obj_id in seen:
            return "F6"
        seen.add(obj_id)
        try:
            children = value
            if isinstance(value, frozenset):
                children = tuple(sorted(value, key=repr))
            for index, child in enumerate(children):
                err = _preflight_value(
                    child, path=f"{path}[{index}]", depth=depth + 1,
                    budget=budget, seen=seen,
                )
                if err:
                    return err
        except Exception:
            return "F4"
        finally:
            seen.remove(obj_id)
        return None

    return "F4"


def structural_preflight(
    source_task: UnrealProductionTaskDefinition,
    plan: UnrealExecutionPlan,
) -> Optional[str]:
    if type(source_task) is not UnrealProductionTaskDefinition:
        return "F1"
    if type(plan) is not UnrealExecutionPlan:
        return "F1"
    budget = [PREFLIGHT_NODE_BUDGET]
    err = _preflight_value(
        source_task, path="source_task", depth=0, budget=budget, seen=set()
    )
    if err:
        return err
    return _preflight_value(
        plan, path="plan", depth=0, budget=budget, seen=set()
    )


def _lookup_vocabulary(task: UnrealProductionTaskDefinition) -> EntryVocabulary:
    for row in EXPECTATION_VOCABULARY:
        if (
            row.entry_name == task.canonical_task_id
            and row.entry_version == task.task_version
        ):
            if row.task_class != task.task_class:
                break
            return row
    raise SemanticExpectationRefusal(
        primary_code=TOKEN_EXPECTATION_VOCABULARY_MISMATCH,
        stage=3,
        reason_class=ReasonClass.BINDING_ABSENT,
        failure_codes=(TOKEN_EXPECTATION_VOCABULARY_MISMATCH,),
        semantic_state=SemanticState.NOT_ESTABLISHED,
        overall_state=OverallState.NOT_ESTABLISHED,
    )


def _validate_exact_set(
    task: UnrealProductionTaskDefinition,
    plan: UnrealExecutionPlan,
    vocabulary: EntryVocabulary,
) -> None:
    required = frozenset(task.target_state.invariant_names)
    carried = frozenset(
        requirement
        for step in plan.steps
        for requirement in step.verification_requirements
    )
    allowed = set(vocabulary.invariant_names)
    if not required:
        raise SemanticExpectationRefusal(
            primary_code=TOKEN_EMPTY_REQUIRED_INVARIANT_SET,
            stage=1,
            reason_class=ReasonClass.BINDING_ABSENT,
            failure_codes=(TOKEN_EMPTY_REQUIRED_INVARIANT_SET,),
        )
    if required - allowed:
        raise SemanticExpectationRefusal(
            primary_code=TOKEN_EXPECTATION_VOCABULARY_MISMATCH,
            stage=3,
            reason_class=ReasonClass.BINDING_ABSENT,
            failure_codes=(TOKEN_EXPECTATION_VOCABULARY_MISMATCH,),
        )
    if required - carried:
        raise SemanticExpectationRefusal(
            primary_code=TOKEN_INCOMPLETE_REQUIRED_INVARIANT_SET,
            stage=3,
            reason_class=ReasonClass.BINDING_ABSENT,
            failure_codes=(TOKEN_INCOMPLETE_REQUIRED_INVARIANT_SET,),
        )
    if carried - required:
        raise SemanticExpectationRefusal(
            primary_code=TOKEN_EXTRA_PLAN_VERIFICATION_REQUIREMENT,
            stage=3,
            reason_class=ReasonClass.BINDING_ABSENT,
            failure_codes=(TOKEN_EXTRA_PLAN_VERIFICATION_REQUIREMENT,),
        )
    canonical_fragments = set(vocabulary.fragment_ids)
    if any(step.semantic_operation not in canonical_fragments for step in plan.steps):
        raise SemanticExpectationRefusal(
            primary_code=TOKEN_PLAN_STEP_NOT_CANONICAL,
            stage=3,
            reason_class=ReasonClass.BINDING_ABSENT,
            failure_codes=(TOKEN_PLAN_STEP_NOT_CANONICAL,),
        )
    if plan.render_plan != is_render_task_class(task.task_class):
        raise SemanticExpectationRefusal(
            primary_code=TOKEN_PLAN_RENDER_CLASSIFICATION_MISMATCH,
            stage=3,
            reason_class=ReasonClass.BINDING_ABSENT,
            failure_codes=(TOKEN_PLAN_RENDER_CLASSIFICATION_MISMATCH,),
        )


def compute_plan_content_digest(plan: UnrealExecutionPlan) -> str:
    # M12.3 owns this canonicalization; M12.6 calls the existing recipe unchanged.
    return _canonical_sha256(plan.to_json_compatible(), "execution_plan")


def _recompute_registry_source_digest() -> str:
    return _domain_a_digest({
        "schema": "m12.6-registry-v1",
        "definitions": [_canonical_definition_projection(d) for d in _DEFINITIONS],
    })


def _recompute_target_table_digest() -> str:
    return _domain_a_digest({
        "schema": "m12.6-target-table-v1",
        "revision": TARGET_TABLE_REVISION,
        "entries": [
            {
                "production_target_id": t.production_target_id,
                "target_revision": t.target_revision,
                "target_digest": t.target_digest,
            }
            for t in sorted(PRODUCTION_TARGETS, key=lambda x: domain_a_bytes(x.production_target_id))
        ],
        "mappings": [
            [r.entry_name, r.entry_version, r.task_class, r.production_target_id]
            for r in sorted(
                PRODUCTION_TARGET_BY_TASK,
                key=lambda x: domain_a_bytes(
                    f"{x.entry_name}|{x.entry_version}|{x.task_class}|{x.production_target_id}"
                ),
            )
        ],
    })


def _authority_integrity() -> None:
    if _recompute_registry_source_digest() != REGISTRY_SOURCE_DIGEST:
        raise SemanticExpectationRefusal(
            primary_code=TOKEN_REGISTRY_SOURCE_NOT_CANONICAL,
            stage=2,
            reason_class=ReasonClass.AUTHORITY_ABSENT,
            failure_codes=(TOKEN_REGISTRY_SOURCE_NOT_CANONICAL,),
        )
    if _recompute_target_table_digest() != TARGET_TABLE_DIGEST:
        raise SemanticExpectationRefusal(
            primary_code=TOKEN_PRODUCTION_TARGET_NOT_CANONICAL,
            stage=2,
            reason_class=ReasonClass.AUTHORITY_ABSENT,
            failure_codes=(TOKEN_PRODUCTION_TARGET_NOT_CANONICAL,),
        )

    names = [d.invariant_name for d in _DEFINITIONS]
    if len(names) != len(set(names)):
        raise SemanticExpectationRefusal(
            primary_code=TOKEN_EXPECTATION_DEFINITION_DUPLICATE,
            stage=2,
            reason_class=ReasonClass.AUTHORITY_ABSENT,
            failure_codes=(TOKEN_EXPECTATION_DEFINITION_DUPLICATE,),
        )
    rows = [
        (r.entry_name, r.entry_version, r.task_class)
        for r in PRODUCTION_TARGET_BY_TASK
    ]
    if len(rows) != len(set(rows)):
        raise SemanticExpectationRefusal(
            primary_code=TOKEN_PRODUCTION_TARGET_MAPPING_DUPLICATE,
            stage=2,
            reason_class=ReasonClass.AUTHORITY_ABSENT,
            failure_codes=(TOKEN_PRODUCTION_TARGET_MAPPING_DUPLICATE,),
        )
    for definition in _DEFINITIONS:
        if definition.authority_class != "CODE_CONSTANT":
            raise SemanticExpectationRefusal(
                primary_code=TOKEN_REGISTRY_AUTHORITY_CLASS_NOT_ADMITTED,
                stage=2,
                reason_class=ReasonClass.AUTHORITY_ABSENT,
                failure_codes=(TOKEN_REGISTRY_AUTHORITY_CLASS_NOT_ADMITTED,),
            )


def _empty_definition(name: str) -> SemanticInvariantDefinition:
    return SemanticInvariantDefinition(
        invariant_name=name,
        definition_revision=1,
        definition_status="DEFERRED",
        authority_class="CODE_CONSTANT",
        observable_paths=(),
        subject_scope=(),
        comparison="EQUALS",
        admissible_value_type="STR",
        expected_value_source="CODE_CONSTANT",
        expected_value=None,
        target_binding="NONE",
        missing_behavior="UNKNOWN_EVIDENCE_INSUFFICIENT",
        unsupported_behavior="UNKNOWN_EVIDENCE_INSUFFICIENT",
        definition_digest="",
        witness_positive=None,
        witness_negative=None,
        witness_lossy=None,
        non_claim="SATISFIED is unavailable until R2-B authority and witnesses exist.",
    )


_DEFINITIONS = tuple(_empty_definition(name) for name in _EXPECTATION_NAMES)


def _canonical_definition_projection(definition: SemanticInvariantDefinition) -> Mapping[str, Any]:
    return {
        "schema": "m12.6-expectation-definition-v1",
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
        "witness_positive": None,
        "witness_negative": None,
        "witness_lossy": None,
    }


def _with_definition_digests(
    definitions: Sequence[SemanticInvariantDefinition],
) -> Tuple[SemanticInvariantDefinition, ...]:
    out = []
    for definition in definitions:
        digest = _domain_a_digest(_canonical_definition_projection(definition))
        out.append(
            SemanticInvariantDefinition(
                **{
                    **definition.__dict__,
                    "definition_digest": digest,
                }
            )
        )
    return tuple(out)


_DEFINITIONS = _with_definition_digests(_DEFINITIONS)
DEFINITIONS_BY_NAME = {d.invariant_name: d for d in _DEFINITIONS}


def _vocabulary_digest(row: EntryVocabulary) -> str:
    return _domain_a_digest({
        "schema": "m12.6-vocabulary-v1",
        "entry_name": row.entry_name,
        "entry_version": row.entry_version,
        "task_class": row.task_class,
        "fragment_ids": list(row.fragment_ids),
        "invariant_names": list(row.invariant_names),
        "parameter_names": list(row.parameter_names),
        "parameter_kinds": [list(v) for v in row.parameter_kinds],
    })


EXPECTATION_VOCABULARY = tuple(
    EntryVocabulary(**{**row.__dict__, "vocabulary_digest": _vocabulary_digest(row)})
    for row in EXPECTATION_VOCABULARY
)
EXPECTATION_VOCABULARY_BY_KEY = {
    (r.entry_name, r.entry_version): r for r in EXPECTATION_VOCABULARY
}

REGISTRY_REVISION = 1
TARGET_TABLE_REVISION = 1
REGISTRY_SOURCE_DIGEST = _domain_a_digest({
    "schema": "m12.6-registry-v1",
    "definitions": [_canonical_definition_projection(d) for d in _DEFINITIONS],
})
TARGET_TABLE_DIGEST = _domain_a_digest({
    "schema": "m12.6-target-table-v1",
    "revision": TARGET_TABLE_REVISION,
    "entries": [],
})


def compute_expectation_identity(
    *,
    vocabulary: EntryVocabulary,
    task: UnrealProductionTaskDefinition,
    plan: UnrealExecutionPlan,
    target: Optional[ProductionTargetSpec],
) -> Mapping[str, Any]:
    return {
        "expectation_contract_revision": EXPECTATION_CONTRACT_REVISION,
        "resolver_revision": RESOLVER_REVISION,
        "registry_revision": REGISTRY_REVISION,
        "registry_digest": REGISTRY_SOURCE_DIGEST,
        "target_table_revision": TARGET_TABLE_REVISION,
        "target_table_digest": TARGET_TABLE_DIGEST,
        "production_target_id": None if target is None else target.production_target_id,
        "target_revision": None if target is None else target.target_revision,
        "target_digest": None if target is None else target.target_digest,
        "task_identity": task.canonical_task_id,
        "task_version": task.task_version,
        "digital_twin_id": task.digital_twin_id,
        "catalog_entry_name": vocabulary.entry_name,
        "catalog_entry_version": vocabulary.entry_version,
        "vocabulary_digest": vocabulary.vocabulary_digest,
        "source_content_digest": compute_source_content_digest(task),
        "plan_id": plan.plan_id,
        "plan_content_digest": compute_plan_content_digest(plan),
        "render_task": is_render_task_class(task.task_class),
        "required_invariant_names": sorted(task.target_state.invariant_names),
        "invariant_expectations_digest": _domain_a_digest([
            {
                "invariant_name": name,
                "definition_digest": DEFINITIONS_BY_NAME[name].definition_digest,
                "status": DEFINITIONS_BY_NAME[name].definition_status,
            }
            for name in sorted(task.target_state.invariant_names)
        ]),
    }


def compute_expectation_digest(identity: Mapping[str, Any]) -> str:
    return _domain_a_digest({
        "schema": "m12.6-expectation-v1",
        **dict(identity),
    })


def _target_lookup(
    vocabulary: EntryVocabulary,
) -> ProductionTargetSpec:
    matches = [
        row for row in PRODUCTION_TARGET_BY_TASK
        if (
            row.entry_name == vocabulary.entry_name
            and row.entry_version == vocabulary.entry_version
            and row.task_class == vocabulary.task_class
        )
    ]
    if len(matches) > 1:
        raise SemanticExpectationRefusal(
            primary_code=TOKEN_PRODUCTION_TARGET_MAPPING_DUPLICATE,
            stage=2,
            reason_class=ReasonClass.AUTHORITY_ABSENT,
            failure_codes=(TOKEN_PRODUCTION_TARGET_MAPPING_DUPLICATE,),
        )
    if not matches:
        raise SemanticExpectationRefusal(
            primary_code=TOKEN_PRODUCTION_TARGET_NOT_ESTABLISHED,
            stage=4,
            reason_class=ReasonClass.AUTHORITY_ABSENT,
            failure_codes=(TOKEN_PRODUCTION_TARGET_NOT_ESTABLISHED,),
        )
    target_id = matches[0].production_target_id
    for target in PRODUCTION_TARGETS:
        if target.production_target_id == target_id:
            return target
    raise SemanticExpectationRefusal(
        primary_code=TOKEN_PRODUCTION_TARGET_NOT_CANONICAL,
        stage=2,
        reason_class=ReasonClass.AUTHORITY_ABSENT,
        failure_codes=(TOKEN_PRODUCTION_TARGET_NOT_CANONICAL,),
    )


def _plan_identity_checks(
    task: UnrealProductionTaskDefinition, plan: UnrealExecutionPlan
) -> None:
    if compute_source_content_digest(task) != plan.source_content_digest:
        raise SemanticExpectationRefusal(
            primary_code=TOKEN_EXPECTATION_IDENTITY_MISMATCH,
            stage=3, reason_class=ReasonClass.BINDING_ABSENT,
            failure_codes=(TOKEN_EXPECTATION_IDENTITY_MISMATCH,),
        )
    if plan.source_task_id != task.canonical_task_id or plan.source_task_version != task.task_version:
        raise SemanticExpectationRefusal(
            primary_code=TOKEN_EXPECTATION_IDENTITY_MISMATCH,
            stage=3, reason_class=ReasonClass.BINDING_ABSENT,
            failure_codes=(TOKEN_EXPECTATION_IDENTITY_MISMATCH,),
        )
    if plan.digital_twin_id != task.digital_twin_id:
        raise SemanticExpectationRefusal(
            primary_code=TOKEN_EXPECTATION_IDENTITY_MISMATCH,
            stage=3, reason_class=ReasonClass.BINDING_ABSENT,
            failure_codes=(TOKEN_EXPECTATION_IDENTITY_MISMATCH,),
        )
    from planning.m12.execution_plan import _build_plan_id
    expected_plan_id = _build_plan_id(
        task.canonical_task_id,
        task.task_version,
        tuple(step.semantic_operation for step in plan.steps),
        plan.source_content_digest,
    )
    if plan.plan_id != expected_plan_id:
        raise SemanticExpectationRefusal(
            primary_code=TOKEN_EXPECTATION_IDENTITY_MISMATCH,
            stage=3, reason_class=ReasonClass.BINDING_ABSENT,
            failure_codes=(TOKEN_EXPECTATION_IDENTITY_MISMATCH,),
        )


def resolve_semantic_expectation(
    *,
    source_task: UnrealProductionTaskDefinition,
    plan: UnrealExecutionPlan,
) -> "SemanticExpectation | SemanticExpectationRefusal":
    preflight_category = structural_preflight(source_task, plan)
    if preflight_category:
        raise SemanticExpectationRefusal(
            primary_code=TOKEN_RESOLVER_INPUT_STRUCTURE_INVALID,
            stage=1,
            reason_class=ReasonClass.BINDING_ABSENT,
            failure_codes=(TOKEN_RESOLVER_INPUT_STRUCTURE_INVALID,),
            detail_category=preflight_category,
        )

    try:
        # S2 authority revalidation precedes all supplied-artifact binding checks.
        _authority_integrity()

        # R2-A deliberately keeps all definitions DEFERRED, so S4 is always
        # the final reachable stage for valid authority/input pairs.
        vocabulary = _lookup_vocabulary(source_task)
        _plan_identity_checks(source_task, plan)
        _validate_exact_set(source_task, plan, vocabulary)

        if _contains_finite_float(plan):
            raise SemanticExpectationRefusal(
                primary_code=TOKEN_PLAN_CONTENT_UNSUPPORTED,
                stage=1,
                reason_class=ReasonClass.BINDING_ABSENT,
                failure_codes=(TOKEN_PLAN_CONTENT_UNSUPPORTED,),
            )

        # Continue with the R2-A coverage checks.
        # the deciding stage. We evaluate both coverage conditions, then apply
        # the R6 row precedence/aggregation rule.
        applicable = []
        required = sorted(source_task.target_state.invariant_names)
        if any(DEFINITIONS_BY_NAME[name].definition_status != "REGISTERED" for name in required):
            applicable.append((6, TOKEN_EXPECTED_VALUE_UNAVAILABLE))
        try:
            target = _target_lookup(vocabulary)
        except SemanticExpectationRefusal as target_exc:
            if target_exc.primary_code == TOKEN_PRODUCTION_TARGET_NOT_ESTABLISHED:
                applicable.append((22, TOKEN_PRODUCTION_TARGET_NOT_ESTABLISHED))
            else:
                raise
            target = None

        if applicable:
            primary, codes = _aggregate_stage_rows(applicable)
            states = {name: InvariantState.UNKNOWN for name in required}
            raise SemanticExpectationRefusal(
                primary_code=primary,
                stage=4,
                reason_class=ReasonClass.AUTHORITY_ABSENT,
                failure_codes=codes,
                semantic_state=SemanticState.NOT_ESTABLISHED,
                overall_state=OverallState.NOT_ESTABLISHED,
                invariant_states=states,
            )

        identity = compute_expectation_identity(
            vocabulary=vocabulary, task=source_task, plan=plan, target=target
        )
        validate_expectation_identity(identity)
        digest = compute_expectation_digest(identity)
        return {
            "expectation_contract_revision": EXPECTATION_CONTRACT_REVISION,
            "resolver_revision": RESOLVER_REVISION,
            **identity,
            "invariant_expectations": (),
            "expectation_digest": digest,
            "origin_status": "NOT_ESTABLISHED",
        }
    except SemanticExpectationRefusal:
        raise
    except Exception as exc:
        raise SemanticExpectationRefusal(
            primary_code=TOKEN_RESOLVER_INTERNAL_FAILURE,
            stage=0,
            reason_class=ReasonClass.INTERNAL_FAILURE,
            failure_codes=(TOKEN_RESOLVER_INTERNAL_FAILURE,),
            semantic_state=SemanticState.UNKNOWN,
            overall_state=OverallState.UNKNOWN,
        ) from exc



# R6 Part XV classifier: one stage, one reason class per row/token.
FAILURE_CLASSIFIER = {
    TOKEN_RESOLVER_INPUT_STRUCTURE_INVALID: (1, ReasonClass.BINDING_ABSENT),
    TOKEN_RESOLVER_INTERNAL_FAILURE: (0, ReasonClass.INTERNAL_FAILURE),
    TOKEN_EXPECTED_VALUE_UNAVAILABLE: (4, ReasonClass.AUTHORITY_ABSENT),
    TOKEN_EXPECTATION_IDENTITY_MISMATCH: (3, ReasonClass.BINDING_ABSENT),
    TOKEN_EXPECTATION_INCOMPLETE: (3, ReasonClass.BINDING_ABSENT),
    TOKEN_REGISTRY_SOURCE_NOT_CANONICAL: (2, ReasonClass.AUTHORITY_ABSENT),
    TOKEN_PRODUCTION_TARGET_NOT_CANONICAL: (2, ReasonClass.AUTHORITY_ABSENT),
    TOKEN_EXPECTATION_DEFINITION_DUPLICATE: (2, ReasonClass.AUTHORITY_ABSENT),
    TOKEN_PRODUCTION_TARGET_MAPPING_DUPLICATE: (2, ReasonClass.AUTHORITY_ABSENT),
    TOKEN_EXPECTATION_VOCABULARY_MISMATCH: (3, ReasonClass.BINDING_ABSENT),
    TOKEN_PLAN_STEP_NOT_CANONICAL: (3, ReasonClass.BINDING_ABSENT),
    TOKEN_EMPTY_REQUIRED_INVARIANT_SET: (3, ReasonClass.BINDING_ABSENT),
    TOKEN_INCOMPLETE_REQUIRED_INVARIANT_SET: (3, ReasonClass.BINDING_ABSENT),
    TOKEN_EXTRA_PLAN_VERIFICATION_REQUIREMENT: (3, ReasonClass.BINDING_ABSENT),
    TOKEN_PLAN_RENDER_CLASSIFICATION_MISMATCH: (3, ReasonClass.BINDING_ABSENT),
    TOKEN_PRODUCTION_TARGET_NOT_ESTABLISHED: (4, ReasonClass.AUTHORITY_ABSENT),
    TOKEN_PLAN_CONTENT_UNSUPPORTED: (1, ReasonClass.BINDING_ABSENT),
    TOKEN_REGISTRY_AUTHORITY_CLASS_NOT_ADMITTED: (2, ReasonClass.AUTHORITY_ABSENT),
    "IDENTITY_MISMATCH": (3, ReasonClass.BINDING_ABSENT),
    "OBSERVATION_IDENTITY_NOT_TRANSPORT_ROOTED": (5, ReasonClass.EVIDENCE_INSUFFICIENT),
    "OBSERVATION_CORRELATION_MISMATCH": (5, ReasonClass.EVIDENCE_INSUFFICIENT),
    "EXTRACTION_CONTRACT_REVISION_MISMATCH": (5, ReasonClass.EVIDENCE_INSUFFICIENT),
    "OBSERVATION_SCOPE_DIVERGENCE": (5, ReasonClass.EVIDENCE_INSUFFICIENT),
    "EXPECTATION_SCOPE_NOT_OBSERVED": (5, ReasonClass.EVIDENCE_INSUFFICIENT),
    "CONTRADICTORY": (5, ReasonClass.EVIDENCE_INSUFFICIENT),
    "EXPECTATION_CONTRADICTORY": (5, ReasonClass.EVIDENCE_INSUFFICIENT),
    "RENDER_TASK_CORRESPONDENCE_NOT_DECIDED": (4, ReasonClass.AUTHORITY_ABSENT),
    "REQUEST_DIGEST_AGREEMENT_NOT_ESTABLISHED": (4, ReasonClass.AUTHORITY_ABSENT),
    "SEQUENCE_AGREEMENT_NOT_ESTABLISHED": (4, ReasonClass.AUTHORITY_ABSENT),
    "RENDER_EVIDENCE_MISSING": (4, ReasonClass.AUTHORITY_ABSENT),
}


def classify_failure(code: str) -> Tuple[int, ReasonClass]:
    try:
        return FAILURE_CLASSIFIER[code]
    except KeyError as exc:
        raise ValueError(f"failure code is outside the closed R2-A classifier: {code!r}") from exc


def aggregate_stage_failures(rows: Sequence[Tuple[int, str]]) -> Tuple[str, ReasonClass, Tuple[str, ...]]:
    if not rows:
        raise ValueError("cannot aggregate empty stage")
    normalized = sorted(rows, key=lambda item: item[0])
    stage, _ = classify_failure(normalized[0][1])
    classes = {classify_failure(code)[1] for _, code in normalized}
    for row, code in normalized:
        row_stage, _row_class = classify_failure(code)
        if row_stage != stage:
            raise ValueError("rows from different stages cannot be aggregated")
    if len(classes) != 1:
        raise ValueError("reason class is not homogeneous within the stage")
    primary = normalized[0][1]
    codes = tuple(sorted({code for _, code in normalized}, key=lambda value: domain_a_bytes(value)))
    return primary, next(iter(classes)), codes


def build_r2a_result_state(
    refusal: SemanticExpectationRefusal,
    *,
    render_task: bool,
) -> Mapping[str, Any]:
    """Closed refusal-only aggregate state for R2-A."""
    if refusal.stage >= 5:
        raise ValueError("R2-A result cannot emit S5/S6 state")
    if refusal.semantic_state not in {
        SemanticState.UNKNOWN, SemanticState.NOT_ESTABLISHED
    }:
        raise ValueError("R2-A semantic state outside reachable subset")
    if refusal.overall_state not in {
        OverallState.UNKNOWN, OverallState.NOT_ESTABLISHED
    }:
        raise ValueError("R2-A overall state outside reachable subset")
    return {
        "semantic_state": refusal.semantic_state.value,
        "overall_state": refusal.overall_state.value,
        "outcome_reason_class": refusal.reason_class.value,
        "render_state": "NOT_VERIFIED" if render_task else "NOT_REQUIRED",
        "failure_codes": refusal.failure_codes,
    }


EVIDENCE_IDENTITY_KEYS = frozenset({
    "schema", "invariant_name", "definition_id", "definition_revision",
    "definition_digest", "authority_class", "comparison", "admissible_value_type",
    "subject_scope", "observed_path_patterns", "value_state", "resolved_observables",
    "observation_bound", "observation_request_id", "observation_scope",
    "canonical_state_digest",
})
INVARIANT_RESULT_KEYS = frozenset({
    "invariant_name", "definition_id", "definition_revision", "definition_digest",
    "authority_class", "subject_scope", "expected_value_identity", "comparison",
    "admissible_value_type", "observed_path_patterns", "value_state",
    "resolved_observables", "observation_bound", "observation_identity",
    "invariant_state", "mismatch_reason", "evidence_identity",
})
RESULT_DIGEST_KEYS = frozenset({
    "schema", "verifier_revision", "expectation_contract_revision", "resolver_revision",
    "registry_revision", "registry_digest", "target_table_revision", "target_table_digest",
    "production_target_id", "target_revision", "target_digest", "task_identity", "task_version",
    "digital_twin_id", "catalog_entry_name", "catalog_entry_version", "vocabulary_digest",
    "plan_id", "source_content_digest", "plan_content_digest", "render_task",
    "required_invariant_names", "expectation_identity", "expectation_digest",
    "observation_identity", "observation_digests", "render_job_identity",
    "render_attempt_identity", "render_evidence_identity", "evidence_trust_basis",
    "invariant_results", "semantic_state", "render_state", "overall_state",
    "outcome_reason_class", "failure_codes", "origin_status",
})
EXPECTATION_IDENTITY_KEYS = frozenset({
    "expectation_contract_revision", "resolver_revision", "registry_revision", "registry_digest",
    "target_table_revision", "target_table_digest", "production_target_id", "target_revision",
    "target_digest", "task_identity", "task_version", "digital_twin_id", "catalog_entry_name",
    "catalog_entry_version", "vocabulary_digest", "source_content_digest", "plan_id",
    "plan_content_digest", "render_task", "required_invariant_names",
    "invariant_expectations_digest", "expectation_digest",
})

def compute_evidence_identity(
    *,
    invariant_name: str,
    definition: SemanticInvariantDefinition,
    resolved_observables: Sequence[ResolvedObservable],
    value_state: str,
    observation_bound: bool,
    observation_request_id: Optional[str],
    observation_scope: Optional[Sequence[str]],
    canonical_state_digest: Optional[str],
) -> str:
    payload = {
        "schema": "m12.6-evidence-identity-v1",
        "invariant_name": invariant_name,
        "definition_id": invariant_name,
        "definition_revision": definition.definition_revision,
        "definition_digest": definition.definition_digest,
        "authority_class": definition.authority_class,
        "comparison": definition.comparison,
        "admissible_value_type": definition.admissible_value_type,
        "subject_scope": list(sorted(definition.subject_scope)),
        "observed_path_patterns": list(sorted(definition.observable_paths)),
        "value_state": value_state,
        "resolved_observables": [
            {"concrete_path": r.concrete_path, "value": r.value}
            for r in sorted(resolved_observables, key=lambda r: domain_a_bytes(r.concrete_path))
        ],
        "observation_bound": observation_bound,
        "observation_request_id": observation_request_id,
        "observation_scope": None if observation_scope is None else list(observation_scope),
        "canonical_state_digest": canonical_state_digest,
    }
    if frozenset(payload) != EVIDENCE_IDENTITY_KEYS:
        raise ValueError("evidence_identity input does not match the closed R6 member set")
    if value_state not in {"PRESENT", "PRESENT_NULL", "ABSENT"}:
        raise ValueError("invalid evidence value_state")
    if observation_bound:
        if observation_request_id is None or observation_scope is None or canonical_state_digest is None:
            raise ValueError("bound evidence must carry request, scope and state digest")
    else:
        if observation_request_id is not None or observation_scope is not None or canonical_state_digest is not None:
            raise ValueError("unbound evidence must null request, scope and state digest")
        if value_state != "ABSENT":
            raise ValueError("unbound evidence must be ABSENT")
    if value_state == "ABSENT" and resolved_observables:
        raise ValueError("ABSENT evidence cannot carry resolved observables")
    return _domain_a_digest(payload)


def compute_invariant_result_digest(entry: Mapping[str, Any]) -> str:
    payload = {k: v for k, v in dict(entry).items() if k != "invariant_result_digest"}
    if frozenset(payload) != INVARIANT_RESULT_KEYS:
        raise ValueError("invariant-result input does not match the closed R6 member set")
    return _domain_a_digest({
        "schema": "m12.6-invariant-result-v1",
        **payload,
    })


def compute_result_digest(payload: Mapping[str, Any]) -> str:
    data = dict(payload)
    if frozenset(data) != RESULT_DIGEST_KEYS:
        raise ValueError("result-digest input does not match the closed R6 member set")
    return _domain_a_digest(data)


def validate_expectation_identity(identity: Mapping[str, Any]) -> None:
    if frozenset(identity) != EXPECTATION_IDENTITY_KEYS:
        raise ValueError("expectation identity does not match the closed R6 member set")


__all__ = [
    "EXPECTATION_CONTRACT_REVISION",
    "RESOLVER_REVISION",
    "VERIFIER_REVISION",
    "PREFLIGHT_NODE_BUDGET",
    "PREFLIGHT_MAX_DEPTH",
    "ReasonClass",
    "InvariantState",
    "SemanticState",
    "OverallState",
    "EntryVocabulary",
    "SemanticInvariantDefinition",
    "TaskTargetMapping",
    "ProductionTargetSpec",
    "ResolvedObservable",
    "InvariantVerificationResult",
    "SemanticExpectationRefusal",
    "EXPECTATION_VOCABULARY",
    "PRODUCTION_TARGETS",
    "PRODUCTION_TARGET_BY_TASK",
    "DEFINITIONS_BY_NAME",
    "REGISTRY_REVISION",
    "TARGET_TABLE_REVISION",
    "REGISTRY_SOURCE_DIGEST",
    "TARGET_TABLE_DIGEST",
    "resolve_semantic_expectation",
    "compute_plan_content_digest",
    "compute_expectation_identity",
    "compute_expectation_digest",
    "validate_expectation_identity",
    "compute_evidence_identity",
    "compute_invariant_result_digest",
    "compute_result_digest",
    "build_r2a_result_state",
    "structural_preflight",
    "TOKEN_PLAN_CONTENT_UNSUPPORTED",
    "_aggregate_stage_rows",
    "FAILURE_CLASSIFIER",
    "classify_failure",
    "aggregate_stage_failures",
]
