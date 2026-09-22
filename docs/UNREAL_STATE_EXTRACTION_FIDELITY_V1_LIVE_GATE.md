# Unreal State Extraction Fidelity v1 — Live Gate Evidence (Phase E)

**Status:** LIVE GATE PASSED — one extractor, one live UE 5.6.1 editor session.
> **Current-state reconciliation — September 22, 2026:** the frozen contract is Revision 3.3 and PR #107's implementation is merged. The detailed Phase E session below is historical evidence; later fixture/review-hardening evidence in this same document records the current rung.

**Contract:** `docs/UNREAL_STATE_EXTRACTION_FIDELITY_V1_DESIGN.md`, Revision 3.3.
**Implementation:** merged by PR #107 at implementation head `805ab3cd5243386af93c0893a7e457b50fa1ea95`.

This document records what was actually executed, with the exact commands, and — equally
important — what the gate does **not** cover yet. Nothing here is a claim about code that
did not run.

---

## 1. Environment

| Item | Value |
|---|---|
| Engine | UE 5.6.1, `Build.version` 5 / 6 / Patch 1 / CL **44394996**, `++UE5+Release-5.6` |
| Editor binary | `Engine/Binaries/Win64/UnrealEditor-Cmd.exe` |
| Build tool | `Engine/Binaries/DotNET/UnrealBuildTool/UnrealBuildTool.exe` |
| Python (gate + tests) | 3.9.6 (`atlas-venv39`, pytest 8.4.2); the suite also passes on 3.12.14 |
| Project | `unreal/AtlasUnrealHarness/AtlasUnrealHarness.uproject` |
| Extractor sources | `unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Private/AtlasStateExtraction.{h,cpp}` |
| Python boundary | `planning/unreal_state_extraction/` |

## 2. Commands executed

```bash
# 1. Compile gate (the first C++ evidence for phases B/C)
"…/Engine/Binaries/DotNET/UnrealBuildTool/UnrealBuildTool.exe" AtlasUnrealHarnessEditor \
  Win64 Development -Project="…/AtlasUnrealHarness.uproject" -WaitMutex
# → Result: Succeeded  (AtlasStateExtraction.cpp compiled; UnrealEditor-AtlasUnrealTransport.dll linked)

# 2. First editor launch — creates and saves the non-partitioned fixture map
"…/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" "…/AtlasUnrealHarness.uproject" \
  -unattended -nosplash -nop4 -nullrhi -stdout -FullStdOutLogOutput

# 3. Second editor launch — opens that map as the editor world
"…/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" "…/AtlasUnrealHarness.uproject" \
  /Game/AtlasTest/Generated/AtlasRenderFixture \
  -unattended -nosplash -nop4 -nullrhi -stdout -FullStdOutLogOutput

# 4. Live gate
python -m tests.unreal_state_extraction_live_gate --json <report.json>
# → result: PASS, 27/27 checks
```

Editor log lines proving the live preconditions (`Saved/Logs/AtlasUnrealHarness.log`):

```text
LogAtlasTransport: Atlas transport server started successfully
Cmd: MAP LOAD FILE="…/Content/AtlasTest/Generated/AtlasRenderFixture.umap"
LogAtlasTransport: Atlas Unreal fixtures ready in world 'AtlasRenderFixture':
    field actor 'Actor_0', sequencer actor 'AtlasSequencerFixture'
```

## 3. Result

```text
result:          PASS   (27 of 27 checks)
digest:          17d87a257b604b5662a1b1f41ae1275027df30e43ea657a8e1cc5354b7337038
canonical bytes: 1796
```

Facts extracted from the live world:

| Field | Live value |
|---|---|
| `world.world_type` | `editor` |
| `world.selection_provenance` | `g_editor_editor_world_context` |
| `world.is_partitioned_world` | `false` |
| `world.engine_version` | `5.6.1` (**not** the legacy `"5.6"` literal — §3.1.2 proved live) |
| `world.engine_build_version` | `++UE5+Release-5.6-CL-44394996` |
| `world.level_scope.levels` | one `persistent` level, `/Game/AtlasTest/Generated/AtlasRenderFixture`, loaded + visible |
| `actors[0].entity_id` | `FIELD_SURFACE` (canonical representative) |
| `actors[0].actor_object_path` | `…AtlasRenderFixture:PersistentLevel.Actor_0` |
| `actors[0].actor_class` | `Actor` |
| `actors[0].transform` | `location_cm` = `0000000000000000` ×3, `rotation` w=`3ff0000000000000`, `scale` = `3ff0000000000000` ×3, `source_component_type` = `binary64` |
| `actors[0].editor_visibility` | `hidden_in_editor: false`, `derived_from_gis_editor: true`, `unrecorded_hidden_inputs: ["bEditable"]` |
| `actors[0].materials` | `[]` (the fixture actor has no mesh component) |
| `actors[0].omitted_material_components` | `{count: 0, classes: []}` |

