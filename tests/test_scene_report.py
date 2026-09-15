"""Deterministic canonical SceneReport input/report contract tests."""
import json
import pytest
from planning.blender import FindingCode, SceneReport, SceneReportInputError, parse_scene_report_input, run_scene_health, scene_input_digest, soccer_field_profile
from planning.blender.scene_model import MeshModel, ObjectModel, SceneModel


def _quad(mid, ox):
    return MeshModel(mesh_id=mid, vertices=((ox,0,0),(ox+1,0,0),(ox,1,0),(ox+1,1,0)), faces=((0,1,2),(1,3,2)))

def _valid_scene():
    return SceneModel(scene_id="s1", unit_system="METERS", objects=(ObjectModel("pitch","pitch",mesh=_quad("m1",0)), ObjectModel("goal_left","goal_left",mesh=_quad("m2",6)), ObjectModel("goal_right","goal_right",mesh=_quad("m3",10))))


def test_valid_parse_roundtrip():
    scene=parse_scene_report_input({"scene_id":"s1","unit_system":"METERS","objects":[{"object_id":"pitch","name":"pitch","mesh":{"mesh_id":"m1","vertices":[[0,0,0],[1,0,0],[0,1,0]],"faces":[[0,1,2]]}}]})
    assert scene.objects[0].mesh.faces==((0,1,2),)

@pytest.mark.parametrize("bad", [{"objects":()}, {"scene_id":"","objects":()}, {"scene_id":"s","unit_system":"M","objects":(),"unknown_key":1}, {"scene_id":"s","unit_system":"M","objects":[{"object_id":1,"name":"x"}]}, {"scene_id":"s","unit_system":"M","objects":[{"object_id":"o","name":"n","mesh":{"mesh_id":"m","vertices":[[0,0,0]],"faces":[[]]}}]}])
def test_malformed_input_fails_closed(bad):
    with pytest.raises((SceneReportInputError,ValueError,TypeError)): parse_scene_report_input(bad)


def test_empty_mesh_contract():
    empty=MeshModel(mesh_id="empty",vertices=(),faces=())
    zero_face=MeshModel(mesh_id="zero_face",vertices=((1,2,3),(4,5,6)),faces=())
    assert empty==MeshModel(mesh_id="empty",vertices=(),faces=())
    assert zero_face.faces==()
    with pytest.raises(SceneReportInputError): MeshModel(mesh_id="bad",vertices=(),faces=((0,1,2),))


def test_required_contract_validation():
    with pytest.raises((SceneReportInputError,ValueError)): MeshModel(mesh_id="m",vertices=((0,0,float("inf")),),faces=((0,),))
    with pytest.raises((SceneReportInputError,ValueError)): MeshModel(mesh_id="m",vertices=((True,0,0),),faces=((0,),))
    with pytest.raises((SceneReportInputError,TypeError)): parse_scene_report_input(type("Lousy",(list,),{})())


def test_empty_mesh_parse_roundtrip_and_digest():
    raw={"scene_id":"s","unit_system":"METERS","objects":[{"object_id":"empty","name":"empty","mesh":{"mesh_id":"m","vertices":[],"faces":[]}}]}
    scene=parse_scene_report_input(raw)
    assert scene.objects[0].mesh==MeshModel(mesh_id="m",vertices=(),faces=())
    assert scene_input_digest(scene)==scene_input_digest(parse_scene_report_input(raw))


def test_report_determinism_digest_and_no_source_mutation():
    scene=_valid_scene(); before=scene
    r1=run_scene_health(scene,soccer_field_profile()); r2=run_scene_health(scene,soccer_field_profile())
    assert r1.canonical_json()==r2.canonical_json(); assert len(r1.digest())==64; assert scene==before
    assert r1.input_digest==scene_input_digest(scene)


def test_metrics_and_findings():
    scene=_valid_scene(); report=run_scene_health(scene,soccer_field_profile())
    assert report.scene_metrics["object_count"]==3 and report.scene_metrics["mesh_object_count"]==3
    assert report.scene_metrics["total_vertices"]==12 and report.findings_for(mesh_id="m1")==()
    bad=MeshModel(mesh_id="m1",vertices=scene.objects[0].mesh.vertices,faces=((0,1,99),))
    scene2=SceneModel(scene_id="s1",unit_system="METERS",objects=(ObjectModel("pitch","pitch",mesh=bad),)+scene.objects[1:])
    assert any(f.code is FindingCode.MESH_INVALID_INDEX for f in run_scene_health(scene2,soccer_field_profile()).findings)


def test_empty_scene_and_scene_without_meshes():
    empty=SceneModel(scene_id="empty",unit_system="METERS",objects=())
    report=run_scene_health(empty,soccer_field_profile()); assert isinstance(report,SceneReport); assert report.validation_state=="needs_review"
    roles=SceneModel(scene_id="s",unit_system="METERS",objects=(ObjectModel("pitch","pitch"),ObjectModel("goal_left","goal_left"),ObjectModel("goal_right","goal_right")))
    assert run_scene_health(roles,soccer_field_profile()).validation_state=="production_ready"


def test_large_coordinate_and_zero_scale_regressions():
    from planning.blender.mesh_health import check_mesh, check_mesh_in_envelope
    m=MeshModel("m",((1_000_000_000.5,0,0),(1_000_000_001.5,0,0),(1_000_000_000.5,1,0)),((0,1,2),))
    assert not check_mesh(m); assert any(f.code.value=="MESH_SCALE_OUT_OF_RANGE" for f in check_mesh_in_envelope(m,(-50,-40,0),(50,40,12)))
    from planning.blender.scene_health import check_scene
    assert FindingCode.OBJECT_TRANSFORM_INVALID in [f.code for f in check_scene(SceneModel("s","METERS",(ObjectModel("o","o_x",scale=(0,0,0)),)),soccer_field_profile())]


def test_profile_digest_and_uv_roundtrip():
    base=soccer_field_profile(); strict=soccer_field_profile(envelope_min=(-1,-1,-1),envelope_max=(1,1,1)); assert run_scene_health(_valid_scene(),base).digest()!=run_scene_health(_valid_scene(),strict).digest()
    m=MeshModel("m",((0,0,0),(1,0,0),(0,1,0)),((0,1,2),),uvs=((.25,.5),)); s=SceneModel("s","METERS",(ObjectModel("pitch","pitch",mesh=m),ObjectModel("goal_left","goal_left"),ObjectModel("goal_right","goal_right"))); assert run_scene_health(s,base).scene_metrics["mesh_metrics"]["m"]["faces"]==1


def test_small_mesh_clean():
    m=MeshModel("m",((0,0,0),(1,0,0),(0,1,0)),((0,1,2),)); assert not run_scene_health(SceneModel("s","METERS",(ObjectModel("pitch","pitch",mesh=m),ObjectModel("goal_left","goal_left"),ObjectModel("goal_right","goal_right"))),soccer_field_profile()).findings
