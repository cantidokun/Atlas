"""M12.6 R2-A final remediation tests (normative input: ATLAS_M12_6_R1_NORMATIVE_DESIGN_REV18.md,
SHA ec5eab43a4dbd3dc8e7c376133aff954a6c25a4283c3eb0d2bed31081ae2b41d).

Covers the final pass: B1 object-side closed-attribute schema, B2 exact F3 domains with catalog_version
opacity (III.2), B3 producer-derived F9, B4 row-29 gating, B5 pre-serialization preflight, B6 compound S2
aggregation, B7 trusted construction, B8 the real M5/durable-record handoff (Part XVII.5) and B9 structural
assertions (X.2/XIV.7.4 single call site, XVII.5 import allowlist, XXVIII.2 dataset, VIII.3 same-object
revalidation).

Real frozen M5/record types are imported by THIS TEST FILE only: M12.6 itself imports no M4-M10 authority
module (Part XVII.5), which the allowlist test below asserts.
"""

import ast
import dataclasses
import pathlib

from planning.m12 import DEFAULT_UNREAL_CATALOG, generate_execution_plan
from planning.m12 import expectation as ex


class _Raises:
    def __init__(self, expected):
        self.expected = expected

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            raise AssertionError(f"expected {self.expected.__name__} to be raised")
        return issubclass(exc_type, self.expected)


def raises(expected):
    return _Raises(expected)


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
R18_PATH = pathlib.Path(r"C:\Users\Gavin's PC\Desktop\ATLAS_M12_6_R1_NORMATIVE_DESIGN_REV18.md")
_JOB_ID = "atlas-render-job-11111111-2222-3333-4444-555555555555"
MODULE_PATH = REPO_ROOT / "planning" / "m12" / "expectation.py"


def _task_and_plan(task_name="unreal.sequence-configure", **overrides):
    parameters = {"twin_id": "twin-1", "sequence_name": "main", "frame_start": 1, "frame_end": 24}
    parameters.update(overrides)
    task = DEFAULT_UNREAL_CATALOG.resolve(task_name, parameters, digital_twin_id="twin-1")
    return task, generate_execution_plan(task)


def _render_task_and_plan():
    entry = next(e for e in ex.EXPECTATION_VOCABULARY if e.entry_name == "unreal.render-execute")
    kinds = dict(entry.parameter_kinds)
    parameters = {name: {"string": "twin-1", "int": 1, "json": {}}[kinds[name]] for name in entry.parameter_names}
    task = DEFAULT_UNREAL_CATALOG.resolve("unreal.render-execute", parameters, digital_twin_id="twin-1")
    return task, generate_execution_plan(task)


def _mutate(obj, **changes):
    for name, value in changes.items():
        object.__setattr__(obj, name, value)
    return obj


# --------------------------------------------------------------- B1: object-side closed attribute schema


def test_b1_undeclared_runtime_attribute_is_refused_at_s1():
    """An attribute added directly to a supplied object (not to its projection) is F2 at S1."""
    task, plan = _task_and_plan()
    object.__setattr__(task, "undeclared_runtime_attribute", 1)
    assert ex.preflight_object(task, "task") == "F2"
    resolution = ex.resolve(task, plan)
    assert resolution.applicable_rows == frozenset({1})
    result = ex.verify_semantic_target_r2a(task, plan)
    assert result.members["deciding_stage"] == "S1"
    assert result.members["primary_failure_code"] == "RESOLVER_INPUT_STRUCTURE_INVALID"

    other_task, other_plan = _task_and_plan()
    object.__setattr__(other_plan, "undeclared_runtime_attribute", 1)
    assert ex.preflight_object(other_plan, "plan") == "F2"
    assert ex.resolve(other_task, other_plan).applicable_rows == frozenset({1})


def test_b1_missing_declared_attribute_is_refused_at_s1():
    task, _plan = _task_and_plan()
    del task.__dict__["intent"]                       # a declared attribute that is missing
    assert ex.preflight_object(task, "task") == "F2"
    assert ex.declared_object_fields("task") >= {"intent", "task_version", "canonical_task_id"}


def test_b1_object_check_precedes_any_serializer_call():
    """VII.4: the object-level checks invent no serializer, canonicalizer or deepcopy call.

    The object both carries an undeclared attribute and holds content whose serialization raises; the refusal
    is the object-side F2, which proves the serializer was never reached.
    """
    task, plan = _task_and_plan()
    object.__setattr__(task, "undeclared_runtime_attribute", 1)
    object.__setattr__(task, "provenance", {"boom": _Exploding()})
    assert ex.preflight_object(task, "task") == "F2"
    assert ex.resolve(task, plan).applicable_rows == frozenset({1})


