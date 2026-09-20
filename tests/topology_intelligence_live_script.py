"""Disposable Blender gate for Read-Only Non-Manifold Evidence Boundary v1."""
import json
import sys
import bpy

from planning.blender.bpy_extraction import extract_scene
from planning.blender.extraction_payload import payload_to_scene_model
from planning.blender.correction_codes import PlannerState
from planning.blender.correction_planner import plan_scene_report
from planning.blender.finding_codes import FindingCode
from planning.blender.mesh_health import check_mesh
from planning.blender.scene_report import build_report
from planning.blender.topology_intelligence import analyze_topology

EXPECTED_BLENDER = (4, 4, 3)
MARKER = "ATLAS_READONLY_NON_MANIFOLD_V1_LIVE"

def profile():
    return {"name":"soccer-field","version":"1","allowed_units":["METERS","meters","m"],"name_pattern":r"^[a-z0-9][a-z0-9._-]*$"}

def add(name, verts, faces, x):
    mesh=bpy.data.meshes.new(name+"_mesh"); mesh.from_pydata(verts, [], faces); mesh.update()
    obj=bpy.data.objects.new(name, mesh); bpy.context.scene.collection.objects.link(obj); obj.location=(x,0,0)
    return obj

def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    specs=[
      ("nm_v1_boundary",[(0,0,0),(1,0,0),(0,1,0)],[(0,1,2)],0),
      ("nm_v2_manifold",[(0,0,0),(1,0,0),(0,1,0),(0,0,1)],[(0,2,1),(1,2,3)],20),
      ("nm_v3_edge3",[(0,0,0),(1,0,0),(.2,1,.5),(.3,1.2,.7),(.4,1.4,.9)],[(0,1,2),(0,1,3),(0,1,4)],40),
      ("nm_v4_edge4",[(0,0,0),(1,0,0),(.2,1,.5),(.3,1.2,.7),(.4,1.4,.9),(.5,1.6,1.1)],[(0,1,2),(0,1,3),(0,1,4),(0,1,5)],60),
      ("nm_clean_control",[(0,0,0),(1,0,0),(0,1,0),(0,0,1)],[(0,2,1),(0,1,3),(1,2,3),(2,0,3)],80),
      ("nm_two_nm_edges",[(0,0,0),(1,0,0),(0,1,0),(0,0,1),(1,1,1),(10,0,0),(11,0,0),(10,1,0),(10,0,1),(11,1,1)],[(0,1,2),(0,1,3),(0,1,4),(5,6,7),(5,6,8),(5,6,9)],100),
      ("nm_quadtri_control",[(0,0,0),(2,0,0),(2,2,0),(0,2,0),(1,1,1)],[(0,1,2,3),(1,0,4)],120),
    ]
    objs=[add(*s) for s in specs]; bpy.context.view_layer.update()
    before={o.name:(tuple(tuple(float(c) for c in v.co) for v in o.data.vertices),tuple(tuple(int(i) for i in p.vertices) for p in o.data.polygons)) for o in objs}
    checks={}
    for o,s in zip(objs,specs):
        checks[o.name+"_raw_faces"]=tuple(tuple(int(i) for i in p.vertices) for p in o.data.polygons)==tuple(tuple(f) for f in s[2])
    pa=extract_scene(bpy); pb=extract_scene(bpy); checks["repeatable_extraction"]=pa==pb
    scene=payload_to_scene_model(pa); by={o.object_id:o for o in scene.objects}
    expected={"nm_v1_boundary":[],"nm_v2_manifold":[],"nm_v3_edge3":[([0,1],3)],"nm_v4_edge4":[([0,1],4)],"nm_clean_control":[],"nm_two_nm_edges":[([0,1],3),([5,6],3)],"nm_quadtri_control":[]}
    for name, exp in expected.items():
        mesh=by[name].mesh; assert mesh is not None
        checks[name+"_canonical_faces"]=tuple(mesh.faces)==tuple(tuple(f) for f in next(s[2] for s in specs if s[0]==name))
        findings=check_mesh(mesh)
        nm=[(f.measured["edge"],f.measured["face_incidence"]) for f in findings if f.code is FindingCode.MESH_NON_MANIFOLD_EDGE]
        checks[name+"_finding"]=nm==exp
        checks[name+"_no_extra_findings"]=[f.code.value for f in findings if f.code is not FindingCode.MESH_NON_MANIFOLD_EDGE]==[]
        topo=analyze_topology(mesh)
        checks[name+"_metric_coherence"]=topo.non_manifold_edge_count==len(nm) and sum(v for k,v in topo.edge_valence_histogram if k>2)==len(nm)
        report=build_report(scene_id="nm-discovery-live",validation_state="needs_review" if nm else "ready",findings=findings,scene_metrics={},profile_name="soccer-field")
        payload=report.to_json_compatible(); payload["digest"]=report.digest()
        plan=plan_scene_report(payload,profile=profile())
        checks[name+"_planner_no_correction"]=plan.corrections==()
        checks[name+"_planner_state"]=plan.state==(PlannerState.REVIEW_REQUIRED.value if nm else PlannerState.NO_CORRECTIONS.value)
    checks["v3_exact_incidence"]=[f.measured["face_incidence"] for f in check_mesh(by["nm_v3_edge3"].mesh) if f.code is FindingCode.MESH_NON_MANIFOLD_EDGE]==[3]
    checks["v4_exact_incidence"]=[f.measured["face_incidence"] for f in check_mesh(by["nm_v4_edge4"].mesh) if f.code is FindingCode.MESH_NON_MANIFOLD_EDGE]==[4]
    checks["two_edge_order"]=[f.measured["edge"] for f in check_mesh(by["nm_two_nm_edges"].mesh) if f.code is FindingCode.MESH_NON_MANIFOLD_EDGE]==[[0,1],[5,6]]
    checks["finding_scope"]=all(f.mesh_id in expected and f.object_id is None for o in scene.objects if o.mesh for f in check_mesh(o.mesh) if f.code is FindingCode.MESH_NON_MANIFOLD_EDGE)
    after={o.name:(tuple(tuple(float(c) for c in v.co) for v in o.data.vertices),tuple(tuple(int(i) for i in p.vertices) for p in o.data.polygons)) for o in objs}
    checks["no_post_validation_mutation"]=before==after
    checks["no_save"]=bpy.data.filepath==""
    checks["fixture_count_stable"]=len(tuple(bpy.context.scene.objects))==len(objs)
    failed=[k for k,v in checks.items() if v is not True]
    passed=len(checks)-len(failed)
    payload={"marker":MARKER,"blender_version":tuple(bpy.app.version),"required_assertions":len(checks),"passed":passed,"failed":failed,"checks":checks,"save_attempted":False,"opened_frozen_asset":False}
    print(json.dumps(payload,sort_keys=True))
    if failed:return 1
    print(f"{MARKER}_PASS {passed} passed"); return 0

if __name__=="__main__": sys.exit(main())
