# Unreal State Extraction Fidelity v1 — Design Gate

**Status:** DESIGN — IMPLEMENTATION NOT AUTHORIZED
**Design status:** HOLD — an independent architectural review must decide CLEAR; this document's author cannot self-clear it
**Design revision:** Revision 3 — remediation of the architectural review findings, with a third hostile self-review
**Revision 1:** red-team hardening 1 (five material ambiguities closed)
**Branch:** `feat/unreal-state-extraction-fidelity-v1-design`
**Parent:** Atlas `main` at the September 18, 2026 checkpoint
**Relationship to M12.5:** independent and intentionally does not modify M12.5
**Relationship to M4–M10:** render/recovery authority is frozen and untouched

This document is the normative contract. Where Revision 2 changes or narrows Revision 1,
the change is recorded in §15 and justified by repository or engine evidence in
`docs/UNREAL_STATE_EXTRACTION_FIDELITY_V1_REV2_REVIEW.md`. Nothing in this document
authorizes implementation.

---

## 1. Purpose

Atlas already has a useful Unreal read surface (world, actor, material, Niagara,
Blueprint, Sequencer and render-state inspection). Those probes are execution-boundary
operations, not a canonical extraction contract: they are partially first-match,
world-selection-inconsistent, and their payloads carry session metadata.

This milestone defines a bounded, deterministic, read-only Unreal state producer that can
become the authoritative source for future target-state verification and cross-engine
digital-twin reasoning.

The milestone is analogous in architectural role to Blender Extraction Fidelity v1. It is
Unreal-specific and makes no cross-engine equivalence claim.

Extraction v1 answers exactly one question:

> What did this Unreal editor world contain, as source facts, for this explicit, bounded
> set of Atlas entities, at the moment of the request?

---

## 2. Authority and trust boundary

### 2.1 Authority chain

```text
Real Unreal editor state
    ↓
C++ read-only extraction producer   (untrusted input to Atlas)
    ↓
extraction value tree               (closed schema, §4)
    ↓
Python structural validation        (fail-closed; NOT verification)
    ↓
RFC 8785 canonical bytes + SHA-256  (identity/integrity value, §6)
    ↓
future consumers (M12.5 and beyond) — RESERVED, NOT IMPLEMENTED
```

### 2.2 The extraction result is untrusted input

The C++ extraction result is **untrusted input**. This is the existing Atlas boundary rule,
not a new one: `planning/unreal_transport_contract.py:6-11` states "Both sides validate
independently; neither trusts the other" and "Responses never carry a `verified` flag —
Atlas verifies independently".

Consequences:

1. Python MUST validate the extraction structure against the closed schema (§4) before any
   other use. Validation failure is a hard failure.
2. Python MUST NOT treat a transport `success` flag, an HTTP-like status, or a
   well-formed payload as evidence that the payload is *correct* or *sufficient*.
3. Python MUST independently reconstruct the digest input from the validated value tree; the
   C++ serializer is never the digest authority (§6.5).

### 2.3 A digest is not a verdict

An extraction digest is an **identity/integrity value**, not a verification verdict.

- It MUST NOT be used to set, imply, or substitute `UnrealEvidence.verified`.
- `planning/unreal_evidence_contract.py:267-268` states the existing invariant: only
  `verify_render_job_evidence()` with an authoritative `AtlasRenderJobRecord` may construct
  verified evidence. Extraction MUST NOT become a second producer of verified evidence.
- Extraction MUST NOT emit a receipt, a recovery record, a durable record, or a
  verification result of any kind.

### 2.4 No second verification authority

- Extraction MUST NOT replace `planning/target_state.py::TargetStateEvaluator`
  (`planning/target_state.py:50-77`). The extractor declares no invariants, returns no
  `satisfied`/`failed` decision, and takes no expected state.
- Extraction MUST NOT become M12.5. `planning/m12/target_state.py` remains a data-only
  descriptor (`planning/m12/target_state.py:1-13,21-92`) and is not modified, consumed, or
  produced by extraction.
- The future seam is **reserved and not implemented**: a future M12.5 verifier may consume a
  validated extraction value tree as one input to invariant evaluation. v1 defines no
  invariant name, no comparison rule, no target state, and no verdict.
- `docs/ATLAS_ARCHITECTURE_CONTRACT.md:23` — "A successful transport or executor response is
  never equivalent to successful target-state verification" — is binding on this milestone.
- `docs/ATLAS_ARCHITECTURE_CONTRACT.md:176-187` (non-regression rules) is binding: preserve
  the evidence ledger, preserve independent verification, do not add a parallel execution
  model.

### 2.5 Prohibitions

The extractor MUST NOT:

- authorize a task;
- execute writes of any kind;
- submit or retry a render;
- issue receipts or verification results;
- alter recovery state or any durable record;
- save packages/assets, mark packages dirty, or modify the transaction buffer;
- mutate Actors, components, sequences, materials, Niagara systems, Blueprints, levels, or
  world state;
- load, unload, or force-visibility of a level;
- create, rename, or destroy any object.

Extraction is a pure read. It executes under the existing authorization/transport contract
like any other read operation; doing so grants it no authority.

---

## 3. v1 extraction scope

### 3.1 Authoritative editor world selection

The v1 authority is the Unreal **editor** world only.

The extractor MUST:

