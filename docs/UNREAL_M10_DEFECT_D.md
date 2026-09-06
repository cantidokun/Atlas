# M10 Remediation — Defect D (frame-count mismatch)

## Live status
- **Defect A: PASS live** · **Defect B: PASS live** · **Defect C: PASS live**
- **Defect D: now REMEDIATED** (was the only blocker to S1 completion). Fixed
  deterministically + UBT-compiled; requires ONE final live S1 rerun after merge.
- **S2–S8 remain NOT EXECUTED.**

## Defect D root cause (exact, from code trace + live observation)

### Observed live mismatch
- Authorized/declared `expected_output_spec`: `start_frame=1, end_frame=24`
  → authoritative `frame_count = 24` (inclusive of both bounds).
- Real UE 5.6 MRQ output: frames 1..23 → **23 files**.

### The two contributing facts (both production defects on the Atlas boundary)
1. **`UnrealRenderSubmissionService.submit_render` did NOT transmit
   `start_frame`/`end_frame` to Unreal.** `submit_arguments` carried entity_ids,
   atlas_job_id, sequence_asset_path, output_directory, config_digest,
   attempt_ordinal, attempt_nonce — but not the frame topology. So the
   Atlas-authorized scope never reached the engine.
2. **C++ `SubmitRender` never applied an authorized range to the MRQ job.**
   It built the job purely from the persisted `AtlasRenderConfig.uasset` + engine
   defaults. MRQ evaluated the effective range as a half-open bound (dropping the
   final frame), so declared end=24 produced frames 1..23. The engine had no
   explicit inclusive range instruction from Atlas.

The Atlas verifier is **authoritative** (`expected_count = exp_end - exp_start + 1`,
inclusive) and correctly rejected the 23-frame result (Case G, no receipt). The
defect was that Unreal was never told to render the exact authorized inclusive range.

## Exact before/after frame semantics

### Data path (before)
```
AtlasRenderJobRecord.expected_output_spec {start:1, end:24}  -> frame_count = 24
  -> submit_arguments: [frames NOT transmitted]
  -> SubmitRender: builds MRQ from persisted AtlasRenderConfig (declared 1..24)
  -> MRQ effective range: half-open -> renders frames 1..23 (23)
  -> output_manifest: 23 entries
  -> verifier: expected 24, got 23 -> FAIL closed (Case G, no receipt)
```

### Data path (after)
```
AtlasRenderJobRecord.expected_output_spec {start:1, end:24}  -> frame_count = 24
  -> submit_arguments: now includes start_frame=1, end_frame=24
  -> SubmitRender: parses them, applies INCLUSIVE [start, end] to MRQ
     (bUseCustomPlaybackRange=true, CustomStartFrame=start, CustomEndFrame=end)
  -> MRQ renders frames 1..24 (24)
  -> output_manifest: 24 entries
  -> verifier: expected 24, got 24 -> PASS
```

## Production fixes

1. **Python — `planning/unreal_render_submission.py`:** `submit_arguments` now carries
   `start_frame` and `end_frame` (from `expected_output_spec`). The authoritative
   frame topology reaches Unreal.
2. **C++ — `unreal/.../AtlasTransportServer.cpp` `SubmitRender`:** parses
   `start_frame`/`end_frame` from arguments; requires both-or-neither and integer,
   sane bounds; when present, applies `bUseCustomPlaybackRange=true`,
   `CustomStartFrame=start`, `CustomEndFrame=end` to the MRQ job's transient config
   (inclusive). Missing values keep engine defaults (backward compatible); Atlas now
   always sends them.

### Requirements honored
- Atlas authorization remains authoritative (frame_count = end-start+1).
- Unreal now renders the FULL authorized range.
- No synthetic frame counted; missing frames still fail verification.
- Atlas does NOT silently accept a shorter range.
- Evidence verifier NOT weakened (24 still required; 23 still fails).
- Output isolation, manifest hashing, HMAC, attempt_ordinal, and all Defect A/B/C
  fixes preserved.

## Regression coverage (tests/m10/test_m10_defect_d_frame_topology.py, 7)
1. authorized start/end values (1..24);
2. expected count = end - start + 1 = 24 (inclusive);
3. submit_render request carries start_frame=1, end_frame=24 (the transmit fix);
4. engine effective range is inclusive [start, end];
5. 24-frame render result passes the authoritative verifier;
6. **a 23-frame result STILL fails closed** (the live failure case; verifier not
   weakened);
7. verifier source retains the exact `expected_count = end - start + 1` and the
   strict `!=` count check (no relaxation).

## Adjacent frame-range audit
- `FindSequencerPlaybackRange` / `InspectSequencerState`: read-side inspection of
  the sequence playback range — not the MRQ output count; NOT the same defect.
- `SetSequencerPlaybackRange`: sets the sequencer fixture range; separate operation,
  not part of the S1 render-output path.
- `configure_render`: sets config CustomStart/CustomEnd from request args (16-17, 
  already inclusive) — but the S1 path never called configure_render; fixed by
  having submit_render apply the range itself.
- Conclusion: the MRQ render job config was the ONLY path determining the S1 output
  frame count and is now fixed. No other genuine instance of the defect.

## Why deterministic tests did not catch it
The M1–M9 submission tests exercised submit_render argument construction but never
verified MRQ's actual rendered frame count against the authorized range (the count
check requires a real engine render). The verifier tests used complete/consistent
manifests, so the count mismatch never surfaced. Only a real UE 5.6 render exposed
that the authorized range was never transmitted/applied.

## UBT result
`UBT_EXIT_CODE=0` — UnrealBuildTool build succeeded on the final tree with the
Defect D C++ change (AtlasTransportServer.cpp compiled).

## Regression (final tree)
- tests/m10: 31 (17 A/B-prior + 7 C + 7 D)
- tests/m6 79, m7 59, m8 19, m9 34, submission green
- full `pytest -m "not integration"`: 1172 passed

## Explicit statements
- Authorized frame topology (end - start + 1, inclusive) remains authoritative.
- The verifier was NOT weakened; a 23-frame result still fails.
- NO live Unreal scenario executed during remediation; NO editor launch; NO Blender;
  NO workflow/action-runner tests.
- Successful 23-frame render + FINISHED journal + HMAC + artifact evidence + the
  declared=24/actual=23 forensics are preserved (live_run_state/s1_final/) and
  treated as valuable diagnostic evidence.
- S1 requires ONE final live rerun after merge to confirm full Case B → FINALIZED →
  exactly one receipt; S2–S8 remain NOT EXECUTED.