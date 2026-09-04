import json

import pytest

from planning.unreal_render_receipt import UnrealRenderReceipt
from planning.unreal_render_receipt_store import UnrealRenderReceiptStore
from planning.unreal_evidence_contract import UnrealEvidence


def _receipt():
    evidence = UnrealEvidence(operation_name="inspect_render_job", entity_ids=("FIELD_SURFACE",), observed_state={"job_id": "job-persist-123", "status": "finished", "finished": True, "success": True, "failed": False, "sequence_asset_path": "/Game/AtlasTest/AtlasSequencerFixtureSequence", "output_directory": "Saved/AtlasRenderOutput", "output_format": "png", "output_files": ["C:/renders/AtlasRender_0001.png"]}, verified=True, source="render-receipt-store-test")
    return UnrealRenderReceipt.issue(evidence)


def test_store_round_trips_receipt(tmp_path):
    store = UnrealRenderReceiptStore(tmp_path / "render-receipt.json")
    receipt = _receipt()
    saved = store.save(receipt)
    restored = store.load()
    assert saved["version"] == 1
    assert restored == receipt
    assert restored.receipt_digest == receipt.receipt_digest
    assert store.exists()


def test_store_is_deterministic(tmp_path):
    path = tmp_path / "render-receipt.json"
    receipt = _receipt()
    store = UnrealRenderReceiptStore(path)
    first = store.save(receipt)
    first_bytes = path.read_bytes()
    second = store.save(receipt)
    second_bytes = path.read_bytes()
    assert first == second
    assert first_bytes == second_bytes


def test_store_rejects_tampered_receipt_digest(tmp_path):
    path = tmp_path / "render-receipt.json"
    store = UnrealRenderReceiptStore(path)
    store.save(_receipt())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["receipt_digest"] = "0" * 64
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RuntimeError, match="digest is inconsistent"):
        store.load()


def test_store_rejects_tampered_job_id(tmp_path):
    path = tmp_path / "render-receipt.json"
    store = UnrealRenderReceiptStore(path)
    store.save(_receipt())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["job_id"] = "job-attacker"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RuntimeError, match="digest is inconsistent"):
        store.load()


def test_store_rejects_extra_fields(tmp_path):
    path = tmp_path / "render-receipt.json"
    store = UnrealRenderReceiptStore(path)
    store.save(_receipt())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["unexpected"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RuntimeError, match="invalid fields"):
        store.load()


def test_store_delete_is_idempotent(tmp_path):
    store = UnrealRenderReceiptStore(tmp_path / "render-receipt.json")
    store.delete()
    assert not store.exists()
    store.save(_receipt())
    assert store.exists()
    store.delete()
    assert not store.exists()
    store.delete()
    assert not store.exists()
