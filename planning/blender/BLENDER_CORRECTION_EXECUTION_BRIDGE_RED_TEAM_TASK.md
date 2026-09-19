# Independent Red-Team Task — Blender Correction Execution Bridge

Target: PR #119 / commit ae606efd57d123a22c77618ef71542710b874f50
Base: main @ 3c0f26402513d708e3c55a0367cc6abd2c205c04
Review mode: architecture/design only; do not modify production code.

## Objective

Independently challenge the Correction Execution Bridge design before implementation authorization.
The desired verdict format is CLEAR, CLEAR WITH MINOR FINDINGS, or BLOCK.

## Required checks

1. Authority isolation:
- no second planner;
- no second authorization system;
- no second canonical correction receipt;
- no retry/rollback/scheduler hidden in the bridge;
- generic Blender authority remains separate.

2. Operation vocabulary:
- closed four-operation vocabulary;
- no arbitrary Blender/Python execution surface;
- verify the vocabulary cannot drift from canonical correction IDs;
- confirm bridge operations are transport identifiers, not a second correction taxonomy.

3. Same-session lifecycle:
- authoritative pre-extraction;
- canonical preconditions;
- exactly one bounded mutation invocation;
- fresh same-session post-extraction;
- canonical postconditions;
- guaranteed disposal on success/failure/timeout/ambiguous result.

4. No-save boundary:
- bridge does not route through execute_with_persistence;
- no .blend/.blend1 output is required for correction success;
- saved-state evidence cannot substitute for same-session post-state;
- no hidden save path exists in the proposed adapter.

5. W1/W1b/W2/W3 compatibility:
- W1/W1b retain their current no-artifact authority model;
- W2/W3 retain mandatory authorization artifacts;
- authorization_verified is not conflated with execution success;
- existing canonical pre/post predicates remain authoritative;
- merge vertex material-slot fidelity already claimed by its existing canonical MQ contract must not be accidentally weakened by broad non-claim language.

6. Transport and receipt:
- BlenderExecutionReceipt remains generic transport evidence;
- correction receipt remains authoritative;
- no unnecessary receipt schema expansion;
- typed failure results cannot be promoted to correction success.

7. Partial mutation and ambiguity:
- no automatic retry;
- no rollback;
- session disposal;
- fresh evidence and a newly validated/authorized plan required for any retry.

8. C++ seam:
- request/result is language-neutral;
- no Python engine objects leak into canonical planner/executor semantics;
- future C++ implementation can preserve operation IDs, digests, failures and canonical postconditions.

9. Existing architecture compatibility:
- generic 14-tool catalog unchanged;
- BlenderExecutionBoundary semantics unchanged;
- action_recovery semantics unchanged;
- SceneModel/mesh-health contracts unchanged;
- no new correction family is implied.

10. Implementation promotion gate:
- identify any hidden production semantic changes;
- identify any missing live evidence;
- identify any assertion that is only transport-level and therefore weaker than claimed;
- identify any missing adversarial refusal path.

## Important repository facts

The current correction executor defines four executable correction types: REMOVE_DUPLICATE_FACE, REMOVE_DEGENERATE_FACE, REPAIR_FACE_WINDING, and REPAIR_MERGE_VERTEX.

The generic Blender schema contains 14 object/scene tools and no mesh/face editing tools.

The generic execution boundary has execute, execute_verified, execute_with_receipt, and execute_with_persistence. The latter is persistence-oriented and must not become the correction bridge.

The correction executor uses injected mutation and extraction seams in production; real Blender mutation/extraction is currently exercised by the live test harnesses.

Wave 14 and Wave 15 already established bounded material-slot evidence and live correction postconditions. The red-team should distinguish canonical claims from raw test-only evidence.

## Required output

Return:

- verdict;
- blockers, if any;
- minor findings;
- exact design sections requiring change;
- explicit statement whether implementation may proceed to the deterministic implementation phase.

No implementation changes are requested by this task.