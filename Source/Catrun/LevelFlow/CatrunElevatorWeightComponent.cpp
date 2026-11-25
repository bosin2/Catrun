#include "CatrunElevatorWeightComponent.h"

#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Engine/TriggerBox.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"

void CatrunElevatorWeight::AdvanceSpring(FSpringState& State, float Target, float FrequencyHz,
    float DampingRatio, float DeltaSeconds, float MinimumOffset, float MaximumOffset)
{
    if (!FMath::IsFinite(DeltaSeconds) || DeltaSeconds <= 0.f) return;
    if (!FMath::IsFinite(State.Offset) || !FMath::IsFinite(State.Velocity)) State = {};
    if (!FMath::IsFinite(Target) || !FMath::IsFinite(FrequencyHz) || !FMath::IsFinite(DampingRatio)
        || !FMath::IsFinite(MinimumOffset) || !FMath::IsFinite(MaximumOffset) || MinimumOffset > MaximumOffset) return;
    Target = FMath::Clamp(Target, MinimumOffset, MaximumOffset);
    const double Omega = 2.0 * PI * FMath::Clamp(FrequencyHz, .1f, 4.f);
    const double Zeta = FMath::Clamp(DampingRatio, .05f, 1.f);
    const double Time = DeltaSeconds;
    const double X = State.Offset - Target;
    const double V = State.Velocity;
    const double Decay = FMath::Exp(-Zeta * Omega * Time);
    double NewX, NewV;
    if (Zeta < .999)
    {
        const double W = Omega * FMath::Sqrt(1.0 - Zeta * Zeta);
        const double C = FMath::Cos(W * Time), S = FMath::Sin(W * Time);
        NewX = Decay * (X * C + (V + Zeta * Omega * X) * S / W);
        NewV = Decay * (V * C - (Omega * Omega * X + Zeta * Omega * V) * S / W);
    }
    else
    {
        const double Linear = V + Omega * X;
        NewX = Decay * (X + Linear * Time);
        NewV = Decay * (V - Omega * Linear * Time);
    }
    State.Offset = FMath::Clamp(static_cast<float>(Target + NewX), MinimumOffset, MaximumOffset);
    State.Velocity = static_cast<float>(NewV);
    if ((State.Offset <= MinimumOffset && State.Velocity < 0.f)
        || (State.Offset >= MaximumOffset && State.Velocity > 0.f)) State.Velocity = 0.f;
    if (FMath::Abs(State.Offset - Target) < .001f && FMath::Abs(State.Velocity) < .005f)
    {
        State.Offset = Target;
        State.Velocity = 0.f;
    }
}

UCatrunElevatorWeightComponent::UCatrunElevatorWeightComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.bStartWithTickEnabled = false;
    PrimaryComponentTick.TickGroup = TG_PrePhysics;
    PrimaryComponentTick.bTickEvenWhenPaused = false;
}

void UCatrunElevatorWeightComponent::StartResponse(float CurrentOffset)
{
    if (bResponding || !GetWorld() || !FMath::IsFinite(CurrentOffset)) return;
    NeutralTransforms.Reset();
    for (AActor* Actor : MovingActors)
    {
        if (!IsValid(Actor) || Actor->GetWorld() != GetWorld()) continue;
        // Attached pieces already follow the nearest authored moving ancestor.
        bool bMovingParent = false;
        for (AActor* Parent = Actor->GetAttachParentActor(); Parent; Parent = Parent->GetAttachParentActor())
            if (MovingActors.Contains(Parent)) { bMovingParent = true; break; }
        if (bMovingParent) continue;
        FTransform Neutral = Actor->GetActorTransform();
        Neutral.AddToTranslation(FVector(0., 0., -CurrentOffset));
        NeutralTransforms.Add(Actor, Neutral);
        if (auto* Root = Actor->GetRootComponent()) Root->SetMobility(EComponentMobility::Movable);
    }
    if (NeutralTransforms.IsEmpty() || SupportActors.IsEmpty()) return;
    Spring = {CurrentOffset, 0.f};
    TargetOffset = CurrentOffset;
    SupportedMassKg = 0.f;
    bResponding = true;
    SetComponentTickEnabled(true);
}

void UCatrunElevatorWeightComponent::SetScriptedRider(ACharacter* Rider)
{
    ScriptedRider = IsValid(Rider) && Rider->GetWorld() == GetWorld() ? Rider : nullptr;
}

void UCatrunElevatorWeightComponent::StopResponse(bool bRestoreNeutral)
{
    if (bRestoreNeutral && bResponding)
    {
        Spring = {};
        ApplyOffset();
    }
    bResponding = false;
    SetComponentTickEnabled(false);
    RemoveMovementPrerequisites();
    NeutralTransforms.Reset();
    ScriptedRider.Reset();
    SupportedMassKg = TargetOffset = 0.f;
}

void UCatrunElevatorWeightComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    StopResponse(false);
    Super::EndPlay(EndPlayReason);
}

