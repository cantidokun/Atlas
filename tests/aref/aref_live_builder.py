"""A-REF in-Blender fixture builder + raw-state witness (R4F 24 steps 3/4; section 9.8).

Imports ``bpy`` at module level: this module is imported ONLY by the in-Blender stage scripts.
The controller must never import it (the A-REF import-boundary test asserts the controller path
loads no bpy-importing module).
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import bpy  # noqa: F401  (Blender-only module; never imported outside a Blender process)

from tests.aref.aref_live_common import LiveError


def reset_scene() -> Any:
    """Disposable deterministic scene: remove every object/datablock/collection but the master."""
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)
    for mat in list(bpy.data.materials):
        bpy.data.materials.remove(mat)
    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)
    scene = bpy.context.scene
    return scene


def build_scene_from_spec(spec: Any) -> Dict[str, Any]:
    """Construct the live scene from the FIX literals ONLY (R4F 24 step 3).

    Realises: mesh datablocks with exact names and tables; objects with exact labels; the declared
    sharing structure (multiple objects referencing ONE datablock); transforms (quaternion mode),
    visibility; material slots; every object linked into the master scene collection (so the
    section 5.4 representative collection is null for master-only objects, as the pure projection
    declares). No runtime value influences the construction.
    """
    scene = reset_scene()
    scene.name = spec.scene["scene_id"]
    try:
        scene.unit_settings.system = "METRIC"
        scene.unit_settings.scale_length = 1.0
    except Exception:  # pragma: no cover - unit settings are always present in 4.x
        pass

    meshes: Dict[str, Any] = {}
    for db in spec.datablocks:
        mesh = bpy.data.meshes.new(db["db_name"])
        mesh.from_pydata([tuple(float(c) for c in v) for v in db["vertices"]], [],
                         [tuple(int(i) for i in f) for f in db["faces"]])
        mesh.update()
        materials = db.get("materials")
        if materials not in (None, "OMITTED"):
            for name in materials:
                mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
                mesh.materials.append(mat)
        meshes[db["db_key"]] = mesh

    objects: Dict[str, Any] = {}
    for record in spec.objects:
        db_key = record.get("datablock_key")
        obj = bpy.data.objects.new(record["object_id"], meshes[db_key] if db_key else None)
        obj.rotation_mode = "QUATERNION"
        obj.rotation_quaternion = tuple(float(c) for c in record.get("rotation", [1.0, 0.0, 0.0, 0.0]))
        obj.location = tuple(float(c) for c in record.get("location", [0.0, 0.0, 0.0]))
        obj.scale = tuple(float(c) for c in record.get("scale", [1.0, 1.0, 1.0]))
        obj.hide_viewport = not bool(record.get("visible", True))
        obj.hide_render = not bool(record.get("visible", True))
        parent_id = record.get("parent_object_id")
        if parent_id is not None:
            obj.parent = objects[parent_id]
        scene.collection.objects.link(obj)
        for slot in record.get("material_slots", []):
            link, name = slot[0], slot[1]
            mat = None if name is None else (bpy.data.materials.get(name) or bpy.data.materials.new(name))
            obj.data.materials.append(mat)
            obj.material_slots[-1].link = link
        objects[record["object_id"]] = obj
    return {"scene": scene, "meshes": meshes, "objects": objects}


def raw_graph_witness() -> Dict[str, Any]:
    """Live graph witness from RAW Blender state (R4F 24 step 4; section 9.8).

    Same shape as the pure-side witness: objects (name/type/data_block_name) in canonical
    ascending-name order; sharing groups by datablock name; the material-slot table; the order.
    """
    objects: List[Dict[str, Any]] = []
    names = sorted(obj.name for obj in bpy.data.objects)
    for name in names:
        obj = bpy.data.objects[name]
        db_name = None
        data = getattr(obj, "data", None)
        if obj.type == "MESH" and data is not None:
            db_name = data.name
        objects.append({"name": obj.name, "type": obj.type, "data_block_name": db_name})
    shared: Dict[str, List[str]] = {}
    for obj in sorted(bpy.data.objects, key=lambda o: o.name):
        data = getattr(obj, "data", None)
        db_name = data.name if (obj.type == "MESH" and data is not None) else None
        if db_name is not None:
            shared.setdefault(db_name, []).append(obj.name)
    slots: List[List[Any]] = []
    for name in names:
        obj = bpy.data.objects[name]
        for slot in getattr(obj, "material_slots", []):
            mat = getattr(slot, "material", None)
            slots.append([slot.link, None if mat is None else mat.name])
    return {"objects": objects, "shared": shared, "material_slots": slots, "order": names}


def raw_tables(object_name: str) -> Dict[str, Any]:
    """Raw vertex/face tables of one object's datablock (independent of the extraction model)."""
    obj = bpy.data.objects.get(object_name)
    if obj is None or getattr(obj, "data", None) is None:
        raise LiveError("FIXTURE-CONSTRUCTION-FAILURE", f"object {object_name!r} has no readable mesh")
    data = obj.data
    return {
        "vertices": [[float(c) for c in v.co] for v in data.vertices],
        "faces": [[int(i) for i in p.vertices] for p in data.polygons],
        "data_block_name": data.name,
    }