1. require an editor build with `GEditor` available;
2. obtain the world exclusively from `GEditor->GetEditorWorldContext().World()`;
3. reject a null or invalid world (`ERR_EXTRACTION_WORLD_UNAVAILABLE`);
4. require `World->WorldType == EWorldType::Editor`, naming the engine enum value explicitly
   (`Engine/Classes/Engine/EngineTypes.h:1222-1249`: `None, Game, Editor, PIE,
   EditorPreview, GamePreview, GameRPC, Inactive`), and reject every other value —
   including `Inactive` ("an editor world that was loaded but not currently being edited in
   the level editor") and `EditorPreview` — with `ERR_EXTRACTION_WORLD_NOT_EDITOR`;
5. require `World->IsPartitionedWorld() == false` (`Engine/Classes/Engine/World.h:2805,2818`)
   and otherwise fail closed with `ERR_EXTRACTION_WORLD_PARTITION_UNSUPPORTED` (§3.2);
6. NOT consult `GEngine->GetWorldContexts()` for world selection, in any form.

The payload records `selection_provenance` as the literal contract value
`g_editor_editor_world_context`.

#### 3.1.1 Existing world selection MUST be replaced, not reused

The existing tree contains three mutually inconsistent, order-dependent world selections.
The extractor MUST NOT use any of them:

| Site | Behaviour | Verdict |
|---|---|---|
| `AtlasTransportServer.cpp:81-100` anonymous `GetActiveEditorWorld()` | prefers `GEditor->GetEditorWorldContext().World()`, then **falls back to the first valid entry of `GEngine->GetWorldContexts()`** | replaced |
| `AtlasUnrealTransport.cpp:149-173` duplicate `GetActiveEditorWorld()` | identical fallback, second copy | replaced |
| `AtlasTransportServer.cpp:2300-2303` `FindActorByEntityId` | selects `GEngine->GetWorldContexts()[0].World()` — a *different* world than either helper — and returns the **first** tag match | replaced |
| `AtlasTransportServer.cpp:779-790` `InspectWorld` | scans contexts and takes the last valid one, preferring `EWorldType::Editor` | not extraction-relevant |

The divergence is real and observable: the harness provisions its fixtures into
`GetActiveEditorWorld()` (`AtlasUnrealTransport.cpp:207`) while entity lookup walks
`GetWorldContexts()[0]`. v1 removes the divergence by construction: one world, obtained one
way, validated against an explicitly named enum value.

This is a contract decision, not "reuse or refine". `inspect_world`, `inspect_target_actors`,
`inspect_material_state`, `inspect_sequencer_state` and the other M4–M10 probes remain
**frozen and unmodified**; the extraction operation is new (§10.1) and does not call them.

#### 3.1.2 Engine identity is sourced, never hardcoded

The world record carries engine identity as extraction facts, sourced from the engine:

- `engine_version` = `FEngineVersion::Current().ToString(EVersionComponent::Patch)`
  (`Core/Public/Misc/EngineVersion.h:34,40`);
- `engine_build_version` = `FApp::GetBuildVersion()` (`Core/Public/Misc/App.h:73`).

The transport's `FString EngineVersion = TEXT("5.6")`
(`AtlasTransportServer.cpp:120`, surfaced through `session_identity.engine_version` at
`AtlasTransportServer.cpp:2322,2331`) is a **hardcoded legacy literal and MUST NOT be the
source** of any extraction fact. This is not a theoretical objection: the host install
reports `MajorVersion 5 / MinorVersion 6 / PatchVersion 1 / Changelist 44394996 /
BranchName ++UE5+Release-5.6` (`UE_5.6/Engine/Build/Build.version`), so the legacy literal
`"5.6"` is already known to disagree with the engine's own version on the reference host.
Repairing the transport literal is explicitly **out of scope** (transport is frozen); the
extraction records the engine's own values instead.

Engine identity participates in the digest. Two byte-identical worlds extracted by two
different engine builds therefore produce different digests. This is intended: the value
tree is a source-fidelity record of what *this binary* reported (§5.4), and diffing across
engine builds is a legitimate use of the digest.

### 3.2 Level scope — loaded-world determinism

The same world identity can yield different visible entity sets depending on level load and
visibility state. `TActorIterator`'s default flags are `OnlyActiveLevels | SkipPendingKill`
(`Engine/Public/EngineUtils.h:509`), and with `OnlyActiveLevels` a level is iterated only if

```text
(bIsVisible && !bIsBeingRemoved) || bIsAssociatingLevel || bIsDisassociatingLevel
```
and its level collection is the world's active collection or of type `StaticLevels`
(`EngineUtils.h:462-483`, using `ULevel::bIsVisible`, `bIsBeingRemoved`,
`bIsAssociatingLevel`, `bIsDisassociatingLevel` — `Engine/Classes/Engine/Level.h:600,644,646,656`).

So an unloaded or hidden streaming level, or a level mid-association, changes the entity set
that a World-scanning lookup can see. v1 MUST NOT inherit that.

#### 3.2.1 The v1 scope rule (normative)

1. **Precondition — complete loaded-visible scope.** Every entry of
   `World->GetStreamingLevels()` (`World.h:1026`) MUST satisfy
   `IsLevelLoaded() && IsLevelVisible()` (`Engine/Classes/Engine/LevelStreaming.h:588,584`).
   Otherwise the extraction fails closed with `ERR_EXTRACTION_LEVEL_SCOPE_INCOMPLETE`.
2. **Partitioned worlds are refused.** `World->IsPartitionedWorld()` MUST be false, else
   `ERR_EXTRACTION_WORLD_PARTITION_UNSUPPORTED`. v1 does not model World Partition cells,
   external actor packages, or cell streaming state; it refuses such worlds rather than
   reporting a load-state-dependent entity set.
3. **No force-loading.** The extractor never loads, unloads, or makes a level visible. A world
   that is not in the required state is not "prepared" by the extractor; it is refused.
4. **Explicit level set, snapshotted once, revalidated after the scan.** Entity binding scans
   exactly the union of `ULevel::Actors` (`Engine/Classes/Engine/Level.h:426-432`, the public
   array documented as the one used by the actor iterators) over the scope levels: the persistent
   level, plus every streaming level that is loaded and visible. The extractor MUST:

   a. **snapshot** the scope once — the ordered list of `ULevel*` for the persistent level and for
      every streaming level that passes the predicate of item 1 — and perform the actor scan over
      that snapshot, never over a re-query;
   b. **revalidate** the snapshot after the scan, re-evaluating the item-1 predicate and requiring
      the same level set (same levels, same loaded and visible values) before any payload is built.
      Any difference fails closed with `ERR_EXTRACTION_SCOPE_CHANGED`;
   c. **never** produce a payload whose recorded scope was not the scope actually scanned. The
      forbidden shape is exactly: *scope checked = A, actor scan performed under scope B, payload
      claims scope A*.

   The revalidation exists because the read path is not assumed to be side-effect-free: the
   material helpers may trigger an engine-side `ConditionalPostLoad` (§3.8.3.6), and the design
   must not depend on "nothing else touches the world while a game-thread task runs". It costs one
   predicate evaluation and removes an unstated assumption.

   The extractor MUST NOT use `TActorIterator` for binding, because its result then depends on
   engine filter semantics rather than on this contract. It MUST also NOT use the engine's
   *narrowed* containers as the scope source: `UWorld::StreamingLevelsToConsider`
   (`World.h:988-993`, a private, actively-considered **subset**) and `UActorContainer::Actors`
   (`Level.h:78-80`, an `FName`-keyed **`TMap`**, hash-ordered, used for PIE cell duplication)
   are both wrong sources, the latter because its iteration order is not canonical.

5. **Actor-slot predicate.** Within a scope level, the scan iterates `ULevel::Actors` and skips
   every entry that is not `IsValid()`, which covers both a null slot and a pending-kill actor —
   the same policy as the engine's own `EActorIteratorFlags::SkipPendingKill`
   (`Engine/Public/EngineUtils.h:440-445`). Null slots are a legal transient state of the array
   (they are created by actor removal and later compacted, `Engine/Private/Level.cpp:833,1223`),
   so a null slot is **not** an error and is deliberately not represented. A null *streaming
   level* entry is an engine-invariant break and fails closed with
   `ERR_EXTRACTION_LEVEL_SCOPE_INVALID` rather than being skipped.

6. **Scope is recorded.** The payload records the scope levels (canonical order, §7.3). Two
   extractions of the same world identity with different level sets therefore cannot produce
   the same digest. Scope entries are keyed by (`level_package_path`, `level_kind`) and duplicates
   are **permitted**: two streaming instances that resolve to the same package are two levels, and
   the record carries one entry each. Rejecting such a world would be a false refusal, so the
   validator asserts sorted order and the item-1 predicate, not uniqueness of scope entries.

The direct consequence, stated plainly: **v1 cannot extract from a world that has an
unloaded or hidden streaming level.** This is a bounded restriction, not a defect, and it is
the reason the entity-not-found error is free of scope ambiguity (§3.3.3).

### 3.3 Entity identity contract

#### 3.3.1 Source binding convention

The source binding tag is exactly `atlas_entity:<entity_id>` (unchanged from the existing
convention; the harness fixture already carries `atlas_entity:FIELD_SURFACE`,
`AtlasUnrealTransport.cpp:24`). The binding is established on the **canonical** name
`FName("atlas_entity:" + canonical_entity_id)` (§3.3.4), never on the raw request string.

#### 3.3.2 Canonical entity-ID grammar

An entity ID is canonical iff it matches exactly:

```text
^[A-Za-z0-9_.-]{1,64}$
```

ASCII letters, digits, `_`, `.`, `-`; length 1..64; no whitespace, no Unicode, no standalone
`atlas_entity:` prefix. A request containing a non-canonical ID fails closed before
extraction (`ERR_EXTRACTION_REQUEST_INVALID`).

The grammar is not cosmetic. It removes three hazards mechanically:

- **collation ambiguity** — with an ASCII-only ID, UTF-8 byte order, UTF-16 code-unit order,
  C++ `FString` order and Python `str` order coincide, so the canonical sort key is
  unambiguous across languages (§7.3);
- **Unicode normalization ambiguity** — nothing to normalize;
- **FName comparison surprises are bounded and modelled** — the engine's identity is not the raw
  string (§3.3.3), so the contract states the exact model instead of assuming it.

#### 3.3.3 FName identity semantics (normative engine model)

A tag is stored as an `FName`, and `FName` identity is **not** the case-folded string. The
engine's actual model, verified in the installed 5.6 source:

1. **Case is folded.** "Names are case-insensitive, but case-preserving"
   (`Core/Public/UObject/NameTypes.h:573`), and the pool's own equality helper compares with
   `Strnicmp` (`Core/Private/UObject/UnrealNames.cpp:3164`).
2. **A trailing `_<digits>` suffix is parsed into a separate number at construction time.**
   `FName(const TCHAR*)` delegates to `FNameHelper::MakeDetectNumber`
   (`UnrealNames.cpp:3411-3417`), which calls `ParseNumber` (`:3169-3199`). The split happens
   only when the digit run is non-empty, shorter than 10 digits, immediately preceded by `_`,
   and either its length is 1 or its first digit is not `0`; the value must also be below
   `MAX_int32`. The stripped base becomes the comparison name.
3. **The number is part of the name.** It is stored as
   `NAME_EXTERNAL_TO_INTERNAL(n) = n + 1` (`NameTypes.h:153`) so that internal `0` keeps meaning
   "no number" (`NAME_NO_NUMBER_INTERNAL`, `:149-156`), and `FName::operator==` compares
   `ToUnstableInt()` (`:762-765`), which in the default configuration
   (`UE_FNAME_OUTLINE_NUMBER 0`, `:38`) is the full (ComparisonIndex, Number) pair.
4. **Rendering round-trips.** A numbered name renders as `base + "_" + number`
   (`UnrealNames.cpp:3605-3607,3617-3621`), i.e. exactly the spelling it was built from.

Consequences, verified rather than assumed:

- **The identity is the pair (case-folded base, number)**, and for tags built by the string
  constructor that pair is a bijection of the original spelling — so two distinct admitted IDs
  can never collide onto one binding.
- **`foo_1`, `foo_01` and `foo` are three distinct names.** `foo_1` is (base `foo`, number 1);
  `foo_01` is the *unnumbered* name `foo_01` because the leading-zero rule above blocks the
  split; `foo` is (index `foo`, no number). None of the three compares equal to another.
- **A case variant is the same name** (`CAM01` ≡ `cam01`): this is the intended
  case-insensitive binding.
- **A spelled `_N` suffix is not string identity.** `atlas_entity:cam_1` denotes (base
  `atlas_entity:cam`, number 1) while `atlas_entity:cam` denotes (index `atlas_entity:cam`, no
  number): different bindings. A request for `cam_1` must not resolve a tag for `cam`, and a
  request for `cam` must not resolve a tag for `cam_1`.

Implementations that silently change identity, and are therefore forbidden:

- `FName::IsEqual(Other, ENameCase::CaseSensitive, /*bCompareNumber=*/false)` — a **number-blind**
  comparison (`NameTypes.h:759-762`) that equates `foo_1` with `foo`;
- comparing or keying on `GetComparisonIndex()` or `GetTypeHash(FName)` alone — the hash is
  index-only under the outline-number configuration (`NameTypes.h:1310-1312`) and is never the
  identity;
- any **string round-trip** of a tag (`FName(Tag.ToString())`, `id.split("_")`, an `FString`
  assembled from a rendered tag): the (base, number) pair must come from the engine, never from
  re-parsing a rendered string;
- **string comparison of rendered tags** (`Tag.ToString() == Expected`): case-folded string
  equality happens to agree with `FName` equality for every reachable construction path, but it
  is not the engine's comparison, and it silently diverges the moment any spelling-level
  normalisation is introduced.

The extractor MUST compare with `FName` equality (`operator==` / `TArray<FName>::Contains`),
because that is the engine's own comparison class.

#### 3.3.4 Canonical identity representation (request-independence)

The payload MUST NOT carry the caller's spelling. The canonical entity identity is

```text
canonical_entity_id = ASCII-uppercase(requested_id)
```

and it is derived from the **source binding**: the extractor binds on
`FName("atlas_entity:" + canonical_entity_id)` and requires the candidate tag to be `FName`-equal
to that name. Both sides therefore go through the same constructor and the same `ParseNumber`,
so the engine's own parse decides — not any string logic written by the extractor.

Consequently:

1. `entity_id` in the payload is the canonical ID, never the request string;
2. a request for `cam01` and a request for `CAM01` produce byte-identical payloads, identical
   canonical bytes and identical digests for the same source actor;
3. the same rule governs `parent.entity_id` and the Sequencer record's `entity_id`;
4. the normative property this exists to guarantee:

   > The same underlying canonical entity source binding cannot produce different extraction
   > identities solely because the caller changed ID casing or FName spelling.

Uppercase is the chosen representative of the comparison class because the repository's existing
binding convention is uppercase — `atlas_entity:FIELD_SURFACE`
(`unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Private/AtlasUnrealTransport.cpp:24`,
`unreal/AtlasUnrealHarness/Source/AtlasUnrealHarness/AtlasUnrealHarness.cpp:233,239`) — so the
canonical form coincides with the source spelling for every existing Atlas fixture. Because
`FName` comparison is case-insensitive, the representative cannot change *which* actors match; it
changes only the identity the payload reports.

This is a canonicalisation of the **identity**, not a normalisation of source strings: no other
normalisation is performed (§5.7), and the tag's own stored casing is never read (§3.3.5 item 6).

#### 3.3.5 Binding rule set (case-insensitive, canonical identity)

Unreal `FName` comparison is case-insensitive: "Names are case-insensitive, but
case-preserving" (`Core/Public/UObject/NameTypes.h:573`), and `FName::operator==` compares
the comparison index and number (`NameTypes.h:762-765`). `TArray<FName>::Contains` — used by
the existing `FindActorByEntityId` (`AtlasTransportServer.cpp:2300-2303`) — therefore matches
case variants of the same tag.

v1's rule set, chosen to be case-insensitive-unique rather than falsely case-sensitive:

1. **Binding lookup is case-insensitive and performed on the canonical ID.** For each requested
   entity ID, the extractor forms `FName("atlas_entity:" + ASCII-uppercase(id))` and collects
   every actor in the scope set carrying a tag `FName`-equal to it (§3.3.3, §3.3.4).
2. **Case-insensitive uniqueness within a request.** A request whose entity-ID set contains
   two IDs that are equal when case-folded (e.g. `cam01` and `CAM01`) fails closed
   (`ERR_EXTRACTION_REQUEST_INVALID`) before extraction. One actor cannot be the extraction
   target of two canonical IDs.
3. **Zero / one / many.** Zero matches → `ERR_EXTRACTION_ENTITY_NOT_FOUND`; exactly one actor
   → accepted; two or more actors → `ERR_EXTRACTION_ENTITY_AMBIGUOUS`. Case-variant duplicate
   tags on different actors land in the ambiguity arm, not in first-match.
4. **Tag conflict on one actor.** If the matched actor carries two or more `atlas_entity:*` tags
   whose IDs are **distinct canonical identities** — i.e. not case variants of one ID, which are
   the same `FName` and collapse to a single binding — the binding is non-injective and fails
   closed with `ERR_EXTRACTION_ENTITY_TAG_CONFLICT`. Duplicate identical tag entries on one actor
   are a set-level duplicate, not a conflict.
5. **Addressability limitation (declared, not silently tolerated).** An entity is addressable in
   v1 if and only if some actor in the scope carries a tag whose ID matches the canonical
   grammar of §3.3.2. A source tag whose ID does not match the grammar (for example
   `atlas_entity:foo bar` with an embedded space) cannot be addressed by any v1 request: the
   binding lookup reports `ERR_EXTRACTION_ENTITY_NOT_FOUND`, which is the correct answer for
   "no canonical binding exists". Source-side tag authoring is therefore subject to the same
   grammar; v1 neither repairs a non-conforming tag nor invents a normalized match. There is no
   failure arm for this case, because a non-canonical ID can never be case-insensitively equal
   to a canonical one, and a dead failure arm would be untestable normative text.
6. **Reported identity is the canonical ID** (§3.3.4), never the request string. The matched
   tag's stored casing is deliberately **not** reported: the comparison class is
   case-insensitive (§3.3.3) so casing carries no canonical identity, and the casing an engine
   would report is a property of the process name table rather than of the extracted actor state
   (separate comparison/display entries, `Core/Private/UObject/UnrealNames.cpp:1860-1883`), so it
   cannot be shown reproducible across processes. A field whose determinism cannot be established
   MUST NOT participate in a digest. For the same reason the extractor MUST NOT look up the
   *request* string and echo it, and MUST NOT derive identity from a rendered tag.
7. **Numbered-name awareness.** The extractor MUST NOT assume that the tag's text equals the
   entity-ID string. A binding is established only by `FName` equality on the canonical name, so
   that the engine's `ParseNumber` decides how a `_<digits>` suffix participates (§3.3.3). An
   entity ID whose spelling ends in `_<digits>` is therefore a first-class identity and must be
   reported as itself: `cam_1` and `cam_01` are different entities, and neither is `cam`.
8. **No inference.** Actor names, actor labels and sequence display names never resolve
   identity.

#### 3.3.6 String comparison discipline

All extraction string comparisons are **ordinal and case-sensitive**, implemented with
explicit case-sensitive APIs in C++ (`FString::Compare(..., ESearchCase::CaseSensitive)` /
`FCString::Strcmp`) — never with `FString::operator==` or `FName::operator==`, both of which
are case-insensitive (`Containers/UnrealString.h.inl:1053-1056,1067-1070`; `NameTypes.h:762`).
The single deliberate exception is entity-tag binding, which uses `FName` equality (the engine's
own case-insensitive comparison, §3.3.3) — never a case-folded string comparison written by the
extractor.

### 3.4 Actor record and source provenance

#### 3.4.1 Three distinct identity notions (do not conflate)

| Notion | Value | Mutating it | Digest |
|---|---|---|---|
| Canonical entity identity | `entity_id` (canonical form of the matched tag binding, §3.3.4) | changing the tag changes canonical identity | changes |
| Source-object provenance | `actor_object_path`, `actor_class`, `level_package_path` | renaming the object changes provenance | **changes (expected)** |
| Mutable source locator | the object path *as a locator* | rename / recreate / level move all change it | not a separate field |

**Renaming a source actor is expected to change the extraction digest.** The digest is a
source-fidelity identity, not an entity-semantic identity. Conversely, digest *inequality*
does not mean the canonical entity changed.

v1 provides **no** rename tracking and **no** stable source-object identifier. A stable
source-object GUID was considered and rejected on evidence:

- `AActor::GetActorGuid()` (`Engine/Classes/GameFramework/Actor.h:1134`) is, for persisted
  actors, *derived from the object path* — `ActorGuid = FGuid::NewDeterministicGuid(GetPathName())`
  (`Engine/Private/Actor.cpp:1013-1015`) — so it carries no information beyond the path;
- for duplicated/non-persistent actors it is *randomly regenerated*
  (`ActorGuid = FGuid::NewGuid()`, `Actor.cpp:1017-1019`), so it is not reproducible across
  sessions, which is fatal for a digest intended to be reproducible across sessions;
- adding a second identity channel would be a second identity authority.

#### 3.4.2 Actor record fields

```text
entity_id
actor_name
actor_object_path
actor_class
level_package_path
parent
editor_visibility
transform
materials
omitted_material_components
```

- `entity_id` = the **canonical** identity of the matched binding (§3.3.4), never the request
  string.
- `actor_name` = `AActor::GetName()` (the object name). The actor **label**
  (`GetActorLabel()`) is not extracted in v1; `actor_name` shown in a UI is not the label.
- `actor_object_path` = the actor's full object path (source locator; includes the level outer
  and the object name).
- `actor_class` = `Actor->GetClass()->GetName()`.
- `level_package_path` = `Actor->GetLevel()->GetOutermost()->GetName()` — the package that
  contains the level, i.e. the level's own package identity (for the persistent level, the map
  package).
- `omitted_material_components` = the declared out-of-scope inventory of §3.8.1a
  (`count` + sorted, deduplicated `classes`).
- There is **no** nested `source_identity` object. Revision 1 carried both a top-level
  `actor_object_path` and a nested `source_identity.actor_object_path`; that duplication was a
  second place for the same fact to be written and is removed (§15). The actor's
  source-object provenance is defined as the tuple
  (`actor_object_path`, `actor_class`, `level_package_path`).

### 3.5 Parent binding

Parent state is derived only from the actor's direct attach-parent actor, defined as
`AActor::GetAttachParentActor()` = the owner of the root component's attach parent
(`Engine/Private/Actor.cpp:2785-2790`). No transitive chain is walked, and no parent identity
is inferred from names.

The canonical form MUST distinguish three states:

```text
parent:
  binding: "none" | "unbound" | "bound"
  entity_id: <string|null>
  actor_object_path: <string|null>
```

| Condition | binding | entity_id | actor_object_path |
|---|---|---|---|
| no attach-parent actor (or no root component) | `none` | `null` | `null` |
| attach-parent actor with no `atlas_entity:` tag | `unbound` | `null` | parent's object path |
| attach-parent actor with exactly one `atlas_entity:` binding | `bound` | parent entity ID (canonical, §3.3.4) | parent's object path |
| attach-parent actor with two or more distinct `atlas_entity:` tags | fail closed (`ERR_EXTRACTION_PARENT_TAG_CONFLICT`) | — | — |

Revision 1 collapsed the first two rows into `unbound/null`, which allowed two materially
different scene graphs to produce the same extraction state. That collapse is removed; the
`unbound` row now carries the parent's source locator so that re-parenting between two
different unbound parents is a digest-visible change.

### 3.6 Editor visibility

`AActor::IsHiddenEd()` is **not** a source flag; it is a derived aggregate
(`Engine/Private/ActorEditor.cpp:973-982`):

```cpp
if( bHiddenEdLayer || !bEditable || ( GIsEditor && ( IsTemporarilyHiddenInEditor() || bHiddenEdLevel ) ) )
    return true;
```

It folds in `bHiddenEdLayer`, `!bEditable`, `bHiddenEdTemporary` and `bHiddenEdLevel`, and it
is execution-mode dependent through `GIsEditor`. Calling it a source fact would be wrong, and
its inputs are not all publicly readable: `bHiddenEdTemporary` is **private**
(`Actor.h:1286-1289`), `bEditable` is **protected** (`Actor.h:1253,1264`), while `bHiddenEd`,
`bHiddenEdLayer` and `bHiddenEdLevel` are public `UPROPERTY` bitfields
(`Actor.h:1233,1241,1245`) with no public getters except `IsHiddenEdAtStartup()`
(`Actor.h:2593-2597`).

