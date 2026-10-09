"""A-REF staged live DRIVER (controller side; R4F 24 steps 2/6/8/12). bpy-free.

The controller:
  * builds the PURE case from the FIX literals (never from live state) — step 2/8;
  * launches the PROBE (Blender) and verifies its evidence against the declared literals — step 6;
  * withholds the EXECUTION launch on ANY mismatch (the real controller-enforced pre-mutation gate);
  * writes the verified plan artifact BYTES and the handoff, launches the EXECUTION (Blender);
  * aggregates and compares pure vs live evidence (steps 11/12) with the existing comparator.

Refusal/failure categories come from aref_live_common; the driver never invents production codes.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tests.aref.aref_evidence import ComparisonResult, compare_normal_forms, outcome_normal_form
from tests.aref.aref_harness import load_plan_artifact, run_pure_case
from tests.aref.aref_live_common import (EXEC_BEGIN, EXEC_END, LiveError, PROBE_BEGIN, PROBE_END,
                                         artifact, build_handoff, canonical_digest,
                                         fixture_spec_sha256, load_case_live, parse_marker,
                                         sha256_hex, validate_handoff, write_json)
from tests.aref.aref_plan import (canonical_plan_bytes, plan_artifact_digest, plan_identity,
                                  raw_to_plan)
from tests.aref.aref_witness import WitnessChannel
from tests.aref.fixtures import load_case

AREF_DIR = Path(__file__).resolve().parent
REPO_ROOT = AREF_DIR.parents[1]
STAGE_SCRIPT = AREF_DIR / "aref_live_stage_script.py"
DEFAULT_EVIDENCE = Path(os.environ.get("AREF_EVIDENCE_DIR",
                                       str(Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
                                           / "Temp" / "aref_evidence")))
LIVE_GATE_ENV = "ATLAS_RUN_LIVE_BLENDER"


def blender_executable() -> str:
    from tools.blender import BLENDER

    return BLENDER


class TransportFailure(LiveError):
    def __init__(self, detail: str) -> None:
        super().__init__("TRANSPORT-FAILURE", detail)


def _launch(mode: str, arg: str, timeout: int = 300) -> Tuple[int, Dict[str, Any], str]:
    """Launch ONE Blender stage process and parse its marker record (R4F 24 steps 11).

    Operator gate ENFORCED at the real launch site: a library caller without
    ATLAS_RUN_LIVE_BLENDER=1 cannot start a Blender stage (the pytest-level skip is not the only
    guard).
    """
    require_live_gate()
    command = [blender_executable(), "--background", "--factory-startup",
               "--python", str(STAGE_SCRIPT), "--", mode, arg]
    try:
        proc = subprocess.run(command, cwd=str(REPO_ROOT), capture_output=True, text=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise TransportFailure(f"stage {mode} timed out after {timeout}s") from exc
    begin, end = (PROBE_BEGIN, PROBE_END) if mode == "probe" else (EXEC_BEGIN, EXEC_END)
    try:
        record = parse_marker(proc.stdout, begin, end)
    except LiveError as exc:
        raise TransportFailure(f"stage {mode} produced no parseable evidence: {exc.detail}; "
                               f"exit={proc.returncode}; tail={proc.stderr[-400:]!r}") from exc
    return proc.returncode, record, proc.stdout


# ---------------------------------------------------------------------------------------------
# Step 2 — pure construction (controller/pure process; never derived from live state).
# ---------------------------------------------------------------------------------------------

def pure_record(fixture_id: str) -> Dict[str, Any]:
    spec = load_case(fixture_id)
    raw = load_plan_artifact(fixture_id)
    run = run_pure_case(spec, raw)
    return {"fixture_id": fixture_id, "scene_digest": run.scene_digest_pre,
            "report_digest": run.report_digest_pre, "plan_id": run.plan_identity.plan_id,
            "correction_ids": list(run.plan_identity.correction_ids),
            "artifact_sha256": plan_artifact_digest(raw), "run": run}


# ---------------------------------------------------------------------------------------------
# Step 6 — controller verification (STRICTLY BEFORE MUTATION). Any mismatch withholds the launch.
# ---------------------------------------------------------------------------------------------

class BindingMismatch(LiveError):
    def __init__(self, detail: str) -> None:
        super().__init__("FIXTURE-BINDING-MISMATCH", detail)


def verify_probe(fixture_id: str, probe_record: Dict[str, Any],
                 pure: Optional[Dict[str, Any]] = None,
                 tamper: str = "NONE") -> Dict[str, Any]:
    """Controller-side binding verification of the probe evidence against the declared literals."""
    if tamper == "TRUNCATED_EVIDENCE":
        probe_record = {"status": "PROBED"}  # malformed/incomplete: must be refused
    spec = load_case_live(fixture_id)
    declared = spec.expected
    declared_plan = declared["plan"]
    record = dict(probe_record)

    if record.get("status") != "PROBED" or record.get("stage") != "PROBE":
        raise BindingMismatch(f"probe did not complete: {record.get('status')!r} "
                              f"({record.get('category', 'n/a')})")

    if record.get("spec_digest") != fixture_spec_sha256(fixture_id):
        raise BindingMismatch("probe spec digest does not match the on-disk fixture specification")
    if record.get("expected_sha256") != canonical_digest(declared):
        raise BindingMismatch("probe expected-literal digest does not match the declared literals")

    construct = record.get("construct") or {}
    for key in ("objects", "shared", "order"):
        if construct.get(key) != declared["graph_witness"].get(key):
            raise BindingMismatch(f"EV-CONSTRUCT[{key}] != declared graph witness")
    if declared["graph_witness"].get("material_slots") is not None and \
            construct.get("material_slots") != declared["graph_witness"].get("material_slots"):
        raise BindingMismatch("EV-CONSTRUCT[material_slots] != declared graph witness")

    pre = record.get("pre") or {}
    if pre.get("live_scene_digest") != declared["pre_digest"]:
        raise BindingMismatch("EV-PRE live scene digest != declared pre_digest")
    if pre.get("live_report_digest") != declared_plan["source_report_digest"]:
        raise BindingMismatch("EV-PRE live report digest != declared source_report_digest")

    if pure is None:
        pure = pure_record(fixture_id)
    if pure["scene_digest"] != declared["pre_digest"]:
        raise BindingMismatch("pure pre-state digest != declared pre_digest")
    if pure["scene_digest"] != pre.get("live_scene_digest"):
        raise BindingMismatch("pure pre-state digest != live pre-state digest (direct comparison)")
    # M1 (implementation review): the PURE side's report digest and plan identity are bound too —
    # step 6 requires BOTH paths' pre-digests, not only the live one.
    if pure["report_digest"] != declared_plan["source_report_digest"]:
        raise BindingMismatch("pure pre-report digest != declared source_report_digest")
    if pure["report_digest"] != pre.get("live_report_digest"):
        raise BindingMismatch("pure pre-report digest != live pre-report digest (direct comparison)")
    if pure["plan_id"] != declared_plan["plan_id"]:
        raise BindingMismatch("pure plan identity != declared plan_id")

    plan = record.get("plan") or {}
    if tamper == "WRONG_ARTIFACT_SHA":
        plan = dict(plan, sha256="0" * 64)
    if tamper == "WRONG_PLAN_ID":
        plan = dict(plan, plan_id="0" * 64)
    if tamper == "WRONG_SOURCE_DIGEST":
        plan = dict(plan, source_report_digest="0" * 64)
    if plan.get("sha256") != declared_plan["artifact_sha256"]:
        raise BindingMismatch("EV-PLAN artifact sha256 != declared")
    raw_artifact = json.loads(plan["raw"])
    recomputed = plan_artifact_digest(raw_artifact)
    if recomputed != plan.get("sha256"):
        raise BindingMismatch("EV-PLAN artifact bytes do not hash to the reported sha256")
    identity = plan_identity(raw_to_plan(raw_artifact))
    if identity.plan_id != declared_plan["plan_id"] or plan.get("plan_id") != declared_plan["plan_id"]:
        raise BindingMismatch("EV-PLAN plan_id != declared")
    if identity.source_report_digest != declared_plan["source_report_digest"] or \
            plan.get("source_report_digest") != declared_plan["source_report_digest"]:
        raise BindingMismatch("EV-PLAN source_report_digest != declared")
    if list(identity.correction_ids) != list(declared_plan["correction_ids"]) or \
            list(plan.get("correction_ids", [])) != list(declared_plan["correction_ids"]):
        raise BindingMismatch("EV-PLAN correction ids != declared")

    return {"spec_digest_ok": True, "construct_ok": True, "graph_ok": True,
            "pre_digest_live_ok": True, "pre_digest_pure_ok": True, "pure_eq_live": True,
            "plan_identity_ok": True, "field_binding_present": bool(declared.get("pre_digest")),
            "pure": {"scene_digest": pure["scene_digest"], "report_digest": pure["report_digest"]},
            "live": {"scene_digest": pre.get("live_scene_digest"),
                     "report_digest": pre.get("live_report_digest")}}


# ---------------------------------------------------------------------------------------------
# Full case: probe -> verify -> (withhold | execute) -> aggregate -> compare.
# ---------------------------------------------------------------------------------------------

def run_live_case(fixture_id: str, *, tamper: str = "NONE", save_evidence: bool = True,
                  timeout: int = 300) -> Dict[str, Any]:
    pure = pure_record(fixture_id)
    spec = load_case_live(fixture_id)
    result: Dict[str, Any] = {"fixture_id": fixture_id, "case": spec.case,
                              "operation": spec.operation, "tamper": tamper,
                              "launches": [], "pure": {k: pure[k] for k in
                                                       ("scene_digest", "report_digest", "plan_id",
                                                        "correction_ids", "artifact_sha256")}}

    try:
        rc, probe_raw, _stdout = _launch("probe", fixture_id, timeout=timeout)
    except LiveError as exc:
        # transport/capture/storage failure of the PROBE: OC8-class evidence-infrastructure failure
        # (R4F 24 step 11) — environment-limited, never a semantic verdict and never parity.
        result["launches"].append({"stage": "probe", "exit": None, "status": "TRANSPORT-FAILURE"})
        result["controller_verification"] = None
        result["execution_launched"] = False
        result["outcome"] = {"status": "ERROR", "category": exc.category,
                             "detail": exc.detail, "disposition": "ENVIRONMENT_LIMITED",
                             "executor_invocations": 0}
        _save(fixture_id, result, save_evidence)
        return result
    result["launches"].append({"stage": "probe", "exit": rc, "status": probe_raw.get("status")})
    result["probe"] = probe_raw
    if probe_raw.get("status") != "PROBED":
        result["controller_verification"] = None
        result["execution_launched"] = False
        result["outcome"] = {"status": probe_raw.get("status"), "category": probe_raw.get("category"),
                             "disposition": "ENVIRONMENT_LIMITED" if probe_raw.get("category")
                             == "TRANSPORT-FAILURE" else "FIXTURE_REFUSAL"}
        _save(fixture_id, result, save_evidence)
        return result

    try:
        verification = verify_probe(fixture_id, probe_raw, pure, tamper=tamper)
    except LiveError as exc:
        result["controller_verification"] = {"status": "WITHHELD", "category": exc.category,
                                             "detail": exc.detail}
        result["execution_launched"] = False
        result["outcome"] = {"status": "WITHHELD", "category": exc.category,
                             "disposition": "POSITIVELY_DEMONSTRATED", "mutation": "none",
                             "executor_invocations": 0}
        _save(fixture_id, result, save_evidence)
        return result
    result["controller_verification"] = {"status": "VERIFIED", **verification}

    # write the verified plan artifact BYTES (both paths consume these same bytes; R4F 9.10(e))
    raw_text = result["probe"]["plan"]["raw"]
    plan_bytes = raw_text.encode("utf-8")
    case_dir = _case_dir(fixture_id)
    suffix = "" if tamper == "NONE" else f"_{tamper.lower()}"
    plan_path = case_dir / f"plan_artifact{suffix}.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_bytes(plan_bytes)
    plan_sha = sha256_hex(plan_bytes)

    if tamper == "WRONG_PARAMETER_IN_HANDOFF":
        tampered = json.loads(raw_text)
        correction = tampered["corrections"][0]
        params = dict(correction.get("parameters", {}))
        if "face_ids" in params:
            params["face_ids"] = [int(params["face_ids"][0]), int(params["face_ids"][0]) + 1]
        elif "face_id" in params:
            params["face_id"] = int(params["face_id"]) + 1
        else:
            params["mesh_id"] = str(params.get("mesh_id", "")) + "-tampered"
        correction["parameters"] = params
        correction["correction_id"] = ""   # re-commit the tampered body
        tampered["plan_id"] = ""           # ... and the plan over it, so the IDENTITY check fires
        plan_bytes = canonical_plan_bytes(tampered)
        plan_path.write_bytes(plan_bytes)
        plan_sha = sha256_hex(plan_bytes)

    probe_record_path = case_dir / f"probe_artifact{suffix}.json"
    write_json(probe_record_path, result["probe"])
    if tamper == "TAMPERED_PROBE_ARTIFACT":
        # execution-side negative: the FILE the execution launch depends on is altered AFTER the
        # controller verified it; the handoff keeps the verified digest, so the stage must refuse.
        stale = dict(result["probe"])
        stale["fixture_id"] = "AREF-TEST-FX-TAMPERED-STALE"
        write_json(probe_record_path, stale)
    handoff = build_handoff(
        fixture_id=fixture_id, case=spec.case, operation=spec.operation,
        spec_digest=fixture_spec_sha256(fixture_id), expected_sha256=canonical_digest(spec.expected),
        plan_sha256=plan_sha, plan_path=str(plan_path),
        declared_pre_digest=spec.expected["pre_digest"],
        declared_report_digest=spec.expected["plan"]["source_report_digest"],
        declared_plan_id=spec.expected["plan"]["plan_id"],
        declared_correction_ids=spec.expected["plan"]["correction_ids"],
        probe_artifact_sha256=result["probe"]["artifact_sha256"],
        probe_record_path=str(probe_record_path))
    handoff_path = case_dir / f"handoff{suffix}.json"
    write_json(handoff_path, handoff)
    result["handoff_sha256"] = canonical_digest(handoff)

    rc, exec_raw, _stdout = _launch("execute", str(handoff_path), timeout=timeout)
    result["launches"].append({"stage": "execution", "exit": rc, "status": exec_raw.get("status")})
    result["execution"] = exec_raw
    result["execution_launched"] = True

    if exec_raw.get("status") == "REFUSED":
        result["outcome"] = {"status": "REFUSED", "category": exec_raw.get("category"),
                             "disposition": "POSITIVELY_DEMONSTRATED",
                             "executor_invocations": int(exec_raw.get("invocation_count", 0))}
        _save(fixture_id, result, save_evidence)
        return result
    if exec_raw.get("status") != "EXECUTED":
        result["outcome"] = {"status": exec_raw.get("status"), "category": exec_raw.get("category"),
                             "disposition": "ENVIRONMENT_LIMITED"}
        _save(fixture_id, result, save_evidence)
        return result

    # ---- step 12: comparator (bindings + normal form + graph witness + child + witnesses) -----
    live_channel = WitnessChannel.from_trace(exec_raw.get("witness"))
    live_nf = outcome_normal_form(exec_raw["receipt"],
                                  invocation_count=int(exec_raw.get("invocation_count", 0)),
                                  witness=live_channel, side="live")
    live_evidence = {"normal_form": live_nf, "child_digest": exec_raw["child"]["scene_digest"],
                     "witness": exec_raw.get("witness")}
    comparison = compare_live(pure["run"], live_evidence, exec_raw,
                              probe_construct=result["probe"].get("construct"),
                              fixture_id=fixture_id)
    result["live_normal_form"] = live_nf
    result["comparison"] = {"verdict": comparison.verdict,
                            "dimensions": comparison.dimensions,
                            "notes": comparison.disposition_notes}
    result["outcome"] = {"status": "EXECUTED",
                         "result": exec_raw["receipt"].get("result"),
                         "failure_code": exec_raw["receipt"].get("failure_code"),
                         "oc_class": live_nf["oc_class"],
                         "invocation_count": int(exec_raw.get("invocation_count", 0)),
                         "child_digest": exec_raw["child"]["scene_digest"]}
    _save(fixture_id, result, save_evidence)
    return result


def pure_graph_witness(fixture_id: str) -> Dict[str, Any]:
    """The pure-side graph witness from the FIX literals (compared directly to the live one)."""
    from tests.aref.aref_harness import graph_witness
    from tests.aref.aref_pure import build_graph

    graph = build_graph(load_case(fixture_id))
    witness = graph_witness(graph)
    return {"objects": witness["objects"], "shared": witness["shared"],
            "material_slots": witness["material_slots"], "order": witness["order"]}


def compare_live(pure_run: Any, live_evidence: Dict[str, Any],
                 exec_raw: Dict[str, Any], probe_construct: Optional[Dict[str, Any]] = None,
                 fixture_id: Optional[str] = None) -> ComparisonResult:
    """Comparison per R4F 15.1/24 step 12: bindings passed (step 6), then the shared dimensions."""
    result = compare_normal_forms(
        pure_run.normal_form, live_evidence["normal_form"],
        pure_child_digest=pure_run.scene_digest_child,
        live_child_digest=live_evidence.get("child_digest"),
        pure_witness=pure_run.witness,
        live_witness=WitnessChannel.from_trace(live_evidence.get("witness")),
    )
    dims = dict(result.dimensions)
    # graph-witness equality (R4F 9.8): the PURE witness vs the LIVE pre-mutation witness — a real
    # comparison dimension (both sides are independently recorded; each is also bound to the
    # declared literal by the controller verification).
    if probe_construct is not None and fixture_id is not None:
        pure_witness = pure_graph_witness(fixture_id)
        live_witness = {key: probe_construct.get(key)
                        for key in ("objects", "shared", "material_slots", "order")}
        dims["graph_witness_pure_eq_live"] = pure_witness == live_witness
    dims["child_graph_unchanged"] = bool(exec_raw.get("child", {}).get("graph_unchanged"))
    notes = list(result.disposition_notes)
    if dims.get("graph_witness_pure_eq_live") is not True or dims["child_graph_unchanged"] is not True:
        notes.append("graph-witness/construction dimension not fully established")
    verdict = result.verdict if all(dims.values()) else "DIVERGENCE"
    return ComparisonResult(dimensions=dims, verdict=verdict, disposition_notes=notes)


def _case_dir(fixture_id: str) -> Path:
    directory = DEFAULT_EVIDENCE / "live" / fixture_id
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _save(fixture_id: str, payload: Dict[str, Any], enabled: bool) -> None:
    """Write this RUN's evidence under tamper-distinct names (no cross-run overwriting)."""
    if not enabled:
        return
    suffix = "" if payload.get("tamper", "NONE") == "NONE" else f"_{payload['tamper'].lower()}"
    stripped = dict(payload)
    stripped.pop("pure", None)
    write_json(_case_dir(fixture_id) / f"case{suffix}.json",
               {k: v for k, v in stripped.items() if k != "probe"})
    write_json(_case_dir(fixture_id) / f"probe_record{suffix}.json", payload.get("probe", {}))
    if payload.get("execution"):
        write_json(_case_dir(fixture_id) / f"execution_record{suffix}.json", payload["execution"])


def live_gate_enabled() -> bool:
    return os.environ.get(LIVE_GATE_ENV, "") == "1"


def require_live_gate() -> None:
    if not live_gate_enabled():
        raise RuntimeError(f"{LIVE_GATE_ENV}=1 is required to launch live Blender stages")
