#include "AtlasTransportServer.h"
#include "AtlasUnrealTransport.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Actor.h"
#include "Components/ActorComponent.h"
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
const int32 FAtlasTransportServer::MaxMessageSize = 1024 * 1024; // 1MB

FAtlasTransportServer::FAtlasTransportServer()
    : Thread(nullptr)
    , bStopRequested(false)
    , PipeHandle(nullptr)
{
}

FAtlasTransportServer::~FAtlasTransportServer()
{
    StopServer();
}

bool FAtlasTransportServer::StartServer()
{
    if (Thread)
    {
        UE_LOG(LogAtlasTransport, Warning, TEXT("Transport server already running"));
        return false;
    }

    bStopRequested = false;
    Thread = FRunnableThread::Create(this, TEXT("AtlasTransportServer"), 0, TPri_Normal);
    
    return Thread != nullptr;
}

void FAtlasTransportServer::StopServer()
{
    if (Thread)
    {
        bStopRequested = true;
        
        // Force close pipe to unblock any waiting operations
        CloseNamedPipe();
        
        Thread->WaitForCompletion();
        delete Thread;
        Thread = nullptr;
    }
}

bool FAtlasTransportServer::Init()
{
    UE_LOG(LogAtlasTransport, Log, TEXT("Initializing transport server thread"));
    return true;
}

uint32 FAtlasTransportServer::Run()
{
    UE_LOG(LogAtlasTransport, Log, TEXT("Transport server thread started"));
    
    while (!bStopRequested)
    {
        if (!CreateNamedPipe())
        {
            UE_LOG(LogAtlasTransport, Error, TEXT("Failed to create named pipe"));
            FPlatformProcess::Sleep(1.0f);
            continue;
        }
        
        UE_LOG(LogAtlasTransport, Log, TEXT("Waiting for client connection..."));
        
        if (!WaitForClient())
        {
            CloseNamedPipe();
            if (!bStopRequested)
            {
                UE_LOG(LogAtlasTransport, Warning, TEXT("Client connection failed"));
                FPlatformProcess::Sleep(0.1f);
            }
            continue;
        }
        
        if (bStopRequested)
        {
            CloseNamedPipe();
            break;
        }
        
        UE_LOG(LogAtlasTransport, Log, TEXT("Client connected"));
        
        FString JsonRequest;
        if (ReadRequest(JsonRequest))
        {
            if (bStopRequested)
            {
                CloseNamedPipe();
                break;
            }
            
            FTransportRequest Request;
            if (ParseRequest(JsonRequest, Request))
            {
                FString ValidationError;
                if (ValidateRequest(Request, ValidationError))
                {
                    FTransportResponse Response;
                    ExecuteRequest(Request, Response);
                    
                    FString JsonResponse = SerializeResponse(Response);
                    WriteResponse(JsonResponse);
                }
                else
                {
                    // Send error response
                    FTransportResponse ErrorResponse;
                    ErrorResponse.RequestId = Request.RequestId;
                    ErrorResponse.OperationName = Request.OperationName;
                    ErrorResponse.EntityIds = Request.EntityIds;
                    ErrorResponse.bSuccess = false;
                    ErrorResponse.Error = ValidationError;
                    ErrorResponse.Source = TEXT("unreal-editor-atlas-transport");
                    
                    FString JsonResponse = SerializeResponse(ErrorResponse);
                    WriteResponse(JsonResponse);
                }
            }
            else
            {
                UE_LOG(LogAtlasTransport, Error, TEXT("Failed to parse request JSON"));
            }
        }
        else
        {
            UE_LOG(LogAtlasTransport, Warning, TEXT("Failed to read request"));
        }
        
        CloseNamedPipe();
    }
    
    UE_LOG(LogAtlasTransport, Log, TEXT("Transport server thread exiting"));
    return 0;
}

void FAtlasTransportServer::Stop()
{
    bStopRequested = true;
}

void FAtlasTransportServer::Exit()
{
    CloseNamedPipe();
}

