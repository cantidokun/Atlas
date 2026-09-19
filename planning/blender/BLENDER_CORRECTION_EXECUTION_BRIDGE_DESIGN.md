# Blender Correction Execution Bridge — Design Gate

Status: DESIGN REVIEW REQUIRED — implementation not authorized
Base: main @ 3c0f26402513d708e3c55a0367cc6abd2c205c04
Scope: Blender correction execution only

## 1. Purpose

Wave 15 closed the live evidence boundary for the four existing controlled correction entry points:

- REMOVE_DUPLICATE_FACE
- REMOVE_DEGENERATE_FACE
- REPAIR_FACE_WINDING
- REPAIR_MERGE_VERTEX

The production correction executor already owns the canonical proposal, source-binding, precondition, mutation, postcondition, and receipt contract. Its engine mutation and extraction seams remain deliberately unbound to a real Blender engine in production.

The next bounded capability is therefore not a new correction family. It is a Correction Execution Bridge that connects the existing correction contract to one bounded real-Blender session while preserving existing authority boundaries.

This document is a design gate. It does not authorize implementation, alter correction schemas, or promote any new correction type.

## 2. Non-negotiable authority rules

1. The correction planner remains the proposal authority.
2. correction_authorization remains the only correction-specific authorization authority.
3. The correction executor remains the canonical correction execution authority.
4. The bridge is a mechanical engine adapter, not a planner, authorizer, scheduler, retry system, or rollback system.
5. The generic Blender tool catalog remains independent. The bridge must not expand BLENDER_TOOL_SCHEMAS with mesh-editing tools.
6. The canonical correction receipt remains the sole correction receipt. BlenderExecutionReceipt remains transport evidence only.
7. Transport success never becomes correction success; canonical postconditions remain authoritative.
8. Correction execution is no-save. Persistence is an explicit outer decision.
9. Failed or ambiguous mutation is never retried automatically and never rolled back implicitly.
10. Any retry requires fresh read-only evidence and a newly validated and explicitly authorized plan.

## 3. Current architecture

### Generic Blender execution stack

The generic path is:

tool request -> BlenderToolSchema -> BlenderExecutionBoundary -> BlenderProcessExecutor -> run_checked_blender -> normalized transport result -> optional execution receipt -> optional persistence evidence

The generic boundary exposes execute, execute_verified, execute_with_receipt, and execute_with_persistence. The persistence helper is deliberately file-backed and is not a correction authority.

### Canonical correction stack

The correction path is:

SceneModel/SceneReport -> correction planner -> optional authorization artifact -> correction executor -> injected mutation -> fresh extraction -> canonical postconditions -> correction receipt

The correction executor already owns plan integrity, source binding, target binding, parameter allowlists, correction-specific preconditions, authorization enforcement where required, bounded mutation, fresh post-mutation extraction, postconditions, and correction receipt semantics.

The production gap is the engine binding at the injected seams.

## 4. Proposed bridge

The bridge contains six bounded pieces.

### 4.1 Closed correction operation vocabulary

Use a correction-specific operation vocabulary separate from the 14-tool generic Blender catalog:

- REMOVE_DUPLICATE_FACE
- REMOVE_DEGENERATE_FACE
- REPAIR_FACE_WINDING
- REPAIR_MERGE_VERTEX

These identifiers are transport-level aliases for the existing canonical correction type identifiers; they must not become a second correction taxonomy. The implementation must derive or validate them against the canonical executor/mapping identifiers rather than maintaining an independently drifting list.

Unknown operations fail closed. The bridge accepts no arbitrary Python expression, arbitrary Blender operator path, or free-form mutation script.

### 4.2 Language-neutral correction request

The minimum engine-facing request should contain:

- operation
- plan_id
- correction_id
- source_report_digest
- object_id
- mesh_id
- parameters
- expected_postcondition_ref
- expected_postcondition_digest

Optional transport metadata may include bridge_version, correction_executor_version, and source_scene_id.

These fields bind an already validated correction; they do not create a second planner or second authority.

### 4.3 Bounded Blender mutation adapter

The adapter resolves the explicitly bound object and mesh, validates the closed request, performs one intended correction mutation, and returns a typed result.

It must not re-plan, select another target, authorize, save, retry, repair additional findings, mutate unrelated objects, or execute arbitrary operators.

The four existing corrections should use the data-level mutation patterns already exercised by the Wave 15 live gates.

### 4.4 Canonical extraction composition

The bridge supplies the correction executor with a real engine-backed extract_and_report implementation using the existing canonical extraction/report path.

The same session must provide:

