"""Declared contract of the portable read-only extraction plugin (Atlas side).

This module is the Python half of the plugin's declared contract. Every constant below is
mirrored by the C++ sources of ``unreal/plugins/AtlasReadOnlyExtraction``, and
``tests/test_unreal_read_only_extraction_plugin.py`` asserts that the two halves agree, so
the declaration cannot drift silently.

Nothing here is authority:

* the values are transport plumbing (a pipe name, a wire bound, an opt-in switch) and the
  name of the observation surface;
* ``OPERATIONS`` is what the plugin *exposes*, not what Atlas expects to be true;
* the response the plugin returns is untrusted evidence — it is validated by
  :mod:`planning.unreal_state_extraction` and never converted into a normative decision.

The plugin is the observation mechanism for the U1 read-only extraction run. U1 population
authority lives in the reviewed M12.2 registry, never here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final, Mapping, Optional, Sequence, Tuple

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PLUGIN_DIR: Final[Path] = REPO_ROOT / "unreal" / "plugins" / "AtlasReadOnlyExtraction"
MODULE_DIR: Final[Path] = PLUGIN_DIR / "Source" / "AtlasReadOnlyExtraction"
PUBLIC_DIR: Final[Path] = MODULE_DIR / "Public"
PRIVATE_DIR: Final[Path] = MODULE_DIR / "Private"
BUILD_RULES_PATH: Final[Path] = MODULE_DIR / "AtlasReadOnlyExtraction.Build.cs"
DESCRIPTOR_PATH: Final[Path] = PLUGIN_DIR / "AtlasReadOnlyExtraction.uplugin"

#: The plugin's own pipe. Deliberately not :data:`HARNESS_PIPE_NAME`.
PIPE_NAME: Final[str] = r"\\.\pipe\AtlasReadOnlyExtraction"

#: The Atlas validation harness transport pipe. A host project must never see both servers
#: contend for one name, and an evidence run must be able to say which mechanism answered.
HARNESS_PIPE_NAME: Final[str] = r"\\.\pipe\AtlasUnrealTransport"

#: The response ``source`` string: provenance of this mechanism, never authority.
SOURCE: Final[str] = "unreal-editor-atlas-read-only-extraction"

#: The closed operation surface, in declaration order. Nothing else is ever dispatched.
OPERATIONS: Final[Tuple[str, ...]] = (
    "extract_actor_state",
    "extract_sequencer_state",
)

#: The capability each exposed operation declares, and the only kind it accepts.
CAPABILITY_BY_OPERATION: Final[Mapping[str, str]] = {
    "extract_actor_state": "inspect_actor",
    "extract_sequencer_state": "sequencer",
}
REQUEST_KIND: Final[str] = "read"

#: Explicit opt-in switches and Engine.ini keys of the plugin's startup policy.
OPT_IN_SWITCH: Final[str] = "-AtlasReadOnlyTransport"
PIPE_SWITCH_PREFIX: Final[str] = "-AtlasReadOnlyTransportPipe="
CONFIG_SECTION: Final[str] = "AtlasReadOnlyExtraction"
CONFIG_ENABLE_KEY: Final[str] = "bReadOnlyTransportEnabled"
CONFIG_PIPE_KEY: Final[str] = "ReadOnlyTransportPipeName"

#: The wire bound the plugin enforces (the existing Atlas transport bound).
WIRE_MESSAGE_LIMIT: Final[int] = 1024 * 1024

SCHEMA_VERSION: Final[int] = 1

#: The response envelope keys the plugin emits (the existing Atlas transport envelope).
RESPONSE_FIELDS: Final[Tuple[str, ...]] = (
    "request_id",
    "operation_name",
    "success",
    "error",
    "source",
    "schema_version",
    "error_code",
    "session_identity",
    "entity_ids",
    "observed_state",
)

#: The six session identity fields the plugin must preserve.
SESSION_IDENTITY_FIELDS: Final[Tuple[str, ...]] = (
    "editor_session_id",
    "project_identity",
    "engine_version",
    "process_id",
    "process_creation_time_utc",
    "server_start_time_utc",
)

#: Operations the plugin must NOT expose. The list is the full Atlas transport surface
#: minus the two extraction operations, so a future copy-paste of the harness server into
#: this plugin fails the plugin's own tests instead of quietly widening the surface.
FORBIDDEN_OPERATIONS: Final[Tuple[str, ...]] = (
    "set_actor_location",
    "set_actor_rotation",
    "set_actor_scale",
    "apply_material_variant",
    "apply_niagara_variant",
    "set_sequencer_playback_range",
    "set_blueprint_metadata",
    "compile_blueprint",
    "configure_render",
    "submit_render",
    "reconcile_render_jobs",
    "inspect_world",
    "inspect_target_actors",
    "inspect_material_state",
    "inspect_niagara_state",
    "inspect_sequencer_state",
    "inspect_blueprint_state",
    "inspect_render_state",
    "inspect_render_job",
    "verify_render_state",
    "verify_blueprint_state",
    "verify_sequencer_playback_range",
    "get_capabilities",
)

#: The plugin source file that names refused operations as test data (guarded by
#: WITH_DEV_AUTOMATION_TESTS and excluded from the production-surface scans).
AUTOMATION_TEST_SOURCE_NAME: Final[str] = "AtlasReadOnlyExtractionAutomationTests.cpp"


def production_sources() -> Tuple[Path, ...]:
    """The plugin sources that ship: everything except the guarded automation tests."""
    return tuple(
        path
        for path in sorted(list(PUBLIC_DIR.glob("*.h")) + list(PRIVATE_DIR.glob("*.cpp")) + list(PRIVATE_DIR.glob("*.h")))
        if path.name != AUTOMATION_TEST_SOURCE_NAME
    )


def all_sources() -> Tuple[Path, ...]:
    """Every plugin source, including the guarded automation tests."""
    return tuple(
        sorted(list(PUBLIC_DIR.glob("*.h")) + list(PRIVATE_DIR.glob("*.cpp")) + list(PRIVATE_DIR.glob("*.h")))
    )


def build_request(
    entity_ids: Sequence[str],
    operation: str = OPERATIONS[0],
    request_id: str = "atlas-read-only-extraction-run",
    capability: Optional[str] = None,
    kind: str = REQUEST_KIND,
    authorization_id: str = "atlas-read-only-extraction-run",
) -> Any:
    """Build one extraction request for the plugin's transport.

    The shape is the existing Atlas transport request contract; the request carries entity
    ids and a capability/kind pair, never an expectation, a target value or a decision.
    """
    from planning.unreal_transport_contract import UnrealTransportRequest

    entity_id_tuple = tuple(entity_ids)
    if not entity_id_tuple:
        raise ValueError("an extraction request needs at least one entity id")
    if operation not in CAPABILITY_BY_OPERATION:
        raise ValueError(f"the plugin exposes no operation named {operation!r}")

    return UnrealTransportRequest(
        request_id=request_id,
        operation_name=operation,
        capability=capability or CAPABILITY_BY_OPERATION[operation],
        kind=kind,
        arguments={"entity_ids": list(entity_id_tuple)},
        entity_ids=entity_id_tuple,
        authorization_id=authorization_id,
    )


def open_transport(pipe_name: str = PIPE_NAME, **kwargs: Any) -> Any:
    """Open the plugin's named-pipe transport (requires pywin32).

    ``planning.unreal_transport_named_pipe`` is imported lazily so that importing this
    module never depends on pywin32.
    """
    from planning.unreal_transport_named_pipe import WindowsNamedPipeTransport

    return WindowsNamedPipeTransport(pipe_name, **kwargs)