bool FAtlasTransportServer::CreateNamedPipe()
{
#if PLATFORM_WINDOWS
    HANDLE hPipe = CreateNamedPipeA(
        TCHAR_TO_ANSI(*PipeName),
        PIPE_ACCESS_DUPLEX,
        PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
        1, // Max instances
        MaxMessageSize,
        MaxMessageSize,
        0, // Default timeout
        nullptr
    );
    
    if (hPipe == INVALID_HANDLE_VALUE)
    {
        UE_LOG(LogAtlasTransport, Error, TEXT("CreateNamedPipe failed with error: %d"), GetLastError());
        return false;
    }
    
    PipeHandle = hPipe;
    return true;
#else
    UE_LOG(LogAtlasTransport, Error, TEXT("Named pipes not supported on this platform"));
    return false;
#endif
}

void FAtlasTransportServer::CloseNamedPipe()
{
#if PLATFORM_WINDOWS
    if (PipeHandle && PipeHandle != INVALID_HANDLE_VALUE)
    {
        CloseHandle((HANDLE)PipeHandle);
        PipeHandle = nullptr;
    }
#endif
}

bool FAtlasTransportServer::WaitForClient()
{
#if PLATFORM_WINDOWS
    if (!PipeHandle || PipeHandle == INVALID_HANDLE_VALUE)
    {
        return false;
    }
    
    BOOL bConnected = ConnectNamedPipe((HANDLE)PipeHandle, nullptr);
    if (!bConnected)
    {
        DWORD dwError = GetLastError();
        if (dwError == ERROR_PIPE_CONNECTED)
        {
            return true; // Client already connected
        }
        
        UE_LOG(LogAtlasTransport, Error, TEXT("ConnectNamedPipe failed with error: %d"), dwError);
        return false;
    }
    
    return true;
#else
    return false;
#endif
}

bool FAtlasTransportServer::ReadRequest(FString& OutJsonRequest)
{
#if PLATFORM_WINDOWS
    if (!PipeHandle || PipeHandle == INVALID_HANDLE_VALUE)
    {
        return false;
    }
    
    TArray<uint8> Buffer;
    Buffer.SetNum(MaxMessageSize);
    
    DWORD BytesRead = 0;
    BOOL bSuccess = ReadFile((HANDLE)PipeHandle, Buffer.GetData(), MaxMessageSize, &BytesRead, nullptr);
    
    if (!bSuccess)
    {
        DWORD dwError = GetLastError();
        if (dwError == ERROR_MORE_DATA)
        {
            UE_LOG(LogAtlasTransport, Error, TEXT("Message exceeds maximum size of %d bytes"), MaxMessageSize);
            return false;
        }
        UE_LOG(LogAtlasTransport, Error, TEXT("ReadFile failed with error: %d"), dwError);
        return false;
    }
    
    if (BytesRead == 0)
    {
        UE_LOG(LogAtlasTransport, Warning, TEXT("No data read from pipe"));
        return false;
    }
    
    // Ensure null termination for UTF-8 conversion
    Buffer.SetNum(BytesRead + 1);
    Buffer[BytesRead] = 0;
    
    // Convert to string
    OutJsonRequest = FString(UTF8_TO_TCHAR(reinterpret_cast<const char*>(Buffer.GetData())));
    
    return true;
#else
    return false;
#endif
}

bool FAtlasTransportServer::WriteResponse(const FString& JsonResponse)
{
#if PLATFORM_WINDOWS
    if (!PipeHandle || PipeHandle == INVALID_HANDLE_VALUE)
    {
        return false;
    }
    
    FTCHARToUTF8 UTF8String(*JsonResponse);
    DWORD BytesToWrite = UTF8String.Length();
    DWORD BytesWritten = 0;
    
    BOOL bSuccess = WriteFile((HANDLE)PipeHandle, UTF8String.Get(), BytesToWrite, &BytesWritten, nullptr);
    
    if (!bSuccess || BytesWritten != BytesToWrite)
    {
        DWORD dwError = GetLastError();
        UE_LOG(LogAtlasTransport, Error, TEXT("WriteFile failed with error: %d"), dwError);
        return false;
    }
    
    FlushFileBuffers((HANDLE)PipeHandle);
    return true;
#else
    return false;
#endif
}

