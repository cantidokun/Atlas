#pragma once

#include "CoreMinimal.h"
#include "Containers/Ticker.h"
#include "Modules/ModuleInterface.h"
#include "Modules/ModuleManager.h"

DECLARE_LOG_CATEGORY_EXTERN(LogAtlasTransport, Log, All);

class FAtlasUnrealTransportModule : public IModuleInterface
{
public:
    virtual void StartupModule() override;
    virtual void ShutdownModule() override;

    /** Access live transport ingress queue if running */
    TSharedPtr<class FAtlasLiveIngressQueue> GetLiveIngressQueue() const { return LiveIngressQueue; }

    /** Access live TCP listener if running */
    TSharedPtr<class FAtlasLiveTcpListener> GetLiveTcpListener() const { return LiveTcpListener; }

    /** Access live GameThread pump if running */
    TSharedPtr<class FAtlasLiveGameThreadPump> GetLiveGameThreadPump() const { return LiveGameThreadPump; }

    /** Access live effect registry if running */
    TSharedPtr<class FAtlasLiveEffectRegistry> GetLiveEffectRegistry() const { return LiveEffectRegistry; }

private:
    bool EnsureSequencerFixture(float DeltaTime);

    class FAtlasTransportServer* TransportServer = nullptr;
    FTSTicker::FDelegateHandle SequencerFixtureTickerHandle;

    // Atlas Live Streaming Transport Subsystem
    TSharedPtr<class FAtlasLiveIngressQueue> LiveIngressQueue;
    TSharedPtr<class FAtlasLiveTcpListener> LiveTcpListener;
    TSharedPtr<class FAtlasLiveGameThreadPump> LiveGameThreadPump;
    TSharedPtr<class FAtlasLiveEffectRegistry> LiveEffectRegistry;
};
