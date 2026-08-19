# Atlas Generic Architecture Contract

## Purpose

This document defines the boundary that every production task must satisfy before it can be treated as a generic Atlas capability.

## Authority

Qwen proposes. Atlas validates and authorizes. Blender executes. Atlas independently verifies authoritative state.

```text
proposal
  -> schema validation
  -> authoritative evidence
  -> target-state evaluation
  -> conditional decision
  -> authorization
  -> deterministic execution
  -> receipt
  -> fresh independent verification
  -> COMPLETE or BLOCKED
```

A successful executor response is never equivalent to successful target-state verification.

## Task boundary

Task-specific code may define:

- evidence requests
- action specifications
- target-state invariants
- allowed tool names
- write policy
- task metadata

Task-specific code must not implement its own authorization, receipt semantics, recovery semantics, or orchestration state machine.

`planning/task_definition.py` is the declarative boundary for this data.

## Required invariants

Every write-capable task must:

1. acquire authoritative evidence before deciding whether a write is necessary;
2. evaluate all required target invariants;
3. authorize the exact proposed mutation before execution;
4. execute through the validated tool boundary;
5. bind the verified normalized result to one immutable execution receipt;
6. acquire fresh authoritative evidence after execution;
7. complete only when the fresh evidence satisfies the target state;
8. enter `BLOCKED` when post-action verification fails.

## Zero-write rule

If authoritative evidence already satisfies every required invariant, the task must perform zero mutation calls.

## Receipt rule

One receipt corresponds to one validated request and one normalized execution result. A receipt must not be reused to authorize a second execution.

## Fail-closed rule

Malformed tool responses, wrong-tool results, mutated request/result data, invalid continuation identity, and failed required verification must not silently complete a task.

## Current proof levels

### Live-proven

- goalpost conditional execution
- generic collection creation

### Implemented but awaiting fresh live proof

- object rotation
- marker creation
- declarative `AtlasTaskDefinition` integration

## Promotion rule

A new task is not promoted to a live-proven generic capability until both an already-correct zero-write case and an incorrect-state authorized-write case pass with fresh independent verification. A false-success executor case must additionally demonstrate `BLOCKED`.