def assert_construction(spec: Any, witness: Dict[str, Any]) -> List[str]:
    """Raw-Blender assertions of the constructed fixture against the declared literals (step 3).

    Returns the list of assertion labels that PASSED; raises FIXTURE-CONSTRUCTION-FAILURE on the
    first mismatch (no executor invocation, no mutation, OC8-family, no verdict).
    """
    passed: List[str] = []
    declared = spec.expected["graph_witness"]
    for key in ("objects", "shared", "order"):
        if witness.get(key) != declared.get(key):
            raise LiveError("FIXTURE-CONSTRUCTION-FAILURE",
                            f"live graph witness [{key}] {witness.get(key)!r} != declared {declared.get(key)!r}")
        passed.append(f"witness:{key}")
    if "material_slots" in declared and witness["material_slots"] != declared["material_slots"]:
        raise LiveError("FIXTURE-CONSTRUCTION-FAILURE",
                        f"live material_slots {witness['material_slots']!r} != declared "
                        f"{declared['material_slots']!r}")
    passed.append("witness:material_slots")
    # raw tables per datablock (after the six-decimal/float32 conventions: exact literals only)
    for db in spec.datablocks:
        owner = None
        for record in spec.objects:
            if record.get("datablock_key") == db["db_key"]:
                owner = record["object_id"]
                break
        if owner is None:
            continue
        tables = raw_tables(owner)
        if tables["data_block_name"] != db["db_name"]:
            raise LiveError("FIXTURE-CONSTRUCTION-FAILURE",
                            f"datablock name {tables['data_block_name']!r} != declared {db['db_name']!r}")
        declared_verts = [[float(c) for c in v] for v in db["vertices"]]
        declared_faces = [[int(i) for i in f] for f in db["faces"]]
        if _float32_exact(tables["vertices"]) != _float32_exact(declared_verts):
            raise LiveError("FIXTURE-CONSTRUCTION-FAILURE",
                            f"live vertices for {owner!r} do not match the declared float32-exact table")
        if tables["faces"] != declared_faces:
            raise LiveError("FIXTURE-CONSTRUCTION-FAILURE",
                            f"live faces for {owner!r} {tables['faces']!r} != declared {declared_faces!r}")
        passed.append(f"tables:{db['db_name']}")
    return passed


def _float32_exact(values: Any) -> Any:
    """Compare through the engine's float32 storage (Blender stores vertex coordinates as float32)."""
    import struct

    def one(value: float) -> float:
        return struct.unpack("<f", struct.pack("<f", float(value)))[0]

    return [[one(c) for c in row] for row in values]
