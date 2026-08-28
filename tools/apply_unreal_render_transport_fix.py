from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CPP = ROOT / "unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Private/AtlasTransportServer.cpp"
HEADER = ROOT / "unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Public/AtlasTransportServer.h"

h = HEADER.read_text(encoding="utf-8")
c = CPP.read_text(encoding="utf-8")

if "static bool InspectRenderState" not in h:
    needle = '    static bool BuildBlueprintState(const FString& AssetPath,TSharedPtr<FJsonObject>& OutBlueprintState,FString& OutError);'
    replacement = needle + '''\n    static bool InspectRenderState(const TArray<FString>& EntityIds,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);\n    static bool ConfigureRender(const FTransportRequest& Request,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);\n    static bool BuildRenderState(TSharedPtr<FJsonObject>& OutRenderState,FString& OutError);'''
    if needle not in h:
        raise SystemExit("Blueprint declaration anchor not found")
    h = h.replace(needle, replacement, 1)

if '#include "Misc/FileHelper.h"' not in c:
    needle = '#include "Misc/PackageName.h"'
    replacement = needle + '\n#include "Misc/FileHelper.h"\n#include "Misc/Paths.h"'
    if needle not in c:
        raise SystemExit("include anchor not found")
    c = c.replace(needle, replacement, 1)

if 'RenderConfigFilePath()' not in c:
    needle = '''    UWorld* GetActiveEditorWorld()\n    {'''
    # Insert helpers immediately before GetActiveEditorWorld so they stay in the anonymous namespace.
    helper = r'''    FString RenderConfigFilePath()
    {
        return FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("AtlasRenderConfig.json"));
    }

    void SetDefaultRenderState(TSharedPtr<FJsonObject>& State)
    {
        State = MakeShareable(new FJsonObject);
        State->SetNumberField(TEXT("width"), 1920);
        State->SetNumberField(TEXT("height"), 1080);
        State->SetNumberField(TEXT("start_frame"), 1);
        State->SetNumberField(TEXT("end_frame"), 1);
        State->SetStringField(TEXT("output_directory"), TEXT("Saved/AtlasRenderOutput"));
        State->SetStringField(TEXT("output_format"), TEXT("png"));
    }

    bool LoadRenderStateFromDisk(TSharedPtr<FJsonObject>& State, FString& Error)
    {
        const FString Filename = RenderConfigFilePath();
        FString JsonText;
        if (!FFileHelper::LoadFileToString(JsonText, *Filename))
        {
            SetDefaultRenderState(State);
            return true;
        }

        TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonText);
        if (!FJsonSerializer::Deserialize(Reader, State) || !State.IsValid())
        {
            Error = FString::Printf(TEXT("Failed to parse persisted render configuration: %s"), *Filename);
            return false;
        }
        return true;
    }

    bool SaveRenderStateToDisk(const TSharedPtr<FJsonObject>& State, FString& Error)
    {
        FString JsonText;
        TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&JsonText);
        if (!FJsonSerializer::Serialize(State.ToSharedRef(), Writer))
        {
            Error = TEXT("Failed to serialize render configuration");
            return false;
        }

        const FString Filename = RenderConfigFilePath();
        if (!FFileHelper::SaveStringToFile(JsonText, *Filename))
        {
            Error = FString::Printf(TEXT("Failed to persist render configuration: %s"), *Filename);
            return false;
        }
        return true;
    }

'''
    if needle not in c:
        raise SystemExit("world helper anchor not found")
    c = c.replace(needle, helper + needle, 1)