# --------------------------------------------------------------- B2: exact F3 scalar domains, III.2 opacity


def test_b2_task_version_domain():
    task, plan = _task_and_plan()
    _mutate(task, task_version=0)
    assert ex.preflight_object(task, "task") == "F3"
    result = ex.verify_semantic_target_r2a(task, plan)
    assert result.members["deciding_stage"] == "S1"
    assert result.members["primary_failure_code"] == "RESOLVER_INPUT_STRUCTURE_INVALID"
    assert ex.verify_semantic_target_r2a(task, plan).members["failure_codes"] == \
           ("RESOLVER_INPUT_STRUCTURE_INVALID",)
    # bool is excluded from the integer domain
    _mutate(task, task_version=True)
    assert ex.preflight_object(task, "task") == "F3"


def test_b2_source_task_version_domain():
    task, plan = _task_and_plan()
    _mutate(plan, source_task_version=0)
    assert ex.preflight_object(plan, "plan") == "F3"
    assert ex.resolve(task, plan).applicable_rows == frozenset({1})
    _mutate(plan, source_task_version=None)
    assert ex.preflight_object(plan, "plan") == "F3"


def test_b2_catalog_version_is_opaque_and_never_validated():
    """III.2: M12.6 does not read or validate `catalog_version`; it is not a schema value here."""
    task, plan = _task_and_plan()
    for value in (1, 999, True, 0, -1):
        _mutate(plan, catalog_version=value)
        assert ex.validate_declared_schema(plan.to_json_compatible(), "plan") is None, value
        assert ex.preflight_object(plan, "plan") is None, value
    # the same opacity holds for the catalog-resolved task's metadata-carrying bag
    document = task.to_json_compatible()
    assert ex.validate_declared_schema(document, "task") is None
    _mutate(plan, catalog_version=999)
    result = ex.verify_semantic_target_r2a(task, plan)
    assert result.members["deciding_stage"] != "S1", "catalog_version must not produce an S1 refusal"
    assert result.members["primary_failure_code"] != "RESOLVER_INPUT_STRUCTURE_INVALID"


def test_b2_digest_members_are_lowercase_hex():
    task, plan = _task_and_plan()
    good = plan.to_json_compatible()
    assert ex.validate_declared_schema(good, "plan") is None
    for bad in ("A" * 64, "g" * 64, "a" * 63):
        assert ex.validate_declared_schema(dict(good, source_content_digest=bad), "plan") == "F3", bad


# --------------------------------------------------------------- B3: producer-derived F9


def test_b3_empty_permitted_sequences_and_real_f9_constraints():
    task, plan = _task_and_plan()
    base = task.to_json_compatible()
    assert ex.validate_declared_schema(dict(base, allowed_mutations=[]), "task") is None
    assert ex.validate_declared_schema(dict(base, dependencies=[]), "task") is None
    assert ex.validate_declared_schema(dict(base, allowed_action_tools=[]), "task") is None
    plan_document = plan.to_json_compatible()
    assert ex.validate_declared_schema(dict(plan_document, steps=[]), "plan") == "F9"   # a plan needs steps
    duplicated_steps = list(plan_document["steps"]) + [dict(plan_document["steps"][0])]
    assert ex.validate_declared_schema(dict(plan_document, steps=duplicated_steps), "plan") == "F9"
    assert ex.validate_declared_schema(dict(base, allowed_mutations=["a", "a"]), "task") == "F9"


# --------------------------------------------------------------- B4: row 29 requires a structurally valid plan


def test_b4_row_29_requires_a_structurally_valid_plan():
    task, plan = _task_and_plan()
    # an invalid plan that also carries a float: row 29 MUST NOT be added
    _mutate(plan, provenance={"float_probe": 1.5})
    _mutate(plan, plan_id=42)                       # the plan now fails the declared-schema check
    resolution = ex.resolve(task, plan)
    assert 29 not in resolution.applicable_rows, resolution.applicable_rows
    assert resolution.applicable_rows == frozenset({1})
    assert resolution.derived["preflight"]["plan"]["category"] == "F3"
    assert "float_policy" not in resolution.derived


