# Unreal State Extraction Fidelity v1 — Revision 2/3 Review

**Status:** REVIEW RECORD — IMPLEMENTATION NOT AUTHORIZED
**Reviews:** `docs/UNREAL_STATE_EXTRACTION_FIDELITY_V1_DESIGN.md` at Revision 2 (§1–§5) and at
Revision 3 (§6)
**Branch:** `feat/unreal-state-extraction-fidelity-v1-design` (PR #106, draft)
**Author of this review:** the remediating agent (not an independent reviewer)
**Input to this review:** (a) the prior independent architectural red-team verdict **BLOCK**,
delivered as findings F1–F15 plus canonicalization and determinism directives; and (b) a second
architectural review pass delivered as eleven priority areas (P1–P11), classified in §6.1

This document records (1) the verification of every input finding against the repository and
the installed UE 5.6 engine source, (2) the design changes those findings produced, (3) the
second-pass hostile review of the revised design, (4) what remains unresolved, and (5) one
verdict token per revision.

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

## 5. Revision 2 verdict (historical)

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

## 6. Revision 3 — architectural review remediation and third-pass review

### 6.1 Classification of the architectural review's priority areas

Verified against the repository and the installed UE 5.6 source; every row carries the evidence
that decided it. **C** = CONFIRMED, **P** = PARTIALLY CONFIRMED, **F** = FALSE POSITIVE.

| Area | Claim | Class | Evidence and decision |
|---|---|---|---|
| **P1** entity-ID case contradiction | Revision 2 could produce different payloads, and therefore different digests, for the same source actor when the caller changes ID casing, while the digest is declared to exclude the request | **C** | Revision 2 §3.3.3.6 read "`entity_id` … is the requested (canonical) ID verbatim" while §6.5 declared the digest excludes the request. `cam01` and `CAM01` are the same `FName` (case-insensitive comparison, `NameTypes.h:573,762-765`) so both bind the same actor, yet the tree recorded the caller's spelling. **Design defect, now fixed by canonicalisation (§3.3.4).** |
| **P1a** FName numeric-name semantics | `foo_1` / `foo_01` / `foo` might be comparison-equivalent through the engine's numbered-name handling | **P** | The engine *does* split a trailing `_<digits>`: `FName(string)` → `FNameHelper::MakeDetectNumber` (`UnrealNames.cpp:3411-3417`) → `ParseNumber` (`:3169-3199`), with the number stored as `NAME_EXTERNAL_TO_INTERNAL(n)=n+1` (`NameTypes.h:153`) against `NAME_NO_NUMBER_INTERNAL 0` (`:149`), and compared as part of `FName::operator==` (`:762-765`, `ToUnstableInt` `:1176-1183`, `UE_FNAME_OUTLINE_NUMBER 0` per `:38`). **But the three spellings are NOT equivalent:** `foo_01` is blocked from splitting by the leading-zero rule, so it stays an unnumbered name; and `foo` (no number) ≠ `foo_1` (base `foo`, number 1). The hypothesis as stated is refuted; the real hazards are different and are now closed: identity is the (base, number) pair, not the string; `FName::IsEqual(..., bCompareNumber=false)` (`:759-762`) is number-blind; `GetTypeHash(FName)` is index-only under the outline-number configuration (`:1310-1312`); and any string round-trip re-parses a rendered tag. All four are forbidden in §3.3.3 and tested in §7.4 D15. |
| **P2** material component type contract | The component set is every `UMeshComponent` while the state machine uses `GetStaticMesh()`/`GetSkinnedAsset()` and class-specific behaviour — broader than the API supports | **C** | Shipped 5.6 defines dozens of `UMeshComponent` subclasses with different material models: `UWidgetComponent` (overrides `GetNumMaterials` **and** `GetMaterial`; `UMG/…/WidgetComponent.h:94,117,119`), `UProceduralMeshComponent` (overrides `GetNumMaterials`; `ProceduralMeshComponent.h:149,307`), `UBaseDynamicMeshComponent` (overrides both; `GeometryFramework/…/BaseDynamicMeshComponent.h:125,667,668`), `UGeometryCollectionComponent` (`:577`), `UHeterogeneousVolumeComponent` (`:20`), plus Paper2D, Groom, Water, Cable, CustomMesh, GeometryCache, Lidar and the editor drawing components. None exposes `GetStaticMesh()`/`GetSkinnedAsset()`, so a generic state machine is not implementable. **Option A adopted** (§3.8.1): the `UStaticMeshComponent` and `USkinnedMeshComponent` families only; anything else registered fails closed with `ERR_EXTRACTION_UNSUPPORTED_COMPONENT_TYPE`. Descendants of those two roots are accepted because they inherit the model (checked: `UInstancedStaticMeshComponent`, `USplineMeshComponent`, `ULandscapeNaniteComponent` declare no material-API override). |
| **P3** source fact vs request-derived data | Some payload fields may be request-derived while the digest excludes the request | **C** | Two were: `entity_id`/`parent.entity_id`/sequence `entity_id` (P1) and `extraction_kind` (copied from the request). Both are now derived — identity from the matched binding, kind from the populated collection (§4.5). The full payload is classified field by field in §4.6, with the new rule that a request defines extraction **scope**, not identity (§4.6.1). Remaining non-source entries are declared: execution metadata (`derived_from_gis_editor`) and implementation metadata (`extraction_schema_version`, `selection_provenance`, `source_component_type`, `unrecorded_hidden_inputs`). |
| **P4** world scope stability | The scope could change between the check and the actor scan, so the payload might claim a scope that was not the one scanned | **C** | Revision 2 checked the predicate and then re-queried the world for the scan, with no snapshot and no revalidation. Supporting facts: `ULevel::Actors` is a public `TArray` that can hold null slots between removal and compaction (`Level.h:426-432`; `Level.cpp:833,1223`); `UWorld::GetStreamingLevels()` is the full list (`World.h:1026`) while `StreamingLevelsToConsider` is a private subset (`World.h:988-993`) and `UActorContainer::Actors` is a hash-ordered `TMap` (`Level.h:78-80`); a material read can trigger `ConditionalPostLoad` (`StaticMeshComponentHelper.h:126-127`). **Fixed** by snapshot → scan → revalidate with `ERR_EXTRACTION_SCOPE_CHANGED`, explicit null-slot and null-streaming-level rules, and a ban on the narrowed containers (§3.2.1.4–5). |
| **P5** double bit encoding | The canonical bit representation may be implicitly host-endian, and the non-finite handling may be incomplete | **P** | The Revision 2 formulation was already value-correct, but it did not *say* so. Measured on the project interpreter: `1.0` yields `3ff0000000000000` under `<`, `>` and `=` packing alike, so the *integer* is endian-neutral; the only wrong form is a mismatched pair, e.g. `struct.unpack(">Q", struct.pack("<d", 1.0))` → `000000000000f03f`. Revision 2 also named `struct.unpack("<Q", struct.pack("<d", v))` without stating why it is correct. **Fixed** by defining the canonical value as the integer value of the bit pattern, naming the counter-example, and adding a fixed vector table (§5.2, §7.4 D20). NaN handling: Revision 2 said non-finite fails closed; Revision 3 additionally refuses quiet *and* signaling NaN by the same `isnan` test and states that NaN payload bits are never encoded (§5.5). |
| **P6** material source/resolution semantics | Two materially different engine states might produce the same canonical material record | **C** (one real collision) | With Revision 2's assigned/resolved pair, the states (override `A`, asset slot `B`) and (override `A`, asset slot `C`) produced **identical** records even though the mesh asset's source state differs, because `resolved` is `A` in both and the asset slot was not recorded. **Fixed** by recording `asset_slot_material_asset_path` and `override_material_asset_path` as source facts beside `resolved_material_asset_path` (§3.8.2, tested by §7.4 D17). The other pairs checked are either distinct (null mesh vs zero slots; Nanite-substituted vs unresolved) or intentionally equivalent and now declared: a null override entry behaves exactly like an absent one, and override entries beyond `GetNumMaterials()` are not slots. |
| **P7** Sequencer read-only semantics | The Sequencer reads may have side effects (lazy loading, player creation, dirtying) | **C** | Verified from source: `ALevelSequenceActor::GetSequence()` is `return LevelSequenceAsset;` (`LevelSequenceActor.cpp:332-335`); `GetSequencePlayer()` is `return SequencePlayer;` (`:145-150`) and does **not** lazily create a player; `ULevelSequence::GetMovieScene()` is `return MovieScene;` (`LevelSequence.cpp:733-736`); `UMovieScene::GetPlaybackRange/GetTickResolution/GetDisplayRate` are member reads (`MovieScene.h:801,809-812,822-825`); path resolution loads nothing. The mutating counterparts (`SetSequence` `:337-347`, `InitializePlayer`/`InitializePlayerWithSequence` `LevelSequenceActor.h:304-307`, `SetPlaybackRange` `MovieScene.h:998,1007`, `MovieScene->Modify()`) are excluded. The only read-path effect in the whole extraction is the material helper's `ConditionalPostLoad()`, now declared as an engine object-graph/lazy-load effect and distinguished from persistent editor-state mutation (§3.8.3.6, §10.3). |
| **P8** read-only architectural boundary | "Do not call write functions" is insufficient when one translation unit contains both halves | **C** | `AtlasTransportServer.cpp` (3105 lines) mixes reads with `set_actor_*` (`:665-679`), `apply_*_variant` (`:687-711`), `set_sequencer_playback_range` (`:763`), render submission, and mutation primitives `SetTaggedVariantName` (`:68-79`), `MarkPackageDirty` (`:78,1062,1234`), `Modify()` (`:764,1219,1539`), `UPackage::SavePackage` (`:1073,1252`), `NewObject<…>` (`:1582`). **Fixed** by §10.2: own translation unit, one-way dispatch, engine-accessor allowlist, and a source-level forbidden-token test (precedent: `tests/m10/test_m10_defect_d2_sequence_range.py:74-102` asserts C++ source text). |
| **P9** canonicalization review | The parser may admit values the canonicalizer rejects, and Python-specific traps (bool/int, duplicates, surrogates) may be unhandled | **C** | Measured on Python 3.11.16: duplicate keys silently last-win (`{"a":1,"a":2}` → `{"a":2}`); `NaN` and `Infinity` tokens are accepted by default; a lone surrogate survives `json.dumps(..., ensure_ascii=False)` and then fails UTF-8 encoding with `UnicodeEncodeError: surrogates not allowed`; `isinstance(True, int)` is `True` while `type(True) is int` is `False`; integers are unbounded (`100000000000000000000000` parses) while the C++ side is int32. **Fixed** by the hardening table in §6.4 (parser hooks plus validation rules) and §7.4 D19. Surrogate pairs were checked and need no special case. |
| **P10** digest collision audit | A systematic state-collapse attack over every category | **C** (one collision) | Full pair-by-pair audit in §6.3. Exactly one unintended same-tree collision was found (the material asset slot, P6). Every other pair is either a different tree, a rejection, or a declared intentional equivalence. |
| **P11** implementation-readiness test | Two engineers could implement some requirements differently while both claiming compliance | **C** | Roughly a dozen such requirements were found (recomputing `IsHiddenEd`, uppercasing semantics, rate reduction, component enumeration, skip predicate, scope multiplicity, object-path collation, tag comparison, hex formatting, digest placement, kind derivation, inventory ordering). All are now frozen decisions in §17, classified as architectural or frozen implementation detail. |

**Totals: 10 CONFIRMED, 2 PARTIALLY CONFIRMED (P1a numeric names, P5 encoding), 0 FALSE POSITIVE.**
No area was dismissed.

### 6.2 Third-pass findings (hostile review of Revision 3 by its own author)

Findings the architectural review did not raise, found while re-attacking the revised text:

| # | Finding | Disposition |
|---|---|---|
| T1 | Revision 2's SP-1 removed the tag's stored casing *because* it is unprovable, and then item 6 kept the caller's spelling as the identity — an internal inconsistency between two adjacent rules in the same section. | Fixed by R3-1 (canonicalisation); the contradiction is gone because identity is now derived from the binding's comparison class. |
| T2 | Revision 2 §7.4 rejected a duplicate (`level_package_path`, `level_kind`) pair in the scope. Two streaming instances of one package are a legal world, so that rule was a **false refusal** — the opposite failure mode from a lossy collapse, and equally a defect. | Fixed: duplicates permitted and each instance recorded (§3.2.1.6, D16). |
| T3 | Revision 2's rule "components that override the slot model … are recorded as the generic `UMeshComponent` contract reports them" described behaviour the API cannot produce (no generic asset accessor exists). | Fixed by the class scope of §3.8.1; the claim is replaced with fail-closed behaviour. |
| T4 | Revision 2 had no rule for null actor slots in `ULevel::Actors` or for a null streaming-level entry — an implementation would have had to guess (skip, crash, or fail). | Frozen: skip `!IsValid()` actor slots; fail closed on a null streaming-level entry (§3.2.1.5). |
| T5 | Revision 2 did not say whether frame-rate pairs may be reduced to lowest terms, although `{60,2}` and `{30,1}` are numerically equal and textually different. | Frozen: verbatim, never reduced (§3.9.3.6). |
| T6 | Stale cross-references: §3.1.1/§4.2 pointed at "§3.10" and §7.4 at "§3.3.3.2", neither of which exists in the document. | Fixed by renumbering and re-pointing. |
| T7 | The number-blind comparison API `FName::IsEqual(Other, ENameCase, bCompareNumber)` was not mentioned anywhere, although it silently equates `foo_1` with `foo`. | Fixed: explicitly forbidden with its citation (§3.3.3). |
| T8 | `GetTypeHash(FName)` is index-only under the outline-number configuration, so a container keyed on it would not distinguish numbered names. | Fixed: keying on the hash is forbidden (§3.3.3). |
| T9 | The `world_type` leaf was specified as the lowercase literal with no anchored source, leaving "lowercase of what?" open. | Frozen: ASCII-lowercased `LexToString(World->WorldType)` (§17). |
| T10 | Revision 2's material state machine had a `slot_state` enum whose values were derivable from, and could contradict, the neighbouring path fields. | Fixed: the enum is removed; the record now carries the source facts plus the resolved value, and Python asserts consistency. |

### 6.3 Collision audit (state-collapse attack, priority 10)

Two materially different engine states are compared per category. "Different tree" means the
canonical bytes differ; "rejected" means the second state fails closed.

| Category | State A → State B | Result |
|---|---|---|
| world | same world extracted in two sessions | **same tree** (intended: reproducibility) |
| world | same content, different engine build/changelist | **different tree** (engine identity is digested, intended) |
| world | `EWorldType::Editor` world vs `Inactive`/PIE/preview context | **rejected** (`ERR_EXTRACTION_WORLD_NOT_EDITOR`) |
| world | non-partitioned world vs partitioned world | **rejected** (`ERR_EXTRACTION_WORLD_PARTITION_UNSUPPORTED`) |
| level scope | all streaming levels loaded+visible vs one unloaded | **rejected** (`ERR_EXTRACTION_LEVEL_SCOPE_INCOMPLETE`) — never a silent same-tree |
| level scope | scope unchanged before/after the scan vs changed | **rejected** (`ERR_EXTRACTION_SCOPE_CHANGED`) |
| level scope | one package loaded once vs loaded twice | **different tree** (two entries; no refusal) |
| level scope | null entry in the streaming-level array | **rejected** (`ERR_EXTRACTION_LEVEL_SCOPE_INVALID`) |
| actor identity | request `cam01` vs `CAM01` for one actor | **same tree** (after R3-1; this was the P1 defect) |
| actor identity | request `cam_1` vs `cam_01` (tags for both exist) | **different tree** (distinct bindings; §7.4 D15) |
| actor identity | one actor renamed (same tag, new object name) | **different tree** (provenance; intended, §3.4.1) |
| actor identity | two actors carrying case-variant tags | **rejected** (`ERR_EXTRACTION_ENTITY_AMBIGUOUS`) |
| actor identity | one actor carrying two distinct entity tags | **rejected** (`ERR_EXTRACTION_ENTITY_TAG_CONFLICT`) |
| parent | no parent vs parent with no entity tag | **different tree** (`none` vs `unbound`, locator recorded) |
| parent | two different unbound parents | **different tree** (locator differs) |
| parent | parent with two distinct entity tags | **rejected** (`ERR_EXTRACTION_PARENT_TAG_CONFLICT`) |
| visibility | `bHiddenEd` / `bHiddenEdLayer` / `bHiddenEdLevel` / temporary flag toggled | **different tree** (raw flags recorded) |
| visibility | only `bEditable` changed, aggregate unchanged | **same tree** — *intentionally omitted, declared in-band* (`unrecorded_hidden_inputs`) |
| visibility | `GIsEditor` differs (editor vs commandlet) | **different tree** (`derived_from_gis_editor`, plus a possibly different aggregate) |
| transform | `q` vs `-q`; `+0.0` vs `-0.0` | **different tree** (both distinct by contract) |
| transform | NaN / ±Inf at the source | **rejected** (`ERR_EXTRACTION_NON_FINITE`) |
| transform | a delta below binary64 resolution (identical doubles) | **same tree** — *intentionally equivalent* (the engine stores the same value) |
| transform | magnitude above `FLT_MAX` | **different tree**, no saturation (no narrowing) |
| material | override `A` + asset slot `B` vs override `A` + asset slot `C` | **different tree** (R3-6; was the P6 collision) |
| material | null override entry vs absent override entry | **same tree** — *intentionally equivalent* (engine behaviour identical) |
| material | mesh asset absent vs mesh asset with zero slots | **different tree** (`mesh_state`, `mesh_asset_path`) |
| material | skinned asset mid-compilation | **rejected** (`ERR_EXTRACTION_MESH_COMPILING`) |
| material | unsupported `UMeshComponent` subclass present | **rejected** (`ERR_EXTRACTION_UNSUPPORTED_COMPONENT_TYPE`) |
| material | non-mesh primitive (e.g. decal) present vs absent | **different tree** (`omitted_material_components`) |
| material | one non-mesh primitive vs two of the same class | **different tree** (`count`) |
| material | two non-mesh primitives of the same class vs a different pair of the same class | **same tree** — *intentionally omitted, declared* (not enumerated) |
| material | dynamic/transient material instance; unstable asset path | **rejected** (`ERR_EXTRACTION_UNSUPPORTED_MATERIAL_SOURCE`, `ERR_EXTRACTION_MATERIAL_UNRESOLVED`) |
| Sequencer | explicit `ALevelSequenceActor` binding vs a non-sequence actor | **rejected** (`ERR_EXTRACTION_SEQUENCE_ACTOR_TYPE`) |
| Sequencer | open playback bound; degenerate range; invalid rate; transient sequence asset | **rejected** (four distinct codes) |
| Sequencer | same range, different tick resolution or display rate | **different tree** |
| Sequencer | `{60,2}` vs `{30,1}` for a rate | **different tree** (verbatim, not reduced) |
| Sequencer | two candidate sequence actors for one entity | **rejected** (`ERR_EXTRACTION_ENTITY_AMBIGUOUS`) |

Classification of the *same-tree* rows, as required: reproducibility rows are intended
equivalences at the engine-state level; the `bEditable` row and the non-mesh-primitive
multiplicity row are **intentionally omitted state, declared in-band**; there is no remaining
row that is an accidental loss. Rejections are not collapses: they are fail-closed refusals,
which is the contract's chosen failure mode for states v1 does not model.

### 6.4 Changes made in Revision 3

R3-1 … R3-14, tabulated with their sections in the design document's §15 change log. In summary:
canonical identity and the engine's `FName` model (§3.3.3–3.3.5); the closed material component
scope and the declared omission inventory (§3.8.1, §3.8.1a); material source facts beside the
resolved value (§3.8.2); scope snapshot and revalidation (§3.2.1); endian-neutral bit encoding
and complete non-finite handling (§5.2, §5.5); declared read-path effects and the verified
Sequencer read path (§3.8.3.6, §10.3); architectural separation (§10.2); parser hardening
(§6.4); field provenance, content-derived `extraction_kind`, and the scope-versus-identity rule
(§4.5, §4.6); verbatim rates (§3.9.3.6); and the frozen implementation-readiness decisions
(§17). Tests D14–D20 were added and acceptance gates 14–17.

### 6.5 Remaining unresolved issues (carried into Revision 3)

Carried from Revision 2, still open, with the same dispositions: **U1** the complete-scope
precondition refuses worlds with an unloaded or hidden streaming level (scope trade-off needing
explicit acceptance); **U2** `bEditable` is unreadable, so `hidden_in_editor` is not fully
decomposable; **U3** no per-class material semantics (now fail-closed for mesh classes and
declared for non-mesh primitives); **U4** component identity is a mutable locator for
runtime-named components; **U5** digests legitimately differ across engine builds; **U6** the
entity-tagged `ALevelSequenceActor` fixture does not exist yet; **U7** the error vocabulary is
closed by contract and tests, not by types; **U8** the practical payload-size limit is unmeasured
(the gate now records sizes); **U9** the `FName` display-casing question is not fully determined
from shipped sources (the contract no longer depends on it); **U10** this review is self-authored
and cannot substitute for independent review.

New in Revision 3:

- **U11** The closed material class scope means an engine release that adds a new
  `UMeshComponent` subclass (or promotes a class out of the supported subtrees) turns formerly
  extractable actors into fail-closed refusals. This is the intended direction (fail closed
  rather than half-model), but it is an operator-visible behaviour change tied to engine
  upgrades, and an implementer should surface it in the error text.
- **U12** `omitted_material_components` is an inventory, not an enumeration: two different
  non-mesh material-bearing components of the same class are indistinguishable. Declared, not
  hidden.
- **U13** The architectural separation of §10.2 is enforced by a source-text test plus an
  allowlist, so it proves the *absence of named mutation calls in our own source*. It cannot
  prove that no engine accessor on the read path mutates state internally; the live gate's
  dirty-state measurement is the empirical complement. Neither alone is a proof, and the design
  says so rather than claiming a stronger property.
- **U14** The scan depends on `ULevel::Actors` being the array that holds a level's actors (it is
  documented as the array used by the engine's own actor iterators, `Level.h:431-432`). A future
  engine change to actor storage (for example external-package-only actors) would require a
  design revision; the contract pins the accessor, not the engine's internals.

### 6.6 Final remediation status (Revision 3)

**HOLD**

Rationale, in order of weight:

1. **Independence.** This remediation was performed and reviewed by one agent (U10). All ten
   confirmed and two partially confirmed areas are closed with source evidence and no finding was
   dismissed, but a self-review cannot supply the independent CLEAR that acceptance gate 1
   requires.
2. **One scope trade-off needs a decision** (U1): v1 refuses any world with an unloaded or hidden
   streaming level. The mechanism is documented and defensible; the acceptance is the reviewer's.
3. **Three items need an operator or architect decision before implementation** (U6, U11, U13),
   and two are declared limitations that should be acknowledged rather than inherited (U12, U14).
4. **Implementation readiness is asserted, not proven.** §17 freezes the decisions where two
   engineers could diverge, and gates 14–17 make the claims testable — but they are obligations
   on the implementation rung, so the design's own status cannot be CLEAR before those tests
   exist and pass.

What is **not** a reason to hold: the review's ten confirmed areas are all closed in the text,
the two partially confirmed ones are refuted-or-refined with citations, the single real digest
collision is removed, and no finding was resolved by expanding scope — World Partition, chunked
transport, forced level loading, generic mesh support, source repair and semantic interpretation
are all explicitly refused instead.

**Implementation remains unauthorized.** Explicitly not authorized by this document: the C++
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

## Appendix B — Reproducing the Revision 3 verification

`FName` identity and numbered names (priority 1, area P1/P1a):

```bash
E="/c/Program Files/Epic Games/UE_5.6/Engine/Source/Runtime"
sed -n '3411,3417p' "$E/Core/Private/UObject/UnrealNames.cpp"   # FName(str) -> MakeDetectNumber
sed -n '3169,3199p' "$E/Core/Private/UObject/UnrealNames.cpp"   # ParseNumber: the '_<digits>' split
sed -n '3605,3621p' "$E/Core/Private/UObject/UnrealNames.cpp"   # rendering: base + "_" + number
sed -n '145,156p'   "$E/Core/Public/UObject/NameTypes.h"        # NAME_NO_NUMBER_INTERNAL / EXTERNAL_TO_INTERNAL
sed -n '757,770p'   "$E/Core/Public/UObject/NameTypes.h"        # IsEqual(bCompareNumber) vs operator==
sed -n '1176,1183p' "$E/Core/Public/UObject/NameTypes.h"        # ToUnstableInt (number in equality)
sed -n '1308,1330p' "$E/Core/Public/UObject/NameTypes.h"        # GetTypeHash(FName), index-only variant
sed -n '36,40p'     "$E/Core/Public/UObject/NameTypes.h"        # UE_FNAME_OUTLINE_NUMBER default
```

Material component families (priority 2, area P2):

```bash
E="/c/Program Files/Epic Games/UE_5.6/Engine"
grep -rn "public UMeshComponent" "$E/Source/Runtime" "$E/Plugins" | sed 's|.*/Engine/||'
grep -n "GetNumMaterials\|GetMaterial(" \
  "$E/Plugins/Runtime/ProceduralMeshComponent/Source/ProceduralMeshComponent/Public/ProceduralMeshComponent.h" \
  "$E/Source/Runtime/UMG/Public/Components/WidgetComponent.h" \
  "$E/Source/Runtime/GeometryFramework/Public/Components/BaseDynamicMeshComponent.h"
grep -n "GetNumMaterials\|GetMaterial(" "$E/Source/Runtime/Engine/Classes/Components/SplineMeshComponent.h"
```

Scope stability, containers and actor slots (priority 4, area P4):

```bash
E="/c/Program Files/Epic Games/UE_5.6/Engine/Source/Runtime"
sed -n '1020,1030p' "$E/Engine/Classes/Engine/World.h"   # UWorld::GetStreamingLevels (full list)
sed -n '985,995p'   "$E/Engine/Classes/Engine/World.h"   # StreamingLevelsToConsider (private subset)
sed -n '426,433p'   "$E/Engine/Classes/Engine/Level.h"   # ULevel::Actors (TArray)
sed -n '70,82p'     "$E/Engine/Classes/Engine/Level.h"   # UActorContainer::Actors (TMap)
grep -n "Actors\[ActorIndex\] = nullptr\|Actors.Remove(nullptr)" "$E/Engine/Private/Level.cpp"
sed -n '440,452p'   "$E/Engine/Public/EngineUtils.h"     # SkipPendingKill / IsActorSuitable
```

Sequencer read path (priority 7, area P7):

```bash
E="/c/Program Files/Epic Games/UE_5.6/Engine/Source/Runtime"
sed -n '145,150p;332,347p' "$E/LevelSequence/Private/LevelSequenceActor.cpp"
sed -n '733,736p'          "$E/LevelSequence/Private/LevelSequence.cpp"
sed -n '298,310p'          "$E/LevelSequence/Public/LevelSequenceActor.h"  # InitializePlayer*
```

Python-side hazards and bit vectors (priorities 5 and 9, areas P5/P9):

```bash
python - <<'PY'
import json, struct, math
print(json.loads('{"k":"a","k":"b"}'))          # duplicate key -> last wins (no error)
print(json.loads('[NaN]'), json.loads('{"i":Infinity}'))   # accepted by default
print(isinstance(True, int), type(True) is int)            # bool is an int subclass
s = json.dumps({"a": "\ud800"}, ensure_ascii=False)
try: s.encode("utf-8")
except Exception as e: print(type(e).__name__, e)          # lone surrogate cannot encode
for name, v in [("1.0",1.0),("-0.0",-0.0),("5e-324",5e-324),
                ("FLT_MAX",3.4028234663852886e38),("1e300",1e300)]:
    print(name, f"{struct.unpack('<Q', struct.pack('<d', v))[0]:016x}")
print("mismatched pair", f"{struct.unpack('>Q', struct.pack('<d', 1.0))[0]:016x}")
try: struct.pack("<f", 1e300)
except Exception as e: print("narrow 1e300 ->", type(e).__name__, e)
print("narrow 5e-324 ->", struct.unpack("<f", struct.pack("<f", 5e-324))[0])
PY
```

Transport module separation evidence (priority 8, area P8):

```bash
R="unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Private/AtlasTransportServer.cpp"
grep -n "MarkPackageDirty\|SavePackage\|->Modify()\|SpawnActor\|NewObject<\|SetActor" "$R"
grep -n "^bool FAtlasTransportServer::SetActor\|^bool FAtlasTransportServer::Apply" "$R"
```

Both revisions were verified without launching an engine process and without executing any test;
every claim above is either a source citation or a measurement on the local interpreter.
