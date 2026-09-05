#pragma once

#include "CoreMinimal.h"
#include "AtlasLiveEffectRegistry.h"
#include "Components/PostProcessComponent.h"

/**
 * Concrete effect handler for the IMPACT_FRAME treatment.
 *
 * Implements a high-contrast, flash/desaturation impact frame visual state.
 * Attaches a transient unbound UPostProcessComponent to TargetActor (or active scene),
 * adjusts color contrast, saturation, and bloom to create a punchy cinematic impact frame,
 * tags the actor with "atlas_vfx_active:impact_frame:<INTENT_ID>",
 * and cleans up deterministically on expiration.
 */
class ATLASUNREALTRANSPORT_API FAtlasLiveImpactFrameHandler : public IAtlasLiveEffectHandler
{
public:
    static const FName ImpactFrameComponentTag;
    static const FString ActiveVfxTagPrefix;

    FAtlasLiveImpactFrameHandler(
        float InContrastBoost = 1.8f,
        float InSaturationDrop = 0.2f);

    virtual ~FAtlasLiveImpactFrameHandler() = default;

    virtual bool Execute(
        AActor* TargetActor,
        const FAtlasLiveProductionIntent& Intent,
        float MaxDurationSeconds) override;

    virtual void Cleanup(AActor* TargetActor) override;

    /**
     * Check if a given actor currently has the impact frame active.
     */
    static bool HasActiveImpactFrame(AActor* TargetActor);

    /**
     * Get the active intent ID associated with the actor's current impact frame, if any.
     */
    static FString GetActiveImpactFrameIntentId(AActor* TargetActor);

private:
    float ContrastBoost;
    float SaturationDrop;
};