bool FAtlasTransportServer::ParseRequest(const FString& JsonString, FTransportRequest& OutRequest)
{
    TSharedPtr<FJsonObject> JsonObject;
    TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonString);
    
    if (!FJsonSerializer::Deserialize(Reader, JsonObject) || !JsonObject.IsValid())
    {
        UE_LOG(LogAtlasTransport, Error, TEXT("Failed to parse JSON request"));
        return false;
    }
    
    // Extract required fields
    if (!JsonObject->TryGetStringField(TEXT("request_id"), OutRequest.RequestId) ||
        !JsonObject->TryGetStringField(TEXT("operation_name"), OutRequest.OperationName) ||
        !JsonObject->TryGetStringField(TEXT("capability"), OutRequest.Capability) ||
        !JsonObject->TryGetStringField(TEXT("kind"), OutRequest.Kind) ||
        !JsonObject->TryGetStringField(TEXT("authorization_id"), OutRequest.AuthorizationId))
    {
        UE_LOG(LogAtlasTransport, Error, TEXT("Missing required fields in request"));
        return false;
    }
    
    // Extract entity_ids as a strict array of strings. Do not silently drop invalid entries.
    if (!JsonObject->TryGetStringArrayField(TEXT("entity_ids"), OutRequest.EntityIds))
    {
        UE_LOG(LogAtlasTransport, Error, TEXT("Missing or invalid entity_ids field"));
        return false;
    }
    
    // Arguments are optional at parse time so a malformed-but-correlatable
    // request can still receive a structured validation error response.
    const TSharedPtr<FJsonObject>* ArgumentsObject;
    if (JsonObject->TryGetObjectField(TEXT("arguments"), ArgumentsObject))
    {
        OutRequest.Arguments = *ArgumentsObject;
    }
    
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
    
    // Entity IDs array
    TArray<TSharedPtr<FJsonValue>> EntityIdsArray;
    for (const FString& EntityId : Response.EntityIds)
    {
        EntityIdsArray.Add(MakeShareable(new FJsonValueString(EntityId)));
    }
    JsonObject->SetArrayField(TEXT("entity_ids"), EntityIdsArray);
    
    // Observed state
    if (Response.ObservedState.IsValid())
    {
        JsonObject->SetObjectField(TEXT("observed_state"), Response.ObservedState);
    }
    else
    {
        JsonObject->SetObjectField(TEXT("observed_state"), MakeShareable(new FJsonObject));
    }
    
    FString OutputString;
    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
    FJsonSerializer::Serialize(JsonObject.ToSharedRef(), Writer);
    
    return OutputString;
}

