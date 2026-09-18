# Unreal State Extraction Fidelity v1 — fixture / validation rung

Design source: `docs/UNREAL_STATE_EXTRACTION_FIDELITY_V1_DESIGN.md` (Revision 3.1), frozen at
`54697e501a917f20a815c187337044938385e81c`. This document reports the implementation rung
that builds dedicated positive extraction fixtures and turns the previously untested
state-space branches into evidence. It is not a design revision and it is not a clearance.

* Design branch: `feat/unreal-state-extraction-fidelity-v1-design` (documentation only, unchanged).
* Implementation branch: `feat/unreal-state-extraction-fidelity-v1-implementation`.
* Engine: Unreal Engine 5.6.1, build changelist `44394996`, `-nullrhi` unattended editor sessions.
* Live gate artefact: `%LOCALAPPDATA%\Temp\atlas-extraction-gate-final.json`.

## 1. How the evidence was produced

    # 1. build
    UnrealBuildTool AtlasUnrealHarnessEditor Win64 Development -Project=<uproject> -WaitMutex

    # 2. generate the fixture content (any session; the provisioner is idempotent)
    #    the fixture ticker writes the map, the sublevel and the sequence assets once
    UnrealEditor-Cmd.exe <uproject> -unattended -nosplash -nop4 -nullrhi -stdout

    # 3. gate session: fixture map open, in-process automation tests requested
    UnrealEditor-Cmd.exe <uproject> /Game/AtlasTest/Generated/AtlasExtractionFixture \
        -unattended -nosplash -nop4 -nullrhi -stdout -FullStdOutLogOutput \
        -ExecCmds="Automation RunTests Atlas.StateExtraction"

    # 4. transport gate against the running editor, folding in the in-process results
    python -m tests.unreal_state_extraction_live_gate \
        --json <report.json> --automation-log <session log>

Regeneration is explicit: the generated content lives in
`Content/AtlasTest/Generated/AtlasExtraction*` and is deleted to regenerate; the provisioner
records its content version so a stale fixture is a visible instruction rather than a silent
difference.

Evidence classes used below, kept strictly apart:

* **LIVE TRANSPORT** — a value tree produced by the real engine over the Atlas transport pipe.
* **LIVE IN-PROCESS** — a real-engine call through the extractor API inside a UE automation
  test (used where the transport cannot induce the state, e.g. the scope-change seam).
* **PYTHON FORCED** — the Python contract boundary against the closed schema and vectors.
* **SOURCE GATE** — a source-level assertion (forbidden tokens, accessor allow-lists, closure).

Source-tested is never reported as live-verified below.

## 2. Fixture inventory

Saved, non-partitioned map `/Game/AtlasTest/Generated/AtlasExtractionFixture`:

| entity tag | actor / component shape | arm |
| --- | --- | --- |
| `IMPL_PERM_A`, `IMPL_PERM_B` | `AStaticMeshActor` (cube, sphere) | request-order permutation |
| `case_lower`, `CASE_UPPER`, `CaseVariantBound` | bare actors | case folding to one FName binding |
| `CAM`, `CAM_1`, `CAM_01` | bare actors | numbered identity classes |
| `IMPL_PARENT_NONE` | bare actor | parent `none` |
| `IMPL_PARENT_UNBOUND` | attached to an untagged actor | parent `unbound` |
| `IMPL_PARENT_BOUND` | attached to `IMPL_PERM_A` | parent `bound` |
| `IMPL_MATERIAL_OVERRIDE_A` | `AStaticMeshActor` (cube) + second mesh component | override ≠ asset slot, two assignment states on one actor |
| `IMPL_MATERIAL_OVERRIDE_B` | `AStaticMeshActor` (sphere) | assignment collision across actors |
| `IMPL_OMITTED` | `ADecalActor` | omitted-primitive inventory |
| `IMPL_NULL_SKINNED` | `ASkeletalMeshActor`, no skinned asset | skinned family, null-mesh state |
| `IMPL_UNSUPPORTED_COMPONENT` | registered `UHeterogeneousVolumeComponent` | unsupported-family refusal |
| `IMPL_SIGNED_ZERO` | `-0.0` on relative location X and relative scale X | signed-zero source facts |
| `IMPL_Q_POS`, `IMPL_Q_NEG` | `+q` / `-q` of the same 90° Z rotation | quaternion sign |
| `IMPL_SEQUENCE_VALID` | `ALevelSequenceActor` + saved sequence | sequencer extraction |
| `IMPL_SEQUENCE_DEGENERATE` | same, `[0,0)` range | degenerate-range refusal |
| `IMPL_SEQUENCE_BAD_RATE` | same, tick resolution `0/1` | invalid-rate refusal |
| untagged parent, untagged control actor | bare actors | negative controls |