if 'Request.OperationName == TEXT("inspect_render_state")' not in c:
    marker = '    OutError = FString::Printf(TEXT("Unsupported operation_name: %s"), *Request.OperationName); return false;'
    block = r'''    if (Request.OperationName == TEXT("inspect_render_state"))
    {
        if (Request.Capability != TEXT("render") || Request.Kind != TEXT("read"))
        {
            OutError = TEXT("inspect_render_state requires render/read");
            return false;
        }
        return true;
    }
    if (Request.OperationName == TEXT("configure_render"))
    {
        if (Request.Capability != TEXT("render") || Request.Kind != TEXT("write"))
        {
            OutError = TEXT("configure_render requires render/write");
            return false;
        }
        double Width = 0, Height = 0, StartFrame = 0, EndFrame = 0;
        FString OutputDirectory, OutputFormat;
        if (!Request.Arguments->TryGetNumberField(TEXT("width"), Width) ||
            !Request.Arguments->TryGetNumberField(TEXT("height"), Height) ||
            !Request.Arguments->TryGetNumberField(TEXT("start_frame"), StartFrame) ||
            !Request.Arguments->TryGetNumberField(TEXT("end_frame"), EndFrame))
        {
            OutError = TEXT("width, height, start_frame, and end_frame must be numeric");
            return false;
        }
        if (FMath::RoundToInt(Width) != Width || FMath::RoundToInt(Height) != Height ||
            FMath::RoundToInt(StartFrame) != StartFrame || FMath::RoundToInt(EndFrame) != EndFrame)
        {
            OutError = TEXT("width, height, start_frame, and end_frame must be integers");
            return false;
        }
        if (Width <= 0 || Height <= 0 || StartFrame > EndFrame)
        {
            OutError = TEXT("render resolution must be positive and start_frame must not exceed end_frame");
            return false;
        }
        if (!Request.Arguments->TryGetStringField(TEXT("output_directory"), OutputDirectory) || OutputDirectory.TrimStartAndEnd().IsEmpty())
        {
            OutError = TEXT("output_directory must be a non-empty string");
            return false;
        }
        if (!Request.Arguments->TryGetStringField(TEXT("output_format"), OutputFormat) || OutputFormat.TrimStartAndEnd().IsEmpty())
        {
            OutError = TEXT("output_format must be a non-empty string");
            return false;
        }
        return true;
    }
    if (Request.OperationName == TEXT("verify_render_state"))
    {
        if (Request.Capability != TEXT("render") || Request.Kind != TEXT("verify"))
        {
            OutError = TEXT("verify_render_state requires render/verify");
            return false;
        }
        double Width = 0, Height = 0, StartFrame = 0, EndFrame = 0;
        FString OutputDirectory, OutputFormat;
        if (!Request.Arguments->TryGetNumberField(TEXT("width"), Width) ||
            !Request.Arguments->TryGetNumberField(TEXT("height"), Height) ||
            !Request.Arguments->TryGetNumberField(TEXT("start_frame"), StartFrame) ||
            !Request.Arguments->TryGetNumberField(TEXT("end_frame"), EndFrame) ||
            !Request.Arguments->TryGetStringField(TEXT("output_directory"), OutputDirectory) ||
            !Request.Arguments->TryGetStringField(TEXT("output_format"), OutputFormat))
        {
            OutError = TEXT("verify_render_state requires the complete render configuration");
            return false;
        }
        return true;
    }
'''
    if marker not in c:
        raise SystemExit("validation terminal anchor not found")
    c = c.replace(marker, block + marker, 1)

if 'Request.OperationName==TEXT("inspect_render_state")' not in c:
    needle = 'Request.OperationName==TEXT("set_blueprint_metadata");'
    replacement = needle[:-1] + '||Request.OperationName==TEXT("inspect_render_state")||Request.OperationName==TEXT("configure_render")||Request.OperationName==TEXT("verify_render_state");'
    if needle not in c:
        raise SystemExit("supported-operation anchor not found")
    c = c.replace(needle, replacement, 1)

if 'S->Request.OperationName==TEXT("inspect_render_state")' not in c:
    needle = '    else if(S->Request.OperationName==TEXT("verify_sequencer_playback_range")) bTaskSuccess=InspectSequencerState(S->Request.EntityIds,S->ObservedState,S->Error);'
    replacement = needle + '\n    else if(S->Request.OperationName==TEXT("inspect_render_state")) bTaskSuccess=InspectRenderState(S->Request.EntityIds,S->ObservedState,S->Error);\n    else if(S->Request.OperationName==TEXT("configure_render")) bTaskSuccess=ConfigureRender(S->Request,S->ObservedState,S->Error);\n    else if(S->Request.OperationName==TEXT("verify_render_state")) bTaskSuccess=InspectRenderState(S->Request.EntityIds,S->ObservedState,S->Error);'
    if needle not in c:
        raise SystemExit("game-thread dispatcher anchor not found")
    c = c.replace(needle, replacement, 1)

