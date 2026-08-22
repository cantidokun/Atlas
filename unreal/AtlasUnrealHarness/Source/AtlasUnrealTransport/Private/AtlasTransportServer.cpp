#include "AtlasTransportServer.h"
#include "AtlasUnrealTransport.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Actor.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "HAL/PlatformFilemanager.h"
#include "Async/Async.h"
#include "Engine/GameViewportClient.h"

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

    FString GetMaterialVariantName(const AActor* Actor)
    {
        if (!Actor) return TEXT("default");
        for (const FName& Tag : Actor->Tags)
        {
            const FString TagString = Tag.ToString();
            if (TagString.StartsWith(MaterialVariantTagPrefix))
            {
                const FString Name = TagString.Mid(MaterialVariantTagPrefix.Len());
                if (!Name.TrimStartAndEnd().IsEmpty()) return Name;
            }
        }
        return TEXT("default");
    }

    void SetMaterialVariantName(AActor* Actor, const FString& VariantName)
    {
        if (!Actor) return;
        for (int32 Index = Actor->Tags.Num() - 1; Index >= 0; --Index)
        {
            if (Actor->Tags[Index].ToString().StartsWith(MaterialVariantTagPrefix)) Actor->Tags.RemoveAt(Index);
        }
        Actor->Tags.Add(FName(*(MaterialVariantTagPrefix + VariantName)));
        Actor->MarkPackageDirty();
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
                    ErrorResponse.RequestId = Request.RequestId;
                    ErrorResponse.OperationName = Request.OperationName;
                    ErrorResponse.EntityIds = Request.EntityIds;
                    ErrorResponse.bSuccess = false;
                    ErrorResponse.Error = ValidationError;
                    ErrorResponse.Source = TEXT("unreal-editor-atlas-transport");
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
    TSharedPtr<FJsonObject> JsonObject = MakeShareable(new FJsonObject); JsonObject->SetStringField(TEXT("request_id"), Response.RequestId); JsonObject->SetStringField(TEXT("operation_name"), Response.OperationName); JsonObject->SetBoolField(TEXT("success"), Response.bSuccess); JsonObject->SetStringField(TEXT("error"), Response.Error); JsonObject->SetStringField(TEXT("source"), Response.Source);
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
        const TSharedPtr<FJsonObject>* LocationObject = nullptr; if (!Request.Arguments->TryGetObjectField(TEXT("location"), LocationObject) || LocationObject == nullptr || !LocationObject->IsValid()) { OutError = TEXT("arguments.location must be an object"); return false; }
        double X = 0.0, Y = 0.0, Z = 0.0; if (!(*LocationObject)->TryGetNumberField(TEXT("x"), X) || !(*LocationObject)->TryGetNumberField(TEXT("y"), Y) || !(*LocationObject)->TryGetNumberField(TEXT("z"), Z)) { OutError = TEXT("arguments.location must contain numeric x, y, and z"); return false; }
        return true;
    }
    if (Request.OperationName == TEXT("set_actor_rotation"))
    {
        if (Request.Capability != TEXT("modify_actor") || Request.Kind != TEXT("write")) { OutError = TEXT("set_actor_rotation requires modify_actor/write"); return false; }
        if (Request.EntityIds.Num() != 1) { OutError = TEXT("set_actor_rotation requires exactly one entity_id"); return false; }
        const TSharedPtr<FJsonObject>* RotationObject = nullptr; if (!Request.Arguments->TryGetObjectField(TEXT("rotation"), RotationObject) || RotationObject == nullptr || !RotationObject->IsValid()) { OutError = TEXT("arguments.rotation must be an object"); return false; }
        double Pitch = 0.0, Yaw = 0.0, Roll = 0.0; if (!(*RotationObject)->TryGetNumberField(TEXT("pitch"), Pitch) || !(*RotationObject)->TryGetNumberField(TEXT("yaw"), Yaw) || !(*RotationObject)->TryGetNumberField(TEXT("roll"), Roll)) { OutError = TEXT("arguments.rotation must contain numeric pitch, yaw, and roll"); return false; }
        return true;
    }
    if (Request.OperationName == TEXT("set_actor_scale"))
    {
        if (Request.Capability != TEXT("modify_actor") || Request.Kind != TEXT("write")) { OutError = TEXT("set_actor_scale requires modify_actor/write"); return false; }
        if (Request.EntityIds.Num() != 1) { OutError = TEXT("set_actor_scale requires exactly one entity_id"); return false; }
        const TSharedPtr<FJsonObject>* ScaleObject = nullptr; if (!Request.Arguments->TryGetObjectField(TEXT("scale"), ScaleObject) || ScaleObject == nullptr || !ScaleObject->IsValid()) { OutError = TEXT("arguments.scale must be an object"); return false; }
        double X = 0.0, Y = 0.0, Z = 0.0; if (!(*ScaleObject)->TryGetNumberField(TEXT("x"), X) || !(*ScaleObject)->TryGetNumberField(TEXT("y"), Y) || !(*ScaleObject)->TryGetNumberField(TEXT("z"), Z)) { OutError = TEXT("arguments.scale must contain numeric x, y, and z"); return false; }
        return true;
    }
    if (Request.OperationName == TEXT("inspect_material_state")) { if (Request.Capability != TEXT("material") || Request.Kind != TEXT("read")) { OutError = TEXT("inspect_material_state requires material/read"); return false; } return true; }
    if (Request.OperationName == TEXT("apply_material_variant"))
    {
        if (Request.Capability != TEXT("material") || Request.Kind != TEXT("write")) { OutError = TEXT("apply_material_variant requires material/write"); return false; }
        const TSharedPtr<FJsonObject>* VariantObject = nullptr; if (!Request.Arguments->TryGetObjectField(TEXT("material_variant"), VariantObject) || VariantObject == nullptr || !VariantObject->IsValid()) { OutError = TEXT("arguments.material_variant must be an object"); return false; }
        FString VariantName; if (!(*VariantObject)->TryGetStringField(TEXT("name"), VariantName) || VariantName.TrimStartAndEnd().IsEmpty()) { OutError = TEXT("arguments.material_variant.name must be a non-empty string"); return false; }
        return true;
    }
    OutError = FString::Printf(TEXT("Unsupported operation_name: %s"), *Request.OperationName); return false;
}

