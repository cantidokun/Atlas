"""Wave-6 bounded isolated-vertex removal.

Pure canonical-model mutation only. No bpy, operators, persistence, recovery, or implicit vertex selection.
"""
from __future__ import annotations
import hashlib, json
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, Tuple
from planning.blender.scene_model import MeshModel, ObjectModel, SceneModel

CORRECTION_TYPE = "REMOVE_ISOLATED_VERTICES"
PLANNER_VERSION = "1"
_ALLOWED_PARAMS = frozenset({"expected_isolated_vertex_indices"})

class IsolatedVertexRemovalError(ValueError):
    def __init__(self, message: str, code: str):
        super().__init__(message); self.code = code

@dataclass(frozen=True)
class IsolatedVertexPlan:
    correction_id: str; plan_id: str; source_report_digest: str; target_object_id: str; mesh_id: str; expected_isolated_vertex_indices: Tuple[int, ...]
    def to_dict(self) -> dict:
        return {"planner_version":PLANNER_VERSION,"correction_type":CORRECTION_TYPE,"correction_id":self.correction_id,"source_report_digest":self.source_report_digest,"target_object_id":self.target_object_id,"mesh_id":self.mesh_id,"params":{"expected_isolated_vertex_indices":list(self.expected_isolated_vertex_indices)},"plan_id":self.plan_id}

@dataclass(frozen=True)
class ExecutionOutcome:
    ok: bool; outcome: str; failure_code: Optional[str]; source_report_digest: str; output_report_digest: Optional[str]; scene: Optional[SceneModel]=None

def _canonical_bytes(value: Any)->bytes:
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode("utf-8")
def _digest(value: Any)->str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()
def _find_object(scene: SceneModel, object_id: str)->Optional[ObjectModel]:
    matches=[o for o in scene.objects if o.object_id==object_id]
    return matches[0] if len(matches)==1 else None

def _validate_face_indices(mesh: MeshModel)->None:
    n=len(mesh.vertices)
    for fi,face in enumerate(mesh.faces):
        for idx in face:
            if type(idx) is not int or isinstance(idx,bool): raise IsolatedVertexRemovalError(f"face {fi} contains a non-integer vertex index","FACE_INDEX_INVALID")
            if not 0<=idx<n: raise IsolatedVertexRemovalError(f"face {fi} contains vertex index {idx} outside 0..{n-1}","FACE_INDEX_OUT_OF_RANGE")

def _isolated_indices(mesh: MeshModel)->Tuple[int,...]:
    _validate_face_indices(mesh); referenced={i for f in mesh.faces for i in f}; return tuple(i for i in range(len(mesh.vertices)) if i not in referenced)

def _validate_isolated_indices(indices: Any)->Tuple[int,...]:
    if type(indices) not in (tuple,list): raise IsolatedVertexRemovalError("expected_isolated_vertex_indices must be a tuple/list","INDICES_TYPE_INVALID")
    if any(type(i) is not int or isinstance(i,bool) for i in indices): raise IsolatedVertexRemovalError("isolated vertex indices must be exact integers","INDEX_TYPE_INVALID")
    result=tuple(indices)
    if any(i<0 for i in result): raise IsolatedVertexRemovalError("isolated vertex indices must be non-negative","INDEX_NEGATIVE")
    if tuple(sorted(set(result)))!=result: raise IsolatedVertexRemovalError("isolated vertex indices must be sorted and unique","INDEX_ORDER_INVALID")
    return result

def _plan_body(*,target_object_id:str,mesh_id:str,expected:Tuple[int,...],source_digest:str)->dict:
    cid=_digest({"correction_type":CORRECTION_TYPE,"target_object_id":target_object_id,"mesh_id":mesh_id,"expected_isolated_vertex_indices":list(expected),"source_report_digest":source_digest})
    body={"planner_version":PLANNER_VERSION,"correction_type":CORRECTION_TYPE,"correction_id":cid,"source_report_digest":source_digest,"target_object_id":target_object_id,"mesh_id":mesh_id,"params":{"expected_isolated_vertex_indices":list(expected)}}
    return {**body,"plan_id":_digest(body)}

def plan_isolated_vertex_removal(scene:SceneModel,source_report_digest:str,*,target_object_id:str,expected_isolated_vertex_indices:Any)->Mapping[str,Any]:
    if type(source_report_digest) is not str or len(source_report_digest)!=64: raise IsolatedVertexRemovalError("source report digest must be a 64-character string","SOURCE_DIGEST_INVALID")
    if type(target_object_id) is not str or not target_object_id: raise IsolatedVertexRemovalError("target object id is required","TARGET_OBJECT_INVALID")
    expected=_validate_isolated_indices(expected_isolated_vertex_indices)
    target=_find_object(scene,target_object_id)
    if target is None or target.mesh is None: raise IsolatedVertexRemovalError("target object must resolve to one mesh","TARGET_NOT_FOUND")
    actual=_isolated_indices(target.mesh)
    if actual!=expected: raise IsolatedVertexRemovalError("authorized set must exactly equal current isolated set","ISOLATED_SET_MISMATCH")
    return _plan_body(target_object_id=target.object_id,mesh_id=target.mesh.mesh_id,expected=expected,source_digest=source_report_digest)

def _remap_mesh(mesh:MeshModel,removed:Tuple[int,...])->MeshModel:
    removed_set=set(removed); survivors=tuple(i for i in range(len(mesh.vertices)) if i not in removed_set); mapping={old:new for new,old in enumerate(survivors)}
    return MeshModel(mesh_id=mesh.mesh_id,vertices=tuple(mesh.vertices[i] for i in survivors),faces=tuple(tuple(mapping[idx] for idx in face) for face in mesh.faces),normals=mesh.normals,uvs=mesh.uvs,materials=mesh.materials,local_frame_id=mesh.local_frame_id)

