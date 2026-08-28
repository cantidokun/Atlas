from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Could not find patch anchor in {path}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# Planner
planner = ROOT / "planning/unreal_task_planner.py"
replace_once(
    planner,
    '    def plan_blueprint_compile(self, intent, asset_path): self._validate_intent(intent); return UnrealTaskPlan(intent.intent_id, UnrealAgentPlanBuilder(self.capabilities).for_blueprint_compile(intent, asset_path))\n',
    '    def plan_blueprint_compile(self, intent, asset_path): self._validate_intent(intent); return UnrealTaskPlan(intent.intent_id, UnrealAgentPlanBuilder(self.capabilities).for_blueprint_compile(intent, asset_path))\n    def plan_render_configuration(self, intent, render_config): self._validate_intent(intent); return UnrealTaskPlan(intent.intent_id, UnrealAgentPlanBuilder(self.capabilities).for_render_configuration(intent, render_config))\n',
)
replace_once(
    planner,
    '    def for_blueprint_compile(self, intent, asset_path):\n',
    '''    def for_render_configuration(self, intent, render_config):
        ids=self._require_targets(intent)
        from planning.unreal_render_contract import normalize_render_config
        config=normalize_render_config(render_config)
        payload={"width":config.width,"height":config.height,"start_frame":config.start_frame,"end_frame":config.end_frame,"output_directory":config.output_directory,"output_format":config.output_format}
        return (
            self._operation(UnrealCapability.RENDER,UnrealOperationKind.READ,"inspect_render_state",ids),
            self._operation(UnrealCapability.RENDER,UnrealOperationKind.WRITE,"configure_render",ids,payload),
            self._operation(UnrealCapability.RENDER,UnrealOperationKind.VERIFY,"verify_render_state",ids,payload),
        )
    def for_blueprint_compile(self, intent, asset_path):
''',
)

# Capability registry
registry = ROOT / "planning/unreal_capability_registry.py"
replace_once(
    registry,
    '    UnrealCapabilitySpec(UnrealCapability.RENDER, frozenset({UnrealOperationKind.READ, UnrealOperationKind.WRITE, UnrealOperationKind.VERIFY}), ("render_state",), "Configure or verify controlled Unreal rendering operations."),',
    '''    UnrealCapabilitySpec(UnrealCapability.RENDER, frozenset({UnrealOperationKind.READ, UnrealOperationKind.WRITE, UnrealOperationKind.VERIFY}), ("render_state",), "Configure or verify controlled Unreal rendering operations.", argument_keys_by_kind={
        UnrealOperationKind.READ: frozenset({"entity_ids"}),
        UnrealOperationKind.WRITE: frozenset({"entity_ids", "width", "height", "start_frame", "end_frame", "output_directory", "output_format"}),
        UnrealOperationKind.VERIFY: frozenset({"entity_ids", "width", "height", "start_frame", "end_frame", "output_directory", "output_format"}),
    }),''',
)
# Insert render validation before Blueprint validation.
replace_once(
    registry,
    '        if operation.capability is UnrealCapability.BLUEPRINT:\n',
    '''        if operation.capability is UnrealCapability.RENDER:
            from planning.unreal_render_contract import normalize_render_config
            config={key: arguments[key] for key in ("width","height","start_frame","end_frame","output_directory","output_format") if key in arguments}
            if operation.kind is UnrealOperationKind.READ:
                if config: raise ValueError("render READ operations must not include render configuration fields")
            else:
                normalize_render_config(config)
        if operation.capability is UnrealCapability.BLUEPRINT:
''',
)

# Production adapter verification mapping.
adapter = ROOT / "planning/unreal_adapter_production.py"
replace_once(
    adapter,
    '            "verify_blueprint_state": (UnrealCapability.BLUEPRINT,"inspect_blueprint_state"),\n',
    '            "verify_blueprint_state": (UnrealCapability.BLUEPRINT,"inspect_blueprint_state"),\n            "verify_render_state": (UnrealCapability.RENDER,"inspect_render_state"),\n',
)

