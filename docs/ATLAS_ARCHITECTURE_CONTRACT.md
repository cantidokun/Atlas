# Atlas Generic Architecture Contract

## Purpose

This document defines the boundary every Atlas production capability must satisfy before it can participate in autonomous execution.

## Authority

Qwen proposes. Atlas validates, resolves, and authorizes. Blender and Unreal execute through controlled adapters. Atlas independently verifies authoritative state.

```text
Qwen proposal
  -> provider/schema validation
  -> trusted catalog resolution
  -> semantic task
  -> Atlas authorization
  -> deterministic execution
  -> immutable receipt/evidence
  -> fresh independent verification
  -> COMPLETE or BLOCKED
```

A successful transport or executor response is never equivalent to successful target-state verification.

## Task boundary

Task-specific code may define evidence requests, action specifications, target-state invariants, allowed tools, write policy, and semantic metadata.

Task-specific code must not implement a second authorization mechanism, receipt model, recovery state machine, scheduler, or execution authority.

`planning/task_definition.py` remains the canonical declarative task boundary. Higher-level production tasks compile into it rather than bypassing it.

## Qwen boundary

Qwen is an untrusted reasoning/proposal source.

For the current Stage 16 contract it may provide only:

- workflow identity;
- optional catalog version;
- workflow parameters.

Qwen may not provide:

- executor objects;
- arbitrary tool calls;
- authorization IDs or receipts;
- scheduling directives;
- recovery authority;
- direct file/scene mutation instructions outside the catalog contract.

`qwen/production_handoff.py` is the explicit seam from validated Qwen intent into Atlas authority. The handoff performs provenance/integrity checks and delegates authorization to the existing Atlas `ActionAuthorization` path.

## Required invariants

Every write-capable task must:

1. acquire authoritative evidence before deciding whether a write is necessary;
2. evaluate all required target invariants;
3. authorize the exact proposed mutation before execution;
4. execute through the validated engine/tool boundary;
5. record immutable execution evidence/receipt according to the existing contract;
6. acquire fresh authoritative evidence after execution;
7. complete only when fresh evidence satisfies the target state;
8. enter `BLOCKED` when required verification fails;
9. require fresh evidence and explicit replan authorization before recovery writes;
10. never automatically retry a failed write.

## Zero-write rule

If authoritative evidence already satisfies every required invariant, the task must perform zero mutation calls and must not mint unnecessary write authorization.

## Authorization rule

Authorization binds to the exact action plan, including dependency declarations and inherited completed prerequisites where applicable. An authorized plan cannot be silently rewritten.

A Qwen proposal never constitutes an authorization receipt. Atlas must explicitly create the authorization after validating the canonical task.

## Continuation and recovery

Durable continuation must bind runtime identity, future state, semantic task provenance, and the exact authorization required for the pending future.

Recovery must be fail-closed:

```text
failure
  -> durable BLOCKED checkpoint
  -> fresh authoritative evidence
  -> recovery gate
  -> explicit replan authorization
  -> replacement future
  -> execution
  -> fresh independent verification
```

Completed prerequisites are recovered from trusted successful checkpoints rather than executor payload claims.

## Current proven development position

### Blender

- Stage 11 controlled live Blender operation — live verified.
- Stage 12 task-aware autonomous execution and recovery — complete for current contract.
- Stage 13 multi-step partial-progress recovery — complete for current contract and live verified.
- Stage 14 dependency-aware serial execution and cross-process recovery — complete for current contract and live verified.
- Stage 15 semantic soccer-production task composition, target-state evaluation, versioned catalog, and provenance persistence — complete for current contract and live verified.
- Stage 16 Qwen provider/proposal integration — in progress.

### Stage 16 verified boundary

The local Qwen proposal-only smoke has been user-verified:

```text
Qwen
  -> Ollama structured output
  -> catalog validation
  -> QwenProductionProposal
  -> ProductionTaskDefinition
  -> semantic task compilation
```

The smoke deliberately stopped before authorization and execution and produced no Blender mutation.

The authorization/runtime handoff is now implemented but awaits the user's live runtime proof:

```text
validated Qwen proposal
  -> provenance-bound QwenProductionTaskHandoff
  -> existing Atlas ActionAuthorization
  -> pre-authorized generic task-runtime bootstrap
  -> existing AutonomousTaskRuntime
  -> existing Blender boundary
```

The first full Qwen-authorized mutation harness has been implemented but is not yet live-verified by the user.

## Engine boundaries

Blender and Unreal remain adapters/execution environments. Engine-specific operations must not become the generic authority model.

Unreal Engine 5.6 render configuration, MRQ submission, job inspection, artifact validation, evidence-bound render receipts, and durable receipt persistence are proven locally for the implemented boundary.

Cross-process Unreal render-job recovery is not implemented.

## Resolution / source footage

Atlas is intended to support 4K/UHD soccer source footage. Resolution affects processing/resource requirements and execution throughput but does not change the orchestration contract. Preserve high-resolution source provenance while using suitable proxies/intermediates.

## Promotion rule

A new production capability is not considered live-proven until appropriate zero-write, authorized-write, independent verification, and failure/recovery cases pass with evidence matching the declared contract.

## Non-regression rules

- Preserve the evidence ledger.
- Preserve independent verification.
- Do not add a parallel execution model before concurrency is independently justified.
- Do not weaken tests to make architectural changes pass.
- Do not give Qwen execution or authorization authority.
- Do not automatically retry failed writes.
- Do not claim cross-process Unreal job recovery until separately implemented and verified.
- Keep the canonical Digital Twin distinct from DCC/engine production artifacts.
- Keep photogrammetry as upstream reconstruction, with Blender handling analysis/cleanup/correction/preparation.