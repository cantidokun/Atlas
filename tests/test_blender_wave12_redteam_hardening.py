from __future__ import annotations

from planning.blender import parent_cycle


def _scene(size: int):
    objects = []
    for index in range(size):
        objects.append(
            {
                "object_id": f"obj-{index}",
                "parent_object_id": f"obj-{index + 1}" if index + 1 < size else None,
                "name": f"name-{index}",
                "location": [index, 0, 0],
                "rotation": [1, 0, 0, 0],
                "scale": [1, 1, 1],
            }
        )
    return {"objects": objects}


def test_cycle_inventory_uses_one_scene_index_for_global_scan(monkeypatch):
    scene = _scene(5000)
    original = parent_cycle._index_objects
    calls = 0

    def counted(scene_model):
        nonlocal calls
        calls += 1
        return original(scene_model)

    monkeypatch.setattr(parent_cycle, "_index_objects", counted)
    assert parent_cycle._cycle_signatures(scene) == frozenset()
    assert calls == 1


def test_cycle_inventory_detects_long_cycle_without_per_object_reindexing(monkeypatch):
    scene = _scene(3000)
    scene["objects"][-1]["parent_object_id"] = "obj-0"
    original = parent_cycle._index_objects
    calls = 0

    def counted(scene_model):
        nonlocal calls
        calls += 1
        return original(scene_model)

    monkeypatch.setattr(parent_cycle, "_index_objects", counted)
    signatures = parent_cycle._cycle_signatures(scene)
    assert len(signatures) == 1
    assert calls == 1
