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

    # 2. the fixture session: provisioning is OPT-IN and verifies committed content.
    #    Without -AtlasExtractionFixture an ordinary harness start-up provisions nothing
    #    and writes nothing; with it, existing content is verified against the fixture
    #    contract and never rewritten. The session prints exactly one
    #    "ATLAS_EXTRACTION_FIXTURE_STATUS: OK version=<n>" line once verified, which the
    #    gate below uses as its precondition.
    UnrealEditor-Cmd.exe <uproject> -AtlasExtractionFixture -unattended -nosplash -nop4 \
        -nullrhi -stdout

    # 3. gate session: fixture map open, fixture mode on, in-process automation requested
    UnrealEditor-Cmd.exe <uproject> /Game/AtlasTest/Generated/AtlasExtractionFixture \
        -AtlasExtractionFixture -unattended -nosplash -nop4 -nullrhi -stdout \
        -FullStdOutLogOutput -ExecCmds="Automation RunTests Atlas.StateExtraction"

    # 4. transport gate against the running editor, folding in the in-process results
    python -m tests.unreal_state_extraction_live_gate \
        --json <report.json> --automation-log <session log>

Regeneration is explicit and never silent: the generated content lives in
`Content/AtlasTest/Generated/AtlasExtraction*`, provisioning only happens in an explicit
`-AtlasExtractionFixture` session, existing content is verified against the fixture contract
rather than rewritten, and a mismatch fails closed with the exact difference (the gate then
refuses to proceed because the `OK` status line never appears). The build's expected content
version is reported by `GetExpectedFixtureContentVersion()`; a bump means the committed
content must change deliberately.

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
| Material assignment vs asset slot vs `resolved` (§3.8, Revision 3.3) | LIVE TRANSPORT: cube slot `WorldGridMaterial` with override `DefaultMaterial` (`resolved` = override); second component with `BasicShapeMaterial`; sphere slot `DefaultMaterial` with override `WorldGridMaterial`; the two actors digest differently. LIVE IN-PROCESS (`MaterialResolutionBoundary`): for every slot the payload's `resolved` equals the **deterministic projection** of the two facts read directly from the engine's own objects (`OverrideMaterials[idx]`, mesh asset slot material), the session's component-accessor value and substitution-gate state are *recorded* as observations, and the recorded value is asserted unaffected by them. Boundary rule (D17c): a divergent `resolved` is refused, in both families | PASS | none for the recorded value; the engine-side substitution is out of scope by construction (see 4.4) |
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
| Payload size bound (`ERR_EXTRACTION_PAYLOAD_TOO_LARGE`) | LIVE IN-PROCESS (`Atlas.StateExtraction.PayloadBoundRefusal`): a deliberately constructed payload crosses the bound on **measured** bytes (`MeasureValueTreeBytes` equals the real serialized UTF-8 length), the early condition flips exactly at the limit, and the transport's own predicate (`ExceedsTransportBound`, the same comparison the wire path uses) accepts exactly the limit and refuses one byte more | PASS (boundary, in-process) | the **live** arm stays NOT YET LIVE-COVERED: no fixture in this rung can produce an engine response near the bound. Nothing here is claimed as a live oversize refusal |
| Populated skinned-mesh material arm | none | NOT YET LIVE-COVERED | no skinned asset exists in project/engine content that is a saved top-level package |
| Fixture content integrity before the gate proceeds (review F-1 items 4-5) | LIVE IN-PROCESS (`Atlas.StateExtraction.FixtureContentIntegrity`): the committed sequences hold exactly their arms' rates and ranges, the map is non-partitioned, every expected entity tag appears exactly once, no unexpected entity tag exists, and each sequence actor resolves to its expected sequence asset; the session's `ATLAS_EXTRACTION_FIXTURE_STATUS: OK version=3` line is the run precondition | PASS (in-process verification + session status precondition) | the integrity check proves the *committed* content; it cannot prove that a future edit to the fixture source keeps it in step, which is why the expected content version is reported and the check fails closed on any difference |
| The static accessor's conditional material-level Nanite step (§3.8.2, Rev 3.2 → 3.3) | none | **NOT A COVERAGE GAP — declared out of scope by Revision 3.3** | the step is session/configuration gated (`ShouldCreateNaniteProxy` + `r.Nanite.MaterialOverrides`) and is therefore *not extracted*: `resolved` is the deterministic projection of the two source facts, so the step cannot appear in the payload even in a session that would take it. The in-process test records the session's accessor value and gate state so a substituting session is visible in the evidence |