bool FAtlasTransportServer::ExecuteRequest(const FTransportRequest& Request, FTransportResponse& OutResponse)
{
    OutResponse.RequestId = Request.RequestId; OutResponse.OperationName = Request.OperationName; OutResponse.EntityIds = Request.EntityIds; OutResponse.Source = TEXT("unreal-editor-atlas-transport");
    if (Request.OperationName == TEXT("inspect_target_actors") || Request.OperationName == TEXT("set_actor_location") || Request.OperationName == TEXT("set_actor_rotation") || Request.OperationName == TEXT("set_actor_scale") || Request.OperationName == TEXT("inspect_material_state") || Request.OperationName == TEXT("apply_material_variant"))
    {
        TSharedPtr<FGameThreadExecutionState> SharedState = MakeShareable(new FGameThreadExecutionState()); SharedState->Request = Request; SharedState->Response.RequestId = Request.RequestId; SharedState->Response.OperationName = Request.OperationName; SharedState->Response.EntityIds = Request.EntityIds; SharedState->Response.Source = TEXT("unreal-editor-atlas-transport");
        AsyncTask(ENamedThreads::GameThread, [SharedState]() { FAtlasTransportServer::ExecuteOnGameThread(SharedState); });
        const uint32 TimeoutMs = 5000; const bool bEventTriggered = SharedState->CompletionEvent->Wait(TimeoutMs);
        if (bStopRequested) { SharedState->bCancelled = true; OutResponse.bSuccess = false; OutResponse.Error = TEXT("Operation cancelled during shutdown"); return false; }
        if (!bEventTriggered) { SharedState->bCancelled = true; OutResponse.bSuccess = false; OutResponse.Error = TEXT("Operation timed out"); return false; }
        OutResponse = SharedState->Response; return SharedState->bSuccess;
    }
    OutResponse.bSuccess = false; OutResponse.Error = FString::Printf(TEXT("Unsupported operation: %s"), *Request.OperationName); return false;
}

