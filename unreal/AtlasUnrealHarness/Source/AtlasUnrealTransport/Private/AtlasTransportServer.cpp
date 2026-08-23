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
    const FString NiagaraVariantTagPrefix = TEXT("atlas_niagara_variant:");

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
    OutError = FString::Printf(TEXT("Unsupported operation_name: %s"), *Request.OperationName); return false;
}

bool FAtlasTransportServer::ExecuteRequest(const FTransportRequest& Request, FTransportResponse& OutResponse)
{
    OutResponse.RequestId=Request.RequestId; OutResponse.OperationName=Request.OperationName; OutResponse.EntityIds=Request.EntityIds; OutResponse.Source=TEXT("unreal-editor-atlas-transport");
    const bool bSupported = Request.OperationName==TEXT("inspect_target_actors")||Request.OperationName==TEXT("set_actor_location")||Request.OperationName==TEXT("set_actor_rotation")||Request.OperationName==TEXT("set_actor_scale")||Request.OperationName==TEXT("inspect_material_state")||Request.OperationName==TEXT("apply_material_variant")||Request.OperationName==TEXT("inspect_niagara_state")||Request.OperationName==TEXT("apply_niagara_variant");
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
    if(!IsInGameThread()||!GEngine||IsEngineExitRequested()){E=TEXT("Engine unavailable or operation is not on the game thread");return false;} if(R.EntityIds.Num()!=1||!R.Arguments.IsValid()){E=TEXT("set_actor_rotation requires exactly one entity_id and valid arguments");return false;} const TSharedPtr<FJsonObject>* P=nullptr; if(!R.Arguments->TryGetObjectField(TEXT("rotation"),P)||!P||!P->IsValid()){E=TEXT("arguments.rotation must be an object");return false;} double A=0,B=0,C=0; if(!(*P)->TryGetNumberField(TEXT("pitch"),A)||!(*P)->TryGetNumberField(TEXT("yaw"),B)||!(*P)->TryGetNumberField(TEXT("roll"),C)){E=TEXT("arguments.rotation must contain numeric pitch, yaw, and roll");return false;} AActor* Actor=FindActorByEntityId(R.EntityIds[0]); if(!Actor||!IsValid(Actor)){E=FString::Printf(TEXT("Actor not found for entity_id: %s"),*R.EntityIds[0]);return false;} Actor->SetActorRotation(FRotator((float)A,(float)B,(float)C)); return InspectTargetActors(R.EntityIds,O,E);
}

bool FAtlasTransportServer::SetActorScale(const FTransportRequest& R,TSharedPtr<FJsonObject>& O,FString& E)
{
    if(!IsInGameThread()||!GEngine||IsEngineExitRequested()){E=TEXT("Engine unavailable or operation is not on the game thread");return false;} if(R.EntityIds.Num()!=1||!R.Arguments.IsValid()){E=TEXT("set_actor_scale requires exactly one entity_id and valid arguments");return false;} const TSharedPtr<FJsonObject>* P=nullptr; if(!R.Arguments->TryGetObjectField(TEXT("scale"),P)||!P||!P->IsValid()){E=TEXT("arguments.scale must be an object");return false;} double X=0,Y=0,Z=0; if(!(*P)->TryGetNumberField(TEXT("x"),X)||!(*P)->TryGetNumberField(TEXT("y"),Y)||!(*P)->TryGetNumberField(TEXT("z"),Z)){E=TEXT("arguments.scale must contain numeric x, y, and z");return false;} AActor* Actor=FindActorByEntityId(R.EntityIds[0]); if(!Actor||!IsValid(Actor)){E=FString::Printf(TEXT("Actor not found for entity_id: %s"),*R.EntityIds[0]);return false;} Actor->SetActorScale3D(FVector((float)X,(float)Y,(float)Z)); return InspectTargetActors(R.EntityIds,O,E);
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
    if(!IsInGameThread()||!GEngine||IsEngineExitRequested()){E=TEXT("Engine unavailable or operation is not on the game thread");return false;} if(!R.Arguments.IsValid()||R.EntityIds.Num()==0){E=TEXT("apply_niagara_variant requires valid arguments and target entity_ids");return false;} const TSharedPtr<FJsonObject>* P=nullptr; if(!R.Arguments->TryGetObjectField(TEXT("niagara_variant"),P)||!P||!P->IsValid()){E=TEXT("arguments.niagara_variant must be an object");return false;} FString Name; if(!(*P)->TryGetStringField(TEXT("name"),Name)||Name.TrimStartAndEnd().IsEmpty()){E=TEXT("arguments.niagara_variant.name must be a non-empty string");return false;} for(const FString& ID:R.EntityIds){AActor* A=FindActorByEntityId(ID);if(!A||!IsValid(A)){E=FString::Printf(TEXT("Actor not found for entity_id: %s"),*ID);return false;}SetTaggedVariantName(A,NiagaraVariantTagPrefix,Name);} return InspectNiagaraState(R.EntityIds,O,E);
}

