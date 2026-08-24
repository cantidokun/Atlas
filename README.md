# Atlas

Atlas is an AI-assisted sports virtual-production and digital-twin platform. Photogrammetry is an upstream reconstruction capability; Blender receives the initial reconstruction for analysis, cleanup, correction, and preparation.

## Execution principle

```text
Qwen / AI agents
    -> reason + propose
Python / Atlas
    -> validate + authorize + execute + verify + recover
Blender
    -> controlled production execution
Independent Atlas verification
    -> authoritative completion decision
```

Qwen never receives direct Blender execution authority.

## Current Blender Agent status

**PROVEN MAJOR MILESTONE: generalized Blender corrective runtime live interruption/replanning proof.**

Atlas has proven that the generalized production corrective runtime can execute against real Blender, retain execution receipts, recover from an externally injected scene-state change, replan from fresh evidence, and independently verify final convergence.

The live gate reported:

```text
ATLAS GENERALIZED BLENDER CORRECTIVE RUNTIME GATE: PASS
receipts = 4
external_change_injected = true
```

Final independently observed state:

```text
Goal_Left_post
location = [1.0, 0.0, 0.0]
rotation = [0.0, 0.0, 45.0]

Goal_Right_post
location = [-1.0, 0.0, 0.0]
rotation = [0.0, 0.0, -45.0]
```

The generalized lifecycle is:

```text
fresh world evidence
 -> corrective planning
 -> explicit authorization
 -> protected Blender execution
 -> normalized result + immutable receipt
 -> fresh observation
 -> external change / interruption
 -> fresh replanning
 -> reauthorization
 -> corrective execution
 -> independent final verification
 -> completion
```

## Current development increment: authorization-bound live writes

The next production gate is being built around a shared authorization-bound Blender write path rather than bespoke lifecycle orchestration for individual tools.

Current target architecture:

```text
ActionSpec
 -> capability admission
 -> exact BlenderWriteAuthorization
 -> BlenderLiveWriteGate
 -> BlenderExecutionBoundary
 -> normalized verified result
 -> authorization-bound immutable receipt
 -> independent authoritative verification
 -> VERIFIED / BLOCKED
```

Current implementation includes:

- `planning/blender_capability_catalog.py` — explicit read/write capability classification and fail-closed unknown capabilities.
- `planning/blender_write_authorization.py` — exact-action authorization for scene-writing capabilities.
- `planning/blender_live_write_gate.py` — final authorization-bound write choke point.
- `planning/blender_live_write_result.py` — explicit `VERIFIED` versus `BLOCKED` outcome contract.
- `planning/blender_live_verification.py` — independent authoritative post-write verification helper.
- `planning/blender_execution_receipt.py` — immutable receipt with optional authorization binding.
- `planning/blender_execution_boundary.py` — raw, verified, receipt-bound, authorized-write, and corrective-replan execution APIs.

The live object-rotation path has also been moved onto the shared authorization-bound architecture. The newest implementation changes remain **not runner-validated**.

## Validation discipline

The latest complete reported full-suite result remains:

```text
589 passed / 18 failed
```

This is **not** a green branch baseline. No newer runner result has superseded it.

Earlier verified results include:

- **Test 313 passed** — earlier action-runner validation.
- **141 passed** — earlier focused suite baseline.
- Generalized Windows/Blender corrective-runtime gate: **PASS**, with 4 receipts and an injected external scene change followed by successful fresh-state replanning and recovery.

Live Blender claims must be backed by actual Windows/Blender runner output. Historical results describe the commits on which they were actually observed.

## Resume gate

The next coding step is to integrate `planning/blender_live_verification.py` into `BlenderLiveWriteGate` so that `VERIFIED` requires authoritative final-state confirmation, not merely successful executor output and receipt binding.

Then prove, in order:

1. authorized `move_object` -> actual Blender subprocess;
2. authoritative state matches -> `VERIFIED` + authorization-bound receipt;
3. executor reports success but authoritative state disagrees -> `BLOCKED`;
4. `BLOCKED` produces no receipt and prevents subsequent writes;
5. only then generalize the shared path to the remaining admitted write capabilities.

Do not weaken verification or create per-tool lifecycle orchestration to make tests pass.

## Authority and verification boundary

Qwen proposes; Atlas validates, authorizes, executes, tracks, verifies, and recovers. Blender is an execution target, never an authority.

```text
Qwen proposal
 -> task/evidence/action validation
 -> authoritative fresh evidence
 -> explicit authorization
 -> deterministic capability execution
 -> normalized result
 -> immutable execution receipt
 -> fresh independent evidence
 -> target verification / replan
 -> completion or conservative recovery
```

## Proven live Blender behavior

The generalized corrective runtime has live proof for:

1. **Object rotation** — authorized mutation, persistence, fresh independent inspection, invariant verification, and receipt validation.
2. **Marker creation** — conditional authorized creation, persistence, fresh scene inspection, independent membership verification, and receipt validation.
3. **Generalized corrective recovery** — real Blender execution across multiple properties, injected external scene change, fresh-state replanning, protected corrective execution, receipt retention, and final independent convergence.

These historical live proofs do not imply that the newest authorization/live-write branch is currently green.

## Development path

1. complete the authorization-bound live-write proof and adversarial `BLOCKED` proof;
2. generalize the proven corrective runtime into reusable production task composition;
3. implement continuation/resume across multi-task Blender operations;
4. advance Digital Twin identity/revision and photogrammetry intake contracts;
5. later integrate Unreal production workflows.

Photogrammetry remains upstream of Blender. Atlas is exclusively concerned with soccer-field-related digital twins; Blender receives the upstream reconstruction for analysis, cleanup, correction, and preparation.

See `ATLAS_HANDOFF_CURRENT.md` for the authoritative resume point and `DEVELOPMENT_LOG.md` for chronological progress.

## Current checkpoint

The current handoff records the exact architecture, files, known issues, validation baseline, runtime setup, and resume sequence. No new test result is claimed by this documentation update.
