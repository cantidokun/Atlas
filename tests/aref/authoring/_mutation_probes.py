"""Adversarial mutation probes: remove a required check -> the suite must fail; restore -> pass.

Each probe records the target file's sha256 BEFORE mutation and re-verifies it AFTER restoration;
a restore that is not byte-identical aborts the probe run instead of silently shipping a mutation.
"""
import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
#: interpreter: the one running this script (override with AREF_PYTHON)
PY = os.environ.get("AREF_PYTHON", sys.executable)
#: evidence output directory (override with AREF_EVIDENCE_DIR); never inside the repo
EVIDENCE_DIR = Path(os.environ.get(
    "AREF_EVIDENCE_DIR",
    str(Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Temp" / "aref_evidence")))
OUT = []


def run_pytest(*args):
    proc = subprocess.run([PY, "-m", "pytest", *args, "-q", "-p", "no:cacheprovider"],
                          cwd=ROOT, capture_output=True, text=True)
    return proc.returncode, (proc.stdout + proc.stderr).strip().splitlines()[-1]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def probe(name, path, old, new, target):
    p = Path(ROOT) / path
    original_bytes = p.read_bytes()
    original = p.read_text(encoding="utf-8")   # NEWLINE-NORMALIZED text for anchor matching
    assert original.count(old) == 1, f"{name}: anchor not found"
    try:
        p.write_text(original.replace(old, new), encoding="utf-8")
        code, line = run_pytest(*target)
        OUT.append(f"{name}: exit={code} | {line} | file_sha256(mutated)={_sha(p.read_bytes())}")
    finally:
        p.write_bytes(original_bytes)                      # exact byte restoration
    restored = p.read_bytes()
    if restored != original_bytes:
        raise SystemExit(f"{name}: RESTORATION IS NOT BYTE-IDENTICAL — aborting probe run")
    code, line = run_pytest(*target)
    OUT.append(f"{name} (restored): exit={code} | {line} | "
               f"byte_identical_restore=TRUE sha256={_sha(restored)}")


probe("probe1: drop the pre-digest binding check",
      "tests/aref/aref_harness.py",
      '    if scene_digest != spec.expected["pre_digest"]:',
      '    if False:',
      ["tests/aref/test_aref_harness.py::test_tampered_pre_digest_fails_closed_without_mutation"])

probe("probe2: drop the marker refusal for authorized_by",
      "tests/aref/aref_fixture.py",
      '''    _require_exact(ab.startswith(MARKER),
                   f"authorization_fixture.authorized_by: must carry the {MARKER} marker (harness refusal rule, R4F 8.2)")''',
      '''    pass''',
      ["tests/aref/test_aref_fixtures.py::test_authorized_by_marker_required_when_auth_declared"])

probe("probe3: allow the marker on the hex-constrained plan_id",
      "tests/aref/aref_fixture.py",
      '''    _require_exact(not v.startswith(MARKER), f"{label}: the {MARKER} marker must not be prefixed to a format-constrained field")''',
      '''    pass''',
      ["tests/aref/test_aref_fixtures.py::test_plan_id_marker_forbidden_and_hex_required"])

probe("probe4: skip the OC1 zero-invocation invariant",
      "tests/aref/aref_evidence.py",
      '''    if result in OC1_RESULTS:
        if invocation_count != 0:
            raise EvidenceError(f"pre-mutation refusal {result!r} after an invocation is inconsistent evidence")''',
      '''    if result in OC1_RESULTS:
        pass''',
      ["tests/aref/test_aref_harness.py::test_oc1_requires_zero_invocations"])

probe("probe5: bypass the controller withholding early-return",
      "tests/aref/aref_live_driver.py",
      """                             "disposition": "POSITIVELY_DEMONSTRATED", "mutation": "none",
                             "executor_invocations": 0}
        _save(fixture_id, result, save_evidence)
        return result""",
      """                             "disposition": "POSITIVELY_DEMONSTRATED", "mutation": "none",
                             "executor_invocations": 0}
        _save(fixture_id, result, save_evidence)""",
      ["tests/aref/test_aref_live_driver.py::test_failed_verification_withholds_the_execution_launch"])

probe("probe6: drop the pure-side report-digest binding check",
      "tests/aref/aref_live_driver.py",
      """    if pure["report_digest"] != declared_plan["source_report_digest"]:
        raise BindingMismatch("pure pre-report digest != declared source_report_digest")""",
      """    if False:
        raise BindingMismatch("pure pre-report digest != declared source_report_digest")""",
      ["tests/aref/test_aref_live_driver.py::test_controller_verification_withholds_on_wrong_pure_report_digest"])

probe("probe7: force the graph-witness pure-vs-live dimension to true",
      "tests/aref/aref_live_driver.py",
      """    if probe_construct is not None and fixture_id is not None:
        pure_witness = pure_graph_witness(fixture_id)
        live_witness = {key: probe_construct.get(key)
                        for key in ("objects", "shared", "material_slots", "order")}
        dims["graph_witness_pure_eq_live"] = pure_witness == live_witness""",
      """    if probe_construct is not None and fixture_id is not None:
        pure_witness = pure_graph_witness(fixture_id)
        live_witness = {key: probe_construct.get(key)
                        for key in ("objects", "shared", "material_slots", "order")}
        _ = (pure_witness, live_witness)
        dims["graph_witness_pure_eq_live"] = True""",
      ["tests/aref/test_aref_live_driver.py::test_graph_witness_pure_eq_live_is_a_real_dimension"])

probe("probe8: disable the execution-side probe-artifact verification call",
      "tests/aref/aref_live_execute.py",
      """    verify_probe_record_file(handoff["probe_record_path"], handoff["probe_artifact_sha256"],
                             fixture_id)""",
      """    pass  # probe-disabled: the execution-side probe-artifact check is bypassed""",
      ["tests/aref/test_aref_live_driver.py::test_execution_stage_verifies_the_probe_artifact_before_the_executor"])

text = "MUTATION PROBES (implementation evidence; each probe disables one required check, must fail, then restores)\n"
text += "\n".join(OUT) + "\n"
(EVIDENCE_DIR / "mutation_probes.txt").write_text(text, encoding="utf-8")
print(text)