void FAtlasTransportServer::ExecuteOnGameThread(TSharedPtr<FGameThreadExecutionState> SharedState)
{
    if (SharedState->bCancelled) { SharedState->Response.bSuccess = false; SharedState->Response.Error = TEXT("Operation cancelled before execution"); SharedState->bSuccess = false; SharedState->bCompleted = true; SharedState->CompletionEvent->Trigger(); return; }
    if (!IsInGameThread()) { SharedState->Response.bSuccess = false; SharedState->Response.Error = TEXT("ExecuteOnGameThread must be called on game thread"); SharedState->bSuccess = false; SharedState->bCompleted = true; SharedState->CompletionEvent->Trigger(); return; }
    if (!GEngine || IsEngineExitRequested()) { SharedState->Response.bSuccess = false; SharedState->Response.Error = TEXT("Engine shutting down"); SharedState->bSuccess = false; SharedState->bCompleted = true; SharedState->CompletionEvent->Trigger(); return; }

    bool bTaskSuccess = false;
    if (SharedState->Request.OperationName == TEXT("inspect_target_actors")) bTaskSuccess = InspectTargetActors(SharedState->Request.EntityIds, SharedState->ObservedState, SharedState->Error);
    else if (SharedState->Request.OperationName == TEXT("set_actor_location")) bTaskSuccess = SetActorLocation(SharedState->Request, SharedState->ObservedState, SharedState->Error);
    else if (SharedState->Request.OperationName == TEXT("set_actor_rotation")) bTaskSuccess = SetActorRotation(SharedState->Request, SharedState->ObservedState, SharedState->Error);
    else if (SharedState->Request.OperationName == TEXT("set_actor_scale")) bTaskSuccess = SetActorScale(SharedState->Request, SharedState->ObservedState, SharedState->Error);
    else if (SharedState->Request.OperationName == TEXT("inspect_material_state")) bTaskSuccess = InspectMaterialState(SharedState->Request.EntityIds, SharedState->ObservedState, SharedState->Error);
    else if (SharedState->Request.OperationName == TEXT("apply_material_variant")) bTaskSuccess = ApplyMaterialVariant(SharedState->Request, SharedState->ObservedState, SharedState->Error);
    else SharedState->Error = FString::Printf(TEXT("Unsupported operation: %s"), *SharedState->Request.OperationName);

    if (bTaskSuccess && SharedState->Error.IsEmpty()) { SharedState->Response.bSuccess = true; SharedState->Response.ObservedState = SharedState->ObservedState; SharedState->bSuccess = true; }
    else { SharedState->Response.bSuccess = false; SharedState->Response.Error = SharedState->Error.IsEmpty() ? TEXT("Unknown error during Unreal operation") : SharedState->Error; SharedState->bSuccess = false; }
    SharedState->bCompleted = true; SharedState->CompletionEvent->Trigger();
}

bool FAtlasTransportServer::SetActorLocation(const FTransportRequest& Request, TSharedPtr<FJsonObject>& OutObservedState, FString& OutError)
{
    if (!IsInGameThread() || !GEngine || IsEngineExitRequested()) { OutError = TEXT("Engine unavailable or operation is not on the game thread"); return false; }
    if (Request.EntityIds.Num() != 1 || !Request.Arguments.IsValid()) { OutError = TEXT("set_actor_location requires exactly one entity_id and valid arguments"); return false; }
    const TSharedPtr<FJsonObject>* LocationObject = nullptr; if (!Request.Arguments->TryGetObjectField(TEXT("location"), LocationObject) || LocationObject == nullptr || !LocationObject->IsValid()) { OutError = TEXT("arguments.location must be an object"); return false; }
    double X = 0.0, Y = 0.0, Z = 0.0; if (!(*LocationObject)->TryGetNumberField(TEXT("x"), X) || !(*LocationObject)->TryGetNumberField(TEXT("y"), Y) || !(*LocationObject)->TryGetNumberField(TEXT("z"), Z)) { OutError = TEXT("arguments.location must contain numeric x, y, and z"); return false; }
    AActor* Actor = FindActorByEntityId(Request.EntityIds[0]); if (!Actor || !IsValid(Actor)) { OutError = FString::Printf(TEXT("Actor not found for entity_id: %s"), *Request.EntityIds[0]); return false; }
    Actor->SetActorLocation(FVector(static_cast<float>(X), static_cast<float>(Y), static_cast<float>(Z)), false, nullptr, ETeleportType::TeleportPhysics);
    return InspectTargetActors(Request.EntityIds, OutObservedState, OutError);
}

bool FAtlasTransportServer::SetActorRotation(const FTransportRequest& Request, TSharedPtr<FJsonObject>& OutObservedState, FString& OutError)
{
    if (!IsInGameThread() || !GEngine || IsEngineExitRequested()) { OutError = TEXT("Engine unavailable or operation is not on the game thread"); return false; }
    if (Request.EntityIds.Num() != 1 || !Request.Arguments.IsValid()) { OutError = TEXT("set_actor_rotation requires exactly one entity_id and valid arguments"); return false; }
    const TSharedPtr<FJsonObject>* RotationObject = nullptr; if (!Request.Arguments->TryGetObjectField(TEXT("rotation"), RotationObject) || RotationObject == nullptr || !RotationObject->IsValid()) { OutError = TEXT("arguments.rotation must be an object"); return false; }
    double Pitch = 0.0, Yaw = 0.0, Roll = 0.0; if (!(*RotationObject)->TryGetNumberField(TEXT("pitch"), Pitch) || !(*RotationObject)->TryGetNumberField(TEXT("yaw"), Yaw) || !(*RotationObject)->TryGetNumberField(TEXT("roll"), Roll)) { OutError = TEXT("arguments.rotation must contain numeric pitch, yaw, and roll"); return false; }
    AActor* Actor = FindActorByEntityId(Request.EntityIds[0]); if (!Actor || !IsValid(Actor)) { OutError = FString::Printf(TEXT("Actor not found for entity_id: %s"), *Request.EntityIds[0]); return false; }
    Actor->SetActorRotation(FRotator(static_cast<float>(Pitch), static_cast<float>(Yaw), static_cast<float>(Roll)));
    return InspectTargetActors(Request.EntityIds, OutObservedState, OutError);
}

