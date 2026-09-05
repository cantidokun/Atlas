#pragma once

#include "CoreMinimal.h"
#include "AtlasLiveEffectRegistry.h"
#include "Components/PointLightComponent.h"

/**
 * Concrete effect handler for the IMPACT_ACCENT treatment (e.g. ball strike burst).
 * 
 * Attaches a transient UPointLightComponent to the target actor's root component,
 * sets intense impact color and attenuation scaled by intent intensity,
 * tags the actor with "atlas_vfx_active:impact_accent:<INTENT_ID>",
 * and cleans up deterministically when the effect duration expires or is preempted.
 */
class ATLASUNREALTRANSPORT_API FAtlasLiveImpactAccentHandler : public IAtlasLiveEffectHandler
{
public:
    static const FName ImpactAccentComponentTag;
    static const FString ActiveVfxTagPrefix;

    FAtlasLiveImpactAccentHandler(
        FLinearColor InFlashColor = FLinearColor(1.0f, 0.45f, 0.05f), // High-energy impact orange
        float InBaseIntensity = 10000.0f,
        float InAttenuationRadius = 600.0f);

    virtual ~FAtlasLiveImpactAccentHandler() = default;

    virtual bool Execute(
        AActor* TargetActor,
        const FAtlasLiveProductionIntent& Intent,
        float MaxDurationSeconds) override;

    virtual void Cleanup(AActor* TargetActor) override;

    /**
     * Check if a given actor currently has the impact accent visual component attached.
     */
    static bool HasActiveImpactAccent(AActor* TargetActor);

    /**
     * Get the active intent ID associated with the actor's current impact accent, if any.
     */
    static FString GetActiveImpactIntentId(AActor* TargetActor);

private:
    FLinearColor FlashColor;
    float BaseIntensity;
    float AttenuationRadius;
};