Saved sequence assets: `AtlasExtractionSequenceValid`, `AtlasExtractionSequenceDegenerate`,
`AtlasExtractionSequenceBadRate`. Saved sublevel: `AtlasExtractionSublevel`.

Per-session runtime probes (cannot be saved by construction): a loaded, visible dynamic
streaming level created from the sublevel (the second scope level the scope-change seam needs)
and `IMPL_RUNTIME_MESH`, an actor whose mesh is a runtime-generated `UStaticMesh`
(`RF_TextExportTransient | RF_NonPIEDuplicateTransient`, outered to the actor) — the shape a
shipped water body has.

Legacy fixtures untouched: the render fixture, the quarantined sequencer integration fixture
and the harness transport fixtures keep their own content and code. A Python test asserts the
new fixture source never references them.

## 3. Validation matrix

### 3.1 PASS

| contract requirement | evidence (class) | result | remaining gap |
| --- | --- | --- | --- |
| Actor extraction of a tagged entity yields a schema-valid tree | LIVE TRANSPORT: digest `5160b6fa11c95d594b6d7262d00ffe742fbf51e996fdef27abc4e793613cc3a6`, 1862 canonical bytes, engine `5.6.1` / `++UE5+Release-5.6-CL-44394996` | PASS | none |
| Deterministic repeated extraction (D5) | LIVE TRANSPORT: repeat digest identical to the first | PASS | none |
| Engine identity sourced from the engine, no legacy literal (§3.1.2) | LIVE TRANSPORT: `engine_version` ≠ `"5.6"` | PASS | none |
| Authoritative world selection (§4.4) | LIVE TRANSPORT: `selection_provenance = g_editor_editor_world_context`, `world_type = editor`, `is_partitioned_world = false` | PASS | none |
| Complete loaded/visible scope recorded (§3.2.1) | LIVE TRANSPORT + LIVE IN-PROCESS (the pre-state assertion proves a two-level scope when the runtime probe level is present: persistent + streaming) | PASS | see note (a) |
| Request-order permutation invariance (§7.4 D3) | LIVE TRANSPORT: `[A,B]` and `[B,A]` → identical canonical bytes and digest `eb92d191…cb2a9`, actor list in canonical ascending order | PASS | none |
| Case variants share one canonical identity (§3.3.4, D14) | LIVE TRANSPORT: `cam`/`CAM` → `ca89f589…7261`, `cam_1`/`CAM_1` → `130f2202…9404`, `cam_01`/`CAM_01` → `94992aee…7e32` | PASS | none |
| Numbered identities are distinct classes | LIVE TRANSPORT: three distinct entity ids and three distinct digests for `CAM`, `CAM_1`, `CAM_01` | PASS | none |
| Parent three-state model (§3.3.6, D7) | LIVE TRANSPORT: `none` (null path), `unbound` (path, null id), `bound` (id `IMPL_PERM_A` + path) | PASS | none |
| Material assignment vs asset slot vs resolved value (§3.8) | LIVE TRANSPORT: cube slot `WorldGridMaterial` with override `DefaultMaterial` (resolved = override); second component with `BasicShapeMaterial`; sphere slot `DefaultMaterial` with override `WorldGridMaterial`; the two actors digest differently | PASS | live Nanite substitution not reachable, see 4.4 |
| Omitted-primitive inventory (§4.10) | LIVE TRANSPORT: `IMPL_OMITTED` reports `count = 2`, classes `["ArrowComponent","BillboardComponent"]` (the skinned actor's own helper primitives; the decal actor adds its own decal component) | PASS | see note (b) |
| Skinned family with a null asset | LIVE TRANSPORT: `SkeletalMeshComponent`, `mesh_state = no_mesh_asset`, empty slots | PASS | no skinned asset is shipped in project content, so the *populated* skinned arm is not covered |
| Signed zero as a source fact (§5.5.1) | LIVE TRANSPORT: `scale.x = 8000000000000000` preserved; LIVE IN-PROCESS: the payload equals the engine's own value bit for bit on location, rotation and scale | PASS | actor *location* normalises the sign, see 4.2 |
| Sequencer extraction of a tagged `ALevelSequenceActor` (§11.2) | LIVE TRANSPORT: `IMPL_SEQUENCE_VALID` → saved asset path `AtlasExtractionSequenceValid`, range `[0,100)`, tick `24000/1`, display `30/1`, digest `16c4941d…9c1b` | PASS | none |
| Tagged-actor exclusion of untagged actors | LIVE IN-PROCESS: an untagged actor and an untagged parent never appear in the payload; no `session` string appears | PASS | none |
| Test-only scope seam is null in production | SOURCE GATE: the probe variable is declared without an initialiser, and neither the transport server nor the module startup sets it | PASS | none |
| Extraction does not depend on fixture content | SOURCE GATE: the extractor TU references no fixture symbol, spawn, or save | PASS | none |

### 3.2 REFUSAL VERIFIED

| contract requirement | evidence (class) | result | remaining gap |
| --- | --- | --- | --- |
| Runtime-generated/unstable mesh asset → fail closed (§3.8.3 rule 7) | LIVE TRANSPORT: `ERR_EXTRACTION_MESH_ASSET_UNSTABLE`, "mesh asset …ImplRuntimeMesh.AtlasGeneratedMesh_0 is not a saved top-level package asset" | REFUSAL VERIFIED | none |
| Unsupported material-bearing component family → fail closed (§3.8.1) | LIVE TRANSPORT: `ERR_EXTRACTION_UNSUPPORTED_COMPONENT_TYPE`, "registered component …UnsupportedVolume (HeterogeneousVolumeComponent) is outside the two supported material component families" | REFUSAL VERIFIED | none |
| Unknown entity → fail closed (§3.3.5) | LIVE TRANSPORT: `ERR_EXTRACTION_ENTITY_NOT_FOUND`; case-folded duplicate request ids → `ERR_EXTRACTION_REQUEST_INVALID` | REFUSAL VERIFIED | none |
| Degenerate playback range → fail closed (§4.8) | LIVE TRANSPORT: `ERR_EXTRACTION_SEQUENCE_RANGE_INVALID`, "the playback range [0, 0) is degenerate" | REFUSAL VERIFIED | none |
| Non-positive frame rate → fail closed (§4.8) | LIVE TRANSPORT: `ERR_EXTRACTION_SEQUENCE_RATE_INVALID`, "non-positive frame rate: tick 0/1, display 30/1" | REFUSAL VERIFIED | none |
| Scope change between snapshot and re-query → fail closed (§3.2.1.4b) | LIVE IN-PROCESS: `Atlas.StateExtraction.ScopeChangeRefusal` Success — the pre-state recorded two scope levels, the probe removed one (level array 2 → 1, asserted), and the extraction then failed with `ERR_EXTRACTION_SCOPE_CHANGED` | REFUSAL VERIFIED | induced through the extractor's null-by-default seam, see note (c) |
| Package dirtiness unchanged by extraction (§11.3) | LIVE IN-PROCESS: `Atlas.StateExtraction.PackageDirtyInvariance` Success — dirty map-package count unchanged, world-package dirty flag unchanged, and a deliberately clean world package stays clean after extraction; resolved content packages stay clean | REFUSAL VERIFIED | see note (d) |
| World Partition → fail closed | LIVE TRANSPORT in the rung-1 session: `ERR_EXTRACTION_WORLD_PARTITION_UNSUPPORTED` against the default partitioned world | REFUSAL VERIFIED | not re-observed in this session (the fixture map is not partitioned), see note (e) |

### 3.3 NOT YET LIVE-COVERED

| contract requirement | evidence | result | remaining gap |
| --- | --- | --- | --- |
| World Partition refusal in the fixture session | none in this session | NOT YET LIVE-COVERED | the fixture map is deliberately non-partitioned; the refusal is observed in the default-world session |
| Payload size bound (`ERR_EXTRACTION_PAYLOAD_TOO_LARGE`, 1 MiB) | none | NOT YET LIVE-COVERED | needs a fixture whose payload approaches the bound; U8 was unmeasured in the design too |
| Populated skinned-mesh material arm | none | NOT YET LIVE-COVERED | no skinned asset exists in project/engine content that is a saved top-level package |

### 3.4 BLOCKED BY ENGINE/API LIMITATION

| contract requirement | obstacle (measured, with engine evidence) | result | remaining gap |
| --- | --- | --- | --- |
| Open playback bound → `ERR_EXTRACTION_SEQUENCE_RANGE_OPEN` | `UMovieScene::SetPlaybackRange(const TRange<FFrameNumber>&)` documents "Must not have any open bounds (ie must be a finite range)" and asserts `NewRange.GetLowerBound().IsClosed() && NewRange.GetUpperBound().IsClosed()` (`MovieScene.cpp:689`). Setting the state aborted a live editor session (observed). The backing `FMovieSceneFrameRange PlaybackRange` is private (`MovieScene.h:1271/1311`) and `ULevelSequence::Initialize` leaves a *degenerate* closed range instead (measured: that asset reported `ERR_EXTRACTION_SEQUENCE_RANGE_INVALID`). | BLOCKED | no fixture can hold the state; the code stays in the closed vocabulary and is cross-checked by the contract-closure test |
| `IsCompiling()` mesh → `ERR_EXTRACTION_MESH_COMPILING` | inducing a compiling `UStaticMesh` needs the static mesh compiling manager (`Runtime/Engine/Private/StaticMeshCompiler.h`), unreachable from a harness module; the only public path is a real async build whose completion timing is not deterministic, which would make the gate flaky. | BLOCKED | arm presence is SOURCE GATE + vocabulary closure only |
| Quaternion `q` vs `-q` distinct through an actor transform | The engine stores an actor's rotation as an `FRotator` and derives the quaternion, so both fixtures hold the same signed quaternion (`z=3fe6a09e667f3bce`, `w=3fe6a09e667f3bcd`, and note the 1-ULP difference between the two components: the round-trip through rotator storage is itself lossy at the last bit). LIVE IN-PROCESS proves the payload equals the engine's own quaternion bit for bit on both fixtures. | BLOCKED | the ±q distinction is evidenced at the encoding level (PYTHON FORCED vectors for both signs) and by in-process fidelity, not by two live actors |
| Live Nanite material substitution (resolved ≠ assignment ≠ asset slot) | the extractor resolves through `UMeshComponent::GetMaterial`, which returns the assignment; Nanite substitution happens in the render path. No shipped material with a Nanite override is available to the fixture. | BLOCKED | the collision matrix for this case is PYTHON FORCED only |

## 4. Notes, and what a reviewer should not read into this document

**(a) Scope levels.** The transport gate's baseline ran after the in-process scope-change test
had removed the runtime streaming level from that session (the test mutates the world on
purpose; the extractor does not), so the baseline's recorded scope shows the persistent level
only. The two-level scope is asserted by the in-process pre-state (`found 2`) and by the
refusal that follows the removal. A rebuilt session restores the probe.

**(b) Omitted inventory.** The reported classes are the engine's own helper primitives on the
fixture actors (`ArrowComponent`, `BillboardComponent` on an `ASkeletalMeshActor`), which is
the inventory behaving as specified. It is not an enumeration of every non-mesh primitive in
the world.

**(c) Scope-change seam.** `ERR_EXTRACTION_SCOPE_CHANGED` is exercised through the extractor's
null-by-default probe: the extractor itself performs no mutation, takes no waits, no task hops
and no polling, and the probe is set only by the automation test. The removal of the streaming
level is the test's action. This is the narrowest mechanism that reaches the branch without
adding an execution capability to the production operation.

**(d) Dirty-state proof.** Package dirtiness is measured directly through the extractor inside
the automation test. Exposing dirtiness through the transport would expand production
authority for a test-only read, which this rung deliberately did not do; if a future rung needs
it as a transport-visible fact, that is an architecture decision, not a test detail.

**(e) World Partition.** The refusal was observed live in the rung-1 session against the
editor's default (partitioned) world and is unchanged here; this session deliberately opens a
non-partitioned map so the extraction can succeed at all.

**(f) Defects this rung found and fixed** (each was caught by a gate, not by inspection):

1. Runtime-created child components were lost from the saved map (they were not in the actor's
   instance-component list). Fixed by engine-owned components (`AStaticMeshActor`,
   `ASkeletalMeshActor`, `ADecalActor`) and `AddInstanceComponent` where a component must be
   created directly. Before the fix every material-bearing arm reported no components.
2. The material fixture's overrides collided with the engine content's own slot materials
   (`/Engine/BasicShapes/Cube` uses `WorldGridMaterial`, the sphere uses `DefaultMaterial`),
   so assignment and asset slot were indistinguishable — the gate failed the arm rather than
   passing it.
3. A dynamically loaded level instance is renamed by the engine
   (`<package>_LevelInstance_<n>`), which defeated the scope probe's lookup; matched by prefix.
4. `extract_sequencer_state` requires the `sequencer` capability, not `inspect_actor`; the
   gate's sequencer requests were corrected (the transport's own rule, unchanged).
5. Building the open-bound range state asserted and aborted a live editor session — reported
   as an engine limitation (3.4) rather than worked around.
6. An earlier gate measurement was misread because the payload's transform scalars are plain
   binary64 strings, not objects with a `source` field; the in-process reader was corrected.

**(g) Status.** Every Revision 3.1 acceptance gate required for implementation freeze is either
demonstrated above or explicitly shown to be impossible without a contract/architecture change.
Two contract arms (`ERR_EXTRACTION_SEQUENCE_RANGE_OPEN`, `ERR_EXTRACTION_MESH_COMPILING`) are
unreachable through any engine API this harness may use, and one arm (`±q`) is not expressible
through an actor transform; all three are recorded as blocked with verbatim evidence, not as
covered. This rung does **not** declare the implementation CLEAR, and it does not close the
implementation gate.