bool FAtlasTransportServer::BuildNiagaraVariantState(AActor* A,TSharedPtr<FJsonObject>& O,FString& E)
{
    if(!A||!IsValid(A)){E=TEXT("Cannot inspect Niagara state for invalid actor");return false;} TSharedPtr<FJsonObject> V=MakeShareable(new FJsonObject);V->SetStringField(TEXT("name"),GetTaggedVariantName(A,NiagaraVariantTagPrefix));O=MakeShareable(new FJsonObject);O->SetObjectField(TEXT("variant"),V);return true;
}

bool FAtlasTransportServer::InspectTargetActors(const TArray<FString>& IDs,TSharedPtr<FJsonObject>& O,FString& E)
{
    if(!IsInGameThread()||!GEngine||IsEngineExitRequested()){E=TEXT("Engine unavailable or operation is not on the game thread");return false;} UWorld* World=nullptr; if(GEngine->GetWorldContexts().Num()>0)World=GEngine->GetWorldContexts()[0].World(); if(!World||!IsValid(World)){E=TEXT("No valid world found");return false;} TSharedPtr<FJsonObject> State=MakeShareable(new FJsonObject);
    for(const FString& ID:IDs){AActor* A=FindActorByEntityId(ID);if(!A||!IsValid(A)){E=FString::Printf(TEXT("Actor not found for entity_id: %s"),*ID);return false;} TSharedPtr<FJsonObject>D=MakeShareable(new FJsonObject);D->SetStringField(TEXT("entity_id"),ID);D->SetStringField(TEXT("actor_name"),A->GetName());D->SetStringField(TEXT("actor_class"),A->GetClass()->GetName()); FVector L=A->GetActorLocation();TSharedPtr<FJsonObject>LO=MakeShareable(new FJsonObject);LO->SetNumberField(TEXT("x"),L.X);LO->SetNumberField(TEXT("y"),L.Y);LO->SetNumberField(TEXT("z"),L.Z);D->SetObjectField(TEXT("location"),LO); FRotator R=A->GetActorRotation();TSharedPtr<FJsonObject>RO=MakeShareable(new FJsonObject);RO->SetNumberField(TEXT("pitch"),R.Pitch);RO->SetNumberField(TEXT("yaw"),R.Yaw);RO->SetNumberField(TEXT("roll"),R.Roll);D->SetObjectField(TEXT("rotation"),RO); FVector S=A->GetActorScale3D();TSharedPtr<FJsonObject>SO=MakeShareable(new FJsonObject);SO->SetNumberField(TEXT("x"),S.X);SO->SetNumberField(TEXT("y"),S.Y);SO->SetNumberField(TEXT("z"),S.Z);D->SetObjectField(TEXT("scale"),SO);State->SetObjectField(ID,D);} O=State;return true;
}

AActor* FAtlasTransportServer::FindActorByEntityId(const FString& EntityId)
{
    if(!IsInGameThread()||!GEngine||IsEngineExitRequested())return nullptr; UWorld* World=nullptr; if(GEngine->GetWorldContexts().Num()>0)World=GEngine->GetWorldContexts()[0].World(); if(!World||!IsValid(World))return nullptr; const FString TagToFind=FString::Printf(TEXT("atlas_entity:%s"),*EntityId); for(TActorIterator<AActor> ActorItr(World);ActorItr;++ActorItr){AActor* Actor=*ActorItr;if(Actor&&IsValid(Actor)&&Actor->Tags.Contains(FName(*TagToFind)))return Actor;} return nullptr;
}
