#pragma once

#include "CoreMinimal.h"
#include "Commandlets/Commandlet.h"
#include "AtlasBlueprintFixtureCommandlet.generated.h"

UCLASS()
class UAtlasBlueprintFixtureCommandlet : public UCommandlet
{
    GENERATED_BODY()

public:
    UAtlasBlueprintFixtureCommandlet();

    virtual int32 Main(const FString& Params) override;
};