# Executor render verifier wiring.
executor = ROOT / "planning/unreal_plan_executor.py"
replace_once(
    executor,
    'from planning.unreal_sequencer_verifier import verify_sequencer_playback_range\n',
    'from planning.unreal_sequencer_verifier import verify_sequencer_playback_range\nfrom planning.unreal_render_contract import verify_render_config\n',
)
replace_once(
    executor,
    '"set_sequencer_playback_range":"verify_sequencer_playback_range","compile_blueprint":"verify_blueprint_state"',
    '"set_sequencer_playback_range":"verify_sequencer_playback_range","configure_render":"verify_render_state","compile_blueprint":"verify_blueprint_state"',
)
replace_once(
    executor,
    '        if write_operation.name=="set_sequencer_playback_range": return {"start_frame":a["start_frame"],"end_frame":a["end_frame"]}\n',
    '        if write_operation.name=="set_sequencer_playback_range": return {"start_frame":a["start_frame"],"end_frame":a["end_frame"]}\n        if write_operation.name=="configure_render": return {key:a[key] for key in ("width","height","start_frame","end_frame","output_directory","output_format")}\n',
)
replace_once(
    executor,
    '            if expected_start_frame is not None and expected_end_frame is not None: evidence=verify_sequencer_playback_range(evidence,expected_start_frame,expected_end_frame)\n',
    '            if expected_start_frame is not None and expected_end_frame is not None: evidence=verify_sequencer_playback_range(evidence,expected_start_frame,expected_end_frame)\n            if operation.name == "verify_render_state": evidence=verify_render_config(evidence, {key: operation.arguments[key] for key in ("width","height","start_frame","end_frame","output_directory","output_format")})\n',
)

# Render evidence verifier is kept with the engine-neutral contract.
render_contract = ROOT / "planning/unreal_render_contract.py"
text = render_contract.read_text(encoding="utf-8")
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
    render_contract.write_text(text, encoding="utf-8")

# Tool schemas.
tools = ROOT / "planning/unreal_tool_schema.py"
needle = '    "verify_blueprint_state": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str, "asset_path": str, "expected_compile_status": str}),\n'
render_tools = '''    "inspect_render_state": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str}),
    "configure_render": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str, "width": int, "height": int, "start_frame": int, "end_frame": int, "output_directory": str, "output_format": str}),
    "verify_render_state": UnrealToolSchema({"entity_ids": (list, tuple), "authorization_id": str, "width": int, "height": int, "start_frame": int, "end_frame": int, "output_directory": str, "output_format": str}),
'''
replace_once(tools, needle, needle + render_tools)

# Adapter forwards render arguments automatically because _build_request uses the operation payload.
# No explicit adapter argument mapping is needed for writes; verification maps to a fresh READ.

# Unreal header declarations.
header = ROOT / "unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Public/AtlasTransportServer.h"
replace_once(
    header,
    '    static bool CompileBlueprint(const FTransportRequest& Request,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);',
    '    static bool CompileBlueprint(const FTransportRequest& Request,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);\n    static bool InspectRenderState(const FTransportRequest& Request,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);\n    static bool ConfigureRender(const FTransportRequest& Request,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);',
)

