# M12.5 v1 — Live Promotion Gate

## Purpose

This gate is the live evidence rung for M12.5 v1 after the deterministic verifier is green.

It uses the existing UE 5.6.1 State Extraction transport and the existing M5
`verify_render_job_evidence()` authority. It does not change either authority.

## Required evidence

### Non-render semantic observation

The gate runs the approved `AtlasExtractionFixture` session and feeds the real
transport request/response pair directly to M12.5.

The expected v1 result is deliberately fail-closed:

- `semantic_state = UNKNOWN`
- `overall_state = NOT_ESTABLISHED`
- `failure_codes` include `EXPECTED_VALUE_UNAVAILABLE`
- no positive `SATISFIED` semantic result
- evidence trust remains `TRANSPORT_CORRELATED`

The live report records deterministic repetition, result immutability, transport
correlation failure, session-identity failure, schema-revision failure,
conflicting-observation refusal, scope divergence, and the explicitly
**NOT DETECTABLE** stale-payload/current-envelope limitation.

### Render composition

The gate uses the existing `UnrealRenderSubmissionService` only as a test-harness
way to produce a real M5 render job, with `receipt_store=None`. M5
`verify_render_job_evidence()` independently verifies the completed render.

M12.5 then consumes that verified evidence and must still report:

- `twin_agreement = ENFORCED`
- `config_digest_agreement = ENFORCED`
- `request_digest_agreement = NOT_ESTABLISHED`
- `sequence_agreement = NOT_ESTABLISHED`
- `artifact_asset_identity = UNKNOWN`
- `render_state != VERIFIED`
- `overall_state != SATISFIED`
- render evidence trust = `DURABLE_RECORD_BACKED`

The gate never issues an M12.5 receipt and does not use the M12.5 verifier as a
substitute for M5 artifact verification.

Controls that depend on upstream capabilities that do not exist in v1 (Q10
catalog resolution, typed sequence binding, semantic expectation authority) are
recorded as `NOT PROVEN`, never as passes.

## Workflow

The dedicated workflow is restricted to the `m12-5-live-promotion-gate` PR branch,
checks out the exact PR head, starts the approved UE fixture session, runs the
existing State Extraction live gate, then runs the M12.5 live gate. It uploads the
JSON evidence and Unreal logs as the promotion record.