bool FAtlasTransportServer::ValidateRequest(const FTransportRequest& Request, FString& OutError)
{
    if (Request.RequestId.IsEmpty())
    {
        OutError = TEXT("request_id cannot be empty");
        return false;
    }

    if (Request.AuthorizationId.IsEmpty() || Request.AuthorizationId.TrimStartAndEnd().IsEmpty())
    {
        OutError = TEXT("authorization_id cannot be empty");
        return false;
    }
    
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
    if (!Request.Arguments->TryGetStringArrayField(TEXT("entity_ids"), ArgumentEntityIds))
    {
        OutError = TEXT("arguments.entity_ids must be an array of strings");
        return false;
    }

    if (ArgumentEntityIds.Num() != Request.EntityIds.Num())
    {
        OutError = TEXT("arguments.entity_ids must match entity_ids");
        return false;
    }

    for (int32 Index = 0; Index < Request.EntityIds.Num(); ++Index)
    {
        if (ArgumentEntityIds[Index] != Request.EntityIds[Index])
        {
            OutError = TEXT("arguments.entity_ids must match entity_ids");
            return false;
        }
    }

    if (Request.OperationName == TEXT("inspect_target_actors"))
    {
        if (Request.Capability != TEXT("inspect_actor"))
        {
            OutError = FString::Printf(TEXT("Unsupported capability for inspect_target_actors: %s"), *Request.Capability);
            return false;
        }
        if (Request.Kind != TEXT("read"))
        {
            OutError = FString::Printf(TEXT("Unsupported kind for inspect_target_actors: %s"), *Request.Kind);
            return false;
        }
        return true;
    }

    if (Request.OperationName == TEXT("set_actor_location"))
    {
        if (Request.Capability != TEXT("modify_actor"))
        {
            OutError = FString::Printf(TEXT("Unsupported capability for set_actor_location: %s"), *Request.Capability);
            return false;
        }
        if (Request.Kind != TEXT("write"))
        {
            OutError = FString::Printf(TEXT("Unsupported kind for set_actor_location: %s"), *Request.Kind);
            return false;
        }
        if (Request.EntityIds.Num() != 1)
        {
            OutError = TEXT("set_actor_location requires exactly one entity_id");
            return false;
        }

        const TSharedPtr<FJsonObject>* LocationObject = nullptr;
        if (!Request.Arguments->TryGetObjectField(TEXT("location"), LocationObject) ||
            LocationObject == nullptr || !LocationObject->IsValid())
        {
            OutError = TEXT("arguments.location must be an object");
            return false;
        }

        double X = 0.0;
        double Y = 0.0;
        double Z = 0.0;
        if (!(*LocationObject)->TryGetNumberField(TEXT("x"), X) ||
            !(*LocationObject)->TryGetNumberField(TEXT("y"), Y) ||
            !(*LocationObject)->TryGetNumberField(TEXT("z"), Z))
        {
            OutError = TEXT("arguments.location must contain numeric x, y, and z");
            return false;
        }
        return true;
    }

    OutError = FString::Printf(TEXT("Unsupported operation_name: %s"), *Request.OperationName);
    return false;
}

bool FAtlasTransportServer::ExecuteRequest(const FTransportRequest& Request, FTransportResponse& OutResponse)
{
    // Initialize response
    OutResponse.RequestId = Request.RequestId;
    OutResponse.OperationName = Request.OperationName;
    OutResponse.EntityIds = Request.EntityIds;
    OutResponse.Source = TEXT("unreal-editor-atlas-transport");
    
    if (Request.OperationName == TEXT("inspect_target_actors") ||
        Request.OperationName == TEXT("set_actor_location"))
    {
        // Create shared state that will outlive this function call
        TSharedPtr<FGameThreadExecutionState> SharedState = MakeShareable(new FGameThreadExecutionState());
        SharedState->Request = Request;
        SharedState->Response.RequestId = Request.RequestId;
        SharedState->Response.OperationName = Request.OperationName;
        SharedState->Response.EntityIds = Request.EntityIds;
        SharedState->Response.Source = TEXT("unreal-editor-atlas-transport");
        
        // Queue execution on game thread with shared state
        AsyncTask(ENamedThreads::GameThread, [SharedState]()
        {
            FAtlasTransportServer::ExecuteOnGameThread(SharedState);
        });
        
        // Wait for completion with timeout
        const uint32 TimeoutMs = 5000; // 5 seconds
        bool bEventTriggered = SharedState->CompletionEvent->Wait(TimeoutMs);
        
        if (bStopRequested)
        {
            OutResponse.bSuccess = false;
            OutResponse.Error = TEXT("Operation cancelled during shutdown");
            return false;
        }
        
        if (!bEventTriggered)
        {
            OutResponse.bSuccess = false;
            OutResponse.Error = TEXT("Operation timed out");
            return false;
        }
        
        // Copy results from shared state
        OutResponse = SharedState->Response;
        return SharedState->bSuccess;
    }
    
    OutResponse.bSuccess = false;
    OutResponse.Error = FString::Printf(TEXT("Unsupported operation: %s"), *Request.OperationName);
    return false;
}

