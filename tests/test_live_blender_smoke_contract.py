from pathlib import Path


def test_live_blender_smoke_is_explicitly_opt_in():
    path = Path(__file__).parent / "live_blender_smoke.py"
    source = path.read_text(encoding="utf-8")

    assert 'TARGET_FILE = "atlas_live_smoke.blend"' in source
    assert "ATLAS_LIVE_BLENDER_SMOKE_PASS" in source
    assert "execute_verified" in source
    assert '"inspect_scene"' in source
