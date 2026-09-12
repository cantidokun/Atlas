from planning.repository_intelligence import build_repository_index
from planning.repository_intelligence.context import compile_context
from planning.repository_intelligence.relevance import RelevanceQuery, RelevanceWeights


def test_explicit_anchors_are_all_admitted_under_budget_pressure(tmp_path):
    (tmp_path / "planning").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "tests").mkdir()
    target = "target\n" * 20
    contract = "contract\n" * 20
    test = "test\n" * 20
    unrelated = "unrelated\n" * 20
    (tmp_path / "planning" / "target.py").write_text(target, encoding="utf-8")
    (tmp_path / "docs" / "contract.md").write_text(contract, encoding="utf-8")
    (tmp_path / "tests" / "test_target.py").write_text(test, encoding="utf-8")
    (tmp_path / "planning" / "unrelated.py").write_text(unrelated, encoding="utf-8")

    index = build_repository_index(tmp_path, include_git_history=False)
    sources = {
        "planning/target.py": target,
        "docs/contract.md": contract,
        "tests/test_target.py": test,
        "planning/unrelated.py": unrelated,
    }
    query = RelevanceQuery.from_values(
        paths=["planning/target.py"],
        contract_paths=["docs/contract.md"],
        test_paths=["tests/test_target.py"],
    )

    package = compile_context(index, query, sources, max_context_chars=90, max_file_chars=100)

    selected = [item.path for item in package.included]
    assert selected[:3] == [
        "docs/contract.md",
        "planning/target.py",
        "tests/test_target.py",
    ]
    assert all(item.truncated for item in package.included[:3])
    assert package.context_chars <= 90


def test_explicit_contract_anchor_is_admitted_without_relevance_explanation(tmp_path):
    (tmp_path / "planning").mkdir()
    (tmp_path / "docs").mkdir()
    target = "target\n" * 10
    contract = "contract\n" * 10
    (tmp_path / "planning" / "target.py").write_text(target, encoding="utf-8")
    (tmp_path / "docs" / "contract.md").write_text(contract, encoding="utf-8")

    index = build_repository_index(tmp_path, include_git_history=False)
    sources = {
        "planning/target.py": target,
        "docs/contract.md": contract,
    }
    query = RelevanceQuery.from_values(
        paths=["planning/target.py"],
        contract_paths=["docs/contract.md"],
    )

    # Force the contract association to carry no relevance weight. The contract
    # path therefore has no ranking explanation, but remains explicit task input.
    zero_contract_weight = RelevanceWeights(contract_association=0)
    package = compile_context(index, query, sources, max_context_chars=40, max_file_chars=40, weights=zero_contract_weight)

    selected = {item.path: item for item in package.included}
    assert "docs/contract.md" in selected
    assert selected["docs/contract.md"].score == 0
    assert selected["docs/contract.md"].reasons == ("explicit_anchor",)
    assert package.context_chars <= 40
