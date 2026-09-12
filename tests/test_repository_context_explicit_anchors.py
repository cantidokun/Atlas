from planning.repository_intelligence import build_repository_index
from planning.repository_intelligence.context import compile_context
from planning.repository_intelligence.relevance import RelevanceQuery


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
        "planning/target.py",
        "docs/contract.md",
        "tests/test_target.py",
    ]
    assert all(item.truncated for item in package.included[:3])
    assert package.context_chars <= 90
