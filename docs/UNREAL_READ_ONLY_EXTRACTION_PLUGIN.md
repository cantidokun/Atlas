## Current evidence state — September 29, 2026 UTC

PR #146 is merged at 8f601184e62da2362ec38c948e61b7ff8058f95b. The portable read-only plugin is validated as an observation mechanism; it does not establish U1 production authority.

The synthetic closeout project was C:\Users\Gavin's PC\Desktop\AtlasU1MockTwin_CleanValidation\AtlasU1MockTwin.uproject.

Final mock status: VALIDATED / FROZEN. Positive actor and sequencer extraction passed; target-map/process identity was proven through fresh isolated runs; the final A–H selected runs completed without reproducing the earlier crash/231 combination; the final independent review returned GLM CLEAR and GPT-SOL-6 CLEAR WITH MINOR FINDINGS with no blockers.

The plugin is ready for its intended next use: evidence collection from the real production Unreal project. No synthetic observation may be copied into planning/m12/expectation.py.

# Unreal read-only extraction plugin (U1 evidence mechanism)

Design and evidence record for `unreal/plugins/AtlasReadOnlyExtraction` — the portable,
read-only Unreal Editor plugin that will collect U1 extraction evidence from the real
production Unreal project once that project is supplied.

This document describes an **observation mechanism**. It is not a normative artifact, it
grants no authority, and it changes none of REV10, R25, R2-A or R2-B.

## 1. Purpose and scope

U1 (`ATLAS_M12_6_R2B_NORMATIVE_DESIGN_REV10.md` §VI, R25 §V.5/V.6.1) needs values observed
from *real production project content*. The existing extraction producer and transport
server live only inside the Atlas validation harness
(`unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport`), alongside fixture provisioning,
write operations, blueprint/material/Niagara/render surfaces and a full automation/test
suite. Points 1–5 of the U1 integration investigation established that:

* the extraction core itself is read-only and harness-independent;
* the surrounding module is not, and copying it wholesale into a production project would
  place write-capable operations and their dependency surface inside that project;
* the transport uses a fixed, global, single-instance pipe name with no engine-verifiable
  authorization token, so the safety of hosting it comes from *what it can do*, not from
  what a caller claims.

The plugin therefore carries the extraction core forward unchanged and exposes it through a
closed, two-operation, opt-in transport. Nothing else.

## 2. Architecture

```
unreal/plugins/AtlasReadOnlyExtraction/
├── AtlasReadOnlyExtraction.uplugin          Editor module, EnabledByDefault=false, no content, no plugin deps
├── .gitignore                               Binaries/ Intermediate/ Saved/ DerivedDataCache/
├── README.md                                operator-facing usage
└── Source/AtlasReadOnlyExtraction/
    ├── AtlasReadOnlyExtraction.Build.cs     Core, CoreUObject, Engine, UnrealEd, LevelSequence, MovieScene, Json
    ├── Public/AtlasReadOnlyExtraction.h                 module interface, runtime state accessors
    ├── Public/AtlasReadOnlyExtractionContract.h         the declared contract (operations, transport, startup)
    ├── Public/AtlasReadOnlyExtractionServer.h           the reduced transport server
    ├── Private/AtlasReadOnlyExtraction.cpp              module startup: opt-in gated, provisions nothing
    ├── Private/AtlasReadOnlyExtractionContract.cpp      constants, capability/kind pairs, opt-in policy
    ├── Private/AtlasReadOnlyExtractionServer.cpp        pipe loop, envelope, closed dispatch
    ├── Private/AtlasReadOnlyExtractionAutomationTests.cpp  8 fixture-free automation tests (dev builds only)
    ├── Private/AtlasStateExtraction.cpp                 carried forward byte-for-byte from the harness
    └── Private/AtlasStateExtraction.h                   carried forward byte-for-byte from the harness
```

Python side:

* `planning/unreal_read_only_extraction.py` — the Python half of the declared contract
  (pipe name, source string, operations, capabilities, opt-in switches, config keys, wire
  bound, session-identity fields) plus request construction and transport opening. It
  imports only `pathlib`, `typing` and the existing transport modules.
* `tests/test_unreal_read_only_extraction_plugin.py` — static gates (see §4).
* `tests/test_unreal_read_only_extraction_live_gate.py` — live gates against a real editor.

### Operation surface

| operation                 | capability      | kind   |
| ------------------------- | --------------- | ------ |
| `extract_actor_state`     | `inspect_actor` | `read` |
| `extract_sequencer_state` | `sequencer`     | `read` |

The surface is closed in two places: `ValidateRequest` refuses any other operation name with
`ERR_UNKNOWN_OPERATION`, and the game-thread dispatcher's table contains only these two calls
into the extraction core. A request that names an exposed operation with a write kind or a
foreign capability is refused with `ERR_MISSING_ARGUMENT` — a malformed request, not a write
path.

### Envelope, session identity and wire bound

The envelope is the existing Atlas transport contract, key for key (the static gate parses
both implementations and compares the key sets):

* request: `request_id`, `operation_name`, `capability`, `kind`, `arguments.entity_ids`,
  `entity_ids`, `authorization_id`, `schema_version`;
* response: `request_id`, `operation_name`, `success`, `error`, `source`, `schema_version`,
  `error_code`, `session_identity`, `entity_ids`, `observed_state`;
* `session_identity`: `editor_session_id`, `project_identity`, `engine_version`,
  `process_id`, `process_creation_time_utc`, `server_start_time_utc`;
* extraction results are wrapped under `observed_state.unreal_state_extraction`, exactly as
  the extraction schema expects;
* the wire bound is the existing 1 MiB limit, and a response that would exceed it fails
  closed with `ERR_EXTRACTION_PAYLOAD_TOO_LARGE` instead of being truncated.

`engine_version` is *sourced* (`FEngineVersion::Current()`), not hard-coded, so the plugin
reports the engine it was actually built into on any engine version — and it branches on
none of them.

### Startup policy

```cpp
FDecision Evaluate(const FString& CommandLine, bool bConfigEnabled, const FString& ConfiguredPipeName);
```

Pure function, no engine state. The transport starts only when the operator opted in:

* `-AtlasReadOnlyTransport` (optionally with `-AtlasReadOnlyTransportPipe=\\.\pipe\<name>`), or
* `[AtlasReadOnlyExtraction] bReadOnlyTransportEnabled=True` in `Engine.ini`.

Loading the plugin never opens a pipe. The default pipe is
`\\.\pipe\AtlasReadOnlyExtraction`, deliberately distinct from the harness pipe
`\\.\pipe\AtlasUnrealTransport`, so the two servers can never contend for one name and an
evidence run can always attribute the response to a mechanism.

`authorization_id` stays the Atlas contract field it always was. The plugin does **not**
treat it as an engine-verifiable token and invents no cryptographic authorization: the goal
is a smaller exposed operation surface, not a new trust authority.

## 3. What was deliberately omitted

Relative to `AtlasUnrealTransport`:

* every write operation: `set_actor_location`, `set_actor_rotation`, `set_actor_scale`,
  `apply_material_variant`, `apply_niagara_variant`, `set_sequencer_playback_range`,
  `set_blueprint_metadata`, `compile_blueprint`, `configure_render`, `submit_render`,
  `reconcile_render_jobs`;
* every non-extraction read operation (`inspect_world`, `inspect_target_actors`,
  `inspect_material_state`, `inspect_niagara_state`, `inspect_sequencer_state`,
  `inspect_blueprint_state`, `inspect_render_state`, `inspect_render_job`,
  `get_capabilities`, and the `verify_*` operations);
* all fixture provisioning: no ticker, no `SpawnActor`, no `CreatePackage`, no `SavePackage`,
  no `LoadObject`, no `/Game/AtlasTest/...`, no harness commandlet;