v1 therefore records **both** layers, labels the derived value as derived, and discloses the
input it cannot read:

```text
editor_visibility:
  hidden_in_editor: <bool>                 # DERIVED = AActor::IsHiddenEd()
  derived_from_gis_editor: <bool>          # GIsEditor at extraction time
  hidden_ed_at_startup: <bool>             # source flag bHiddenEd
  temporarily_hidden_in_editor: <bool>     # source flag bHiddenEdTemporary (via IsTemporarilyHiddenInEditor(false))
  hidden_ed_layer: <bool>                  # source flag bHiddenEdLayer
  hidden_ed_level: <bool>                  # source flag bHiddenEdLevel
  unrecorded_hidden_inputs: ["bEditable"]  # frozen literal; see below
```

Normative rules:

1. `hidden_in_editor` is a derived value and MUST be labelled as such; it MUST NOT be
   presented as a source fact.
2. `derived_from_gis_editor` records the execution-mode input that materially affects the
   derived value (`GIsEditor`), so an execution-mode change is digest-visible.
3. `unrecorded_hidden_inputs` is exactly the literal array `["bEditable"]`. It exists so the
   contract admits, in-band and machine-checkably, that `hidden_in_editor` cannot be fully
   decomposed by v1: an actor whose `bEditable` changed while `IsHiddenEd()` stayed `true` is
   **not distinguishable** from the extracted state. `bHiddenEdLayer` and `bHiddenEdLevel` are
   read from their public bitfield members; a future engine rev that makes them private is an
   implementation-blocking change, not a silent omission.
4. No renderer visibility, component visibility, lighting visibility, "visible to camera"
   state, or occlusion state is extracted. `hidden_in_editor == false` does not mean the actor
   is visible in any rendered frame.

### 3.7 Transform representation

World-space transform sources, all binary64 (§5):

- translation = `AActor::GetActorLocation()` in Unreal source units (centimetres);
- rotation = the exact `AActor::GetActorQuat()` world quaternion (not a Euler decomposition,
  which `GetActorRotation()` would be and which loses source information);
- scale = the exact `AActor::GetActorScale3D()`.

The canonical transform object is exactly:

```text
transform:
  source_component_type: "binary64"
  location_cm: { x, y, z }
  rotation:
    coordinate_frame:
      handedness: "left"
      up_axis: "Z"
      positive_x: "forward"
      positive_y: "right"
      positive_z: "up"
    representation: "quaternion"
    component_order: "x,y,z,w"
    unit: "unitless"
    source: "actor_world_quaternion"
    x, y, z, w
  scale: { x, y, z }
```

`source_component_type: "binary64"` is a frozen literal. It exists so that the precision
claim is asserted inside the payload itself and any future narrowing is a schema-visible
defect (§5.6). It is subject to §4.3: it MUST be derived from a compile-time assertion on
`FVector::FReal` / `FQuat::FReal`, not written as a hopeful constant.

No conversion to another engine's basis occurs in v1. No quaternion normalization,
shortest-path selection, interpolation, smoothing, tolerance, or equivalence comparison
occurs anywhere in the producer (§5.4).

### 3.8 Material-source state machine

#### 3.8.1 Component set — explicitly supported component classes only

v1 defines material extraction for **two component families only**, by class:

| Supported family | Root class | Material model |
|---|---|---|
| static mesh | `UStaticMeshComponent` (and descendants) | mesh-asset slot list + component override array, resolved by `FStaticMeshComponentHelper` |
| skinned mesh | `USkinnedMeshComponent` (and descendants) | skinned-asset material list + component override array, resolved by `FSkinnedMeshComponentHelper` |

The candidate set is `Actor->GetComponents<UMeshComponent>(Components,
/*bIncludeFromChildActors=*/false)` (`Engine/Classes/GameFramework/Actor.h:3979-3980`), and each
candidate is then:

1. kept only if `IsA<UStaticMeshComponent>()` or `IsA<USkinnedMeshComponent>()`;
2. required to satisfy `IsRegistered()` (`Engine/Classes/Components/ActorComponent.h:1243`) — an
   unregistered component does not participate in the world, and recording its necessarily
   unresolved material view would add source facts no world state depends on;
3. otherwise a hard failure of the whole extraction with
   `ERR_EXTRACTION_UNSUPPORTED_COMPONENT_TYPE`.

Rule 3 is not optional, and the reason is measured rather than assumed. `UMeshComponent` has
dozens of subclasses in shipped 5.6 whose material model is *not* the slot model defined here:
`UWidgetComponent` (`Runtime/UMG/Public/Components/WidgetComponent.h:94`, overrides both
`GetNumMaterials` and `GetMaterial` and draws a widget render target),
`UProceduralMeshComponent`
(`Plugins/Runtime/ProceduralMeshComponent/.../ProceduralMeshComponent.h:149`, overrides
`GetNumMaterials`), `UBaseDynamicMeshComponent`
(`Runtime/GeometryFramework/Public/Components/BaseDynamicMeshComponent.h:125`, overrides both),
`UGeometryCollectionComponent` (`Runtime/Experimental/GeometryCollectionEngine/...:577`),
`UHeterogeneousVolumeComponent` (`Runtime/Engine/Classes/Components/HeterogeneousVolumeComponent.h:20`),
`UGroomComponent`, `UGroomSolverComponent`, `UWaterMeshComponent`, `UCableComponent`,
`UCustomMeshComponent`, `UGeometryCacheComponent`, `UPaperSpriteComponent`,
`UPaperFlipbookComponent`, `UPaperTileMapComponent`, `UPaperGroupedSpriteComponent`,
`ULidarPointCloudComponent`, and the editor drawing components (`UTriangleSetComponent`,
`UPointSetComponent`, `UMeshWireframeComponent`, `ULineSetComponent`,
`UBasicTriangleSetComponentBase`, `UBasicPointSetComponentBase`, `UBasicLineSetComponentBase`).

None of those has `GetStaticMesh()` or `GetSkinnedAsset()`, so a generic `UMeshComponent` state
machine is **not implementable**: it would require per-class branching that this design does not
specify, and any claim of generic support would be false. Option A of the review is therefore
adopted: unsupported mesh components fail closed rather than being half-modelled.

Within the two supported families, descendants are accepted *because they inherit the material
model rather than replacing it*: `UInstancedStaticMeshComponent`
(`Components/InstancedStaticMeshComponent.h:157`), `USplineMeshComponent` (`:118`),
`UCameraProxyMeshComponent`, `ULandscapeNaniteComponent`, `UControlPointMeshComponent`,
`ULandscapeMeshProxyComponent`, `UInteractiveFoliageComponent`,
`UViewAdjustedStaticMeshGizmoComponent` declare no `GetNumMaterials`/`GetMaterial` override, and
`USkeletalMeshComponent`, `UPoseableMeshComponent` and `UInstancedSkinnedMeshComponent` inherit
`USkinnedMeshComponent`'s. A future class added to either subtree inherits the contract; a future
class added directly under `UMeshComponent` fails closed by rule 3 until this design is revised.

#### 3.8.1a Components deliberately outside the material contract (declared, not silent)

Material state of components that are **not** in the supported mesh families is out of v1 scope —
but the omission is recorded in-band rather than left invisible. For every registered
`UPrimitiveComponent` of the actor outside the supported families, the actor record carries:

```text
omitted_material_components:
  count: int                  # number of such registered components
  classes: [string, ...]      # their class names, sorted, deduplicated, canonical collation
```

This is classified as *intentionally omitted state made visible* (§4.6): v1 makes no material
claim about those components, and two actors that differ only in such a component still produce
different digests because the inventory differs. It does not enumerate them individually, so two
decals of the same class are indistinguishable from each other — a declared limit, not an
accidental loss.

Component identity is the component's object path. The contract does not derive a stable
component identity, so a component created at runtime with an engine-generated name
(`NAME_None`) is a mutable source locator, exactly like an actor name (§3.4.1). The live gate
MUST use explicitly named components.

Records are sorted by (`component_object_path`, `slot_index`) in canonical collation order
(§7.3); the ordering of the engine's component array is irrelevant to the payload.

#### 3.8.2 States (total function)

The state machine is evaluated per component from the engine's own answers. It is total: every
component in the set yields exactly one `mesh_state`, and every slot yields exactly one record.

Component level:

```text
component_object_path: string
component_class: string          # the supported root family is derivable from this name
mesh_asset_path: string|null     # null iff mesh_state == "no_mesh_asset"
mesh_state: "mesh_asset_present" | "no_mesh_asset"
slot_count: int                  # == len(slots)
slots: [ slot, ... ]
```

- `mesh_state = "no_mesh_asset"` — the component's mesh asset accessor (`GetStaticMesh()` for the
  static family, `GetSkinnedAsset()` for the skinned family) returns null. `mesh_asset_path` is
  `null`, `slot_count` is 0, `slots` is `[]`. The component is still recorded, so a null-mesh
  component cannot be silently omitted; `UStaticMeshComponent::GetNumMaterials()` returns 0 in
  this state (`Engine/Private/Components/StaticMeshComponent.cpp:2765-2775`).
- `mesh_state = "mesh_asset_present"` — the accessor returns non-null and `mesh_asset_path` is its
  stable object path.

Slot level — the record carries the two **assignment source facts** *and* the engine's resolved
value:

```text
slot_index: int
asset_slot_material_asset_path: string|null   # the mesh asset's material for this slot
override_material_asset_path: string|null     # the component's override for this slot
resolved_material_asset_path: string|null     # what the engine's resolver returns
```

Derivation, exactly as the engine's own helpers do it
(`Engine/Public/StaticMeshComponentHelper.h:108-137`;
`Engine/Public/SkinnedMeshComponentHelper.h:108-123`):

1. static family: `resolved` = the valid non-null override if present, else the asset slot value
   (`UStaticMesh::GetMaterial` returns the raw `StaticMaterials[idx].MaterialInterface`,
   `Engine/Private/StaticMesh.cpp:9520-9528`, which may be null);
2. skinned family: `resolved` = the valid non-null override if present, else the skinned asset's
   material for that index when the asset is not compiling and the index is valid, else null;
3. in both families the resolved value may then be replaced by a Nanite override material
   (`OutMaterial->GetNaniteOverride()`) when the component uses Nanite override materials
   (`StaticMeshComponentHelper.h:123-134`).

`resolved_material_asset_path` is therefore exactly `Component->GetMaterial(idx)`
(`StaticMeshComponent.cpp:2803-2811`, `SkinnedMeshComponent.cpp:1753-1756`), and the contract
distinguishes **assigned source value** from **resolved engine value**; a difference between them
is the engine's own resolution result, not an extraction transform.

Recording the asset slot as its own field is required for collision-freedom, not for
completeness: with only an assigned/resolved pair, the states (override `A`, asset slot `B`) and
(override `A`, asset slot `C`) would produce identical records although the mesh asset's source
state differs. That collapse is reviewed in §4.6 and in the review record (§P10).

Intentionally equivalent representations, stated so no implementation treats them as distinct:

- a null override **entry** (`OverrideMaterials.IsValidIndex(idx) && OverrideMaterials[idx] ==
  nullptr`) is equivalent to having no entry at all — both read as
  `override_material_asset_path: null` and both fall through to the asset slot;
- override entries at indices `>= GetNumMaterials()` are not slots and are not extracted;
- an `asset_slot_empty` slot (`asset_slot_material_asset_path: null` with no override) does
  **not** mean the slot renders with no material: the engine substitutes its default material at
  render-proxy creation. That substitution is render state and is **not** extracted.

#### 3.8.3 Fail-closed material rules

1. **Async compilation.** If the component's mesh asset reports compiling
   (`UStaticMesh::IsCompiling()`, `Engine/Classes/Engine/StaticMesh.h:627`;
   `USkinnedAsset::IsCompiling()`, `Engine/Classes/Engine/SkinnedAsset.h:254-256`), the
   extraction fails closed with `ERR_EXTRACTION_MESH_COMPILING`. This is not cosmetic:
   `USkinnedMeshComponent::GetNumMaterials()` returns 0 and
   `FSkinnedMeshComponentHelper::GetMaterial` returns null **while compiling**
   (`Engine/Private/Components/SkinnedMeshComponent.cpp:1713-1720`,
   `SkinnedMeshComponentHelper.h:114-120`), so a binary resolved/missing contract read during
   compilation would report transient `asset_slot_empty` states that are not source facts.
2. **Unresolvable non-null material.** A non-null material interface without a stable
   non-transient asset/object path is a hard failure (`ERR_EXTRACTION_MATERIAL_UNRESOLVED`),
   never an omission.
3. **Transient/dynamic material instances are unsupported.**
   `UMaterialInstanceDynamic`, or any material interface whose outermost package is the
   transient package (`/Engine/Transient`) or which carries `RF_Transient`, fails closed with
   `ERR_EXTRACTION_UNSUPPORTED_MATERIAL_SOURCE`. A transient instance is never represented by
   a variant tag, an object name, or a synthesized path.
4. **Unsupported mesh component classes fail closed.** Any registered `UMeshComponent` of the
   actor that is neither a `UStaticMeshComponent` nor a `USkinnedMeshComponent` (nor a
   descendant of either) is a hard failure, `ERR_EXTRACTION_UNSUPPORTED_COMPONENT_TYPE`
   (§3.8.1). v1 does not half-model such a component, and it does not silently drop it.
5. **No per-class special-casing inside a supported family.** Within the two supported families
   the slot model of §3.8.2 is the whole contract; the extractor invokes the engine's own
   helpers and applies no class-specific branch of its own. A class that would require one is by
   definition outside the supported set and fails closed under rule 4.
