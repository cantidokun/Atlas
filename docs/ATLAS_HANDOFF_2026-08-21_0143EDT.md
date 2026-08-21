# Atlas Development Handoff — August 21, 2026 01:43 EDT

## Current repository state

- Current `main` HEAD: `3a7501b95e0ce2b292f513d0331c7382794e7b0b`
- HEAD message: `docs: record August 21 Blender reasoning milestone`
- Latest verified regression baseline: **687 passed**
- Python 3.9: **PASS**
- Python 3.11: **PASS**
- Intermediate **686 failed** because a stale Qwen/Blender reasoning fixture used an outdated rotation argument shape; the fixture was corrected to the canonical `rotation_degrees` schema and required object/file fields, producing the 687-pass result.

## Operating state

Atlas remains actively under development. Testing remains part of development, and the actual regression result must be inspected after each meaningful implementation increment. The earlier temporary workflow-testing pause was later superseded by explicit authorization to resume testing.

Do not treat the 687-pass baseline as validation for code added after that run.

## Scope

This development track is the **Blender Agent**. Unreal Agent work is out of scope for this thread.

Photogrammetry is upstream: dedicated photogrammetry software creates the initial 3D reconstruction. Blender receives that reconstruction for analysis, cleanup, correction, optimization, and preparation.

Atlas remains a soccer/sports digital-twin production platform.

## Current architecture

```text
Qwen / AI
  ↓ reason + propose
structured Blender reasoning
  ↓
BlenderTaskIntent
  ↓
capability + argument validation
  ↓
ActionPlan
  ↓
explicit authorization
  ↓
controlled execution boundary
  ↓
independent verification
  ↓
verified agent state / immutable evidence
  ↓
replan if objective remains unsatisfied
```

Qwen is a proposal source, never execution authority. A successful production-tool response does not establish final state; independent verification does.

Core generic machinery now includes:

- `ActionSpec` / `ActionPlan`
- evidence planning
- target-state evaluation
- verification planning
- action authorization
- replan authorization
- deterministic futures and future recovery
- runtime integrity
- audit trail
- immutable Blender execution receipts
- task runtime policy
- agent state
- evidence-driven replanning
- structured Qwen → Atlas reasoning validation

## Recent Blender-agent milestone

The Qwen/Atlas reasoning boundary is cleared for the current contract.

Structured reasoning is rejected before it can become an executable intent when it contains invalid confidence, empty required objective/observation/action/evidence fields, non-object action arguments, invalid structured action shapes, or unknown/non-capability Blender tools.

Evidence-driven replanning consumes verified Blender observations. If the objective is already satisfied, replanning stops. If not, it produces a new `BlenderTaskIntent` that must go through the normal planning and authorization path. An already-authorized plan is never silently mutated.

The latest fixture correction aligned the reasoning test with the canonical Blender rotation schema:

- `rotation_degrees`
- required object fields
- required file fields

## Latest test evidence

The current verified baseline is:

```text
687 passed
Python 3.9: PASS
Python 3.11: PASS
```

The preceding 686-test failure was a test-contract/fixture mismatch, not a newly discovered execution-boundary failure. After correcting the stale fixture, the suite reached 687 passed.

Future implementation changes require a fresh regression result before being promoted as verified.

## Current development stage

### Stage 10 — Blender Adapter / Real Execution Bridge

**Current target:** build the adapter that maps an already-authorized Atlas action into a controlled real Blender execution request and maps Blender response/evidence back into Atlas.

The adapter must:

- preserve capability restrictions;
- preserve exact validated arguments;
- prevent authorization-scope expansion;
- execute deterministically and observably;
- normalize Blender results into the existing Blender result contract;
- keep verification independent;
- fail closed on malformed or ambiguous responses;
- return usable evidence to agent state/replanning;
- prevent Qwen from using the adapter as an arbitrary Python execution channel.

Do not create a second bespoke execution architecture. Reuse the existing planning, authorization, receipt, verification, and state machinery.

## Blender integration gate

Do not connect to the real Blender environment merely because the adapter architecture looks complete.

First require focused offline adapter tests and a fresh green CI result. Then use the smallest possible live proof:

```text
controlled Blender scene
  ↓
inspect
  ↓
one authorized operation
  ↓
structured result
  ↓
independent verification
```

Only after that proof should the loop expand toward multi-step closed-loop autonomous Blender work.

## Regression requirements

Maintain coverage for:

- already-satisfied → zero writes;
- unsatisfied → exact authorized order;
- successful write → verification still mandatory;
- verification failure → `BLOCKED`;
- action failure → recovery gate;
- mutated arguments/result → receipt mismatch;
- malformed executor result → rejected;
- wrong result tool → rejected;
- invalid continuation identity → rejected;
- authorized fresh-evidence replan → accepted;
- unauthorized replan → rejected;
- malformed Qwen reasoning → rejected;
- unknown/non-capability Blender tool → rejected;
- adapter cannot bypass authorization;
- adapter preserves validated arguments;
- adapter normalizes executor results;
- adapter fails closed on malformed/ambiguous responses.

## Exact next steps

1. Start from current `main` HEAD `3a7501b95e0ce2b292f513d0331c7382794e7b0b`.
2. Inspect the latest reasoning/replanning changes and preserve their validated contracts.
3. Implement the smallest coherent Blender adapter increment.
4. Add focused offline tests for the adapter boundary.
5. Establish and inspect a fresh regression result; 687 is only the current historical baseline.
6. Verify the adapter cannot expand authorization or bypass existing receipt/verification machinery.
7. After focused tests are green, prepare the first controlled live Blender connection.
8. Live-prove one inspect → one authorized operation → structured result → independent verification.
9. Expand to multi-step closed-loop operation only after the adapter and first live operation are proven.

## Do not regress

- Never give Qwen direct Blender execution authority.
- Never allow automatic retry after failed writes.
- Never silently mutate an authorized plan during replanning.
- Never declare completion from a write response alone.
- Never make goalpost-specific behavior the generic architecture.
- Never skip regression validation after meaningful implementation changes.
- Never connect live Blender before the adapter's focused tests are green.
- Never represent the 687-pass baseline as proof for later code.
