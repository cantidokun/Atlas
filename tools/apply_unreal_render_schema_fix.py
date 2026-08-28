from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch(path, old, new):
    text = path.read_text()
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Patch anchor not found: {path}")
    path.write_text(text.replace(old, new, 1))

registry = ROOT / "planning/unreal_capability_registry.py"
patch(registry,
    '    UnrealCapabilitySpec(UnrealCapability.RENDER, frozenset({UnrealOperationKind.READ, UnrealOperationKind.WRITE, UnrealOperationKind.VERIFY}), ("render_state",), "Configure or verify controlled Unreal rendering operations."),',
    '''    UnrealCapabilitySpec(UnrealCapability.RENDER, frozenset({UnrealOperationKind.READ, UnrealOperationKind.WRITE, UnrealOperationKind.VERIFY}), ("render_state",), "Configure or verify controlled Unreal rendering operations.", argument_keys_by_kind={
        UnrealOperationKind.READ: frozenset({"entity_ids"}),
        UnrealOperationKind.WRITE: frozenset({"entity_ids", "width", "height", "start_frame", "end_frame", "output_directory", "output_format"}),
        UnrealOperationKind.VERIFY: frozenset({"entity_ids", "width", "height", "start_frame", "end_frame", "output_directory", "output_format"}),
    }),''')

tools = ROOT / "planning/unreal_tool_schema.py"
patch(tools,
    '    "verify_blueprint_state": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str, "asset_path": str, "expected_compile_status": str}),\n',
    '''    "verify_blueprint_state": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str, "asset_path": str, "expected_compile_status": str}),
    "inspect_render_state": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str}),
    "configure_render": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str, "width": int, "height": int, "start_frame": int, "end_frame": int, "output_directory": str, "output_format": str}),
    "verify_render_state": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str, "width": int, "height": int, "start_frame": int, "end_frame": int, "output_directory": str, "output_format": str}),
''')

contract = ROOT / "planning/unreal_render_contract.py"
text = contract.read_text()
if "def verify_render_config(" not in text:
    text += '''\n\ndef verify_render_config(evidence, expected):
    """Independently verify fresh Unreal render-state evidence."""
    observed = evidence.observed_state
    state = observed.get("render") if isinstance(observed, Mapping) else None
    if not isinstance(state, Mapping):
        raise ValueError("render evidence is missing render state")
    actual = normalize_render_config({
        "width": state.get("width"),
        "height": state.get("height"),
        "start_frame": state.get("start_frame"),
        "end_frame": state.get("end_frame"),
        "output_directory": state.get("output_directory"),
        "output_format": state.get("output_format"),
    })
    expected_config = normalize_render_config(expected)
    if actual != expected_config:
        raise ValueError(f"render state does not match expected configuration: expected={expected_config!r}, observed={actual!r}")
    return evidence
'''
    contract.write_text(text)

print("Applied Unreal render schema and evidence verification fix.")
