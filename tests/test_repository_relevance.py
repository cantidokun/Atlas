from planning.repository_intelligence import build_repository_index
from planning.repository_intelligence.relevance import RelevanceQuery, RelevanceWeights, rank_repository_files


def _fixture_index(tmp_path):
    (tmp_path / "planning").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "planning" / "target.py").write_text(
        "from planning.helper import Helper\n\nclass Target:\n    def run(self):\n        return Helper()\n",
        encoding="utf-8",
    )
    (tmp_path / "planning" / "helper.py").write_text(
        "class Helper:\n    pass\n", encoding="utf-8"
    )
    (tmp_path / "planning" / "unrelated.py").write_text(
        "class Unrelated:\n    pass\n", encoding="utf-8"
    )
    (tmp_path / "tests" / "test_target.py").write_text(
        "from planning.target import Target\n\ndef test_target():\n    Target().run()\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "target_contract.md").write_text("Target contract\n", encoding="utf-8")
    return build_repository_index(tmp_path, include_git_history=False)


def test_exact_path_and_dependency_are_ranked_above_unrelated(tmp_path):
    index = _fixture_index(tmp_path)
    result = rank_repository_files(
        index,
        RelevanceQuery.from_values(paths=["planning/target.py"]),
    )

    assert result.ranked_paths()[:3] == (
        "planning/target.py",
        "planning/helper.py",
        "tests/test_target.py",
    )
    assert "planning/unrelated.py" not in result.ranked_paths()


def test_symbol_query_resolves_to_symbol_file(tmp_path):
    index = _fixture_index(tmp_path)
    result = rank_repository_files(
        index,
        RelevanceQuery.from_values(symbols=["Target"]),
    )
    assert result.ranked_paths()[0] == "planning/target.py"
    assert result.explanations[0].score >= RelevanceWeights().exact_symbol
    assert "exact_symbol" in result.explanations[0].reasons


def test_test_association_is_deterministic_and_explainable(tmp_path):
    index = _fixture_index(tmp_path)
    query = RelevanceQuery.from_values(paths=["planning/target.py"], test_paths=["tests/test_target.py"])
    first = rank_repository_files(index, query)
    second = rank_repository_files(index, query)
    assert first == second
    test_item = next(item for item in first.explanations if item.path == "tests/test_target.py")
    assert "test_association" in test_item.reasons


def test_contract_and_recent_signals_are_explicit(tmp_path):
    index = _fixture_index(tmp_path)
    query = RelevanceQuery.from_values(
        paths=["planning/target.py"],
        contract_paths=["docs/target_contract.md"],
        recent_paths=["planning/helper.py"],
    )
    result = rank_repository_files(index, query)
    contract = next(item for item in result.explanations if item.path == "docs/target_contract.md")
    helper = next(item for item in result.explanations if item.path == "planning/helper.py")
    assert "contract_association" in contract.reasons
    assert "recent_change" in helper.reasons


def test_explicit_anchors_are_not_displaced_by_secondary_associations(tmp_path):
    index = _fixture_index(tmp_path)
    query = RelevanceQuery.from_values(
        paths=["planning/target.py"],
        contract_paths=["docs/target_contract.md"],
        test_paths=["tests/test_target.py"],
    )
    result = rank_repository_files(index, query)
    ranked = result.ranked_paths()
    explicit = {"planning/target.py", "docs/target_contract.md", "tests/test_target.py"}
    first_secondary = next(i for i, path in enumerate(ranked) if path not in explicit)
    assert all(path in explicit for path in ranked[:first_secondary])


def test_limit_and_minimum_score_are_deterministic(tmp_path):
    index = _fixture_index(tmp_path)
    result = rank_repository_files(index, RelevanceQuery.from_values(paths=["planning/target.py"]))
    assert len(result.ranked_paths(limit=2)) == 2
    assert result.ranked_paths(minimum_score=10**9) == ()
