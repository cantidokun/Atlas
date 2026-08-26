"""Apply the Blueprint transport implementation to an existing Unreal harness.

This migration is intentionally deterministic: it edits only the known Atlas
transport anchors and aborts instead of guessing if the transport has drifted.
Run from the repository root after pulling the Blueprint contract commits.
"""

from pathlib import Path


CPP = Path("unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Private/AtlasTransportServer.cpp")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one {label} anchor, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    if not CPP.exists():
        raise SystemExit(f"missing transport source: {CPP}")
    text = CPP.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '#include "Editor.h"\n',
        '#include "Editor.h"\n#include "Engine/Blueprint.h"\n#include "Kismet2/KismetEditorUtilities.h"\n',
        "Blueprint includes",
    ) if '#include "Engine/Blueprint.h"' not in text else text

    validation_anchor = '    if (Request.OperationName == TEXT("inspect_sequencer_state"))\n'
    validation = '''    if (Request.OperationName == TEXT("inspect_blueprint_state"))
    {
        if (Request.Capability != TEXT("blueprint") || Request.Kind != TEXT("read")) { OutError = TEXT("inspect_blueprint_state requires blueprint/read"); return false; }
        FString AssetPath;
        if (!Request.Arguments->TryGetStringField(TEXT("asset_path"), AssetPath) || !AssetPath.StartsWith(TEXT("/"))) { OutError = TEXT("arguments.asset_path must be a non-empty Unreal package path"); return false; }
        return true;
    }
    if (Request.OperationName == TEXT("compile_blueprint"))
    {
        if (Request.Capability != TEXT("blueprint") || Request.Kind != TEXT("write")) { OutError = TEXT("compile_blueprint requires blueprint/write"); return false; }
        FString AssetPath;
        if (!Request.Arguments->TryGetStringField(TEXT("asset_path"), AssetPath) || !AssetPath.StartsWith(TEXT("/"))) { OutError = TEXT("arguments.asset_path must be a non-empty Unreal package path"); return false; }
        return true;
    }
    if (Request.OperationName == TEXT("verify_blueprint_state"))
    {
        if (Request.Capability != TEXT("blueprint") || Request.Kind != TEXT("verify")) { OutError = TEXT("verify_blueprint_state requires blueprint/verify"); return false; }
        FString AssetPath;
        FString ExpectedStatus;
        if (!Request.Arguments->TryGetStringField(TEXT("asset_path"), AssetPath) || !AssetPath.StartsWith(TEXT("/"))) { OutError = TEXT("arguments.asset_path must be a non-empty Unreal package path"); return false; }
        if (!Request.Arguments->TryGetStringField(TEXT("expected_compile_status"), ExpectedStatus) || ExpectedStatus.TrimStartAndEnd().IsEmpty()) { OutError = TEXT("arguments.expected_compile_status must be a non-empty string"); return false; }
        return true;
    }
'''
    text = replace_once(text, validation_anchor, validation + validation_anchor, "Blueprint validation") if 'Request.OperationName == TEXT("inspect_blueprint_state")' not in text else text

    supported_anchor = 'Request.OperationName==TEXT("verify_sequencer_playback_range");'
    supported = 'Request.OperationName==TEXT("verify_sequencer_playback_range")||Request.OperationName==TEXT("inspect_blueprint_state")||Request.OperationName==TEXT("compile_blueprint")||Request.OperationName==TEXT("verify_blueprint_state");'
    text = replace_once(text, supported_anchor, supported, "supported operation list") if 'Request.OperationName==TEXT("inspect_blueprint_state")' not in text else text

    dispatch_anchor = '    else if(S->Request.OperationName==TEXT("inspect_sequencer_state")) bTaskSuccess=InspectSequencerState(S->Request.EntityIds,S->ObservedState,S->Error);\n'
    dispatch = dispatch_anchor + '''    else if(S->Request.OperationName==TEXT("inspect_blueprint_state")) bTaskSuccess=InspectBlueprintState(S->Request,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("compile_blueprint")) bTaskSuccess=CompileBlueprint(S->Request,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("verify_blueprint_state")) bTaskSuccess=InspectBlueprintState(S->Request,S->ObservedState,S->Error);
'''
    text = replace_once(text, dispatch_anchor, dispatch, "game-thread Blueprint dispatch") if 'OperationName==TEXT("compile_blueprint")' not in text else text

    implementation_anchor = 'AActor* FAtlasTransportServer::FindActorByEntityId(const FString& EntityId)\n'
    implementation = r'''namespace
{
    FString BlueprintStatusToString(const UBlueprint* Blueprint)
    {
        if (!Blueprint) return TEXT("unknown");
        switch (Blueprint->Status)
        {
        case BS_UpToDate: return TEXT("success");
        case BS_UpToDateWithWarnings: return TEXT("success");
        case BS_Error: return TEXT("error");
        case BS_Dirty: return TEXT("dirty");
        case BS_BeingCreated: return TEXT("being_created");
        default: return TEXT("unknown");
        }
    }
}

bool FAtlasTransportServer::BuildBlueprintState(const FString& AssetPath,TSharedPtr<FJsonObject>& O,FString& E)
{
    if(!IsInGameThread()||!GEngine||IsEngineExitRequested()){E=TEXT("Engine unavailable or operation is not on the game thread");return false;}
    UBlueprint* Blueprint=LoadObject<UBlueprint>(nullptr,*AssetPath);
    if(!Blueprint||!IsValid(Blueprint)){E=FString::Printf(TEXT("Blueprint not found at asset_path: %s"),*AssetPath);return false;}
    TSharedPtr<FJsonObject> State=MakeShareable(new FJsonObject);
    State->SetStringField(TEXT("asset_path"),AssetPath);
    State->SetStringField(TEXT("blueprint_name"),Blueprint->GetName());
    State->SetStringField(TEXT("compile_status"),BlueprintStatusToString(Blueprint));
    State->SetBoolField(TEXT("is_up_to_date"),Blueprint->IsUpToDate());
    if(Blueprint->GeneratedClass) State->SetStringField(TEXT("generated_class"),Blueprint->GeneratedClass->GetPathName());
    else State->SetStringField(TEXT("generated_class"),TEXT(""));
    O=State;
    return true;
}

bool FAtlasTransportServer::InspectBlueprintState(const FTransportRequest& R,TSharedPtr<FJsonObject>& O,FString& E)
{
    if(R.EntityIds.Num()==0){E=TEXT("inspect_blueprint_state requires at least one entity_id");return false;}
    FString AssetPath;
    if(!R.Arguments.IsValid()||!R.Arguments->TryGetStringField(TEXT("asset_path"),AssetPath)||!AssetPath.StartsWith(TEXT("/"))){E=TEXT("arguments.asset_path must be a non-empty Unreal package path");return false;}
    TSharedPtr<FJsonObject> BlueprintState;
    if(!BuildBlueprintState(AssetPath,BlueprintState,E)) return false;
    TSharedPtr<FJsonObject> Entry=MakeShareable(new FJsonObject);
    Entry->SetStringField(TEXT("entity_id"),R.EntityIds[0]);
    Entry->SetObjectField(TEXT("blueprint"),BlueprintState);
    TSharedPtr<FJsonObject> State=MakeShareable(new FJsonObject);
    for(const FString& ID:R.EntityIds) State->SetObjectField(ID,Entry);
    O=State;
    return true;
}

bool FAtlasTransportServer::CompileBlueprint(const FTransportRequest& R,TSharedPtr<FJsonObject>& O,FString& E)
{
    if(R.EntityIds.Num()==0){E=TEXT("compile_blueprint requires at least one entity_id");return false;}
    FString AssetPath;
    if(!R.Arguments.IsValid()||!R.Arguments->TryGetStringField(TEXT("asset_path"),AssetPath)||!AssetPath.StartsWith(TEXT("/"))){E=TEXT("arguments.asset_path must be a non-empty Unreal package path");return false;}
    UBlueprint* Blueprint=LoadObject<UBlueprint>(nullptr,*AssetPath);
    if(!Blueprint||!IsValid(Blueprint)){E=FString::Printf(TEXT("Blueprint not found at asset_path: %s"),*AssetPath);return false;}
    FCompilerResultsLog Results;
    FKismetEditorUtilities::CompileBlueprint(Blueprint,EBlueprintCompileOptions::None,&Results);
    if(Blueprint->Status==BS_Error){E=FString::Printf(TEXT("Blueprint compilation failed for %s"),*AssetPath);return false;}
    return InspectBlueprintState(R,O,E);
}

'''
    text = replace_once(text, implementation_anchor, implementation + implementation_anchor, "Blueprint implementation insertion") if 'bool FAtlasTransportServer::CompileBlueprint(' not in text else text

    CPP.write_text(text, encoding="utf-8", newline="\n")
    print(f"Blueprint transport implementation applied to {CPP}")


if __name__ == "__main__":
    main()