### 3.4 BLOCKED BY ENGINE/API LIMITATION

| contract requirement | obstacle (measured, with engine evidence) | result | remaining gap |
| --- | --- | --- | --- |
| Open playback bound → `ERR_EXTRACTION_SEQUENCE_RANGE_OPEN` | `UMovieScene::SetPlaybackRange(const TRange<FFrameNumber>&)` documents "Must not have any open bounds (ie must be a finite range)" and asserts `NewRange.GetLowerBound().IsClosed() && NewRange.GetUpperBound().IsClosed()` (`MovieScene.cpp:689`). Setting the state aborted a live editor session (observed). The backing `FMovieSceneFrameRange PlaybackRange` is private (`MovieScene.h:1271/1311`) and `ULevelSequence::Initialize` leaves a *degenerate* closed range instead (measured: that asset reported `ERR_EXTRACTION_SEQUENCE_RANGE_INVALID`). | BLOCKED | no fixture can hold the state; the code stays in the closed vocabulary and is cross-checked by the contract-closure test |
| `IsCompiling()` mesh → `ERR_EXTRACTION_MESH_COMPILING` | inducing a compiling `UStaticMesh` needs the static mesh compiling manager (`Runtime/Engine/Private/StaticMeshCompiler.h`), unreachable from a harness module; the only public path is a real async build whose completion timing is not deterministic, which would make the gate flaky. | BLOCKED | arm presence is SOURCE GATE + vocabulary closure only |
| Quaternion `q` vs `-q` distinct through an actor transform | The engine stores an actor's rotation as an `FRotator` and derives the quaternion, so both fixtures hold the same signed quaternion (`z=3fe6a09e667f3bce`, `w=3fe6a09e667f3bcd`, and note the 1-ULP difference between the two components: the round-trip through rotator storage is itself lossy at the last bit). LIVE IN-PROCESS proves the payload equals the engine's own quaternion bit for bit on both fixtures. | BLOCKED | the ±q distinction is evidenced at the encoding level (PYTHON FORCED vectors for both signs) and by in-process fidelity, not by two live actors |
| Live Nanite material substitution (resolved ≠ assignment ≠ asset slot) | Revision 3.3 resolves this as a **design** matter rather than a coverage matter: the engine's material accessor applies a session/configuration-gated substitution, so a digested field may not be defined through it. `resolved` is now the deterministic projection of the two source facts, a divergent tree is refused at the boundary (D17c), and the extractor no longer calls the accessor at all. | **RESOLVED by Revision 3.3 — out of scope by construction** | none for the recorded value; the engine substitution itself is deliberately not modelled |

### 3.5 Review-hardening mechanisms (F-1, R-1, R-2)

These address the independent review's findings without touching the frozen Revision 3.3 contract
(no design change was required) and without changing extraction semantics.

