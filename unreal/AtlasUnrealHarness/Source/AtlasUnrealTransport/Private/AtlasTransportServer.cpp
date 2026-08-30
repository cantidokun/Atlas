#include "AtlasTransportServer.h"
#include "AtlasUnrealTransport.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Actor.h"
#include "MovieScene.h"
#include "LevelSequence.h"
#include "LevelSequenceActor.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "HAL/PlatformFilemanager.h"
#include "Async/Async.h"
#include "Engine/GameViewportClient.h"
#include "Editor.h"
#include "Engine/Blueprint.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "UObject/MetaData.h"
#include "UObject/SavePackage.h"
#include "Misc/PackageName.h"
#include "MoviePipelinePrimaryConfig.h"
#include "MoviePipelineOutputSetting.h"
#include "MoviePipelineImageSequenceOutput.h"

#if PLATFORM_WINDOWS
#include "Windows/AllowWindowsPlatformTypes.h"
#include <windows.h>
#include "Windows/HideWindowsPlatformTypes.h"
#endif

const FString FAtlasTransportServer::PipeName = TEXT("\\\\.\\pipe\\AtlasUnrealTransport");
const int32 FAtlasTransportServer::MaxMessageSize = 1024 * 1024;

namespace
{
    const FString MaterialVariantTagPrefix = TEXT("atlas_material_variant:");
    const FString NiagaraVariantTagPrefix = TEXT("atlas_niagara_variant:");
    const FString HeterogeneousNiagaraFailureAuthorization = TEXT("real-heterogeneous-recovery-failure-auth");

    FString GetTaggedVariantName(const AActor* Actor, const FString& Prefix)
    {
        if (!Actor) return TEXT("default");
        for (const FName& Tag : Actor->Tags)
        {
            const FString TagString = Tag.ToString();
            if (TagString.StartsWith(Prefix))
            {
                const FString Name = TagString.Mid(Prefix.Len());
                if (!Name.TrimStartAndEnd().IsEmpty()) return Name;
            }
        }
        return TEXT("default");
    }

    void SetTaggedVariantName(AActor* Actor, const FString& Prefix, const FString& VariantName)
    {
        if (!Actor) return;
        for (int32 Index = Actor->Tags.Num() - 1; Index >= 0; --Index)
        {
            if (Actor->Tags[Index].ToString().StartsWith(Prefix)) Actor->Tags.RemoveAt(Index);
        }
        Actor->Tags.Add(FName(*(Prefix + VariantName)));
        Actor->MarkPackageDirty();
    }

    UWorld* GetActiveEditorWorld()
    {
        if (GEditor)
        {
            UWorld* EditorWorld = GEditor->GetEditorWorldContext().World();
            if (EditorWorld && IsValid(EditorWorld))
            {
                return EditorWorld;
            }
        }

        if (GEngine)
        {
            for (const FWorldContext& Context : GEngine->GetWorldContexts())
            {
                UWorld* Candidate = Context.World();
                if (Candidate && IsValid(Candidate))
                {
                    return Candidate;
                }
            }
        }

        return nullptr;
    }
}

FAtlasTransportServer::FAtlasTransportServer() : Thread(nullptr), bStopRequested(false), PipeHandle(nullptr) {}
FAtlasTransportServer::~FAtlasTransportServer() { StopServer(); }

bool FAtlasTransportServer::StartServer()
{
    if (Thread) { UE_LOG(LogAtlasTransport, Warning, TEXT("Transport server already running")); return false; }
    bStopRequested = false;
    Thread = FRunnableThread::Create(this, TEXT("AtlasTransportServer"), 0, TPri_Normal);
    return Thread != nullptr;
}

void FAtlasTransportServer::StopServer()
{
    if (Thread)
    {
        bStopRequested = true;
        CloseNamedPipe();
        Thread->WaitForCompletion();
        delete Thread;
        Thread = nullptr;
    }
}

bool FAtlasTransportServer::Init() { UE_LOG(LogAtlasTransport, Log, TEXT("Initializing transport server thread")); return true; }

uint32 FAtlasTransportServer::Run()
{
    UE_LOG(LogAtlasTransport, Log, TEXT("Transport server thread started"));
    while (!bStopRequested)
    {
        if (!CreatePipeHandle()) { UE_LOG(LogAtlasTransport, Error, TEXT("Failed to create named pipe")); FPlatformProcess::Sleep(1.0f); continue; }
        UE_LOG(LogAtlasTransport, Log, TEXT("Waiting for client connection..."));
        if (!WaitForClient()) { CloseNamedPipe(); if (!bStopRequested) { UE_LOG(LogAtlasTransport, Warning, TEXT("Client connection failed")); FPlatformProcess::Sleep(0.1f); } continue; }
        if (bStopRequested) { CloseNamedPipe(); break; }
        UE_LOG(LogAtlasTransport, Log, TEXT("Client connected"));
        FString JsonRequest;
        if (ReadRequest(JsonRequest))
        {
            if (bStopRequested) { CloseNamedPipe(); break; }
            FTransportRequest Request;
            if (ParseRequest(JsonRequest, Request))
            {
                FString ValidationError;
                if (ValidateRequest(Request, ValidationError))
                {
                    FTransportResponse Response;
                    ExecuteRequest(Request, Response);
                    WriteResponse(SerializeResponse(Response));
                }
                else
                {
                    FTransportResponse ErrorResponse;
                    ErrorResponse.RequestId = Request.RequestId; ErrorResponse.OperationName = Request.OperationName; ErrorResponse.EntityIds = Request.EntityIds;
                    ErrorResponse.bSuccess = false; ErrorResponse.Error = ValidationError; ErrorResponse.Source = TEXT("unreal-editor-atlas-transport");
                    WriteResponse(SerializeResponse(ErrorResponse));
                }
            }
            else UE_LOG(LogAtlasTransport, Error, TEXT("Failed to parse request JSON"));
        }
        else UE_LOG(LogAtlasTransport, Warning, TEXT("Failed to read request"));
        CloseNamedPipe();
    }
    UE_LOG(LogAtlasTransport, Log, TEXT("Transport server thread exiting"));
    return 0;
}

void FAtlasTransportServer::Stop() { bStopRequested = true; }
void FAtlasTransportServer::Exit() { CloseNamedPipe(); }

