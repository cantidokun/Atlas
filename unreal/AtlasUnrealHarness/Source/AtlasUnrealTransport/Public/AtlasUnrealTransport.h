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

private:
    bool EnsureSequencerFixture(float DeltaTime);

    class FAtlasTransportServer* TransportServer = nullptr;
    FTSTicker::FDelegateHandle SequencerFixtureTickerHandle;
};