if 'bool FAtlasTransportServer::BuildRenderState(' not in c:
    needle = 'AActor* FAtlasTransportServer::FindActorByEntityId(const FString& EntityId)'
    implementation = r'''bool FAtlasTransportServer::BuildRenderState(TSharedPtr<FJsonObject>& O, FString& E)
{
    if (!IsInGameThread() || !GEngine || IsEngineExitRequested())
    {
        E = TEXT("Engine unavailable or operation is not on the game thread");
        return false;
    }
    return LoadRenderStateFromDisk(O, E);
}

bool FAtlasTransportServer::InspectRenderState(const TArray<FString>& IDs, TSharedPtr<FJsonObject>& O, FString& E)
{
    if (IDs.Num() == 0)
    {
        E = TEXT("inspect_render_state requires at least one entity_id");
        return false;
    }

    TSharedPtr<FJsonObject> RenderState;
    if (!BuildRenderState(RenderState, E)) return false;

    TSharedPtr<FJsonObject> State = MakeShareable(new FJsonObject);
    for (const FString& ID : IDs)
    {
        TSharedPtr<FJsonObject> Entry = MakeShareable(new FJsonObject);
        Entry->SetStringField(TEXT("entity_id"), ID);
        Entry->SetObjectField(TEXT("render"), RenderState);
        State->SetObjectField(ID, Entry);
    }
    O = State;
    return true;
}

bool FAtlasTransportServer::ConfigureRender(const FTransportRequest& R, TSharedPtr<FJsonObject>& O, FString& E)
{
    if (R.EntityIds.Num() == 0 || !R.Arguments.IsValid())
    {
        E = TEXT("configure_render requires valid entity_ids and arguments");
        return false;
    }

    double Width = 0, Height = 0, StartFrame = 0, EndFrame = 0;
    FString OutputDirectory, OutputFormat;
    if (!R.Arguments->TryGetNumberField(TEXT("width"), Width) ||
        !R.Arguments->TryGetNumberField(TEXT("height"), Height) ||
        !R.Arguments->TryGetNumberField(TEXT("start_frame"), StartFrame) ||
        !R.Arguments->TryGetNumberField(TEXT("end_frame"), EndFrame) ||
        !R.Arguments->TryGetStringField(TEXT("output_directory"), OutputDirectory) ||
        !R.Arguments->TryGetStringField(TEXT("output_format"), OutputFormat))
    {
        E = TEXT("configure_render requires the complete render configuration");
        return false;
    }

    if (FMath::RoundToInt(Width) != Width || FMath::RoundToInt(Height) != Height ||
        FMath::RoundToInt(StartFrame) != StartFrame || FMath::RoundToInt(EndFrame) != EndFrame)
    {
        E = TEXT("render configuration numeric fields must be integers");
        return false;
    }
    if (Width <= 0 || Height <= 0 || StartFrame > EndFrame)
    {
        E = TEXT("render resolution must be positive and start_frame must not exceed end_frame");
        return false;
    }
    OutputDirectory = OutputDirectory.TrimStartAndEnd();
    OutputFormat = OutputFormat.TrimStartAndEnd().ToLower();
    if (OutputDirectory.IsEmpty() || OutputFormat.IsEmpty())
    {
        E = TEXT("output_directory and output_format must not be empty");
        return false;
    }

    TSharedPtr<FJsonObject> RenderState = MakeShareable(new FJsonObject);
    RenderState->SetNumberField(TEXT("width"), FMath::RoundToInt(Width));
    RenderState->SetNumberField(TEXT("height"), FMath::RoundToInt(Height));
    RenderState->SetNumberField(TEXT("start_frame"), FMath::RoundToInt(StartFrame));
    RenderState->SetNumberField(TEXT("end_frame"), FMath::RoundToInt(EndFrame));
    RenderState->SetStringField(TEXT("output_directory"), OutputDirectory);
    RenderState->SetStringField(TEXT("output_format"), OutputFormat);

    if (!SaveRenderStateToDisk(RenderState, E)) return false;
    return InspectRenderState(R.EntityIds, O, E);
}

'''
    if needle not in c:
        raise SystemExit("render implementation anchor not found")
    c = c.replace(needle, implementation + needle, 1)

HEADER.write_text(h, encoding="utf-8")
CPP.write_text(c, encoding="utf-8")
print("Applied Unreal render transport boundary.")