bool UCatrunElevatorWeightComponent::IsInsideVolume(const ACharacter& Rider) const
{
    const auto* Box = OccupancyVolume ? Cast<UBoxComponent>(OccupancyVolume->GetCollisionComponent()) : nullptr;
    if (!Box) return true; // The exact supporting floor remains authoritative without an optional broadphase box.
    const FVector Local = Box->GetComponentTransform().InverseTransformPosition(Rider.GetActorLocation()).GetAbs();
    const FVector Extent = Box->GetUnscaledBoxExtent();
    return Local.X <= Extent.X && Local.Y <= Extent.Y && Local.Z <= Extent.Z + MaximumSag + MaximumRise;
}

bool UCatrunElevatorWeightComponent::IsFloorActor(const AActor* Actor) const
{
    return IsValid(Actor) && SupportActors.Contains(Actor);
}

bool UCatrunElevatorWeightComponent::HasSupportedRider(const ACharacter* Rider) const
{
    if (!IsValid(Rider) || Rider->GetWorld() != GetWorld() || !IsInsideVolume(*Rider)) return false;
    const auto* Capsule = Rider->GetCapsuleComponent();
    const auto* Movement = Rider->GetCharacterMovement();
    if (!Capsule || !Movement || !Capsule->IsQueryCollisionEnabled()) return false;
    const bool bScripted = Rider == ScriptedRider.Get();
    // A jumping cat passing above the platform contributes no weight.
    if (!bScripted && !Movement->IsMovingOnGround()) return false;
    if (!bScripted && Movement->CurrentFloor.IsWalkableFloor()
        && IsFloorActor(Movement->CurrentFloor.HitResult.GetActor())
        && Movement->CurrentFloor.GetDistanceToFloor() <= 5.f) return true;

    // The cinematic lease deliberately disables CharacterMovement; verify its actual feet instead.
    const FVector Feet = Rider->GetActorLocation() - FVector(0., 0., Capsule->GetScaledCapsuleHalfHeight());
    FCollisionQueryParams Params(SCENE_QUERY_STAT(CatrunElevatorWeight), false, Rider);
    if (GetOwner()) Params.AddIgnoredActor(GetOwner());
    FHitResult Hit;
    return GetWorld()->LineTraceSingleByChannel(Hit, Feet + FVector(0., 0., 3.f), Feet - FVector(0., 0., 7.f),
        ECC_Visibility, Params) && IsFloorActor(Hit.GetActor()) && Hit.ImpactNormal.Z >= Movement->GetWalkableFloorZ();
}

void UCatrunElevatorWeightComponent::RefreshRiders()
{
    SupportedMassKg = 0.f;
    TSet<TWeakObjectPtr<UCharacterMovementComponent>> CurrentMovements;
    for (TActorIterator<ACharacter> It(GetWorld()); It; ++It)
    {
        ACharacter* Rider = *It;
        if (!HasSupportedRider(Rider)) continue;
        auto* Movement = Rider->GetCharacterMovement();
        if (!FMath::IsFinite(Movement->Mass) || Movement->Mass <= 0.f) continue;
        SupportedMassKg += Movement->Mass;
        if (!Movement->IsComponentTickEnabled()) continue;
        CurrentMovements.Add(Movement);
        if (!OrderedMovements.Contains(Movement))
            Movement->PrimaryComponentTick.AddPrerequisite(this, PrimaryComponentTick);
    }
    for (const auto& Weak : OrderedMovements)
        if (!CurrentMovements.Contains(Weak))
            if (auto* Movement = Weak.Get()) Movement->PrimaryComponentTick.RemovePrerequisite(this, PrimaryComponentTick);
    OrderedMovements = MoveTemp(CurrentMovements);
    const float Ratio = SupportedMassKg / FMath::Max(.01f, ReferenceMass);
    TargetOffset = -FMath::Clamp(LoadedSag * Ratio, 0.f, FMath::Max(0.f, MaximumSag));
}

void UCatrunElevatorWeightComponent::RemoveMovementPrerequisites()
{
    for (const auto& Weak : OrderedMovements)
        if (auto* Movement = Weak.Get()) Movement->PrimaryComponentTick.RemovePrerequisite(this, PrimaryComponentTick);
    OrderedMovements.Reset();
}

void UCatrunElevatorWeightComponent::ApplyOffset()
{
    for (const auto& Item : NeutralTransforms)
    {
        AActor* Actor = Item.Key.Get();
        if (!Actor) continue;
        const FVector Position = Item.Value.GetLocation() + FVector(0., 0., Spring.Offset);
        // Movement bases handle the grounded character. Never translate the pawn or its mesh here.
        Actor->SetActorLocation(Position, false, nullptr, ETeleportType::None);
    }
}

void UCatrunElevatorWeightComponent::TickComponent(float DeltaSeconds, ELevelTick TickType,
    FActorComponentTickFunction* ThisTickFunction)
{
    Super::TickComponent(DeltaSeconds, TickType, ThisTickFunction);
    if (!bResponding || !GetWorld() || GetWorld()->IsPaused()) return;
    RefreshRiders();
    const float Previous = Spring.Offset;
    CatrunElevatorWeight::AdvanceSpring(Spring, TargetOffset, SpringFrequency, DampingRatio, DeltaSeconds,
        -FMath::Max(0.f, MaximumSag), FMath::Max(0.f, MaximumRise));
    if (!FMath::IsNearlyEqual(Previous, Spring.Offset, .0001f)) ApplyOffset();
}