* the witness journal, render-job registry, HMAC attestation and report machinery;
* the harness's UI/Kismet/render-pipeline/asset-registry dependencies.

## 4. Read-only guarantees and how they are enforced

| guarantee | enforcement |
| --------- | ----------- |
| no write-capable API in the shipped sources | static gate over the whole plugin, using the harness's own `FORBIDDEN_TOKENS`/`FORBIDDEN_ENGINE_PATHS` tuple imported from `tests/test_unreal_state_extraction_readonly_source.py` (the plugin cannot weaken a list it does not own) |
| the core is unaltered | `AtlasStateExtraction.{h,cpp}` byte-identical to the harness copies (hash equality, both directions) |
| the surface is closed | static gates on the operation names + live refusals over the real pipe (write and render probes → `ERR_UNKNOWN_OPERATION`) |
| nothing is provisioned at startup | static gate (no ticker/provisioning calls) + live gate (opt-out run: pipe unreachable) |
| extraction does not dirty packages | `Atlas.ReadOnlyExtraction.PackageDirtyInvarianceAcrossExtractionCall` (dynamic, in-editor) |
| the response is untrusted evidence | the Python boundary validates it; the plugin emits no decision vocabulary (static gate) and no verification authority |

Each static "absence" gate carries a **control**: the same scan is run against the harness
sources, which do contain the write operations, the write tokens and the fixture
identifiers — so absence in the plugin is a measurement, not an assumption.

## 5. Fixture isolation

Asserted over every plugin source (including the guarded test file):

* no `AtlasUnrealHarness`, `AtlasExtractionFixture`, `AtlasRenderFixture`,
  `AtlasSequencerFixture`, `AtlasSequencerFixtureSequence`, `AtlasFieldSurfaceFixture`,
  `AtlasTest`, `atlas_entity:FIELD_SURFACE`, `IMPL_PERM_A`, `IMPL_MATERIAL_OVERRIDE_A`;
* no `/Game/` content path anywhere;
* the automation tests are fixture-free: they use an entity id no project content can carry
  (`ATLAS_U1_PROBE_ENTITY_ABSENT`) and assert the closed refusal, never fixture behaviour;
* the `.uplugin` declares one module, no plugin dependencies and no content.

A host project therefore loads the plugin with **no** harness module, no fixture asset and
no Atlas content.

## 6. Authority model

The plugin is observation only. By construction and by gate it does not: decide `SATISFIED`
or `NOT_SATISFIED`; verify production targets; construct registry authority; authorize
positive R2-B; touch `planning/m12/expectation.py`; or treat extracted values as normative.
Its Python contract imports nothing from the M12 registry, and the plugin's sources refer to
no planning code.

The U1 dependency graph is unchanged:

```
production project
  → read-only extraction plugin (this mechanism)
    → read-only extraction run (untrusted value tree + session identity)
      → reviewed source_reference artifact
        → U1 population (separately reviewed)
          → witness generation (positive / minimal-difference negative / lossy)
            → U1 review
```

## 7. Limits and non-claims

* Windows named pipes only; no POSIX leg is implemented or claimed.
* The pipe carries no engine-verifiable authorization token. While the transport is up, any
  local process that can reach the pipe can send requests; the mitigation is that the
  surface is read-only and two operations wide, and that the transport is off unless the
  operator opted in.
* `authorization_id` is passed through and recorded, not enforced by the engine.
* The extraction observes the *loaded editor world* of the host project: it opens no level,
  loads no asset and saves nothing.
* The plugin's tests prove mechanism and isolation. They are **not** U1 evidence: U1
  evidence comes only from a real production project, and no harness or fixture value may be
  used as a U1 value.

## 8. Measured evidence

Every number below is from a run on this host (Windows, NTFS, UE 5.6). Commands are given
verbatim.

