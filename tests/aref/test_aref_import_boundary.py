"""A-REF import-boundary validation (R4F 22(a) static, 22(b) runtime import-graph)."""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLANNING = REPO / "planning"


def test_static_no_production_module_references_aref():
    """22(a): no module under planning/ may import or reference any A-REF conformance module."""
    hits = []
    for path in sorted(PLANNING.rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for token in ("tests.aref", "tests/aref", "aref_fixture", "aref_pure", "aref_plan",
                      "aref_harness", "aref_evidence", "aref_witness"):
            if token in text:
                hits.append(f"{path.relative_to(REPO)}: {token}")
    # packaging/entry-point declarations must not reference one either
    for name in ("pyproject.toml", "setup.cfg", "setup.py"):
        f = REPO / name
        if f.exists():
            text = f.read_text(encoding="utf-8", errors="replace")
            if "aref" in text or "tests.aref" in text:
                hits.append(f"{name}: aref reference")
    assert hits == [], hits


def test_runtime_production_entry_surface_does_not_load_aref(tmp_path):
    """22(b): import the headless production entry surface in a FRESH interpreter; no A-REF module
    may appear in sys.modules afterwards. (The bridge runtime is excluded: it imports bpy at module
    level and needs the live environment — the headless entry surface is the set A-REF itself uses.)"""
    script = tmp_path / "probe.py"
    script.write_text(
        "import sys\n"
        "import planning.blender.correction_executor\n"
        "import planning.blender.correction_planner\n"
        "import planning.blender.correction_contract\n"
        "import planning.blender.correction_values\n"
        "import planning.blender.kernel\n"
        "import planning.blender.extraction_payload\n"
        "import planning.blender.correction_authorization\n"
        "bad = sorted(m for m in sys.modules if m.startswith('tests.aref') or m.startswith('aref_'))\n"
        "print('AREF_MODULES=' + repr(bad))\n"
        "print('COUNT=' + str(len(sys.modules)))\n",
        encoding="utf-8")
    import os

    env = dict(os.environ, PYTHONPATH=str(REPO))
    proc = subprocess.run([sys.executable, str(script)], cwd=str(REPO), env=env,
                          capture_output=True, text=True, timeout=180)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    line = [l for l in proc.stdout.splitlines() if l.startswith("AREF_MODULES=")][0]
    assert line == "AREF_MODULES=[]", line
    assert "COUNT=" in proc.stdout
