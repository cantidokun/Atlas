# M10 Remediation — Defect D v2 (sequence playback range)

## Live status
- **Defect A: PASS live** · **Defect B: PASS live** · **Defect C: PASS live**
- **Defect D v1 (Python transmission): PASS live** — start_frame/end_frame are
  actually transmitted to Unreal.
- **Defect D v2 (MRQ shot range): REMEDIATED** — the authorized inclusive range is
  now applied to the sequence playback range (the source MRQ enumerates shots from).
- **Verifier remains strict; a 23-frame result still fails.**
- S1 requires another FRESH live rerun after merge; S2–S8 remain NOT EXECUTED.

## Defect D v1 recap
`submit_render` (Python) now transmits `start_frame`/`end_frame`; C++ applied the
authorized inclusive `[start, end]` to the MRQ **output/render setting**
(`bUseCustomPlaybackRange`, `CustomStartFrame`, `CustomEndFrame`). This was
necessary but INSUFFICIENT.

## Defect D v2 root cause (engine path, evidence-confirmed live)

Live MRQ log, every run:
```
LogMovieRenderPipeline: Registering range: [800,19200) (AtlasSequencerFixtureSequence)
```
That `[800,19200)` is the SEQUENCE playback range in 80-tick units (800/80=10 to
19200/80=240), i.e. the source sequence's playback range — NOT the MRQ output
setting's custom range. MRQ enumerates the RENDER SHOT FRAMES from the SEQUENCE
playback range. Setting `bUseCustomPlaybackRange`/`CustomStartFrame/EndFrame` on the
output setting did not change shot enumeration, so an authorized 1..24 still
rendered frames 1..23.

### Engine path traced
```
submit_render args {start_frame, end_frame}
  -> C++ SubmitRender parses AtlasStartFrame/AtlasEndFrame
  -> transient MRQ config: output setting CustomStart/CustomEnd (v1, retained)
  -> NEW: duplicate source ULevelSequence into transient, set playback range
          SetPlaybackRange(AtlasStartFrame, AtlasEndFrame - AtlasStartFrame + 1)
  -> Job->SetSequence(transient duplicate)   <-- the sequence MRQ enumerates shots from
  -> MRQ shot enumeration now covers inclusive [start,end] = end-start+1 frames
  -> output_manifest -> expected_output_spec -> verifier (strict)
```

Which sequence object owns the playback range:
- The MRQ job's sequence is `Job->SetSequence(SequenceAssetPath)`, i.e. the source
  `ULevelSequence` asset (`/Game/AtlasTest/AtlasSequencerFixtureSequence`).
- Its playback range is owned by `UMovieScene::GetPlaybackRange()`/`SetPlaybackRange`.
- `SetPlaybackRange(lower, size)` takes a SIZE; the range upper bound is EXCLUSIVE.
  To render INCLUSIVE frames `[start, end]` the required size is `end - start + 1`
  (upper bound `end + 1`). This is the exact off-by-one.

Which MRQ setting v1 modified: the OUTPUT setting custom playback range. MRQ does
NOT use it for shot enumeration. Which setting MRQ actually uses: the SEQUENCE
playback range.

## Fix (engine boundary — isolation-safe)

In `SubmitRender`, when Atlas supplies `start_frame`/`end_frame`:
1. Duplicate the source `ULevelSequence` into `GetTransientPackage()` with a unique
   per-job name (`AtlasSeq_<atlas_job_id>_<start>_<end>`).
2. `SetPlaybackRange(AtlasStartFrame, AtlasEndFrame - AtlasStartFrame + 1)` on the
   transient copy's MovieScene (inclusive coverage of `end`).
3. `Job->SetSequence(FSoftObjectPath(TransientSequence))` so MRQ enumerates shots
   from the isolated transient sequence.
4. Retain the v1 output-setting range (independently reported).
5. Also fixed the related `SetSequencerPlaybackRange` op's identical exclusive-
   upper-bound off-by-one (`EndFrame - StartFrame + 1`).

### Isolation / non-mutation analysis (task 4)
- The mutation operates ONLY on a `DuplicateObject<ULevelSequence>(...,
  GetTransientPackage())` transient object.
- The source `ULevelSequence` asset (`/Game/...Sequence`) is never mutated, saved,
  or `Modify()`d. The global fixture `ALevelSequenceActor`/`AtlasSequencerFixture
  Sequence` asset is untouched.
- The transient sequence is per-job (unique name keyed on the unique Atlas job id),
  so subsequent jobs cannot inherit a previous job's playback range.
- `SetSequencerPlaybackRange` (external op) now sets the inclusive range on the
  world actor's sequence with `Modify()` — consistent and correct, and not on the
  S1 render path (which uses the transient duplicate).

Requirements honored: Atlas remains authoritative; Unreal executes exactly the
authorized topology; no silent clamping; no synthetic frame; verifier strict;
output isolation / manifest hashing / HMAC / attempt_ordinal / Defect A/B/C fixes
preserved.

## Regression coverage (tests/m10/test_m10_defect_d2_sequence_range.py, 8)
1. authorized 1..24 = 24 frames (inclusive);
2. inclusive→SetPlaybackRange conversion: size = end-start+1, upper bound end+1,
   24 frames enumerated;
3. submit transmits 1..24;
4. source sequence asset NOT mutated (transient duplicate used, never `Modify()`
   on the loaded asset);
5. transient sequence is per-job unique (keyed on atlas_job_id);
6. 24-frame result passes the verifier;
7. 23-frame result STILL fails (verifier not weakened);
8. verifier retains strict count (no relaxation) + adjacent SetSequencerPlaybackRange
   off-by-one is fixed.

## Related-range audit (task 6)
- `SubmitRender` output-setting range (v1): retained, independently reported.
- `SubmitRender` sequence-playback range (v2): FIXED (the shot-enumeration source).
- `configure_render`: sets config CustomStart/End — config objective, not a render
  run; already inclusive; not on the S1 path.
- `SetSequencerPlaybackRange`: FIXED (same exclusive-upper-bound off-by-one).
- `FindSequencerPlaybackRange`/`InspectSequencerState`: read-only inspection.
- No other path reinterprets the authorized frame topology.

## UBT result
`UBT_EXIT_CODE=0` on the FINAL working tree (AtlasTransportServer.cpp compiled with
the transient-sequence + SetSequencerPlaybackRange fixes).

## Regression (final tree)
- tests/m10: 39
- tests/m6 79, m7 59, m8 19, m9 34, submission/receipt/production suites green
- full `pytest -m "not integration"`: 1180 passed

## Explicit statements
- NO live Unreal scenario executed during this remediation.
- NO UnrealEditor launch; NO Blender; NO workflow/action-runner tests.
- Verifier remains strict; 23 frames still fails; expected_output_spec unchanged.
- Successful 23-frame renders, FINISHED journals, HMAC, manifests, and the
  declared-24/actual-23 forensics are preserved (live_run_state/s1_final/,
  s1_final2/) and treated as valuable diagnostic evidence.
- S1 requires a FRESH live rerun after merge; S2–S8 remain NOT EXECUTED.