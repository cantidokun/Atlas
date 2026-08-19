#include "AtlasUnrealTransport.h"
#include "AtlasTransportServer.h"
#include "Modules/ModuleManager.h"

DEFINE_LOG_CATEGORY(LogAtlasTransport);

void FAtlasUnrealTransportModule::StartupModule()
{
    UE_LOG(LogAtlasTransport, Log, TEXT("AtlasUnrealTransport module starting up"));
    
    TransportServer = new FAtlasTransportServer();
    if (!TransportServer->StartServer())
    {
        UE_LOG(LogAtlasTransport, Error, TEXT("Failed to start Atlas transport server"));
        delete TransportServer;
        TransportServer = nullptr;
    }
    else
    {
        UE_LOG(LogAtlasTransport, Log, TEXT("Atlas transport server started successfully"));
    }
}

void FAtlasUnrealTransportModule::ShutdownModule()
{
    UE_LOG(LogAtlasTransport, Log, TEXT("AtlasUnrealTransport module shutting down"));
    
    if (TransportServer)
    {
        TransportServer->StopServer();
        delete TransportServer;
        TransportServer = nullptr;
    }
    
    UE_LOG(LogAtlasTransport, Log, TEXT("AtlasUnrealTransport module shutdown complete"));
}

IMPLEMENT_MODULE(FAtlasUnrealTransportModule, AtlasUnrealTransport)
