> Current checkpoint — September 29, 2026 UTC.
>
> MOCK TWIN VALIDATED / FROZEN. PR #146 functional merge is 8f601184e62da2362ec38c948e61b7ff8058f95b. The plugin is a read-only observation mechanism; it does not establish U1 production authority.
>
> The synthetic validation project completed its isolated case matrix and final independent review: GLM CLEAR; GPT-SOL-6 CLEAR WITH MINOR FINDINGS, blockers none. Review bundle SHA: eacdeba5cfec9e8fa4af486e8ea0aaaa8f617bfbf7c43f5da92bd17067cc0079.
>
> Next use: point the plugin at the actual production .uproject, capture real session/project/world identity and actor/sequencer responses, and preserve raw evidence for REV10 review. Do not copy mock observations into planning/m12/expectation.py; do not rebuild or expand the mock fixture unless separately required.

# AtlasReadOnlyExtraction

A portable, read-only Unreal Editor plugin that carries the Atlas state-extraction core and
exposes it over a closed, two-operation transport. It exists so the U1 evidence run can
observe a **real production project** without that project containing, or being modified
by, anything from the Atlas validation harness.

This plugin is an observation mechanism. It decides nothing:

* it does not decide `SATISFIED` / `NOT_SATISFIED`;
* it does not verify production targets;
* it constructs no registry authority and never touches `planning/m12/expectation.py`;
* the response it returns is untrusted evidence for Atlas, and Atlas validates it
  (`planning/unreal_state_extraction`).

## What it exposes

Exactly two read operations, and nothing else:

| operation                 | capability      | kind   |
| ------------------------- | --------------- | ------ |
| `extract_actor_state`     | `inspect_actor` | `read` |
| `extract_sequencer_state` | `sequencer`     | `read` |

Every other Atlas transport operation — `set_actor_*`, `apply_material_variant`,
`apply_niagara_variant`, `set_sequencer_playback_range`, `set_blueprint_metadata`,
`compile_blueprint`, `configure_render`, `submit_render`, `reconcile_render_jobs`, the
inspection and verification operations, and every fixture commandlet — is absent from this
plugin. Requests naming them are refused with `ERR_UNKNOWN_OPERATION`; a write-shaped kind
is refused with `ERR_MISSING_ARGUMENT` even for an exposed operation.

The extraction core (`Source/AtlasReadOnlyExtraction/Private/AtlasStateExtraction.{h,cpp}`)
is carried forward **byte-for-byte** from
`unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Private/`, and
`tests/test_unreal_read_only_extraction_plugin.py` fails if that equality ever breaks.

## Explicit opt-in

Loading the plugin does **not** start the transport. It starts only when the operator opted
in, by either route:

1. command line: `-AtlasReadOnlyTransport`, optionally with
   `-AtlasReadOnlyTransportPipe=\\.\pipe\<name>`;
2. `Engine.ini`:

   ```ini
   [AtlasReadOnlyExtraction]
   bReadOnlyTransportEnabled=True
   ReadOnlyTransportPipeName=\\.\pipe\AtlasReadOnlyExtraction
   ```

Without either, the plugin logs

```
Read-only transport NOT started: no explicit opt-in (no -AtlasReadOnlyTransport switch and
bReadOnlyTransportEnabled is not set): the read-only transport stays down
```

and opens no pipe.

The default pipe is `\\.\pipe\AtlasReadOnlyExtraction` — deliberately **not** the harness
pipe `\\.\pipe\AtlasUnrealTransport`, so the two servers can never contend for one name and
an evidence run can always say which mechanism answered it.

`authorization_id` remains the Atlas contract field it has always been. This plugin does
not treat it as an engine-verifiable token and invents no cryptographic authorization: the
goal is a smaller exposed operation surface, not a new trust authority.

## Envelope

The request and response envelopes are the existing Atlas transport ones:

* request: `request_id`, `operation_name`, `capability`, `kind`, `arguments.entity_ids`,
  `entity_ids`, `authorization_id`, `schema_version`;
* response: `request_id`, `operation_name`, `success`, `error`, `source`,
  `schema_version`, `error_code`, `session_identity`, `entity_ids`, `observed_state`;
* `session_identity`: `editor_session_id`, `project_identity`, `engine_version`,
  `process_id`, `process_creation_time_utc`, `server_start_time_utc`;
* extraction responses are wrapped under `observed_state.unreal_state_extraction`;
* the wire bound is the existing 1 MiB transport limit, and a response that would exceed it
  fails closed with `ERR_EXTRACTION_PAYLOAD_TOO_LARGE` rather than being truncated.

`source` is `unreal-editor-atlas-read-only-extraction`.

## Read-only guarantees

* **Static**: the whole plugin passes the harness's own forbidden-token/engine-path gate
  (`MarkPackageDirty`, `Modify(`, `SavePackage`, `CreatePackage`, `NewObject<`,
  `SpawnActor`, `Destroy(`, `Rename(`, actor/material/sequence setters, `LoadObject`,
  `StaticLoadObject`, `TryLoad`, `FSoftObjectPath`, `Tags.Add/Remove`, `TActorIterator`,
  `GetActiveEditorWorld`, `GetWorldContexts`, …). The plugin imports that token list from
  `tests/test_unreal_state_extraction_readonly_source.py` instead of restating it, so the
  plugin cannot weaken the gate.
* **Startup**: the module provisions nothing — no ticker, no asset, no level edit — and
  starts the transport only behind the opt-in decision.
* **Dynamic**: `Atlas.ReadOnlyExtraction.PackageDirtyInvarianceAcrossExtractionCall`
  measures package dirty state immediately before and after extraction calls, including the
  clean-before/clean-after form.
* **Live**: `tests/test_unreal_read_only_extraction_live_gate.py` runs the plugin inside a
  real editor process and asserts, over the real pipe, that only the two operations answer.

## Building and testing

The plugin builds against a host project that does not contain the harness. Any project
that enables the plugin can host it:

```bat
call "<Engine>\Engine\Build\BatchFiles\Build.bat" <Project>Editor Win64 Development ^
     -project="<absolute path>\<Project>.uproject" -waitmutex
```

Automation tests (fixture-free: no tagged actor, no `/Game` asset, no harness module):

```
UnrealEditor-Cmd.exe <Project>.uproject -unattended -nosplash -noprerequisites -nullrhi \
  -ExecCmds="Automation RunTests Atlas.ReadOnlyExtraction" \
  -testexit="Automation Test Queue Empty"
```

Static gates and the live gate:

```bash
python -m pytest tests/test_unreal_read_only_extraction_plugin.py -q
python -m pytest tests/test_unreal_read_only_extraction_live_gate.py -q -s
```

## Removing it

Delete the plugin directory (or disable it in the host project's `.uproject`) and rebuild
the editor target. The plugin makes no project change, holds no content and writes nothing,
so removal leaves the project exactly as found.
