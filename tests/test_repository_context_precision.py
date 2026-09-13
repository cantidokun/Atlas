from planning.repository_intelligence import build_repository_index
from planning.repository_intelligence.context import _token_aware_secondary_order, compile_context
from planning.repository_intelligence.relevance import RelevanceExplanation, RelevanceQuery


def test_token_aware_secondary_order_prefers_relevance_per_context_character():
    explanations = [RelevanceExplanation("docs/large.md", 30, ("content_match:1",)), RelevanceExplanation("docs/small.md", 20, ("content_match:1",))]
    sources = {"docs/large.md": "x" * 100, "docs/small.md": "x" * 20}
    ordered = _token_aware_secondary_order(explanations, sources, 100)
    assert [item.path for item in ordered] == ["docs/small.md", "docs/large.md"]


def test_token_aware_secondary_order_is_deterministic_for_equal_utility():
    explanations = [RelevanceExplanation("docs/b.md", 10, ("content_match:1",)), RelevanceExplanation("docs/a.md", 10, ("content_match:1",))]
    sources = {"docs/a.md": "x" * 10, "docs/b.md": "x" * 10}
    first = _token_aware_secondary_order(explanations, sources, 100)
    second = _token_aware_secondary_order(list(reversed(explanations)), sources, 100)
    assert [item.path for item in first] == ["docs/a.md", "docs/b.md"]
    assert [item.path for item in second] == ["docs/a.md", "docs/b.md"]


def test_token_aware_secondary_order_skips_missing_or_empty_sources():
    explanations = [RelevanceExplanation("docs/missing.md", 100, ("content_match:1",)), RelevanceExplanation("docs/empty.md", 90, ("content_match:1",)), RelevanceExplanation("docs/usable.md", 10, ("content_match:1",))]
    sources = {"docs/empty.md": "", "docs/usable.md": "usable"}
    ordered = _token_aware_secondary_order(explanations, sources, 100)
    assert [item.path for item in ordered] == ["docs/usable.md"]


def test_token_aware_secondary_order_prefers_complete_fit_when_budget_is_tight():
    explanations = [
        RelevanceExplanation("docs/long.md", 100, ("content_match:1",)),
        RelevanceExplanation("docs/short.md", 60, ("content_match:1",)),
        RelevanceExplanation("docs/tiny.md", 40, ("content_match:1",)),
    ]
    sources = {
        "docs/long.md": "x" * 80,
        "docs/short.md": "x" * 50,
        "docs/tiny.md": "x" * 20,
    }
    ordered = _token_aware_secondary_order(explanations, sources, 100, budget=70)
    assert [item.path for item in ordered] == ["docs/tiny.md", "docs/short.md", "docs/long.md"]


def test_token_aware_secondary_context_keeps_explicit_anchor(tmp_path):
    (tmp_path / "planning").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "planning" / "target.py").write_text("class Target:\n    pass\n", encoding="utf-8")
    (tmp_path / "docs" / "high_value.md").write_text("recovery boundary semantic\n", encoding="utf-8")
    (tmp_path / "docs" / "generic.md").write_text("recovery\n" * 40, encoding="utf-8")
    index = build_repository_index(tmp_path, include_git_history=False)
    sources = {item["path"]: (tmp_path / item["path"]).read_text(encoding="utf-8") for item in index.files}
    query = RelevanceQuery.from_values(paths=["planning/target.py"], text="recovery boundary semantic")
    package = compile_context(index, query, sources, max_context_chars=100, max_file_chars=100)
    assert package.included[0].path == "planning/target.py"