1. authoritative pre-state extraction;
2. existing source binding and preconditions;
3. one bounded mutation;
4. fresh post-state extraction;
5. existing canonical postcondition evaluation.

The bridge must not create a second SceneModel vocabulary or second health predicate system.

### 4.5 Bounded correction session

The lifecycle is:

open -> pre-extract -> validate -> mutate -> post-extract -> dispose

The process/session exists for one correction invocation only. Dispose it after completion, failure, timeout, crash, malformed response, or ambiguous mutation. A disposed session is never reused.

### 4.6 Verification bridge

Generic verify_blender_execution remains transport/shape verification only.

The existing correction executor remains authoritative for exact state deltas, target identity, unrelated-state preservation, finding clearing, authorization semantics, and correction receipt derivation.

## 5. Exact execution order

1. Receive a closed correction request.
2. Validate envelope shape and operation vocabulary.
3. Establish plan, correction, and source binding through the canonical executor.
4. Open the bounded Blender session without persistence.
5. Extract authoritative pre-state.
6. Run existing correction preconditions.
7. For W2/W3, verify the existing authorization artifact through correction_authorization.
8. Translate the already-approved correction into one bounded engine operation.
9. Execute exactly one intended correction mutation.
10. Return a typed mutation result.
11. Freshly extract state in the same session.
12. Run existing canonical postconditions.
13. Emit the existing canonical correction result and receipt.
14. Dispose the session.
15. Persist only if an explicit outer workflow later elects to do so.

The bridge must not introduce a second authorization gate. Structural transport validation is permitted, but it is not authority.

## 6. Authorization

W1 and W1b retain their current deterministic authority model; the bridge must not invent an authorization artifact requirement.

W2 and W3 retain mandatory correction authorization. The bridge receives an already verified authorization decision and must never interpret plan state alone as authorization.

Proposal, plan validity, authorization validity, engine success, and postcondition success remain separate concepts.

authorization_verified=true is not a success flag. An accepted authorization followed by a no-op mutation must still fail postconditions.

## 7. No-save and persistence

The correction bridge must not call BlenderExecutionBoundary.execute_with_persistence because that API is intentionally file-oriented.

During correction execution:

- the source file is opened for the bounded session;
- mutation exists only in Blender memory;
- no .blend or .blend1 file is created or overwritten;
- session disposal ends the correction execution lifecycle.

Live evidence should demonstrate no-save with source/output path state, created-file inventory, absence of a save operation in the adapter, and process disposal.

Persistence is outside the correction success contract.

## 8. Partial mutation and ambiguity

An engine crash or ambiguous result may leave uncertain internal progress. Such a case is always failure.

Required behavior:

- return MUTATION_FAILED or PARTIAL_FAILURE as appropriate;
- never infer completion from process survival;
- never roll back implicitly;
- never retry automatically;
- dispose the session;
- invalidate current execution evidence;
- require fresh read-only evidence and a new validated/authorized plan before any retry.

This conforms to the existing action recovery policy.

## 9. One invocation / one intended edit

The adapter contract is one mutation invocation equals one intended bounded correction edit.

This is an adapter-boundary contract, not an assertion that Blender internally uses only one bpy call. Production code should not add internal bpy-call counting.

Existing bounded edits are:

- duplicate/degenerate removal: one recorded face removed;
- winding: one exact face-orientation reversal;
- merge vertex: one bounded vertex/face rebuild.

No second correction may be performed as a side effect.

## 10. Compatibility with existing corrections

REMOVE_DUPLICATE_FACE: same-datablock rebuild removing exactly the recorded duplicate, followed by existing canonical postconditions.

REMOVE_DEGENERATE_FACE: execution-time revalidation of the recorded degenerate face, followed by the existing postcondition contract. The Wave 15 two-vertex polygon case remains covered.

REPAIR_FACE_WINDING: exact directed-edge reversal already exercised by the W2 live gate. Mandatory authorization remains unchanged.

REPAIR_MERGE_VERTEX: existing bounded merge behavior and survivor rules remain unchanged; the bridge only supplies the real engine mutation and fresh extraction.

## 11. Fidelity boundaries

The bridge inherits the established Wave 14/15 fidelity boundary and does not silently expand it.

Unless an existing canonical contract already guarantees them, the bridge does not newly guarantee:

- polygon material_index preservation;
- material datablock identity;
- arbitrary Blender datablock identity;
- normals preservation;
- UV-layer semantics;
- arbitrary custom-data-layer preservation;
- broader local-coordinate-frame fidelity.

The important qualification is operation-specific: REPAIR_MERGE_VERTEX already has canonical material-slot preservation clauses in its existing MQ postconditions. The bridge must preserve that existing claim rather than weakening it. By contrast, raw material-slot/datablock observations that are not part of a canonical correction contract remain test-only evidence.

