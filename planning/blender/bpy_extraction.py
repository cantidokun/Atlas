"""Thin read-only Blender bpy extraction primitive -> canonical extraction payload."""
from typing import Any, Dict, List, Optional
from planning.blender.blender_units import UnitMappingError, map_unit_system
from planning.blender.extraction_payload import PAYLOAD_SCHEMA_VERSION, validate_payload_schema
from planning.blender.transforms import euler_xyz_degrees_to_quaternion
_SORT_KEY = "name"
_OBJECT_LINK = "OBJECT"

class SceneMembershipError(ValueError):
    pass

def _discover_scene_objects(scene) -> List[Any]:
    collection=getattr(scene,"collection",None)
    if collection is None: raise SceneMembershipError("scene.collection is unavailable; cannot enumerate scene membership (fail closed)")
    members=getattr(collection,"objects",None)
    if members is None: raise SceneMembershipError("scene.collection.objects is unavailable; cannot enumerate scene membership (fail closed)")
    return list(members)

def _extract_vertex_coords(v)->List[float]:
    if hasattr(v,"co"):
        co=v.co
        if co is None or len(co)<3: raise ValueError("MeshVertex.co is malformed/absent; refusing to emit coordinates (fail closed)")
        return [round(float(co[0]),6),round(float(co[1]),6),round(float(co[2]),6)]
    if all(hasattr(v,a) for a in ("x","y","z")): return [round(float(getattr(v,a)),6) for a in ("x","y","z")]
    raise ValueError("MeshVertex has neither a usable .co nor a complete .x/.y/.z surface; refusing to manufacture coordinates (fail closed)")

def _safe_str(v)->str: return str(v)

def extract_scene(bpy)->dict:
    context=getattr(bpy,"context",None)
    if context is None: raise ValueError("bpy.context is not available; cannot extract a scene")
    try:
        scene=context.scene; scene_name=_safe_str(scene.name); unit_system=map_unit_system(scene.unit_settings)
    except UnitMappingError as exc: raise ValueError(f"cannot map Blender unit system to canonical unit: {exc}") from exc
    except Exception as exc: raise ValueError(f"cannot read Blender scene metadata: {exc}") from exc
    try: objects_raw=_discover_scene_objects(scene)
    except SceneMembershipError as exc: raise ValueError(str(exc)) from exc
    objects=[_extract_object(bpy,o) for o in sorted(objects_raw,key=lambda o:getattr(o,_SORT_KEY,""))]
    payload={"schema_version":PAYLOAD_SCHEMA_VERSION,"scene_id":scene_name,"unit_system":unit_system,"objects":objects}
    validate_payload_schema(payload); return payload

def _extract_object(bpy,obj)->dict:
    oid=_safe_str(getattr(obj,"name","")); parent=getattr(obj,"parent",None); parent_id=_safe_str(getattr(parent,"name","")) if parent is not None else None
    collections=getattr(obj,"users_collection",()) or (); collection=_safe_str(collections[0].name) if collections else None
    visible=bool(getattr(obj,"visible",True)) if hasattr(obj,"visible") else True
    location=tuple(getattr(obj.location,a,0.0) for a in ("x","y","z")) if hasattr(obj,"location") else (0.0,0.0,0.0)
    scale=tuple(getattr(obj.scale,a,1.0) for a in ("x","y","z")) if hasattr(obj,"scale") else (1.0,1.0,1.0)
    rotation=(1.0,0.0,0.0,0.0)
    if hasattr(obj,"rotation_euler"):
        try:
            import math
            raw=[float(getattr(obj.rotation_euler,a,0.0)) for a in ("x","y","z")]
            rotation=euler_xyz_degrees_to_quaternion(math.degrees(raw[0]),math.degrees(raw[1]),math.degrees(raw[2]))
        except Exception: rotation=(1.0,0.0,0.0,0.0)
    mesh=_extract_mesh(obj) if getattr(obj,"type","")=="MESH" else None
    return {"object_id":oid,"name":oid,"collection":collection,"parent_object_id":parent_id,"location":[float(v) for v in location],"scale":[float(v) for v in scale],"rotation":[float(v) for v in rotation],"visible":visible,"mesh":mesh}

# ---------------------------------------------------------------------------
# Extraction fidelity v1 §4.3 — materials: ordered, single-valued decision tree.
# Ported from the frozen producer (branch feat/blender-extraction-fidelity-v1) so that the Temporal
# v1 representation-state mechanism has a producer that can emit all three encodings.
# ---------------------------------------------------------------------------

def _material_name(value, label):
    if type(value) is not str or not value.strip():
        raise ValueError(f"{label} must be a non-empty material name; refusing to invent a token (§4.3 branch 1) (fail closed)")
    return value

def _extract_materials(obj, label):
    """Return the data-slot names, ``[]``, or ``None`` meaning "omit the key" (§4.3).

    Branch precedence is normative and single-valued:
      1. any assigned material with a malformed/empty name -> FAIL CLOSED;
      2. any unrepresentable object-level slot (``link == 'OBJECT'`` or unassigned) -> OMIT the key
         entirely; this branch dominates even when the mesh datablock has zero data slots;
      3. zero data slots (and, by branch 2, no OBJECT-linked slot) -> ``[]``;
      4. otherwise the data-slot names in exact source slot order (never lexically sorted).
    """
    object_slots=getattr(obj,"material_slots",None)
    if object_slots is None: raise ValueError(f"{label}.material_slots is unavailable; cannot determine slot representability (fail closed)")
    data_slots=getattr(getattr(obj,"data",None),"materials",None)
    if data_slots is None: raise ValueError(f"{label}.data.materials is unavailable (fail closed)")

    for slot in object_slots:
        material=getattr(slot,"material",None)
        if material is None: continue
        _material_name(getattr(material,"name",None), f"{label} material slot")

    for slot in object_slots:
        link=getattr(slot,"link",None)
        if link not in ("DATA",_OBJECT_LINK): raise ValueError(f"{label} has a material slot with an unreadable link ({link!r}) (fail closed)")
        if link==_OBJECT_LINK or getattr(slot,"material",None) is None: return None

    if len(data_slots)==0: return []

    names=[]
    for material in data_slots:
        if material is None: raise ValueError(f"{label}.data.materials contains an unassigned slot mid-list; refusing a partial list (fail closed)")
        names.append(_material_name(getattr(material,"name",None), f"{label}.data.materials[i]"))
    return names

def _extract_mesh(obj)->Optional[dict]:
    data=getattr(obj,"data",None)
    if data is None: raise ValueError(f"mesh object {getattr(obj,'name','')} has no data; refusing a count-only mesh")
    vertices_raw=getattr(data,"vertices",()) or (); vertices=[_extract_vertex_coords(v) for v in vertices_raw]
    if not vertices: raise ValueError("mesh has no vertices; refusing to emit an empty/partial mesh")
    polygons=getattr(data,"polygons",()) or (); faces=[[int(idx) for idx in poly.vertices] for poly in polygons]
    # Wave 11: zero polygons are a truthful source state. Never invent topology.
    label=_safe_str(getattr(obj,"name",""))
    mesh={"mesh_id":label,"vertices":vertices,"faces":faces,"normals":None,"uvs":None,"local_frame_id":None}
    # Extraction fidelity v1 §4.3: materials is emitted only when the decision tree permits it;
    # an unrepresentable slot omits the key entirely (omission is all-or-nothing per mesh).
    materials=_extract_materials(obj,label)
    if materials is not None: mesh["materials"]=materials
    return mesh

def run_live_blender_extraction(bpy)->dict: return extract_scene(bpy)