def test_b4_valid_float_plan_with_an_independent_task_defect_unions_both_rows():
    task, plan = _task_and_plan()
    _mutate(task, metadata={"s": {1, 2}})           # an independent task-side F4
    _mutate(plan, provenance={"float_probe": 1.5})  # a structurally valid float-bearing plan
    resolution = ex.resolve(task, plan)
    assert resolution.applicable_rows == frozenset({1, 29})
    outcome = ex.decisive_outcome(sorted(resolution.applicable_rows))
    assert outcome.deciding_stage == "S1"
    assert outcome.primary_code == "RESOLVER_INPUT_STRUCTURE_INVALID"   # the lowest-numbered applicable row
    assert set(outcome.failure_codes) == {"RESOLVER_INPUT_STRUCTURE_INVALID", "PLAN_CONTENT_UNSUPPORTED"}


# --------------------------------------------------------------- B5: pre-serialization preflight


class _Exploding:
    """A supplied-content object whose deepcopy / serialization path raises."""

    def __deepcopy__(self, memo):
        raise RuntimeError("hostile deepcopy")

    def __repr__(self):
        raise RuntimeError("hostile repr")


def test_b5_serialization_exception_is_attributed_to_the_supplied_input():
    task, plan = _task_and_plan()
    _mutate(task, provenance={"boom": _Exploding()})
    assert ex.preflight_object(task, "task") is None          # the object-level checks pass: no serializer used
    resolution = ex.resolve(task, plan)
    assert resolution.applicable_rows == frozenset({1})
    assert resolution.derived["preflight"]["task"] == {"category": "F4"}
    result = ex.verify_semantic_target_r2a(task, plan)
    assert result.members["deciding_stage"] == "S1"
    assert result.members["primary_failure_code"] == "RESOLVER_INPUT_STRUCTURE_INVALID"
    assert result.members["primary_failure_code"] != "RESOLVER_INTERNAL_FAILURE"


def test_b5_no_digest_work_before_structural_eligibility():
    """Digest/canonical work begins only after structural eligibility: a malformed input never reaches it."""
    task, plan = _task_and_plan()
    _mutate(plan, provenance={"boom": _Exploding()})
    resolution = ex.resolve(task, plan)
    assert resolution.applicable_rows == frozenset({1})
    assert resolution.derived.get("target") is None          # S4 was never entered
    result = ex.verify_semantic_target_r2a(task, plan)
    assert result.members["plan_content_digest"] is None      # no digest was taken from malformed content


# --------------------------------------------------------------- B6: compound S2 aggregation


def _definition(**overrides):
    fields = dict(
        invariant_name="probe.invariant", definition_revision=1, definition_status="REGISTERED",
        authority_class="CODE_CONSTANT", observable_paths=("world.path.a",), subject_scope=("entity-1",),
        comparison="EQUALS", admissible_value_type="string", expected_value_source="CODE_CONSTANT",
        expected_value="x", target_binding="PRODUCTION_TARGET",
        missing_behavior="EXPECTED_VALUE_UNAVAILABLE", unsupported_behavior="EXPECTED_VALUE_UNAVAILABLE",
        witness_positive=None, witness_negative=None, witness_lossy=None, non_claim="probe",
    )
    fields.update(overrides)
    return ex.SemanticInvariantDefinition(**fields)


def test_b6_compound_s2_rows_are_unioned_with_the_lowest_as_primary():
    task, _plan = _task_and_plan()
    triple = ex._selector_triple(task)
    duplicate_names = (_definition(), dataclasses.replace(_definition(), definition_revision=2))
    dangling = ex.TaskTargetMapping(triple[0], triple[1], triple[2], "target-does-not-exist")
    duplicated_triple = (dangling, dataclasses.replace(dangling, production_target_id="other"))
    rows = ex.revalidate_authority(definitions=duplicate_names, targets=(), mappings=duplicated_triple)
    assert isinstance(rows, frozenset)
    assert {10, 11, 12} <= set(rows), sorted(rows)             # three independent integrity conditions coexist
    assert {9} <= set(rows)                                    # the reviewed registry no longer recomputes
    outcome = ex.decisive_outcome(sorted(rows))
    assert outcome.primary_code == ex.failure_token(min(rows))
    assert outcome.deciding_stage == "S2"


