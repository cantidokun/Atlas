# Atlas Unreal Agent — Current Development Handoff

**Updated:** August 22, 2026 — actor-rotation semantic verification
**Current focus:** Controlled actor transform expansion — rotation proof boundary
**Current branch:** `feat/unreal-rotation-semantic-verification`
**Current state:** actor-rotation planning, tool-schema validation, transport execution, and post-write semantic verification are implemented in the development branch.

## Latest completed milestone

PR #33 (`Fix planning runtime proposal revalidation`) is merged into `feat/unreal-production-actor-write`. Issue #32 is closed. The local planning-runtime regression gate is green:

```text
Planning runtime boundary suite: 13 passed
Qwen planning runtime suite:     5 passed
Total:                           18 passed
```

The fix preserves the provider-neutral trust boundary by revalidating provider-built proposals before authorization.

## Current rotation boundary

Actor rotation now has the complete deterministic planning shape:

```text
READ inspect_target_actors
WRITE set_actor_rotation
VERIFY verify_target_actor_mapping
```

The Python Unreal tool schema strictly admits:

```text
entity_ids
authorization_id
rotation:
  pitch
  yaw
  roll
```

The new semantic verification boundary proves that the fresh Unreal observation actually matches the requested rotation rather than merely accepting a successful transport response.

`planning/unreal_state_verifier.py` now exposes:

```python
verify_actor_rotation(evidence, expected_rotation)
```

`UnrealPlanExecutor` applies that verifier immediately after every actor-rotation write/verify pair.

Focused regression coverage was added for:

- matching rotation with tolerance;
- per-axis rotation mismatch;
- missing rotation evidence;
- malformed expected rotation shape;
- executor success only when post-write rotation matches;
- executor failure when Unreal reports a different post-write rotation.

## Immediate verification gate

Run the focused Python gate first:

```powershell
python -m pytest tests/test_unreal_state_verifier_rotation.py tests/test_unreal_rotation_executor_verification.py -q
```

Then run the existing actor-rotation boundary tests:

```powershell
python -m pytest tests/test_unreal_actor_rotation_tool_schema.py tests/test_unreal_actor_rotation_execution.py -q
```

If those are green, the remaining proof gate is the real Unreal integration:

```powershell
python -m pytest tests/test_unreal_actor_rotation_real_integration.py -vv -s
```

The real integration test mutates `FIELD_SURFACE`, verifies the requested rotation through fresh Unreal evidence, and restores the original rotation in `finally`.

## Architectural invariants

- Atlas owns the Twin.
- Unreal Agent reasons/plans.
- Atlas authorizes.
- Unreal adapter executes.
- Unreal provides evidence.
- Atlas verifies semantic state independently.
- Failures require fresh evidence and explicit recovery.
- Replacement mutations require explicit plan-bound authorization.
- The Unreal Agent must never become a second autonomous authority separate from Atlas.
- Keep development isolated from the action/workflow runner.
- Do not weaken fail-closed validation.
- Preserve stateless Unreal adapter behavior.
- Preserve independent evidence verification.
