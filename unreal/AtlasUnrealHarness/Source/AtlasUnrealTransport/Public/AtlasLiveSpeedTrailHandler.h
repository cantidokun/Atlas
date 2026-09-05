#pragma once

#include "CoreMinimal.h"
#include "AtlasLiveEffectRegistry.h"
#include "Components/LineBatchComponent.h"

/**
 * Concrete effect handler for the SPEED_TRAIL treatment (e.g. ball or player velocity ribbon/trail).
 *
 * Implements a deterministic, frame-accurate directional trail visual attached to TargetActor.
 * Renders directional visual velocity markers using transient ULineBatchComponent lines/points,
 * tags the actor with "atlas_vfx_active:speed_trail:<INTENT_ID>",
 * and cleans up deterministically on expiration or preemption.
 */
class ATLASUNREALTRANSPORT_API FAtlasLiveSpeedTrailHandler : public IAtlasLiveEffectHandler
{
public:
    static const FName SpeedTrailComponentTag;
    static const FString ActiveVfxTagPrefix;

    FAtlasLiveSpeedTrailHandler(
        FLinearColor InTrailColor = FLinearColor(0.1f, 0.8f, 1.0f), // Neon cyan trail
        float InBaseLength = 200.0f,
        float InThickness = 6.0f);

    virtual ~FAtlasLiveSpeedTrailHandler() = default;

    virtual bool Execute(
        AActor* TargetActor,
        const FAtlasLiveProductionIntent& Intent,
        float MaxDurationSeconds) override;

    virtual void Cleanup(AActor* TargetActor) override;

    /**
     * Check if a given actor currently has the speed trail active.
     */
    static bool HasActiveSpeedTrail(AActor* TargetActor);

    /**
     * Get the active intent ID associated with the actor's current speed trail, if any.
     */
    static FString GetActiveTrailIntentId(AActor* TargetActor);

private:
    FLinearColor TrailColor;
    float BaseLength;
    float Thickness;
};