| finding | mechanism now in the tree | evidence |
| --- | --- | --- |
| **F-1.1/F-1.2** — provisioning must not run in every editor start-up | `FAtlasUnrealTransportModule::StartupModule` starts the fixture ticker only when `-AtlasExtractionFixture` is on the command line; otherwise it logs that provisioning is disabled | LIVE: an ordinary session's log contains no fixture line and writes no content (verified by running one); the fixture session's log contains exactly one status line |
| **F-1.3** — behaviour preserved in fixture mode | the same provisioner and per-session runtime probes run unchanged when the switch is present | LIVE: the fixture session produces the same payloads as before (digests below) |
| **F-1.4** — committed content must not be rewritten every start-up | `EnsureSequenceAsset` verifies an existing asset against `FSequenceExpectation` and returns without marking it dirty or saving; the map branch no longer regenerates anything | LIVE IN-PROCESS: `FixtureContentIntegrity`; source: the save path is now reachable only for absent content |
| **F-1.5** — stale content must fail closed | `VerifyFixtureContentIntegrity` (pure read) reports the first difference and the ticker stops with `ATLAS_EXTRACTION_FIXTURE_STATUS: FAILED …`; the gate's `fixture_status_precondition` then fails the run | SOURCE GATE + LIVE: the precondition case appears in the gate report; a session without the switch fails it |
| **F-1.6** — provisioning stays out of the extractor | the new checks live in `AtlasExtractionFixture.cpp`; the extractor TU still references no fixture symbol | SOURCE GATE: `test_extractor_never_depends_on_fixture_content` |
| **R-1** — the §10.2 item 4 allow-list must be an allow-list | `PERMITTED_ARROW_CALLS` closes the extractor's `->` call surface: every arrow call must be declared (with its design clause) and every declared entry must be used; the component/Nanite accessors are separately forbidden | SOURCE GATE: `test_every_arrow_call_is_on_the_declared_list`, `test_the_declared_list_has_no_stale_entries`, `test_forbidden_accessor_is_never_called` |
| **R-2** — the response must be measured, not assumed | the extractor's early condition measures the value tree with no envelope allowance; the server's `SerializeExtractionCheckedResponse` serializes the **actual** response through the existing path, measures its wire form with the transport's predicate and, for the two extraction operations only, replaces an oversize response with `ERR_EXTRACTION_PAYLOAD_TOO_LARGE` and clears `observed_state` before anything is written | SOURCE GATE: the closure tests pin the measured path, the scoping, the shared limit and the code; LIVE IN-PROCESS: the boundary test above |

## 4. Notes, and what a reviewer should not read into this document

