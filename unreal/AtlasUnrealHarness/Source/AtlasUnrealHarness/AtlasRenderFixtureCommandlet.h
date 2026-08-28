#pragma once

#include "CoreMinimal.h"
#include "Commandlets/Commandlet.h"
#include "AtlasRenderFixtureCommandlet.generated.h"

UCLASS()
class ATLASUNREALHARNESS_API UAtlasRenderFixtureCommandlet : public UCommandlet
{
    GENERATED_BODY()

public:
    UAtlasRenderFixtureCommandlet();

    virtual int32 Main(const FString& Params) override;
};
