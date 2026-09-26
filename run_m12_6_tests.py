#!/usr/bin/env python3
"""Deterministic test runner for the M12.6 R2-A suite under the pinned CPython 3.11.16 runtime.

pytest is not installed for the interpreter the contract pins (XI.3 records CPython 3.11.16 and the integer
digit limit), so this runner imports the test module and executes every ``test_*`` callable in definition order,
reporting one line per test and a PASS/FAIL summary. It runs the same functions pytest would collect.

Usage: python run_m12_6_tests.py [module ...]      (default: tests.m12.test_m12_6_r2a_refusal)
"""

from __future__ import annotations

import importlib
import sys
import traceback

DEFAULT_MODULES = ("tests.m12.test_m12_6_r2a_refusal", "tests.m12.test_m12_6_r2a_remediation")


def run(module_names) -> int:
    passed, failed = 0, []
    for module_name in module_names:
        module = importlib.import_module(module_name)
        names = [n for n in dir(module) if n.startswith("test_")]
        names.sort(key=lambda n: getattr(module, n).__code__.co_firstlineno)
        for name in names:
            func = getattr(module, name)
            if not callable(func):
                continue
            try:
                func()
            except Exception:
                failed.append((module_name, name, traceback.format_exc()))
                print(f"FAIL  {module_name}::{name}")
            else:
                passed += 1
                print(f"PASS  {module_name}::{name}")
    print()
    for module_name, name, tb in failed:
        print(f"===== {module_name}::{name} =====")
        print(tb)
    print(f"RESULT: {passed} PASS / {len(failed)} FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:] or DEFAULT_MODULES))