### 8.1 Build — the plugin builds from the repository source in a harness-free project

```
Engine:      C:\Program Files\Epic Games\UE_5.6   (UnrealEditor-Cmd.exe present)
Toolchain:   MSVC 14.44.35207 (VS 2022 Community) — UBT warns it is not the preferred
             version for 5.6; the build succeeds with the warning
Host:        %LOCALAPPDATA%\Temp\atlas_u1_ro_plugin_host\AtlasReadOnlyHost.uproject
             (bare project: no Content assets, no atlas_entity tag, no harness module;
              Plugins/AtlasReadOnlyExtraction is a junction to the repository plugin)
Command:     cmd /c build_plugin.bat
             build_plugin.bat:
               call "<Engine>\Engine\Build\BatchFiles\Build.bat" AtlasReadOnlyHostEditor
                    Win64 Development -project="<host>\AtlasReadOnlyHost.uproject" -waitmutex
Result:      Result: Succeeded
Output:      unreal/plugins/AtlasReadOnlyExtraction/Binaries/Win64/UnrealEditor-AtlasReadOnlyExtraction.dll
             (linked in place through the junction; the file is the repository's build)
```

The build needed exactly the dependency set the build rules declare — `Core`, `CoreUObject`,
`Engine`, `UnrealEd`, `LevelSequence`, `MovieScene`, `Json` — and no additional module. No
dependency on `AtlasUnrealHarness`, the render pipeline, Kismet, AssetRegistry, Slate or the
editor widget modules was required or declared.

### 8.2 Static gates

```
$ python -m pytest tests/test_unreal_read_only_extraction_plugin.py -q
149 passed
```

Includes, with a control for every absence claim:

* forbidden-token and forbidden-engine-path scans over the whole plugin, using the harness's
  own tuple (control: the same scan finds those tokens in the harness sources);
* the carried-forward core's byte identity (`5f984132168d23038fee057fc54b4b06ad6eba7613ac1e91dac621b775714984`
  for `AtlasStateExtraction.cpp`, `f144e30bf77384c2c10c1acaed2d11d1a7d65ce9eba99df54b4d2c983d8cecdb`
  for `AtlasStateExtraction.h`, equal to the harness copies);
* absence of all 23 refused operation names from the shipping sources (control: each name is
  present in the harness server it came from);
* absence of every fixture/harness identifier and of any `/Game/` path (control: present in
  the harness module);
* envelope and session-identity key parity with the harness implementations, parsed from
  both source files and compared;
* cross-language agreement of the pipe name, source string, opt-in switches, config keys and
  wire bound between the C++ contract and `planning/unreal_read_only_extraction.py`;
* startup gating (the opt-in decision precedes the single server construction site, and the
  module provisions nothing);
* the change-set scope gate (which also proves REV10, R25, R2-A, the harness and the U1
  registry are untouched by this branch).

### 8.3 Live gates — a real editor process, a real pipe

```
$ python -m pytest tests/test_unreal_read_only_extraction_live_gate.py -v -s
5 passed in 30.03s
```

| run | observed |
| --- | -------- |
| no opt-in | plugin loaded (`LogAtlasReadOnlyExtraction: ... starting up`), then `Read-only transport NOT started: no explicit opt-in (no -AtlasReadOnlyTransport switch and bReadOnlyTransportEnabled is not set)`; `\\.\pipe\AtlasReadOnlyExtraction` unreachable |
| `-AtlasReadOnlyTransport` | `Read-only transport started on \\.\pipe\AtlasReadOnlyExtraction (opt-in: command-line opt-in -AtlasReadOnlyTransport)` |
| `extract_actor_state` (absent entity) | refusal `ERR_EXTRACTION_WORLD_PARTITION_UNSUPPORTED`, `success=false`, `observed_state` empty, session identity complete (`engine_version=5.6.1-44394996+++UE5+Release-5.6`, `source=unreal-editor-atlas-read-only-extraction`) |
| `extract_sequencer_state` (absent entity) | refusal with a closed `ERR_EXTRACTION_*` code, no payload |
| exposed operation with `kind="write"` | `ERR_MISSING_ARGUMENT` |
| `set_actor_location` | `ERR_UNKNOWN_OPERATION` |
| `submit_render` | `ERR_UNKNOWN_OPERATION` |

