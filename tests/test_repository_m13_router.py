"""M13.4 advisory bridge tests; no provider or workflow execution."""

from planning.m11_router.model_profile import ModelProfile, ModelTier
from planning.m11_router.router import ModelRouter
from planning.repository_intelligence.index import RepositoryIndex
from planning.repository_intelligence.m13_router import advise_context_route
from planning.repository_intelligence.relevance import RelevanceQuery


def _index() -> RepositoryIndex:
    return RepositoryIndex(
        fingerprint="repo-test",
        files=(
            {
                "path": "planning/target.py",
                "symbols": ["Target"],
                "imports": [],
            },
            {
                "path": "tests/test_target.py",
                "symbols": [],
                "imports": ["planning.target"],
            },
        ),
    )


def _router() -> ModelRouter:
    return ModelRouter(
        [
            ModelProfile(
                tier=ModelTier.L0,
                model_id="test-l0",
                capabilities=frozenset({"docs"}),
                token_budget=1000,
            ),
            ModelProfile(
                tier=ModelTier.L1,
                model_id="test-l1",
                capabilities=frozenset({"tests"}),
                token_budget=2000,
            ),
        ]
    )


def test_context_is_compiled_before_routing_and_payload_is_bounded():
    advice = advise_context_route(
        task_id="m13.4-test",
        dimension_scores={"correctness": 1},
        index=_index(),
        query=RelevanceQuery.from_values(text="Target", paths=["planning/target.py"]),
        source_by_path={
            "planning/target.py": "class Target:\n    pass\n",
            "tests/test_target.py": "def test_target():\n    assert True\n",
        },
        router=_router(),
        task_classes=["docs"],
        stable_instructions="stable",
        dynamic_state={"step": 1},
        max_context_chars=100,
    )

    assert advice.decision.selection is not None
    assert advice.decision.selection.selected_model_id == "test-l0"
    assert advice.context.context_chars <= 100
    assert advice.context.stable_instructions == "stable"
    assert advice.context.dynamic_state == {"step": 1}
    payload = advice.model_payload()
    assert payload["stable_instructions"] == "stable"
    assert payload["dynamic_state"] == {"step": 1}
    assert payload["context_fingerprint"] == advice.context.fingerprint


def test_router_failure_remains_fail_closed_while_context_is_preserved():
    router = ModelRouter([])
    advice = advise_context_route(
        task_id="m13.4-no-capable-model",
        dimension_scores={"correctness": 3},
        index=_index(),
        query=RelevanceQuery.from_values(paths=["planning/target.py"]),
        source_by_path={"planning/target.py": "class Target: pass\n"},
        router=router,
        task_classes=["tests"],
    )

    assert advice.decision.needs_human_review is True
    assert advice.context.included[0].path == "planning/target.py"


def test_advisory_result_does_not_contain_provider_or_authorization_fields():
    advice = advise_context_route(
        task_id="m13.4-boundary",
        dimension_scores={"correctness": 0},
        index=_index(),
        query=RelevanceQuery.from_values(paths=["planning/target.py"]),
        source_by_path={"planning/target.py": "class Target: pass\n"},
        router=_router(),
        task_classes=["docs"],
    )
    payload = advice.model_payload()
    assert "authorization_id" not in payload
    assert "receipt" not in payload
    assert "provider_credentials" not in payload
