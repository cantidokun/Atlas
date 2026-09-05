#include "AtlasLiveSpeedTrailHandler.h"
#include "AtlasUnrealTransport.h"
#include "GameFramework/Actor.h"
#include "Components/SceneComponent.h"
#include "Components/LineBatchComponent.h"

const FName FAtlasLiveSpeedTrailHandler::SpeedTrailComponentTag(TEXT("atlas_live_speed_trail_comp"));
const FString FAtlasLiveSpeedTrailHandler::ActiveVfxTagPrefix(TEXT("atlas_vfx_active:speed_trail:"));

FAtlasLiveSpeedTrailHandler::FAtlasLiveSpeedTrailHandler(
    FLinearColor InTrailColor,
    float InBaseLength,
    float InThickness)
    : TrailColor(InTrailColor)
    , BaseLength(InBaseLength)
    , Thickness(InThickness)
{
}

bool FAtlasLiveSpeedTrailHandler::Execute(
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

    // 1. Clean up existing trail on this actor
    Cleanup(TargetActor);

    // 2. Create transient LineBatchComponent for deterministic directional trail drawing
    ULineBatchComponent* LineComp = NewObject<ULineBatchComponent>(
        TargetActor,
        TEXT("AtlasLiveSpeedTrailLineBatch"),
        RF_Transient);

    if (!LineComp)
    {
        return false;
    }

    LineComp->ComponentTags.AddUnique(SpeedTrailComponentTag);
    LineComp->AttachToComponent(RootComp, FAttachmentTransformRules::KeepRelativeTransform);
    LineComp->RegisterComponent();

    // 3. Determine directional trail segment
    FVector StartLoc = TargetActor->GetActorLocation();
    FVector Direction = Intent.Direction.GetSafeNormal();
    if (Direction.IsZero())
    {
        Direction = FVector(-1.0f, 0.0f, 0.0f); // Default backward trail along -X
    }

    // Trail extends backwards from motion direction
    float IntensityScale = FMath::Clamp(Intent.Intensity, 0.1f, 1.0f);
    float TrailLength = BaseLength * (0.5f + 0.5f * IntensityScale);
    FVector EndLoc = StartLoc - (Direction * TrailLength);

    // Draw main trail line and supporting energy lines
    LineComp->DrawLine(StartLoc, EndLoc, TrailColor, 0, Thickness * IntensityScale, MaxDurationSeconds);
    LineComp->DrawPoint(StartLoc, TrailColor, Thickness * 2.0f * IntensityScale, 0, MaxDurationSeconds);
    LineComp->DrawPoint(EndLoc, TrailColor * 0.5f, Thickness * IntensityScale, 0, MaxDurationSeconds);

    // 4. Mark actor with active VFX tag
    FString ActiveTag = FString::Printf(TEXT("%s%s"), *ActiveVfxTagPrefix, *Intent.IntentId);
    TargetActor->Tags.AddUnique(FName(*ActiveTag));

    return true;
}

void FAtlasLiveSpeedTrailHandler::Cleanup(AActor* TargetActor)
{
    if (!TargetActor || !IsValid(TargetActor))
    {
        return;
    }

    // 1. Destroy line batch components
    TArray<UActorComponent*> Comps = TargetActor->GetComponentsByTag(
        ULineBatchComponent::StaticClass(),
        SpeedTrailComponentTag);

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

bool FAtlasLiveSpeedTrailHandler::HasActiveSpeedTrail(AActor* TargetActor)
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

FString FAtlasLiveSpeedTrailHandler::GetActiveTrailIntentId(AActor* TargetActor)
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
