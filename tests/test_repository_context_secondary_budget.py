from planning.repository_intelligence import build_repository_index
from planning.repository_intelligence.context import compile_context
from planning.repository_intelligence.relevance import RelevanceQuery


def test_secondary_coverage_budget_is_distributed_across_candidates(tmp_path):
    (tmp_path / "planning").mkdir()
    (tmp_path / "docs").mkdir()
    target = "target\n" * 3
    first = "semantic recovery boundary\n" * 20
    second = "semantic recovery boundary\n" * 20
    (tmp_path / "planning" / "target.py").write_text(target, encoding="utf-8")
    (tmp_path / "docs" / "first.md").write_text(first, encoding="utf-8")
    (tmp_path / "docs" / "second.md").write_text(second, encoding="utf-8")
    index = build_repository_index(tmp_path, include_git_history=False)
    sources = {
        "planning/target.py": target,
        "docs/first.md": first,
        "docs/second.md": second,
    }

    package = compile_context(
        index,
        RelevanceQuery.from_values(paths=["planning/target.py"], text="semantic recovery boundary"),
        sources,
        max_context_chars=100,
        max_file_chars=100,
    )

    selected = [item.path for item in package.included]
    assert selected[0] == "planning/target.py"
    assert "docs/first.md" in selected
    assert "docs/second.md" in selected
    assert package.context_chars <= 100
