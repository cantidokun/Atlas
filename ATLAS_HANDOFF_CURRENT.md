# Atlas Current Development Handoff

**Updated:** August 21, 2026 — overnight handoff  
**Latest verified CI:** 687 passed; Python 3.9 and 3.11 green  
**Purpose:** canonical resume point for the next Atlas Blender-Agent development session.

## 1. Current operating state

Testing is active and must remain part of development. Do not treat an old test count as evidence for newer code. After each meaningful implementation increment, run/follow the applicable regression gate and inspect the actual CI result.

The user explicitly authorized testing earlier in this session. The old temporary instruction to pause workflow testing is superseded by that explicit authorization.

## 2. Scope

This track is **Blender Agent only**. Unreal Agent work is out of scope for this development thread.

Photogrammetry remains upstream: dedicated photogrammetry software creates the initial 3D reconstruction; Blender receives it for analysis, cleanup, correction, optimization, and preparation.

## 3. Architecture currently established

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

Qwen is never execution authority. A successful production-tool response is never sufficient to establish final state.

Core generic primitives include action/evidence plans, target-state evaluation, verification plans, action authorization, replan authorization, deterministic futures, future execution/recovery, runtime integrity, audit trail, immutable Blender execution receipts, and task runtime policy.

## 4. Recent Blender-agent work

### Agent state + evidence-driven replanning

Replanning consumes a **verified** Blender observation and either:

- stops when the objective is verified satisfied; or
- produces a new `BlenderTaskIntent` for the normal planning/authorization path.

An existing authorized plan is never silently mutated by the replanner.

### Qwen → Atlas reasoning contract

Structured Qwen output is constrained before it can become an executable intent. Current coverage rejects malformed confidence, empty objective/observation/action/evidence fields, non-object action arguments, and unknown Blender tools at the capability-planning boundary.

The latest correction aligned the Qwen reasoning test with the canonical Blender rotation schema (`rotation_degrees`, required file/object fields).

## 5. Latest test status

**CI milestone: 687 passed.**

The corresponding GitHub Actions run is green on both:

- Python 3.9
- Python 3.11

This is the current verified baseline. The suite must be rerun after subsequent code changes.

## 6. Current development stage

### Stage 10 — Blender Adapter / Real Execution Bridge

**CURRENT**

The next implementation target is the adapter that maps an already-authorized Atlas action into a controlled real Blender execution request and maps the resulting Blender response/evidence back into Atlas.

Required properties:

- capability restrictions remain enforced;
- exact validated arguments are preserved;
- authorization scope cannot expand at the adapter;
- execution is deterministic and observable;
- results are normalized into the existing Blender result contract;
- verification remains independent;
- malformed/ambiguous responses fail closed;
- evidence can be returned to agent state/replanning;
- Qwen cannot use the adapter as an arbitrary Python execution channel.

Do not add a second bespoke execution architecture. Reuse the existing planning, authorization, receipt, verification, and state machinery.

## 7. Blender integration gate

Do **not** connect to the user's real Blender environment yet merely because the architecture looks close.

Before requesting/using the live Blender connection, the adapter contract must have focused offline tests and a fresh green CI result.

Then the first live proof should be intentionally small:

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

Only after that should the loop be expanded toward autonomous multi-step Blender work.

## 8. Milestone map

```text
Foundation / safety                     COMPLETE
Capability + schemas                    COMPLETE
Planning + authorization                COMPLETE
Execution + verification primitives     COMPLETE
Agent state + replanning                SUBSTANTIALLY COMPLETE
Qwen → Atlas reasoning contract         COMPLETE FOR CURRENT CONTRACT
────────────────────────────────────────────────────────
Blender adapter                         CURRENT
First live Blender operation            NEXT LIVE GATE
Closed-loop autonomous Blender Agent    FUTURE
```

## 9. Regression requirements

Preserve and extend coverage for:

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

## 10. Tomorrow's exact resume procedure

1. Read this handoff first.
2. Inspect the current branch/HEAD and confirm which commits contain the latest reasoning/replanning work.
3. Inspect the newest GitHub Actions result rather than assuming 687 still applies.
4. Implement the smallest coherent Blender adapter increment.
5. Add focused tests before considering the increment complete.
6. Run the regression gate and fix any failures.
7. Only after the adapter tests are green, prepare the first controlled live Blender connection.

## 11. Product architecture reminders

- Atlas is a soccer/sports digital-twin production platform, not a generic gym-digital-twin system.
- Photogrammetry is upstream of Blender.
- Blender is responsible for receiving the initial reconstruction and performing analysis, cleanup, correction, optimization, and preparation.
- Unreal is a later complementary production environment.
- Canonical Digital Twin identity/state must remain distinct from `.blend` representations and shot-specific variants.

## 12. Do not regress

- Do not give Qwen direct Blender execution authority.
- Do not allow automatic retry after failed writes.
- Do not silently mutate an authorized plan during replanning.
- Do not declare completion from a write response alone.
- Do not make goalpost-specific behavior the generic architecture.
- Do not skip tests after meaningful implementation changes.
- Do not connect live Blender until the adapter's focused tests are green.
