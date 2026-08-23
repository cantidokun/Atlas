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

**MAJOR MILESTONE PASSED: generalized Blender corrective runtime live interruption/replanning proof.**

Atlas has now proven that the generalized production corrective runtime can execute against real Blender, retain execution receipts, recover from an externally injected scene-state change, replan from fresh evidence, and independently verify final convergence.

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

## Proven live Blender behavior

Atlas now has live proof for:

1. **Object rotation** — authorized mutation, persistence, fresh independent inspection, invariant verification, and receipt validation.
2. **Marker creation** — conditional authorized creation, persistence, fresh scene inspection, independent membership verification, and receipt validation.
3. **Generalized corrective recovery** — real Blender execution across multiple properties, injected external scene change, fresh-state replanning, protected corrective execution, receipt retention, and final independent convergence.

The generalized corrective runtime is no longer dependent on the earlier specialized multi-step corrective demo.

## Next development gate

The next objective is to turn this proven generalized corrective runtime into a reusable production-facing autonomous Blender task runtime capable of composing different authorized operations while preserving:

- fresh observation before each decision;
- explicit authorization;
- capability restrictions;
- exact action/receipt binding;
- normalized execution results;
- independent post-action verification;
- fail-closed completion and step budgets;
- interruption recovery and continuation/resume.

Do not rebuild lifecycle orchestration for individual tools. Extend the declarative task contract and shared runtime.

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

## Verification discipline

Historical CI/live results describe earlier commits unless explicitly associated with the current branch/commit. Focused tests are regression evidence; live Blender claims require actual Windows/Blender runner output.

## Development path

1. generalize the proven corrective runtime into reusable production task composition;
2. implement continuation/resume across multi-task Blender operations;
3. advance Digital Twin identity/revision and photogrammetry intake contracts;
4. later integrate Unreal production workflows.

Photogrammetry remains upstream of Blender. Atlas is exclusively concerned with soccer-field-related digital twins; Blender receives the upstream reconstruction for analysis, cleanup, correction, and preparation.

See `ATLAS_HANDOFF_CURRENT.md` for the authoritative resume point and `DEVELOPMENT_LOG.md` for chronological progress.
