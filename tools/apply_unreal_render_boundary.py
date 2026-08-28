from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLANNER = ROOT / "planning/unreal_task_planner.py"
ADAPTER = ROOT / "planning/unreal_adapter_production.py"
EXECUTOR = ROOT / "planning/unreal_plan_executor.py"


def replace_once(path, old, new):
    text = path.read_text()
    if new in text:
        return False
    if old not in text:
        raise SystemExit(f"Could not find patch anchor in {path}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1))
    return True

# Planner: expose the deterministic inspect -> configure -> verify shape.
replace_once(
    PLANNER,
    '    def plan_blueprint_compile(self, intent, asset_path): self._validate_intent(intent); return UnrealTaskPlan(intent.intent_id, UnrealAgentPlanBuilder(self.capabilities).for_blueprint_compile(intent, asset_path))\n',
    '    def plan_blueprint_compile(self, intent, asset_path): self._validate_intent(intent); return UnrealTaskPlan(intent.intent_id, UnrealAgentPlanBuilder(self.capabilities).for_blueprint_compile(intent, asset_path))\n    def plan_render_configuration(self, intent, render_config): self._validate_intent(intent); return UnrealTaskPlan(intent.intent_id, UnrealAgentPlanBuilder(self.capabilities).for_render_configuration(intent, render_config))\n',
)
replace_once(
    PLANNER,
    '    def for_blueprint_compile(self, intent, asset_path):\n',
    '''    def for_render_configuration(self, intent, render_config):\n        ids=self._require_targets(intent)\n        from planning.unreal_render_contract import normalize_render_config\n        config=normalize_render_config(render_config)\n        payload={\n            "width":config.width,"height":config.height,"start_frame":config.start_frame,\n            "end_frame":config.end_frame,"output_directory":config.output_directory,\n            "output_format":config.output_format,\n        }\n        return (\n            self._operation(UnrealCapability.RENDER,UnrealOperationKind.READ,"inspect_render_state",ids),\n            self._operation(UnrealCapability.RENDER,UnrealOperationKind.WRITE,"configure_render",ids,payload),\n            self._operation(UnrealCapability.RENDER,UnrealOperationKind.VERIFY,"verify_render_state",ids,payload),\n        )\n    def for_blueprint_compile(self, intent, asset_path):\n''',
)

# Adapter: verification must perform a fresh render read, just like Blueprint verification.
replace_once(
    ADAPTER,
    '            "verify_blueprint_state": (UnrealCapability.BLUEPRINT,"inspect_blueprint_state"),\n',
    '            "verify_blueprint_state": (UnrealCapability.BLUEPRINT,"inspect_blueprint_state"),\n            "verify_render_state": (UnrealCapability.RENDER,"inspect_render_state"),\n',
)
replace_once(
    ADAPTER,
    '            if operation.capability is UnrealCapability.BLUEPRINT:\n                arguments["asset_path"] = operation.arguments["asset_path"]\n',
    '            if operation.capability is UnrealCapability.BLUEPRINT:\n                arguments["asset_path"] = operation.arguments["asset_path"]\n            if operation.capability is UnrealCapability.RENDER:\n                for key in ("width","height","start_frame","end_frame","output_directory","output_format"):\n                    if key in operation.arguments: arguments[key] = operation.arguments[key]\n',
)

# Executor: render writes are immediately followed by render verification, with exact expected values.
replace_once(
    EXECUTOR,
    '"set_sequencer_playback_range":"verify_sequencer_playback_range","compile_blueprint":"verify_blueprint_state"',
    '"set_sequencer_playback_range":"verify_sequencer_playback_range","configure_render":"verify_render_state","compile_blueprint":"verify_blueprint_state"',
)
replace_once(
    EXECUTOR,
    '        if write_operation.name=="set_sequencer_playback_range": return {"start_frame":a["start_frame"],"end_frame":a["end_frame"]}\n',
    '        if write_operation.name=="set_sequencer_playback_range": return {"start_frame":a["start_frame"],"end_frame":a["end_frame"]}\n        if write_operation.name=="configure_render": return {key:a[key] for key in ("width","height","start_frame","end_frame","output_directory","output_format")}\n',
)

print("Applied Unreal render planner/adapter/executor boundary.")
