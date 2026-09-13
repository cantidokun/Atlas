from planning.repository_intelligence import build_repository_index
from planning.repository_intelligence.context import compile_context
from planning.repository_intelligence.relevance import RelevanceQuery


def test_token_aware_secondary_order_prefers_relevance_density(tmp_path):
    (tmp_path / "planning").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "planning" / "target.py").write_text("class Target:\n    pass\n", encoding="utf-8")
    (tmp_path / "docs" / "high_value.md").write_text("recovery boundary semantic\n", encoding="utf-8")
    (tmp_path / "docs" / "generic.md").write_text("recovery\n" * 40, encoding="utf-8")
    index = build_repository_index(tmp_path, include_git_history=False)
    sources = {item["path"]: (tmp_path / item["path"]).read_text(encoding="utf-8") for item in index.files}
    query = RelevanceQuery.from_values(paths=["planning/target.py"], text="recovery boundary semantic")

    package = compile_context(index, query, sources, max_context_chars=100, max_file_chars=100)

    selected = [item.path for item in package.included]
    assert selected[0] == "planning/target.py"
    assert "docs/high_value.md" in selected
