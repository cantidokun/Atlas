"""M11.4 operator-invoked live-validation command line.

CONTROLLED / GATED: this tool performs REAL provider calls ONLY when explicitly
invoked by an operator with:
  - ``--live`` (enables the M11 gate), and
  - secure credentials present in the environment (ATLAS_M11_OPENROUTER_API_KEY /
    ATLAS_M11_*_API_KEY) or a resolver env file.

It NEVER runs in the deterministic default suite. It performs ONE request per
task, never retries, records safe telemetry, and never persists credentials.

Usage (operator):
  python -m planning.m11_router.live_operator --live --smoke
  python -m planning.m11_router.live_operator --live --benchmark --out report.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

from planning.m11_router.live_validation import run_live_smoke
from planning.m11_router.router import ModelRouter
from planning.m11_router.model_profile import load_profiles
from planning.m11_router.benchmark import run_benchmark_corpus


def _router() -> ModelRouter:
    profiles = load_profiles([
        {"tier": "L0", "provider": "cfg0", "model": "cfg-lite", "capability_floor": "L0",
         "supported_task_classes": ["docs", "test"], "token_budget": 2000, "timeout_s": 30},
        {"tier": "L1", "provider": "cfg1", "model": "cfg-eng", "capability_floor": "L1",
         "supported_task_classes": ["docs", "test", "refactor", "adapter", "api-boundary"],
         "token_budget": 8000, "timeout_s": 60},
        {"tier": "L2", "provider": "cfg2", "model": "cfg-strong", "capability_floor": "L2",
         "supported_task_classes": ["docs", "test", "refactor", "api-boundary", "recovery",
                                    "concurrency", "contract"],
         "token_budget": 20000, "timeout_s": 180},
        {"tier": "L3", "provider": "cfg3", "model": "cfg-frontier", "capability_floor": "L3",
         "supported_task_classes": ["security-crypto", "recovery", "contract"],
         "token_budget": 60000, "timeout_s": 600},
    ])
    return ModelRouter(profiles)


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(prog="m11-live", description="M11.4 controlled live validation")
    ap.add_argument("--live", action="store_true",
                    help="enable the M11 live gate (operator-invoked; required for real calls)")
    ap.add_argument("--smoke", action="store_true", help="run one trivial docs smoke task")
    ap.add_argument("--benchmark", action="store_true", help="run the full corpus through live provider")
    ap.add_argument("--out", default=None, help="write machine-readable benchmark report to this JSON path")
    args = ap.parse_args(argv)

    if not args.live:
        print("M11 live gate is OFF. Pass --live to enable real provider calls (operator-invoked).")
        print("Default offline path: nothing sent to any provider.")
        return 0
    if not (args.smoke or args.benchmark):
        ap.error("choose --smoke or --benchmark")
    if not os.environ.get("ATLAS_M11_ROUTING_ENABLED"):
        # operator may set it; also accept --live as the explicit gate.
        os.environ["ATLAS_M11_ROUTING_ENABLED"] = "1"
    if not os.environ.get("ATLAS_M11_OPENROUTER_API_KEY"):
        print("WARN: ATLAS_M11_OPENROUTER_API_KEY not set; the adapter will fail closed (AUTH_ERROR).")
        print("This is safe (no silent fallback) but real calls cannot succeed.")

    if args.smoke:
        env = dict(os.environ)
        res = run_live_smoke(gated_enabled=True, resolver_env=env)
        print(json.dumps(res.to_dict(), indent=2, default=str))
        return 0 if res.request_status == "success" else 1

    if args.benchmark:
        router = _router()
        from planning.m11_router.live_validation import ControlledLiveValidator
        from planning.m11_router.provider.openrouter_adapter import OpenRouterAdapter
        from planning.m11_router.provider.providers_config import ProviderConfig, ModelTier
        from planning.m11_router.provider.secure_config import SecureConfigResolver
        env = dict(os.environ)
        cfg = ProviderConfig(
            provider="openrouter", model=env.get("ATLAS_M11_LIVE_MODEL") or "deepseek-v4-flash",
            capability_tier=ModelTier.L1,
            supported_task_classes=frozenset({"docs", "test", "refactor", "api-boundary",
                                               "recovery", "security-crypto", "contract"}),
            token_budget=8000, timeout_s=120,
            endpoint_config_ref=env.get("ATLAS_M11_ROUTING_ENDPOINT_REF") or "openrouter",
            pricing=None,
        )
        adapter = OpenRouterAdapter(SecureConfigResolver(env=env),
                                    base_url=env.get("ATLAS_M11_ROUTING_ENDPOINT"))
        validator = ControlledLiveValidator(router, [cfg], adapter=adapter)
        report = run_benchmark_corpus(router, validator=validator, live=True)
        text = json.dumps(report, indent=2, default=str)
        print(text)
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
            print(f"\nreport written to {args.out}")
        # honest: non-zero exit if any provider errors
        if report["summary"]["provider_errors"]:
            return 1
        return 0
    return 0


def run_offline_baseline_report() -> dict:
    """Produce a machine-readable baseline report WITHOUT any live call.

    This is the offline (provider-independent) baseline: routing decisions only,
    no invocation. It is safe for CI/automation and answers which tiers the
    router picks per task class, with honest UNKNOWN token/cost values.

    NOTE: 'path A = existing Hermes path' is the authoritative Hermes execution
    the operator compares against externally; this report is the 'B = M11
    selected-model path' machine-readable output for that comparison.
    """
    from planning.m11_router.benchmark import run_benchmark_corpus
    return run_benchmark_corpus(_router(), live=False)


def run_live_baseline_report() -> dict:
    """Operator-invoked live benchmark (requires credentials). Returns the
    machine-readable report; never persists credentials."""
    import os
    from planning.m11_router.live_validation import ControlledLiveValidator
    from planning.m11_router.provider.openrouter_adapter import OpenRouterAdapter
    from planning.m11_router.provider.secure_config import SecureConfigResolver
    router = _router()
    env = dict(os.environ)
    cfg = None
    # provider config (names are deployment config params)
    from planning.m11_router.provider.providers_config import ProviderConfig, ModelTier
    cfg = ProviderConfig(
        provider="openrouter",
        model=env.get("ATLAS_M11_LIVE_MODEL") or "deepseek-v4-flash",
        capability_tier=ModelTier.L1,
        supported_task_classes=frozenset({"docs", "test", "refactor", "api-boundary",
                                           "recovery", "security-crypto", "contract",
                                           "concurrency", "adapter"}),
        token_budget=int(env.get("ATLAS_M11_LIVE_TOKEN_BUDGET", "20000")),
        timeout_s=int(env.get("ATLAS_M11_LIVE_TIMEOUT_S", "120")),
        endpoint_config_ref=env.get("ATLAS_M11_ROUTING_ENDPOINT_REF") or "openrouter",
        pricing=None,
    )
    adapter = OpenRouterAdapter(SecureConfigResolver(env=env),
                                base_url=env.get("ATLAS_M11_ROUTING_ENDPOINT"))
    validator = ControlledLiveValidator(router, [cfg], adapter=adapter)
    return run_benchmark_corpus(router, validator=validator, live=True)


if __name__ == "__main__":
    sys.exit(main())