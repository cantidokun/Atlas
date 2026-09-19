# Pre-Review Architectural Adversarial Assessment — Correction Execution Bridge

Target: PR #119
Current design head: 99ef1e2e730bd8e592a7bc5d7cc2564a3726f83b
Base: main @ 3c0f26402513d708e3c55a0367cc6abd2c205c04

## Assessment status

**PRE-REVIEW RESULT: CLEAR WITH MINOR FINDINGS — REQUIRED FINDINGS CLOSED**

This record is paired with the independent Hermes/GLM-style red-team review supplied for PR #119. That review returned CLEAR WITH MINOR FINDINGS and allowed deterministic implementation once the §5 ordering finding was closed. The required findings are now incorporated; implementation is authorized only for the deterministic bridge phase, subject to the promotion gates.

## Checks performed

### Authority isolation

PASS.

The design keeps the correction planner as proposal authority, correction_authorization as the correction-specific authorization authority, and correction_executor as canonical mutation/postcondition authority.

No second planner, scheduler, retry controller, rollback engine, or correction receipt authority is introduced.

### Operation vocabulary

PASS after hardening.

The bridge is closed to exactly the four currently implemented correction IDs. The design now explicitly prevents a future correction from becoming bridge-executable merely because it enters a broader executor allowlist.

### Postcondition authority

PASS after hardening.

A potentially dangerous path was identified: caller-controlled expected postcondition identifiers/digests could have become a second acceptance authority. The design now explicitly requires the bridge to compute/verify these bindings from the canonical correction operation/executor contract and reject caller-supplied alternatives.

### Same-session lifecycle

PASS.

The design requires one bounded session for pre-extraction, mutation, and fresh post-extraction, with disposal on success, failure, timeout, crash, malformed response, or ambiguity.

### No-save boundary

PASS with implementation evidence required.

The design correctly rejects reuse of the generic file-persistence helper for correction execution and permits an input .blend to be loaded without permitting save/write. Live evidence must prove that the source/frozen asset is not modified and that no .blend/.blend1 artifact is created.

### Existing correction compatibility

PASS.

W1/W1b remain deterministic without invented authorization artifacts. W2/W3 retain mandatory authorization artifacts. Existing correction executor predicates and receipt schemas remain authoritative.

The design explicitly preserves the existing material-slot postcondition claim for REPAIR_MERGE_VERTEX while keeping Wave 14 raw observations outside global canonical claims.

### Generic Blender stack coexistence

PASS.

No expansion of the 14-tool schema is authorized. Existing BlenderExecutionBoundary semantics remain untouched.

### Partial mutation / ambiguity

PASS.

The design requires fail-closed outcomes, session disposal, no rollback, no automatic retry, and fresh evidence plus a newly validated/authorized plan before any retry.

### C++ seam

PASS.

The request/result shape is language-neutral and does not expose Python engine objects to the canonical correction layer.

## Minor findings

1. The implementation must be explicit about how the canonical postcondition binding is computed. The design is correct at the authority level, but the implementation must not invent a separate digest helper with semantics that can drift from the existing executor.

2. No-save proof must include process/session evidence, not only filesystem comparison. Filesystem evidence alone cannot prove that no save was attempted if the source and destination happen to be equivalent.

3. Adapter-boundary 'one invocation = one intended edit' is intentionally weaker than internal bpy-call cardinality. The implementation and live gate must preserve that distinction and must not accidentally claim stronger engine-call guarantees.

4. The bridge should be integrated through narrow dependency-injection seams rather than changing the semantics of the existing generic Blender execution boundary.

## Implementation gate

**Not authorized yet.**

Before implementation begins, the independent red-team must confirm that the four minor points above are either explicitly closed or accepted as non-blocking limitations.

Required implementation sequence after clearance:

design approval -> production bridge implementation -> deterministic tests -> existing-suite regression -> real Blender live bridge gate -> independent post-implementation red-team -> promotion.