6. **Declared read-path side effect.** The engine's material helpers call
   `OutMaterial->ConditionalPostLoad()` inside the resolution chain
   (`Engine/Public/StaticMeshComponentHelper.h:126-127`). That is an engine-internal lazy-init /
   object-graph effect (it may load the material's package) and is **not** persistent editor-state
   mutation: it does not dirty a package, modify a transaction, or change the level. It is
   declared here because the read-only claim must be exact. Any engine call that *could* dirty
   (`MarkPackageDirty`), modify (`Modify`), or change ownership remains forbidden, and the live
   gate measures package dirty state across the extraction call (§11.3).

#### 3.8.4 Relationship to `verify_material_variant` and the `atlas_material_variant:` tag

These are **unrelated** mechanisms and the canonical material state MUST NOT be derived from,
compared with, or equated to the tag mechanism:

- `atlas_material_variant:<name>` (`AtlasTransportServer.cpp:51`) is an actor **tag** written
  by `apply_material_variant` (`AtlasTransportServer.cpp:687-689`).
- `inspect_material_state` reads only that tag (`BuildMaterialVariantState`,
  `AtlasTransportServer.cpp:692-694`), returning `{"variant": {"name": <tag or "default">}}`.
  It reads no material, no component, and no slot.
- `verify_material_variant` is mapped to that tag read
  (`planning/unreal_adapter_production.py:109`), so it verifies a label, not material state.

Therefore: the tag-based verification contract is **not** equivalent to the canonical material
state machine, and a future consumer MUST NOT treat a `verify_material_variant` result as
evidence about canonical materials. v1 defines no mapping between the two; any such mapping is
a separate milestone with its own design gate.

### 3.9 Sequencer contract

#### 3.9.1 Target identity

A Sequencer extraction request targets one explicit canonical entity ID whose bound actor MUST
be an `ALevelSequenceActor` (`Actor->IsA<ALevelSequenceActor>()`), else
`ERR_EXTRACTION_SEQUENCE_ACTOR_TYPE`.

The extractor MUST NOT scan for "the first valid" sequence actor and MUST NOT enumerate
LevelSequenceActors other than through the entity binding of §3.3. The existing
`FindSequencerPlaybackRange` / `InspectSequencerState` behaviour
(`AtlasTransportServer.cpp:719-750`) — first `ALevelSequenceActor` with a valid sequence, with
the entity ID used only as an output key — is explicitly **not** the extraction contract.

Because entity binding is uniqueness-enforced (§3.3.3), "multiple candidate
LevelSequenceActors for the same entity" is an **unreachable** condition and is not a failure
class in v1. Revision 1 listed it; that entry is removed (§15).

#### 3.9.2 Sequence record

```text
sequence:
  entity_id: string          # canonical ID, §3.3.4
  sequence_actor_object_path: string
  sequence_asset_object_path: string
  playback_range:
    lower_frame: int
    lower_bound: "inclusive"
    upper_frame: int
    upper_bound: "exclusive"
  tick_resolution: { numerator: int, denominator: int }
  display_rate:    { numerator: int, denominator: int }
```

#### 3.9.3 Validity predicate (normative)

All of the following MUST hold, each with its own error:

1. the resolved actor's `GetSequence()` is non-null and its `GetMovieScene()` is non-null
   (`ERR_EXTRACTION_SEQUENCE_ASSET_UNRESOLVED`);
2. the sequence asset has a stable, non-transient object path — its outermost package is not
   the transient package and it does not carry `RF_Transient`
   (`ERR_EXTRACTION_UNSUPPORTED_SEQUENCE_SOURCE`);
3. `MovieScene->GetPlaybackRange()`
   (`Engine/Source/Runtime/MovieScene/Public/MovieScene.h:801`)
   returns a `TRange<FFrameNumber>` with both bounds set:
   `HasLowerBound()` and `HasUpperBound()` MUST both be true, else
   `ERR_EXTRACTION_SEQUENCE_RANGE_OPEN`. Open bounds are not accepted;
4. `lower_frame = GetLowerBoundValue().Value` and `upper_frame = GetUpperBoundValue().Value`
   are int32 frame numbers in the MovieScene tick-resolution space. The bounds are recorded as
   `inclusive` lower / `exclusive` upper, which is the engine's semantics:
   `UMovieScene::SetPlaybackRange(FFrameNumber Start, int32 Duration)` (`MovieScene.h:998`)
   takes a lower bound and a size, i.e. a half-open range;
5. `upper_frame > lower_frame`, else `ERR_EXTRACTION_SEQUENCE_RANGE_INVALID`. A degenerate or
   inverted range is a legal engine state but is refused in v1 as a deliberate bounded
   restriction (fail-closed, not lossy);
6. `tick_resolution = MovieScene->GetTickResolution()` (`MovieScene.h:809-812`) and
   `display_rate = MovieScene->GetDisplayRate()` (`MovieScene.h:822-825`) are recorded as exact
   int32 rational pairs, **verbatim and never reduced to lowest terms**: `{60,2}` and `{30,1}`
   are numerically equal but are different stored source values, and the contract records what the
   engine stores. v1's own validity predicate is `numerator > 0 && denominator > 0`
   (`ERR_EXTRACTION_SEQUENCE_RATE_INVALID`). This is deliberately **stronger** than
   `FFrameRate::IsValid()`, which tests only `Denominator > 0`
   (`Core/Public/Misc/FrameRate.h:48-51`) and therefore accepts a zero or negative numerator.

Both rates are retained because MovieScene frame numbers live in tick-resolution space while
display rate is the user-facing sequence rate. Neither is rounded, scaled, or converted to a
float.

#### 3.9.4 Compatibility boundary with the existing probes (disclosed, not repaired)

The existing probes are frozen and are **not** changed by this milestone, but two conventions
in them are asymmetric and MUST NOT be inherited silently:

- `inspect_sequencer_state` reports `sequencer.end_frame` as the **exclusive** upper bound
  (`FindSequencerPlaybackRange` returns `GetUpperBoundValue().Value`,
  `AtlasTransportServer.cpp:719-743`).
- `set_sequencer_playback_range` treats its `end_frame` argument as **inclusive** and converts
  to the engine's half-open form with size `EndFrame - StartFrame + 1`
  (`AtlasTransportServer.cpp:763`), a convention frozen by
  `tests/m10/test_m10_defect_d2_sequence_range.py:95-102`.

v1 uses the distinct field names `lower_frame` / `upper_frame` with explicit
`lower_bound` / `upper_bound` markers. v1 does **not** redefine, alias, or reinterpret the
legacy `start_frame` / `end_frame` fields, and a consumer MUST NOT assume the legacy fields
carry v1's semantics.

---

## 4. Extraction value tree boundary and closed schema

### 4.1 What is not part of the value tree

The transport response envelope
(`AtlasTransportServer.cpp:294-311`; modelled at `planning/unreal_transport_contract.py:63-107`)
carries `request_id`, `operation_name`, `success`, `error`, `error_code`, `source`,
`schema_version`, `entity_ids`, `observed_state` and **`session_identity`** — the last
containing `editor_session_id`, `process_id`, `process_creation_time_utc`,
`server_start_time_utc`, `engine_version`, `project_identity`
(`AtlasTransportServer.cpp:2309-2333`).

None of these are extraction facts except the extraction node itself. Specifically:

- `session_identity` is **envelope metadata**, never extracted;
- the existing adapter merges `session_identity` **into `observed_state`** as
  `_session_identity` (`planning/unreal_adapter_production.py:84-94`), and the existing
  evidence digest digests `observed_state` verbatim
  (`planning/unreal_evidence_digest.py:36-45,52-57`). That combination makes the existing
  evidence digest session-varying: process id, session GUID and timestamps are inside the
  digested material. Extraction MUST NOT repeat this pattern;
- `inspect_render_state` additionally embeds `engine_session_identity` inside its
  `observed_state` (`AtlasTransportServer.cpp:1969-1971`) — another instance of the same
  contamination class, outside extraction scope.

### 4.2 The extraction boundary (normative)

1. Extraction is a distinct operation (§10.1). Its response `observed_state` contains
   **exactly one key**: `unreal_state_extraction`. Any other key at that level is a hard
   failure (`ERR_EXTRACTION_SCHEMA`).
2. The value tree is the object under `unreal_state_extraction`, with exactly these five keys:

   ```text
   extraction_schema_version: 1
   extraction_kind: "actor_state" | "sequencer_state"
   world: { ... }
   actors: [ ... ]
   sequences: [ ... ]
   ```

   Unused collections are empty arrays, never omitted.
3. **The schema is closed at every level.** Every object in the tree has an exact key set; a
   missing key, an additional key, or a `null` where the contract requires a value is a hard
   failure. Closedness is what makes digest determinism mechanically enforceable: there is no
   open bag of keys that transient metadata could be added to.
4. **Reserved-key rejection.** Any key equal to, or beginning with, `_` is rejected at any
   depth. Specifically `_session_identity`, `session_identity`, `engine_session_identity`,
   `process_id`, `editor_session_id`, `server_start_time_utc`,
   `process_creation_time_utc` and any other timestamp/session field are rejected wherever they
   appear. Rejection is by closed schema first and by reserved-prefix second, so an
   unrecognised session-like key cannot slip through under a new name.
5. **The digest input is reconstructed, not copied.** Python builds the canonical digest input
   by copying the *declared fields only* from the validated value tree into a fresh structure.
   It never serialises raw `observed_state`, never serialises the transport response, and never
   serialises a mapping it did not itself construct field by field. This is the mechanical
   answer to "how is canonicalization prevented from seeing session/timestamp fields": the
   session fields are never in the structure that canonicalization is handed.
6. `extraction_schema_version` is the **value tree** version, deliberately named so it cannot
   be confused with the transport's own `schema_version` (which is `1` for requests and
   responses, `planning/unreal_transport_contract.py:33-39,78-86`).
7. The digest is not a field of the value tree. It is computed *about* the tree (§6.5), which
   keeps the tree free of self-reference.
8. **The extraction boundary runs un-augmented.** Extraction MUST NOT consume a payload that
   passed through the existing session-augmenting adapter path
   (`planning/unreal_adapter_production.py:76-95`, which copies `observed_state` and injects
   `_session_identity`). It reads the transport response's own `observed_state`, or an adapter
   path that performs no augmentation. If a session key is nevertheless present, validation
   fails closed — the remedy is to stop augmenting, never to strip the key (§8.2 forbids
   stripping). Without this rule the extraction boundary would fail closed on every production
   response, and the cheapest "fix" a future implementer could reach for — deleting the key —
   is exactly the containment breach §4.1 exists to prevent.

### 4.3 Asserted preconditions must be derived, not written

Several fields are *acceptance markers*: their legal value is fixed by this contract
(`world_type: "editor"`, `is_partitioned_world: false`,
`selection_provenance: "g_editor_editor_world_context"`, `level_scope.levels[].loaded: true`,
`level_scope.levels[].visible: true`, `transform.source_component_type: "binary64"`). A marker
that a producer writes as a literal proves nothing, so:

1. the C++ producer MUST compute each marker from the engine object it describes
   (`World->WorldType`, `World->IsPartitionedWorld()`, the selection site that produced the
   world, `ULevelStreaming::IsLevelLoaded()` / `IsLevelVisible()`) — never as a constant;
2. where the marker describes a compile-time property, the producer MUST assert it at compile
   time (`static_assert` on `FVector::FReal` / `FQuat::FReal` being `double`,
   `Core/Public/Math/Vector.h:55`), so the literal cannot become a lie;
3. Python MUST assert each marker equals its contracted value and fail closed
   (`ERR_EXTRACTION_SCHEMA`) otherwise.

A marker that is not derived and asserted is a hardcoded assertion of the contract's own
precondition, and a gate that only observes it proves nothing.

### 4.4 World record (closed)

```text
world:
  world_object_path: string
  world_package_path: string
  world_name: string
  world_type: "editor"
  engine_version: string
  engine_build_version: string
  selection_provenance: "g_editor_editor_world_context"
  is_partitioned_world: false
  level_scope:
    levels:
      - level_package_path: string
        level_kind: "persistent" | "streaming"
        loaded: true
        visible: true
```

`world_type` is the lowercased `EWorldType::Editor`; only `"editor"` is legal in v1.
`is_partitioned_world` is a frozen literal `false` (extraction from a partitioned world is
refused, §3.2.1). `level_scope.levels` is in canonical order (§7.3). All markers follow the
derivation rule of §4.3.

For a non-partitioned world the persistent level's package **is** the world package, so
`world_package_path` and the persistent level's `level_package_path` are equal by construction;
this is expected and MUST NOT be "corrected" by stripping a level suffix. For a streaming
level the package is the streaming level's own world-asset package
(`ULevelStreaming::GetWorldAssetPackageFName()`, `Engine/Classes/Engine/LevelStreaming.h:514`).

World facts are always bound into the payload, so the same actor state cannot be silently
interpreted as belonging to a different editor world, a different level set, or a different
engine build.

### 4.5 Sequencer and actor collections

- `extraction_kind = "actor_state"`: `actors` holds the requested entities in canonical order
  (§7.3); `sequences` is `[]`.
- `extraction_kind = "sequencer_state"`: `sequences` holds exactly one record; `actors` is `[]`.
- **`extraction_kind` is derived from the payload content, not copied from the request.** It MUST
  equal `"actor_state"` iff `actors` is non-empty and `sequences` is empty, and
  `"sequencer_state"` iff the converse; a tree in which both are non-empty or both are empty is a
  schema failure (`ERR_EXTRACTION_SCHEMA`). The producer asserts the derivation and Python
  re-derives it, so no request field survives into the payload through this leaf.
- The operation still determines what the extraction *asks for* (§10.1); that is scope, not
  identity, and the distinction is stated normatively in §4.6.

### 4.6 Field provenance classification (no request-derived value in the payload)

Every payload field is classified by provenance. The digest excludes request, authorization,
transport, session and clock (as does `docs/ATLAS_ARCHITECTURE_CONTRACT.md:23,176-187`), so a
field in categories 3–5 must be either eliminated or explicitly justified.