# Unreal transport includes and dispatch/validation. Render state is backed by a real Movie Render Pipeline PrimaryConfig asset.
cpp = ROOT / "unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Private/AtlasTransportServer.cpp"
replace_once(cpp, '#include "Misc/PackageName.h"', '#include "Misc/PackageName.h"\n#include "MoviePipelinePrimaryConfig.h"\n#include "MoviePipelineOutputSetting.h"\n#include "MoviePipelineImageSequenceOutput.h"')
replace_once(
    cpp,
    '    if (Request.OperationName == TEXT("inspect_sequencer_state"))\n',
    '''    if (Request.OperationName == TEXT("inspect_render_state"))
    {
        if (Request.Capability != TEXT("render") || Request.Kind != TEXT("read")) { OutError = TEXT("inspect_render_state requires render/read"); return false; }
        return true;
    }
    if (Request.OperationName == TEXT("configure_render"))
    {
        if (Request.Capability != TEXT("render") || Request.Kind != TEXT("write")) { OutError = TEXT("configure_render requires render/write"); return false; }
        double Width=0,Height=0,StartFrame=0,EndFrame=0;
        FString OutputDirectory,OutputFormat;
        if(!Request.Arguments->TryGetNumberField(TEXT("width"),Width)||!Request.Arguments->TryGetNumberField(TEXT("height"),Height)||!Request.Arguments->TryGetNumberField(TEXT("start_frame"),StartFrame)||!Request.Arguments->TryGetNumberField(TEXT("end_frame"),EndFrame)){OutError=TEXT("render dimensions and frame range must be numeric");return false;}
        if(FMath::RoundToInt(Width)!=Width||FMath::RoundToInt(Height)!=Height||FMath::RoundToInt(StartFrame)!=StartFrame||FMath::RoundToInt(EndFrame)!=EndFrame){OutError=TEXT("render dimensions and frame range must be integers");return false;}
        if(!Request.Arguments->TryGetStringField(TEXT("output_directory"),OutputDirectory)||OutputDirectory.TrimStartAndEnd().IsEmpty()){OutError=TEXT("output_directory must be a non-empty string");return false;}
        if(!Request.Arguments->TryGetStringField(TEXT("output_format"),OutputFormat)||OutputFormat.TrimStartAndEnd().IsEmpty()){OutError=TEXT("output_format must be a non-empty string");return false;}
        if(Width<=0||Height<=0||StartFrame>EndFrame){OutError=TEXT("invalid render configuration values");return false;}
        if(!OutputFormat.Equals(TEXT("png"),ESearchCase::IgnoreCase)){OutError=TEXT("Only PNG output_format is supported by the initial Unreal render boundary");return false;}
        return true;
    }
    if (Request.OperationName == TEXT("verify_render_state"))
    {
        if (Request.Capability != TEXT("render") || Request.Kind != TEXT("verify")) { OutError = TEXT("verify_render_state requires render/verify"); return false; }
        return true;
    }
    if (Request.OperationName == TEXT("inspect_sequencer_state"))
''',
)
replace_once(
    cpp,
    'Request.OperationName==TEXT("set_blueprint_metadata");',
    'Request.OperationName==TEXT("set_blueprint_metadata")||Request.OperationName==TEXT("inspect_render_state")||Request.OperationName==TEXT("configure_render")||Request.OperationName==TEXT("verify_render_state");',
)
replace_once(
    cpp,
    '    else if(S->Request.OperationName==TEXT("inspect_blueprint_state")) bTaskSuccess=InspectBlueprintState(S->Request,S->ObservedState,S->Error);',
    '    else if(S->Request.OperationName==TEXT("inspect_blueprint_state")) bTaskSuccess=InspectBlueprintState(S->Request,S->ObservedState,S->Error);\n    else if(S->Request.OperationName==TEXT("inspect_render_state")) bTaskSuccess=InspectRenderState(S->Request,S->ObservedState,S->Error);\n    else if(S->Request.OperationName==TEXT("configure_render")) bTaskSuccess=ConfigureRender(S->Request,S->ObservedState,S->Error);',
)
replace_once(
    cpp,
    '    else if(S->Request.OperationName==TEXT("verify_blueprint_state")) bTaskSuccess=InspectBlueprintState(S->Request,S->ObservedState,S->Error);',
    '    else if(S->Request.OperationName==TEXT("verify_blueprint_state")) bTaskSuccess=InspectBlueprintState(S->Request,S->ObservedState,S->Error);\n    else if(S->Request.OperationName==TEXT("verify_render_state")) bTaskSuccess=InspectRenderState(S->Request,S->ObservedState,S->Error);',
)

