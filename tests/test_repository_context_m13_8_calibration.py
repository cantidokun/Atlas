from planning.repository_intelligence import build_repository_index
from planning.repository_intelligence.context import compile_context
from planning.repository_intelligence.relevance import RelevanceQuery


def test_generated_unreal_trees_are_not_indexed(tmp_path):
    (tmp_path / "planning").mkdir()
    (tmp_path / "unreal" / "AtlasUnrealHarness" / "Intermediate" / "Build").mkdir(parents=True)
    (tmp_path / "unreal" / "AtlasUnrealHarness" / "Source").mkdir(parents=True)
    (tmp_path / "planning" / "target.py").write_text("class Target: pass\n", encoding="utf-8")
    (tmp_path / "unreal" / "AtlasUnrealHarness" / "Intermediate" / "Build" / "Generated.h").write_text("generated noise\n", encoding="utf-8")
    (tmp_path / "unreal" / "AtlasUnrealHarness" / "Source" / "Atlas.cpp").write_text("source\n", encoding="utf-8")

    index = build_repository_index(tmp_path, include_git_history=False)
    paths = {item["path"] for item in index.files}

    assert "planning/target.py" in paths
    assert "unreal/AtlasUnrealHarness/Source/Atlas.cpp" in paths
    assert "unreal/AtlasUnrealHarness/Intermediate/Build/Generated.h" not in paths


def test_secondary_selection_has_a_hard_file_cap(tmp_path):
    (tmp_path / "planning").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "planning" / "target.py").write_text("class Target: pass\n", encoding="utf-8")
    sources = {"planning/target.py": "class Target: pass\n"}
    for index in range(20):
        path = tmp_path / "docs" / f"note_{index}.md"
        content = f"recovery boundary architecture signal {index}\n"
        path.write_text(content, encoding="utf-8")
        sources[path.relative_to(tmp_path).as_posix()] = content

    index = build_repository_index(tmp_path, include_git_history=False)
    query = RelevanceQuery.from_values(paths=["planning/target.py"], text="recovery boundary architecture")
    package = compile_context(index, query, sources, max_context_chars=32_000, max_file_chars=1_000)

    selected = [item.path for item in package.included if item.path.startswith("docs/")]
    assert len(selected) <= 8
    assert package.context_chars <= 32_000


def test_selection_fingerprint_is_stable_after_calibration(tmp_path):
    (tmp_path / "target.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    index = build_repository_index(tmp_path, include_git_history=False)
    query = RelevanceQuery.from_values(paths=["target.py"])
    sources = {"target.py": "def run():\n    return 1\n"}

    first = compile_context(index, query, sources)
    second = compile_context(index, query, sources)

    assert first.selection_fingerprint == second.selection_fingerprint
    assert first.fingerprint == second.fingerprint