| Category | Fields | Status |
|---|---|---|
| **1 — authoritative engine source fact** | `world_object_path`, `world_package_path`, `world_name`, `engine_version`, `engine_build_version`, `level_scope.levels[]` (`level_package_path`, `level_kind`, `loaded`, `visible`), `actor_name`, `actor_object_path`, `actor_class`, `level_package_path`, `parent.binding`, `parent.actor_object_path`, `editor_visibility.hidden_ed_at_startup`, `.temporarily_hidden_in_editor`, `.hidden_ed_layer`, `.hidden_ed_level`, `transform.location_cm`, `.rotation`, `.scale`, `materials[].component_object_path`, `.component_class`, `.mesh_asset_path`, `slots[].slot_index`, `.asset_slot_material_asset_path`, `.override_material_asset_path`, `.resolved_material_asset_path`, `omitted_material_components`, `sequences[].sequence_actor_object_path`, `.sequence_asset_object_path`, `playback_range.*`, `tick_resolution.*`, `display_rate.*` | digested |
| **2 — deterministic derivation from source facts** | `entity_id` and `parent.entity_id` (canonical identity class of the matched binding, §3.3.4), `editor_visibility.hidden_in_editor` (from the engine's own `IsHiddenEd()`), `materials[].mesh_state` (from asset presence), `slot_count` (from the slot list), `extraction_kind` (§4.5), `world_type`/`is_partitioned_world` (marker assertions of §4.3) | digested |
| **3 — request metadata** | *none.* The request's entity set determines the extraction **scope**, not the identity of anything in the tree (§4.6.1) | removed |
| **4 — execution metadata** | `editor_visibility.derived_from_gis_editor` (`GIsEditor` at extraction time — an input that materially changes `hidden_in_editor`, so it is recorded deliberately) | digested, declared |
| **5 — implementation metadata** | `extraction_schema_version`, `selection_provenance`, `transform.source_component_type`, `editor_visibility.unrecorded_hidden_inputs` | digested, declared |

#### 4.6.1 Scope is not identity

The request legitimately defines **which** entities are extracted: a different entity set is a
different extraction and yields a different tree. That is scope. What the request MUST NOT do is
change the *identity* of anything that is extracted. Concretely:

- the same entity requested with different casing or FName spelling yields byte-identical
  payloads (§3.3.4);
- permuting the requested entity IDs yields byte-identical payloads (§7.4 D3);
- no request field (`request_id`, `authorization_id`, `entity_ids` as a *list*, the raw spelling,
  the requested `extraction_kind` string) appears anywhere in the tree;
- therefore the digest is an identity of the extracted state **for that scope**, and two digests
  are comparable only when both extractions requested the same entity set and the same extraction
  kind. Cross-scope and cross-kind digest comparison is meaningless and MUST NOT be performed;
  equality of two digests already implies their scopes matched, because the scope is in the tree.

---

## 5. Exact numeric policy

### 5.1 Source representation is binary64, not binary32

Revision 1 asserted that "All Unreal transform scalar values in v1 originate as `float32`
source facts" and canonicalised them as eight-hex-digit binary32 strings. That premise is
false in UE5 with Large World Coordinates. In the installed engine:

- `using FVector = UE::Math::TVector<double>;` (`Core/Public/Math/MathFwd.h:47`)
- `using FQuat  = UE::Math::TQuat<double>;`   (`MathFwd.h:50`)
- `using FTransform = UE::Math::TTransform<double>;` (`MathFwd.h:53`)
- float variants are separate types: `FVector3f = TVector<float>` (`MathFwd.h:73`),
  `FQuat4f = TQuat<float>` (`MathFwd.h:76`)
- the LWC declaration macro binds the default alias to `double`
  (`Core/Public/Misc/LargeWorldCoordinates.h:17`)

`AActor::GetActorLocation()` / `GetActorQuat()` / `GetActorScale3D()` all return these default
aliases (`Engine/Classes/GameFramework/Actor.h:1700,2482,2500`), i.e. **binary64**.

Canonicalising binary64 source facts as binary32 is lossy. Revision 1 named that loss "exact
source fidelity"; Revision 2 removes the loss rather than the label.

### 5.2 Canonical scalar encoding

Every Unreal floating-point transform scalar (all components of `location_cm`, `rotation`,
`scale`) is represented as the **IEEE-754 binary64 bit pattern** of the value the engine
returned, written as exactly 16 lowercase hexadecimal digits:

```json
"x": "3ff0000000000000"
```

Rules:

1. **The canonical value is the integer value of the binary64 bit pattern, and the encoding is
   endian-neutral by definition.** The double is reinterpreted as an unsigned 64-bit integer
   (C++: `std::bit_cast<uint64_t>` or `memcpy` of the same host object; Python:
   `struct.unpack("<Q", struct.pack("<d", v))[0]`) and that integer is rendered as 16 lowercase
   hex digits. Endianness never enters the canonical string because the *integer* is a property
   of the double, not of its byte order — measured: `1.0` yields `3ff0000000000000` under
   little-endian, big-endian and native packing alike.
   The one formulation that is **wrong** is a mismatched pair that reinterprets the byte order:
   `struct.unpack(">Q", struct.pack("<d", v))` yields `000000000000f03f` for `1.0`. The contract
   therefore fixes the *value* semantics ("the integer value of the bit pattern") rather than
   naming a host byte order, and the C++ side must never hex-dump `reinterpret_cast`ed memory
   bytes directly.
2. Lowercase hex, zero-padded to 16 digits, no prefix, no separators. The C++ formatter is
   `FString::Printf(TEXT("%016llx"), Bits)` (lowercase by construction) and the Python form is
   `f"{bits:016x}"`.
3. The lexical form is part of the schema: a transform scalar MUST match `^[0-9a-f]{16}$`. A
   decimal lexeme, a shorter hex string, an 8-digit binary32 pattern, or a JSON number in a
   transform scalar position is a hard failure (`ERR_EXTRACTION_SCHEMA`). This makes the
   precision claim checkable rather than merely asserted.
4. No narrowing is permitted anywhere between the engine accessor and the hex encoding: no
   `static_cast<float>`, no `UE_REAL_TO_FLOAT*` macro
   (`LargeWorldCoordinates.h:30-36`), no `float32` intermediate, no `numpy.float32`, no
   `struct.pack("<f")`.

### 5.3 Integers

Frame numbers, schema versions, slot indices and frame-rate numerators/denominators are exact
JSON integers within their declared int32 source types. Floating-point JSON numbers are
**forbidden anywhere in the value tree**: the Python validator rejects any parsed `float`
value and any JSON number lexeme that is not an integer. With no floats in the payload,
implementation-dependent floating-point lexeme formatting (the historical cross-language
determinism hazard) cannot occur.

### 5.4 Source-fidelity identity versus semantic equivalence

The contract defines these as two different notions, and v1 implements only the first:

- **Source-fidelity identity** — the canonical value tree is byte-identical. This is what the
  digest commits to.
- **Semantic equivalence** — two states would be judged the same by a reasoning layer (for
  example `q` versus `-q`, `+0.0` versus `-0.0`, a rename, or a translationally equivalent
  scene). v1 does **not** define, compute, or imply semantic equivalence, and MUST NOT
  introduce semantic interpretation into the extractor merely to make digests "nicer".

Consequences, stated normatively:

- `q` and `-q` are **distinct** source encodings. Neither is chosen as canonical. No
  shortest-path selection, sign flip, or normalization occurs.
- `+0.0` and `-0.0` are **distinct** facts (`0000000000000000` vs `8000000000000000`) and are
  not canonicalised.
- Equal digest ⇒ the two extractions produced byte-identical canonical value trees ⇒ identical
  extracted source facts *for the recorded scope*. It does not assert that the two engine
  states were identical: inputs the contract does not read exist (§3.6.3, §3.8.4, §12).
- Different digest ⇒ at least one extracted fact, or the recorded scope (including engine
  identity and level scope), differs. It does **not** assert semantic difference.

### 5.5 Non-finite values

Non-finite source values MUST be detected **at the source representation** — `std::isnan` /
`std::isinf` on the returned `double`, `math.isfinite` in any Python-side path — **before** any
encoding, and MUST fail closed with `ERR_EXTRACTION_NON_FINITE`. No sentinel, no skip, no partial
record, no substitution of a finite value.

Every non-finite class is refused, and for a stated reason:

- **quiet NaN and signaling NaN are both refused** by the same `isnan` test, so the
  signaling/quiet distinction never reaches the canonical form;
- **NaN payload bits are never encoded.** They are not portable anyway: NaN payload semantics
  differ by platform and by architecture, so a canonical hex string of a NaN would be an
  implementation artefact dressed as a source fact;
- **±Inf are refused** by `isinf`, so a saturated or diverged value cannot be published as a
  location.

Because the check runs on the returned `double` and precedes the bit encoding, there is no
ordering in which a non-finite value can reach `struct.pack("<d", v)` or the C++ bit cast.

### 5.6 Overflow and underflow cannot silently alter a fact

Because no narrowing exists in the pipeline, the two classic corruption modes are structurally
impossible, and this is asserted rather than assumed:

- a finite binary64 above `FLT_MAX` cannot become `inf`;
- a nonzero binary64 whose magnitude is below the smallest normal float32 (or below a flush-to-
  zero threshold) cannot become `0`.

Both cases are nevertheless **required test obligations** at the canonical boundary (§7.4
D11–D12), so that a future narrowing regression is caught: a scalar of magnitude greater than
`FLT_MAX` must round-trip to its exact binary64 pattern, and a magnitude at the binary64
denormal floor must round-trip to a **nonzero** pattern.

### 5.7 Strings

Strings remain value strings. No trimming, case folding, Unicode normalization, path
normalization, or escaping-based normalization is performed by the extraction layer. The only
string constraint in v1 is the entity-ID grammar of §3.3.2, which is enforced as a
*request-level accept/reject rule*, not as a rewrite. The source spelling of the matched tag is
reported verbatim (`entity_id`); the tag's stored casing is not a v1 fact (§3.3.3.6).

---

## 6. Canonicalization and digest

### 6.1 Standard

Canonical bytes are produced by JSON Canonicalization Scheme, **RFC 8785**, UTF-8 encoded, with
no BOM and no trailing newline. Canonicalization is performed over the validated value tree
(§4.2.5's reconstructed structure), never over Unreal's own JSON serializer output and never
over the transport response.

### 6.2 Atlas has no JCS implementation today

RFC 8785 appears nowhere in the repository except in Revision 1 of this design document. Every
existing digest path uses Python's `json.dumps(..., sort_keys=True, separators=(",", ":"))`,
with `ensure_ascii` differing between call sites — for example
`planning/unreal_evidence_digest.py:56`, `planning/unreal_render_contract.py:54,88`,
`planning/production_artifact.py:75`, `planning/blender_execution_receipt.py:12`. There is no
shared canonicalizer and no JCS conformance test.

### 6.3 `json.dumps(sort_keys=True)` is not RFC 8785

They differ in ways that are reachable for this payload:

1. **Key ordering domain.** Python sorts `str` keys by Unicode *code point*; JCS orders object
   names by *UTF-16 code units*. These orders differ when a set of names mixes astral-plane
   characters with `U+E000..U+FFFF`. Entity IDs are ASCII (§3.3.2) so they are safe, but object
   paths are not constrained and are exactly where this divergence is reachable.
2. **String escaping.** JCS uses ECMAScript `JSON.stringify` escaping (short escapes for
   `\b \t \n \f \r \" \\`, `\u00xx` for other control characters, and — unlike `ensure_ascii=True`
   — no escaping of non-ASCII characters). Python's escaping is different, and the repository's
   call sites do not even agree with each other (`ensure_ascii=True` in
   `unreal_render_contract.py`, `False` in `unreal_evidence_digest.py`).
3. **Number serialisation.** JCS mandates ECMAScript number serialisation. Our payload contains
   only integers (§5.3), where the two agree, but the contract forbids floats precisely so that
   this rule can never be load-bearing; and a Python float like `-0.0` serialises as `-0.0`
   while the ECMAScript rule yields `0`.

### 6.4 Implementation strategy (no implementation in this task)

- **Ownership.** Atlas Python owns canonicalization and the digest. The C++ producer never
  canonicalises, never hashes, and never signs. There is exactly one canonicalizer
  implementation for this contract, and it is a new Atlas-owned module on the Python side.
- **Scope of the implementation.** It implements RFC 8785 over the restricted domain of this
  payload: closed-schema objects with string keys, strings, integers, booleans, `null`, and
  arrays. It MUST fail closed on any value outside that domain (no floats, no bytes, no
  non-string keys) rather than falling back to `json.dumps`.
- **The parser must not admit values the canonicalizer rejects.** A canonicalizer that validates
  its input is not sufficient if the *parser* already changed the input. The C++-produced JSON
  text is therefore decoded under a hardened policy, each item of which was measured on the
  project interpreter (Python 3.11.16):

  | Hazard | Measured default behaviour | Required policy |
  |---|---|---|
  | duplicate object keys | `json.loads('{"entity_id":"a","entity_id":"b"}')` → `{"entity_id": "b"}`: silently **last-wins** | `object_pairs_hook` that raises on any duplicate key (a payload whose key set depends on position is not a value tree) |
  | `NaN` / `Infinity` tokens | accepted by default (`parse_constant`) | `parse_constant` raises (`ERR_EXTRACTION_SCHEMA`) |
  | float lexemes | parsed into binary floats | `parse_float` raises — floats are outside the domain, and a rounded parse would destroy a decimal lexeme before any check |
  | lone surrogates | `json.dumps(..., ensure_ascii=False)` yields `"\ud800"`, and UTF-8 encoding then raises `UnicodeEncodeError: surrogates not allowed` | reject any string containing a code point in `U+D800..U+DFFF` during validation, before canonicalization |
  | surrogate **pairs** | `"\ud83d\ude00"` correctly parses to one astral character | accepted; not a special case |
  | `bool` vs `int` | `isinstance(True, int)` is `True`; `type(True) is int` is `False` | integer fields validate with `type(x) is int` (`bool` is rejected where an integer is required, and vice versa) |
  | integer range | Python integers are unbounded, and `100000000000000000000000` parses fine | every integer field MUST be bounded to its declared source range (int32 for frame numbers, slot indices, `slot_count`, `count`, and rate numerators/denominators) and rejected otherwise — a value C++ could never have produced is a hard failure |

- **Domain closure is checked on the reconstructed structure, not on the parsed text.** Python
  validates, then rebuilds the digest input field by field (§4.2.5), so any residual parser
  artefact that is not a declared field cannot reach canonicalization at all.
- **Test vectors.** RFC 8785's published test vectors MUST be committed with the module and
  asserted by a deterministic test (§7.4 D9). The obligation is split, because the restricted
  domain and full JCS are not the same thing:
  - vectors whose values lie **inside** the restricted domain MUST canonicalise byte-exactly as
    the vectors specify — these are the vectors that carry the object-key-ordering rule
    (UTF-16 code units) and the string-escaping rules, which is exactly what this contract
    needs;
  - vectors that exercise values **outside** the domain (floating-point numbers, exponent
    forms) MUST be **rejected** by the canonicalizer rather than passed, and the test MUST
    assert the rejection. A canonicalizer that "passes" a float vector has silently acquired a
    number-formatting behaviour this contract forbids.

  `json.dumps(sort_keys=True, ...)` is explicitly **not** an acceptable oracle for either
  half.
- **Byte encoding.** UTF-8, no BOM, no trailing newline; the canonical bytes are the SHA-256
  input.
- **No reuse of an existing digest path.** The extraction digest MUST NOT reuse
  `digest_evidence` / `digest_evidence_ledger` (`planning/unreal_evidence_digest.py`), whose
  digested material is `observed_state` plus envelope fields
  (`unreal_evidence_digest.py:36-45`) — i.e. exactly the session-contaminated surface §4.1
  rejects — and whose canonicalization is `json.dumps`, not JCS.

### 6.5 Digest boundary

- The digest is `sha256(canonical_bytes)` over exactly the extraction value tree of §4.2,
  rendered as 64 lowercase hex digits. It is computed by Python, after structural validation,
  from the reconstructed structure.
- The digest commits to the extraction facts, the recorded world identity, the engine identity,
  and the recorded level scope. It commits to nothing else: not the request, not the
  authorization, not the transport, not the session, not the clock.
- The digest is not stored inside the value tree (§4.2.7).
- The digest is an identity/integrity value and is never a verification verdict (§2.3).

---

## 7. Determinism contract

Determinism is *demonstrated*, not asserted. This section fixes who orders what, under which
collation, and which tests are mandatory.

### 7.1 Who performs ordering

The C++ producer MUST emit every array in the canonical order defined in §7.3. Python MUST
**validate** the canonical order and fail closed (`ERR_EXTRACTION_NON_CANONICAL_ORDER`) if any
array is not in it. Python MUST NOT silently re-sort: silent sorting would hide a producer
defect and make the digest depend on the validator's tolerance. JCS itself preserves array
order, so array order in the canonical bytes is exactly the order the producer emitted.

### 7.2 What never participates in payload identity

Pointer values, memory addresses, `TSet`/`TMap` iteration order, hash seeds, object arrival
order, request order, dictionary insertion order, process identity, wall-clock time, thread
scheduling, and engine-session identity MUST NOT participate in the value tree, the canonical
bytes, or the digest.

Two concrete engine facts this forbids relying on:

- `FLevelCollection::GetLevels()` returns a `TSet<TObjectPtr<ULevel>>`
  (`Engine/Classes/Engine/World.h:675` with member at `:735`) — hash order; it MUST NOT be used
  to build the level scope at all.
- `UWorld::GetLevels()` returns an array (`World.h:3426`) whose order is level arrival order,
  not a canonical order; it MUST NOT be used as the scope order.

### 7.3 Canonical order and collation

| Collection | Canonical order |
|---|---|
| `world.level_scope.levels` | `level_package_path` ascending, UTF-16 code-unit order |
| `actors` | `entity_id` ascending, UTF-16 code-unit order |
| `materials` (component records) | `component_object_path` ascending, UTF-16 code-unit order; no tie-break needed |
| `materials[].slots` | `slot_index` ascending, numeric |
| `sequences` | exactly one element |
| object keys | JCS order (UTF-16 code units of the key), applied by the canonicalizer |

Collation is **ordinal**, never locale-aware, never case-insensitive.

- Entity IDs are ASCII (§3.3.2), so UTF-8 byte order = UTF-16 code-unit order = C++ `FString`
  order = Python `str` order. The equivalence is a consequence of the grammar, not a hope.
- Object paths are not ASCII-constrained, so the contract fixes **UTF-16 code-unit order** and
  states how to obtain it in both languages: compare `s.encode("utf-16-be")` byte sequences in
  Python (equivalent to comparing UTF-16 code units as unsigned values) and `FString`'s
  code-unit comparison restricted to case-sensitive comparison in C++ (§3.3.4). Python's
  default `sorted()` on `str` (code-point order) is **not** equivalent and MUST NOT be used for
  object paths.

### 7.4 Source order, duplicates, and mandatory tests

**Source order.** v1 has no array with meaningful source order: `actors`, `materials`,
`slots`, `sequences` and `levels` are all canonically ordered sets. No implementation may claim
"source order" for them.

**Duplicates.** Duplicates are rejected, never deduplicated, **where the identity must be
unique**: duplicate entity IDs in a request (case-insensitively, §3.3.5.2), two actors matching
one entity ID (`ERR_EXTRACTION_ENTITY_AMBIGUOUS`), two distinct `atlas_entity:` tags on one actor
(`ERR_EXTRACTION_ENTITY_TAG_CONFLICT`), a duplicate JSON object key (§6.4). Scope entries are the
deliberate exception: two streaming instances of one package are two levels, so repeated
(`level_package_path`, `level_kind`) pairs are permitted and each occurrence is recorded
(§3.2.1.6).

**Mandatory deterministic tests** (design obligations; they are the evidence for the
determinism claim):

- **D1** — two independent Python processes with deliberately different `PYTHONHASHSEED`
  values produce identical canonical bytes and digest for the same value tree.
- **D2** — the same logical value tree built by two different construction sequences (different
  dictionary insertion orders) produces identical bytes.
- **D3** — permuting the requested entity-ID order produces identical bytes.
- **D4** — permuting fixture construction order (actor spawn order, component registration
  order, tag addition order, and material slot assignment order where the engine permits it)
  produces identical bytes.
- **D5** — repeated extraction within one editor session produces identical bytes.
- **D6** — repeated extraction across two fresh editor sessions produces identical bytes.
- **D7** — a value tree whose arrays are not in canonical order is **rejected**
  (`ERR_EXTRACTION_NON_CANONICAL_ORDER`); asserts the validator does not silently sort.
- **D8** — a value tree carrying extra keys, `_session_identity`, `session_identity`,
  `engine_session_identity`, `process_id`, or a timestamp at any depth is **rejected**; and the
  digest of a conforming tree is **unchanged** when envelope-level session metadata varies
  between two otherwise identical responses.
- **D9** — the new canonicalizer passes the RFC 8785 published test vectors **within the
  restricted domain** byte-exactly, including the object-key-ordering vector that distinguishes
  UTF-16 code-unit order from code-point order, and **rejects** the vectors that exercise
  values outside the domain (floats/exponent forms) (§6.4).
- **D10** — two value trees differing only in `engine_version` (and separately only in
  `engine_build_version`) produce **different** digests; asserts the fields are digested rather
  than silently dropped.
- **D11** — a transform scalar whose magnitude exceeds `FLT_MAX` round-trips to its exact
  binary64 pattern.
- **D12** — a transform scalar at the binary64 denormal floor round-trips to a **nonzero**
  pattern (the anti-flush-to-zero proof).
- **D13** — a transform scalar of lexical shape other than 16 lowercase hex digits (a decimal
  string, an 8-digit hex string, a JSON number) is rejected.
- **D14 (canonical identity, hostile).** Against one source actor carrying one `atlas_entity:`
  tag, all of these must produce **byte-identical** payloads and digests: requests spelled
  `cam01`, `CAM01`, `Cam01`; and the request order permuted. A tag stored as
  `atlas_entity:CAM01` must resolve for a `cam01` request and vice versa, because the binding is
  `FName` equality on the canonical name (§3.3.4).
- **D15 (numbered names, hostile).** With tags `atlas_entity:CAM_1`, `atlas_entity:CAM_01` and
  `atlas_entity:CAM` present in the world simultaneously: a request for `cam_1` resolves only
  the `CAM_1` binding; a request for `cam_01` resolves only `CAM_01`; a request for `cam`
  resolves only `CAM`; and the three payloads differ. A world in which two *different* actors
  carry `atlas_entity:CAM_1` and `atlas_entity:cam_1` fails closed as ambiguous, not first-match.
- **D16 (scope revalidation).** A stub that changes a scope level's loaded/visible state between
  the snapshot and the revalidation makes the extraction fail closed with
  `ERR_EXTRACTION_SCOPE_CHANGED`; a stub that returns a null streaming-level entry fails closed
  with `ERR_EXTRACTION_LEVEL_SCOPE_INVALID`; and a scope containing two instances of one package
  is accepted with two entries (no false refusal).
- **D17 (material collision pairs).** The following pairs must produce **different** records:
  (override `A`, asset slot `B`) vs (override `A`, asset slot `C`); a supported component with a
  mesh asset and zero slots vs one with no mesh asset; a Nanite-substituted resolution vs an
  unresolvable one. And these must produce the **same** record (intentionally equivalent): a null
  override entry vs no override entry.
- **D18 (unsupported component).** An actor carrying a registered `UWidgetComponent` (or any
  non-supported `UMeshComponent`) fails closed with
  `ERR_EXTRACTION_UNSUPPORTED_COMPONENT_TYPE`; an actor carrying a registered non-mesh primitive
  (for example a decal) is extracted with `omitted_material_components.count >= 1` and a class
  list containing that class.
- **D19 (parser hardening).** A C++-produced payload containing a duplicate object key, a `NaN`
  or `Infinity` token, a float lexeme, a lone surrogate, an out-of-int32 integer, or `true` where
  an integer is required is **rejected**; and a payload containing a surrogate pair or an astral
  (non-BMP) character in an object path is accepted and canonicalises reproducibly (§6.4).
- **D20 (bit-encoding vectors).** The canonical scalar encoding is asserted against a fixed
  vector table — at minimum `1.0`→`3ff0000000000000`, `-0.0`→`8000000000000000`,
  `5e-324`→`0000000000000001`, `FLT_MAX`→`47efffffe0000000`, `1e300`→`7e37e43c8800759c` — by both
  the C++ producer and the Python validator, so a byte-order or precision regression is caught at
  the boundary rather than by inspection.

---

## 8. Failure semantics — closed error vocabulary

### 8.1 Extraction error codes

The extraction operation has a **closed** error vocabulary. The producer MUST set exactly one
of the following on any failure; it MUST NOT report a normative extraction failure as the
generic `ERR_OPERATION_FAILED` (`AtlasTransportServer.cpp:656-659`) or as an empty code.

| Code | Normative failure class |
|---|---|
| `ERR_EXTRACTION_REQUEST_INVALID` | malformed request; duplicate or case-insensitively duplicate entity IDs; non-canonical entity ID |
| `ERR_EXTRACTION_WORLD_UNAVAILABLE` | no valid editor world |
| `ERR_EXTRACTION_WORLD_NOT_EDITOR` | `WorldType != EWorldType::Editor` |
| `ERR_EXTRACTION_WORLD_PARTITION_UNSUPPORTED` | partitioned world |
| `ERR_EXTRACTION_LEVEL_SCOPE_INCOMPLETE` | a streaming level is not loaded or not visible |
| `ERR_EXTRACTION_LEVEL_SCOPE_INVALID` | the streaming-level array contains a null entry (engine-invariant break) |
| `ERR_EXTRACTION_SCOPE_CHANGED` | the scope revalidation after the actor scan disagrees with the snapshot (§3.2.1.4b) |
| `ERR_EXTRACTION_ENTITY_NOT_FOUND` | zero matches for a canonical entity ID |
| `ERR_EXTRACTION_ENTITY_AMBIGUOUS` | two or more actors match one entity ID |
| `ERR_EXTRACTION_ENTITY_TAG_CONFLICT` | one actor carries two or more distinct `atlas_entity:` tags |
| `ERR_EXTRACTION_UNSUPPORTED_COMPONENT_TYPE` | a registered `UMeshComponent` outside the two supported families (§3.8.1) |
| `ERR_EXTRACTION_ENGINE_IDENTITY_UNAVAILABLE` | `FEngineVersion::Current()` / `FApp::GetBuildVersion()` yields an empty version or build string |
| `ERR_EXTRACTION_PARENT_TAG_CONFLICT` | the attach parent's binding is ambiguous |
| `ERR_EXTRACTION_NON_FINITE` | NaN/±Inf in a source transform scalar |
| `ERR_EXTRACTION_MESH_COMPILING` | mesh asset mid async compilation |
| `ERR_EXTRACTION_MATERIAL_UNRESOLVED` | non-null material without a stable asset identity |
| `ERR_EXTRACTION_UNSUPPORTED_MATERIAL_SOURCE` | dynamic/transient material instance |
| `ERR_EXTRACTION_SEQUENCE_ACTOR_TYPE` | bound actor is not an `ALevelSequenceActor` |
| `ERR_EXTRACTION_SEQUENCE_ASSET_UNRESOLVED` | sequence asset or MovieScene missing |
| `ERR_EXTRACTION_UNSUPPORTED_SEQUENCE_SOURCE` | transient sequence asset |
| `ERR_EXTRACTION_SEQUENCE_RANGE_OPEN` | playback range has an open bound |
| `ERR_EXTRACTION_SEQUENCE_RANGE_INVALID` | degenerate/inverted range |
| `ERR_EXTRACTION_SEQUENCE_RATE_INVALID` | non-positive rate numerator or denominator |
| `ERR_EXTRACTION_PAYLOAD_TOO_LARGE` | response would exceed the transport bound (§9) |

Python-side codes (the validator's own failures, distinct from producer codes):

| Code | Condition |
|---|---|
| `ERR_EXTRACTION_SCHEMA` | closed-schema violation, wrong types (including `bool` where an integer is required), forbidden float, `NaN`/`Infinity` token, duplicate JSON object key, lone surrogate, out-of-range integer, bad hex lexical form, derived-field inconsistency (`extraction_kind`, `slot_count`, markers) |
| `ERR_EXTRACTION_NON_CANONICAL_ORDER` | an array is not in canonical order |
| `ERR_EXTRACTION_ERROR_CODE_UNKNOWN` | `success == false` with an absent or unrecognised `error_code` |

### 8.2 Fail-closed rules

- A failed extraction returns **no** value tree and no partial payload. No partial result may
  be presented as authoritative.
- Python MUST treat any of the following as hard failure: `success == false`; a missing
  `unreal_state_extraction` node; a schema violation; an unknown producer code; an empty
  `error_code` on failure.
- Any attempt to obtain extraction data through a write/mutation path is a contract violation.
- A schema violation MUST NOT be repaired, coerced, or partially accepted. Unknown-key
  stripping is forbidden: stripping would make the digest depend on the validator version.

---

## 9. Capacity, framing, and execution bounds

v1 does **not** redesign the transport. The existing bounds are the extraction's bounds.

1. **Message size.** The engine's named pipe is created with
   `MaxMessageSize = 1024 * 1024` (`AtlasTransportServer.cpp:46`) in `PIPE_TYPE_MESSAGE` mode
   (`:218`), and an oversize read is detected as `ERROR_MORE_DATA` and fails the request
   (`:251`). The Python client allocates a matching `1024 * 1024` read buffer
   (`planning/unreal_transport_named_pipe.py:212`).
2. **Framing.** Responses may carry the existing bounded frame
   `ATLAS_FRAME:<length>:<sha256>:\n<payload>`, verified client-side with a declared-length
   check and a SHA-256 check that fail closed on mismatch
   (`planning/unreal_transport_named_pipe.py:261-281`). This protocol is preserved and is not
   modified by this milestone.
3. **Fail closed before responding.** The producer MUST compute the serialized byte length of
   the response it is about to send and MUST fail closed with
   `ERR_EXTRACTION_PAYLOAD_TOO_LARGE` if the response would not fit the transport bound. An
   oversize extraction MUST NOT be truncated, chunked, or partially returned, and MUST NOT be
   allowed to surface as an opaque framing error after crossing the wire.
4. **No chunking in v1.** Multi-message extraction, pagination, streaming, and compression are
   explicitly out of scope; each is a transport-layer redesign with its own design gate.
5. **Execution bound.** Transport execution is bounded by a 5000 ms game-thread wait
   (`AtlasTransportServer.cpp:606`), producing `ERR_OPERATION_TIMED_OUT`
   (`:608`). That is a transport class, not an extraction class: a timeout means the extraction
   result is unknown, and Python MUST treat it as a failure, never as an empty or partial
   payload. Extraction MUST NOT extend, retry, or mask that bound.
6. **No new resource caps are invented here.** v1 defines no numeric entity/slot caps; the byte
   bound above plus explicit failure are the contract. Caps are not a substitute for
   measurement.

---

## 10. Python/C++ interoperability

The C++ producer obtains authoritative source facts from the engine and constructs the typed v1
value tree. It performs no canonicalization and no hashing.

Python is responsible for:

- transport interaction under the existing contract;
- closed-schema structural validation;
- canonicalization (RFC 8785) and SHA-256;
- fixture/audit orchestration;
- deterministic and hostile-input tests.

The contract is value-based and language-neutral. A future native C++ consumer or alternate
producer can replace the Python orchestration without changing the semantic state shape.

The C++ transport serializer is never itself the digest authority.

### 10.1 Operation surface

Two new READ operations are defined, one per extraction kind:

```text
extract_actor_state      (capability: inspect_actor, kind: read,
                          arguments: { entity_ids: [string, ...] })
extract_sequencer_state  (capability: sequencer,     kind: read,
                          arguments: { entity_ids: [string] })
```

Normative constraints on the seam:

- exactly one entity-ID set per request; `entity_ids` MUST also appear in `arguments` per the
  existing request contract (`planning/unreal_adapter_production.py:56-75`);
- the argument set is closed: `entity_ids` only;
- the response `observed_state` is exactly `{"unreal_state_extraction": <value tree>}` (§4.2);
- the operations MUST NOT be added to any VERIFY path or verification name set, and MUST NOT
  cause `verified=True` anywhere (`planning/unreal_evidence_contract.py:267-268`);
- the existing probes and their behaviour stay frozen; extraction neither calls nor modifies
  them.

### 10.2 Minimum architectural separation (read-only by construction)

"It does not call a write function" is not sufficient, because the existing transport already
contains both halves in one class: `AtlasTransportServer.cpp` (3105 lines) implements reads
(`inspect_world`, `inspect_target_actors`, `inspect_material_state`, `inspect_sequencer_state`, …)
*and* writes in the same translation unit — `set_actor_location` / `set_actor_rotation` /
`set_actor_scale` (`:665-679`), `apply_material_variant` / `apply_niagara_variant`
(`:687-711`), `set_sequencer_playback_range` (`:763`), render submission, plus the mutation
primitives `SetTaggedVariantName` (`:68-79`), `MarkPackageDirty` (`:78,1062,1234`),
`Package->Modify()` (`:764,1219,1539`), `UPackage::SavePackage` (`:1073,1252`) and
`NewObject<...>` (`:1582`). A read-only extractor placed inside that TU sits among them.

The minimum separation, therefore:

1. **A new translation unit** (and its header) in the same `AtlasUnrealTransport` module,
   containing the extractor and nothing else. It MUST NOT be a member of `FAtlasTransportServer`
   and MUST NOT receive a pointer or reference to the server.
2. **A one-way dispatch seam.** The server's dispatcher adds one branch that calls the extractor
   with the world and the request's arguments and receives either a value tree or an error code.
   The extractor never calls back into the server.
3. **A forbidden-token set, enforced by a source-level test.** The extractor TU MUST contain zero
   occurrences (outside comments) of: `MarkPackageDirty`, `Modify(`, `SavePackage`,
   `CreatePackage`, `NewObject<`, `SpawnActor`, `Destroy(`, `Rename(`, `SetActor`,
   `SetIsTemporarilyHiddenInEditor`, `SetStaticMesh`, `SetMaterial`, `CreateDynamicMaterialInstance`,
   `SetSequence`, `SetPlaybackRange`, `InitializePlayer`, `GetSequencePlayer`, `LoadObject`,
   `StaticLoadObject`, `TryLoad`, `FSoftObjectPath` loading calls, and `Tags.Add`/`Tags.Remove`.
   The repo already has precedent for source-level assertions of this kind
   (`tests/m10/test_m10_defect_d2_sequence_range.py:74-102` asserts C++ source strings), so this is
   a testable requirement rather than a review convention.
4. **An engine-accessor allowlist.** The extractor may call only the accessors this design names:
   world/level/actor identity and transform accessors, the visibility accessors of §3.6, the
   registered-component enumeration and material helpers of §3.8, and the sequencer accessors of
   §3.9. Anything else is a design change first.

Why this is the minimum rather than a redesign: the transport wire protocol, the request/response
contract, the authorization path and the existing operations are all untouched; only the
*placement* of new read code is constrained, and the constraint is checkable mechanically.

### 10.3 Sequencer read path is side-effect-free (verified)

The Sequencer accessors used by §3.9 were checked for lazy behaviour in the installed source:

- `ALevelSequenceActor::GetSequence()` is `return LevelSequenceAsset;`
  (`Runtime/LevelSequence/Private/LevelSequenceActor.cpp:332-335`) — a pointer read;
- `ALevelSequenceActor::GetSequencePlayer()` is likewise `return SequencePlayer;`
  (`:145-150`) — it does **not** lazily construct a player, but v1 still forbids calling it,
  because it is not needed and the read surface is kept minimal (§10.2.3);
- `ULevelSequence::GetMovieScene()` is `return MovieScene;`
  (`Runtime/LevelSequence/Private/LevelSequence.cpp:733-736`) — a pointer read;
- `UMovieScene::GetPlaybackRange()`, `GetTickResolution()` and `GetDisplayRate()` return members
  or member-derived values (`MovieScene/Public/MovieScene.h:801,809-812,822-825`) — no
  evaluation, no playback, no sequencer UI involvement;
- object-path resolution is `UObject::GetPathName()`, which reads the outer chain and loads
  nothing.

The mutating Sequencer APIs are correspondingly excluded by §10.2.3: `SetSequence`
(`LevelSequenceActor.cpp:337-347`, which touches the player), `InitializePlayer` /
`InitializePlayerWithSequence` (`LevelSequenceActor.h:304-307`), `SetPlaybackRange`
(`MovieScene.h:998,1007`) and `MovieScene->Modify()`.

The one engine-internal effect on the extraction read path is `ConditionalPostLoad()` inside the
material resolution helper (§3.8.3.6): an object-graph/lazy-load effect, explicitly distinguished
from persistent editor-state mutation. The live gate measures package dirty state across the call
(§11.3) so the distinction is verified rather than asserted.

---

## 11. Live evidence and fixture policy

### 11.1 Fixture quarantine: `AtlasSequencerIntegrationFixture.cpp`

`unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Private/AtlasSequencerIntegrationFixture.cpp`
is **quarantined** from the extraction gate. Verified properties, each of which conflicts with
this contract:

| Property | Evidence | Why it disqualifies the fixture |
|---|---|---|
| runs from a core ticker at 0.25 s | `FTSTicker::GetCoreTicker().AddTicker(...)`, `:72` | provisioning races extraction; the actor set is not fixed when a request arrives |
| spawns into the live editor world | `GEditor->GetEditorWorldContext().World()`, `:21`; `World->SpawnActor<ALevelSequenceActor>`, `:41` | mutates the very world under extraction |
| engine-generated object name | `SpawnParams.NameMode = ESpawnActorNameMode::Requested`, `:38` — the mode means "if the supplied name is already in use then generate an unused one" (`Engine/Classes/Engine/World.h:496-509`) | the actor object path is session-history dependent |
| transient, unnamed sequence asset | `NewObject<ULevelSequence>(GetTransientPackage(), NAME_None, RF_Transient)`, `:50` | supplies `/Engine/Transient.LevelSequence_<n>` with a counter suffix, violating the stable non-transient sequence identity of §3.9.3.2 |
| CVar- and clock-dependent MovieScene | `ULevelSequence::Initialize()` reads `CVarDefaultTickResolution` / `CVarDefaultDisplayRate` and stamps `MetaData->SetCreated(FDateTime::UtcNow())` (`LevelSequence/Private/LevelSequence.cpp:103-127`) | tick/display rates and embedded metadata are not reproducible |

This task does **not** modify the fixture. Two consequences are recorded instead:

1. The fixture MUST NOT be the extraction target of any live assertion. Its presence in the
   world is, however, harmless to the contract **by construction**, because extraction never
   enumerates the world's actor set: it binds explicitly requested entities and records the
   level scope, so a foreign transient actor cannot enter the payload. That is the design-level
   quarantine.
2. The harness's own entity-tagged fixture (tag `atlas_entity:FIELD_SURFACE`,
   `AtlasUnrealTransport.cpp:24`) remains a valid `actor_state` target.

### 11.2 Fixture the sequencer gate requires (implementation deliverable, not done here)

The existing `ALevelSequenceActor` fixture carries only the non-entity tag
`atlas_sequencer_fixture` (`AtlasUnrealTransport.cpp:26,299-328`), and its sequence asset is a
stable saved package `/Game/AtlasTest/AtlasSequencerFixtureSequence.AtlasSequencerFixtureSequence`
(`AtlasUnrealTransport.cpp:335-339,360-363`). It therefore satisfies §3.9.3.2 but **cannot be
bound by an entity ID**. The resolved live gate requires one new fixture actor that carries both
an `atlas_entity:<id>` tag and that stable sequence asset. That fixture is an implementation
deliverable of the next rung, listed here so the gate is not discovered to be unbuildable later.

### 11.3 Live gate obligations

The live gate must prove, against the disposable `AtlasRenderFixture` world
(`EWorldType::Editor`, `bCreateWorldPartition = false`, `AtlasUnrealTransport.cpp:67-69`):

- editor-world selection is deterministic and never falls back to context iteration;
- `world_type` is `editor`, `is_partitioned_world` is `false`, and the recorded level scope is
  the world's complete level set;
- engine identity equals the version the engine reports in its own log, and is not the legacy
  hardcoded literal (`AtlasTransportServer.cpp:120`);
- unique entity binding succeeds; duplicate and case-variant duplicate bindings fail closed;
- a source tag whose ID does not match the canonical grammar is not addressable in v1
  (§3.3.3.5), and a case-variant duplicate tag on two actors is ambiguous rather than
  first-match;
- actor transform facts are exact **at the binary64 level**;
- parent `none` / `unbound` / `bound` are distinguishable, with the unbound parent's locator
  recorded;
- visibility source flags and the derived aggregate are both present, and
  `unrecorded_hidden_inputs` is the frozen literal;
- material records are identical across component construction order, and a null-mesh
  component is recorded rather than omitted;
- `asset_slot` versus `override` versus `resolved` material paths are distinguished, including a
  Nanite override case where the engine substitutes, and the collision pair of §7.4 D17 is
  asserted live;
- an unsupported mesh component class fails closed, and a non-mesh material-bearing primitive
  appears in `omitted_material_components` (§7.4 D18);
- a transient/dynamic material instance fails closed;
- explicit `ALevelSequenceActor` entity binding succeeds; a non-sequence actor fails closed;
- playback bounds, tick resolution and display rate are exact, and an open range fails closed;
- **canonical identity is request-independent live**: the same fixture entity extracted through
  two different request spellings (`cam01` / `CAM01`, and a `_1`-suffixed id against its
  leading-zero neighbour) yields byte-identical payloads and digests (§7.4 D14, D15);
- **scope revalidation is exercised live**: the recorded scope equals the scope scanned
  (§3.2.1.4), and the gate reports the observed level set;
- repeated extraction in one session yields identical bytes and digest;
- repeated extraction across two fresh editor sessions yields identical bytes and digest;
- the canonicalizer passes the RFC 8785 vectors in-process and rejects the out-of-domain ones;
- **the reported payload size is recorded** for each gate case, so the transport bound of §9 is
  characterised by measurement rather than assumption;
- **no persistent editor-state mutation** is attributable to the extraction operation: the level
  package's and the actor's package dirty flags, plus the count of dirty packages in the editor,
  are compared immediately before and after the extraction call. The harness's own provisioning
  calls `FixtureActor->MarkPackageDirty()` (`AtlasUnrealTransport.cpp:438`), so dirty-state
  assertions MUST be scoped to the extraction operation and MUST NOT be asserted across editor
  startup.

The frozen M4–M10 render/recovery fixtures are not mutated by this gate.

---

## 12. Non-goals and scope prohibitions

This milestone does NOT implement, and confirmed findings MUST NOT be "solved" by expanding into:

- M12.5 semantic verification;
- semantic event abstraction;
- temporal observation / state delta;
- cross-engine equivalence;
- render-job recovery;
- artifact/receipt issuance;
- persistence, or a second durable state authority;
- generic Unreal scene reconstruction;
- arbitrary-geometry extraction;
- Nanite/Lumen internals;
- VFX simulation state;
- camera/lens physical calibration beyond data exposed by explicit target inspection;
- material parameter evaluation or runtime shader state.

Additional prohibitions introduced by Revision 2:

- **World Partition support** (cells, external actor packages, cell streaming state) is out of
  scope; partitioned worlds are refused (§3.2.1).
- **Forced level loading / visibility adjustment** is out of scope; extraction refuses rather
  than prepares (§3.2.1).
- **Chunked, paginated, streamed, or compressed transport** is out of scope; capacity fails
  closed (§9).
- **Repair of the source** — no rename, no re-tag, no material fix-up, no dirty-state rollback —
  is out of scope. Source defects are reported, never corrected.
- **Semantic interpretation** (quaternion sign, `±0` canonicalisation, rename tolerance,
  approximate comparison) is out of scope for the extractor (§5.4).
- **Per-class material semantics** (landscape, widget, procedural/dynamic mesh and similar
  overrides) are out of scope: such classes fail closed rather than being half-modelled (§3.8.1).
- **Generic `UMeshComponent` support** is out of scope. v1 supports the `UStaticMeshComponent` and
  `USkinnedMeshComponent` families only; a claim of general mesh-component support would require
  per-class material models this design does not define.
- **Material extraction for non-mesh primitives** (decals, landscape components, particles, text
  and billboard renderers, and similar) is out of scope and is declared in-band through
  `omitted_material_components` (§3.8.1a), never silently.

---

## 13. Acceptance gates

Before implementation can merge:

1. design review is independently CLEAR;
2. the C++ extraction producer is read-only by code inspection, including no package dirtying;
3. Python contract tests prove the closed schema, the reserved-key rejection, and the full
   error vocabulary;
4. determinism tests D1–D20 (§7.4) pass, including deliberately different `PYTHONHASHSEED`
   values, deliberately reordered fixture construction, the hostile canonical-identity matrix
   (D14, D15), the scope-revalidation and material-collision pairs (D16, D17), the parser
   hardening cases (D19) and the RFC 8785 vectors;
5. Python 3.9/3.11 parity passes where applicable;
6. the Unreal 5.6 live gate passes against a disposable fixture (§11.3);
7. repeated extraction yields byte-identical canonical bytes and digest within and across
   sessions;
8. duplicate, case-variant-duplicate and ambiguous identity fixtures fail closed, and a
   `cam01`/`CAM01` pair of requests produces identical digests;
9. no M4–M10 behaviour changes and no M12.5 changes;
10. no workflow/action-runner tests are required unless separately authorized;
11. `AtlasSequencerIntegrationFixture.cpp` is unmodified, or its modification is separately
    authorized and disclosed;
12. every acceptance marker is engine-derived and Python-asserted per §4.3, with the
    compile-time `FReal` assertion present, and a test proves that a marker written as a
    constant is caught (a stub that reports `world_type: "editor"` for a non-editor world must
    fail);
13. the extraction boundary is proven un-augmented (§4.2.8): a response carrying
    `_session_identity` at the extraction boundary fails closed, and no code path strips it;
14. the architectural separation of §10.2 holds: the extractor lives in its own translation
    unit, the server's dispatch is one-way, and the source-level forbidden-token test passes
    over that unit;
15. the material scope of §3.8.1 is enforced: an unsupported registered `UMeshComponent` fails
    closed, and no unsupported mesh component can disappear silently;
16. the parser hardening of §6.4 is enforced by tests (duplicate keys, `NaN`/`Infinity`, float
    lexemes, lone surrogates, out-of-int32 integers, `bool`-as-integer);
17. the implementation-readiness checklist of §17 is answered in writing for every normative
    requirement, with any residual ambiguity classified as architectural (design change) or
    implementation detail (allowed).

---

## 14. Implementation shape after design clearance

Only after an independent design review returns CLEAR:

```text
Unreal C++ (new, read-only)
  ├─ extraction producer: explicit level-set scan, closed value tree
  └─ no canonicalization, no hashing, no mutation

Python (new)
  ├─ extraction contract: closed-schema validation, reserved-key rejection
  ├─ RFC 8785 canonicalizer + SHA-256 (own module, own vectors)
  ├─ hostile/determinism tests D1–D13
  └─ live Unreal 5.6 extraction gate
```

The existing `inspect_target_actors`, `inspect_material_state`, `inspect_sequencer_state` and
`inspect_world` remain the frozen M4–M10 source probes. They are **not** the extraction
contract, extraction does not call them, and their world-selection and first-match behaviour is
**replaced** for extraction rather than refined (§3.1.1).

---

## 15. Revision history and finding resolution map

Revision 2 remediated the prior independent architectural red-team (verdict BLOCK). Each
finding's classification, repository evidence and the resulting design change are recorded in
`docs/UNREAL_STATE_EXTRACTION_FIDELITY_V1_REV2_REVIEW.md`. Summary of the contract changes:

| Finding | Revision 2 change |
|---|---|
| F1 transform precision | source scalars are binary64; canonical form is a 16-hex-digit binary64 bit pattern; `transform.source_component_type: "binary64"` (§3.7, §5.1–5.2) |
| F2 transport/session metadata | closed value tree under one `unreal_state_extraction` key; reserved-key rejection; digest input reconstructed from declared fields only; `session_identity` is envelope-only (§4) |
| F3 loaded-world scope | complete loaded-visible scope is a precondition; partitioned worlds refused; explicit level set replaces `TActorIterator`; the scope is recorded in the payload (§3.2) |
| F4 parent identity | three states `none`/`unbound`/`bound`; the unbound state carries the parent's locator (§3.5) |
| F5 visibility semantics | raw flags and the derived aggregate are both recorded and separately labelled; `GIsEditor` is recorded; unrecorded input `bEditable` is declared in-band (§3.6) |
| F6 sequencer fixture | fixture quarantined with five enumerated conflicts; foreign transient actors are harmless by construction (no world actor-set enumeration); a new entity-tagged sequencer fixture is an implementation deliverable (§11.1–11.2) |
| F7 FName case semantics | canonical entity-ID grammar; case-insensitive uniqueness; ambiguity rejection; ordinal/case-sensitive string discipline; the tag's stored casing is not an extraction fact (§3.3) |
| F8 source identity | canonical identity, source provenance and mutable locator separated; rename is expected to change the digest; the duplicated nested `source_identity` object is removed; GUID identity rejected on engine evidence (§3.4) |
| F9 material state machine | total component/slot state machine with assigned-versus-resolved separation, null-mesh and compiling states, Nanite substitution, transient rejection, and an explicit non-equivalence statement for `verify_material_variant` / `atlas_material_variant:` (§3.8) |
| F10 numeric fail-closed | finiteness tested at the binary64 source; no narrowing exists, so overflow/underflow cannot alter a fact; both classes are mandatory tests (§5.5–5.6, D11–D13) |
| F11 quaternion / zero | `q`/`-q` and `±0` are distinct; source-fidelity identity is explicitly separated from semantic equivalence (§5.4) |
| F12 trust boundary | extraction result is untrusted input; validation is not verification; digest is not a verdict; no second verification authority; the M12.5 seam is reserved and not implemented (§2) |
| F13 world selection / version | `GEditor->GetEditorWorldContext().World()` only; `EWorldType::Editor` named explicitly; three existing order-dependent selections replaced not reused; engine version sourced from `FEngineVersion::Current()` / `FApp::GetBuildVersion()` (§3.1) |
| F14 Sequencer validity | explicit validity predicate; v1's own `numerator > 0 && denominator > 0` rather than `FFrameRate::IsValid()`; legacy `end_frame` asymmetry disclosed; the unreachable multiple-candidate condition removed (§3.9) |
| F15 errors and capacity | closed extraction error vocabulary with class→code mapping; explicit Python-side codes; 1 MiB bound, framing, pre-response size check, no chunking, timeout classification (§8, §9) |

Revision 1's five original ambiguities (world selection, numeric bytes, duplicate tags,
material component/slot semantics, Sequencer identity/bounds/rates) remain closed; where
Revision 2 supersedes a Revision 1 sentence, the superseded text is that sentence's premise
(e.g. "All Unreal transform scalar values in v1 originate as `float32` source facts") and the
replacement is normative above.

Second-pass review of Revision 2 itself (hostile, self-directed) produced seven further contract
changes, all applied above and itemised in the review document (SP-1..SP-7):

| Second-pass item | Change |
|---|---|
| SP-1 | the matched tag's stored casing (`entity_tag_literal`) is removed: its determinism cannot be established from the shipped engine sources, and an unprovable field must not be digested (§3.3.3.6, §3.4) |
| SP-2 | the "non-canonical source tag that would have matched" failure arm (and the parallel parent clause) is removed as unreachable normative text and replaced by an explicit addressability limitation (§3.3.3.5, §3.5) |
| SP-3 | acceptance markers MUST be engine-derived and Python-asserted, with compile-time assertions where applicable (§4.3) |
| SP-4 | the extraction boundary MUST run un-augmented; stripping a session key is forbidden (§4.2.8) |
| SP-5 | the material component set is filtered to registered components (§3.8.1) |
| SP-6 | an empty engine version/build string is a closed failure (`ERR_EXTRACTION_ENGINE_IDENTITY_UNAVAILABLE`) (§8.1) |
| SP-7 | the RFC 8785 vector obligation is split: in-domain vectors must pass byte-exactly, out-of-domain (float/exponent) vectors must be rejected, not passed (§6.4, §7.4 D9) |

### Revision 3 change log (architectural-review remediation + third hostile self-review)

Revision 3 closes the findings raised against Revision 2 by the architectural review, plus the
issues the third self-review found in Revision 2's own text. Every classification, citation and
remaining item is recorded in `docs/UNREAL_STATE_EXTRACTION_FIDELITY_V1_REV2_REVIEW.md`.

| Item | Change |
|---|---|
| R3-1 | **canonical entity identity is request-independent**: `entity_id`, `parent.entity_id` and the Sequencer `entity_id` are the ASCII-uppercase canonical form of the matched binding, never the caller's spelling (§3.3.4, §4.6) |
| R3-2 | **the engine's real `FName` identity model is stated**: case-folded (base, number) with `ParseNumber` splitting a trailing `_<digits>`, the `NAME_EXTERNAL_TO_INTERNAL` offset, rendering round-trip, and the forbidden number-blind / index-only / string-round-trip comparisons (§3.3.3) |
| R3-3 | numbered-name awareness is a binding rule: a `_<digits>` suffix is identity, so `cam_1`, `cam_01` and `cam` are three different entities (§3.3.5.7, §7.4 D15) |
| R3-4 | **material component scope is closed by class**: `UStaticMeshComponent` and `USkinnedMeshComponent` families only; any other registered `UMeshComponent` fails closed with `ERR_EXTRACTION_UNSUPPORTED_COMPONENT_TYPE`, with the subclass inventory that proves a generic contract is not implementable (§3.8.1) |
| R3-5 | non-mesh material-bearing primitives are declared in-band via `omitted_material_components` (`count` + sorted class list) instead of disappearing (§3.8.1a, §3.4.2) |
| R3-6 | **slot records carry the assignment source facts** (`asset_slot_material_asset_path`, `override_material_asset_path`) beside `resolved_material_asset_path`, closing the collision in which two different mesh-asset slots under one override produced identical records (§3.8.2, §7.4 D17) |
| R3-7 | **scope snapshot + post-scan revalidation** with `ERR_EXTRACTION_SCOPE_CHANGED`, explicit null-slot and null-streaming-level rules, the forbidden narrowed containers (`StreamingLevelsToConsider`, `UActorContainer::Actors`), and duplicate scope entries permitted so a two-instance world is not falsely refused (§3.2.1.4–6, §7.4 D16) |
| R3-8 | the bit encoding is stated as the **integer value** of the binary64 pattern (endian-neutral), with the mismatched-pair counter-example and a fixed vector table (§5.2, §7.4 D20) |
| R3-9 | all non-finite classes are refused before encoding, including quiet/signaling NaN and payload bits (§5.5) |
| R3-10 | the material helper's `ConditionalPostLoad()` is declared as an engine-internal read-path effect, and the Sequencer read path is verified side-effect-free from source (§3.8.3.6, §10.3) |
| R3-11 | **minimum architectural separation**: own translation unit, one-way dispatch, source-level forbidden-token test, engine-accessor allowlist (§10.2) |
| R3-12 | **parser hardening before canonicalization**: duplicate JSON keys, `NaN`/`Infinity` tokens, float lexemes, lone surrogates, `bool`-as-integer and out-of-int32 integers, each with the measured default behaviour (§6.4, §7.4 D19) |
| R3-13 | **field provenance classification** of the whole payload, `extraction_kind` derived from content rather than copied from the request, and the scope-versus-identity rule (§4.5, §4.6) |
| R3-14 | rate pairs are recorded verbatim and never reduced to lowest terms (§3.9.3.6), and the implementation-readiness decisions are frozen (§17) |

Implementation remains unauthorized until an independent review confirms that these rules are
internally consistent, implementable in UE 5.6, and compatible with the frozen M4–M10 and
M12.5 boundaries.

---

## 16. Architectural intent

The major objective is to make Unreal state factual, bounded, deterministic and portable
across Python/C++ boundaries before semantic layers begin interpreting it.

The design keeps v1 small on purpose: explicit entities, one world, one recorded level scope,
one closed value tree, one canonicalization standard, one digest that means exactly one thing,
and a closed vocabulary for every way it can fail. Where Revision 1 bought simplicity with
lossy representation, Revision 2 pays the cost back in explicit state — binary64 instead of
binary32, three parent states instead of two, raw flags beside a derived aggregate,
assigned-beside-resolved materials, recorded scope beside a refused world.

This work is deliberately independent of M12.5. It improves the substrate that a future
verifier can consume without changing the existing verification authority.

---

## 17. Implementation-readiness decisions (frozen)

The test this section answers is: *could two competent engineers implement a requirement
differently while both honestly claiming compliance?* Where the answer was yes, the decision is
frozen here rather than left to the implementer. Each row is a decision, not a discussion.

| Question an implementer would reasonably ask | Frozen answer | Kind |
|---|---|---|
| How is `hidden_in_editor` produced? | By calling `AActor::IsHiddenEd()` itself. Recomputing it from the readable flags is **forbidden**: the engine's version folds in `bEditable`, which the extractor cannot read, so a recomputation would silently disagree (§3.6.3). | architectural |
| How is the canonical ID uppercased? | `ASCII-uppercase` applied to an ID that has already passed the grammar of §3.3.2, i.e. ASCII-only input, so no Unicode case mapping is involved. `Locale`-sensitive or Unicode case folding MUST NOT be used. | implementation detail, frozen to avoid divergence |
| Are frame rates reduced to lowest terms? | No. Verbatim int32 pairs (§3.9.3.6). | architectural |
| Which component-enumeration call? | `Actor->GetComponents<UMeshComponent>(Out, /*bIncludeFromChildActors=*/false)`, then `IsRegistered()`, then the class test of §3.8.1. Child-actor components are excluded by the explicit `false`. | implementation detail |
| What is `slot_count`? | `len(slots)` — the number of emitted slot records, not a re-read of `GetNumMaterials()` (they must agree; Python asserts it). | implementation detail |
| When is `mesh_asset_path` null? | Exactly when `mesh_state == "no_mesh_asset"`; otherwise it is the non-null asset's stable object path. | architectural |
| When is `parent.actor_object_path` null? | Exactly when `parent.binding == "none"`. | architectural |
| How is `world_name` produced? | `World->GetName()` on the authoritative world. | implementation detail |
| How is `world_type` produced? | The ASCII-lowercased engine rendering of `World->WorldType` (`LexToString`), which MUST equal `"editor"`. | implementation detail, frozen to avoid divergence |
| Which actors are skipped in the scan? | Entries where `!IsValid(Actor)` — null slots and pending-kill actors (§3.2.1.5). Nothing else is skipped. | architectural |
| Which levels make up the scope? | The persistent level plus every `GetStreamingLevels()` entry that is loaded and visible, snapshotted once and revalidated (§3.2.1.4). | architectural |
| What happens if two scope levels share a package? | Two entries are recorded; no refusal (§3.2.1.6). | architectural |
| How are object paths ordered? | UTF-16 code-unit order, implemented as `str.encode("utf-16-be")` byte comparison in Python and ordinal `TCHAR` comparison in C++ (§7.3). Python's default `sorted()` is forbidden for object paths. | architectural |
| How are strings that are not entity IDs compared? | Case-sensitive ordinal comparison (§3.3.6). Only tag binding uses `FName` equality. | architectural |
| How is a tag compared? | `FName` equality (`operator==` / `Contains`). `IsEqual(..., bCompareNumber=false)`, comparison-index-only tests, hashes and string round-trips are forbidden (§3.3.3). | architectural |
| What is the exact hex format? | 16 lowercase hex digits of the unsigned 64-bit integer value of the double's bit pattern; C++ `%016llx`, Python `f"{bits:016x}"` (§5.2). | implementation detail, frozen to avoid divergence |
| Where is the digest stored? | Nowhere inside the value tree; it is computed about the tree (§4.2.7, §6.5). | architectural |
| Is `extraction_kind` taken from the request? | No — derived from the populated collection and re-derived by Python (§4.5). | architectural |
| What is `omitted_material_components.classes` order and content? | Sorted, deduplicated class names in canonical collation; `count` is the number of such registered components, so multiplicity is visible even when classes repeat (§3.8.1a). | implementation detail |
| May the extractor load anything? | No explicit load: no `LoadObject`, `StaticLoadObject`, `TryLoad`, or forced level load; the only lazy effect permitted on the read path is the engine-internal `ConditionalPostLoad()` inside the material helper (§3.8.3.6, §10.2.3). | architectural |
| May two implementations differ in the number of transport round trips? | Yes. The operation surface is one request and one response per extraction (§10.1); polling, retry and chunking are forbidden (§9.4). | implementation detail |
| What if the payload would be large? | Fail closed with `ERR_EXTRACTION_PAYLOAD_TOO_LARGE` before responding; never truncate (§9.3). | architectural |

Anything not decided above is either already normative elsewhere in this document or is genuinely
an implementation detail with no observable effect on the canonical bytes, the digest, or the
failure vocabulary. An implementer who finds a requirement where two readings produce different
bytes MUST raise it as a design change before writing code.
