# Atlas U1 Mock Validation Closeout — September 29, 2026 UTC

> MOCK TWIN VALIDATED. The synthetic U1 validation track is complete and frozen. This is the restart/closeout surface for the September 28–29 session.
>
> The mock validates the portable read-only extraction mechanism and the evidence workflow under isolated Unreal processes. It does not establish U1 production authority and does not provide a general cross-project security guarantee.

## Exact repository state

- PR #146 functional merge: 8f601184e62da2362ec38c948e61b7ff8058f95b.
- Latest documentation checkpoint before this closeout: b15efe1e4afe33f6ca557c6db977be8feb996797.
- No production U1 expectation values, REV10, R25, or R2-B production implementation were changed by this validation closeout.

## Mock validation result

STATUS: MOCK TWIN VALIDATED

Clean fixture:
C:\Users\Gavin's PC\Desktop\AtlasU1MockTwin_CleanValidation\AtlasU1MockTwin.uproject

Positive evidence:
- Actor extraction passed Atlas validation.
- Saved canonical actor response SHA-256: 16a8f89a990bfdb9eb963c9f501d6f096289eae7897ddfd4f7e9424248fdd141.
- Sequencer extraction passed Atlas validation and its canonical-byte hash independently matched the recorded digest.
- Direct LevelSequence inspection found two camera possessables, MockCamera_Main and MockCamera_Wide, both CineCameraActor; one camera-cut track; one camera-cut section spanning frames 100–240 bound to MockCamera_Main. CAM_WIDE is not claimed to participate in a cut section.

Isolation and case evidence:
- Earlier invalid same-process results were superseded by fresh isolated runs that verified requested map -> actual editor world -> extraction response/session identity.
- NegativeCamera produced the intended class deviation and passed the extraction/validator path; canonical response digest: 28137266324cdb7ecd0b8d6a2519ccc776d0f307283147b5ed0a9c75ae1959c7.
- MissingCamera, MissingSequence, UntaggedExpected, ForeignId, IncompleteScope and ForeignMap produced identity-checked recorded refusals where applicable.
- UnsupportedClass and WrongClass extracted successfully and passed observation validation; these are extraction-behavior evidence, not semantic-policy verdicts.
- A distinct Project-B foreign-project control was run in a fresh process. The plugin reported a distinct .uproject project_identity, Atlas validation passed, and the canonical digest matched an independent recomputation.
- The ForeignMap case also records an observed same-project all-ID refusal, ERR_EXTRACTION_ENTITY_TAG_CONFLICT, on a map carrying conflicting atlas_entity bindings. That is an observed result, not a semantic-policy conclusion.

Process and visual evidence:
- Final selected A-H validation runs completed without reproducing the earlier crash/231 combination.
- CreateNamedPipe error 231 remains classified only as observed pipe contention in the affected earlier run; crash causality was not established.
- The accepted visual capture came from a normal GUI Unreal Editor with real rendering, not -nullrhi; it showed the field/stadium scene rather than only the Outliner.
- Named-pipe startup/shutdown and editor scripting closed cleanly in the accepted runs.

Independent final review:
- Review bundle SHA-256: eacdeba5cfec9e8fa4af486e8ea0aaaa8f617bfbf7c43f5da92bd17067cc0079.
- GLM exact-state review: CLEAR.
- GPT-SOL-6 exact-state review: CLEAR WITH MINOR FINDINGS, blockers none.
- Remaining findings were bounded/documentation coverage limitations; no blocker remained.

## Frozen M12.6 state

R2-A:
- Frozen normative authority: R25.
- R25 SHA-256: 8f9cccc6c59635a554cc63f200c719d80c09dce0372e13715c83aee1809ae1c8.
- R2-A implementation: 7b591445d1a11e0ae181330fafaf0956d6cebdbb.
- PR #143 merge: e9a572c2104153285b1139d7dc09d1e9acd479ac.

R2-B:
- Frozen external normative baseline: REV10.
- REV10 SHA-256: 5d2409cf2ee0c15e35f73ecbae59ab2e03ddbd70abdb3f8c5e4dfc1d9b0d452f.
- REV10 declaration self-digest: d9e014e5631471bfd37309bdccdaa602fef2797012e17b4a181488cdb3f645d0.
- Size: 254,816 bytes / 2,155 lines.
- Fresh exact-SHA GLM: CLEAR.
- Fresh exact-SHA GPT-SOL-6: CLEAR.
- R2-B implementation remains NOT AUTHORIZED because U1/U7 operational evidence and the required human gate remain outstanding.
- Do not create REV11 unless a genuinely new normative blocker is independently established.
- PR #142 remains historical/open/draft/blocked and must not be used as an implementation base.

## Production boundary and next restart point

U1 PRODUCTION AUTHORITY: NOT ESTABLISHED.

The mock track is frozen. Do not spend the next session making the mock more realistic or creating another mock project.

Next work is the real production U1 evidence path:
1. Obtain or identify the actual production .uproject and the reviewed U1 target/expectation population required by REV10.
2. Load the real project with the portable read-only plugin only; do not use the mock as a source of production expected values.
3. Capture exact session/project/world identity and the real actor/sequencer extraction responses.
4. Recompute canonical hashes independently and preserve raw evidence.
5. Review the real evidence against REV10 authority and identity conditions before any production expectation registry population or R2-B implementation.
6. Keep U7 deployment/store-custody evidence separate; mock evidence is not U7 evidence.

Strict prohibitions:
- Do not populate planning/m12/expectation.py from mock observations.
- Do not modify REV10 or R25.
- Do not modify or revive PR #142.
- Do not begin R2-B production implementation.
- Do not reopen Blender, Temporal, M11, or unrelated Unreal history.
- Do not create another mock project unless a separately reviewed requirement makes it necessary.

## Restart surfaces

Read in this order:
1. ATLAS_HANDOFF_CURRENT.md
2. UNREAL_AGENT_HANDOFF_CURRENT.md
3. ATLAS_HANDOFF_CONTEXT.txt
4. ATLAS_HANDOFF_2026-09-29_U1_MOCK_VALIDATION_CLOSEOUT.md

Then resume with real-production U1 intake/evidence collection.