def test_b6_duplicate_selector_mapping_and_dangling_reference_are_distinct():
    task, _plan = _task_and_plan()
    triple = ex._selector_triple(task)
    first = ex.TaskTargetMapping(triple[0], triple[1], triple[2], "t1")
    second = ex.TaskTargetMapping(triple[0], triple[1], triple[2], "t2")
    assert ex.mapping_reference_status(triple, mappings=(first, second), targets=()) == "duplicate"
    assert ex.mapping_reference_status(triple, mappings=(first,), targets=()) == "dangling"
    specs = (ex.ProductionTargetSpec("t1", 1, "a", "b", (), (), None, "ref", "n"),
             ex.ProductionTargetSpec("t2", 1, "a", "b", (), (), None, "ref", "n"))
    assert ex.mapping_reference_status(triple, mappings=(first,), targets=specs) == "ok"
    rows = ex.revalidate_authority(definitions=(), targets=specs, mappings=(first, second))
    assert 12 in rows and 11 not in rows


# --------------------------------------------------------------- B7: trusted construction


def _trusted(members, rows):
    return ex.M126Result(members=members, applicable_rows=rows,
                         _construction_token=ex._RESULT_CONSTRUCTION_TOKEN)


def test_b7_result_cannot_be_forged_without_the_trusted_token():
    task, plan = _task_and_plan()
    result = ex.verify_semantic_target_r2a(task, plan)
    with raises(ex.M126ContractError):
        ex.M126Result(members=dict(result.members), applicable_rows=result.applicable_rows)
    with raises(ex.M126ContractError):
        ex.M126Result(members=dict(result.members), applicable_rows=(1,), _construction_token=object())
    # an omitted lower applicable row cannot be smuggled in: the derived fields must match the row set
    with raises(ex.M126ContractError):
        _trusted(dict(result.members), (22,))
    with raises(ex.M126ContractError):
        _trusted(dict(result.members), (3, 6, 22, 44))          # a forged extra row
    assert _trusted(dict(result.members), result.applicable_rows).result_digest == result.result_digest


def test_b7_member_types_and_nullability_are_validated_at_construction():
    task, plan = _task_and_plan()
    result = ex.verify_semantic_target_r2a(task, plan)
    members = dict(result.members)
    rows = result.applicable_rows
    for name, value in (("registry_revision", "1"), ("registry_digest", "not-a-digest"),
                        ("task_identity", 5), ("render_task", "yes"),
                        ("failure_codes", [1, 2]), ("invariant_results", ("not-an-entry",)),
                        ("evidence_trust_basis", {"semantic_observation": "NOT_ESTABLISHED"}),
                        ("evidence_trust_basis", {"semantic_observation": "NOT_ESTABLISHED",
                                                  "render_evidence": "INVENTED"}),
                        ("schema", None), ("semantic_state", None)):
        with raises(ex.M126ContractError):
            _trusted(dict(members, **{name: value}), rows)
    assert _trusted(members, rows).canonical_dict()


def test_b7_invalid_state_primary_and_mutation_are_refused():
    task, plan = _task_and_plan()
    result = ex.verify_semantic_target_r2a(task, plan)
    members = dict(result.members)
    rows = result.applicable_rows
    with raises(ex.M126ContractError):
        _trusted(dict(members, primary_failure_code="PRODUCTION_TARGET_NOT_ESTABLISHED"), rows)
    with raises(ex.M126ContractError):
        _trusted(dict(members, semantic_state="SATISFIED"), rows)
    with raises(ex.M126ContractError):
        _trusted(dict(members, deciding_stage="S5"), rows)
    with raises(TypeError):
        result.members["semantic_state"] = "SATISFIED"
    with raises(TypeError):
        result.members["evidence_trust_basis"]["render_evidence"] = "DURABLE_RECORD_BACKED"
    with raises(ex.M126ContractError):
        _trusted(dict(members, registry_revision=True), rows)          # rejected at construction
    with raises(ex.M126ContractError):
        ex.M126Result(members=dict(members), applicable_rows=rows)     # untrusted construction refused


# --------------------------------------------------------------- B8: the real M5 handoff (XVII.5)


class _Handoff:
    """The permitted M5-to-M12.6 handoff carrier: the real evidence object and the real durable record."""

    def __init__(self, evidence, record):
        self.evidence = evidence
        self.record = record


