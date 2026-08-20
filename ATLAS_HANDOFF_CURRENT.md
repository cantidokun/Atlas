# Atlas Current Development Handoff

**Updated:** August 20, 2026 03:30 EDT  
**Branch:** `controller/communication-runtime`  
**Controller bridge status:** architecture complete; ChatGPT integration pending  
**Main Blender baseline:** `934a615f3a1be5a22b75c3251ad005df7f7f79a2` — `fix: retry transient Ollama planning timeout in collection task`

## 1. Scope and authority

This handoff now records two related tracks:

1. the established Blender Agent development baseline; and
2. the completed controller/communication layer whose purpose is to remove the human bridge between ChatGPT/the reasoning side and the local coding agent.

The controller track does **not** authorize Blender or Unreal execution directly. Its role is communication, session state, request correlation, model-turn supervision, local Aider process control, and safe routing into the existing Atlas controller.

Atlas authority model:

```text
Qwen / AI -> reason + propose
Python / Atlas -> validate -> authorize -> execute -> track -> verify -> recover
Production adapters -> execute
Atlas -> independent authoritative-state verification
```

Qwen is never the execution authority. Production-tool success is never by itself authoritative state.

Photogrammetry is upstream: dedicated photogrammetry software creates the initial reconstruction; Blender receives it for analysis, cleanup, correction, and preparation.

## 2. Current runtime/test posture

Workflow and action-runner testing is authorized by the user and has resumed.

The local GitHub Actions runner `atlas-local` is operational and is used for Windows/Blender live regressions. Ollama is treated as dedicated Atlas infrastructure for this development track.

The GitHub-hosted offline CI workflow remains separate from local Blender live workflows.

The controller/communication branch is also using GitHub Actions as its offline validation gate. Recent controller milestones have passed their required tests, including **Test #623**, which cleared the final controller resilience/process-boundary proof.

## 3. Generic architecture

Implemented generic primitives include:

- `ActionPlan`
- `EvidencePlan`
- `TargetStateEvaluator`
- `VerificationPlan`
- `PlanningOrchestrator`
- `ConditionalPlanningOrchestrator`
- `ActionAuthorization`
- `ReplanAuthorization`
- `DeterministicFutureGenerator`
- `FutureExecutionController`
- `FutureRecoveryGate`
- runtime-context fingerprinting / integrity checks
- audit trail
- immutable Blender execution receipts
- `AtlasTaskDefinition`
- `docs/ATLAS_ARCHITECTURE_CONTRACT.md`

Conditional execution remains explicitly separated into evidence acquisition, target evaluation, skip/execute decision, authorization, deterministic execution, fresh verification, and fail-closed completion/blocking.

## 4. Blender files/tools

Core boundary:

- `planning/blender_tool_schema.py` — validates supported Blender tools, required arguments, types, and 3D coordinates; includes `create_empty_marker`.
- `planning/blender_execution_boundary.py` — validated execution, `execute_verified()`, and receipt-bound single execution.
- `planning/blender_result_contract.py` — normalized immutable result contract.
- `planning/blender_verification.py` — requested-tool identity and successful-execution verification.
- `planning/blender_execution_receipt.py` — deterministic request/result receipt and mutation detection.
- `planning/verification_plan.py` — required/pending/complete/blocked verification state.
- `planning/task_definition.py` — `AtlasTaskDefinition` declarative task boundary.
- `tools/blender.py` — scene/relationship inspection, collection creation, marker creation, goalpost movement.
- `tools/blender_transform.py` — transform inspection and rotation mutation.
- `tools/__init__.py` — Blender tool registry.

## 5. Controller communication architecture

The controller/communication layer now includes:

- `controller/communication_gateway.py` — protocol, sessions, request deduplication, and controller-owned command dispatch;
- `controller/communication_runtime.py` — session-bound controller runtime and bounded model-turn integration;
- `controller/communication_turn.py` — deterministic model-turn state machine with deadline, heartbeat, timeout, failure, and cancellation states;
- `controller/aider_model_client.py` — non-shell, bounded Aider subprocess adapter;
- `controller/communication_stdio.py` — newline-delimited JSON transport and composition layer;
- `controller/communication_host.py` — standalone local host with local executor/Aider configuration;
- `controller/communication_client.py` — programmatic caller-side client for the local host;
- `controller/controller_integration.py` — bridge into the existing Atlas controller execution boundary.

Safety properties proven by the controller test suite include:

- no arbitrary remote tool dispatch;
- session and request correlation;
- request deduplication;
- structured errors;
- bounded model turns;
- hard Aider timeout/termination;
- recovery after a stalled Aider turn;
- multiple sequential turns in one session;
- controller-owned Aider Git commit policy;
- process-level communication without manual message copying.