bool FAtlasTransportServer::CreatePipeHandle()
{
#if PLATFORM_WINDOWS
    HANDLE hPipe = CreateNamedPipeA(TCHAR_TO_ANSI(*PipeName), PIPE_ACCESS_DUPLEX, PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT, 1, MaxMessageSize, MaxMessageSize, 0, nullptr);
    if (hPipe == INVALID_HANDLE_VALUE) { UE_LOG(LogAtlasTransport, Error, TEXT("CreateNamedPipe failed with error: %d"), GetLastError()); return false; }
    PipeHandle = hPipe; return true;
#else
    return false;
#endif
}

void FAtlasTransportServer::CloseNamedPipe()
{
#if PLATFORM_WINDOWS
    if (PipeHandle && PipeHandle != INVALID_HANDLE_VALUE) { CloseHandle((HANDLE)PipeHandle); PipeHandle = nullptr; }
#endif
}

bool FAtlasTransportServer::WaitForClient()
{
#if PLATFORM_WINDOWS
    if (!PipeHandle || PipeHandle == INVALID_HANDLE_VALUE) return false;
    BOOL bConnected = ConnectNamedPipe((HANDLE)PipeHandle, nullptr);
    if (!bConnected) { const DWORD dwError = GetLastError(); if (dwError == ERROR_PIPE_CONNECTED) return true; UE_LOG(LogAtlasTransport, Error, TEXT("ConnectNamedPipe failed with error: %d"), dwError); return false; }
    return true;
#else
    return false;
#endif
}

bool FAtlasTransportServer::ReadRequest(FString& OutJsonRequest)
{
#if PLATFORM_WINDOWS
    if (!PipeHandle || PipeHandle == INVALID_HANDLE_VALUE) return false;
    TArray<uint8> Buffer; Buffer.SetNum(MaxMessageSize); DWORD BytesRead = 0;
    BOOL bSuccess = ReadFile((HANDLE)PipeHandle, Buffer.GetData(), MaxMessageSize, &BytesRead, nullptr);
    if (!bSuccess) { const DWORD dwError = GetLastError(); if (dwError == ERROR_MORE_DATA) { UE_LOG(LogAtlasTransport, Error, TEXT("Message exceeds maximum size of %d bytes"), MaxMessageSize); return false; } UE_LOG(LogAtlasTransport, Error, TEXT("ReadFile failed with error: %d"), dwError); return false; }
    if (BytesRead == 0) return false;
    Buffer.SetNum(BytesRead + 1); Buffer[BytesRead] = 0; OutJsonRequest = FString(UTF8_TO_TCHAR(reinterpret_cast<const char*>(Buffer.GetData()))); return true;
#else
    return false;
#endif
}

bool FAtlasTransportServer::WriteResponse(const FString& JsonResponse)
{
#if PLATFORM_WINDOWS
    if (!PipeHandle || PipeHandle == INVALID_HANDLE_VALUE) return false;
    FTCHARToUTF8 UTF8String(*JsonResponse); const DWORD BytesToWrite = UTF8String.Length(); DWORD BytesWritten = 0;
    const BOOL bSuccess = WriteFile((HANDLE)PipeHandle, UTF8String.Get(), BytesToWrite, &BytesWritten, nullptr);
    if (!bSuccess || BytesWritten != BytesToWrite) { UE_LOG(LogAtlasTransport, Error, TEXT("WriteFile failed with error: %d"), GetLastError()); return false; }
    FlushFileBuffers((HANDLE)PipeHandle); return true;
#else
    return false;
#endif
}

bool FAtlasTransportServer::ParseRequest(const FString& JsonString, FTransportRequest& OutRequest)
{
    TSharedPtr<FJsonObject> JsonObject; TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonString);
    if (!FJsonSerializer::Deserialize(Reader, JsonObject) || !JsonObject.IsValid()) return false;
    if (!JsonObject->TryGetStringField(TEXT("request_id"), OutRequest.RequestId) || !JsonObject->TryGetStringField(TEXT("operation_name"), OutRequest.OperationName) || !JsonObject->TryGetStringField(TEXT("capability"), OutRequest.Capability) || !JsonObject->TryGetStringField(TEXT("kind"), OutRequest.Kind) || !JsonObject->TryGetStringField(TEXT("authorization_id"), OutRequest.AuthorizationId)) return false;
    if (!JsonObject->TryGetStringArrayField(TEXT("entity_ids"), OutRequest.EntityIds)) return false;
    const TSharedPtr<FJsonObject>* ArgumentsObject; if (JsonObject->TryGetObjectField(TEXT("arguments"), ArgumentsObject)) OutRequest.Arguments = *ArgumentsObject;
    return true;
}

FString FAtlasTransportServer::SerializeResponse(const FTransportResponse& Response)
{
    TSharedPtr<FJsonObject> JsonObject = MakeShareable(new FJsonObject);
    JsonObject->SetStringField(TEXT("request_id"), Response.RequestId); JsonObject->SetStringField(TEXT("operation_name"), Response.OperationName); JsonObject->SetBoolField(TEXT("success"), Response.bSuccess); JsonObject->SetStringField(TEXT("error"), Response.Error); JsonObject->SetStringField(TEXT("source"), Response.Source);
    TArray<TSharedPtr<FJsonValue>> EntityIdsArray; for (const FString& EntityId : Response.EntityIds) EntityIdsArray.Add(MakeShareable(new FJsonValueString(EntityId))); JsonObject->SetArrayField(TEXT("entity_ids"), EntityIdsArray);
    if (Response.ObservedState.IsValid()) JsonObject->SetObjectField(TEXT("observed_state"), Response.ObservedState); else JsonObject->SetObjectField(TEXT("observed_state"), MakeShareable(new FJsonObject));
    FString OutputString; TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString); FJsonSerializer::Serialize(JsonObject.ToSharedRef(), Writer); return OutputString;
}

