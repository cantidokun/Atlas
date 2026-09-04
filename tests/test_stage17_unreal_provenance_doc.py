from pathlib import Path


def test_stage17_unreal_provenance_document_exists_and_states_safety_boundary():
    path = Path(__file__).parents[1] / "docs" / "STAGE17_UNREAL_PROVENANCE.md"
    text = path.read_text(encoding="utf-8")
    assert "verified `inspect_render_job` evidence" in text
    assert "output_files" in text
    assert "engine identity to remain `Unreal`" in text
    assert "do not execute Unreal work" in text
    assert "Cross-process Unreal render-job recovery" in text
