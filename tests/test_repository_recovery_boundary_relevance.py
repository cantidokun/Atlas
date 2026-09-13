from planning.repository_intelligence import build_repository_index
from planning.repository_intelligence.relevance import RelevanceQuery, rank_repository_files


def test_execution_boundary_role_is_domain_anchored(tmp_path):
    (tmp_path / "planning").mkdir()
    (tmp_path / "planning" / "unreal_render_recovery_coordinator.py").write_text(
        "from planning.unreal_execution_boundary import Boundary\n",
        encoding="utf-8",
    )
    (tmp_path / "planning" / "unreal_execution_boundary.py").write_text(
        "class Boundary: pass\n",
        encoding="utf-8",
    )
    (tmp_path / "planning" / "blender_execution_boundary.py").write_text(
        "class Boundary: pass\n",
        encoding="utf-8",
    )
    index = build_repository_index(tmp_path, include_git_history=False)
    query = RelevanceQuery.from_values(
        text="Unreal recovery failed execution boundary no retry",
        paths=["planning/unreal_render_recovery_coordinator.py"],
    )
    result = rank_repository_files(index, query)

    unreal = next(item for item in result.explanations if item.path == "planning/unreal_execution_boundary.py")
    blender = next(item for item in result.explanations if item.path == "planning/blender_execution_boundary.py")

    assert "architectural_role:execution_boundary" in unreal.reasons
    assert "architectural_role:execution_boundary" not in blender.reasons
    assert result.ranked_paths().index("planning/unreal_execution_boundary.py") < result.ranked_paths().index("planning/blender_execution_boundary.py")