bool FAtlasTransportServer::ValidateRequest(const FTransportRequest& Request, FString& OutError)
{
    if (Request.RequestId.IsEmpty()) { OutError = TEXT("request_id cannot be empty"); return false; }
    if (Request.AuthorizationId.IsEmpty() || Request.AuthorizationId.TrimStartAndEnd().IsEmpty()) { OutError = TEXT("authorization_id cannot be empty"); return false; }
    if (Request.EntityIds.Num() == 0) { OutError = TEXT("entity_ids cannot be empty"); return false; }
    for (const FString& EntityId : Request.EntityIds) if (EntityId.IsEmpty() || EntityId.TrimStartAndEnd().IsEmpty()) { OutError = TEXT("entity_ids cannot contain empty strings"); return false; }
    if (!Request.Arguments.IsValid()) { OutError = TEXT("arguments cannot be null"); return false; }
    TArray<FString> ArgumentEntityIds; if (!Request.Arguments->TryGetStringArrayField(TEXT("entity_ids"), ArgumentEntityIds)) { OutError = TEXT("arguments.entity_ids must be an array of strings"); return false; }
    if (ArgumentEntityIds.Num() != Request.EntityIds.Num()) { OutError = TEXT("arguments.entity_ids must match entity_ids"); return false; }
    for (int32 Index = 0; Index < Request.EntityIds.Num(); ++Index) if (ArgumentEntityIds[Index] != Request.EntityIds[Index]) { OutError = TEXT("arguments.entity_ids must match entity_ids"); return false; }
    if (Request.OperationName == TEXT("inspect_target_actors")) { if (Request.Capability != TEXT("inspect_actor") || Request.Kind != TEXT("read")) { OutError = TEXT("inspect_target_actors requires inspect_actor/read"); return false; } return true; }
    if (Request.OperationName == TEXT("set_actor_location"))
    {
        if (Request.Capability != TEXT("modify_actor") || Request.Kind != TEXT("write")) { OutError = TEXT("set_actor_location requires modify_actor/write"); return false; }
        if (Request.EntityIds.Num() != 1) { OutError = TEXT("set_actor_location requires exactly one entity_id"); return false; }
        const TSharedPtr<FJsonObject>* O=nullptr; if (!Request.Arguments->TryGetObjectField(TEXT("location"),O)||!O||!O->IsValid()){OutError=TEXT("arguments.location must be an object");return false;} double X=0,Y=0,Z=0; if(!(*O)->TryGetNumberField(TEXT("x"),X)||!(*O)->TryGetNumberField(TEXT("y"),Y)||!(*O)->TryGetNumberField(TEXT("z"),Z)){OutError=TEXT("arguments.location must contain numeric x, y, and z");return false;} return true;
    }
    if (Request.OperationName == TEXT("set_actor_rotation"))
    {
        if (Request.Capability != TEXT("modify_actor") || Request.Kind != TEXT("write")) { OutError = TEXT("set_actor_rotation requires modify_actor/write"); return false; }
        if (Request.EntityIds.Num() != 1) { OutError = TEXT("set_actor_rotation requires exactly one entity_id"); return false; }
        const TSharedPtr<FJsonObject>* O=nullptr; if (!Request.Arguments->TryGetObjectField(TEXT("rotation"),O)||!O||!O->IsValid()){OutError=TEXT("arguments.rotation must be an object");return false;} double A=0,B=0,C=0; if(!(*O)->TryGetNumberField(TEXT("pitch"),A)||!(*O)->TryGetNumberField(TEXT("yaw"),B)||!(*O)->TryGetNumberField(TEXT("roll"),C)){OutError=TEXT("arguments.rotation must contain numeric pitch, yaw, and roll");return false;} return true;
    }
    if (Request.OperationName == TEXT("set_actor_scale"))
    {
        if (Request.Capability != TEXT("modify_actor") || Request.Kind != TEXT("write")) { OutError = TEXT("set_actor_scale requires modify_actor/write"); return false; }
        if (Request.EntityIds.Num() != 1) { OutError = TEXT("set_actor_scale requires exactly one entity_id"); return false; }
        const TSharedPtr<FJsonObject>* O=nullptr; if (!Request.Arguments->TryGetObjectField(TEXT("scale"),O)||!O||!O->IsValid()){OutError=TEXT("arguments.scale must be an object");return false;} double X=0,Y=0,Z=0; if(!(*O)->TryGetNumberField(TEXT("x"),X)||!(*O)->TryGetNumberField(TEXT("y"),Y)||!(*O)->TryGetNumberField(TEXT("z"),Z)){OutError=TEXT("arguments.scale must contain numeric x, y, and z");return false;} return true;
    }
    if (Request.OperationName == TEXT("inspect_material_state")) { if (Request.Capability != TEXT("material") || Request.Kind != TEXT("read")) { OutError = TEXT("inspect_material_state requires material/read"); return false; } return true; }
    if (Request.OperationName == TEXT("apply_material_variant"))
    {
        if (Request.Capability != TEXT("material") || Request.Kind != TEXT("write")) { OutError = TEXT("apply_material_variant requires material/write"); return false; }
        const TSharedPtr<FJsonObject>* O=nullptr; if(!Request.Arguments->TryGetObjectField(TEXT("material_variant"),O)||!O||!O->IsValid()){OutError=TEXT("arguments.material_variant must be an object");return false;} FString Name; if(!(*O)->TryGetStringField(TEXT("name"),Name)||Name.TrimStartAndEnd().IsEmpty()){OutError=TEXT("arguments.material_variant.name must be a non-empty string");return false;} return true;
    }
    if (Request.OperationName == TEXT("inspect_niagara_state")) { if (Request.Capability != TEXT("niagara") || Request.Kind != TEXT("read")) { OutError = TEXT("inspect_niagara_state requires niagara/read"); return false; } return true; }
    if (Request.OperationName == TEXT("apply_niagara_variant"))
    {
        if (Request.Capability != TEXT("niagara") || Request.Kind != TEXT("write")) { OutError = TEXT("apply_niagara_variant requires niagara/write"); return false; }
        const TSharedPtr<FJsonObject>* O=nullptr; if(!Request.Arguments->TryGetObjectField(TEXT("niagara_variant"),O)||!O||!O->IsValid()){OutError=TEXT("arguments.niagara_variant must be an object");return false;} FString Name; if(!(*O)->TryGetStringField(TEXT("name"),Name)||Name.TrimStartAndEnd().IsEmpty()){OutError=TEXT("arguments.niagara_variant.name must be a non-empty string");return false;} return true;
    }
    if (Request.OperationName == TEXT("inspect_blueprint_state"))
    {
        if (Request.Capability != TEXT("blueprint") || Request.Kind != TEXT("read")) { OutError = TEXT("inspect_blueprint_state requires blueprint/read"); return false; }
        FString AssetPath;
        if (!Request.Arguments->TryGetStringField(TEXT("asset_path"), AssetPath) || !AssetPath.StartsWith(TEXT("/"))) { OutError = TEXT("arguments.asset_path must be a non-empty Unreal package path"); return false; }
        return true;
    }
    if (Request.OperationName == TEXT("set_blueprint_metadata"))
    {
        if (Request.Capability != TEXT("blueprint") || Request.Kind != TEXT("write"))
        {
            OutError = TEXT("set_blueprint_metadata requires blueprint/write");
            return false;
        }

        FString AssetPath;
        FString MetadataKey;
        FString MetadataValue;

        if (!Request.Arguments->TryGetStringField(TEXT("asset_path"), AssetPath) ||
            !AssetPath.StartsWith(TEXT("/")))
        {
            OutError = TEXT("arguments.asset_path must be a non-empty Unreal package path");
            return false;
        }

        if (!Request.Arguments->TryGetStringField(TEXT("metadata_key"), MetadataKey) ||
            MetadataKey.TrimStartAndEnd().IsEmpty())
        {
            OutError = TEXT("arguments.metadata_key must be a non-empty string");
            return false;
        }

        if (!Request.Arguments->TryGetStringField(TEXT("metadata_value"), MetadataValue))
        {
            OutError = TEXT("arguments.metadata_value must be a string");
            return false;
        }

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
    if (Request.OperationName == TEXT("inspect_render_state"))
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
    {
        if (Request.Capability != TEXT("sequencer") || Request.Kind != TEXT("read")) { OutError = TEXT("inspect_sequencer_state requires sequencer/read"); return false; }
        return true;
    }
    if (Request.OperationName == TEXT("set_sequencer_playback_range"))
    {
        if (Request.Capability != TEXT("sequencer") || Request.Kind != TEXT("write")) { OutError = TEXT("set_sequencer_playback_range requires sequencer/write"); return false; }
        const TSharedPtr<FJsonObject>* Start=nullptr; const TSharedPtr<FJsonObject>* End=nullptr;
        double StartFrame=0, EndFrame=0;
        if(!Request.Arguments->TryGetNumberField(TEXT("start_frame"),StartFrame)||!Request.Arguments->TryGetNumberField(TEXT("end_frame"),EndFrame)){OutError=TEXT("start_frame and end_frame must be numeric");return false;}
        if(FMath::RoundToInt(StartFrame)!=StartFrame||FMath::RoundToInt(EndFrame)!=EndFrame){OutError=TEXT("start_frame and end_frame must be integers");return false;}
        if(StartFrame>EndFrame){OutError=TEXT("Sequencer start frame must not exceed end frame");return false;} return true;
    }
    if (Request.OperationName == TEXT("verify_sequencer_playback_range"))
    {
        if (Request.Capability != TEXT("sequencer") || Request.Kind != TEXT("verify")) { OutError = TEXT("verify_sequencer_playback_range requires sequencer/verify"); return false; }
        double StartFrame=0, EndFrame=0;
        if(!Request.Arguments->TryGetNumberField(TEXT("expected_start_frame"),StartFrame)||!Request.Arguments->TryGetNumberField(TEXT("expected_end_frame"),EndFrame)){OutError=TEXT("expected_start_frame and expected_end_frame must be numeric");return false;}
        if(FMath::RoundToInt(StartFrame)!=StartFrame||FMath::RoundToInt(EndFrame)!=EndFrame){OutError=TEXT("expected_start_frame and expected_end_frame must be integers");return false;}
        if(StartFrame>EndFrame){OutError=TEXT("Sequencer start frame must not exceed end frame");return false;} return true;
    }
    OutError = FString::Printf(TEXT("Unsupported operation_name: %s"), *Request.OperationName); return false;
}

bool FAtlasTransportServer::ExecuteRequest(const FTransportRequest& Request, FTransportResponse& OutResponse)
{
    OutResponse.RequestId=Request.RequestId; OutResponse.OperationName=Request.OperationName; OutResponse.EntityIds=Request.EntityIds; OutResponse.Source=TEXT("unreal-editor-atlas-transport");
    const bool bSupported = Request.OperationName==TEXT("inspect_target_actors")||Request.OperationName==TEXT("set_actor_location")||Request.OperationName==TEXT("set_actor_rotation")||Request.OperationName==TEXT("set_actor_scale")||Request.OperationName==TEXT("inspect_material_state")||Request.OperationName==TEXT("apply_material_variant")||Request.OperationName==TEXT("inspect_niagara_state")||Request.OperationName==TEXT("apply_niagara_variant")||Request.OperationName==TEXT("inspect_sequencer_state")||Request.OperationName==TEXT("set_sequencer_playback_range")||Request.OperationName==TEXT("verify_sequencer_playback_range")||Request.OperationName==TEXT("inspect_blueprint_state")||Request.OperationName==TEXT("compile_blueprint")||Request.OperationName==TEXT("verify_blueprint_state")||Request.OperationName==TEXT("set_blueprint_metadata")||Request.OperationName==TEXT("inspect_render_state")||Request.OperationName==TEXT("configure_render")||Request.OperationName==TEXT("verify_render_state");
    if (!bSupported) { OutResponse.bSuccess=false; OutResponse.Error=FString::Printf(TEXT("Unsupported operation: %s"),*Request.OperationName); return false; }
    TSharedPtr<FGameThreadExecutionState> SharedState=MakeShareable(new FGameThreadExecutionState()); SharedState->Request=Request; SharedState->Response.RequestId=Request.RequestId; SharedState->Response.OperationName=Request.OperationName; SharedState->Response.EntityIds=Request.EntityIds; SharedState->Response.Source=TEXT("unreal-editor-atlas-transport");
    AsyncTask(ENamedThreads::GameThread,[SharedState](){FAtlasTransportServer::ExecuteOnGameThread(SharedState);});
    const bool bEventTriggered=SharedState->CompletionEvent->Wait(5000);
    if (bStopRequested) { SharedState->bCancelled=true; OutResponse.bSuccess=false; OutResponse.Error=TEXT("Operation cancelled during shutdown"); return false; }
    if (!bEventTriggered) { SharedState->bCancelled=true; OutResponse.bSuccess=false; OutResponse.Error=TEXT("Operation timed out"); return false; }
    OutResponse=SharedState->Response; return SharedState->bSuccess;
}

void FAtlasTransportServer::ExecuteOnGameThread(TSharedPtr<FGameThreadExecutionState> S)
{
    if (S->bCancelled) { S->Response.bSuccess=false; S->Response.Error=TEXT("Operation cancelled before execution"); S->bSuccess=false; S->bCompleted=true; S->CompletionEvent->Trigger(); return; }
    if (!IsInGameThread()) { S->Response.bSuccess=false; S->Response.Error=TEXT("ExecuteOnGameThread must be called on game thread"); S->bSuccess=false; S->bCompleted=true; S->CompletionEvent->Trigger(); return; }
    if (!GEngine || IsEngineExitRequested()) { S->Response.bSuccess=false; S->Response.Error=TEXT("Engine shutting down"); S->bSuccess=false; S->bCompleted=true; S->CompletionEvent->Trigger(); return; }
    bool bTaskSuccess=false;
    if(S->Request.OperationName==TEXT("inspect_target_actors")) bTaskSuccess=InspectTargetActors(S->Request.EntityIds,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("set_actor_location")) bTaskSuccess=SetActorLocation(S->Request,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("set_actor_rotation")) bTaskSuccess=SetActorRotation(S->Request,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("set_actor_scale")) bTaskSuccess=SetActorScale(S->Request,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("inspect_material_state")) bTaskSuccess=InspectMaterialState(S->Request.EntityIds,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("apply_material_variant")) bTaskSuccess=ApplyMaterialVariant(S->Request,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("inspect_niagara_state")) bTaskSuccess=InspectNiagaraState(S->Request.EntityIds,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("apply_niagara_variant")) bTaskSuccess=ApplyNiagaraVariant(S->Request,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("inspect_sequencer_state")) bTaskSuccess=InspectSequencerState(S->Request.EntityIds,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("inspect_blueprint_state")) bTaskSuccess=InspectBlueprintState(S->Request,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("inspect_render_state")) bTaskSuccess=InspectRenderState(S->Request,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("configure_render")) bTaskSuccess=ConfigureRender(S->Request,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("compile_blueprint")) bTaskSuccess=CompileBlueprint(S->Request,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("set_blueprint_metadata")) bTaskSuccess=SetBlueprintMetadata(S->Request,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("verify_blueprint_state")) bTaskSuccess=InspectBlueprintState(S->Request,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("verify_render_state")) bTaskSuccess=InspectRenderState(S->Request,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("set_sequencer_playback_range")) bTaskSuccess=SetSequencerPlaybackRange(S->Request,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("verify_sequencer_playback_range")) bTaskSuccess=InspectSequencerState(S->Request.EntityIds,S->ObservedState,S->Error);
    else S->Error=FString::Printf(TEXT("Unsupported operation: %s"),*S->Request.OperationName);
    if(bTaskSuccess&&S->Error.IsEmpty()){S->Response.bSuccess=true;S->Response.ObservedState=S->ObservedState;S->bSuccess=true;}else{S->Response.bSuccess=false;S->Response.Error=S->Error.IsEmpty()?TEXT("Unknown error during Unreal operation"):S->Error;S->bSuccess=false;}
    S->bCompleted=true; S->CompletionEvent->Trigger();
}

bool FAtlasTransportServer::SetActorLocation(const FTransportRequest& R,TSharedPtr<FJsonObject>& O,FString& E)
{
    if(!IsInGameThread()||!GEngine||IsEngineExitRequested()){E=TEXT("Engine unavailable or operation is not on the game thread");return false;} if(R.EntityIds.Num()!=1||!R.Arguments.IsValid()){E=TEXT("set_actor_location requires exactly one entity_id and valid arguments");return false;}
    const TSharedPtr<FJsonObject>* P=nullptr; if(!R.Arguments->TryGetObjectField(TEXT("location"),P)||!P||!P->IsValid()){E=TEXT("arguments.location must be an object");return false;} double X=0,Y=0,Z=0; if(!(*P)->TryGetNumberField(TEXT("x"),X)||!(*P)->TryGetNumberField(TEXT("y"),Y)||!(*P)->TryGetNumberField(TEXT("z"),Z)){E=TEXT("arguments.location must contain numeric x, y, and z");return false;} AActor* A=FindActorByEntityId(R.EntityIds[0]); if(!A||!IsValid(A)){E=FString::Printf(TEXT("Actor not found for entity_id: %s"),*R.EntityIds[0]);return false;} A->SetActorLocation(FVector((float)X,(float)Y,(float)Z),false,nullptr,ETeleportType::TeleportPhysics); return InspectTargetActors(R.EntityIds,O,E);
}

bool FAtlasTransportServer::SetActorRotation(const FTransportRequest& R,TSharedPtr<FJsonObject>& O,FString& E)
{
    if(!IsInGameThread()||!GEngine||IsEngineExitRequested()){E=TEXT("Engine unavailable or operation is not on the game thread");return false;} if(R.EntityIds.Num()!=1||!R.Arguments.IsValid()){E=TEXT("set_actor_rotation requires exactly one entity_id");return false;} const TSharedPtr<FJsonObject>* P=nullptr; if(!R.Arguments->TryGetObjectField(TEXT("rotation"),P)||!P||!P->IsValid()){E=TEXT("arguments.rotation must be an object");return false;} double A=0,B=0,C=0; if(!(*P)->TryGetNumberField(TEXT("pitch"),A)||!(*P)->TryGetNumberField(TEXT("yaw"),B)||!(*P)->TryGetNumberField(TEXT("roll"),C)){E=TEXT("arguments.rotation must contain numeric pitch, yaw, and roll");return false;} AActor* Actor=FindActorByEntityId(R.EntityIds[0]); if(!Actor||!IsValid(Actor)){E=FString::Printf(TEXT("Actor not found for entity_id: %s"),*R.EntityIds[0]);return false;} Actor->SetActorRotation(FRotator((float)A,(float)B,(float)C)); return InspectTargetActors(R.EntityIds,O,E);
}

bool FAtlasTransportServer::SetActorScale(const FTransportRequest& R,TSharedPtr<FJsonObject>& O,FString& E)
{
    if(!IsInGameThread()||!GEngine||IsEngineExitRequested()){E=TEXT("Engine unavailable or operation is not on the game thread");return false;} if(R.EntityIds.Num()!=1||!R.Arguments.IsValid()){E=TEXT("set_actor_scale requires exactly one entity_id");return false;} const TSharedPtr<FJsonObject>* P=nullptr; if(!R.Arguments->TryGetObjectField(TEXT("scale"),P)||!P||!P->IsValid()){E=TEXT("arguments.scale must be an object");return false;} double X=0,Y=0,Z=0; if(!(*P)->TryGetNumberField(TEXT("x"),X)||!(*P)->TryGetNumberField(TEXT("y"),Y)||!(*P)->TryGetNumberField(TEXT("z"),Z)){E=TEXT("arguments.scale must contain numeric x, y, and z");return false;} AActor* Actor=FindActorByEntityId(R.EntityIds[0]); if(!Actor||!IsValid(Actor)){E=FString::Printf(TEXT("Actor not found for entity_id: %s"),*R.EntityIds[0]);return false;} Actor->SetActorScale3D(FVector((float)X,(float)Y,(float)Z)); return InspectTargetActors(R.EntityIds,O,E);
}

bool FAtlasTransportServer::InspectMaterialState(const TArray<FString>& IDs,TSharedPtr<FJsonObject>& O,FString& E)
{
    if(!IsInGameThread()||!GEngine||IsEngineExitRequested()){E=TEXT("Engine unavailable or operation is not on the game thread");return false;} if(IDs.Num()==0){E=TEXT("inspect_material_state requires at least one entity_id");return false;} TSharedPtr<FJsonObject> State=MakeShareable(new FJsonObject);
    for(const FString& ID:IDs){AActor* A=FindActorByEntityId(ID);if(!A||!IsValid(A)){E=FString::Printf(TEXT("Actor not found for entity_id: %s"),*ID);return false;} TSharedPtr<FJsonObject> M; if(!BuildMaterialVariantState(A,M,E))return false; TSharedPtr<FJsonObject>D=MakeShareable(new FJsonObject);D->SetStringField(TEXT("entity_id"),ID);D->SetObjectField(TEXT("material"),M);State->SetObjectField(ID,D);} O=State;return true;
}

bool FAtlasTransportServer::ApplyMaterialVariant(const FTransportRequest& R,TSharedPtr<FJsonObject>& O,FString& E)
{
    if(!IsInGameThread()||!GEngine||IsEngineExitRequested()){E=TEXT("Engine unavailable or operation is not on the game thread");return false;} if(!R.Arguments.IsValid()||R.EntityIds.Num()==0){E=TEXT("apply_material_variant requires valid arguments and target entity_ids");return false;} const TSharedPtr<FJsonObject>* P=nullptr; if(!R.Arguments->TryGetObjectField(TEXT("material_variant"),P)||!P||!P->IsValid()){E=TEXT("arguments.material_variant must be an object");return false;} FString Name; if(!(*P)->TryGetStringField(TEXT("name"),Name)||Name.TrimStartAndEnd().IsEmpty()){E=TEXT("arguments.material_variant.name must be a non-empty string");return false;} for(const FString& ID:R.EntityIds){AActor* A=FindActorByEntityId(ID);if(!A||!IsValid(A)){E=FString::Printf(TEXT("Actor not found for entity_id: %s"),*ID);return false;}SetTaggedVariantName(A,MaterialVariantTagPrefix,Name);} return InspectMaterialState(R.EntityIds,O,E);
}

bool FAtlasTransportServer::BuildMaterialVariantState(AActor* A,TSharedPtr<FJsonObject>& O,FString& E)
{
    if(!A||!IsValid(A)){E=TEXT("Cannot inspect material state for invalid actor");return false;} TSharedPtr<FJsonObject> V=MakeShareable(new FJsonObject);V->SetStringField(TEXT("name"),GetTaggedVariantName(A,MaterialVariantTagPrefix));O=MakeShareable(new FJsonObject);O->SetObjectField(TEXT("variant"),V);return true;
}

bool FAtlasTransportServer::InspectNiagaraState(const TArray<FString>& IDs,TSharedPtr<FJsonObject>& O,FString& E)
{
    if(!IsInGameThread()||!GEngine||IsEngineExitRequested()){E=TEXT("Engine unavailable or operation is not on the game thread");return false;} if(IDs.Num()==0){E=TEXT("inspect_niagara_state requires at least one entity_id");return false;} TSharedPtr<FJsonObject> State=MakeShareable(new FJsonObject);
    for(const FString& ID:IDs){AActor* A=FindActorByEntityId(ID);if(!A||!IsValid(A)){E=FString::Printf(TEXT("Actor not found for entity_id: %s"),*ID);return false;} TSharedPtr<FJsonObject>N; if(!BuildNiagaraVariantState(A,N,E))return false; TSharedPtr<FJsonObject>D=MakeShareable(new FJsonObject);D->SetStringField(TEXT("entity_id"),ID);D->SetObjectField(TEXT("niagara"),N);State->SetObjectField(ID,D);} O=State;return true;
}

bool FAtlasTransportServer::ApplyNiagaraVariant(const FTransportRequest& R,TSharedPtr<FJsonObject>& O,FString& E)
{
    if(!IsInGameThread()||!GEngine||IsEngineExitRequested()){E=TEXT("Engine unavailable or operation is not on the game thread");return false;} if(!R.Arguments.IsValid()||R.EntityIds.Num()==0){E=TEXT("apply_niagara_variant requires valid arguments and target entity_ids");return false;} const TSharedPtr<FJsonObject>* P=nullptr; if(!R.Arguments->TryGetObjectField(TEXT("niagara_variant"),P)||!P||!P->IsValid()){E=TEXT("arguments.niagara_variant must be an object");return false;} FString Name; if(!(*P)->TryGetStringField(TEXT("name"),Name)||Name.TrimStartAndEnd().IsEmpty()){E=TEXT("arguments.niagara_variant.name must be a non-empty string");return false;}
    if (R.AuthorizationId == HeterogeneousNiagaraFailureAuthorization)
    {
        E = TEXT("deterministic heterogeneous recovery failure injected by Unreal validation harness");
        return false;
    }
    for(const FString& ID:R.EntityIds){AActor* A=FindActorByEntityId(ID);if(!A||!IsValid(A)){E=FString::Printf(TEXT("Actor not found for entity_id: %s"),*ID);return false;}SetTaggedVariantName(A,NiagaraVariantTagPrefix,Name);} return InspectNiagaraState(R.EntityIds,O,E);
}

bool FAtlasTransportServer::BuildNiagaraVariantState(AActor* A,TSharedPtr<FJsonObject>& O,FString& E)
{
    if(!A||!IsValid(A)){E=TEXT("Cannot inspect Niagara state for invalid actor");return false;} TSharedPtr<FJsonObject> V=MakeShareable(new FJsonObject);V->SetStringField(TEXT("name"),GetTaggedVariantName(A,NiagaraVariantTagPrefix));O=MakeShareable(new FJsonObject);O->SetObjectField(TEXT("variant"),V);return true;
}

bool FAtlasTransportServer::FindSequencerPlaybackRange(int32& OutStartFrame, int32& OutEndFrame, FString& OutError)
{
    if(!IsInGameThread()||!GEngine||IsEngineExitRequested()){OutError=TEXT("Engine unavailable or operation is not on the game thread");return false;}
    UWorld* World=GetActiveEditorWorld();
    if(!World||!IsValid(World)){OutError=TEXT("No valid active editor world found");return false;}
    for(TActorIterator<ALevelSequenceActor> It(World); It; ++It)
    {
        ALevelSequenceActor* SequenceActor=*It;
        if(!SequenceActor||!IsValid(SequenceActor)||!SequenceActor->GetSequence()) continue;
        ULevelSequence* Sequence=SequenceActor->GetSequence();
        if(!Sequence->GetMovieScene()) continue;
        UMovieScene* MovieScene=Sequence->GetMovieScene();
        const TRange<FFrameNumber> PlaybackRange=MovieScene->GetPlaybackRange();
        if(!PlaybackRange.HasLowerBound() || !PlaybackRange.HasUpperBound())
        {
            OutError=TEXT("Sequencer playback range is open-ended");
            return false;
        }
        OutStartFrame=PlaybackRange.GetLowerBoundValue().Value;
        OutEndFrame=PlaybackRange.GetUpperBoundValue().Value;
        return true;
    }
    OutError=TEXT("No Level Sequence actor with a valid sequence found in the active Unreal editor world"); return false;
}

bool FAtlasTransportServer::InspectSequencerState(const TArray<FString>& IDs,TSharedPtr<FJsonObject>& O,FString& E)
{
    if(IDs.Num()==0){E=TEXT("inspect_sequencer_state requires at least one entity_id");return false;}
    if(IDs.Num()!=1){E=TEXT("inspect_sequencer_state currently requires exactly one entity_id");return false;}
    int32 StartFrame=0,EndFrame=0; if(!FindSequencerPlaybackRange(StartFrame,EndFrame,E)) return false;
    TSharedPtr<FJsonObject> State=MakeShareable(new FJsonObject); TSharedPtr<FJsonObject> Entry=MakeShareable(new FJsonObject);
    Entry->SetStringField(TEXT("entity_id"),IDs[0]); TSharedPtr<FJsonObject> Seq=MakeShareable(new FJsonObject); Seq->SetNumberField(TEXT("start_frame"),StartFrame); Seq->SetNumberField(TEXT("end_frame"),EndFrame); Entry->SetObjectField(TEXT("sequencer"),Seq); State->SetObjectField(IDs[0],Entry); O=State; return true;
}

bool FAtlasTransportServer::SetSequencerPlaybackRange(const FTransportRequest& R,TSharedPtr<FJsonObject>& O,FString& E)
{
    if(R.EntityIds.Num()!=1){E=TEXT("set_sequencer_playback_range requires exactly one entity_id");return false;}
    double StartFrameValue=0,EndFrameValue=0; if(!R.Arguments->TryGetNumberField(TEXT("start_frame"),StartFrameValue)||!R.Arguments->TryGetNumberField(TEXT("end_frame"),EndFrameValue)){E=TEXT("start_frame and end_frame must be numeric");return false;}
    if(FMath::RoundToInt(StartFrameValue)!=StartFrameValue||FMath::RoundToInt(EndFrameValue)!=EndFrameValue){E=TEXT("start_frame and end_frame must be integers");return false;}
    const int32 StartFrame=FMath::RoundToInt(StartFrameValue); const int32 EndFrame=FMath::RoundToInt(EndFrameValue); if(StartFrame>EndFrame){E=TEXT("Sequencer start frame must not exceed end frame");return false;}
    UWorld* World=GetActiveEditorWorld(); if(!World||!IsValid(World)){E=TEXT("No valid active editor world found");return false;}
    for(TActorIterator<ALevelSequenceActor> It(World); It; ++It)
    {
        ALevelSequenceActor* SequenceActor=*It; if(!SequenceActor||!IsValid(SequenceActor)||!SequenceActor->GetSequence()) continue;
        ULevelSequence* Sequence=SequenceActor->GetSequence(); UMovieScene* MovieScene=Sequence->GetMovieScene(); if(!MovieScene) continue;
        MovieScene->Modify(); MovieScene->SetPlaybackRange(StartFrame,EndFrame - StartFrame); return InspectSequencerState(R.EntityIds,O,E);
    }
    E=TEXT("No Level Sequence actor with a valid sequence found in the active Unreal editor world"); return false;
}

bool FAtlasTransportServer::InspectTargetActors(const TArray<FString>& IDs,TSharedPtr<FJsonObject>& O,FString& E)
{
    if(!IsInGameThread()||!GEngine||IsEngineExitRequested()){E=TEXT("Engine unavailable or operation is not on the game thread");return false;} UWorld* World=nullptr; if(GEngine->GetWorldContexts().Num()>0)World=GEngine->GetWorldContexts()[0].World(); if(!World||!IsValid(World)){E=TEXT("No valid world found");return false;} TSharedPtr<FJsonObject> State=MakeShareable(new FJsonObject);
    for(const FString& ID:IDs){AActor* A=FindActorByEntityId(ID);if(!A||!IsValid(A)){E=FString::Printf(TEXT("Actor not found for entity_id: %s"),*ID);return false;} TSharedPtr<FJsonObject>D=MakeShareable(new FJsonObject);D->SetStringField(TEXT("entity_id"),ID);D->SetStringField(TEXT("actor_name"),A->GetName());D->SetStringField(TEXT("actor_class"),A->GetClass()->GetName()); FVector L=A->GetActorLocation();TSharedPtr<FJsonObject>LO=MakeShareable(new FJsonObject);LO->SetNumberField(TEXT("x"),L.X);LO->SetNumberField(TEXT("y"),L.Y);LO->SetNumberField(TEXT("z"),L.Z);D->SetObjectField(TEXT("location"),LO); FRotator R=A->GetActorRotation();TSharedPtr<FJsonObject>RO=MakeShareable(new FJsonObject);RO->SetNumberField(TEXT("pitch"),R.Pitch);RO->SetNumberField(TEXT("yaw"),R.Yaw);RO->SetNumberField(TEXT("roll"),R.Roll);D->SetObjectField(TEXT("rotation"),RO); FVector S=A->GetActorScale3D();TSharedPtr<FJsonObject>SO=MakeShareable(new FJsonObject);SO->SetNumberField(TEXT("x"),S.X);SO->SetNumberField(TEXT("y"),S.Y);SO->SetNumberField(TEXT("z"),S.Z);D->SetObjectField(TEXT("scale"),SO);State->SetObjectField(ID,D);} O=State;return true;
}

namespace
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

    TSharedPtr<FJsonObject> Metadata = MakeShareable(new FJsonObject);
    if (TMap<FName, FString>* MetadataValues = FMetaData::GetMapForObject(Blueprint))
    {
        for (const TPair<FName, FString>& Pair : *MetadataValues)
        {
            Metadata->SetStringField(Pair.Key.ToString(), Pair.Value);
        }
    }
    State->SetObjectField(TEXT("metadata"), Metadata);
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


bool FAtlasTransportServer::SetBlueprintMetadata(
    const FTransportRequest& R,
    TSharedPtr<FJsonObject>& O,
    FString& E)
{
    if (R.EntityIds.Num() == 0)
    {
        E = TEXT("set_blueprint_metadata requires at least one entity_id");
        return false;
    }

    if (!R.Arguments.IsValid())
    {
        E = TEXT("set_blueprint_metadata requires arguments");
        return false;
    }

    FString AssetPath;
    FString MetadataKey;
    FString MetadataValue;

    if (!R.Arguments->TryGetStringField(TEXT("asset_path"), AssetPath) ||
        !AssetPath.StartsWith(TEXT("/")))
    {
        E = TEXT("arguments.asset_path must be a non-empty Unreal package path");
        return false;
    }

    if (!R.Arguments->TryGetStringField(TEXT("metadata_key"), MetadataKey) ||
        MetadataKey.TrimStartAndEnd().IsEmpty())
    {
        E = TEXT("arguments.metadata_key must be a non-empty string");
        return false;
    }

    if (!R.Arguments->TryGetStringField(TEXT("metadata_value"), MetadataValue))
    {
        E = TEXT("arguments.metadata_value must be a string");
        return false;
    }

    MetadataKey = MetadataKey.TrimStartAndEnd();
    MetadataValue = MetadataValue.TrimStartAndEnd();

    UBlueprint* Blueprint = LoadObject<UBlueprint>(nullptr, *AssetPath);
    if (!Blueprint || !IsValid(Blueprint))
    {
        E = FString::Printf(
            TEXT("Blueprint not found at asset_path: %s"),
            *AssetPath);
        return false;
    }

    UPackage* Package = Blueprint->GetOutermost();
    if (!Package || !IsValid(Package))
    {
        E = FString::Printf(
            TEXT("Blueprint package unavailable at asset_path: %s"),
            *AssetPath);
        return false;
    }

    FMetaData& MetaData = Package->GetMetaData();
    MetaData.SetValue(Blueprint, *MetadataKey, *MetadataValue);
    Package->MarkPackageDirty();

    const FString PackageFilename =
        FPackageName::LongPackageNameToFilename(
            Package->GetName(),
            FPackageName::GetAssetPackageExtension());

    FSavePackageArgs SaveArgs;
    SaveArgs.TopLevelFlags = RF_Public | RF_Standalone;
    SaveArgs.SaveFlags = SAVE_None;

    if (!UPackage::SavePackage(
            Package,
            Blueprint,
            *PackageFilename,
            SaveArgs))
    {
        E = FString::Printf(
            TEXT("Failed to save Blueprint package at asset_path: %s"),
            *AssetPath);
        return false;
    }

    return InspectBlueprintState(R, O, E);
}


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
        UMoviePipelineOutputSetting* Setting = Cast<UMoviePipelineOutputSetting>(Config->FindSettingByClass(UMoviePipelineOutputSetting::StaticClass(), false, true));
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
        UMoviePipelineImageSequenceOutput_PNG* Existing = Cast<UMoviePipelineImageSequenceOutput_PNG>(Config->FindSettingByClass(UMoviePipelineImageSequenceOutput_PNG::StaticClass(), false, true));
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

AActor* FAtlasTransportServer::FindActorByEntityId(const FString& EntityId)
{
    if(!IsInGameThread()||!GEngine||IsEngineExitRequested())return nullptr; UWorld* World=nullptr; if(GEngine->GetWorldContexts().Num()>0)World=GEngine->GetWorldContexts()[0].World(); if(!World||!IsValid(World))return nullptr; const FString TagToFind=FString::Printf(TEXT("atlas_entity:%s"),*EntityId); for(TActorIterator<AActor> ActorItr(World);ActorItr;++ActorItr){AActor* Actor=*ActorItr;if(Actor&&IsValid(Actor)&&Actor->Tags.Contains(FName(*TagToFind)))return Actor;} return nullptr;
}
