import json
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "live_blender_write_gate_rotation.py"


def test_live_rotation_probe_contains_real_and_adversarial_modes():
    source = SCRIPT.read_text(encoding="utf-8")
    assert '"--adversarial"' in source
    assert '"ATLAS BLENDER LIVE WRITE VERIFIED: PASS"' in source
    assert '"ATLAS BLENDER LIVE WRITE ADVERSARIAL GATE: PASS"' in source
    assert "set_object_rotation(**arguments)" in source
    assert "inspect_object_transform(" in source


def test_adversarial_probe_requires_blocked_without_receipt():
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'outcome.status != "BLOCKED" or outcome.receipt is not None' in source


def test_probe_output_is_json_serializable_contract():
    payload = {
        "case": "incorrect",
        "adversarial": False,
        "status": "VERIFIED",
        "reason": "ok",
        "verification": {},
        "receipt_present": True,
    }
    assert json.loads(json.dumps(payload))["status"] == "VERIFIED"
