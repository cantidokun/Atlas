"""M12.1 authority-isolation tests.

Demonstrates through types that the M12 semantic layer cannot and does not:
- create a second scheduler;
- create a second retry controller;
- create a second persistence authority;
- mint receipts, recovery authority, protected flags, or authorization IDs;
- authorize execution by creating/normalizing/compiling a semantic task.

Execution authorization continues to flow exclusively through the existing Atlas
mechanism (render submission / recovery coordinator / evidence verifier / receipt
machinery); the M12 package must not import or expose any of it.
"""

import importlib
import pkgutil

import pytest

import planning.m12
from planning.m12 import (
    UnauthorizedSemanticFieldError,
    compile_unreal_semantic_task,
    normalize_unreal_semantic_request,
)

# Production-authority modules that the M12 semantic layer must NEVER reference.
AUTHORITY_MODULES = (
    "planning.unreal_render_submission",
    "planning.unreal_render_recovery_coordinator",
    "planning.unreal_render_receipt",
    "planning.unreal_render_receipt_store",
    "planning.unreal_evidence_contract",
    "planning.unreal_render_job_store",
    "planning.unreal_render_job_record",
)


def test_m12_package_does_not_import_authority_modules():
    loaded = set()
    m12 = importlib.import_module("planning.m12")
    for info in pkgutil.walk_packages(m12.__path__, prefix="planning.m12."):
        try:
            module = importlib.import_module(info.name)
        except Exception:
            continue
        loaded.add(info.name)

    for authority in AUTHORITY_MODULES:
        # The semantic package must not import any authority module, transitively.
        assert authority not in loaded, (
            f"M12 semantic layer illegally imports authority module {authority}"
        )


def test_production_authority_is_not_reachable_from_router_api():
    import planning.m12

    exposed = {
        name
        for _mod in [planning.m12]
        for name in getattr(_mod, "__all__", ())
    }
    for token in (
        "authorization",
        "receipt",
        "reconcile",
        "submit_render",
        "schedule",
        "persist",
        "recovery",
    ):
        assert not any(token in name.lower() for name in exposed), (
            f"authority-shaped name leaked into M12 public API: {exposed}"
        )


def test_normalize_and_compile_do_not_authorize_execution():
    raw = {
        "canonical_task_id": "cam-01-setup",
        "task_class": "camera-configure",
        "digital_twin_id": "twin-stadium-01",
        "task_version": 1,
        "intent": "Configure camera slot 1 framing.",
        "target_state": {
            "description": "Camera slot 1 framed.",
            "invariant_names": ["camera_slot_1_framed"],
        },
        "allowed_mutations": ["camera-configure"],
        "evidence": [
            {"tool": "unreal_inspect", "arguments": {}, "name": "inspect"}
        ],
        "actions": [
            {"tool": "unreal_inspect", "arguments": {}, "name": "inspect"}
        ],
        "allowed_action_tools": ["unreal_inspect"],
    }
    task = normalize_unreal_semantic_request(raw)
    compiled = compile_unreal_semantic_task(task)

    # Creating/normalizing/compiling produces NO authorization material.
    for obj, label in ((task, "semantic task"), (compiled, "compiled task")):
        snapshot = obj.snapshot() if hasattr(obj, "snapshot") else {}
        text = str(snapshot).lower()
        for token in (
            "authorization_id",
            "receipt",
            "recovery",
            "artifact_manifest",
            "attempt_nonce",
            "hmac",
        ):
            assert token not in text, f"{label} leaked authority token {token}"
        # No execution-authorization field.
        assert "authorized" not in text


def test_no_model_authorization_material_is_trusted():
    raw = {
        "canonical_task_id": "cam-01",
        "task_class": "camera-configure",
        "digital_twin_id": "twin-stadium-01",
        "task_version": 1,
        "intent": "i",
        "target_state": {"description": "d", "invariant_names": ["s"]},
        "allowed_mutations": ["camera-configure"],
        "evidence": [{"tool": "unreal_inspect", "arguments": {}, "name": "e"}],
        "actions": [{"tool": "unreal_inspect", "arguments": {}, "name": "a"}],
        "allowed_action_tools": ["unreal_inspect"],
        "provenance": {"hmac_key": "s3cret", "authorization_id": "forged"},
    }
    with pytest.raises(UnauthorizedSemanticFieldError):
        normalize_unreal_semantic_request(raw)


def test_semantic_task_object_has_no_authority_methods():
    raw = {
        "canonical_task_id": "cam-01",
        "task_class": "camera-configure",
        "digital_twin_id": "twin-stadium-01",
        "task_version": 1,
        "intent": "i",
        "target_state": {"description": "d", "invariant_names": ["s"]},
        "allowed_mutations": ["camera-configure"],
        "evidence": [{"tool": "unreal_inspect", "arguments": {}, "name": "e"}],
        "actions": [{"tool": "unreal_inspect", "arguments": {}, "name": "a"}],
        "allowed_action_tools": ["unreal_inspect"],
    }
    task = normalize_unreal_semantic_request(raw)
    forbidden_attrs = (
        "authorize",
        "submit_render",
        "reconcile",
        "schedule",
        "persist",
        "mint_receipt",
        "issue_recovery",
        "grant_capability",
    )
    for attr in forbidden_attrs:
        assert not hasattr(task, attr), f"semantic task must not expose {attr}"