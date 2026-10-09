"""A-REF live stage scripts (Blender entry points; R4F 24 steps 11).

Usage (operator-gated; the controller builds this command):

  blender --background --factory-startup --python <script> -- probe <fixture_id>
  blender --background --factory-startup --python <script> -- execute <handoff_path>

Each script emits exactly ONE marker-delimited JSON evidence record and exits with a category
code: 0 = stage complete, 2 = probe refusal, 3 = execution refusal (pre-mutation), 4 = transport
or internal failure. The controller classifies on the marker record; a missing marker is a
transport failure (OC8), never parity.
"""

from __future__ import annotations

import json
import os
import sys
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from tests.aref.aref_live_common import (EXEC_BEGIN, EXEC_END, PROBE_BEGIN, PROBE_END,  # noqa: E402
                                         LiveError, emit_marker)


def _args() -> list:
    argv = sys.argv
    if "--" not in argv:
        return []
    return argv[argv.index("--") + 1:]


def main() -> int:
    args = _args()
    if not args:
        print("usage: <script> -- probe <fixture_id> | execute <handoff_path>")
        return 4
    mode = args[0]
    try:
        if mode == "probe":
            from tests.aref.aref_live_probe import probe

            record = probe(args[1])
            emit_marker(PROBE_BEGIN, PROBE_END, record)
            return 0
        if mode == "alias-attempt":
            from tests.aref.aref_live_alias_attempt import run_attempt

            emit_marker(PROBE_BEGIN, PROBE_END, run_attempt())
            return 0
        if mode == "execute":
            from tests.aref.aref_live_execute import execute_stage

            record = execute_stage(args[1])
            emit_marker(EXEC_BEGIN, EXEC_END, record)
            return 0
        print(f"unknown mode {mode!r}")  # probe | execute | alias-attempt
        return 4
    except LiveError as exc:
        refusal = {"status": "REFUSED", "stage": "PROBE" if mode == "probe" else "EXECUTION",
                   "category": exc.category, "detail": exc.detail, "invocation_count": 0}
        if mode == "probe":
            emit_marker(PROBE_BEGIN, PROBE_END, refusal)
            return 2
        emit_marker(EXEC_BEGIN, EXEC_END, refusal)
        return 3
    except BaseException as exc:  # noqa: BLE001 - transport/internal failure is evidence too
        failure = {"status": "ERROR", "stage": "PROBE" if mode == "probe" else "EXECUTION",
                   "category": "TRANSPORT-FAILURE",
                   "detail": f"{type(exc).__name__}: {exc}",
                   "traceback_tail": traceback.format_exc()[-2000:],
                   "invocation_count": 0}
        if mode == "probe":
            emit_marker(PROBE_BEGIN, PROBE_END, failure)
        else:
            emit_marker(EXEC_BEGIN, EXEC_END, failure)
        return 4


if __name__ == "__main__":
    sys.exit(main())