bool FAtlasTransportServer::SetActorScale(const FTransportRequest& Request, TSharedPtr<FJsonObject>& OutObservedState, FString& OutError)
{
    if (!IsInGameThread() || !GEngine || IsEngineExitRequested()) { OutError = TEXT("Engine unavailable or operation is not on the game thread"); return false; }
    if (Request.EntityIds.Num() != 1 || !Request.Arguments.IsValid()) { OutError = TEXT("set_actor_scale requires exactly one entity_id and valid arguments"); return false; }
    const TSharedPtr<FJsonObject>* ScaleObject = nullptr; if (!Request.Arguments->TryGetObjectField(TEXT("scale"), ScaleObject) || ScaleObject == nullptr || !ScaleObject->IsValid()) { OutError = TEXT("arguments.scale must be an object"); return false; }
    double X = 0.0, Y = 0.0, Z = 0.0; if (!(*ScaleObject)->TryGetNumberField(TEXT("x"), X) || !(*ScaleObject)->TryGetNumberField(TEXT("y"), Y) || !(*ScaleObject)->TryGetNumberField(TEXT("z"), Z)) { OutError = TEXT("arguments.scale must contain numeric x, y, and z"); return false; }
    AActor* Actor = FindActorByEntityId(Request.EntityIds[0]); if (!Actor || !IsValid(Actor)) { OutError = FString::Printf(TEXT("Actor not found for entity_id: %s"), *Request.EntityIds[0]); return false; }
    Actor->SetActorScale3D(FVector(static_cast<float>(X), static_cast<float>(Y), static_cast<float>(Z)));
    return InspectTargetActors(Request.EntityIds, OutObservedState, OutError);
}

bool FAtlasTransportServer::InspectMaterialState(const TArray<FString>& EntityIds, TSharedPtr<FJsonObject>& OutObservedState, FString& OutError)
{
    if (!IsInGameThread() || !GEngine || IsEngineExitRequested()) { OutError = TEXT("Engine unavailable or operation is not on the game thread"); return false; }
    if (EntityIds.Num() == 0) { OutError = TEXT("inspect_material_state requires at least one entity_id"); return false; }
    TSharedPtr<FJsonObject> ObservedState = MakeShareable(new FJsonObject);
    for (const FString& EntityId : EntityIds)
    {
        AActor* Actor = FindActorByEntityId(EntityId); if (!Actor || !IsValid(Actor)) { OutError = FString::Printf(TEXT("Actor not found for entity_id: %s"), *EntityId); return false; }
        TSharedPtr<FJsonObject> MaterialState; if (!BuildMaterialVariantState(Actor, MaterialState, OutError)) return false;
        TSharedPtr<FJsonObject> ActorData = MakeShareable(new FJsonObject); ActorData->SetStringField(TEXT("entity_id"), EntityId); ActorData->SetObjectField(TEXT("material"), MaterialState); ObservedState->SetObjectField(EntityId, ActorData);
    }
    OutObservedState = ObservedState; return true;
}

bool FAtlasTransportServer::ApplyMaterialVariant(const FTransportRequest& Request, TSharedPtr<FJsonObject>& OutObservedState, FString& OutError)
{
    if (!IsInGameThread() || !GEngine || IsEngineExitRequested()) { OutError = TEXT("Engine unavailable or operation is not on the game thread"); return false; }
    if (!Request.Arguments.IsValid() || Request.EntityIds.Num() == 0) { OutError = TEXT("apply_material_variant requires valid arguments and target entity_ids"); return false; }
    const TSharedPtr<FJsonObject>* VariantObject = nullptr; if (!Request.Arguments->TryGetObjectField(TEXT("material_variant"), VariantObject) || VariantObject == nullptr || !VariantObject->IsValid()) { OutError = TEXT("arguments.material_variant must be an object"); return false; }
    FString VariantName; if (!(*VariantObject)->TryGetStringField(TEXT("name"), VariantName) || VariantName.TrimStartAndEnd().IsEmpty()) { OutError = TEXT("arguments.material_variant.name must be a non-empty string"); return false; }
    for (const FString& EntityId : Request.EntityIds) { AActor* Actor = FindActorByEntityId(EntityId); if (!Actor || !IsValid(Actor)) { OutError = FString::Printf(TEXT("Actor not found for entity_id: %s"), *EntityId); return false; } SetMaterialVariantName(Actor, VariantName); }
    return InspectMaterialState(Request.EntityIds, OutObservedState, OutError);
}

