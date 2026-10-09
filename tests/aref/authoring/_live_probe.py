"""LIVE mutation probe for the dynamic execution-side negative (hardening review M2).

The headless probe (authoring/_mutation_probes.py, probe 8) shows the static call-site test is
load-bearing. This probe shows the DYNAMIC safeguard is load-bearing too: with the execution-side
probe-artifact verification disabled, the live negative TAMPERED_PROBE_ARTIFACT (whose execution
launch must REFUSE) actually executes the executor and the gate test fails; after a byte-identical
restore it passes again.

The mutated run writes its evidence to a SCRATCH evidence directory (AREF_EVIDENCE_DIR), so the
delivered evidence tree is never overwritten.

Usage:  <venv python> -m tests.aref.authoring._live_probe      (from the repository root)
Requires: ATLAS_RUN_LIVE_BLENDER=1 is set by this script for the two live test runs.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = os.environ.get("AREF_PYTHON", sys.executable)
EVIDENCE = Path(os.environ.get(
    "AREF_EVIDENCE_DIR",
    str(Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Temp" / "aref_evidence")))
SCRATCH = EVIDENCE / "live_probe_scratch"
TARGET = ROOT / "tests" / "aref" / "aref_live_execute.py"
ANCHOR = '''    verify_probe_record_file(handoff["probe_record_path"], handoff["probe_artifact_sha256"],
                             fixture_id)'''
MUTATION = '''    pass  # live-probe-disabled: the execution-side probe-artifact check is bypassed'''
TARGET_TEST = ("tests/aref/test_aref_live_conformance.py::"
               "test_execution_launch_refuses_before_mutation[AREF-TEST-FX-C1-PAIR-TAMPERED_PROBE_ARTIFACT]")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run_live_test(label: str) -> tuple:
    """Run the live negative with its OWN scratch evidence dir (both runs stay inspectable)."""
    scratch = SCRATCH / label
    env = dict(os.environ, ATLAS_RUN_LIVE_BLENDER="1", AREF_EVIDENCE_DIR=str(scratch))
    proc = subprocess.run([PY, "-m", "pytest", TARGET_TEST, "-q", "-p", "no:cacheprovider"],
                          cwd=str(ROOT), capture_output=True, text=True, env=env, timeout=600)
    last = (proc.stdout + proc.stderr).strip().splitlines()[-1] if (proc.stdout or proc.stderr) else ""
    outcome = "n/a"
    case = scratch / "live" / "AREF-TEST-FX-C1-PAIR" / "case_tampered_probe_artifact.json"
    if case.exists():
        try:
            payload = json.loads(case.read_text(encoding="utf-8"))
            outcome = json.dumps(payload.get("outcome"), sort_keys=True)
        except Exception as exc:  # noqa: BLE001
            outcome = f"unreadable: {exc}"
    return proc.returncode, last, outcome


def main() -> int:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    original_bytes = TARGET.read_bytes()
    original = TARGET.read_text(encoding="utf-8")   # newline-normalized anchor matching
    if original.count(ANCHOR) != 1:
        print(f"live-probe: anchor not found exactly once in {TARGET}")
        return 2
    lines = []
    try:
        TARGET.write_text(original.replace(ANCHOR, MUTATION), encoding="utf-8")
        code, last, outcome = _run_live_test("mutated")
        lines.append(f"live-probe (execution-side check DISABLED): exit={code} | {last} | "
                     f"file_sha256(mutated)={_sha(TARGET.read_bytes())} | "
                     f"tampered-case outcome under mutation: {outcome}")
    finally:
        TARGET.write_bytes(original_bytes)          # exact byte restoration
    if TARGET.read_bytes() != original_bytes:
        print("live-probe: RESTORATION IS NOT BYTE-IDENTICAL — aborting")
        return 3
    code, last, outcome = _run_live_test("restored")
    lines.append(f"live-probe (restored): exit={code} | {last} | byte_identical_restore=TRUE "
                 f"sha256={_sha(TARGET.read_bytes())} | tampered-case outcome restored: {outcome}")
    text = ("LIVE MUTATION PROBE (dynamic execution-side negative; the mutated run must FAIL and\n"
            "the restored run must PASS; evidence written to a scratch directory only)\n"
            + "\n".join(lines) + "\n")
    (EVIDENCE / "mutation_probes_live.txt").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
