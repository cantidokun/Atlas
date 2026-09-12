from planning.repository_intelligence import build_repository_index
from planning.repository_intelligence.context import compile_context
from planning.repository_intelligence.relevance import RelevanceQuery


def test_context_compilation_is_bounded_and_explainable(tmp_path):
    (tmp_path / "planning").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "planning" / "target.py").write_text("class Target:\n    pass\n", encoding="utf-8")
    (tmp_path / "planning" / "helper.py").write_text("class Helper:\n    pass\n", encoding="utf-8")
    (tmp_path / "tests" / "test_target.py").write_text("from planning.target import Target\n", encoding="utf-8")
    index = build_repository_index(tmp_path, include_git_history=False)
    sources = {
        "planning/target.py": "class Target:\n    pass\n",
        "planning/helper.py": "class Helper:\n    pass\n",
        "tests/test_target.py": "from planning.target import Target\n",
    }

    package = compile_context(index, RelevanceQuery.from_values(paths=["planning/target.py"]), sources, max_context_chars=35)

    assert package.context_chars <= 35
    assert package.included[0].path == "planning/target.py"
    assert package.included[0].score > 0
    repeated = compile_context(index, RelevanceQuery.from_values(paths=["planning/target.py"]), sources, max_context_chars=35)
    assert package.fingerprint == repeated.fingerprint
    assert package.selection_fingerprint == repeated.selection_fingerprint


def test_explicit_context_anchors_are_admitted_before_secondary_context(tmp_path):
    (tmp_path / "planning").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "planning" / "target.py").write_text("target content\n", encoding="utf-8")
    (tmp_path / "planning" / "helper.py").write_text("helper content\n", encoding="utf-8")
    (tmp_path / "docs" / "contract.md").write_text("contract content\n", encoding="utf-8")
    index = build_repository_index(tmp_path, include_git_history=False)
    sources = {
        "planning/target.py": "target content\n",
        "planning/helper.py": "helper content\n",
        "docs/contract.md": "contract content\n",
    }
    query = RelevanceQuery.from_values(paths=["planning/target.py"], contract_paths=["docs/contract.md"])

    package = compile_context(index, query, sources, max_context_chars=30, max_file_chars=100)

    selected = [item.path for item in package.included]
    assert selected == ["planning/target.py", "docs/contract.md"]
    assert "planning/helper.py" in package.excluded_paths


def test_secondary_signal_coverage_precedes_remaining_ranked_context(tmp_path):
    (tmp_path / "planning").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "planning" / "target.py").write_text("target content\n", encoding="utf-8")
    (tmp_path / "planning" / "helper.py").write_text("helper content\n", encoding="utf-8")
    (tmp_path / "docs" / "recovery_notes.md").write_text("recovery notes\n", encoding="utf-8")
    index = build_repository_index(tmp_path, include_git_history=False)
    sources = {
        "planning/target.py": "target content\n",
        "planning/helper.py": "helper content\n",
        "docs/recovery_notes.md": "recovery notes\n",
    }
    query = RelevanceQuery.from_values(paths=["planning/target.py"], text="recovery")

    package = compile_context(index, query, sources, max_context_chars=35, max_file_chars=100)

    selected = [item.path for item in package.included]
    assert selected[0] == "planning/target.py"
    assert "docs/recovery_notes.md" in selected


def test_truncation_prefers_line_boundary(tmp_path):
    (tmp_path / "target.py").write_text("line one\nline two\nline three\n", encoding="utf-8")
    index = build_repository_index(tmp_path, include_git_history=False)
    package = compile_context(index, RelevanceQuery.from_values(paths=["target.py"]), {"target.py": "line one\nline two\nline three\n"}, max_context_chars=19, max_file_chars=100)
    assert package.included[0].truncated is True
    assert package.included[0].content == "line one\nline two"


def test_selection_fingerprint_ignores_dynamic_state(tmp_path):
    (tmp_path / "target.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    index = build_repository_index(tmp_path, include_git_history=False)
    query = RelevanceQuery.from_values(paths=["target.py"])
    sources = {"target.py": "def run():\n    return 1\n"}
    first = compile_context(index, query, sources, dynamic_state={"current_step": 1})
    second = compile_context(index, query, sources, dynamic_state={"current_step": 2})
    assert first.selection_fingerprint == second.selection_fingerprint
    assert first.fingerprint != second.fingerprint


def test_sensitive_files_are_never_compiled(tmp_path):
    (tmp_path / "planning").mkdir()
    (tmp_path / "planning" / "target.py").write_text("class Target: pass\n", encoding="utf-8")
    (tmp_path / ".env").write_text("TOKEN=do-not-include\n", encoding="utf-8")
    index = build_repository_index(tmp_path, include_git_history=False)
    package = compile_context(index, RelevanceQuery.from_values(paths=[".env"]), {".env": "TOKEN=do-not-include\n"})
    assert all(item.path != ".env" for item in package.included)
    assert ".env" in package.excluded_paths


def test_dynamic_state_stays_out_of_stable_instructions(tmp_path):
    (tmp_path / "target.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    index = build_repository_index(tmp_path, include_git_history=False)
    package = compile_context(index, RelevanceQuery.from_values(paths=["target.py"]), {"target.py": "def run():\n    return 1\n"}, stable_instructions="STATIC RULES", dynamic_state={"current_step": 3})
    assert package.stable_instructions == "STATIC RULES"
    assert package.dynamic_state == {"current_step": 3}
    assert "current_step" not in package.stable_instructions


def test_missing_source_is_excluded_not_fabricated(tmp_path):
    (tmp_path / "target.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    index = build_repository_index(tmp_path, include_git_history=False)
    package = compile_context(index, RelevanceQuery.from_values(paths=["target.py"]), {})
    assert package.included == ()
    assert "target.py" in package.excluded_paths