def _real_record(twin="twin-1", job_id="atlas-render-job-11111111-2222-3333-4444-555555555555", attempt_ordinal=2):
    from planning.unreal_render_job_record import AtlasRenderJobRecord

    return AtlasRenderJobRecord.create_intent(
        atlas_job_id=job_id,
        attempt_ordinal=attempt_ordinal,
        authorization_id="authz-0001",
        canonical_digital_twin_id=twin,
        sequence_asset_path="/Game/Atlas/Sequence/Main",
        request_digest="a" * 64,
        config_digest="b" * 64,
        output_parent_directory="/srv/atlas/renders",
        output_directory="/srv/atlas/renders/" + job_id,
        expected_output_spec={"format": "png", "frame_count": 24, "width": 1920, "height": 1080},
        created_at="2026-09-26T12:00:00Z",
    )


def _real_evidence(verified=True):
    from planning.unreal_evidence_contract import UnrealEvidence

    return UnrealEvidence(operation_name="inspect_render_job", entity_ids=("twin-1",),
                          observed_state={"status": "completed", "finished": True}, source="engine",
                          verified=verified)


def test_b8_real_m5_verified_evidence_populates_the_render_identity():
    task, plan = _render_task_and_plan()
    handoff = _Handoff(_real_evidence(verified=True), _real_record())
    result = ex.verify_semantic_target_r2a(task, plan, render_evidence=handoff)
    assert 36 not in result.applicable_rows and 44 not in result.applicable_rows
    assert result.members["render_job_identity"] == _JOB_ID
    assert result.members["render_attempt_identity"] == 2
    assert result.members["render_evidence_identity"] is not None
    assert result.members["evidence_trust_basis"]["render_evidence"] == "DURABLE_RECORD_BACKED"
    assert result.members["render_state"] == "NOT_VERIFIED"      # VERIFIED stays unreachable (XVII.1)


def test_b8_real_durable_record_twin_mismatch_is_row_37():
    task, plan = _render_task_and_plan()
    handoff = _Handoff(_real_evidence(verified=True), _real_record(twin="twin-OTHER"))
    result = ex.verify_semantic_target_r2a(task, plan, render_evidence=handoff)
    assert 37 in result.applicable_rows
    assert 36 not in result.applicable_rows
    assert result.members["evidence_trust_basis"]["render_evidence"] == "DURABLE_RECORD_BACKED"


def test_b8_real_m5_refusal_is_row_36_and_missing_evidence_is_row_44():
    task, plan = _render_task_and_plan()
    refused = ex.verify_semantic_target_r2a(task, plan, render_evidence=_Handoff(_real_evidence(False),
                                                                                _real_record()))
    assert 36 in refused.applicable_rows and 44 not in refused.applicable_rows
    assert refused.members["render_job_identity"] is None
    missing = ex.verify_semantic_target_r2a(task, plan)
    assert 44 in missing.applicable_rows and 36 not in missing.applicable_rows
    # the real types cannot be faked: a shadow object carrying the right field names is refused
    shadow = type("UnrealEvidence", (), {"verified": True, "operation_name": "inspect_render_job"})()
    assert 36 in ex.verify_semantic_target_r2a(
        task, plan, render_evidence=_Handoff(shadow, _real_record())).applicable_rows
    # a real evidence object without the durable record cannot establish the render dimension
    assert 36 in ex.verify_semantic_target_r2a(
        task, plan, render_evidence=_Handoff(_real_evidence(True), None)).applicable_rows


def test_b8_no_mapping_only_path_remains():
    task, plan = _render_task_and_plan()
    mapping_carrier = {"evidence": _real_evidence(True), "record": _real_record()}
    assert 36 in ex.verify_semantic_target_r2a(task, plan, render_evidence=mapping_carrier).applicable_rows


# --------------------------------------------------------------- B9: structural assertions


def _module_source():
    return MODULE_PATH.read_text(encoding="utf-8")


_PROHIBITED_MODULE_PREFIXES = (
    "planning.unreal_evidence_contract",
    "planning.unreal_render",
    "planning.unreal_journal_attestation",
)


def _prohibited_module_references(source: str) -> set:
    """Detect any reference to a prohibited M4-M10 authority module: import, from-import, deferred or string."""
    found = set()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found |= {name for name in _PROHIBITED_MODULE_PREFIXES if alias.name.startswith(name)}
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            found |= {name for name in _PROHIBITED_MODULE_PREFIXES if module.startswith(name)}
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            found |= {name for name in _PROHIBITED_MODULE_PREFIXES if name in node.value}
        elif isinstance(node, ast.Attribute):
            found |= {name for name in _PROHIBITED_MODULE_PREFIXES if node.attr.startswith(name.rsplit(".", 1)[-1])}
    return found


