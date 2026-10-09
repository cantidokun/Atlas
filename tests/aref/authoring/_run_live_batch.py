"""Run the two-phase live driver over registered cases; print a compact status table."""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from tests.aref.aref_live_driver import run_live_case  # noqa: E402
from tests.aref.fixtures import SPECS  # noqa: E402

CASE_ORDER = [
    "AREF-TEST-FX-C1-PAIR", "AREF-TEST-FX-C1-ROTATED", "AREF-TEST-FX-C1-REVERSED",
    "AREF-TEST-FX-C1-TRIPLE-S2", "AREF-TEST-FX-C1-TRIPLE-S3", "AREF-TEST-FX-C1-TRIPLE-AMB",
    "AREF-TEST-FX-C1-PRECOND", "AREF-TEST-FX-C2-DEGEN", "AREF-TEST-FX-C3-POS",
    "AREF-TEST-FX-C3-AUTHREQ", "AREF-TEST-FX-MM-C1", "AREF-TEST-FX-AL-C1",
    "AREF-TEST-FX-AL-C1-R",
]


def main() -> int:
    wanted = sys.argv[1:] or CASE_ORDER
    failures = 0
    for fixture_id in wanted:
        if fixture_id not in SPECS:
            print(f"{fixture_id}: NOT-REGISTERED")
            failures += 1
            continue
        try:
            result = run_live_case(fixture_id)
        except Exception as exc:  # noqa: BLE001 - report and continue
            print(f"{fixture_id}: DRIVER-ERROR {type(exc).__name__}: {exc}")
            failures += 1
            continue
        launches = "+".join(f"{l['stage']}:{l['status']}({l['exit']})" for l in result["launches"])
        outcome = result.get("outcome") or {}
        comparison = result.get("comparison") or {}
        verification = result.get("controller_verification") or {}
        print(json.dumps({
            "fixture": fixture_id,
            "launches": launches,
            "verification": verification.get("status"),
            "execution_launched": result.get("execution_launched"),
            "outcome": outcome.get("status"),
            "result": outcome.get("result"),
            "oc": outcome.get("oc_class"),
            "invocations": outcome.get("invocation_count"),
            "verdict": comparison.get("verdict"),
            "notes": comparison.get("notes"),
        }, sort_keys=True))
    print(f"BATCH-DONE failures={failures}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