bool FAtlasTransportServer::BuildMaterialVariantState(AActor* Actor, TSharedPtr<FJsonObject>& OutMaterialState, FString& OutError)
{
    if (!Actor || !IsValid(Actor)) { OutError = TEXT("Cannot inspect material state for invalid actor"); return false; }
    TSharedPtr<FJsonObject> Variant = MakeShareable(new FJsonObject); Variant->SetStringField(TEXT("name"), GetMaterialVariantName(Actor)); OutMaterialState = MakeShareable(new FJsonObject); OutMaterialState->SetObjectField(TEXT("variant"), Variant); return true;
}

bool FAtlasTransportServer::InspectTargetActors(const TArray<FString>& EntityIds, TSharedPtr<FJsonObject>& OutObservedState, FString& OutError)
{
    if (!IsInGameThread() || !GEngine || IsEngineExitRequested()) { OutError = TEXT("Engine unavailable or operation is not on the game thread"); return false; }
    UWorld* World = nullptr; if (GEngine->GetWorldContexts().Num() > 0) World = GEngine->GetWorldContexts()[0].World();
    if (!World || !IsValid(World)) { OutError = TEXT("No valid world found"); return false; }
    TSharedPtr<FJsonObject> ObservedState = MakeShareable(new FJsonObject);
    for (const FString& EntityId : EntityIds)
    {
        AActor* Actor = FindActorByEntityId(EntityId); if (!Actor || !IsValid(Actor)) { OutError = FString::Printf(TEXT("Actor not found for entity_id: %s"), *EntityId); return false; }
        TSharedPtr<FJsonObject> ActorData = MakeShareable(new FJsonObject); ActorData->SetStringField(TEXT("entity_id"), EntityId); ActorData->SetStringField(TEXT("actor_name"), Actor->GetName()); ActorData->SetStringField(TEXT("actor_class"), Actor->GetClass()->GetName());
        const FVector Location = Actor->GetActorLocation(); TSharedPtr<FJsonObject> LocationObj = MakeShareable(new FJsonObject); LocationObj->SetNumberField(TEXT("x"), Location.X); LocationObj->SetNumberField(TEXT("y"), Location.Y); LocationObj->SetNumberField(TEXT("z"), Location.Z); ActorData->SetObjectField(TEXT("location"), LocationObj);
        const FRotator Rotation = Actor->GetActorRotation(); TSharedPtr<FJsonObject> RotationObj = MakeShareable(new FJsonObject); RotationObj->SetNumberField(TEXT("pitch"), Rotation.Pitch); RotationObj->SetNumberField(TEXT("yaw"), Rotation.Yaw); RotationObj->SetNumberField(TEXT("roll"), Rotation.Roll); ActorData->SetObjectField(TEXT("rotation"), RotationObj);
        const FVector Scale = Actor->GetActorScale3D(); TSharedPtr<FJsonObject> ScaleObj = MakeShareable(new FJsonObject); ScaleObj->SetNumberField(TEXT("x"), Scale.X); ScaleObj->SetNumberField(TEXT("y"), Scale.Y); ScaleObj->SetNumberField(TEXT("z"), Scale.Z); ActorData->SetObjectField(TEXT("scale"), ScaleObj);
        ObservedState->SetObjectField(EntityId, ActorData);
    }
    OutObservedState = ObservedState; return true;
}

AActor* FAtlasTransportServer::FindActorByEntityId(const FString& EntityId)
{
    if (!IsInGameThread() || !GEngine || IsEngineExitRequested()) return nullptr;
    UWorld* World = nullptr; if (GEngine->GetWorldContexts().Num() > 0) World = GEngine->GetWorldContexts()[0].World();
    if (!World || !IsValid(World)) return nullptr;
    const FString TagToFind = FString::Printf(TEXT("atlas_entity:%s"), *EntityId);
    for (TActorIterator<AActor> ActorItr(World); ActorItr; ++ActorItr) { AActor* Actor = *ActorItr; if (Actor && IsValid(Actor) && Actor->Tags.Contains(FName(*TagToFind))) return Actor; }
    return nullptr;
}
