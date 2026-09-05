#include "AtlasLiveImpactFrameHandler.h"
#include "AtlasUnrealTransport.h"
#include "GameFramework/Actor.h"
#include "Components/SceneComponent.h"
#include "Components/PostProcessComponent.h"

const FName FAtlasLiveImpactFrameHandler::ImpactFrameComponentTag(TEXT("atlas_live_impact_frame_postprocess"));
const FString FAtlasLiveImpactFrameHandler::ActiveVfxTagPrefix(TEXT("atlas_vfx_active:impact_frame:"));

FAtlasLiveImpactFrameHandler::FAtlasLiveImpactFrameHandler(
    float InContrastBoost,
    float InSaturationDrop)
    : ContrastBoost(InContrastBoost)
    , SaturationDrop(InSaturationDrop)
{
}

bool FAtlasLiveImpactFrameHandler::Execute(
    AActor* TargetActor,
    const FAtlasLiveProductionIntent& Intent,
    float MaxDurationSeconds)
{
    if (!TargetActor || !IsValid(TargetActor))
    {
        return false;
    }

    USceneComponent* RootComp = TargetActor->GetRootComponent();
    if (!RootComp)
    {
        return false;
    }

    // 1. Clean up existing impact frame on this actor
    Cleanup(TargetActor);

    // 2. Create transient PostProcessComponent configured for impact frame styling
    UPostProcessComponent* PostProcessComp = NewObject<UPostProcessComponent>(
        TargetActor,
        TEXT("AtlasLiveImpactFramePostProcess"),
        RF_Transient);

    if (!PostProcessComp)
    {
        return false;
    }

    float IntensityScale = FMath::Clamp(Intent.Intensity, 0.1f, 1.0f);

    PostProcessComp->bUnbound = true; // Affects whole viewport frame during impact
    PostProcessComp->Priority = 1000.0f; // High priority override
    PostProcessComp->BlendWeight = 1.0f;

    // Configure PostProcessSettings for high-contrast impact frame:
    // Boost contrast, drop saturation (dramatic anime/manga impact flash styling)
    PostProcessComp->Settings.bOverride_ColorContrast = true;
    PostProcessComp->Settings.ColorContrast = FVector4(
        1.0f + (ContrastBoost - 1.0f) * IntensityScale,
        1.0f + (ContrastBoost - 1.0f) * IntensityScale,
        1.0f + (ContrastBoost - 1.0f) * IntensityScale,
        1.0f);

    PostProcessComp->Settings.bOverride_ColorSaturation = true;
    PostProcessComp->Settings.ColorSaturation = FVector4(
        FMath::Lerp(1.0f, SaturationDrop, IntensityScale),
        FMath::Lerp(1.0f, SaturationDrop, IntensityScale),
        FMath::Lerp(1.0f, SaturationDrop, IntensityScale),
        1.0f);

    PostProcessComp->Settings.bOverride_BloomIntensity = true;
    PostProcessComp->Settings.BloomIntensity = 2.0f * IntensityScale;

    PostProcessComp->ComponentTags.AddUnique(ImpactFrameComponentTag);
    PostProcessComp->AttachToComponent(RootComp, FAttachmentTransformRules::KeepRelativeTransform);
    PostProcessComp->RegisterComponent();

    // 3. Mark actor with active VFX tag
    FString ActiveTag = FString::Printf(TEXT("%s%s"), *ActiveVfxTagPrefix, *Intent.IntentId);
    TargetActor->Tags.AddUnique(FName(*ActiveTag));

    return true;
}

void FAtlasLiveImpactFrameHandler::Cleanup(AActor* TargetActor)
{
    if (!TargetActor || !IsValid(TargetActor))
    {
        return;
    }

    // 1. Destroy post process component
    TArray<UActorComponent*> Comps = TargetActor->GetComponentsByTag(
        UPostProcessComponent::StaticClass(),
        ImpactFrameComponentTag);

    for (UActorComponent* Comp : Comps)
    {
        if (Comp && IsValid(Comp))
        {
            Comp->UnregisterComponent();
            Comp->DestroyComponent();
        }
    }

    // 2. Remove active VFX tags
    for (int32 i = TargetActor->Tags.Num() - 1; i >= 0; --i)
    {
        FString TagStr = TargetActor->Tags[i].ToString();
        if (TagStr.StartsWith(ActiveVfxTagPrefix))
        {
            TargetActor->Tags.RemoveAt(i);
        }
    }
}

bool FAtlasLiveImpactFrameHandler::HasActiveImpactFrame(AActor* TargetActor)
{
    if (!TargetActor || !IsValid(TargetActor))
    {
        return false;
    }

    for (const FName& Tag : TargetActor->Tags)
    {
        if (Tag.ToString().StartsWith(ActiveVfxTagPrefix))
        {
            return true;
        }
    }
    return false;
}

FString FAtlasLiveImpactFrameHandler::GetActiveImpactFrameIntentId(AActor* TargetActor)
{
    if (!TargetActor || !IsValid(TargetActor))
    {
        return FString();
    }

    for (const FName& Tag : TargetActor->Tags)
    {
        FString TagStr = Tag.ToString();
        if (TagStr.StartsWith(ActiveVfxTagPrefix))
        {
            return TagStr.Mid(ActiveVfxTagPrefix.Len());
        }
    }
    return FString();
}
