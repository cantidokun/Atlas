# Atlas Planning Layer

The planning layer defines the contracts that separate AI proposals from controlled production execution.

## Autonomous production path

```text
Qwen / AI agent
    -> proposes an ActionPlan
    -> ActionPlan is validated and authorized
    -> ActionPlanSequenceAdapter
    -> AutonomousTaskSequence
    -> autonomous admission / READY
    -> ProductionOperationLifecycle
    -> authorized execution
    -> authoritative verification
    -> execution / completion receipt
    -> tamper-evident checkpoint
    -> resume without replay
```

The planning layer does not give Qwen direct Blender authority. Existing capability admission, exact authorization, execution, verification, journal, registry, checkpoint, and completion boundaries remain authoritative.

## ActionPlan → autonomous sequence

`planning/action_plan_sequence_adapter.py` is the explicit bridge from an existing authorized `ActionPlan` to an `AutonomousTaskSequence`.

The adapter accepts only a **pristine, authorized** plan. Unauthorized, empty, partially executed, or failed plans are rejected. A resumed or interrupted plan must use the established checkpoint/recovery path instead of being rebuilt as a fresh sequence.

The adapter constructs operations but does not execute them or issue authorization.

## Autonomous sequence integrity

`planning/autonomous_task_sequence.py` provides ordered autonomous production sequencing with:

- stable operation identity binding;
- checkpoint serialization and rehydration;
- canonical SHA-256 checkpoint integrity validation;
- admission gating;
- persistence-before-progress advancement;
- fail-closed resume semantics.

A checkpoint is not an execution credential. Saved authorization is never replayed.

## Foundational boundaries

The planning layer continues to rely on these existing authorities:

- `blender_capability_catalog.py` — admitted Blender capabilities;
- `blender_write_authorization.py` — exact action authorization;
- `blender_live_write_gate.py` — final write choke point and durable execution journal;
- `blender_live_verification.py` — authoritative post-write verification;
- `blender_execution_receipt.py` — immutable execution receipt;
- `blender_execution_recovery.py` — interrupted execution recovery;
- `blender_autonomous_admission.py` — startup reconciliation and autonomous readiness;
- `production_operation_lifecycle.py` — authoritative production completion/blocking;
- `production_completion_receipt.py` — immutable completion evidence.

## Architectural direction

The next major layer is production-goal orchestration: transforming a validated higher-level production objective into an ordered set of already-admissible operations without creating a second execution or authorization mechanism.

Photogrammetry remains upstream of Blender. Atlas is concerned with soccer-field-related digital twins and their controlled production workflows. C++ interoperability remains a future architectural requirement, so subsystem contracts should remain language-agnostic.