Checks that passed (all with live data, not fixtures): value-tree validation through the
Python closed schema; engine identity sourced from the engine; world type, partition and
selection-provenance markers; a complete loaded-visible scope with exactly one persistent
level; canonical `entity_id`; 16-hex-digit binary64 transform scalars; **repeat extraction
byte-identical** (D5 live); **case-variant request (`field_surface`) producing the identical
digest** (D14 live); envelope-only session identity (six session keys present in the
envelope, none in the canonical bytes) (D8 live); `ERR_EXTRACTION_ENTITY_NOT_FOUND` for a
missing entity; `ERR_EXTRACTION_REQUEST_INVALID` for case-folded duplicate IDs.

## 4. A frozen restriction observed live

The first launch (default editor world) produced, end to end through the real transport:

```text
success:    false
error:      "World Partition worlds are refused in v1"
error_code: ERR_EXTRACTION_WORLD_PARTITION_UNSUPPORTED
```

UE 5.6's default new-world path is World Partition, so the contract refused it and no
payload was produced. This is the frozen v1 restriction (§3.2.1.2, cleared in Revision 3.1)
working exactly as written — reported here as evidence rather than worked around.

## 5. Not covered by this gate, and why

Recorded as gaps, not as passes. Each needs fixture content or an engine-side read that
this rung does not have:

| Gap | Why it is not live-covered |
|---|---|
| material slot / override / resolved / Nanite collision cases | the harness fixture actor is a bare `AActor` with no `UMeshComponent`; the material arms ran only in the Python and source-level tests |
| mesh-asset instability refusal (`ERR_EXTRACTION_MESH_ASSET_UNSTABLE`) | needs a component holding a runtime-generated mesh (e.g. a water body or a harness-built `RF_TextExportTransient` asset) |
| `ERR_EXTRACTION_UNSUPPORTED_COMPONENT_TYPE` | needs a registered non-mesh-family `UMeshComponent` on a tagged actor |
| compiling-mesh refusal | needs to catch an asset mid async compile |
| scope-change refusal (`ERR_EXTRACTION_SCOPE_CHANGED`) | needs a world with a streaming level that can be made unloaded between snapshot and re-query |
| request-order permutation (D3/D4 live) | needs at least two entity-tagged actors; the fixture has one |
| numbered-name cases (D15 live) | needs `atlas_entity:CAM`, `atlas_entity:CAM_1`, `atlas_entity:CAM_01` tags on real actors |
| signed-zero / quaternion-sign cases live | needs a fixture actor placed with a `-0.0` component and a negated quaternion |
| package-dirty invariance across the extraction call | would need an engine-side dirty-state read; the frozen transport exposes none, and adding one is new transport surface (§9.5/§10.2 keep the transport out of this change). The static half is covered by the forbidden-token and allowlist gates; the dynamic half remains an obligation for the next fixture rung |
| sequencer extraction (`extract_sequencer_state`) live | needs the entity-tagged `ALevelSequenceActor` of §11.2, which does not exist yet (the harness's sequencer fixture carries only the non-entity tag `atlas_sequencer_fixture`) |

## 6. Contract/engine mismatch encountered and how it was resolved

**`UWorld::PersistentLevel` is private in UE 5.6 with no public getter.** §3.2.1.4 requires
the persistent level in the scope, and the obvious accessor does not exist for external
modules (verified: `Engine/Classes/Engine/World.h:941` under `private:`; no
`GetPersistentLevel()` in `UWorld`).

Resolution (implementation-level, no rule weakened, no compatibility shim): the level is
identified by **identity** — the level whose package equals the world package, which is the
equivalence §4.4 itself states for a non-partitioned world — over the world's level list,
with a fail-closed arm (`ERR_EXTRACTION_LEVEL_SCOPE_INVALID`) if the equivalence does not
identify exactly one level. Arrival order is never used for the scope order, so §7.2's
prohibition on using that list as a *scope order* is respected; the source-level gate pins
the use to exactly one site and requires the canonical ordering to be present
(`tests/test_unreal_state_extraction_readonly_source.py`).

Any future engine revision that makes the persistent level reachable through a public
accessor should switch to that accessor; nothing else in the contract depends on the
identification method.

## 7. Reproducing the gate

1. Build the editor target (command 1 above).
2. Launch once without a map: the module creates and saves
   `Content/AtlasTest/Generated/AtlasRenderFixture.umap` (the generated artifact is not
   committed).
3. Relaunch with that map as the argument (command 3) and wait for
   `Atlas Unreal fixtures ready in world 'AtlasRenderFixture'` in the editor log.
4. Run the gate (command 4). `PASS` requires all 27 checks; the JSON report records every
   check individually so a partial pass cannot be mistaken for a pass.
5. Stop the editor. The gate never writes: it issues read operations only.

## 8. Later rungs — current session shape (fixture rung and review-hardening rung)

Sections 1-7 above record the Phase-E session exactly as it ran (27/27 checks, `/Game/AtlasTest/
Generated/AtlasRenderFixture`). Two later rungs changed how the extraction session is started and
what it must prove; this section is the current form, and the per-case evidence lives in
`docs/UNREAL_STATE_EXTRACTION_FIDELITY_V1_VALIDATION_MATRIX.md`.

Fixture provisioning is **opt-in** (independent review F-1):

```bash
# build
dotnet.exe "…/Engine/Binaries/DotNET/UnrealBuildTool/UnrealBuildTool.dll" \
  AtlasUnrealHarnessEditor Win64 Development -Project="…/AtlasUnrealHarness.uproject" -WaitMutex
# → Result: Succeeded

# ordinary start-up: provisions NOTHING and writes NOTHING (no fixture switch present)
"…/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" "…/AtlasUnrealHarness.uproject" \
  /Game/AtlasTest/Generated/AtlasExtractionFixture \
  -unattended -nosplash -nop4 -nullrhi -stdout -FullStdOutLogOutput
# → "Atlas extraction fixture provisioning disabled (no -AtlasExtractionFixture switch)"
# → no ATLAS_EXTRACTION_FIXTURE_STATUS line; committed fixture assets byte-identical afterwards

# extraction-fixture session: the only session that may provision or verify fixture content
"…/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" "…/AtlasUnrealHarness.uproject" \
  /Game/AtlasTest/Generated/AtlasExtractionFixture \
  -AtlasExtractionFixture -unattended -nosplash -nop4 -nullrhi -stdout -FullStdOutLogOutput \
  -ExecCmds="Automation RunTests Atlas.StateExtraction"
# → "Atlas extraction fixture content already exists (version 3); verifying it against the
#    fixture contract instead of rewriting it"
# → "ATLAS_EXTRACTION_FIXTURE_STATUS: OK version=3"      (exactly one such line)
# → 8 of 8 automation tests Success
# → committed fixture assets byte-identical afterwards (verified by SHA-256 before/after)

# transport gate (the session's log is also the fixture precondition's source)
python -m tests.unreal_state_extraction_live_gate --json <report.json> --automation-log <session log>
# → result: PASS — 13 PASS / 4 REFUSAL VERIFIED / 3 BLOCKED BY ENGINE/API LIMITATION /
#            6 NOT YET LIVE-COVERED, including fixture_status_precondition: PASS
#   positive_baseline digest 5160b6fa11c95d594b6d7262d00ffe742fbf51e996fdef27abc4e793613cc3a6
#   (1862 canonical bytes) — byte-identical to the Revision 3.3 session, so this rung changed no
#   successful extraction payload
```

The gate now has one **precondition**: the session log must carry
`ATLAS_EXTRACTION_FIXTURE_STATUS: OK version=<n>`. A session that was not started with
`-AtlasExtractionFixture` reports nothing, so the gate fails closed instead of running against
content nobody verified; a session whose committed content no longer matches the fixture contract
reports `FAILED …` with the exact difference and is likewise refused.

Two cases remain deliberately *not* live-covered in this rung and are recorded as such rather than
asserted: the payload bound (no fixture here can approach 1 MiB; it is proven in-process on a
constructed payload) and the fixture-integrity check itself (proven in-process, with the session
status line as the live precondition).
