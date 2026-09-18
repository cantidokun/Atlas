# Unreal Agent — Shot-Level Production Continuity Design Review

**Date:** September 17, 2026  
**Branch:** `reconcile/unreal-autonomy-origin-20c6d10`

## Review result

**CLEAR WITH MINOR FINDINGS** for a narrow shot-level production-continuity implementation.

The existing architecture can express the required continuity invariants without a generic workflow engine, a new transport primitive, a second authorization authority, or an Atlas-side entity cache. The implementation seam should remain a **plan-level continuity contract plus existing production/render workflows**, not another orchestration layer.

## Existing contracts already cover

### Scene/range continuity

`UnrealProductionSpec` already requires the production `start_frame` / `end_frame` to match the `UnrealRenderConfig` range. This prevents the authorized production plan from carrying two different frame ranges before execution.

The composed production plan contains the Sequencer write/verify pair followed later by render configuration write/verify. The existing executor preserves the established WRITE -> VERIFY rule.

### Render configuration continuity

The render configuration operation is authorized as part of the production plan and independently verifies fresh Unreal render-state evidence. The authoritative values include resolution, frame range, output directory, and output format.

### Render-job identity continuity

The render submission already produces a job identity, and subsequent job verification can bind observations to the expected job ID. The final receipt is issued only from verified completed `inspect_render_job` evidence and binds the exact job ID, sequence asset path, and evidence digest.

### Failure/recovery continuity

Production execution remains fail-closed. A later mutation/verification failure preserves completed evidence and recovery requires explicit reassessment and fresh authorization rather than replaying the failed authorization.

## Findings requiring the next implementation slice

### 1. Sequence asset path is not part of the production plan

`sequence_asset_path` currently enters at `UnrealProductionWorkflow.run()` and is then used to construct the separate render-submission plan. It is therefore validated and authorized at the render boundary, but it is not one of the values represented in the heterogeneous production plan itself.

The next seam should bind the sequence path to the already-authorized production intent without creating another authority. The preferred approach is to make the continuity contract carry the exact sequence asset path and have the workflow reject any submission path that differs from that authorized value.

### 2. Final job evidence does not yet expose the submitted frame range

The Unreal transport's render-job state already persists and returns `sequence_asset_path`, `output_directory`, `output_format`, status, job identity, and output files. It does not currently persist the effective start/end frame range inside the render-job registry.

That means Atlas can verify job identity and output location/format continuity, but it cannot yet prove from the final job evidence that the submitted job covered exactly the authorized frame range.

The next implementation slice should extend the existing render-job evidence with the effective frame range captured at submission time. This is an evidence-contract extension, not a new transport primitive.

### 3. Artifact completeness is stronger than non-empty output but weaker than frame coverage

Current completion verification requires output files and validates absolute-path existence/non-zero size where the transport provides absolute paths. This proves that artifacts exist, but it does not yet prove that an image-sequence job produced the complete authorized frame topology.

For the current PNG image-sequence boundary, the deterministic rule should be:

```text
expected_frame_count = end_frame - start_frame + 1
observed_output_files = unique output files
observed_output_files count == expected_frame_count
```

The implementation must not generalize this rule to other output formats without an explicit format-specific contract.

## Frozen invariants

1. Sequence asset path is exact and authorization-bound.
2. Sequencer start/end frames and render start/end frames remain identical.
3. Final render-job evidence must report the same sequence asset path as authorized.
4. Final render-job evidence must report the effective submitted frame range.
5. Final render-job evidence must report the effective output directory and format.
6. PNG image-sequence completion must prove expected frame-count coverage in addition to non-empty files.
7. Job ID remains exact and authorization-bound as already established.
8. Evidence remains fresh; no echoed write arguments may substitute for observed engine state.
9. Recovery remains fail-closed and requires fresh evidence plus new authorization.
10. No new transport operation, generic workflow engine, entity cache, or distributed-render architecture is introduced.

## Deterministic matrix before live UE validation

The next deterministic gate must cover:

- matching sequence path passes;
- sequence path mismatch fails before render submission;
- matching Sequencer/render ranges pass;
- mismatched ranges fail before render submission;
- final job identity mismatch fails;
- final sequence path mismatch fails;
- final frame-range mismatch fails;
- final output-directory or format mismatch fails;
- PNG incomplete frame-count fails;
- PNG complete frame-count passes;
- production failure blocks submission;
- recovery remains explicit and authorization-bound.

## Live gate entry condition

Only after this deterministic matrix is green should the UE 5.6.1 live production-continuity integration be run.

The live gate should use the existing Named Pipe transport and the real MRQ path. It should leave the Unreal fixture restored byte-for-byte and preserve the existing receipt persistence checks.