## 12. Receipts and provenance

The canonical correction receipt remains authoritative.

BlenderExecutionReceipt remains generic transport evidence and must not replace or force an expansion of the correction receipt.

Engine/session provenance needed for live evidence belongs in gate evidence or separate lineage metadata, not in the canonical correction receipt.

## 13. Generic-stack coexistence

The bridge must coexist with the existing generic Blender execution boundary without changing its semantics.

Do not:

- add correction operations to the generic 14-tool schema;
- change execute, execute_verified, execute_with_receipt, or execute_with_persistence semantics;
- make generic execution aware of correction authorization;
- make generic persistence mandatory for correction execution;
- route correction execution through the file-oriented persistence helper.

Shared low-level process infrastructure is acceptable only when it is mechanical and does not merge authority models.

## 14. C++ seam

The request/result contract must be language-neutral.

A future C++ adapter must be able to implement the same structured request, typed result, deterministic digest, operation identifiers, and failure codes without changing planner semantics, authorization semantics, canonical postconditions, or correction receipts.

## 15. Required adversarial matrix

Request/plan integrity: unknown operation, malformed envelope, missing field, extra field, invalid digest, plan mismatch, correction mismatch, source mismatch, postcondition reference mismatch.

Target binding: missing object, missing mesh, object/mesh mismatch, ambiguous owner, substituted target, changed target content.

Preconditions: stale face index, changed face tuple, correction no longer present, stale authorization target, altered engine state between planning and execution.

Authorization: missing artifact, malformed artifact, invalid artifact, unapproved decision, scope mismatch, wrong correction/plan/source IDs, incorrect designation/counterpart binding.

Engine behavior: process failure, timeout, malformed marker envelope, invalid JSON, unexpected result shape, mutation exception, ambiguous termination, partial mutation, no-op mutation, wrong-target mutation.

Postconditions: wrong state delta, more than one intended correction, unrelated object/mesh change, prohibited vertex-table change, finding not cleared, receipt/result inconsistency.

Persistence: attempted save, unexpected output file, source overwrite attempt, accidental use of persisted-state evidence in place of same-session in-memory evidence.

Every negative case must fail closed and must not authorize a second mutation within the same session.

## 16. Live acceptance plan

Before implementation may advance to live testing, deterministic tests must establish:

1. closed request/result schema;
2. operation allowlist;
3. same-session lifecycle;
4. no-save behavior;
5. adapter isolation;
6. real extraction composition;
7. partial/ambiguous failure disposal;
8. correction receipt preservation;
9. generic-stack non-regression.

The real Blender live gate must then prove pre-extraction, real mutation, fresh post-extraction, canonical completion/refusal, W2/W3 authorization behavior, target/content binding, adapter-boundary mutation budget, no-save evidence, frozen-file evidence, receipt integrity, and process disposal.

Existing W1, W1b, W2, and merge live gates remain capability-specific and must not be collapsed into a generic mutation-success assertion.

## 17. Promotion gate

Implementation is not promotion-ready until:

- bridge deterministic tests are green;
- the full deterministic suite remains green;
- generic Blender execution tests remain green;
- existing W1/W1b/W2/merge live gates remain green;
- the new bridge live gate passes on real Blender;
- frozen asset audit is unchanged;
- no-save audit is clean;
- only explicitly approved bridge modules carry production semantic changes;
- no new correction family is introduced;
- no generic tool schema expansion occurs;
- no duplicate authorization exists;
- no correction receipt schema drift occurs;
- no implicit retry or rollback is introduced;
- independent red-team review finds no blocker;
- all findings are closed or explicitly recorded as non-blocking limitations.

## 18. Frozen boundaries

This milestone does not authorize changes to Temporal Observation + State Delta, Unreal, new correction mapping entries, SceneModel schema, mesh-health predicates, generic Blender tool semantics, generic persistence semantics, action recovery, correction receipt schema, material_index claims, normals/UV/custom-data guarantees, multi-correction transactions, background scheduling, automatic retry, or rollback.

## 19. Explicit non-goals

The bridge is not a general Blender scripting interface, generic mesh-editing API, second planner, second authorization system, persistence manager, rollback engine, workflow scheduler, arbitrary-code runner, or replacement for the canonical correction executor.

## 20. Design conclusion

The controlled production bridge is justified because the correction contracts and live evidence are already mature while the production mutation and extraction seams remain intentionally unbound.

The correct next implementation is therefore a narrow, correction-specific, no-save, same-session engine adapter and verification bridge.

This document remains a gate until independently reviewed. Its existence does not authorize implementation.