void FAtlasTransportServer::ExecuteOnGameThread(TSharedPtr<FGameThreadExecutionState> SharedState)
{
    // Ensure we're on the game thread
    if (!IsInGameThread())
    {
        SharedState->Response.bSuccess = false;
        SharedState->Response.Error = TEXT("ExecuteOnGameThread must be called on game thread");
        SharedState->bSuccess = false;
        SharedState->bCompleted = true;
        SharedState->CompletionEvent->Trigger();
        return;
    }
    
    // Check if engine is still valid before accessing world
    if (!GEngine || IsEngineExitRequested())
    {
        SharedState->Response.bSuccess = false;
        SharedState->Response.Error = TEXT("Engine shutting down");
        SharedState->bSuccess = false;
        SharedState->bCompleted = true;
        SharedState->CompletionEvent->Trigger();
        return;
    }
    
    bool bTaskSuccess = false;
    if (SharedState->Request.OperationName == TEXT("inspect_target_actors"))
    {
        bTaskSuccess = InspectTargetActors(
            SharedState->Request.EntityIds,
            SharedState->ObservedState,
            SharedState->Error);
    }
    else if (SharedState->Request.OperationName == TEXT("set_actor_location"))
    {
        bTaskSuccess = SetActorLocation(
            SharedState->Request,
            SharedState->ObservedState,
            SharedState->Error);
    }
    else
    {
        SharedState->Error = FString::Printf(
            TEXT("Unsupported operation: %s"),
            *SharedState->Request.OperationName);
    }
    
    if (bTaskSuccess && SharedState->Error.IsEmpty())
    {
        SharedState->Response.bSuccess = true;
        SharedState->Response.ObservedState = SharedState->ObservedState;
        SharedState->bSuccess = true;
    }
    else
    {
        SharedState->Response.bSuccess = false;
        SharedState->Response.Error = SharedState->Error.IsEmpty() ? TEXT("Unknown error during Unreal operation") : SharedState->Error;
        SharedState->bSuccess = false;
    }
    
    // Signal completion
    SharedState->bCompleted = true;
    SharedState->CompletionEvent->Trigger();
}

bool FAtlasTransportServer::SetActorLocation(const FTransportRequest& Request, TSharedPtr<FJsonObject>& OutObservedState, FString& OutError)
{
    if (!IsInGameThread())
    {
        OutError = TEXT("SetActorLocation must be called on game thread");
        return false;
    }
    
    if (!GEngine || IsEngineExitRequested())
    {
        OutError = TEXT("Engine not available or shutting down");
        return false;
    }

    if (Request.EntityIds.Num() != 1 || !Request.Arguments.IsValid())
    {
        OutError = TEXT("set_actor_location requires exactly one entity_id and valid arguments");
        return false;
    }

    const TSharedPtr<FJsonObject>* LocationObject = nullptr;
    if (!Request.Arguments->TryGetObjectField(TEXT("location"), LocationObject) ||
        LocationObject == nullptr || !LocationObject->IsValid())
    {
        OutError = TEXT("arguments.location must be an object");
        return false;
    }

    double X = 0.0;
    double Y = 0.0;
    double Z = 0.0;
    if (!(*LocationObject)->TryGetNumberField(TEXT("x"), X) ||
        !(*LocationObject)->TryGetNumberField(TEXT("y"), Y) ||
        !(*LocationObject)->TryGetNumberField(TEXT("z"), Z))
    {
        OutError = TEXT("arguments.location must contain numeric x, y, and z");
        return false;
    }

    AActor* Actor = FindActorByEntityId(Request.EntityIds[0]);
    if (!Actor || !IsValid(Actor))
    {
        OutError = FString::Printf(TEXT("Actor not found for entity_id: %s"), *Request.EntityIds[0]);
        return false;
    }

    const FVector NewLocation(static_cast<float>(X), static_cast<float>(Y), static_cast<float>(Z));
    Actor->SetActorLocation(NewLocation, false, nullptr, ETeleportType::TeleportPhysics);

    // Return independent post-write observation so the caller receives
    // evidence of the state that Unreal actually holds after mutation.
    return InspectTargetActors(Request.EntityIds, OutObservedState, OutError);
}

