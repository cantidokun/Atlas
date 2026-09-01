import pytest

from planning.runtime_state import FutureRuntimeStateStore


def test_malformed_json_fails_closed(tmp_path):
    path = tmp_path / "runtime.json"
    path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(RuntimeError, match="not valid JSON"):
        FutureRuntimeStateStore(path).load()


def test_invalid_integrity_shape_fails_closed(tmp_path):
    path = tmp_path / "runtime.json"
    path.write_text(
        '{"version":1,"plan_digest":"x","snapshot":{"plan_digest":"x"},"runtime_integrity":[]}',
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="integrity receipt is invalid"):
        FutureRuntimeStateStore(path).load()
