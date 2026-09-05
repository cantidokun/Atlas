#include "AtlasLiveImpactAccentHandler.h"
#include "AtlasUnrealTransport.h"
#include "GameFramework/Actor.h"
#include "Components/SceneComponent.h"
#include "Components/PointLightComponent.h"

const FName FAtlasLiveImpactAccentHandler::ImpactAccentComponentTag(TEXT("atlas_live_impact_accent_light"));
const FString FAtlasLiveImpactAccentHandler::ActiveVfxTagPrefix(TEXT("atlas_vfx_active:impact_accent:"));

FAtlasLiveImpactAccentHandler::FAtlasLiveImpactAccentHandler(
    FLinearColor InFlashColor,
    float InBaseIntensity,
    float InAttenuationRadius)
    : FlashColor(InFlashColor)
    , BaseIntensity(InBaseIntensity)
    , AttenuationRadius(InAttenuationRadius)
{
}

bool FAtlasLiveImpactAccentHandler::Execute(
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

    // 1. Clean up any existing impact light on this actor first
    Cleanup(TargetActor);

    // 2. Create transient point light component attached to target actor root
    UPointLightComponent* LightComp = NewObject<UPointLightComponent>(
        TargetActor,
        TEXT("AtlasLiveImpactLight"),
        RF_Transient);

    if (!LightComp)
    {
        return false;
    }

    // Configure light parameters scaled by intent intensity
    float IntensityScale = FMath::Clamp(Intent.Intensity, 0.1f, 1.0f);
    LightComp->SetIntensity(BaseIntensity * IntensityScale);
    LightComp->SetLightColor(FlashColor);
    LightComp->SetAttenuationRadius(AttenuationRadius * (0.5f + 0.5f * IntensityScale));
    LightComp->SetCastShadows(false); // Low cost, zero shadow map overhead for transient VFX
    LightComp->ComponentTags.AddUnique(ImpactAccentComponentTag);

    // Set relative location to intent Origin if specified, else root center
    if (!Intent.Origin.IsZero())
    {
        LightComp->SetWorldLocation(Intent.Origin);
    }
    else
    {
        LightComp->SetRelativeLocation(FVector(0.0f, 0.0f, 30.0f)); // Slightly offset above actor origin
    }

    LightComp->AttachToComponent(RootComp, FAttachmentTransformRules::KeepRelativeTransform);
    LightComp->RegisterComponent();

    // 3. Mark actor with active VFX tag
    FString ActiveTag = FString::Printf(TEXT("%s%s"), *ActiveVfxTagPrefix, *Intent.IntentId);
    TargetActor->Tags.AddUnique(FName(*ActiveTag));

    return true;
}

void FAtlasLiveImpactAccentHandler::Cleanup(AActor* TargetActor)
{
    if (!TargetActor || !IsValid(TargetActor))
    {
        return;
    }

    // 1. Destroy any attached impact accent light components
    TArray<UActorComponent*> Comps = TargetActor->GetComponentsByTag(
        UPointLightComponent::StaticClass(),
        ImpactAccentComponentTag);

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

bool FAtlasLiveImpactAccentHandler::HasActiveImpactAccent(AActor* TargetActor)
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

FString FAtlasLiveImpactAccentHandler::GetActiveImpactIntentId(AActor* TargetActor)
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