bool FAtlasTransportServer::InspectTargetActors(const TArray<FString>& EntityIds, TSharedPtr<FJsonObject>& OutObservedState, FString& OutError)
{
    if (!IsInGameThread())
    {
        OutError = TEXT("InspectTargetActors must be called on game thread");
        return false;
    }
    
    if (!GEngine || IsEngineExitRequested())
    {
        OutError = TEXT("Engine not available or shutting down");
        return false;
    }
    
    UWorld* World = nullptr;
    if (GEngine->GetWorldContexts().Num() > 0)
    {
        World = GEngine->GetWorldContexts()[0].World();
    }
    
    if (!World || !IsValid(World))
    {
        OutError = TEXT("No valid world found");
        return false;
    }
    
    TSharedPtr<FJsonObject> ObservedState = MakeShareable(new FJsonObject);
    
    for (const FString& EntityId : EntityIds)
    {
        AActor* Actor = FindActorByEntityId(EntityId);
        if (!Actor || !IsValid(Actor))
        {
            OutError = FString::Printf(TEXT("Actor not found for entity_id: %s"), *EntityId);
            return false;
        }
        
        // Create actor observation
        TSharedPtr<FJsonObject> ActorData = MakeShareable(new FJsonObject);
        
        ActorData->SetStringField(TEXT("entity_id"), EntityId);
        ActorData->SetStringField(TEXT("actor_name"), Actor->GetName());
        ActorData->SetStringField(TEXT("actor_class"), Actor->GetClass()->GetName());
        
        // Location
        FVector Location = Actor->GetActorLocation();
        TSharedPtr<FJsonObject> LocationObj = MakeShareable(new FJsonObject);
        LocationObj->SetNumberField(TEXT("x"), Location.X);
        LocationObj->SetNumberField(TEXT("y"), Location.Y);
        LocationObj->SetNumberField(TEXT("z"), Location.Z);
        ActorData->SetObjectField(TEXT("location"), LocationObj);
        
        // Rotation
        FRotator Rotation = Actor->GetActorRotation();
        TSharedPtr<FJsonObject> RotationObj = MakeShareable(new FJsonObject);
        RotationObj->SetNumberField(TEXT("pitch"), Rotation.Pitch);
        RotationObj->SetNumberField(TEXT("yaw"), Rotation.Yaw);
        RotationObj->SetNumberField(TEXT("roll"), Rotation.Roll);
        ActorData->SetObjectField(TEXT("rotation"), RotationObj);
        
        ObservedState->SetObjectField(EntityId, ActorData);
    }
    
    OutObservedState = ObservedState;
    return true;
}

AActor* FAtlasTransportServer::FindActorByEntityId(const FString& EntityId)
{
    if (!IsInGameThread())
    {
        return nullptr;
    }
    
    if (!GEngine || IsEngineExitRequested())
    {
        return nullptr;
    }
    
    UWorld* World = nullptr;
    if (GEngine->GetWorldContexts().Num() > 0)
    {
        World = GEngine->GetWorldContexts()[0].World();
    }
    
    if (!World || !IsValid(World))
    {
        return nullptr;
    }
    
    FString TagToFind = FString::Printf(TEXT("atlas_entity:%s"), *EntityId);
    
    for (TActorIterator<AActor> ActorItr(World); ActorItr; ++ActorItr)
    {
        AActor* Actor = *ActorItr;
        if (Actor && IsValid(Actor) && Actor->Tags.Contains(FName(*TagToFind)))
        {
            return Actor;
        }
    }
    
    return nullptr;
}
