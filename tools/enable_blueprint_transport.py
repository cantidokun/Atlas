"""Apply the Blueprint transport implementation to an existing Unreal harness.

This migration is intentionally deterministic: it edits only the known Atlas
transport anchors and aborts instead of guessing if the transport has drifted.
Run from the repository root after pulling the Blueprint contract commits.
"""

from pathlib import Path

CPP = Path("unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Private/AtlasTransportServer.cpp")
HEADER = Path("unreal/AtlasUnrealHarness/Source/AtlasUnrealTransport/Public/AtlasTransportServer.h")
EXECUTOR = Path("planning/unreal_plan_executor.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one {label} anchor, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    if not CPP.exists() or not HEADER.exists():
        raise SystemExit(f"missing Blueprint transport source/header: {CPP} / {HEADER}")

    text = CPP.read_text(encoding="utf-8")
    header_text = HEADER.read_text(encoding="utf-8")

    if '#include "Engine/Blueprint.h"' not in text:
        text = replace_once(
            text,
            '#include "Editor.h"\n',
            '#include "Editor.h"\n#include "Engine/Blueprint.h"\n#include "Kismet2/KismetEditorUtilities.h"\n',
            "Blueprint includes",
        )

    if '#include "Misc/PackageName.h"' not in text:
        text = replace_once(
            text,
            '#include "Kismet2/KismetEditorUtilities.h"\n',
            '#include "Kismet2/KismetEditorUtilities.h"\n#include "Misc/PackageName.h"\n#include "UObject/SavePackage.h"\n',
            "Blueprint save includes",
        )

    if 'static bool SetBlueprintMetadata' not in header_text:
        header_text = replace_once(
            header_text,
            '    static bool CompileBlueprint(const FTransportRequest& Request,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);\n',
            '    static bool CompileBlueprint(const FTransportRequest& Request,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);\n    static bool SetBlueprintMetadata(const FTransportRequest& Request,TSharedPtr<FJsonObject>& OutObservedState,FString& OutError);\n',
            "Blueprint metadata declaration",
        )

    if 'Request.OperationName == TEXT("inspect_blueprint_state")' not in text:
        validation_anchor = '    if (Request.OperationName == TEXT("inspect_sequencer_state"))\n'
        validation = '''    if (Request.OperationName == TEXT("inspect_blueprint_state"))
    {
        if (Request.Capability != TEXT("blueprint") || Request.Kind != TEXT("read")) { OutError = TEXT("inspect_blueprint_state requires blueprint/read"); return false; }
        FString AssetPath;
        if (!Request.Arguments->TryGetStringField(TEXT("asset_path"), AssetPath) || !AssetPath.StartsWith(TEXT("/"))) { OutError = TEXT("arguments.asset_path must be a non-empty Unreal package path"); return false; }
        return true;
    }
    if (Request.OperationName == TEXT("set_blueprint_metadata"))
    {
        if (Request.Capability != TEXT("blueprint") || Request.Kind != TEXT("write")) { OutError = TEXT("set_blueprint_metadata requires blueprint/write"); return false; }
        FString AssetPath;
        FString MetadataKey;
        FString MetadataValue;
        if (!Request.Arguments->TryGetStringField(TEXT("asset_path"), AssetPath) || !AssetPath.StartsWith(TEXT("/"))) { OutError = TEXT("arguments.asset_path must be a non-empty Unreal package path"); return false; }
        if (!Request.Arguments->TryGetStringField(TEXT("metadata_key"), MetadataKey) || MetadataKey.TrimStartAndEnd().IsEmpty()) { OutError = TEXT("arguments.metadata_key must be a non-empty string"); return false; }
        if (!Request.Arguments->TryGetStringField(TEXT("metadata_value"), MetadataValue) || MetadataValue.TrimStartAndEnd().IsEmpty()) { OutError = TEXT("arguments.metadata_value must be a non-empty string"); return false; }
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
        text = replace_once(text, validation_anchor, validation + validation_anchor, "Blueprint validation")
    elif 'Request.OperationName == TEXT("set_blueprint_metadata")' not in text:
        validation_anchor = '    if (Request.OperationName == TEXT("inspect_sequencer_state"))\n'
        validation = '''    if (Request.OperationName == TEXT("set_blueprint_metadata"))
    {
        if (Request.Capability != TEXT("blueprint") || Request.Kind != TEXT("write")) { OutError = TEXT("set_blueprint_metadata requires blueprint/write"); return false; }
        FString AssetPath;
        FString MetadataKey;
        FString MetadataValue;
        if (!Request.Arguments->TryGetStringField(TEXT("asset_path"), AssetPath) || !AssetPath.StartsWith(TEXT("/"))) { OutError = TEXT("arguments.asset_path must be a non-empty Unreal package path"); return false; }
        if (!Request.Arguments->TryGetStringField(TEXT("metadata_key"), MetadataKey) || MetadataKey.TrimStartAndEnd().IsEmpty()) { OutError = TEXT("arguments.metadata_key must be a non-empty string"); return false; }
        if (!Request.Arguments->TryGetStringField(TEXT("metadata_value"), MetadataValue) || MetadataValue.TrimStartAndEnd().IsEmpty()) { OutError = TEXT("arguments.metadata_value must be a non-empty string"); return false; }
        return true;
    }
'''
        text = replace_once(text, validation_anchor, validation + validation_anchor, "Blueprint metadata validation")

    supported_anchor = 'Request.OperationName==TEXT("verify_sequencer_playback_range");'
    if 'Request.OperationName==TEXT("set_blueprint_metadata")' not in text[text.find('const bool bSupported'):text.find('const bool bSupported') + 1800]:
        supported = 'Request.OperationName==TEXT("verify_sequencer_playback_range")||Request.OperationName==TEXT("inspect_blueprint_state")||Request.OperationName==TEXT("set_blueprint_metadata")||Request.OperationName==TEXT("compile_blueprint")||Request.OperationName==TEXT("verify_blueprint_state");'
        text = replace_once(text, supported_anchor, supported, "supported operation list")
    elif 'Request.OperationName==TEXT("set_blueprint_metadata")' not in text:
        text = replace_once(text, supported_anchor, 'Request.OperationName==TEXT("verify_sequencer_playback_range")||Request.OperationName==TEXT("set_blueprint_metadata");', "Blueprint metadata supported operation")

    dispatch_anchor = '    else if(S->Request.OperationName==TEXT("inspect_sequencer_state")) bTaskSuccess=InspectSequencerState(S->Request.EntityIds,S->ObservedState,S->Error);\n'
    if 'else if(S->Request.OperationName==TEXT("set_blueprint_metadata"))' not in text:
        dispatch = dispatch_anchor + '''    else if(S->Request.OperationName==TEXT("inspect_blueprint_state")) bTaskSuccess=InspectBlueprintState(S->Request,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("set_blueprint_metadata")) bTaskSuccess=SetBlueprintMetadata(S->Request,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("compile_blueprint")) bTaskSuccess=CompileBlueprint(S->Request,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("verify_blueprint_state")) bTaskSuccess=InspectBlueprintState(S->Request,S->ObservedState,S->Error);
'''
        text = replace_once(text, dispatch_anchor, dispatch, "game-thread Blueprint dispatch")

    if 'bool FAtlasTransportServer::CompileBlueprint(' not in text:
        implementation_anchor = 'AActor* FAtlasTransportServer::FindActorByEntityId(const FString& EntityId)\n'
        implementation = '''namespace
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
    const TArray<FName>& MetadataKeys=Blueprint->GetMetaData().GetKeys();
    TSharedPtr<FJsonObject> Metadata=MakeShareable(new FJsonObject);
    for(const FName& Key:MetadataKeys) Metadata->SetStringField(Key.ToString(),Blueprint->GetMetaData(Key));
    State->SetObjectField(TEXT("metadata"),Metadata);
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

bool FAtlasTransportServer::SetBlueprintMetadata(const FTransportRequest& R,TSharedPtr<FJsonObject>& O,FString& E)
{
    if(R.EntityIds.Num()==0){E=TEXT("set_blueprint_metadata requires at least one entity_id");return false;}
    FString AssetPath, MetadataKey, MetadataValue;
    if(!R.Arguments.IsValid()||!R.Arguments->TryGetStringField(TEXT("asset_path"),AssetPath)||!AssetPath.StartsWith(TEXT("/"))){E=TEXT("arguments.asset_path must be a non-empty Unreal package path");return false;}
    if(!R.Arguments->TryGetStringField(TEXT("metadata_key"),MetadataKey)||MetadataKey.TrimStartAndEnd().IsEmpty()){E=TEXT("arguments.metadata_key must be a non-empty string");return false;}
    if(!R.Arguments->TryGetStringField(TEXT("metadata_value"),MetadataValue)||MetadataValue.TrimStartAndEnd().IsEmpty()){E=TEXT("arguments.metadata_value must be a non-empty string");return false;}
    UBlueprint* Blueprint=LoadObject<UBlueprint>(nullptr,*AssetPath);
    if(!Blueprint||!IsValid(Blueprint)){E=FString::Printf(TEXT("Blueprint not found at asset_path: %s"),*AssetPath);return false;}
    MetadataKey=MetadataKey.TrimStartAndEnd();
    MetadataValue=MetadataValue.TrimStartAndEnd();
    Blueprint->SetMetaData(FName(*MetadataKey),*MetadataValue);
    Blueprint->MarkPackageDirty();
    UPackage* Package=Blueprint->GetOutermost();
    const FString PackageName=Package->GetName();
    const FString Filename=FPackageName::LongPackageNameToFilename(PackageName,FPackageName::GetAssetPackageExtension());
    FSavePackageArgs SaveArgs;
    SaveArgs.TopLevelFlags=RF_Public|RF_Standalone;
    SaveArgs.Error=GError;
    if(!UPackage::SavePackage(Package,Blueprint,*Filename,SaveArgs)){E=FString::Printf(TEXT("Failed to save Blueprint metadata to %s"),*Filename);return false;}
    return InspectBlueprintState(R,O,E);
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
        text = replace_once(text, implementation_anchor, implementation + implementation_anchor, "Blueprint implementation insertion")
    elif 'bool FAtlasTransportServer::SetBlueprintMetadata(' not in text:
        implementation_anchor = 'bool FAtlasTransportServer::CompileBlueprint('
        metadata_impl = '''bool FAtlasTransportServer::SetBlueprintMetadata(const FTransportRequest& R,TSharedPtr<FJsonObject>& O,FString& E)
{
    if(R.EntityIds.Num()==0){E=TEXT("set_blueprint_metadata requires at least one entity_id");return false;}
    FString AssetPath, MetadataKey, MetadataValue;
    if(!R.Arguments.IsValid()||!R.Arguments->TryGetStringField(TEXT("asset_path"),AssetPath)||!AssetPath.StartsWith(TEXT("/"))){E=TEXT("arguments.asset_path must be a non-empty Unreal package path");return false;}
    if(!R.Arguments->TryGetStringField(TEXT("metadata_key"),MetadataKey)||MetadataKey.TrimStartAndEnd().IsEmpty()){E=TEXT("arguments.metadata_key must be a non-empty string");return false;}
    if(!R.Arguments->TryGetStringField(TEXT("metadata_value"),MetadataValue)||MetadataValue.TrimStartAndEnd().IsEmpty()){E=TEXT("arguments.metadata_value must be a non-empty string");return false;}
    UBlueprint* Blueprint=LoadObject<UBlueprint>(nullptr,*AssetPath);
    if(!Blueprint||!IsValid(Blueprint)){E=FString::Printf(TEXT("Blueprint not found at asset_path: %s"),*AssetPath);return false;}
    MetadataKey=MetadataKey.TrimStartAndEnd();
    MetadataValue=MetadataValue.TrimStartAndEnd();
    Blueprint->SetMetaData(FName(*MetadataKey),*MetadataValue);
    Blueprint->MarkPackageDirty();
    UPackage* Package=Blueprint->GetOutermost();
    const FString Filename=FPackageName::LongPackageNameToFilename(Package->GetName(),FPackageName::GetAssetPackageExtension());
    FSavePackageArgs SaveArgs;
    SaveArgs.TopLevelFlags=RF_Public|RF_Standalone;
    SaveArgs.Error=GError;
    if(!UPackage::SavePackage(Package,Blueprint,*Filename,SaveArgs)){E=FString::Printf(TEXT("Failed to save Blueprint metadata to %s"),*Filename);return false;}
    return InspectBlueprintState(R,O,E);
}

'''
        text = replace_once(text, implementation_anchor, metadata_impl + implementation_anchor, "Blueprint metadata implementation insertion")

    if 'const TArray<FName>& MetadataKeys=Blueprint->GetMetaData().GetKeys();' not in text:
        metadata_anchor = '    else State->SetStringField(TEXT("generated_class"),TEXT(""));\n    O=State;\n'
        metadata_block = '''    else State->SetStringField(TEXT("generated_class"),TEXT(""));
    const TArray<FName>& MetadataKeys=Blueprint->GetMetaData().GetKeys();
    TSharedPtr<FJsonObject> Metadata=MakeShareable(new FJsonObject);
    for(const FName& Key:MetadataKeys) Metadata->SetStringField(Key.ToString(),Blueprint->GetMetaData(Key));
    State->SetObjectField(TEXT("metadata"),Metadata);
    O=State;
'''
        text = replace_once(text, metadata_anchor, metadata_block, "Blueprint metadata state")

    if EXECUTOR.exists():
        executor_text = EXECUTOR.read_text(encoding="utf-8")
        old_shape = '            if verification.kind is not UnrealOperationKind.VERIFY: raise UnrealPlanExecutionError(f"Write operation {index} (\'{operation.name}\') must be immediately followed by verification")'
        new_shape = '            if verification.kind is not UnrealOperationKind.VERIFY:\n                if not (operation.name == "set_blueprint_metadata" and verification.kind is UnrealOperationKind.WRITE and verification.name == "compile_blueprint"):\n                    raise UnrealPlanExecutionError(f"Write operation {index} (\'{operation.name}\') must be immediately followed by verification")'
        if 'operation.name == "set_blueprint_metadata"' not in executor_text:
            executor_text = replace_once(executor_text, old_shape, new_shape, "Blueprint metadata write/compile execution rule")
            EXECUTOR.write_text(executor_text, encoding="utf-8")

    CPP.write_text(text, encoding="utf-8")
    HEADER.write_text(header_text, encoding="utf-8")
    print(f"Blueprint metadata transport implementation applied to {CPP}")


if __name__ == "__main__":
    main()
