#include "AtlasTransportServer.h"
#include "HAL/CriticalSection.h"
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
#include "Misc/Paths.h"
#include "MoviePipelinePrimaryConfig.h"
#include "MoviePipelineOutputSetting.h"
#include "MoviePipelineImageSequenceOutput.h"
#include "MoviePipelineDeferredPasses.h"
#include "MoviePipelineQueueSubsystem.h"
#include "MoviePipelinePIEExecutor.h"
#include "MoviePipelineExecutor.h"
#include "MoviePipelineQueue.h"


#if PLATFORM_WINDOWS
#include "Windows/AllowWindowsPlatformTypes.h"
#include <windows.h>
#include <bcrypt.h>
#include "Windows/HideWindowsPlatformTypes.h"
#endif

const FString FAtlasTransportServer::PipeName = TEXT("\\\\.\\pipe\\AtlasUnrealTransport");

FCriticalSection FAtlasTransportServer::RenderJobRegistryMutex;
TMap<FString,TSharedPtr<FAtlasTransportServer::FRenderJobState>> FAtlasTransportServer::RenderJobRegistry;
FAtlasTransportServer* FAtlasTransportServer::ActiveInstance = nullptr;
const int32 FAtlasTransportServer::MaxMessageSize = 1024 * 1024;

namespace
{
    FString S_ErrorCode;
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

FAtlasTransportServer::FAtlasTransportServer() : Thread(nullptr), bStopRequested(false), PipeHandle(nullptr), ProcessId(0) {}
FAtlasTransportServer::~FAtlasTransportServer() { StopServer(); }

bool FAtlasTransportServer::StartServer()
{
    if (Thread) { UE_LOG(LogAtlasTransport, Warning, TEXT("Transport server already running")); return false; }
    bStopRequested = false;

    // Initialize process incarnation identity
    EditorSessionId = FGuid::NewGuid();
    ProcessId = FPlatformProcess::GetCurrentProcessId();
    ServerStartTimeUtc = FDateTime::UtcNow().ToIso8601();
    EngineVersion = TEXT("5.6");
    ProjectIdentity = FPaths::GetProjectFilePath();

    // Acquire true OS creation timestamp on Windows
    ProcessCreationTimeUtc = ServerStartTimeUtc;
#if PLATFORM_WINDOWS
    HANDLE hProcess = GetCurrentProcess();
    FILETIME ftCreation, ftExit, ftKernel, ftUser;
    if (GetProcessTimes(hProcess, &ftCreation, &ftExit, &ftKernel, &ftUser))
    {
        SYSTEMTIME stUTC;
        if (FileTimeToSystemTime(&ftCreation, &stUTC))
        {
            FDateTime CreationDateTime(stUTC.wYear, stUTC.wMonth, stUTC.wDay, stUTC.wHour, stUTC.wMinute, stUTC.wSecond, stUTC.wMilliseconds);
            ProcessCreationTimeUtc = CreationDateTime.ToIso8601();
        }
    }
#endif

    ActiveInstance = this;
    Thread = FRunnableThread::Create(this, TEXT("AtlasTransportServer"), 0, TPri_Normal);
    return Thread != nullptr;
}

void FAtlasTransportServer::StopServer()
{
    if (ActiveInstance == this)
    {
        ActiveInstance = nullptr;
    }
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
                    ErrorResponse.SchemaVersion = 1;
                    if (Request.SchemaVersion != 1)
                    {
                        ErrorResponse.ErrorCode = TEXT("ERR_UNSUPPORTED_SCHEMA_VERSION");
                    }
                    else
                    {
                        ErrorResponse.ErrorCode = TEXT("ERR_MISSING_ARGUMENT");
                    }
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

    // Parse schema_version (defaults to 0 if not present, enforcing fail-closed on unversioned requests)
    int32 SchemaVer = 0;
    if (JsonObject->TryGetNumberField(TEXT("schema_version"), SchemaVer))
    {
        OutRequest.SchemaVersion = SchemaVer;
    }
    else
    {
        OutRequest.SchemaVersion = 0;
    }

    const TSharedPtr<FJsonObject>* ArgumentsObject; if (JsonObject->TryGetObjectField(TEXT("arguments"), ArgumentsObject)) OutRequest.Arguments = *ArgumentsObject;
    return true;
}

FString FAtlasTransportServer::SerializeResponse(const FTransportResponse& Response)
{
    TSharedPtr<FJsonObject> JsonObject = MakeShareable(new FJsonObject);
    JsonObject->SetStringField(TEXT("request_id"), Response.RequestId);
    JsonObject->SetStringField(TEXT("operation_name"), Response.OperationName);
    JsonObject->SetBoolField(TEXT("success"), Response.bSuccess);
    JsonObject->SetStringField(TEXT("error"), Response.Error);
    JsonObject->SetStringField(TEXT("source"), Response.Source);
    JsonObject->SetNumberField(TEXT("schema_version"), Response.SchemaVersion > 0 ? Response.SchemaVersion : 1);
    JsonObject->SetStringField(TEXT("error_code"), Response.ErrorCode);

    TSharedPtr<FJsonObject> SessionObject = MakeShareable(new FJsonObject);
    CollectSessionIdentity(SessionObject);
    JsonObject->SetObjectField(TEXT("session_identity"), SessionObject);

    TArray<TSharedPtr<FJsonValue>> EntityIdsArray; for (const FString& EntityId : Response.EntityIds) EntityIdsArray.Add(MakeShareable(new FJsonValueString(EntityId))); JsonObject->SetArrayField(TEXT("entity_ids"), EntityIdsArray);
    if (Response.ObservedState.IsValid()) JsonObject->SetObjectField(TEXT("observed_state"), Response.ObservedState); else JsonObject->SetObjectField(TEXT("observed_state"), MakeShareable(new FJsonObject));
    FString OutputString; TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString); FJsonSerializer::Serialize(JsonObject.ToSharedRef(), Writer); return OutputString;
}