In-editor automation (engine-reported, `-ReportExportPath`):

```
succeeded=8, failed=0, notRun=0
Atlas.ReadOnlyExtraction.OperationSurfaceIsClosed                          SUCCESS
Atlas.ReadOnlyExtraction.NonExtractionOperationsAreRefused                 SUCCESS
Atlas.ReadOnlyExtraction.CapabilityAndKindMustBeRead                       SUCCESS
Atlas.ReadOnlyExtraction.EnvelopeIsPreserved                               SUCCESS
Atlas.ReadOnlyExtraction.SessionIdentityIsPreserved                        SUCCESS
Atlas.ReadOnlyExtraction.RefusalCarriesNoPartialPayload                    SUCCESS
Atlas.ReadOnlyExtraction.PackageDirtyInvarianceAcrossExtractionCall        SUCCESS
Atlas.ReadOnlyExtraction.TransportStartupIsExplicitOptIn                   SUCCESS
```

`PackageDirtyInvarianceAcrossExtractionCall` is the dynamic read-only proof: package dirty
state (count and world-package flag) is measured immediately before and after extraction
calls, including the clean-before/clean-after form.

### 8.4 Existing suites re-run on this branch

```
$ python -m pytest tests/test_unreal_state_extraction_*.py tests/test_unreal_transport_*.py \
                 tests/m7 tests/m12 -q
1126 passed, 4 skipped in 15.18s

  the 4 skips are pre-existing and unrelated to this change:
  tests/test_unreal_transport_named_pipe_windows.py skips its 4 real-pipe tests because
  pywin32 ('win32file') is not installed in this venv. The plugin's own live gate does not
  depend on pywin32: it drives the pipe through ctypes.
```

### 8.5 NOT YET LIVE-COVERED (stated, not implied)

* **A successful extraction value tree.** Without project content, the only editor world
  available in the host project is UE 5.6's default *World Partition* untitled world, and
  extraction v1 refuses partitioned worlds (`ERR_EXTRACTION_WORLD_PARTITION_UNSUPPORTED` —
  the extractor's own contract, not a plugin behaviour). The success path therefore requires
  the production project's level. **U1 prerequisite:** the production project must supply a
  **non-partitioned** persistent level containing `atlas_entity:`-tagged actors; if the
  production levels are World Partition levels, extraction v1 cannot produce a value tree
  for them and that is a design question outside this task.
* **Live schema-v1 validation of a returned tree** (follows from the above). The tree
  *shape* is unchanged (`AtlasStateExtraction` is byte-identical and the envelope wraps it
  under `unreal_state_extraction`), and the Python boundary's schema/parser/canonicalization
  tests pass, but no live tree has been produced on this host.
* **POSIX.** Named pipes only; no POSIX leg is implemented.
* **Engine-verifiable authorization.** None; `authorization_id` is a contract field, not a
  token.


### 8.6 Where this landed

```
branch:  feat/u1-readonly-extraction-plugin   (from origin/main @ 326105c6)
commit:  aacb55e1  feat(u1): portable read-only extraction plugin for real-project evidence
pr:      https://github.com/cantidokun/Atlas/pull/146
scope:   17 files added, 0 modified, 0 deleted — the plugin, its Python contract, its two
         test modules and this document
```

## 9. Removal

Delete `unreal/plugins/AtlasReadOnlyExtraction` (or disable the plugin in the host
project's `.uproject`) and rebuild the editor target. The plugin adds no project source, no
content and no configuration to a host project, so removal leaves it exactly as found.