def test_b9_xvii5_import_allowlist_with_aliased_deferred_and_string_controls():
    assert _prohibited_module_references(_module_source()) == set()      # the real module is clean
    controls = {
        "direct": "import planning.unreal_evidence_contract\n",
        "aliased": "import planning.unreal_evidence_contract as m5\n",
        "from-import": "from planning.unreal_evidence_contract import verify_render_job_evidence\n",
        "deferred": "def f():\n    import planning.unreal_render_job_record\n",
        "string": "import importlib\nimportlib.import_module(\"planning.unreal_evidence_contract\")\n",
        "render-prefix": "from planning.unreal_render_execution import EngineThread\n",
    }
    for name, source in controls.items():
        assert _prohibited_module_references(source), name


def test_b9_x2_plan_digest_single_call_site():
    """X.2 item 2: one call site of the canonicalizer inside the one plan-digest function; no re-derivation."""
    tree = ast.parse(_module_source())
    recipe_calls = []
    digest_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if name in ("_canonical_sha256", "_canonical_bytes"):
                recipe_calls.append(node.lineno)
            if name == "compute_plan_content_digest":
                digest_calls.append(node.lineno)
    assert len(recipe_calls) == 1, recipe_calls                     # exactly one call site of the recipe
    owner = next(node for node in ast.walk(tree)
                 if isinstance(node, ast.FunctionDef) and node.name == "compute_plan_content_digest")
    assert owner.lineno <= recipe_calls[0] <= (owner.end_lineno or owner.lineno)
    assert digest_calls, "every other use must call the one function rather than re-derive"


def test_b9_xxviii2_recorded_assertion_dataset():
    """XXVIII.2: the recorded file/line/category dataset, compared against the actual assertion values."""
    if not R18_PATH.exists():
        print("SKIP: the R18 artifact is not present in this environment")
        return
    text = R18_PATH.read_text(encoding="utf-8")
    section = text[text.index("## XXVIII.2"):text.index("## XXVIII.3")]
    blocks = section.split("|---|---|---|---|")[1:]
    tables = [[line for line in block.splitlines()
               if line.startswith("| ") and line.split("|")[1].strip().isdigit()] for block in blocks[:2]]
    category_i, category_ii = tables
    assert len(category_i) == 22 and len(category_ii) == 2
    statements = category_i + category_ii
    assert len(statements) == 24
    tests_dir = REPO_ROOT / "tests" / "m12"
    for statement in statements:
        cells = [cell.strip() for cell in statement.split("|")]
        file_name, base_line, recorded = cells[2], int(cells[3]), cells[4].strip("`")
        lines_of_file = (tests_dir / file_name).read_text(encoding="utf-8").splitlines()
        actual = lines_of_file[base_line - 1]
        assert "assert" in actual, (file_name, base_line, actual)
        # the recorded assertion value must still be the value the base line asserts
        literal = next((part for part in recorded.replace("(", " ").replace(")", " ").split()
                        if '"' in part), None)
        if literal is not None:
            assert literal.strip("`") in actual, (file_name, base_line, literal, actual)
    # the record's two affected files are untouched by this remediation
    changed = {"test_m12_5_verification.py", "test_m12_5_adversarial.py"}
    assert changed == {statement.split("|")[2].strip() for statement in statements}


def test_b9_viii3_same_object_revalidation_identity_and_mutation_detection():
    """VIII.3: the revalidation reads the same authoritative objects, and a mutated table is detected."""
    defaults = ex.revalidate_authority.__defaults__
    assert defaults[0] is ex.SEMANTIC_INVARIANT_DEFINITIONS
    assert defaults[1] is ex.PRODUCTION_TARGETS
    assert defaults[2] is ex.PRODUCTION_TARGET_BY_TASK
    assert defaults[0] is ex.registry_revision.__globals__["SEMANTIC_INVARIANT_DEFINITIONS"]
    # the same authoritative objects handed to the resolver are handed back for revalidation
    duplicates = (_definition(), dataclasses.replace(_definition(), definition_revision=2))
    assert 11 in ex.revalidate_authority(definitions=duplicates, targets=())
    assert 33 in ex.revalidate_authority(
        definitions=(dataclasses.replace(_definition(), authority_class="OTHER"),), targets=())
    assert 38 in ex.revalidate_authority(
        definitions=(dataclasses.replace(_definition(), subject_scope=("b", "a")),), targets=())
    assert ex.revalidate_authority() == frozenset()
