# M10 Remediation — Defect C (adapter argument boundary)

## Live status
- **Defect A: PASS live** (reconcile_read travels the READ/inspect path).
- **Defect B: PASS live** (catalog preserves journal-derived M8 attestation fields).
- **Defect C: BLOCKED reconciliation** — now fixed in production, deterministic-tested.
  Reconciliation was blocked because the coordinator's reconcile request lacked the
  nested `arguments.entity_ids` the C++ engine requires.
- **S1 must be rerun after merge before S2–S8.** No further live scenario was run
  during this remediation.

## Defect C root cause

### Exact data path traced
```
UnrealRenderRecoveryCoordinator._query_catalog
  -> UnrealOperation(name="reconcile_render_jobs", kind=READ,
                     arguments={"job_ids":[atlas_job_id]},
                     entity_ids=("RENDER_RECOVERY",))
  -> UnrealAdapterProduction.inspect   (READ-only path)
  -> _build_request: arguments=dict(operation.arguments)   # verbatim, NO nested entity_ids
                    entity_ids=tuple(operation.entity_ids)  # only at top level
  -> UnrealTransportRequest  -> named pipe
  -> C++ ValidateRequest (generic): requires arguments.entity_ids (string array)
     to MATCH Request.EntityIds for EVERY operation.
  -> FALSE: "arguments.entity_ids must be an array of strings (ERR_MISSING_ARGUMENT)"
  -> coordinator catalog processing: exception -> None -> Case J / RECOVERY_PENDING.
```

### Expected vs actual operation shape
- Expected (C++ contract): top-level `entity_ids` AND `arguments.entity_ids` (nested
  array) both present and equal.
- Actual (coordinator via `_build_request`): `arguments` was a verbatim copy of
  `operation.arguments`; `entity_ids` existed only at the top level — the nested
  `arguments.entity_ids` was ABSENT.

### Field names/types
- `arguments.entity_ids`: required array of strings, equal to `entity_ids`.
- `entity_ids`: tuple of strings at the transport request top level.
- Coordinator supplied `arguments={"job_ids": [str]}` (no `arguments.entity_ids`).

### Where the mismatch is introduced
`UnrealAdapterProduction._build_request` — it copied `operation.arguments` verbatim
into the transport `arguments` and did NOT relay the operation's `entity_ids` into
the nested `arguments.entity_ids`. This is a transport-boundary (adapter) gap, not
a coordinator logic error: the coordinator correctly declared `entity_ids` at the
operation level; the adapter failed to materialize them where the engine expects.

### Why deterministic tests did not catch it
The coordinator/M6/M7/M8/M9 tests used `MagicMock`/`ScriptedCoordinatorAdapter`
adapters that do NOT enforce the C++ `arguments.entity_ids` validation. They
accepted any `operation.arguments` and returned a canned catalog, so the missing
nested `entity_ids` never surfaced. Only the real UE engine (live run) enforced it.

## Fix (production, adapter transport boundary only)

`UnrealAdapterProduction._build_request` now:
- relays the operation's `entity_ids` into `arguments["entity_ids"]` (nested array)
  when absent — no value synthesis, ids come verbatim from the operation;
- if `arguments` already contains `entity_ids`, requires it to MATCH the operation-
  level ids and FAILS CLOSED on conflict (no silent override).

This is generic (covers reconcile_render_jobs AND every other operation), keeps
`reconcile_render_jobs` READ-only through `adapter.inspect`, does not make the
coordinator know transport details, adds no special-case bypass, and preserves
authorization/correlation/schema validation. No C++ change was needed.

## Regression coverage (tests/m10/test_m10_defect_c_argument_shape.py, 7)

Derived from the ACTUAL live failure (an EngineLikeTransport enforces the C++
`arguments.entity_ids` contract):
1. exact live-shaped reconcile request accepted (nested entity_ids injected);
2. wrong shape (no nested entity_ids) rejected by the engine-like validator;
3. coordinator still constructs a READ `reconcile_render_jobs` op;
4. inspect() receives nested arguments.entity_ids == operation entity_ids;
5. WRITE ops also carry nested entity_ids and still require authorization;
6. correlation/schema checks still active (wrong request_id rejected);
7. malformed/unreadable catalog responses still fail closed (Case J, no receipt).

Also corrected one existing adapter test fixture that had a pre-existing
inconsistent arguments.entity_ids (it would have been rejected by the engine too).

## UBT result

NOT REQUIRED — the fix is entirely in Python (`planning/unreal_adapter_production.py`
+ tests). No C++ production code changed. (If a C++ change had been needed, UBT
would have been run on the final tree.)

## Regression

- tests/m10: 24 (17 prior + 7 Defect C)
- tests/m6 79, m7 59, m8 19, m9 34, adapter 25, submission green
- full `pytest -m "not integration"`: 1165 passed

## Explicit statements
- NO live Unreal scenario executed during this remediation.
- NO UnrealEditor launch; NO Blender; NO workflow/action-runner tests.
- S1 must be rerun after merge (to confirm full Case B → FINALIZED → exactly one
  receipt) before S2–S8, which remain NOT EXECUTED.
- Successful S1 render/journal/artifacts + Defect C forensic evidence preserved
  (live_run_state/s1_verify/, live_run_state/s1_rerun/, live_run_state/); not
  overwritten.