def _replace_target(scene:SceneModel,target_id:str,new_mesh:MeshModel)->SceneModel:
    return SceneModel(scene_id=scene.scene_id,unit_system=scene.unit_system,objects=tuple(ObjectModel(object_id=o.object_id,name=o.name,collection=o.collection,parent_object_id=o.parent_object_id,location=o.location,scale=o.scale,rotation=o.rotation,visible=o.visible,mesh=new_mesh if o.object_id==target_id else o.mesh) for o in scene.objects),coordinate_frame=scene.coordinate_frame,world_bounds=scene.world_bounds)

def execute_remove_isolated_vertices(plan:Mapping[str,Any],authorization:Mapping[str,Any],*,extractor:Callable[[],Tuple[SceneModel,str]])->ExecutionOutcome:
    source=plan.get("source_report_digest")
    if plan.get("correction_type")!=CORRECTION_TYPE: return ExecutionOutcome(False,"PLAN_INVALID","CORRECTION_TYPE_MISMATCH",str(source),None)
    params=plan.get("params")
    if type(params) is not dict or set(params)!=_ALLOWED_PARAMS: return ExecutionOutcome(False,"PLAN_INVALID","PARAMS_INVALID",str(source),None)
    try: expected=_validate_isolated_indices(params["expected_isolated_vertex_indices"])
    except IsolatedVertexRemovalError as exc: return ExecutionOutcome(False,"PLAN_INVALID",exc.code,str(source),None)
    if authorization.get("decision")!="APPROVED" or authorization.get("correction_type")!=CORRECTION_TYPE: return ExecutionOutcome(False,"AUTHORIZATION_REFUSED","AUTHORIZATION_INVALID",str(source),None)
    for key in ("correction_id","plan_id","source_report_digest"):
        if authorization.get(key)!=plan.get(key): return ExecutionOutcome(False,"AUTHORIZATION_REFUSED",key.upper()+"_MISMATCH",str(source),None)
    target_id=plan.get("target_object_id"); mesh_id=plan.get("mesh_id")
    expected_plan=_plan_body(target_object_id=target_id,mesh_id=mesh_id,expected=expected,source_digest=source)
    if plan.get("correction_id")!=expected_plan["correction_id"] or plan.get("plan_id")!=expected_plan["plan_id"]: return ExecutionOutcome(False,"PLAN_INVALID","PLAN_ID_MISMATCH",str(source),None)
    before,fresh_digest=extractor()
    if fresh_digest!=source: return ExecutionOutcome(False,"SOURCE_MISMATCH","SOURCE_DIGEST_MISMATCH",fresh_digest,None)
    target=_find_object(before,target_id)
    if target is None or target.mesh is None or target.mesh.mesh_id!=mesh_id: return ExecutionOutcome(False,"PRECONDITION_FAILED","TARGET_MISMATCH",fresh_digest,None)
    try: actual=_isolated_indices(target.mesh)
    except IsolatedVertexRemovalError as exc: return ExecutionOutcome(False,"PRECONDITION_FAILED",exc.code,fresh_digest,None)
    if actual!=expected: return ExecutionOutcome(False,"PRECONDITION_FAILED","ISOLATED_SET_MISMATCH",fresh_digest,None)
    after=_replace_target(before,target_id,_remap_mesh(target.mesh,expected))
    after_target=_find_object(after,target_id)
    if after_target is None or after_target.mesh is None: return ExecutionOutcome(False,"POSTCONDITION_FAILED","TARGET_MISSING",fresh_digest,None)
    if _isolated_indices(after_target.mesh): return ExecutionOutcome(False,"POSTCONDITION_FAILED","ISOLATED_VERTICES_REMAIN",fresh_digest,None)
    if tuple(o.object_id for o in after.objects)!=tuple(o.object_id for o in before.objects): return ExecutionOutcome(False,"POSTCONDITION_FAILED","OBJECT_IDENTITY_CHANGED",fresh_digest,None)
    for bo,ao in zip(before.objects,after.objects):
        if bo.object_id==target_id:
            if (bo.name,bo.collection,bo.parent_object_id,bo.location,bo.scale,bo.rotation,bo.visible)!=(ao.name,ao.collection,ao.parent_object_id,ao.location,ao.scale,ao.rotation,ao.visible): return ExecutionOutcome(False,"POSTCONDITION_FAILED","TARGET_OBJECT_STATE_CHANGED",fresh_digest,None)
        elif bo!=ao: return ExecutionOutcome(False,"POSTCONDITION_FAILED","UNRELATED_OBJECT_CHANGED",fresh_digest,None)
    removed_set=set(expected); mapping={old:new for new,old in enumerate(i for i in range(len(target.mesh.vertices)) if i not in removed_set)}; expected_faces=tuple(tuple(mapping[i] for i in face) for face in target.mesh.faces)
    if after_target.mesh.faces!=expected_faces or len(after_target.mesh.faces)!=len(target.mesh.faces): return ExecutionOutcome(False,"POSTCONDITION_FAILED","FACE_REMAP_MISMATCH",fresh_digest,None)
    output_digest=_digest({"mesh_id":after_target.mesh.mesh_id,"vertices":after_target.mesh.vertices,"faces":after_target.mesh.faces})
    return ExecutionOutcome(True,"CORRECTION_APPLIED",None,fresh_digest,output_digest,after)
