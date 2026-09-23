"""M12.5 authority-isolation tests."""

import ast
import inspect

import planning.m12.verification as verification


FORBIDDEN_MODULES = {
    "planning.unreal_render_submission",
    "planning.unreal_render_receipt_store",
    "planning.unreal_render_receipt",
    "planning.unreal_render_recovery_coordinator",
}
FORBIDDEN_TOKENS = {
    "authorization_id",
    "attempt_nonce",
    "last_accepted_lease_token",
}


def _tree():
    return ast.parse(inspect.getsource(verification))


def _authority_violations(source):
    tree = ast.parse(source)
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in FORBIDDEN_MODULES:
                    violations.append(("import", alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module in FORBIDDEN_MODULES:
                violations.append(("from", node.module))
        elif isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "importlib"
                and func.attr == "import_module"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value in FORBIDDEN_MODULES
            ):
                violations.append(("deferred", node.args[0].value))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in FORBIDDEN_MODULES:
                violations.append(("string", node.value))
    return violations


def test_verifier_has_no_forbidden_authority_paths():
    source = inspect.getsource(verification)
    assert _authority_violations(source) == []


def test_forbidden_authority_detector_has_positive_controls():
    samples = {
        "ordinary": "import planning.unreal_render_submission",
        "aliased": "import planning.unreal_render_submission as submission",
        "deferred": (
            "import importlib\n"
            "importlib.import_module('planning.unreal_render_submission')"
        ),
        "string": "module_name = 'planning.unreal_render_submission'",
    }
    for kind, sample in samples.items():
        violations = _authority_violations(sample)
        assert violations, kind
        assert any(item[1] == "planning.unreal_render_submission" for item in violations), (
            kind,
            violations,
        )


def test_no_deferred_importlib_authority_path_in_verifier():
    source = inspect.getsource(verification)
    assert "importlib" not in source


def test_producer_owned_result_fields_are_not_verifier_inputs():
    signature = inspect.signature(verification.verify_semantic_target)
    parameter_names = set(signature.parameters)
    assert "provenance" not in parameter_names
    assert "observation_identity" not in parameter_names
    assert "render_evidence_identity" not in parameter_names
    assert "evidence_trust_basis" not in parameter_names
    assert "verified" not in parameter_names
    assert "expected_value" not in parameter_names


def test_v1_invariant_registry_is_closed_and_has_no_caller_predicates():
    assert verification.REGISTERED_INVARIANTS == {}
    tree = _tree()
    assert not any(isinstance(node, ast.Lambda) for node in ast.walk(tree))
    source = inspect.getsource(verification)
    assert "eval(" not in source
    assert "exec(" not in source


def test_verifier_source_does_not_copy_authority_fields():
    source = inspect.getsource(verification).lower()
    for token in FORBIDDEN_TOKENS:
        assert token not in source
