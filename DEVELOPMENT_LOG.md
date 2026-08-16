# Atlas Development Log

## August 16, 2026 — Conditional Action Planning V1 Proven Live

### Conditional action planning — PASS

The live conditional workflow has now passed both branches against the real self-hosted Windows runner, real Blender installation, deterministic Blender fixtures, local Qwen through Ollama, and the Atlas Python execution boundary.

#### Already-correct branch — PASS

Atlas successfully:

1. provisioned the deterministic correct Blender fixture
2. found the fixture in `GITHUB_WORKSPACE`
3. accepted and semantically validated the Qwen proposal
4. gathered authoritative read-only evidence
5. determined `target_satisfied = true`
6. skipped all conditional writes
7. independently re-inspected the Blender scene
8. verified the no-op result

#### Incorrect branch — PASS

Atlas successfully:

1. provisioned the deterministic incorrect Blender fixture
2. gathered authoritative read-only evidence
3. determined `target_satisfied = false`
4. crossed the explicit authorization boundary
5. executed the required `move_object` actions
6. independently inspected the resulting Blender state
7. verified the corrected target state

This proves the complete conditional loop:

```text
Qwen proposal
 ↓
Python validation
 ↓
Read-only evidence
 ↓
Target-state decision
 ├── already correct → NO-OP → independent verification
 └── incorrect → authorization → writes → independent verification
```

The important architectural result is that Qwen proposes, while Python controls whether action is necessary, authorization, execution, and verification.

### Live integration debugging completed

The conditional live tests exposed and resolved these integration issues:

- incorrect evidence argument names
- strict flat Qwen plan normalization
- incorrect Qwen object names
- incorrect deterministic fixture state
- Blender executable discovery on the self-hosted runner
- opaque Qwen parse failures
- fixture generation using the developer Desktop instead of `GITHUB_WORKSPACE`
- Blender tool path resolution using the legacy Desktop root
- Qwen returning full Windows paths where the tool contract required basenames

The final working contract is:

```text
GITHUB_WORKSPACE
    ↓
deterministic fixture files
    ↓
Blender tool resolution
    ↓
exact fixture object contract
    ↓
Qwen basename-only file references
```

### General Action Planning V1

The generic `action_plan.py` primitive remains the execution state machine for ordered authorized actions. The goalpost behavior is not being promoted into the generic architecture.

### General Evidence Planning V1

The generic `evidence_plan.py` primitive remains responsible for ordered evidence requests, completion, reuse, and blocking failures.

### Planning Orchestrator V1

`planning_orchestrator.py` continues to enforce evidence completion before authorized action execution.

### Controlled failure / recovery

The live recovery harness passed.

A failed write is detected as recoverable, fresh evidence is required, and automatic retry is refused. A new validated and explicitly authorized plan is required before retrying.

### Audit trail

The live action workflow records the lifecycle in order:

```text
Qwen proposal
 ↓
Evidence
 ↓
Authorization
 ↓
Execution
 ↓
Verification
```

### Regression status

The local regression suite was green on the conditional planning changes, including Local Tests #51 on commit `efa6adcf`.

### Documentation

`README.md`, `ATLAS_HANDOFF_CONTEXT.txt`, and `DEVELOPMENT_LOG.md` are being synchronized with the verified conditional milestone.

### Next architecture target

The goalpost conditional harness should remain as a permanent regression test, but the next implementation step is to extract the reusable conditional behavior away from the goalpost-specific contract.

The generic abstraction should allow a soccer-field task to define:

```text
required evidence
 ↓
target-state predicate
 ↓
authorized actions
 ↓
independent verification
```

The next proof should use different soccer-field objects and a different target predicate so we can demonstrate that the conditional engine is genuinely reusable rather than merely a goalpost special case.

Do not add a new Blender tool unless a real capability gap is proven.

### User test protocol

When a new local test is ready, immediately provide the exact command/prompt. Do not ask the user to run a test before the harness exists on `main`.