render_impl = r'''

namespace
{
    const TCHAR* AtlasRenderConfigAssetPath = TEXT("/Game/AtlasTest/AtlasRenderConfig.AtlasRenderConfig");

    UMoviePipelinePrimaryConfig* LoadAtlasRenderConfig(FString& OutError)
    {
        UMoviePipelinePrimaryConfig* Config = LoadObject<UMoviePipelinePrimaryConfig>(nullptr, AtlasRenderConfigAssetPath);
        if (!Config || !IsValid(Config))
        {
            OutError = FString::Printf(TEXT("Render config asset not found at asset_path: %s"), AtlasRenderConfigAssetPath);
            return nullptr;
        }
        return Config;
    }

    UMoviePipelineOutputSetting* GetAtlasRenderOutputSetting(UMoviePipelinePrimaryConfig* Config, FString& OutError)
    {
        if (!Config)
        {
            OutError = TEXT("Render config is invalid");
            return nullptr;
        }
        UMoviePipelineOutputSetting* Setting = Config->FindSettingByClass<UMoviePipelineOutputSetting>(false);
        if (!Setting)
        {
            OutError = TEXT("Render config is missing MoviePipelineOutputSetting");
            return nullptr;
        }
        return Setting;
    }

    FString GetAtlasRenderOutputFormat(UMoviePipelinePrimaryConfig* Config)
    {
        for (UMoviePipelineOutputBase* Output : Config->GetOutputContainers())
        {
            if (!Output || !IsValid(Output)) continue;
            const FString ClassName = Output->GetClass()->GetName();
            if (ClassName.Contains(TEXT("PNG"))) return TEXT("png");
        }
        return TEXT("");
    }

    bool SetAtlasRenderOutputFormat(UMoviePipelinePrimaryConfig* Config, const FString& Format, FString& OutError)
    {
        if (!Format.Equals(TEXT("png"), ESearchCase::IgnoreCase))
        {
            OutError = TEXT("Only PNG output_format is supported by the initial Unreal render boundary");
            return false;
        }
        UMoviePipelineImageSequenceOutput_PNG* Existing = Config->FindSettingByClass<UMoviePipelineImageSequenceOutput_PNG>(false);
        if (!Existing)
        {
            Existing = Cast<UMoviePipelineImageSequenceOutput_PNG>(Config->FindOrAddSettingByClass(UMoviePipelineImageSequenceOutput_PNG::StaticClass(), false, true));
        }
        if (!Existing || !IsValid(Existing))
        {
            OutError = TEXT("Unable to add PNG Movie Render Pipeline output setting");
            return false;
        }
        return true;
    }
}

bool FAtlasTransportServer::InspectRenderState(const FTransportRequest& R,TSharedPtr<FJsonObject>& O,FString& E)
{
    if(!IsInGameThread()||!GEngine||IsEngineExitRequested()){E=TEXT("Engine unavailable or operation is not on the game thread");return false;}
    if(R.EntityIds.Num()==0){E=TEXT("inspect_render_state requires at least one entity_id");return false;}
    UMoviePipelinePrimaryConfig* Config=LoadAtlasRenderConfig(E); if(!Config)return false;
    UMoviePipelineOutputSetting* Setting=GetAtlasRenderOutputSetting(Config,E); if(!Setting)return false;
    const FString Format=GetAtlasRenderOutputFormat(Config); if(Format.IsEmpty()){E=TEXT("Render config has no supported output format");return false;}
    TSharedPtr<FJsonObject> Render=MakeShareable(new FJsonObject);
    Render->SetNumberField(TEXT("width"),Setting->OutputResolution.X);
    Render->SetNumberField(TEXT("height"),Setting->OutputResolution.Y);
    Render->SetNumberField(TEXT("start_frame"),Setting->bUseCustomPlaybackRange?Setting->CustomStartFrame:0);
    Render->SetNumberField(TEXT("end_frame"),Setting->bUseCustomPlaybackRange?Setting->CustomEndFrame:0);
    Render->SetStringField(TEXT("output_directory"),Setting->OutputDirectory.Path);
    Render->SetStringField(TEXT("output_format"),Format);
    Render->SetStringField(TEXT("asset_path"),AtlasRenderConfigAssetPath);
    TSharedPtr<FJsonObject> Entry=MakeShareable(new FJsonObject); Entry->SetStringField(TEXT("entity_id"),R.EntityIds[0]); Entry->SetObjectField(TEXT("render"),Render);
    TSharedPtr<FJsonObject> State=MakeShareable(new FJsonObject); for(const FString& ID:R.EntityIds) State->SetObjectField(ID,Entry); O=State; return true;
}

bool FAtlasTransportServer::ConfigureRender(const FTransportRequest& R,TSharedPtr<FJsonObject>& O,FString& E)
{
    if(!IsInGameThread()||!GEngine||IsEngineExitRequested()){E=TEXT("Engine unavailable or operation is not on the game thread");return false;}
    if(R.EntityIds.Num()==0||!R.Arguments.IsValid()){E=TEXT("configure_render requires target entity_ids and arguments");return false;}
    double Width=0,Height=0,StartFrame=0,EndFrame=0; FString OutputDirectory,OutputFormat;
    if(!R.Arguments->TryGetNumberField(TEXT("width"),Width)||!R.Arguments->TryGetNumberField(TEXT("height"),Height)||!R.Arguments->TryGetNumberField(TEXT("start_frame"),StartFrame)||!R.Arguments->TryGetNumberField(TEXT("end_frame"),EndFrame)){E=TEXT("render dimensions and frame range must be numeric");return false;}
    if(!R.Arguments->TryGetStringField(TEXT("output_directory"),OutputDirectory)||!R.Arguments->TryGetStringField(TEXT("output_format"),OutputFormat)){E=TEXT("render output fields must be strings");return false;}
    if(FMath::RoundToInt(Width)!=Width||FMath::RoundToInt(Height)!=Height||FMath::RoundToInt(StartFrame)!=StartFrame||FMath::RoundToInt(EndFrame)!=EndFrame){E=TEXT("render dimensions and frame range must be integers");return false;}
    if(Width<=0||Height<=0||StartFrame>EndFrame){E=TEXT("invalid render configuration values");return false;}
    UMoviePipelinePrimaryConfig* Config=LoadAtlasRenderConfig(E); if(!Config)return false;
    UMoviePipelineOutputSetting* Setting=GetAtlasRenderOutputSetting(Config,E); if(!Setting)return false;
    if(!SetAtlasRenderOutputFormat(Config,OutputFormat,E))return false;
    Setting->Modify();
    Setting->OutputResolution=FIntPoint(FMath::RoundToInt(Width),FMath::RoundToInt(Height));
    Setting->bUseCustomPlaybackRange=true;
    Setting->CustomStartFrame=FMath::RoundToInt(StartFrame);
    Setting->CustomEndFrame=FMath::RoundToInt(EndFrame);
    Setting->OutputDirectory.Path=OutputDirectory.TrimStartAndEnd();
    Config->MarkPackageDirty();
    if(!Config->GetOutermost()->IsDirty()) Config->GetOutermost()->MarkPackageDirty();
    return InspectRenderState(R,O,E);
}

'''
replace_once(cpp, '\nAActor* FAtlasTransportServer::FindActorByEntityId(const FString& EntityId)', render_impl + 'AActor* FAtlasTransportServer::FindActorByEntityId(const FString& EntityId)')

# Build dependencies.
build = ROOT / "unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/AtlasUnrealTransport.Build.cs"
replace_once(build, '            "KismetCompiler"\n', '            "KismetCompiler",\n            "MovieRenderPipelineCore",\n            "MovieRenderPipelineRenderPasses"\n')

print("Applied Unreal render production boundary changes.")
