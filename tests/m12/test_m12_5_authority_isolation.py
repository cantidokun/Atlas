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


def test_verifier_has_only_allowed_authority_imports():
    tree = _tree()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in FORBIDDEN_MODULES
                assert alias.name != "importlib"
        elif isinstance(node, ast.ImportFrom):
            assert node.module not in FORBIDDEN_MODULES
            assert node.module != "importlib"


def test_no_deferred_dynamic_authority_import_or_authority_string_path():
    source = inspect.getsource(verification)
    assert "importlib.import_module" not in source
    assert "unreal_render_submission" not in source
    assert "unreal_render_receipt_store" not in source
    assert "unreal_render_recovery_coordinator" not in source


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