bool FAtlasTransportServer::ValidateRequest(const FTransportRequest& Request, FString& OutError)
{
    if (Request.SchemaVersion != 1)
    {
        OutError = FString::Printf(TEXT("Unsupported schema_version: %d (expected 1)"), Request.SchemaVersion);
        return false;
    }
    if (Request.RequestId.IsEmpty()) { OutError = TEXT("request_id cannot be empty"); return false; }
    if (Request.AuthorizationId.IsEmpty() || Request.AuthorizationId.TrimStartAndEnd().IsEmpty()) { OutError = TEXT("authorization_id cannot be empty"); return false; }
    const bool bIsWorldInspection =
        Request.OperationName == TEXT("inspect_world");

    const bool bIsServerCapability =
        Request.OperationName == TEXT("get_capabilities");

    if (!bIsWorldInspection && !bIsServerCapability)
    {
        if (Request.EntityIds.Num() == 0)
        {
            OutError = TEXT("entity_ids cannot be empty");
            return false;
        }

        for (const FString& EntityId : Request.EntityIds)
        {
            if (EntityId.IsEmpty() || EntityId.TrimStartAndEnd().IsEmpty())
            {
                OutError = TEXT("entity_ids cannot contain empty strings");
                return false;
            }
        }

        if (!Request.Arguments.IsValid())
        {
            OutError = TEXT("arguments cannot be null");
            return false;
        }

        TArray<FString> ArgumentEntityIds;

        if (!Request.Arguments->TryGetStringArrayField(
                TEXT("entity_ids"),
                ArgumentEntityIds))
        {
            OutError =
                TEXT("arguments.entity_ids must be an array of strings");
            return false;
        }

        if (ArgumentEntityIds.Num() != Request.EntityIds.Num())
        {
            OutError =
                TEXT("arguments.entity_ids must match entity_ids");
            return false;
        }

        for (int32 Index = 0;
             Index < Request.EntityIds.Num();
             ++Index)
        {
            if (ArgumentEntityIds[Index] != Request.EntityIds[Index])
            {
                OutError =
                    TEXT("arguments.entity_ids must match entity_ids");
                return false;
            }
        }
    }

    if (Request.OperationName == TEXT("inspect_world"))
    {
        if (Request.Capability != TEXT("world") ||
            Request.Kind != TEXT("inspect"))
        {
            OutError = TEXT("inspect_world requires world/inspect");
            return false;
        }

        return true;
    }

    if (Request.OperationName == TEXT("get_capabilities"))
    {
        if (Request.Capability != TEXT("server") || Request.Kind != TEXT("inspect"))
        {
            OutError = TEXT("get_capabilities requires server/inspect");
            return false;
        }
        return true;
    }

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
    if (Request.OperationName == TEXT("submit_render"))
    {
        if (Request.Capability != TEXT("render") || Request.Kind != TEXT("write"))
        {
            OutError = TEXT("submit_render requires render/write");
            return false;
        }

        if (Request.EntityIds.Num() != 1)
        {
            OutError = TEXT("submit_render requires exactly one entity_id");
            return false;
        }

        FString JobId;
        if (Request.Arguments->TryGetStringField(TEXT("job_id"), JobId) &&
            JobId.TrimStartAndEnd().IsEmpty())
        {
            OutError = TEXT("arguments.job_id must be a non-empty string when provided");
            return false;
        }

        return true;
    }

    if (Request.OperationName == TEXT("inspect_render_job"))
    {
        if (Request.Capability != TEXT("render") || Request.Kind != TEXT("read"))
        {
            OutError = TEXT("inspect_render_job requires render/read");
            return false;
        }

        FString JobId;
        if (!Request.Arguments->TryGetStringField(TEXT("job_id"), JobId) ||
            JobId.TrimStartAndEnd().IsEmpty())
        {
            OutError = TEXT("arguments.job_id must be a non-empty string");
            return false;
        }

        return true;
    }

    if (Request.OperationName == TEXT("reconcile_render_jobs"))
    {
        if (Request.Capability != TEXT("render") || Request.Kind != TEXT("read"))
        {
            OutError = TEXT("reconcile_render_jobs requires render/read");
            return false;
        }
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
    OutResponse.SchemaVersion=1;
    OutResponse.ErrorCode=TEXT("");

    const bool bSupported = Request.OperationName==TEXT("inspect_world")||Request.OperationName==TEXT("inspect_target_actors")||Request.OperationName==TEXT("set_actor_location")||Request.OperationName==TEXT("set_actor_rotation")||Request.OperationName==TEXT("set_actor_scale")||Request.OperationName==TEXT("inspect_material_state")||Request.OperationName==TEXT("apply_material_variant")||Request.OperationName==TEXT("inspect_niagara_state")||Request.OperationName==TEXT("apply_niagara_variant")||Request.OperationName==TEXT("inspect_sequencer_state")||Request.OperationName==TEXT("set_sequencer_playback_range")||Request.OperationName==TEXT("verify_sequencer_playback_range")||Request.OperationName==TEXT("inspect_blueprint_state")||Request.OperationName==TEXT("compile_blueprint")||Request.OperationName==TEXT("verify_blueprint_state")||Request.OperationName==TEXT("set_blueprint_metadata")||Request.OperationName==TEXT("inspect_render_state")||Request.OperationName==TEXT("configure_render")||Request.OperationName==TEXT("submit_render")||Request.OperationName==TEXT("inspect_render_job")||Request.OperationName==TEXT("verify_render_state")||Request.OperationName==TEXT("get_capabilities")||Request.OperationName==TEXT("reconcile_render_jobs");
    if (!bSupported) { OutResponse.bSuccess=false; OutResponse.Error=FString::Printf(TEXT("Unsupported operation: %s"),*Request.OperationName); OutResponse.ErrorCode=TEXT("ERR_UNKNOWN_OPERATION"); return false; }
    TSharedPtr<FGameThreadExecutionState> SharedState=MakeShareable(new FGameThreadExecutionState()); SharedState->Request=Request; SharedState->Response.RequestId=Request.RequestId; SharedState->Response.OperationName=Request.OperationName; SharedState->Response.EntityIds=Request.EntityIds; SharedState->Response.Source=TEXT("unreal-editor-atlas-transport");
    SharedState->Response.SchemaVersion=1;
    AsyncTask(ENamedThreads::GameThread,[SharedState](){FAtlasTransportServer::ExecuteOnGameThread(SharedState);});
    const bool bEventTriggered=SharedState->CompletionEvent->Wait(5000);
    if (bStopRequested) { SharedState->bCancelled=true; OutResponse.bSuccess=false; OutResponse.Error=TEXT("Operation cancelled during shutdown"); OutResponse.ErrorCode=TEXT("ERR_OPERATION_CANCELLED"); return false; }
    if (!bEventTriggered) { SharedState->bCancelled=true; OutResponse.bSuccess=false; OutResponse.Error=TEXT("Operation timed out"); OutResponse.ErrorCode=TEXT("ERR_OPERATION_TIMED_OUT"); return false; }
    OutResponse=SharedState->Response; return SharedState->bSuccess;
}

void FAtlasTransportServer::ExecuteOnGameThread(TSharedPtr<FGameThreadExecutionState> S)
{
    if (S->bCancelled) { S->Response.bSuccess=false; S->Response.Error=TEXT("Operation cancelled before execution"); S->bSuccess=false; S->bCompleted=true; S->CompletionEvent->Trigger(); return; }
    if (!IsInGameThread()) { S->Response.bSuccess=false; S->Response.Error=TEXT("ExecuteOnGameThread must be called on game thread"); S->bSuccess=false; S->bCompleted=true; S->CompletionEvent->Trigger(); return; }
    if (!GEngine || IsEngineExitRequested()) { S->Response.bSuccess=false; S->Response.Error=TEXT("Engine shutting down"); S->bSuccess=false; S->bCompleted=true; S->CompletionEvent->Trigger(); return; }
    bool bTaskSuccess=false;
    S_ErrorCode.Empty();
    if(S->Request.OperationName==TEXT("inspect_world")) bTaskSuccess=InspectWorld(S->ObservedState,S->Error);

    else if(S->Request.OperationName==TEXT("inspect_target_actors")) bTaskSuccess=InspectTargetActors(S->Request.EntityIds,S->ObservedState,S->Error);
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
    else if(S->Request.OperationName==TEXT("submit_render")) bTaskSuccess=SubmitRender(S->Request,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("inspect_render_job")) bTaskSuccess=InspectRenderJob(S->Request,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("compile_blueprint")) bTaskSuccess=CompileBlueprint(S->Request,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("set_blueprint_metadata")) bTaskSuccess=SetBlueprintMetadata(S->Request,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("verify_blueprint_state")) bTaskSuccess=InspectBlueprintState(S->Request,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("verify_render_state")) bTaskSuccess=InspectRenderState(S->Request,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("set_sequencer_playback_range")) bTaskSuccess=SetSequencerPlaybackRange(S->Request,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("verify_sequencer_playback_range")) bTaskSuccess=InspectSequencerState(S->Request.EntityIds,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("get_capabilities")) bTaskSuccess=GetCapabilities(S->Request,S->ObservedState,S->Error);
    else if(S->Request.OperationName==TEXT("reconcile_render_jobs")) bTaskSuccess=ReconcileRenderJobs(S->Request,S->ObservedState,S->Error);
    else S->Error=FString::Printf(TEXT("Unsupported operation: %s"),*S->Request.OperationName);
    if(bTaskSuccess&&S->Error.IsEmpty()){
        S->Response.bSuccess=true;
        S->Response.ObservedState=S->ObservedState;
        S->Response.ErrorCode=TEXT("");
        S->bSuccess=true;
    }else{
        S->Response.bSuccess=false;
        S->Response.Error=S->Error.IsEmpty()?TEXT("Unknown error during Unreal operation"):S->Error;
        if(!S_ErrorCode.IsEmpty())
        {
            S->Response.ErrorCode=S_ErrorCode;
        }
        else if(S->Response.ErrorCode.IsEmpty())
        {
            S->Response.ErrorCode=TEXT("ERR_OPERATION_FAILED");
        }
        S->bSuccess=false;
    }
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

bool FAtlasTransportServer::InspectWorld(
    TSharedPtr<FJsonObject>& O,
    FString& E)
{
    if(!IsInGameThread() || !GEngine || IsEngineExitRequested())
    {
        E=TEXT("Engine unavailable or operation is not on the game thread");
        return false;
    }

    UWorld* World=nullptr;

    for(const FWorldContext& Context : GEngine->GetWorldContexts())
    {
        if(Context.World() && IsValid(Context.World()))
        {
            World=Context.World();
            if(Context.WorldType==EWorldType::Editor)
            {
                break;
            }
        }
    }

    if(!World || !IsValid(World))
    {
        E=TEXT("No valid world found");
        return false;
    }

    TSharedPtr<FJsonObject> State=
        MakeShareable(new FJsonObject);

    State->SetStringField(
        TEXT("world_name"),
        World->GetName());

    State->SetStringField(
        TEXT("world_path"),
        World->GetPathName());

    FString WorldTypeString;

    switch(World->WorldType)
    {
    case EWorldType::Editor:
        WorldTypeString=TEXT("Editor");
        break;

    case EWorldType::Game:
        WorldTypeString=TEXT("Game");
        break;

    case EWorldType::PIE:
        WorldTypeString=TEXT("PIE");
        break;

    case EWorldType::EditorPreview:
        WorldTypeString=TEXT("EditorPreview");
        break;

    case EWorldType::GamePreview:
        WorldTypeString=TEXT("GamePreview");
        break;

    case EWorldType::GameRPC:
        WorldTypeString=TEXT("GameRPC");
        break;

    case EWorldType::Inactive:
        WorldTypeString=TEXT("Inactive");
        break;

    default:
        WorldTypeString=TEXT("Unknown");
        break;
    }

    State->SetStringField(
        TEXT("world_type"),
        WorldTypeString);

    State->SetNumberField(
        TEXT("actor_count"),
        World->GetCurrentLevel()
            ? World->GetCurrentLevel()->Actors.Num()
            : 0);

    TArray<TSharedPtr<FJsonValue>> Actors;

    for(TActorIterator<AActor> ActorItr(World);
        ActorItr;
        ++ActorItr)
    {
        AActor* Actor=*ActorItr;

        if(!Actor || !IsValid(Actor))
        {
            continue;
        }

        TSharedPtr<FJsonObject> ActorState=
            MakeShareable(new FJsonObject);

        ActorState->SetStringField(
            TEXT("name"),
            Actor->GetName());

        ActorState->SetStringField(
            TEXT("class"),
            Actor->GetClass()->GetName());

        FVector Location=Actor->GetActorLocation();

        TSharedPtr<FJsonObject> LocationObject=
            MakeShareable(new FJsonObject);

        LocationObject->SetNumberField(TEXT("x"),Location.X);
        LocationObject->SetNumberField(TEXT("y"),Location.Y);
        LocationObject->SetNumberField(TEXT("z"),Location.Z);

        ActorState->SetObjectField(
            TEXT("location"),
            LocationObject);

        TArray<TSharedPtr<FJsonValue>> Tags;

        for(const FName& Tag : Actor->Tags)
        {
            Tags.Add(
                MakeShareable(
                    new FJsonValueString(Tag.ToString())));
        }

        ActorState->SetArrayField(
            TEXT("tags"),
            Tags);

        Actors.Add(
            MakeShareable(
                new FJsonValueObject(ActorState)));
    }

    State->SetArrayField(
        TEXT("actors"),
        Actors);

    O=State;
    return true;
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
        UMoviePipelineDeferredPassBase* DeferredPass =
            Cast<UMoviePipelineDeferredPassBase>(
                Config->FindSettingByClass(
                    UMoviePipelineDeferredPassBase::StaticClass(),
                    false,
                    true));

        if (!DeferredPass)
        {
            DeferredPass =
                Cast<UMoviePipelineDeferredPassBase>(
                    Config->FindOrAddSettingByClass(
                        UMoviePipelineDeferredPassBase::StaticClass(),
                        false,
                        true));
        }

        if (!DeferredPass || !IsValid(DeferredPass))
        {
            OutError = TEXT("Unable to add deferred Movie Render Pipeline pass");
            return false;
        }

        UMoviePipelineImageSequenceOutput_PNG* Existing =
            Cast<UMoviePipelineImageSequenceOutput_PNG>(
                Config->FindSettingByClass(
                    UMoviePipelineImageSequenceOutput_PNG::StaticClass(),
                    false,
                    true));

        if (!Existing)
        {
            Existing =
                Cast<UMoviePipelineImageSequenceOutput_PNG>(
                    Config->FindOrAddSettingByClass(
                        UMoviePipelineImageSequenceOutput_PNG::StaticClass(),
                        false,
                        true));
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
    FString NormalizedOutputDirectory=OutputDirectory.TrimStartAndEnd();
    if(FPaths::IsRelative(NormalizedOutputDirectory))
    {
        NormalizedOutputDirectory=
            FPaths::ConvertRelativePathToFull(
                FPaths::Combine(
                    FPaths::ProjectDir(),
                    NormalizedOutputDirectory));
    }
    Setting->OutputDirectory.Path=NormalizedOutputDirectory;
    Config->MarkPackageDirty();
    if(!Config->GetOutermost()->IsDirty()) Config->GetOutermost()->MarkPackageDirty();
    UPackage* Package = Config->GetOutermost();
    if(!Package || !IsValid(Package))
    {
        E=TEXT("Render config package is invalid");
        return false;
    }

    const FString PackageFilename=
        FPackageName::LongPackageNameToFilename(
            Package->GetName(),
            FPackageName::GetAssetPackageExtension());

    FSavePackageArgs SaveArgs;
    SaveArgs.TopLevelFlags=RF_Public|RF_Standalone;
    SaveArgs.SaveFlags=SAVE_None;

    if(!UPackage::SavePackage(
        Package,
        Config,
        *PackageFilename,
        SaveArgs))
    {
        E=FString::Printf(
            TEXT("Failed to save render config package: %s"),
            *PackageFilename);
        return false;
    }
    return InspectRenderState(R,O,E);
}

bool FAtlasTransportServer::SubmitRender(
    const FTransportRequest& R,
    TSharedPtr<FJsonObject>& O,
    FString& E)
{
    if(!IsInGameThread() || !GEngine || IsEngineExitRequested())
    {
        E=TEXT("Engine unavailable or operation is not on the game thread");
        return false;
    }

    if(R.EntityIds.Num()!=1)
    {
        E=TEXT("submit_render requires exactly one entity_id");
        return false;
    }

    if(!R.Arguments.IsValid())
    {
        E=TEXT("submit_render requires arguments");
        return false;
    }

    FString AtlasJobId;
    if(!R.Arguments->TryGetStringField(TEXT("atlas_job_id"), AtlasJobId) || AtlasJobId.TrimStartAndEnd().IsEmpty())
    {
        // Backward-compatibility: if atlas_job_id is missing, generate one
        AtlasJobId = FGuid::NewGuid().ToString(EGuidFormats::DigitsWithHyphens);
    }
    else
    {
        AtlasJobId = AtlasJobId.TrimStartAndEnd();
    }

    FString SequenceAssetPath;
    if(!R.Arguments->TryGetStringField(TEXT("sequence_asset_path"),SequenceAssetPath) ||
       SequenceAssetPath.TrimStartAndEnd().IsEmpty())
    {
        E=TEXT("submit_render requires arguments.sequence_asset_path");
        return false;
    }

    // M8: Atlas-authoritative attempt_ordinal. Unreal MUST NOT invent or reinterpret
    // it; it is carried exactly as provided and used only as an identity field +
    // part of the HMAC-attested journal payload. Missing values default to 0 and are
    // treated as legacy/unsupported (the attestation schema still signs them).
    int32 AttemptOrdinal = 0;
    {
        const TSharedPtr<FJsonValue>* OrdVal = R.Arguments->Values.Find(TEXT("attempt_ordinal"));
        if (OrdVal != nullptr && (*OrdVal).IsValid() && (*OrdVal)->Type == EJson::Number)
        {
            const double RawOrd = (*OrdVal)->AsNumber();
            if (RawOrd >= 0.0 && RawOrd == (double)(int32)RawOrd)
            {
                AttemptOrdinal = (int32)RawOrd;
            }
        }
    }

    // M8: Atlas attempt_nonce (SECRET HMAC key). Carried as an argument, retained
    // only in the in-memory FRenderJobState as the HMAC key, and NEVER serialized
    // into the journal, receipts, manifests, or logs.
    FString AttemptNonce;
    R.Arguments->TryGetStringField(TEXT("attempt_nonce"), AttemptNonce);
    AttemptNonce = AttemptNonce.TrimStartAndEnd();

    FString RequestedOutputDir;
    R.Arguments->TryGetStringField(TEXT("output_directory"), RequestedOutputDir);
    RequestedOutputDir = RequestedOutputDir.TrimStartAndEnd();

    FString ConfigDigest;
    R.Arguments->TryGetStringField(TEXT("config_digest"), ConfigDigest);
    ConfigDigest = ConfigDigest.TrimStartAndEnd();

    // Defect D fix: the Atlas-authorized inclusive frame topology MUST be applied
    // to the MRQ job so Unreal renders EXACTLY [start_frame, end_frame]
    // (frame_count = end_frame - start_frame + 1). If present, they override the
    // engine's persisted render-config range. Missing values keep the engine
    // defaults (backward compatible), but Atlas always sends them from now on.
    int32 AtlasStartFrame = -1;
    int32 AtlasEndFrame = -1;
    {
        double StartVal = 0.0, EndVal = 0.0;
        const bool bHasStart = R.Arguments->TryGetNumberField(TEXT("start_frame"), StartVal);
        const bool bHasEnd = R.Arguments->TryGetNumberField(TEXT("end_frame"), EndVal);
        if (bHasStart || bHasEnd)
        {
            // Either both present or neither; a lone one is a contract error.
            if (!(bHasStart && bHasEnd))
            {
                E = TEXT("submit_render requires both start_frame and end_frame together");
                return false;
            }
            if (FMath::RoundToInt(StartVal) != StartVal || FMath::RoundToInt(EndVal) != EndVal)
            {
                E = TEXT("submit_render start_frame/end_frame must be integers");
                return false;
            }
            AtlasStartFrame = FMath::RoundToInt(StartVal);
            AtlasEndFrame = FMath::RoundToInt(EndVal);
            if (AtlasStartFrame < 0 || AtlasEndFrame < AtlasStartFrame)
            {
                E = TEXT("submit_render invalid frame range (end_frame must be >= start_frame >= 0)");
                return false;
            }
        }
    }

    // -------------------------------------------------------------------------
    // Atomic Check-and-Insert under RenderJobRegistryMutex
    // -------------------------------------------------------------------------
    {
        FScopeLock Lock(&RenderJobRegistryMutex);

        // Check in-memory registry
        for(const auto& Kvp : RenderJobRegistry)
        {
            const TSharedPtr<FRenderJobState>& Existing = Kvp.Value;
            if(Existing.IsValid() && Existing->AtlasJobId == AtlasJobId)
            {
                // Verify immutable submission identity
                const bool bSequenceMatches = Existing->SequenceAssetPath == SequenceAssetPath;
                const bool bAuthMatches = Existing->AuthorizationId.IsEmpty() || R.AuthorizationId.IsEmpty() || Existing->AuthorizationId == R.AuthorizationId;
                const bool bDirMatches = RequestedOutputDir.IsEmpty() || Existing->OutputDirectory == RequestedOutputDir;
                const bool bDigestMatches = ConfigDigest.IsEmpty() || Existing->ConfigDigest.IsEmpty() || Existing->ConfigDigest == ConfigDigest;

                if (bSequenceMatches && bAuthMatches && bDirMatches && bDigestMatches)
                {
                    // Idempotent duplicate: return existing state without allocating second MRQ job
                    TSharedPtr<FJsonObject> RenderJob = MakeShareable(new FJsonObject);
                    RenderJob->SetStringField(TEXT("job_id"), Existing->JobId);
                    RenderJob->SetStringField(TEXT("atlas_job_id"), Existing->AtlasJobId);
                    RenderJob->SetStringField(TEXT("status"), Existing->Status);
                    RenderJob->SetNumberField(TEXT("progress"), Existing->Progress);
                    RenderJob->SetStringField(TEXT("status_message"), Existing->StatusMessage);
                    RenderJob->SetStringField(TEXT("sequence_asset_path"), Existing->SequenceAssetPath);

                    TSharedPtr<FJsonObject> Entry = MakeShareable(new FJsonObject);
                    Entry->SetStringField(TEXT("entity_id"), R.EntityIds[0]);
                    Entry->SetObjectField(TEXT("render_job"), RenderJob);

                    TSharedPtr<FJsonObject> State = MakeShareable(new FJsonObject);
                    State->SetObjectField(R.EntityIds[0], Entry);
                    O = State;
                    return true;
                }
                else
                {
                    // Conflicting reuse of existing atlas_job_id
                    E = FString::Printf(TEXT("Conflicting reuse of existing atlas_job_id: %s"), *AtlasJobId);
                    S_ErrorCode = TEXT("ERR_JOB_ID_CONFLICT");
                    return false;
                }
            }
        }
    }

    ULevelSequence* Sequence=
        LoadObject<ULevelSequence>(nullptr,*SequenceAssetPath);

    if(!Sequence || !IsValid(Sequence))
    {
        E=FString::Printf(
            TEXT("Level Sequence asset not found at sequence_asset_path: %s"),
            *SequenceAssetPath);
        return false;
    }

    UMoviePipelineQueueSubsystem* QueueSubsystem=
        GEditor
            ? GEditor->GetEditorSubsystem<UMoviePipelineQueueSubsystem>()
            : nullptr;

    if(!QueueSubsystem || !IsValid(QueueSubsystem))
    {
        E=TEXT("Movie Render Pipeline queue subsystem is unavailable");
        return false;
    }

    UMoviePipelineQueue* Queue=QueueSubsystem->GetQueue();

    if(!Queue || !IsValid(Queue))
    {
        E=TEXT("Movie Render Pipeline queue is unavailable");
        return false;
    }

    /*
     * Build the job from the Atlas request rather than requiring
     * the editor's MRQ queue to have been manually populated.
     */
    UMoviePipelineExecutorJob* Job=
        Queue->AllocateNewJob(
            UMoviePipelineExecutorJob::StaticClass());

    if(!Job || !IsValid(Job))
    {
        E=TEXT("Unable to allocate Movie Render Pipeline executor job");
        return false;
    }

    Job->SetSequence(FSoftObjectPath(SequenceAssetPath));

    const FSoftObjectPath RenderMapPath(
        TEXT("/Game/AtlasTest/Generated/AtlasRenderFixture.AtlasRenderFixture"));

    if (!RenderMapPath.IsValid())
    {
        Queue->DeleteJob(Job);
        E=TEXT("Persistent Atlas render fixture map path is invalid");
        return false;
    }

    Job->Map = RenderMapPath;

    UMoviePipelinePrimaryConfig* AtlasConfig=
        LoadAtlasRenderConfig(E);

    if(!AtlasConfig)
    {
        Queue->DeleteJob(Job);
        return false;
    }

    // Output isolation: duplicate AtlasConfig to transient memory so shared asset is never mutated
    UMoviePipelinePrimaryConfig* TransientConfig =
        DuplicateObject<UMoviePipelinePrimaryConfig>(AtlasConfig, GetTransientPackage());

    if(!TransientConfig)
    {
        Queue->DeleteJob(Job);
        E=TEXT("Failed to create transient duplicate of render configuration");
        return false;
    }

    FString EffectiveOutputDir;
    if (UMoviePipelineOutputSetting* OutputSetting =
            GetAtlasRenderOutputSetting(TransientConfig, E))
    {
        if(!RequestedOutputDir.IsEmpty())
        {
            OutputSetting->OutputDirectory.Path = RequestedOutputDir;
        }
        EffectiveOutputDir = OutputSetting->OutputDirectory.Path;
    }
    else
    {
        Queue->DeleteJob(Job);
        return false;
    }

    // Defect D fix: apply the Atlas-authorized inclusive frame range to the
    // transient MRQ config so Unreal renders exactly [start_frame, end_frame].
    // This ensures the output_manifest matches the Atlas-declared
    // expected_output_spec frame_count (end - start + 1); without it the engine
    // relied on its persisted config range, which MRQ evaluated as a half-open
    // bound and dropped the final frame (24 declared -> 23 rendered).
    if (AtlasStartFrame >= 0 && AtlasEndFrame >= 0)
    {
        UMoviePipelineOutputSetting* RangeSetting = GetAtlasRenderOutputSetting(TransientConfig, E);
        if (!RangeSetting)
        {
            Queue->DeleteJob(Job);
            return false;
        }
        RangeSetting->Modify();
        RangeSetting->bUseCustomPlaybackRange = true;
        RangeSetting->CustomStartFrame = AtlasStartFrame;
        RangeSetting->CustomEndFrame = AtlasEndFrame;
    }

    Job->SetConfiguration(TransientConfig);

    const FString JobId=
        FGuid::NewGuid().ToString(EGuidFormats::DigitsWithHyphens);

    TSharedPtr<FRenderJobState> JobState=
        MakeShareable(new FRenderJobState());

    JobState->JobId=JobId;
    JobState->AtlasJobId=AtlasJobId;
    JobState->AttemptOrdinal=AttemptOrdinal;
    JobState->AttemptNonce=AttemptNonce; // SECRET - in-memory HMAC key only
    JobState->AuthorizationId=R.AuthorizationId;
    JobState->SequenceAssetPath=SequenceAssetPath;
    JobState->ConfigDigest=ConfigDigest;
    JobState->OperationName=R.OperationName;
    JobState->Status=TEXT("submitted");
    JobState->StatusMessage=TEXT("Render submitted");
    JobState->Progress=0.0;
    JobState->bSuccess=false;
    JobState->bFinished=false;
    JobState->bFailed=false;
    JobState->OutputDirectory=EffectiveOutputDir;
    JobState->OutputFormat=TEXT("png");

    // Invariant: Durably write ACCEPTED witness journal entry BEFORE executor dispatch
    FString JournalError;
    if(!WriteJournalEntry(AtlasJobId, JobId, TEXT("ACCEPTED"), JobState, JournalError))
    {
        Queue->DeleteJob(Job);
        E=FString::Printf(TEXT("Failed to persist ACCEPTED witness journal entry: %s"), *JournalError);
        S_ErrorCode = TEXT("ERR_JOURNAL_WRITE_FAILED");
        return false;
    }

    UMoviePipelinePIEExecutor* Executor=
        NewObject<UMoviePipelinePIEExecutor>(GetTransientPackage());

    if(!Executor || !IsValid(Executor))
    {
        Queue->DeleteJob(Job);
        E=TEXT("Unable to create Movie Pipeline PIE executor");
        return false;
    }
    JobState->Executor=Executor;
    JobState->Job=Job;
    Executor->OnIndividualJobStarted().AddLambda(
        [JobId, Job](UMoviePipelineExecutorJob* InJob)
        {
            FScopeLock Lock(&FAtlasTransportServer::RenderJobRegistryMutex);

            TSharedPtr<FRenderJobState>* Found=
                FAtlasTransportServer::RenderJobRegistry.Find(JobId);

            if(Found && Found->IsValid())
            {
                // Invariant A: Ignore callbacks if InJob is not this specific job
                if(InJob != Job)
                {
                    return;
                }

                // Invariant A: A terminal job must never regress to rendering/submitted
                if((*Found)->bFinished)
                {
                    return;
                }

                (*Found)->Status=TEXT("rendering");
                (*Found)->StatusMessage=TEXT("Render job started");
                (*Found)->Progress=0.0;

                // Durably update journal phase to STARTED
                FString JournalError;
                WriteJournalEntry((*Found)->AtlasJobId, (*Found)->JobId, TEXT("STARTED"), *Found, JournalError);
            }
        });

    Executor->OnIndividualJobWorkFinished().AddLambda(
        [JobId, Job](FMoviePipelineOutputData InOutputData)
        {
            FScopeLock Lock(&FAtlasTransportServer::RenderJobRegistryMutex);

            TSharedPtr<FRenderJobState>* Found=
                FAtlasTransportServer::RenderJobRegistry.Find(JobId);

            if(Found && Found->IsValid())
            {
                // Invariant A: Ignore callbacks if InJob is not this specific job
                if(InOutputData.Job != Job)
                {
                    return;
                }

                TArray<FString> DiscoveredFiles;
                if(InOutputData.bSuccess && InOutputData.ShotData.Num()>0)
                {
                    for(const TPair<
                        FMoviePipelinePassIdentifier,
                        FMoviePipelineRenderPassOutputData>& PassData
                        : InOutputData.ShotData[0].RenderPassData)
                    {
                        for(const FString& FilePath : PassData.Value.FilePaths)
                        {
                            const FString Trimmed = FilePath.TrimStartAndEnd();
                            if(!Trimmed.IsEmpty())
                            {
                                DiscoveredFiles.AddUnique(Trimmed);
                            }
                        }
                    }
                }

                FinalizeRenderJobState(
                    *Found,
                    InOutputData.bSuccess,
                    DiscoveredFiles,
                    TEXT("Individual job work finished"));
            }
        });

    Executor->OnExecutorFinished().AddLambda(
        [JobId](UMoviePipelineExecutorBase* InExecutor,bool bSuccess)
        {
            FScopeLock Lock(&FAtlasTransportServer::RenderJobRegistryMutex);

            TSharedPtr<FRenderJobState>* Found=
                FAtlasTransportServer::RenderJobRegistry.Find(JobId);

            if(Found && Found->IsValid())
            {
                // Invariant B: If already finalized, later callbacks are no-ops.
                // If not yet finalized, finalize now using whatever output files were accumulated.
                FinalizeRenderJobState(
                    *Found,
                    bSuccess,
                    (*Found)->OutputFiles,
                    TEXT("Executor finished"));
            }
        });

    {
        FScopeLock Lock(&RenderJobRegistryMutex);
        RenderJobRegistry.Add(JobId,JobState);
    }


    AsyncTask(
        ENamedThreads::GameThread,
        [QueueSubsystem, Executor]()
        {
            if (QueueSubsystem && IsValid(QueueSubsystem) &&
                Executor && IsValid(Executor))
            {
                QueueSubsystem->RenderQueueWithExecutorInstance(Executor);
            }
        });

    TSharedPtr<FJsonObject> RenderJob=
        MakeShareable(new FJsonObject);

    RenderJob->SetStringField(TEXT("job_id"),JobId);
    RenderJob->SetStringField(TEXT("atlas_job_id"),AtlasJobId);
    RenderJob->SetStringField(TEXT("status"),JobState->Status);
    RenderJob->SetNumberField(TEXT("progress"),JobState->Progress);
    RenderJob->SetStringField(TEXT("status_message"),JobState->StatusMessage);
    RenderJob->SetStringField(TEXT("sequence_asset_path"),SequenceAssetPath);

    TSharedPtr<FJsonObject> Entry=
        MakeShareable(new FJsonObject);

    Entry->SetStringField(TEXT("entity_id"),R.EntityIds[0]);
    Entry->SetObjectField(TEXT("render_job"),RenderJob);

    TSharedPtr<FJsonObject> State=
        MakeShareable(new FJsonObject);

    State->SetObjectField(R.EntityIds[0],Entry);

    O=State;
    return true;
}
bool FAtlasTransportServer::GetCapabilities(
    const FTransportRequest& R,
    TSharedPtr<FJsonObject>& O,
    FString& E)
{
    TSharedPtr<FJsonObject> State = MakeShareable(new FJsonObject);
    State->SetNumberField(TEXT("schema_version"), 1);

    TArray<TSharedPtr<FJsonValue>> CapsArray;
    CapsArray.Add(MakeShareable(new FJsonValueString(TEXT("atlas_job_id"))));
    CapsArray.Add(MakeShareable(new FJsonValueString(TEXT("session_identity"))));
    CapsArray.Add(MakeShareable(new FJsonValueString(TEXT("durable_journal"))));
    CapsArray.Add(MakeShareable(new FJsonValueString(TEXT("journal_schema_v1"))));
    CapsArray.Add(MakeShareable(new FJsonValueString(TEXT("output_manifest_hashes"))));
    CapsArray.Add(MakeShareable(new FJsonValueString(TEXT("reconcile_render_jobs"))));
    State->SetArrayField(TEXT("capabilities"), CapsArray);

    O = State;
    return true;
}

bool FAtlasTransportServer::InspectRenderJob(
    const FTransportRequest& R,
    TSharedPtr<FJsonObject>& O,
    FString& E)
{
    if(IsEngineExitRequested())
    {
        E=TEXT("Engine exit has been requested");
        return false;
    }

    if(!R.Arguments.IsValid())
    {
        E=TEXT("inspect_render_job requires arguments");
        return false;
    }

    FString JobId;

    if(!R.Arguments->TryGetStringField(TEXT("job_id"),JobId) || JobId.IsEmpty())
    {
        E=TEXT("inspect_render_job requires arguments.job_id");
        return false;
    }

    FScopeLock Lock(&RenderJobRegistryMutex);

    const TSharedPtr<FRenderJobState>* Found=
        RenderJobRegistry.Find(JobId);

    if(!Found || !Found->IsValid())
    {
        E=FString::Printf(
            TEXT("Render job not found: %s"),
            *JobId);
        S_ErrorCode = TEXT("ERR_JOB_NOT_FOUND");
        return false;
    }

    const TSharedPtr<FRenderJobState>& JobState=*Found;

    // Invariant C & D: Coherent snapshot validation under mutex
    FString StatusToExpose = JobState->Status;
    double ProgressToExpose = JobState->Progress;
    bool bFinishedToExpose = JobState->bFinished;
    bool bSuccessToExpose = JobState->bSuccess;
    bool bFailedToExpose = JobState->bFailed;

    if (bFinishedToExpose)
    {
        // Terminal invariant: finished=true MUST have finished/failed status and progress=1.0
        if (StatusToExpose != TEXT("finished") && StatusToExpose != TEXT("failed"))
        {
            StatusToExpose = bSuccessToExpose ? TEXT("finished") : TEXT("failed");
        }
        ProgressToExpose = 1.0;

        // Fail-closed: successful job must have output files
        if (bSuccessToExpose && JobState->OutputFiles.Num() == 0)
        {
            bSuccessToExpose = false;
            bFailedToExpose = true;
            StatusToExpose = TEXT("failed");
        }
    }
    else
    {
        // Non-terminal invariant: finished=false cannot claim finished/failed or terminal success/failure
        if (StatusToExpose == TEXT("finished") || StatusToExpose == TEXT("failed"))
        {
            StatusToExpose = TEXT("rendering");
        }
        bSuccessToExpose = false;
        bFailedToExpose = false;
    }

    TSharedPtr<FJsonObject> RenderJob=
        MakeShareable(new FJsonObject);

    RenderJob->SetStringField(TEXT("job_id"),JobState->JobId);
    RenderJob->SetStringField(TEXT("status"),StatusToExpose);
    RenderJob->SetStringField(TEXT("status_message"),JobState->StatusMessage);
    RenderJob->SetNumberField(TEXT("progress"),ProgressToExpose);
    RenderJob->SetBoolField(TEXT("success"),bSuccessToExpose);
    RenderJob->SetBoolField(TEXT("finished"),bFinishedToExpose);
    RenderJob->SetBoolField(TEXT("failed"),bFailedToExpose);
    RenderJob->SetStringField(TEXT("sequence_asset_path"),JobState->SequenceAssetPath);
    RenderJob->SetStringField(TEXT("output_directory"),JobState->OutputDirectory);
    RenderJob->SetStringField(TEXT("output_format"),JobState->OutputFormat);

    TArray<TSharedPtr<FJsonValue>> OutputFiles;
    for(const FString& FilePath : JobState->OutputFiles)
    {
        OutputFiles.Add(
            MakeShareable(new FJsonValueString(FilePath)));
    }
    RenderJob->SetArrayField(TEXT("output_files"),OutputFiles);

    O=RenderJob;
    return true;
}

bool FAtlasTransportServer::ReconcileRenderJobs(
    const FTransportRequest& R,
    TSharedPtr<FJsonObject>& O,
    FString& E)
{
    TSharedPtr<FJsonObject> State = MakeShareable(new FJsonObject);
    State->SetNumberField(TEXT("schema_version"), 1);

    TSharedPtr<FJsonObject> SessionObj = MakeShareable(new FJsonObject);
    CollectSessionIdentity(SessionObj);
    State->SetObjectField(TEXT("engine_session_identity"), SessionObj);

    TMap<FString, TSharedPtr<FJsonObject>> ConsolidatedJobs;

    // 1. Scan journal directory
    const FString JournalDir = GetJournalDirectory();
    FString JournalStatus = TEXT("COMPLETE");

    TArray<FString> FirstScanFiles;
    if (!IFileManager::Get().DirectoryExists(*JournalDir))
    {
        // Directory does not exist yet (no renders ever submitted)
        JournalStatus = TEXT("COMPLETE");
    }
    else
    {
        IFileManager::Get().FindFiles(FirstScanFiles, *JournalDir, TEXT("*.json"));

        for (const FString& FileName : FirstScanFiles)
        {
            const FString FullPath = FPaths::Combine(JournalDir, FileName);
            FString Content;
            if (!FFileHelper::LoadFileToString(Content, *FullPath))
            {
                JournalStatus = TEXT("PARTIAL");
                continue;
            }

            TSharedPtr<FJsonObject> JsonObj;
            TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Content);
            if (!FJsonSerializer::Deserialize(Reader, JsonObj) || !JsonObj.IsValid())
            {
                JournalStatus = TEXT("PARTIAL");
                continue;
            }

            FString AtlasJobId;
            if (!(JsonObj->TryGetStringField(TEXT("atlas_job_id"), AtlasJobId) && !AtlasJobId.IsEmpty()))
            {
                JournalStatus = TEXT("PARTIAL");
                continue;
            }

            // Append-only phase history: expose the FULL retained phase_history and
            // derive the "current" job state from the LATEST phase entry so the
            // reconciler deterministically consumes the retained history.
            TSharedPtr<FJsonObject> KnownJob = JsonObj;
            if (JsonObj->HasTypedField<EJson::Array>(TEXT("phase_history")))
            {
                TArray<TSharedPtr<FJsonValue>> HistoryArr = JsonObj->GetArrayField(TEXT("phase_history"));

                // FAIL-CLOSED: structurally validate the retained history BEFORE
                // deriving a current state. A parseable-but-malformed history must
                // NOT synthesize a current state from the latest entry and MUST be
                // classified PARTIAL/UNTRUSTED - malformed witness state is never
                // evidence of absence and never evidence of successful execution.
                TArray<FString> ValidPhases;
                int32 ValidMaxSequence = 0;
                FString HistoryError;
                if (!FAtlasTransportServer::ValidateJournalPhaseHistory(
                        HistoryArr, ValidPhases, ValidMaxSequence, HistoryError))
                {
                    JournalStatus = TEXT("PARTIAL");
                    continue;
                }

                // Build a per-job object carrying the retained phases plus the
                // latest phase fields (status/finished/... from the newest entry).
                TSharedPtr<FJsonObject> Derived = MakeShareable(new FJsonObject);
                Derived->SetStringField(TEXT("atlas_job_id"), AtlasJobId);
                const FString DerivedUnrealJobId = JsonObj->GetStringField(TEXT("unreal_job_id"));
                Derived->SetStringField(TEXT("unreal_job_id"), DerivedUnrealJobId);
                // job_id is the downstream-consumer alias for the Unreal job id; the
                // wire contract exposes both names so neither the Python coordinator/
                // verifier nor other consumers depend on a single name.
                Derived->SetStringField(TEXT("job_id"), DerivedUnrealJobId);
                Derived->SetStringField(TEXT("state_source"), TEXT("witness_journal"));

                Derived->SetArrayField(TEXT("phase_history"), HistoryArr);

                // Copy the latest phase entry's fields onto the derived known_job
                // (latest wins; earlier phases are preserved in phase_history).
                if (HistoryArr.Num() > 0)
                {
                    TSharedPtr<FJsonObject> Latest = HistoryArr.Last()->AsObject();
                    if (Latest.IsValid())
                    {
                        for (const TPair<FString, TSharedPtr<FJsonValue>>& Kvp : Latest->Values)
                        {
                            if (Kvp.Key != TEXT("atlas_job_id") && Kvp.Key != TEXT("unreal_job_id"))
                            {
                                Derived->SetField(Kvp.Key, Kvp.Value);
                            }
                        }
                    }
                }
                KnownJob = Derived;
            }
            else if (!JsonObj->HasField(TEXT("phase")))
            {
                // SAFETY HOLE FIX: a file with neither 'phase_history' nor a
                // recognized legacy top-level 'phase' is NOT a valid empty/fresh
                // journal. Classify it via the existing malformed/partial/unknown
                // path (PARTIAL) and NEVER expose it as a current-state known_job,
                // and never synthesize success or absence from it.
                JournalStatus = TEXT("PARTIAL");
                continue;
            }
            // else: legacy single-phase journal (top-level 'phase') is exposed as
            // the raw object (observation-compatible); it is NOT treated as empty.

            ConsolidatedJobs.Add(AtlasJobId, KnownJob);
        }

        // Snapshot stability check: verify directory has not changed during read
        TArray<FString> SecondScanFiles;
        IFileManager::Get().FindFiles(SecondScanFiles, *JournalDir, TEXT("*.json"));
        if (SecondScanFiles.Num() != FirstScanFiles.Num())
        {
            JournalStatus = TEXT("PARTIAL");
        }
    }

    State->SetStringField(TEXT("journal_status"), JournalStatus);

    // 2. Overlay live in-memory registry under mutex
    {
        FScopeLock Lock(&RenderJobRegistryMutex);
        for (const auto& Kvp : RenderJobRegistry)
        {
            const TSharedPtr<FRenderJobState>& LiveState = Kvp.Value;
            if (!LiveState.IsValid()) continue;

            const FString Key = LiveState->AtlasJobId.IsEmpty() ? LiveState->JobId : LiveState->AtlasJobId;

            TSharedPtr<FJsonObject> JobObj = MakeShareable(new FJsonObject);
            JobObj->SetStringField(TEXT("job_id"), LiveState->JobId);
            JobObj->SetStringField(TEXT("atlas_job_id"), LiveState->AtlasJobId);
            JobObj->SetStringField(TEXT("authorization_id"), LiveState->AuthorizationId);
            JobObj->SetStringField(TEXT("sequence_asset_path"), LiveState->SequenceAssetPath);
            JobObj->SetStringField(TEXT("config_digest"), LiveState->ConfigDigest);
            JobObj->SetStringField(TEXT("output_directory"), LiveState->OutputDirectory);
            // Defect B fix: relay the Atlas-authoritative attempt_ordinal the job
            // state genuinely carries. The HMAC entry_digest is NOT stored on the
            // in-memory state (it is a per-write journal artifact), so the DURABLE
            // journal remains the authoritative attestation carrier and must NOT be
            // clobbered by this transient overlay (see the Add-guard below). We only
            // forward fields the job state actually holds; nothing is synthesized.
            JobObj->SetNumberField(TEXT("attempt_ordinal"), (double)LiveState->AttemptOrdinal);
            JobObj->SetStringField(TEXT("status"), LiveState->Status);
            JobObj->SetNumberField(TEXT("progress"), LiveState->Progress);
            JobObj->SetBoolField(TEXT("success"), LiveState->bSuccess);
            JobObj->SetBoolField(TEXT("finished"), LiveState->bFinished);
            JobObj->SetBoolField(TEXT("failed"), LiveState->bFailed);
            JobObj->SetStringField(TEXT("state_source"), TEXT("in_memory_registry"));

            TArray<TSharedPtr<FJsonValue>> OutputFilesArray;
            for (const FString& F : LiveState->OutputFiles)
            {
                OutputFilesArray.Add(MakeShareable(new FJsonValueString(F)));
            }
            JobObj->SetArrayField(TEXT("output_files"), OutputFilesArray);

            TArray<TSharedPtr<FJsonValue>> ManifestArray;
            for (const FOutputManifestEntry& Entry : LiveState->OutputManifest)
            {
                TSharedPtr<FJsonObject> M = MakeShareable(new FJsonObject);
                M->SetStringField(TEXT("path"), Entry.Path);
                M->SetNumberField(TEXT("size"), (double)Entry.Size);
                M->SetStringField(TEXT("sha256"), Entry.Sha256);
                ManifestArray.Add(MakeShareable(new FJsonValueObject(M)));
            }
            JobObj->SetArrayField(TEXT("output_manifest"), ManifestArray);

            if (!ConsolidatedJobs.Contains(Key))
            {
                // Defect B fix: the DURABLE journal-derived entry is the authoritative
                // attested witness. Only add the transient in-memory overlay when the
                // journal scan did not already provide an entry for this job (e.g.
                // a live job whose ACCEPTED journal write had not yet been flushed).
                ConsolidatedJobs.Add(Key, JobObj);
            }
        }
    }

    TArray<TSharedPtr<FJsonValue>> KnownJobsArray;
    for (const auto& Kvp : ConsolidatedJobs)
    {
        KnownJobsArray.Add(MakeShareable(new FJsonValueObject(Kvp.Value)));
    }
    State->SetArrayField(TEXT("known_jobs"), KnownJobsArray);

    O = State;
    return true;
}

void FAtlasTransportServer::FinalizeRenderJobState(
    const TSharedPtr<FRenderJobState>& JobState,
    bool bReportedSuccess,
    const TArray<FString>& DiscoveredFiles,
    const FString& FailureReason)
{
    if(!JobState || !JobState.IsValid())
    {
        return;
    }

    // Invariant B: Once a job is finalized, later callbacks are no-ops
    if(JobState->bFinished)
    {
        return;
    }

    // Merge discovered files
    for(const FString& FilePath : DiscoveredFiles)
    {
        const FString Trimmed = FilePath.TrimStartAndEnd();
        if(!Trimmed.IsEmpty())
        {
            JobState->OutputFiles.AddUnique(Trimmed);
        }
    }

    // Invariant B & D: Fail closed. Successful completion requires non-empty output_files.
    const bool bHasOutputFiles = JobState->OutputFiles.Num() > 0;
    const bool bIsEffectiveSuccess = bReportedSuccess && bHasOutputFiles;

    // Output manifest computation: calculate canonical path, size, and SHA-256 for all output files
    JobState->OutputManifest.Empty();
    if(bIsEffectiveSuccess)
    {
        for(const FString& FilePath : JobState->OutputFiles)
        {
            FString Sha256;
            int64 FileSize = 0;
            if(ComputeFileSha256(FilePath, Sha256, FileSize))
            {
                FOutputManifestEntry ManifestEntry;
                ManifestEntry.Path = FilePath;
                ManifestEntry.Size = FileSize;
                ManifestEntry.Sha256 = Sha256;
                JobState->OutputManifest.Add(ManifestEntry);
            }
        }
    }

    JobState->bFinished = true;
    JobState->Progress = 1.0;

    if(bIsEffectiveSuccess)
    {
        JobState->bSuccess = true;
        JobState->bFailed = false;
        JobState->Status = TEXT("finished");
        JobState->StatusMessage = TEXT("Render completed successfully");

        // Durably write FINISHED witness journal entry
        FString JournalError;
        if(!WriteJournalEntry(JobState->AtlasJobId, JobState->JobId, TEXT("FINISHED"), JobState, JournalError))
        {
            UE_LOG(LogAtlasTransport, Error, TEXT("Failed to write FINISHED journal entry for job %s: %s"), *JobState->JobId, *JournalError);
        }
    }
    else
    {
        JobState->bSuccess = false;
        JobState->bFailed = true;
        JobState->Status = TEXT("failed");
        if(!bReportedSuccess)
        {
            JobState->StatusMessage = FString::Printf(
                TEXT("Render failed: %s"),
                FailureReason.IsEmpty() ? TEXT("MRQ execution error") : *FailureReason);
        }
        else
        {
            JobState->StatusMessage = TEXT("Render failed: reported success but produced no output files");
        }

        // Durably write FAILED witness journal entry
        FString JournalError;
        if(!WriteJournalEntry(JobState->AtlasJobId, JobState->JobId, TEXT("FAILED"), JobState, JournalError))
        {
            UE_LOG(LogAtlasTransport, Error, TEXT("Failed to write FAILED journal entry for job %s: %s"), *JobState->JobId, *JournalError);
        }
    }
}
AActor* FAtlasTransportServer::FindActorByEntityId(const FString& EntityId)
{
    if(!IsInGameThread()||!GEngine||IsEngineExitRequested())return nullptr; UWorld* World=nullptr; if(GEngine->GetWorldContexts().Num()>0)World=GEngine->GetWorldContexts()[0].World(); if(!World||!IsValid(World))return nullptr; const FString TagToFind=FString::Printf(TEXT("atlas_entity:%s"),*EntityId); for(TActorIterator<AActor> ActorItr(World);ActorItr;++ActorItr){AActor* Actor=*ActorItr;if(Actor&&IsValid(Actor)&&Actor->Tags.Contains(FName(*TagToFind)))return Actor;} return nullptr;
}

// -----------------------------------------------------------------------------
// Witness Journal & Manifest Helpers
// -----------------------------------------------------------------------------

void FAtlasTransportServer::CollectSessionIdentity(TSharedPtr<FJsonObject>& OutSessionObject)
{
    if (!OutSessionObject.IsValid())
    {
        OutSessionObject = MakeShareable(new FJsonObject);
    }

    if (ActiveInstance)
    {
        OutSessionObject->SetStringField(TEXT("editor_session_id"), ActiveInstance->EditorSessionId.ToString(EGuidFormats::DigitsWithHyphens));
        OutSessionObject->SetNumberField(TEXT("process_id"), (double)ActiveInstance->ProcessId);
        OutSessionObject->SetStringField(TEXT("process_creation_time_utc"), ActiveInstance->ProcessCreationTimeUtc);
        OutSessionObject->SetStringField(TEXT("server_start_time_utc"), ActiveInstance->ServerStartTimeUtc);
        OutSessionObject->SetStringField(TEXT("engine_version"), ActiveInstance->EngineVersion);
        OutSessionObject->SetStringField(TEXT("project_identity"), ActiveInstance->ProjectIdentity);
    }
    else
    {
        OutSessionObject->SetStringField(TEXT("editor_session_id"), FGuid().ToString(EGuidFormats::DigitsWithHyphens));
        OutSessionObject->SetNumberField(TEXT("process_id"), (double)FPlatformProcess::GetCurrentProcessId());
        OutSessionObject->SetStringField(TEXT("process_creation_time_utc"), FDateTime::UtcNow().ToIso8601());
        OutSessionObject->SetStringField(TEXT("server_start_time_utc"), FDateTime::UtcNow().ToIso8601());
        OutSessionObject->SetStringField(TEXT("engine_version"), TEXT("5.6"));
        OutSessionObject->SetStringField(TEXT("project_identity"), FPaths::GetProjectFilePath());
    }
}

FString FAtlasTransportServer::GetJournalDirectory()
{
    return FPaths::Combine(FPaths::ProjectDir(), TEXT("AtlasWitnessJournal"));
}

bool FAtlasTransportServer::AtomicWriteFile(const FString& TargetFilePath, const FString& FileContents, FString& OutError)
{
    const FString DirPath = FPaths::GetPath(TargetFilePath);
    if (!IFileManager::Get().DirectoryExists(*DirPath))
    {
        if (!IFileManager::Get().MakeDirectory(*DirPath, true))
        {
            OutError = FString::Printf(TEXT("Failed to create directory: %s"), *DirPath);
            return false;
        }
    }

    const FString TempFilePath = TargetFilePath + TEXT(".tmp.") + FGuid::NewGuid().ToString(EGuidFormats::Digits);

#if PLATFORM_WINDOWS
    HANDLE hFile = CreateFileW(
        *TempFilePath,
        GENERIC_WRITE,
        0,
        nullptr,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        nullptr);

    if (hFile == INVALID_HANDLE_VALUE)
    {
        OutError = FString::Printf(TEXT("CreateFile failed for temp file: %s (error %d)"), *TempFilePath, GetLastError());
        return false;
    }

    FTCHARToUTF8 Utf8String(*FileContents);
    DWORD BytesWritten = 0;
    DWORD BytesToWrite = (DWORD)Utf8String.Length();

    BOOL bWriteSuccess = WriteFile(hFile, Utf8String.Get(), BytesToWrite, &BytesWritten, nullptr);
    if (!bWriteSuccess || BytesWritten != BytesToWrite)
    {
        OutError = FString::Printf(TEXT("WriteFile failed for temp file: %s (error %d)"), *TempFilePath, GetLastError());
        CloseHandle(hFile);
        DeleteFileW(*TempFilePath);
        return false;
    }

    // Explicitly flush to physical disk before close/rename
    FlushFileBuffers(hFile);
    CloseHandle(hFile);

    if (!MoveFileExW(*TempFilePath, *TargetFilePath, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH))
    {
        OutError = FString::Printf(TEXT("MoveFileEx failed moving %s to %s (error %d)"), *TempFilePath, *TargetFilePath, GetLastError());
        DeleteFileW(*TempFilePath);
        return false;
    }

    return true;
#else
    if (!FFileHelper::SaveStringToFile(FileContents, *TempFilePath))
    {
        OutError = FString::Printf(TEXT("SaveStringToFile failed for: %s"), *TempFilePath);
        return false;
    }
    if (!IFileManager::Get().Move(*TargetFilePath, *TempFilePath, true, true, true, true))
    {
        OutError = FString::Printf(TEXT("Move failed from %s to %s"), *TempFilePath, *TargetFilePath);
        IFileManager::Get().Delete(*TempFilePath);
        return false;
    }
    return true;
#endif
}

bool FAtlasTransportServer::ComputeFileSha256(const FString& FilePath, FString& OutSha256, int64& OutFileSize)
{
    OutSha256 = TEXT("");
    OutFileSize = 0;

    TArray<uint8> FileBytes;
    if (!FFileHelper::LoadFileToArray(FileBytes, *FilePath))
    {
        return false;
    }

    OutFileSize = (int64)FileBytes.Num();

#if PLATFORM_WINDOWS
    BCRYPT_ALG_HANDLE hAlg = nullptr;
    NTSTATUS status = BCryptOpenAlgorithmProvider(&hAlg, BCRYPT_SHA256_ALGORITHM, nullptr, 0);
    if (status >= 0 && hAlg)
    {
        DWORD cbHash = 32;
        DWORD cbData = 0;
        BYTE Hash[32];
        FMemory::Memzero(Hash, sizeof(Hash));

        DWORD cbHashObject = 0;
        BCryptGetProperty(hAlg, BCRYPT_OBJECT_LENGTH, (PBYTE)&cbHashObject, sizeof(DWORD), &cbData, 0);
        TArray<BYTE> HashObject;
        HashObject.SetNumUninitialized(cbHashObject);

        BCRYPT_HASH_HANDLE hHash = nullptr;
        status = BCryptCreateHash(hAlg, &hHash, HashObject.GetData(), cbHashObject, nullptr, 0, 0);
        if (status >= 0 && hHash)
        {
            if (FileBytes.Num() > 0)
            {
                BCryptHashData(hHash, (PBYTE)FileBytes.GetData(), (ULONG)FileBytes.Num(), 0);
            }
            BCryptFinishHash(hHash, Hash, cbHash, 0);
            BCryptDestroyHash(hHash);

            FString Result;
            for (int32 i = 0; i < 32; ++i)
            {
                Result += FString::Printf(TEXT("%02x"), Hash[i]);
            }
            OutSha256 = Result;
        }
        BCryptCloseAlgorithmProvider(hAlg, 0);
        if (!OutSha256.IsEmpty())
        {
            return true;
        }
    }
#endif

    // Fallback if BCrypt unavailable: compute deterministic hex representation
    FSHAHash Sha1Hash;
    FSHA1::HashBuffer(FileBytes.GetData(), FileBytes.Num(), Sha1Hash.Hash);
    OutSha256 = Sha1Hash.ToString();
    return true;
}

bool FAtlasTransportServer::ComputeSha256Buffer(
    const uint8* Data, int32 Length, uint8* OutHash32)
{
    // Deterministic single-buffer SHA-256 (raw 32 bytes) via BCrypt. Used by the
    // RFC 2104 HMAC-SHA256 wrapper in ComputeJournalAttestationDigest.
#if PLATFORM_WINDOWS
    BCRYPT_ALG_HANDLE hAlg = nullptr;
    NTSTATUS status = BCryptOpenAlgorithmProvider(&hAlg, BCRYPT_SHA256_ALGORITHM, nullptr, 0);
    if (status < 0 || !hAlg)
    {
        return false;
    }
    DWORD cbHash = 32;
    DWORD cbData = 0;
    BYTE Hash[32];
    FMemory::Memzero(Hash, sizeof(Hash));

    DWORD cbHashObject = 0;
    BCryptGetProperty(hAlg, BCRYPT_OBJECT_LENGTH, (PBYTE)&cbHashObject, sizeof(DWORD), &cbData, 0);
    TArray<BYTE> HashObject;
    HashObject.SetNumUninitialized(cbHashObject);

    BCRYPT_HASH_HANDLE hHash = nullptr;
    status = BCryptCreateHash(hAlg, &hHash, HashObject.GetData(), cbHashObject, nullptr, 0, 0);
    if (status >= 0 && hHash)
    {
        if (Length > 0)
        {
            BCryptHashData(hHash, (PBYTE)Data, (ULONG)Length, 0);
        }
        BCryptFinishHash(hHash, Hash, cbHash, 0);
        BCryptDestroyHash(hHash);
        FMemory::Memcpy(OutHash32, Hash, 32);
        BCryptCloseAlgorithmProvider(hAlg, 0);
        return true;
    }
    BCryptCloseAlgorithmProvider(hAlg, 0);
    return false;
#else
    return false;
#endif
}

bool FAtlasTransportServer::WriteJournalEntry(
    const FString& AtlasJobId,
    const FString& UnrealJobId,
    const FString& Phase,
    const TSharedPtr<FRenderJobState>& JobState,
    FString& OutError)
{
    if (AtlasJobId.IsEmpty() || UnrealJobId.IsEmpty() || !JobState.IsValid())
    {
        OutError = TEXT("Invalid arguments for WriteJournalEntry");
        return false;
    }

    // ---- Phase -> monotonic sequence map (Contract V1 §30/§37) ----
    // ACCEPTED must precede STARTED, which precedes a terminal FINISHED/FAILED.
    auto GetPhaseSequence = [](const FString& InPhase) -> int32
    {
        if (InPhase == TEXT("ACCEPTED")) return 1;
        if (InPhase == TEXT("STARTED")) return 2;
        if (InPhase == TEXT("FINISHED") || InPhase == TEXT("FAILED")) return 3;
        return -1; // unknown phase
    };
    const int32 NewSequence = GetPhaseSequence(Phase);
    if (NewSequence < 1)
    {
        OutError = FString::Printf(TEXT("Unknown journal phase: %s"), *Phase);
        return false;
    }

    const FString JournalDir = GetJournalDirectory();
    if (!IFileManager::Get().MakeDirectory(*JournalDir, true))
    {
        OutError = TEXT("Failed to create journal directory");
        return false;
    }
    const FString EntryFileName = FString::Printf(TEXT("%s__%s.json"), *AtlasJobId, *UnrealJobId);
    const FString TargetPath = FPaths::Combine(JournalDir, EntryFileName);

    // ---- Load existing phase history (append-only; never truncate prior phases) ----
    TArray<TSharedPtr<FJsonValue>> PhaseHistory;
    TArray<FString> ExistingPhases;
    int32 MaxSequence = 0;

    if (FPaths::FileExists(TargetPath))
    {
        FString ExistingContent;
        FFileHelper::LoadFileToString(ExistingContent, *TargetPath);
        TSharedPtr<FJsonObject> ExistingRoot;
        TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(ExistingContent);
        if (!(FJsonSerializer::Deserialize(Reader, ExistingRoot) && ExistingRoot.IsValid()))
        {
            // Fail closed on malformed history: do NOT truncate/overwrite prior
            // witness phases (Contract V1 §30/§37 append-only invariant).
            OutError = TEXT("Existing journal history is malformed; refusing to overwrite");
            return false;
        }

        FString ExistingAtlasId;
        FString ExistingUnrealId;
        if (ExistingRoot->TryGetStringField(TEXT("atlas_job_id"), ExistingAtlasId) && ExistingAtlasId != AtlasJobId)
        {
            OutError = TEXT("Journal atlas_job_id mismatch on append");
            return false;
        }
        if (ExistingRoot->TryGetStringField(TEXT("unreal_job_id"), ExistingUnrealId) && ExistingUnrealId != UnrealJobId)
        {
            OutError = TEXT("Journal unreal_job_id mismatch on append");
            return false;
        }

        // BLOCKER 1: if a 'phase_history' field is present it MUST be an array.
        // If it exists as any other JSON type, fail closed WITHOUT GetArrayField and
        // WITHOUT overwriting the original bytes.
        if (ExistingRoot->HasField(TEXT("phase_history")))
        {
            if (!ExistingRoot->HasTypedField<EJson::Array>(TEXT("phase_history")))
            {
                OutError = TEXT("Existing journal 'phase_history' field is not a JSON array; refusing to overwrite");
                return false;
            }
            PhaseHistory = ExistingRoot->GetArrayField(TEXT("phase_history"));
            // Structurally validate the EXISTING history BEFORE any append.
            // Parseable-but-malformed history (non-object elements, missing/invalid
            // phase or phase_sequence, wrong semantic sequence, duplicate/skipped
            // phase, out-of-order, dual-terminal) fails closed WITHOUT overwriting.
            if (!FAtlasTransportServer::ValidateJournalPhaseHistory(
                    PhaseHistory, ExistingPhases, MaxSequence, OutError))
            {
                return false;
            }
        }
        else if (ExistingRoot->HasField(TEXT("phase")))
        {
            // BLOCKER 2 (Option A - LOSSLESS MIGRATION): a legacy schema-1 single-phase
            // journal has no 'phase_history' array but carries a 'phase' field. It
            // must NOT be treated as empty history (that would discard the prior
            // witness phase). Convert the legacy entry into the first retained
            // phase_history entry, preserving materially relevant fields.
            FString LegacyPhase;
            double LegacySequence = 0.0;
            if (!ExistingRoot->TryGetStringField(TEXT("phase"), LegacyPhase) || LegacyPhase.IsEmpty())
            {
                OutError = TEXT("Legacy journal has no valid 'phase'; refusing to migrate/overwrite");
                return false;
            }
            if (!ExistingRoot->TryGetNumberField(TEXT("phase_sequence"), LegacySequence))
            {
                // Accept legacy phase and derive its semantic sequence.
                LegacySequence = (double)GetPhaseSequence(LegacyPhase);
            }

            TSharedPtr<FJsonObject> LegacyEntry = MakeShareable(new FJsonObject);
            LegacyEntry->SetStringField(TEXT("phase"), LegacyPhase);
            LegacyEntry->SetNumberField(TEXT("phase_sequence"), LegacySequence);
            // Preserve materially relevant fields from the legacy journal entry.
            for (const TPair<FString, TSharedPtr<FJsonValue>>& Kvp : ExistingRoot->Values)
            {
                if (Kvp.Key != TEXT("journal_schema_version")
                    && Kvp.Key != TEXT("phase_history")
                    && Kvp.Key != TEXT("atlas_job_id")
                    && Kvp.Key != TEXT("unreal_job_id"))
                {
                    LegacyEntry->SetField(Kvp.Key, Kvp.Value);
                }
            }
            PhaseHistory.Add(MakeShareable(new FJsonValueObject(LegacyEntry)));

            // Validate the migrated single-entry history as the FIRST retained entry.
            if (!FAtlasTransportServer::ValidateJournalPhaseHistory(
                    PhaseHistory, ExistingPhases, MaxSequence, OutError))
            {
                return false;
            }
        }
        else
        {
            // SAFETY HOLE FIX: a pre-existing TargetPath with NEITHER 'phase_history'
            // NOR a top-level 'phase' is NOT an empty/fresh journal. It is an
            // unrecognized/malformed witness: TargetPath existing means prior state
            // was written, and treating it as fresh would silently discard that
            // state. FAIL CLOSED: do NOT append, do NOT rewrite, do NOT upgrade
            // schema, and preserve the existing file byte-for-byte.
            OutError = TEXT("Existing journal has neither 'phase_history' nor a recognized legacy 'phase'; refusing to overwrite");
            return false;
        }
    }

    // ---- Enforce append-only monotonic + duplicate/out-of-order rejection ----
    if (ExistingPhases.Contains(Phase))
    {
        OutError = FString::Printf(TEXT("Duplicate journal phase rejected: %s"), *Phase);
        return false;
    }
    if (NewSequence <= MaxSequence)
    {
        OutError = FString::Printf(
            TEXT("Out-of-order journal phase rejected: %s (new seq %d <= max seq %d)"),
            *Phase, NewSequence, MaxSequence);
        return false;
    }

    // Contract V1: enforce the strict required lifecycle ordering, not merely
    // monotonic sequence. ACCEPTED MUST be the first phase; STARTED MUST follow
    // ACCEPTED; a terminal FINISHED/FAILED MUST follow STARTED. A jump from
    // ACCEPTED directly to a terminal (skipping STARTED) is out-of-order.
    {
        const bool bHasAccepted = ExistingPhases.Contains(TEXT("ACCEPTED"));
        const bool bHasStarted = ExistingPhases.Contains(TEXT("STARTED"));
        if (Phase == TEXT("ACCEPTED"))
        {
            if (!ExistingPhases.IsEmpty())
            {
                OutError = TEXT("ACCEPTED must be the first journal phase");
                return false;
            }
        }
        else if (Phase == TEXT("STARTED"))
        {
            if (!bHasAccepted)
            {
                OutError = TEXT("STARTED requires ACCEPTED first");
                return false;
            }
        }
        else // FINISHED / FAILED (terminal)
        {
            if (!bHasStarted)
            {
                OutError = TEXT("Terminal phase requires STARTED first");
                return false;
            }
        }
    }

    // ---- Build the phase entry object (retain all identity/error/manifest fields) ----
    TSharedPtr<FJsonObject> JsonObject = MakeShareable(new FJsonObject);
    JsonObject->SetNumberField(TEXT("journal_schema_version"), 2);
    JsonObject->SetStringField(TEXT("atlas_job_id"), AtlasJobId);
    JsonObject->SetStringField(TEXT("unreal_job_id"), UnrealJobId);
    JsonObject->SetStringField(TEXT("phase"), Phase);
    JsonObject->SetNumberField(TEXT("phase_sequence"), (double)NewSequence);
    JsonObject->SetNumberField(TEXT("attempt_ordinal"), (double)JobState->AttemptOrdinal);
    JsonObject->SetStringField(TEXT("state_source"), TEXT("unreal-editor-atlas-transport"));

    FString AttestEditorSessionId;
    FString AttestProcessCreationTimeUtc;
    if (ActiveInstance)
    {
        AttestEditorSessionId = ActiveInstance->EditorSessionId.ToString(EGuidFormats::DigitsWithHyphens);
        AttestProcessCreationTimeUtc = ActiveInstance->ProcessCreationTimeUtc;
        JsonObject->SetStringField(TEXT("editor_session_id"), AttestEditorSessionId);
        JsonObject->SetNumberField(TEXT("process_id"), (double)ActiveInstance->ProcessId);
        JsonObject->SetStringField(TEXT("process_creation_time_utc"), AttestProcessCreationTimeUtc);
    }
    else
    {
        AttestEditorSessionId = FGuid().ToString(EGuidFormats::DigitsWithHyphens);
        AttestProcessCreationTimeUtc = FDateTime::UtcNow().ToIso8601();
        JsonObject->SetStringField(TEXT("editor_session_id"), AttestEditorSessionId);
        JsonObject->SetNumberField(TEXT("process_id"), (double)FPlatformProcess::GetCurrentProcessId());
        JsonObject->SetStringField(TEXT("process_creation_time_utc"), AttestProcessCreationTimeUtc);
    }

    JsonObject->SetStringField(TEXT("sequence_asset_path"), JobState->SequenceAssetPath);
    JsonObject->SetStringField(TEXT("config_digest"), JobState->ConfigDigest);
    JsonObject->SetStringField(TEXT("authorization_id"), JobState->AuthorizationId);
    JsonObject->SetStringField(TEXT("output_directory"), JobState->OutputDirectory);
    JsonObject->SetStringField(TEXT("status"), JobState->Status);
    JsonObject->SetNumberField(TEXT("progress"), JobState->Progress);
    JsonObject->SetBoolField(TEXT("success"), JobState->bSuccess);
    JsonObject->SetBoolField(TEXT("finished"), JobState->bFinished);
    JsonObject->SetBoolField(TEXT("failed"), JobState->bFailed);
    JsonObject->SetStringField(TEXT("written_at"), FDateTime::UtcNow().ToIso8601());

    // Expected output spec (optional/default in M1)
    TSharedPtr<FJsonObject> SpecObj = MakeShareable(new FJsonObject);
    SpecObj->SetStringField(TEXT("format"), JobState->OutputFormat);
    JsonObject->SetObjectField(TEXT("expected_output_spec"), SpecObj);

    // Output manifest (built before HMAC since the canonical payload covers it)
    TArray<TSharedPtr<FJsonValue>> ManifestArray;
    for (const FOutputManifestEntry& Entry : JobState->OutputManifest)
    {
        TSharedPtr<FJsonObject> ManifestObj = MakeShareable(new FJsonObject);
        ManifestObj->SetStringField(TEXT("path"), Entry.Path);
        ManifestObj->SetNumberField(TEXT("size"), (double)Entry.Size);
        ManifestObj->SetStringField(TEXT("sha256"), Entry.Sha256);
        ManifestArray.Add(MakeShareable(new FJsonValueObject(ManifestObj)));
    }
    JsonObject->SetArrayField(TEXT("output_manifest"), ManifestArray);

    // M8: Contract V1 canonical HMAC-SHA256 attestation keyed by Atlas attempt_nonce.
    // The journal entry digest is computed over the canonical payload (schema_version,
    // atlas_job_id, unreal_job_id, attempt_ordinal, phase, phase_sequence,
    // editor_session_id, process_creation_time_utc, output_directory, output_manifest).
    // If no attempt_nonce was provided (legacy/unsupported), the entry carries an
    // EMPTY entry_digest and is NOT attested; the Python reconciler treats it as an
    // unsupported/legacy witness and fails closed (no synthesized success).
    if (!JobState->AttemptNonce.IsEmpty())
    {
        TArray<uint8> CanonicalBytes;
        if (ComputeJournalAttestationCanonical(
                1, // journal_schema_version used as the attestation schema_version
                AtlasJobId,
                UnrealJobId,
                JobState->AttemptOrdinal,
                Phase,
                NewSequence,
                AttestEditorSessionId,
                AttestProcessCreationTimeUtc,
                JobState->OutputDirectory,
                JobState->OutputManifest,
                CanonicalBytes))
        {
            FString HexDigest;
            if (ComputeJournalAttestationDigest(JobState->AttemptNonce, CanonicalBytes, HexDigest))
            {
                JsonObject->SetStringField(TEXT("entry_digest"), HexDigest);
            }
            else
            {
                OutError = TEXT("Failed to compute HMAC-SHA256 journal attestation digest");
                return false;
            }
        }
        else
        {
            OutError = TEXT("Failed to build canonical journal attestation payload");
            return false;
        }
    }
    else
    {
        // Legacy/unsupported: no attestation. Record an empty digest distinctly.
        JsonObject->SetStringField(TEXT("entry_digest"), TEXT(""));
    }

    TArray<TSharedPtr<FJsonValue>> OutputFilesArray;
    for (const FString& File : JobState->OutputFiles)
    {
        OutputFilesArray.Add(MakeShareable(new FJsonValueString(File)));
    }
    JsonObject->SetArrayField(TEXT("output_files"), OutputFilesArray);

    // ---- Append to retained history (append-only) ----
    PhaseHistory.Add(MakeShareable(new FJsonValueObject(JsonObject)));

    // ---- Build container document: history array + latest-phase convenience fields ----
    TSharedPtr<FJsonObject> RootDocument = MakeShareable(new FJsonObject);
    RootDocument->SetNumberField(TEXT("journal_schema_version"), 2);
    RootDocument->SetStringField(TEXT("atlas_job_id"), AtlasJobId);
    RootDocument->SetStringField(TEXT("unreal_job_id"), UnrealJobId);
    RootDocument->SetArrayField(TEXT("phase_history"), PhaseHistory);
    // Latest-phase convenience fields (consumers read these as the current state).
    RootDocument->SetStringField(TEXT("phase"), Phase);
    RootDocument->SetNumberField(TEXT("phase_sequence"), (double)NewSequence);
    RootDocument->SetStringField(TEXT("status"), JobState->Status);
    RootDocument->SetNumberField(TEXT("progress"), JobState->Progress);
    RootDocument->SetBoolField(TEXT("success"), JobState->bSuccess);
    RootDocument->SetBoolField(TEXT("finished"), JobState->bFinished);
    RootDocument->SetBoolField(TEXT("failed"), JobState->bFailed);

    FString OutputString;
    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
    if (!FJsonSerializer::Serialize(RootDocument.ToSharedRef(), Writer))
    {
        OutError = TEXT("Failed to serialize journal entry JSON");
        return false;
    }

    return AtomicWriteFile(TargetPath, OutputString, OutError);
}

bool FAtlasTransportServer::ValidateJournalPhaseHistory(
    const TArray<TSharedPtr<FJsonValue>>& PhaseHistory,
    TArray<FString>& OutPhases,
    int32& OutMaxSequence,
    FString& OutError)
{
    // Structural validation of an EXISTING append-only phase_history.
    // Contract V1: ACCEPTED(1) -> STARTED(2) -> FINISHED(3) | FAILED(3).
    // Each element must be a JSON object carrying a valid phase and an integer
    // phase_sequence that matches the SEMANTIC phase number exactly. The
    // sequence must be strictly increasing, phases unique and in lifecycle
    // order, no dual terminal, nothing after a terminal.

    auto PhaseToSequence = [](const FString& InPhase) -> int32
    {
        if (InPhase == TEXT("ACCEPTED")) return 1;
        if (InPhase == TEXT("STARTED")) return 2;
        if (InPhase == TEXT("FINISHED") || InPhase == TEXT("FAILED")) return 3;
        return -1;
    };

    OutPhases.Reset();
    OutMaxSequence = 0;

    int32 PrevSequence = 0;
    TArray<FString> SeenPhases;
    TArray<int32> SeenSequences;
    bool bTerminalSeen = false;

    for (int32 i = 0; i < PhaseHistory.Num(); ++i)
    {
        const TSharedPtr<FJsonValue>& EntryValue = PhaseHistory[i];
        // Every element MUST be an object.
        if (!EntryValue.IsValid() || EntryValue->Type != EJson::Object)
        {
            OutError = FString::Printf(TEXT("phase_history element %d is not a JSON object"), i);
            return false;
        }
        const TSharedPtr<FJsonObject>& EntryObj = EntryValue->AsObject();

        // phase must be a non-empty string with a known phase.
        FString EPhase;
        if (!EntryObj->TryGetStringField(TEXT("phase"), EPhase) || EPhase.IsEmpty())
        {
            OutError = FString::Printf(TEXT("phase_history element %d missing/invalid 'phase'"), i);
            return false;
        }
        const int32 ESeq = PhaseToSequence(EPhase);
        if (ESeq < 1)
        {
            OutError = FString::Printf(TEXT("phase_history element %d has unknown phase '%s'"), i, *EPhase);
            return false;
        }

        // phase_sequence must be present and an integer equal to the semantic phase number.
        const TSharedPtr<FJsonValue>* SequenceValue = EntryObj->Values.Find(TEXT("phase_sequence"));
        if (SequenceValue == nullptr || !(*SequenceValue).IsValid() || (*SequenceValue)->Type != EJson::Number)
        {
            OutError = FString::Printf(TEXT("phase_history element %d missing/invalid 'phase_sequence'"), i);
            return false;
        }
        const double RawSeq = (*SequenceValue)->AsNumber();
        if (RawSeq != (double)(int32)RawSeq) // not integral
        {
            OutError = FString::Printf(TEXT("phase_history element %d 'phase_sequence' not integer"), i);
            return false;
        }
        const int32 ESeqValue = (int32)RawSeq;
        if (ESeqValue != ESeq)
        {
            OutError = FString::Printf(
                TEXT("phase_history element %d sequence mismatch: phase '%s' requires %d, got %d"),
                i, *EPhase, ESeq, ESeqValue);
            return false;
        }

        // Duplicate phase rejected.
        if (SeenPhases.Contains(EPhase))
        {
            OutError = FString::Printf(TEXT("phase_history contains duplicate phase '%s'"), *EPhase);
            return false;
        }
        // Nothing after a terminal.
        if (bTerminalSeen)
        {
            OutError = TEXT("phase_history contains an entry after a terminal phase");
            return false;
        }
        // Strictly increasing sequence.
        if (ESeqValue <= PrevSequence && i > 0)
        {
            OutError = FString::Printf(
                TEXT("phase_history out-of-order: element %d seq %d <= previous %d"),
                i, ESeqValue, PrevSequence);
            return false;
        }
        // Required lifecycle ordering: ACCEPTED first, STARTED after ACCEPTED,
        // terminal after STARTED.
        if (i == 0 && EPhase != TEXT("ACCEPTED"))
        {
            OutError = TEXT("phase_history must begin with ACCEPTED");
            return false;
        }
        if (EPhase == TEXT("STARTED") && !SeenPhases.Contains(TEXT("ACCEPTED")))
        {
            OutError = TEXT("phase_history STARTED requires ACCEPTED first");
            return false;
        }
        if ((EPhase == TEXT("FINISHED") || EPhase == TEXT("FAILED")) && !SeenPhases.Contains(TEXT("STARTED")))
        {
            OutError = TEXT("phase_history terminal requires STARTED first");
            return false;
        }

        SeenPhases.Add(EPhase);
        SeenSequences.Add(ESeqValue);
        PrevSequence = ESeqValue;
        if (ESeqValue == 3)
        {
            bTerminalSeen = true;
        }
    }

    if (PhaseHistory.Num() == 0)
    {
        OutError = TEXT("phase_history is empty");
        return false;
    }

    OutPhases = SeenPhases;
    OutMaxSequence = PrevSequence;
    OutError = TEXT("");
    return true;
}

// -----------------------------------------------------------------------------
// M8: Contract V1 canonical journal attestation (HMAC-SHA256)
// -----------------------------------------------------------------------------
bool FAtlasTransportServer::ComputeJournalAttestationCanonical(
    int32 SchemaVersion,
    const FString& AtlasJobId,
    const FString& UnrealJobId,
    int32 AttemptOrdinal,
    const FString& Phase,
    int32 PhaseSequence,
    const FString& EditorSessionId,
    const FString& ProcessCreationTimeUtc,
    const FString& OutputDirectory,
    const TArray<FOutputManifestEntry>& OutputManifest,
    TArray<uint8>& OutCanonicalBytes)
{
    // Canonical message (must match Python planning/unreal_journal_attestation):
    //   field(\x1f field)* \x1e
    // where the fields in order are: schema_version, atlas_job_id, unreal_job_id,
    // attempt_ordinal, phase, phase_sequence, editor_session_id,
    // process_creation_time_utc, output_directory, output_manifest.
    // Each manifest entry: path \x1c size \x1c sha256 \x1d
    FString Canonical = FString::Printf(
        TEXT("%d\x1f%s\x1f%s\x1f%d\x1f%s\x1f%d\x1f%s\x1f%s\x1f%s\x1f"),
        SchemaVersion,
        *AtlasJobId,
        *UnrealJobId,
        AttemptOrdinal,
        *Phase,
        PhaseSequence,
        *EditorSessionId,
        *ProcessCreationTimeUtc,
        *OutputDirectory);

    for (const FOutputManifestEntry& Entry : OutputManifest)
    {
        Canonical += FString::Printf(
            TEXT("%s\x1c%d\x1c%s\x1d"),
            *Entry.Path,
            (int32)Entry.Size,
            *Entry.Sha256);
    }
    Canonical += TEXT("\x1e");

    // Encode to UTF-8 bytes.
    FTCHARToUTF8 Utf8(*Canonical);
    OutCanonicalBytes.SetNumUninitialized(Utf8.Length());
    for (int32 i = 0; i < Utf8.Length(); ++i)
    {
        OutCanonicalBytes[i] = (uint8)Utf8.Get()[i];
    }
    return true;
}

bool FAtlasTransportServer::ComputeJournalAttestationDigest(
    const FString& AttemptNonce,
    const TArray<uint8>& CanonicalBytes,
    FString& OutHexDigest)
{
    OutHexDigest = TEXT("");
#if PLATFORM_WINDOWS
    // HMAC-SHA256 per RFC 2104, computed on top of the BCrypt SHA-256 provider
    // (already proven in ComputeFileSha256). This is the REAL keyed HMAC contract:
    //   HMAC(K, m) = SHA256( (K\xe2\x80\x98 XOR opad) || SHA256( (K\xe2\x80\x98 XOR ipad) || m ) )
    // where K\xe2\x80\x98 is the key padded/truncated to the SHA-256 block size (64 bytes),
    // ipad = 0x36, opad = 0x5c. This uses only BCRYPT_SHA256_ALGORITHM and is fully
    // deterministic and independent of any provider string such as an HMAC variant.
    const int32 BlockSize = 64;

    FTCHARToUTF8 KeyUtf8(*AttemptNonce);
    const int32 KeyLen = KeyUtf8.Length();

    // K' = key padded with zeros to BlockSize (truncate if longer than block).
    uint8 KeyBlock[64];
    for (int32 i = 0; i < BlockSize; ++i)
    {
        KeyBlock[i] = (i < KeyLen) ? (uint8)KeyUtf8.Get()[i] : 0;
    }

    // Inner: SHA256( ipad || message )
    // Build ipad block first: (K' XOR 0x36), then append message.
    TArray<uint8> InnerInput;
    InnerInput.SetNumUninitialized(BlockSize + CanonicalBytes.Num());
    for (int32 i = 0; i < BlockSize; ++i)
    {
        InnerInput[i] = (uint8)(KeyBlock[i] ^ 0x36);
    }
    if (CanonicalBytes.Num() > 0)
    {
        FMemory::Memcpy(&InnerInput[BlockSize], CanonicalBytes.GetData(), CanonicalBytes.Num());
    }
    uint8 InnerHash[32];
    if (!ComputeSha256Buffer(InnerInput.GetData(), InnerInput.Num(), InnerHash))
    {
        return false;
    }

    // Outer: SHA256( opad || inner_hash )
    TArray<uint8> OuterInput;
    OuterInput.SetNumUninitialized(BlockSize + 32);
    for (int32 i = 0; i < BlockSize; ++i)
    {
        OuterInput[i] = (uint8)(KeyBlock[i] ^ 0x5c);
    }
    FMemory::Memcpy(&OuterInput[BlockSize], InnerHash, 32);
    uint8 OuterHash[32];
    if (!ComputeSha256Buffer(OuterInput.GetData(), OuterInput.Num(), OuterHash))
    {
        return false;
    }

    FString Result;
    for (int32 i = 0; i < 32; ++i)
    {
        Result += FString::Printf(TEXT("%02x"), OuterHash[i]);
    }
    OutHexDigest = Result;
    return true;
#else
    return false;
#endif
}