## 6. Controller milestones — VERIFIED

### Milestone 1 — communication/process boundary

**COMPLETE**

Proven path:

```text
programmatic client
    ↓
standalone controller host
    ↓
controller runtime
    ↓
Aider subprocess
    ↓
structured response
```

### Milestone 2 — autonomous multi-turn communication

**COMPLETE**

Proven path:

```text
model turn 1
    ↓
controller-retained state/result
    ↓
next model turn
    ↓
Aider again
    ↓
continued session
```

The controller can sustain sequential model turns and preserve terminal state between turns.

### Resilience milestone — stalled-model recovery

**COMPLETE**

Proven path:

```text
Aider/model turn stalls
    ↓
hard timeout
    ↓
Aider process terminated
    ↓
controller remains alive
    ↓
new model turn succeeds
```

**GitHub Actions Test #623 — PASS.**

## 7. Human-bridge removal — current roadblock

The controller architecture is now **communication-complete**. The remaining blocker is outside the controller protocol itself:

> **This ChatGPT session does not currently have a live callable interface into the user's local Atlas controller process.**

The distinction is important:

```text
ARCHITECTURE PROVEN
ChatGPT-side caller
        ↓
programmatic controller client
        ↓
local controller
        ↓
Aider
        ↓
local machine
```

The tests prove that this path works when a local program can invoke the controller client. They do **not** establish that the current ChatGPT conversation has a tool connection capable of making those local calls itself.

Therefore:

- the human relay is **architecturally removable**;
- the human relay is **not yet operationally removed from this ChatGPT session**;
- no additional controller redesign is required merely to solve this boundary;
- the missing component is a secure, callable ChatGPT-to-local-controller integration.

A suitable integration must preserve the existing controller as the authority boundary. An MCP-style callable integration is one viable direction, but the specific deployment mechanism remains to be established.

The integration must **not** bypass:

- controller authorization;
- session/request validation;
- timeout and recovery rules;
- request deduplication;
- Aider subprocess isolation;
- controller-owned Git commit policy;
- independent verification and existing Atlas execution boundaries.

## 8. Current known Blender boundaries

- `create_empty_marker` remains the next materially distinct Blender capability to live-prove if required by the promotion sequence.
- Broader production-facing autonomous continuation across multiple materially different Blender capabilities is not yet declared complete.
- Generic live proofs establish the architecture for the tested capabilities; they do not prove arbitrary Blender production planning.
- Executor success is never authoritative state; fresh verification remains mandatory.
- Do not add task-specific branches to generic planners or bypass authorization/verification.

## 9. Immediate next steps

### Controller track

1. Establish a callable ChatGPT-to-local-controller integration.
2. Connect that integration to the already-verified `controller/communication_client.py` / `communication_host.py` path.
3. Run one controlled autonomous development task with no manual message relay.
4. Keep the controller unchanged as the authority boundary while validating the integration.

### Blender/Unreal tracks

Once the communication integration is available, the controller can be used to accelerate the existing production-agent work.

For Blender, the immediate capability remains `create_empty_marker` followed by broader continuation/resume proof.

For Unreal, the authoritative Unreal handoff still identifies PR #10's first real Unreal Engine smoke test as the next required engine-side gate; do not replace that test with additional architecture.

## 10. Required regression coverage

Preserve proofs for:

- already-satisfied -> zero writes
- unsatisfied -> exact authorized action order
- authorization mandatory before writes
- successful write -> verification mandatory
- failed verification -> `BLOCKED`
- failed action -> recovery gate
- mutated arguments -> receipt mismatch
- mutated result -> receipt mismatch
- malformed executor response -> rejected
- wrong result tool -> rejected
- invalid continuation identity -> rejected
- authorized replan from fresh evidence -> accepted
- unauthorized replan -> rejected
- one receipt-bound execution cannot cause duplicate writes
- controller request deduplication
- controller structured errors
- model-turn timeout/termination
- stalled-model recovery
- sequential model turns
- process-level client/host/Aider round trip
- no arbitrary remote tool dispatch

## 11. Resume instructions

Read this file first.

**Controller status:** architecture complete; ChatGPT callable integration pending.

**Do not treat the successful controller test suite as proof that this ChatGPT session can already invoke the local machine.** That final integration boundary is the remaining human-bridge blocker.

**Blender resume point:** preserve the passing baseline and continue the existing validation → authorization → deterministic future → execution → verification → receipt architecture.

**Unreal resume point:** preserve the existing PR #10 disposable harness and complete the first real Unreal Engine smoke test before adding production transport architecture.
