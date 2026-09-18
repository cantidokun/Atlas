# Unreal State Extraction Fidelity v1 — Revision 2 Review

**Status:** REVIEW RECORD — IMPLEMENTATION NOT AUTHORIZED
**Reviews:** `docs/UNREAL_STATE_EXTRACTION_FIDELITY_V1_DESIGN.md` at Revision 2
**Branch:** `feat/unreal-state-extraction-fidelity-v1-design` (PR #106, draft)
**Author of this review:** the remediating agent (not an independent reviewer)
**Input to this review:** the second independent red-team (Claude Opus 5) verdict **BLOCK**,
delivered as findings F1–F15 plus canonicalization and determinism directives

This document records (1) the verification of every input finding against the repository and
the installed UE 5.6 engine source, (2) the design changes those findings produced, (3) the
second-pass hostile review of the revised design, (4) what remains unresolved, and (5) one
verdict token.

Environment used for every engine citation: `C:/Program Files/Epic Games/UE_5.6/Engine/`
(Build.version: `MajorVersion 5 / MinorVersion 6 / PatchVersion 1 / Changelist 44394996`).
Repository citations are `path:line` against the design branch head.

---

## 1. Input finding classification

Legend: **C** = CONFIRMED, **P** = PARTIALLY CONFIRMED, **F** = FALSE POSITIVE.

| # | Finding | Class | Repository / engine evidence |
|---|---|---|---|
| F1 | Transform precision premise (LWC doubles) | **C** | `Core/Public/Math/MathFwd.h:47,50,53` — `FVector = TVector<double>`, `FQuat = TQuat<double>`, `FTransform = TTransform<double>`; float variants are separate types at `:73` (`FVector3f`) and `:76` (`FQuat4f`); the LWC macro binds the default alias to `double` (`Core/Public/Misc/LargeWorldCoordinates.h:17`). `AActor::GetActorLocation/GetActorQuat/GetActorScale3D` return those aliases (`Engine/Classes/GameFramework/Actor.h:1700,2482,2500`). Revision 1 §4's "All Unreal transform scalar values in v1 originate as `float32` source facts" was false. |
| F2 | Transport/session metadata contaminates extraction | **C** | Envelope carries `session_identity` beside `observed_state` (`AtlasTransportServer.cpp:294-311`); contents are `editor_session_id`, `process_id`, `process_creation_time_utc`, `server_start_time_utc`, `engine_version`, `project_identity` (`:2309-2333`). The Python adapter copies `observed_state` and injects `_session_identity` (`planning/unreal_adapter_production.py:76-95`), and the existing evidence digest digests `observed_state` verbatim (`planning/unreal_evidence_digest.py:36-45,52-57`) — so the existing evidence digest is session-varying. `inspect_render_state` embeds `engine_session_identity` inside its own `observed_state` (`AtlasTransportServer.cpp:1969-1971`). Revision 1 declared session metadata "excluded" without defining the boundary. |
| F3 | Loaded-world scope | **C** | `TActorIterator`'s default flags are `OnlyActiveLevels \| SkipPendingKill` (`Engine/Public/EngineUtils.h:509`) and with `OnlyActiveLevels` a level is iterated only when `(bIsVisible && !bIsBeingRemoved) \|\| bIsAssociatingLevel \|\| bIsDisassociatingLevel` and its collection is the active collection or `StaticLevels` (`EngineUtils.h:462-483`). So load/visibility/association state changes the visible entity set for one world identity. The existing code also has two divergent selections: `FindActorByEntityId` uses `GEngine->GetWorldContexts()[0].World()` (`AtlasTransportServer.cpp:2300-2303`) while provisioning uses `GetActiveEditorWorld()` (`AtlasUnrealTransport.cpp:207`) — the exact split-world trap. |
| F4 | Parent identity is lossy | **C** | Revision 1 §3.2 mapped both "no attach-parent actor" and "attach-parent actor with no Atlas entity binding" to `unbound/null`, so two different scene graphs produced one extraction state. The current C++ has no parent extraction at all to fall back on. |
| F5 | Visibility semantics | **C** | `AActor::IsHiddenEd()` is a derived aggregate: `bHiddenEdLayer \|\| !bEditable \|\| (GIsEditor && (IsTemporarilyHiddenInEditor() \|\| bHiddenEdLevel))` (`Engine/Private/ActorEditor.cpp:973-982`) — execution-mode dependent through `GIsEditor`, and it folds in a flag (`bEditable`) that is `protected` (`Actor.h:1253,1264`) and one (`bHiddenEdTemporary`) that is `private` (`Actor.h:1286-1289`). Revision 1 called `IsHiddenEd()` a "source fact". |
| F6 | Sequencer fixture violates the contract | **C** | All five reported properties verified in `AtlasSequencerIntegrationFixture.cpp`: core ticker at 0.25 s (`:72`); spawns into the live editor world (`:21,41`); `ESpawnActorNameMode::Requested` (`:38`), which per `Engine/Classes/Engine/World.h:496-509` generates an unused name when the requested one is taken; transient, `NAME_None` sequence (`:50`). Two further conflicts found: `ULevelSequence::Initialize()` reads `CVarDefaultTickResolution` / `CVarDefaultDisplayRate` and stamps `FDateTime::UtcNow()` into MovieScene metadata (`LevelSequence/Private/LevelSequence.cpp:103-127`), and the harness fixture dirties the level package at startup (`AtlasUnrealTransport.cpp:438`, also `:113` and `:378`). |
| F7 | FName/entity-ID case semantics | **C** | `FName` is "case-insensitive, but case-preserving" (`Core/Public/UObject/NameTypes.h:573`) and compares comparison-index + number (`:762-765`); `Tags.Contains(FName(...))` (`AtlasTransportServer.cpp:2300-2303`) is therefore case-insensitive. Additionally `FString::operator==` is case-insensitive (`Containers/UnrealString.h.inl:1053-1056,1067-1070`) — a cross-language divergence hazard for any ordinal comparison written with `==`. |
| F8 | Actor object path versus stable identity | **C** | The object path contains the mutable object name, so rename/recreate/level-move change it. A stable GUID alternative is refuted on engine evidence: `ActorGuid` is derived from the path for persisted actors (`Engine/Private/Actor.cpp:1013-1015`) and randomly regenerated on duplicate (`:1017-1019`), i.e. it either adds nothing or is not reproducible across sessions. Revision 1 also duplicated `actor_object_path` at top level and inside `source_identity`. |
| F9 | Material state machine | **C** | A binary `resolved \| missing` is insufficient: `UStaticMeshComponent::GetNumMaterials()` returns 0 with no mesh asset (`Engine/Private/Components/StaticMeshComponent.cpp:2765-2775`); the skinned path returns 0 slots **while compiling** and `GetMaterial` returns null while compiling (`SkinnedMeshComponent.cpp:1713-1720`, `Engine/Public/SkinnedMeshComponentHelper.h:114-120`); the resolved value may be a **Nanite override** rather than the assigned one (`StaticMeshComponentHelper.h:108-137`); empty slots render with the engine's default material, which is render state. The existing "material verification" is unrelated: `BuildMaterialVariantState` returns only a tag name (`AtlasTransportServer.cpp:692-694`) and `verify_material_variant` is mapped to that read (`planning/unreal_adapter_production.py:109`). |
| F10 | Fail-closed numeric semantics | **P** | The narrowing premise is confirmed as F1 (binary32 canonicalisation of binary64 source facts). The specific corruption outcomes — a finite value becoming infinite, a nonzero becoming zero — were **latent in the specified representation rather than demonstrated**, because Revision 1 had no implementation; and Revision 1 did require non-finite values to fail closed. Recorded as PARTIALLY CONFIRMED: real hazard, not yet an observed defect. |
| F11 | Quaternion / zero semantics | **P** | Revision 1 already forbade normalisation, shortest-path selection, tolerance and equivalence comparison, and stated that non-finite values fail closed — so part of the directive was met. It did not state that `q`/`-q` and `±0` remain **distinct**, and it did not separate source-fidelity identity from semantic equivalence. |
| F12 | State authority / trust boundary | **P** | Revision 1 said the extractor must not authorize/receipt/verify and that M12.5 is unchanged. Missing: the untrusted-input statement, "validation is not verification", "a digest is not a verdict", "must not replace `TargetStateEvaluator`", "must not become M12.5", and the reserved seam. Anchors that make these binding: `planning/unreal_transport_contract.py:6-11` ("neither trusts the other", "responses never carry a `verified` flag"), `planning/unreal_evidence_contract.py:267-268` (only `verify_render_job_evidence` constructs verified evidence), `planning/target_state.py:50-77`, `planning/m12/target_state.py:1-13`, `docs/ATLAS_ARCHITECTURE_CONTRACT.md:23,176-187`. |
| F13 | World-selection implementation mismatch | **C** | `GetActiveEditorWorld()` falls back to `GEngine->GetWorldContexts()` in **two** copies (`AtlasTransportServer.cpp:81-100`, `AtlasUnrealTransport.cpp:149-173`); `FindActorByEntityId` uses `GetWorldContexts()[0].World()` and returns the first tag match (`AtlasTransportServer.cpp:2300-2303`); `InspectWorld` takes the last valid context, preferring `EWorldType::Editor` (`:769-790`). The world enum is `namespace EWorldType { enum Type { None, Game, Editor, PIE, EditorPreview, GamePreview, GameRPC, Inactive } }` (`Engine/Classes/Engine/EngineTypes.h:1222-1249`). Engine version is a hardcoded literal `FString EngineVersion = TEXT("5.6")` (`AtlasTransportServer.cpp:120`) surfaced through `session_identity` (`:2322,2331`), and it **already disagrees with the host engine**, which is 5.6.1 (`UE_5.6/Engine/Build/Build.version`). Revision 1 §13 said the probes may be "reused or refined". |
| F14 | Sequencer validity/bounds | **P** | Revision 1 did define bound markers, exact rational rates and open-bound rejection. Missing: a validity predicate, the fact that `FFrameRate::IsValid()` tests **only** `Denominator > 0` (`Core/Public/Misc/FrameRate.h:48-51`), the legacy read/write asymmetry, and removal of an unreachable failure class. The asymmetry is real and frozen: `inspect_sequencer_state` reports `end_frame` as the **exclusive** upper bound (`AtlasTransportServer.cpp:719-743`) while `set_sequencer_playback_range` treats `end_frame` as **inclusive** and converts with size `EndFrame - StartFrame + 1` (`:763`, frozen by `tests/m10/test_m10_defect_d2_sequence_range.py:95-102`). `SetPlaybackRange(FFrameNumber Start, int32 Duration)` is half-open (`MovieScene/Public/MovieScene.h:998`). |
| F15 | Error and capacity boundaries | **C** | The transport vocabulary is 9 free-string codes with a generic catch-all `ERR_OPERATION_FAILED` set in the dispatcher wrapper (`AtlasTransportServer.cpp:658`); the Python side has 5 codes; nothing maps extraction failure classes to codes. Both directions are bounded at 1 MiB (`AtlasTransportServer.cpp:46`, `:218`, `:251`; `planning/unreal_transport_named_pipe.py:212`), and a client-side framed envelope with declared length + SHA-256 fails closed on mismatch (`unreal_transport_named_pipe.py:261-281`). Game-thread execution is bounded by a 5000 ms wait (`AtlasTransportServer.cpp:606,608`). No policy existed for oversize extraction. |
| — | Canonicalization: no in-repo JCS implementation | **C** | `RFC 8785` / "JSON Canonicalization" appears nowhere in the repository except Revision 1 of the design. Every existing digest path uses `json.dumps(..., sort_keys=True, separators=(",", ":"))` with inconsistent `ensure_ascii` (`planning/unreal_evidence_digest.py:56`, `planning/unreal_render_contract.py:54,88`, `planning/production_artifact.py:75`, `planning/blender_execution_receipt.py:12`). |
| — | Canonicalization: `json.dumps(sort_keys=True)` is not RFC 8785 | **C** | Three reachable divergences: key ordering domain (Python code points vs JCS UTF-16 code units — reachable through object paths, which are not ASCII-constrained); string escaping (JCS = ECMAScript `JSON.stringify`; the repo's own call sites do not even agree with each other on `ensure_ascii`); number serialisation (ECMAScript rules, where Python prints `-0.0` for negative zero). Revision 1 named the standard and supplied no implementation strategy, ownership, vector requirement or byte-encoding rule. |
| — | Determinism: ordering/collation/testing unspecified | **C** | Revision 1 asserted determinism without naming who orders arrays, the collation for entity IDs and object paths, source-order preservation, duplicate handling, or any process-run/seed/reordered-fixture test. Two engine traps it did not exclude: `FLevelCollection::GetLevels()` is a `TSet` (hash order, `Engine/Classes/Engine/World.h:675,735`) and `UWorld::GetLevels()` is an arrival-ordered array (`:3426`). |

**Totals: 11 CONFIRMED, 4 PARTIALLY CONFIRMED, 0 FALSE POSITIVE**, plus all canonicalization and
determinism directives confirmed. No input finding was dismissed.

---

## 2. Changes made to the design

Only `docs/UNREAL_STATE_EXTRACTION_FIDELITY_V1_DESIGN.md` was modified. No C++ or Python
production code, no tests, no transport, no M4–M10 file, no M12.5 file, and no fixture were
touched. The document was restructured into a closed normative contract; the changes below are
the substance (the design's §15 carries the same mapping).

### 2.1 Structure

New: §2 Authority and trust boundary; §4.2 extraction boundary; §4.3 asserted-precondition
derivation; §4.4 world record; §4.5 collections; §5 exact numeric policy; §6 canonicalization
and digest; §7 determinism contract; §8 closed error vocabulary; §9 capacity/framing/execution
bounds; §10.1 operation surface; §11 fixture policy. Sections 3.1–3.9, 11 and 13–15 were
rewritten where the findings land.

### 2.2 Per-finding remediation

- **F1** — source scalars are declared binary64 with engine citations; canonical form is a
  16-hex-digit binary64 bit pattern reinterpreted by `memcpy`/`struct.pack`; narrowing
  (`static_cast<float>`, `UE_REAL_TO_FLOAT*`, `struct.pack("<f")`, `numpy.float32`) is forbidden
  anywhere between accessor and encoding; the payload asserts the claim in-band via
  `transform.source_component_type: "binary64"`, derived from a compile-time `FReal`
  assertion (§3.7, §5.1–5.2, §4.3).
- **F2** — the value tree is a closed schema under exactly one key
  (`observed_state.unreal_state_extraction`); reserved-key rejection at any depth (including
  `_session_identity`, `session_identity`, `engine_session_identity`, `process_id` and all
  timestamps); the digest input is **reconstructed from declared fields only**, never copied
  from `observed_state`; the extraction boundary must run un-augmented and stripping is
  forbidden (§4.1–4.2, §6.5).
- **F3** — a complete loaded-visible scope is a precondition
  (`IsLevelLoaded() && IsLevelVisible()` for every streaming level); partitioned worlds are
  refused; the extractor never force-loads; entity binding scans an explicit level set
  (`ULevel::Actors` over the scope) instead of `TActorIterator`; the scope is recorded in the
  payload (§3.2).
- **F4** — three parent states `none` / `unbound` / `bound`; the `unbound` state carries the
  parent's object path, so re-parenting between unbound parents is digest-visible; two or more
  `atlas_entity:` tags on the parent fails closed (§3.5).
- **F5** — the derived aggregate (`hidden_in_editor` from `IsHiddenEd()`) is labelled derived
  and separated from the four public source flags; `GIsEditor` is recorded as
  `derived_from_gis_editor`; the unreadable input is declared in-band as the frozen literal
  `unrecorded_hidden_inputs: ["bEditable"]` (§3.6).
- **F6** — the ticker fixture is quarantined with a five-row evidence table; the design records
  that foreign transient actors are harmless **by construction** because extraction never
  enumerates the world actor set; the entity-tagged sequencer fixture that the gate needs is
  named as an implementation deliverable; the design does not modify the fixture (§11.1–11.2).
- **F7** — canonical entity-ID grammar `^[A-Za-z0-9_.-]{1,64}$`; case-insensitive uniqueness
  within a request; case-insensitive binding with explicit zero/one/many arms; tag-conflict
  rejection; ordinal, case-sensitive string comparison mandated everywhere except the binding
  lookup; the grammar makes UTF-8/UTF-16/code-point orders coincide, which is what makes the
  cross-language sort key unambiguous (§3.3, §7.3).
- **F8** — canonical entity identity, source-object provenance and mutable source locator are
  separated in a table; renaming is declared to change the digest by design; the duplicated
  nested `source_identity` object is removed; GUID-based identity is rejected on the
  `NewDeterministicGuid`/`NewGuid` evidence (§3.4).
- **F9** — a total component/slot state machine
  (`mesh_state` × `slot_state` ∈ {`mesh_asset_present`,`no_mesh_asset`} ×
  {`component_override`,`asset_slot`,`asset_slot_empty`}), with `assigned_*` and `resolved_*`
  material paths distinguished, Nanite substitution documented as the engine's own resolution,
  async compilation failing closed, transient/dynamic instances rejected, null-mesh components
  recorded rather than omitted, registered-component filtering, and an explicit non-equivalence
  statement for `verify_material_variant` / `atlas_material_variant:` (§3.8).
- **F10** — finiteness is tested on the returned `double` before encoding; no narrowing exists,
  so overflow-to-inf and flush-to-zero are structurally impossible; both classes are mandatory
  tests D11–D12, with D13 rejecting any non-16-hex lexical form (§5.5–5.6, §7.4).
- **F11** — `q`/`-q` and `±0` are declared distinct and never canonicalised; source-fidelity
  identity is defined separately from semantic equivalence, with the four implication rules for
  equal and unequal digests (§5.4).
- **F12** — extraction results are untrusted input; validation is not verification; a digest is
  an identity/integrity value and never a verdict; extraction must not replace
  `TargetStateEvaluator`, must not become M12.5, and the M12.5 seam is reserved and not
  implemented (§2).
- **F13** — `GEditor->GetEditorWorldContext().World()` only, `EWorldType::Editor` named
  explicitly, `Inactive` and `EditorPreview` rejected by name, partitioned worlds refused; the
  three existing order-dependent selections are tabulated as **replaced, not reused**; engine
  identity is sourced from `FEngineVersion::Current().ToString(EVersionComponent::Patch)` and
  `FApp::GetBuildVersion()` with the hardcoded legacy literal explicitly disqualified (§3.1).
- **F14** — a six-clause validity predicate with one error per clause; v1's own
  `numerator > 0 && denominator > 0` in place of `FFrameRate::IsValid()`; `upper_frame >
  lower_frame`; the legacy exclusive-read/inclusive-write asymmetry disclosed as a compatibility
  boundary; the unreachable multiple-candidate condition removed (§3.9).
- **F15** — a closed 21-code extraction vocabulary plus 3 Python-side codes, with one error per
  normative failure class and a prohibition on reporting extraction failures as
  `ERR_OPERATION_FAILED`; the 1 MiB bound, the framed envelope, a pre-response size check that
  fails closed with `ERR_EXTRACTION_PAYLOAD_TOO_LARGE`, no chunking, and timeout classified as a
  transport class (§8, §9).
- **Canonicalization** — RFC 8785 retained with an explicit implementation strategy: single
  Atlas-owned Python canonicalizer, restricted payload domain, in-domain vectors pass
  byte-exactly, out-of-domain (float/exponent) vectors must be **rejected**, byte encoding fixed
  as UTF-8 without BOM or trailing newline, and the existing `digest_evidence` path excluded
  (§6).
- **Determinism** — the producer orders arrays, Python **validates** canonical order and fails
  closed rather than silently sorting (JCS preserves array order); collation fixed as UTF-16
  code-unit order with the ASCII equivalence stated for entity IDs and the
  `utf-16-be`-key technique stated for object paths; the `TSet`/arrival-order traps named;
  duplicates rejected not deduplicated; mandatory tests D1–D13 covering different
  `PYTHONHASHSEED` values, reordered construction, request-order permutation, one-session and
  fresh-session repetition, non-canonical-order rejection, metadata rejection, JCS vectors,
  engine-identity difference, and the binary64 magnitude cases (§7).

---

## 3. Second-pass findings (hostile review of Revision 2)

The revised design was attacked for new contradictions, unresolved normative choices, decisions
left to the future coder, determinism gaps, hidden authority coupling, UE5.6 API assumptions and
live-fixture impossibilities. Seven findings were raised; all seven were remediated in the same
revision. They are recorded here rather than hidden, because each was a defect the remediating
author introduced.

### SP-1 — A field whose determinism is unprovable was in the digest — REMEDIATED (field removed)

Revision 2 (as first drafted) reported `entity_tag_literal`, the matched tag's stored casing.
That field is not demonstrably reproducible: tag comparison is case-insensitive
(`NameTypes.h:573,762`), and the casing returned for a name is a property of the process name
table — comparison and display entries are distinct, `FNamePool::Store` returns an existing
display entry for an exact-casing match and otherwise inserts one against the already-existing
comparison entry (`Core/Private/UObject/UnrealNames.cpp:1860-1883`), with
`InsertExistingEntryWithNumber` / `SetLoadedDifferentDisplayId` paths for the numbered and
loaded cases. The shipped headers and implementation do not let this contract *prove* that the
reported casing is identical across two fresh sessions, and a field that cannot be shown
deterministic must not participate in a digest. Removed; §3.3.3.6 now states the removal and the
reason, and the actor record no longer carries the field.

Disposition: the underlying engine question ("which casing does a tag FName report, and is it
stable across processes?") is **not fully determined from shipped sources** and is recorded here
as an open engine-semantics question. The contract no longer depends on the answer.

### SP-2 — Dead normative text — REMEDIATED (removed, replaced by a limitation)

Revision 2 (as first drafted) defined a failure arm for "a source tag whose prefix matches and
whose ID is case-insensitively equal to the requested ID but violates the canonical grammar".
That arm is unreachable: for a canonical request ID, a case-insensitively equal ID is itself
canonical, since the grammar admits both cases. A dead failure arm is exactly the defect the
input's F14 identified in Revision 1. The arm and its code
(`ERR_EXTRACTION_SOURCE_TAG_NON_CANONICAL`) are removed; the parallel parent clause is removed
too; and the real consequence is now stated as an explicit addressability limitation (§3.3.3.5):
a source tag whose ID is not canonical cannot be addressed by v1, and the answer is a correct
not-found.

### SP-3 — Acceptance markers could be satisfied by hardcoding — REMEDIATED (§4.3)

Revision 2 carries several fields whose legal value is fixed by the contract
(`world_type: "editor"`, `is_partitioned_world: false`, `selection_provenance`,
`level_scope.levels[].loaded/visible`, `transform.source_component_type: "binary64"`). As first
drafted, an implementation could write those literals — and a live gate observing them would
prove nothing. §4.3 now requires each marker to be **derived from the engine object it
describes**, with a compile-time assertion where the property is compile-time
(`FVector::FReal`/`FQuat::FReal` being `double`, `Math/Vector.h:55`), and asserted by Python.
Acceptance gate 12 requires a negative test: a stub reporting `world_type: "editor"` for a
non-editor world must fail.

### SP-4 — Hidden coupling to the session-augmenting adapter path — REMEDIATED (§4.2.8)

The production adapter copies `observed_state` and injects `_session_identity`
(`planning/unreal_adapter_production.py:76-95`). With §4.2.1's closed-schema rule, an extraction
consuming that path would fail closed on **every** production response — and the cheapest
apparent fix available to a future implementer is to delete the key, which is precisely the
containment breach §4.1 exists to prevent. §4.2.8 now states that the extraction boundary reads
the transport response's own `observed_state` (or an adapter path that does no augmentation),
that a session key at the boundary is a hard failure, and that stripping is forbidden.

### SP-5 — Unregistered components would have been extracted — REMEDIATED (§3.8.1)

As first drafted, the component set was "every `UMeshComponent`", which includes unregistered
components: components that do not participate in the world and whose material view is
necessarily unresolved. That would have introduced source facts no world state depends on and
made the payload sensitive to transient component construction. The set is now filtered to
registered components (`UActorComponent::IsRegistered()`, `ActorComponent.h:1243`).

### SP-6 — Engine identity could silently degrade to empty — REMEDIATED (§8.1)

`engine_version` and `engine_build_version` are digested, so an empty string would silently
weaken identity instead of failing. A closed code
`ERR_EXTRACTION_ENGINE_IDENTITY_UNAVAILABLE` now covers an empty version or build string.

### SP-7 — The JCS vector obligation contradicted the restricted domain — REMEDIATED (§6.4, D9)

Revision 2 requires a canonicalizer that fails closed on floats, and simultaneously requires the
RFC 8785 published vectors to pass — but those vectors include floating-point/exponent cases the
restricted domain can never produce. The two obligations as originally written could only be
satisfied by a canonicalizer that silently grows a number-formatting behaviour the contract
forbids. The obligation is now split: in-domain vectors (including the key-ordering and
string-escaping cases this contract actually needs) must canonicalise byte-exactly; out-of-domain
vectors must be **rejected**, and the test must assert the rejection.

### Second-pass items checked and found sound (no change)

- The closed-schema/reserved-key design does not accidentally forbid any legitimate field (no
  declared field name begins with `_`).
- The `world_package_path` == persistent `level_package_path` equality is a consequence of the
  scope rule, not a defect; it is now stated explicitly so it is not "corrected" by stripping a
  suffix.
- The material state machine is total over the component/slot domain, and every reported slot
  maps to exactly one state.
- The digest's exclusion of the request, the authorization, the transport and the session is
  intentional (identity of *source state*, not of intent) and is stated.
- The engine-identity-in-digest decision makes digests differ across engine builds; this is
  intended, is stated in §3.1.2, and is covered by D10 rather than left implicit.
- No finding was remediated by expanding scope: World Partition, chunked transport, forced level
  loading, source repair and semantic interpretation were all refused explicitly (§12).

---

## 4. Remaining unresolved issues

These are not masked and are not fixed here. Each has an explicit disposition.

**U1 — The complete-scope precondition is a material scope restriction (accepted, requires
independent acceptance).** v1 refuses to extract from any world with a streaming level that is
not loaded and visible. Many production maps deliberately keep a streaming level unloaded, so
those worlds are simply not extractable in v1. The alternative — extracting from a partial scope
and recording incompleteness — was rejected because it reintroduces exactly the ambiguity F3
exists to remove (an entity present only in an unloaded level would be indistinguishable from a
non-existent entity). Disposition: accepted bounded cost, documented in §3.2.1; an independent
reviewer should confirm the trade-off is acceptable rather than assume it.

**U2 — `hidden_in_editor` is not fully decomposable.** `bEditable` is `protected` and is folded
into the derived aggregate, so a change in that flag that leaves the aggregate unchanged is not
observable. Disposition: declared in-band via `unrecorded_hidden_inputs` (§3.6.3); a reviewer
could reasonably prefer a reflection-based read, which this design rejects as brittle and as a
private-state read path.

**U3 — Class-specific material semantics are out of scope.** Landscape and similar components
override the slot model; v1 records the generic `UMeshComponent` answer and claims nothing
class-specific (§3.8.3.4). Disposition: declared scope limit.

**U4 — Component identity is a mutable locator.** A component created at runtime with an
engine-generated name yields a non-reproducible object path. Disposition: declared (§3.8.1),
with the live gate required to use explicitly named components. A future milestone could bind
component identity to a slot name rather than an object path; that is a separate design.

**U5 — Cross-engine-build digest instability is intended but must be understood.** Because
engine identity is digested, the same content extracted by two engine builds yields different
digests. Disposition: stated (§3.1.2, D10); consumers must compare digests within a build.

**U6 — The live gate is not buildable as written.** §11.1.2's obligations require an
`ALevelSequenceActor` carrying an `atlas_entity:` tag; the repository's stable-sequence fixture
actor carries only `atlas_sequencer_fixture`. The fixture is named as an implementation
deliverable; no fixture was modified in this task. Disposition: implementation precondition,
recorded so the next rung cannot discover it late.

**U7 — The error vocabulary is contract-closed, not type-closed.** The transport's `error_code`
is a free string and the C++ side has no enum, so closure is enforced by tests and by the Python
validator, not by the type system. Disposition: an enforcement-quality note; the acceptance gates
require tests over the full vocabulary.

**U8 — The practical capacity limit is unmeasured.** No engine run was performed, so whether a
realistic multi-entity extraction approaches the 1 MiB bound is unknown. The design fails closed
either way (pre-response size check). Disposition: unmeasured; the first live gate should report
observed payload sizes.

**U9 — The FName display-casing question is unresolved at the engine level.** SP-1 records it:
the contract no longer depends on the answer, but the underlying semantics were not established
from shipped sources. Disposition: open engine-semantics question, documented, no reliance.

**U10 — This review is not independent.** It was written by the same agent that produced
Revision 2. Per the standing gate convention, a design milestone must not self-clear.
Disposition: the revised head requires an independent re-gate before implementation.

---

## 5. Final verdict

**HOLD**

Reasons, in order of weight:

1. **Self-review cannot supply the required independence.** This review verified the input
   findings against real repository and engine source and remediated all of them, but the
   remediating author is not the independent reviewer the design's own acceptance gate 1
   requires. The rung the process defines here is an independent re-gate on this head, not a
   self-clearance.
2. **One material scope trade-off requires independent acceptance.** U1 (complete-scope
   precondition) materially narrows which worlds v1 can extract from. It is defensible, it is
   documented, and it is the only mechanism found that removes the F3 ambiguity — but it is a
   scope decision that a reviewer must accept explicitly rather than inherit.
3. **One live-gate precondition does not exist in the tree yet** (U6: no entity-tagged
   `ALevelSequenceActor` fixture), and one bound is unmeasured (U8). Neither blocks the design,
   both block an immediate implementation start without a decision.
4. **The error vocabulary and the JCS domain are contract-level closures** enforced by tests
   rather than by types (U7, §6.4), so the first implementation slice must land the vocabulary
   tests and the vector tests before any consumer exists.

What is **not** a reason to hold: the eleven confirmed and four partially confirmed input
findings are all resolved explicitly in the design text, and no finding was dismissed,
downgraded without evidence, or "fixed" by expanding scope. All seven second-pass defects the
remediating author introduced were found and removed in the same revision.

**Implementation remains unauthorized.** Explicitly NOT authorized by this document: the C++
extractor, Python extraction code, any change to the transport, to M4–M10, to M12.5, or to
`AtlasSequencerIntegrationFixture.cpp`; and merging PR #106.

---

## Appendix A — Reproducing the verification

Repository evidence (no engine required):

```bash
git -C <repo> show <head>:docs/UNREAL_STATE_EXTRACTION_FIDELITY_V1_DESIGN.md | sed -n '820,930p'
grep -n "_session_identity" planning/unreal_adapter_production.py
grep -n "observed_state" planning/unreal_evidence_digest.py
grep -n "GetWorldContexts" unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Private/AtlasTransportServer.cpp
grep -n "EngineVersion = TEXT" unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Private/AtlasTransportServer.cpp
grep -rn "8785" . --include=*.py --include=*.md
```

Engine evidence (installed UE 5.6.1, no editor launch required):

```bash
E="/c/Program Files/Epic Games/UE_5.6/Engine/Source/Runtime"
sed -n '45,58p' "$E/Core/Public/Math/MathFwd.h"                  # FVector/FQuat are double
sed -n '1860,1883p' "$E/Core/Private/UObject/UnrealNames.cpp"      # FName comparison vs display id
sed -n '973,982p'  "$E/Engine/Private/ActorEditor.cpp"            # IsHiddenEd is derived
sed -n '462,483p'  "$E/Engine/Public/EngineUtils.h"               # TActorIterator level filter
sed -n '48,51p'    "$E/Core/Public/Misc/FrameRate.h"              # FFrameRate::IsValid
sed -n '108,137p'  "$E/Engine/Public/StaticMeshComponentHelper.h" # assigned vs resolved, Nanite
sed -n '114,120p'  "$E/Engine/Public/SkinnedMeshComponentHelper.h"# compiling -> null material
cat "/c/Program Files/Epic Games/UE_5.6/Engine/Build/Build.version" # 5.6.1 vs hardcoded "5.6"
```

No engine process was launched, no test was executed, and no file outside the two documents
named in this task was modified.
