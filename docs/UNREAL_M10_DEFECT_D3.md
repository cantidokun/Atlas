# M10 Remediation — Defect D v3 (MRQ output-frame range — exclusive upper)

## Live status
- **Defect A, B, C: PASS live.** **Defect D v1 (transmit): PASS live.**
- **Defect D v2 (sequence playback range): confirmed active (MRQ "Registering range:
  [1,25)") but INSUFFICIENT** — the render still produced 23 files.
- **Defect D v3: REMEDIATED** — fixes the actual MRQ output-frame enumeration range.
- **Verifier remains strict; 23 frames still fails.**
- S1 requires another FRESH live rerun after merge; S2–S8 remain NOT EXECUTED.

## Root cause (UE 5.6 source-verified — not guessed)

MRQ's output-frame enumeration does NOT come from the sequence playback range (the
D-v2 lever). It comes from `UMoviePipelinePrimaryConfig::GetEffectivePlaybackRange()`
(MoviePipelinePrimaryConfig.cpp:182-200):

```
if (OutputSettings->bUseCustomPlaybackRange) {
    StartTick = TransformTime(CustomStartFrame, DisplayRate, TickResolution).Floor()
    EndTick   = TransformTime(CustomEndFrame,   DisplayRate, TickResolution).Floor()
    return TRange<FFrameNumber>(StartTick, EndTick);   // [Inclusive, Exclusive)
}
return InSequence->GetMovieScene()->GetPlaybackRange();
```

and `MoviePipelineTiming.cpp` (line 698) stops the output loop BEFORE producing when
`CurrentTickInRoot >= TotalOutputRangeRoot.GetUpperBoundValue()`. Therefore the
number of output frames MRQ produces is exactly:

```
CustomEndFrame - CustomStartFrame   (half-open [start, end))
```

### Why prior fixes failed
- **D-v1** set `CustomStartFrame=1, CustomEndFrame=24` → `24 - 1 = 23` frames
  (off-by-one: one-fewer than the verifier's inclusive `end-start+1 = 24`).
- **D-v2** set the transient SEQUENCE playback range to `[1,25)`, but
  `GetEffectivePlaybackRange` IGNORES the sequence range when
  `bUseCustomPlaybackRange` is set. MRQ logged `[1,25)` from the "Transient" shot
  (proving a sequence object with that range existed) but enumerated output frames
  from the unchanged output setting `[1,24)` → still 23.

### D-v3 fix (narrowest production boundary)
For an Atlas-authorized INCLUSIVE `[start_frame, end_frame]` (verifier count =
`end_frame - start_frame + 1`), set the output setting's custom range to the
**exclusive upper bound**:

```
CustomStartFrame = start_frame
CustomEndFrame   = end_frame + 1     // exclusive upper => end-start+1 output frames
```

So for the standard S1 (1..24): `CustomStartFrame=1, CustomEndFrame=25` →
`25 - 1 = 24` files = frames 1..24. The verifier's authoritative `24` is satisfied.

Isolation preserved: the modified output setting lives on `TransientConfig`, a
`DuplicateObject` of the shared `AtlasConfig`; the shared/source sequence asset is
NEVER mutated. Per-job isolation holds (transient per job).

## Exact before/after frame/time-domain behavior

| | D-v1 (bug) | D-v2 (insufficient) | D-v3 (fix) |
|---|---|---|---|
| output CustomStartFrame | 1 | 1 | 1 |
| output CustomEndFrame | 24 | 24 | **25** |
| MRQ GetEffectivePlaybackRange | [1,24) | [1,24) (seq ignored) | **[1,25)** |
| output frames produced | 23 | 23 | **24** |
| verifier (frame_count=24) | FAIL | FAIL | **PASS** |

Transmit of start/end (D v1 fix, Python) is retained and correct.

## Regression coverage
- `tests/m10/test_m10_defect_d2_sequence_range.py` (8): updated to assert the D-v3
  output-setting fix (CustomEndFrame = end+1), source-asset non-mutation, per-job
  isolation, 24 passes / 23 fails, verifier strict.
- `tests/m10/test_m10_defect_d3_output_range.py` (9): exact half-open arithmetic
  (v1→23, v3→24), authorized 1..24 requires CustomEnd=25, verifier expected count
  stays end-start+1, 24 passes, 23 still fails, verifier no-relaxation, C++ fix
  present, no residual v1 bug, per-job isolation preserved.

## UBT result
`UBT_EXIT_CODE=0` on the FINAL tree (AtlasTransportServer.cpp compiled with the D-v3
output-range fix).

## Regression (final tree)
- tests/m10: 48
- tests/m6 79, m7 59, m8 19, m9 34, submission/receipt/production suites green
- full `pytest -m "not integration"`: 1189 passed

## Explicit statements
- NO live Unreal scenario executed during this remediation.
- NO UnrealEditor launch; NO Blender; NO workflow/action-runner tests.
- Verifier remains STRICT (frame_count = end-start+1); a 23-frame result still fails;
  expected_output_spec unchanged.
- All prior forensics preserved (s1_final, s1_final2, s1_final3; 23-frame runs,
  journals, HMAC, MRQ logs) — the 23-frame runs are diagnostic evidence.
- S1 requires ANOTHER fresh live rerun after merge; S2–S8 remain NOT EXECUTED.