**(h) Revision 3.2 — material-resolution semantic correction.** The material/validation work in
this rung measured one genuine contract/implementation mismatch and it was corrected in the
**contract**, not in the extractor. *(Superseded on the determinism question by note (i): Revision 3.2
defined the field as the engine accessor's value, which is session sensitive.)* Revision 3.1 described `resolved_material_asset_path` as the
engine's resolution "including Nanite substitution" and applied that to *both* component families;
the sources show the material-level Nanite-override step exists only in the **static** family's
accessor (`StaticMeshComponentHelper.h:108-137`) and is **session-gated**
(`UseNaniteOverrideMaterials` → `ShouldCreateNaniteProxy(Component, nullptr) && GEnableNaniteMaterialOverrides != 0`),
while the skinned accessor has no such step (`SkinnedMeshComponentHelper.h:108-121`). Revision 3.2
narrows the field to **the read-boundary value of `Component->GetMaterial(slot)`** after the
component's own assignment resolution, states that it is not rendered-material state, and fixes the
boundary in one sentence:

> Nanite render-path substitution is outside v1 extraction because the extraction accessor does not
> expose that rendered state.

The extraction accessor is unchanged, no refusal was weakened, no error code or field name changed,
and no render-state access was added. The live material cases were re-run under the narrowed
contract and still pass. A gate case
(`material_rendered_appearance_dimension`) records the rendered-appearance dimension as
NOT YET LIVE-COVERED so the rung never claims it. Design-side record:
`docs/UNREAL_STATE_EXTRACTION_FIDELITY_V1_REV2_REVIEW.md` §8 and the Revision 3.2 change log.

**(i) Revision 3.3 — deterministic material resolution (session/configuration independence).** The
analysis that followed Revision 3.2's hold established that `Component->GetMaterial(slot)` is **not**
a deterministic function of saved source state: its material-level Nanite step is gated by
`UseNaniteOverrideMaterials` → `ShouldCreateNaniteProxy(Component, nullptr) && GEnableNaniteMaterialOverrides != 0`,
whose inputs include the shader platform, `UseNanite(ShaderPlatform)`, the mesh's Nanite data,
`Nanite::IsMaskingAllowed`, and the editor-only `IsDisplayNaniteFallbackMesh()` viewport toggle; the
gate itself is the scalability CVar `r.Nanite.MaterialOverrides`. Two sessions of the *same* build can
therefore return different materials for the same saved map. Revision 3.3 removes the dependence by
construction: `resolved_material_asset_path` is the **deterministic projection** of the slot's two
source facts (override when non-null, else asset slot), the component material accessor is off the
extraction read boundary entirely (so the material helper's `ConditionalPostLoad` no longer occurs),
and a divergent tree is refused at the boundary (D17c). Consequence for this document's evidence: the
`resolved` values recorded in every case below are unchanged by the revision, because the sessions
were run in configurations where the accessor already agreed with the projection — but that agreement
is now a recorded *observation*, not a load-bearing assumption. Invariance evidence (measured, two
sessions of the same build on the same saved map, differing only in session configuration): session A
ran with `r.Nanite.MaterialOverrides=1` and session B with `r.Nanite.MaterialOverrides=0` (each
recorded by the in-process test), both ran the six automation tests green and both transport gates
returned OVERALL PASS with the **same ten PASS / four REFUSAL VERIFIED / three BLOCKED / four NOT YET
LIVE-COVERED** classification, and the material cases produced **identical evidence and identical
digests** (`IMPL_MATERIAL_OVERRIDE_A` `a5917d03…d7cb`, `IMPL_MATERIAL_OVERRIDE_B` `9736fa18…e437` in
both sessions) — so identical saved source state plus identical engine build plus a different session
configuration produced byte-identical extraction. The in-process test also records, per fixture slot,
the session's component-accessor value, whether it agrees with the projection, and whether the
substitution gate is enabled (it is disabled in these `-nullrhi` sessions, which is itself recorded
rather than assumed). Design-side record:
`docs/UNREAL_STATE_EXTRACTION_FIDELITY_V1_REV2_REVIEW.md` §9 and the Revision 3.3 change log.

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

**(i) Review-hardening rung — measured results (F-1, R-1, R-2).** The three findings of the
independent implementation review were addressed without touching the frozen Revision 3.3 contract
(exact changes and mechanisms in §3.5):

* **Live session (fixture mode, `-AtlasExtractionFixture`):** `ATLAS_EXTRACTION_FIXTURE_STATUS: OK
  version=3`, **8/8 automation tests Success** (`FixtureContentIntegrity` and `PayloadBoundRefusal`
  among them), and the committed fixture assets were **byte-identical before and after the session**
  (SHA-256 of all six `.umap`/`.uasset` files), so existing content is verified rather than rewritten.
* **Ordinary start-up (no switch):** zero `ATLAS_EXTRACTION_FIXTURE_STATUS` lines, the
  "provisioning disabled" line present, and the same six assets byte-identical afterwards, so an
  ordinary start-up provisions and writes nothing.
* **Transport gate:** `result: PASS` — **13 PASS / 4 REFUSAL VERIFIED / 3 BLOCKED BY ENGINE/API
  LIMITATION / 6 NOT YET LIVE-COVERED**, with `fixture_status_precondition: PASS`,
  `payload_bound_refusal_in_process: PASS` and `fixture_content_integrity_in_process: PASS`. The two
  live-dimension cases (`payload_bound_refusal`, `fixture_content_integrity`) stay
  NOT YET LIVE-COVERED with their in-process evidence recorded.
* **Digest invariance:** `positive_baseline` = `5160b6fa11c95d594b6d7262d00ffe742fbf51e996fdef27abc4e793613cc3a6`
  over 1862 canonical bytes — byte-identical to the Revision 3.3 session, so the rung changed no
  successful extraction payload.
* **Suites:** `tests/test_unreal_state_extraction_*.py` — **448 passed** on CPython 3.9.6, 3.11.16 and
  3.12.14; UBT `AtlasUnrealHarnessEditor Win64 Development` → `Result: Succeeded`.

One measurement corrected a wrong assumption in the first version of the integrity check: the legacy
field-surface fixture spawns its entity-tagged actor into whichever world is open, so a foreign
`atlas_entity:` tag can be present in the fixture session's world without being committed content
(the extraction map's package does not contain it — verified). The check therefore verifies its own
tag set exactly and *reports* foreign tags instead of failing on them; a renamed, removed or
duplicated extraction-fixture actor still fails as a wrong expected-tag count.

This rung does **not** declare the implementation CLEAR, and it does not merge anything.
