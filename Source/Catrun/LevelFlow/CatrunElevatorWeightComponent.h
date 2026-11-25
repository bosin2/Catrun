#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "CatrunElevatorWeightComponent.generated.h"

class ACharacter;
class ATriggerBox;
class UCharacterMovementComponent;

namespace CatrunElevatorWeight
{
    struct FSpringState
    {
        float Offset = 0.f;
        float Velocity = 0.f;
    };

    /** Bounded exact damped-spring integration; zero time leaves state unchanged. */
    CATRUN_API void AdvanceSpring(FSpringState& State, float Target, float FrequencyHz,
        float DampingRatio, float DeltaSeconds, float MinimumOffset, float MaximumOffset);
}

/** A small vertical response of the docked cabin, independent of the one-shot cinematic. */
UCLASS(ClassGroup=(Catrun), meta=(BlueprintSpawnableComponent))
class CATRUN_API UCatrunElevatorWeightComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UCatrunElevatorWeightComponent();
    virtual void TickComponent(float DeltaSeconds, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

    /** Moving cabin parts only. Exclude the fixed guide rails, landing and cameras. */
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Weight")
    TArray<TObjectPtr<AActor>> MovingActors;

    /** Walkable cabin floor actors only; side walls/roof must not count as a rider's support. */
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Weight")
    TArray<TObjectPtr<AActor>> SupportActors;

    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Weight")
    TObjectPtr<ATriggerBox> OccupancyVolume;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Elevator|Weight", meta=(ClampMin="0", ClampMax="10", Units="cm"))
    float LoadedSag = 4.f;

    /** Reference mass is normalized to the existing character movement mass, without editing the cat. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Elevator|Weight", meta=(ClampMin="0.01", Units="kg"))
    float ReferenceMass = 100.f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Elevator|Weight", meta=(ClampMin="0", ClampMax="12", Units="cm"))
    float MaximumSag = 6.f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Elevator|Weight", meta=(ClampMin="0", ClampMax="3", Units="cm"))
    float MaximumRise = 1.25f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Elevator|Weight", meta=(ClampMin="0.1", ClampMax="4"))
    float SpringFrequency = 1.15f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Elevator|Weight", meta=(ClampMin="0.05", ClampMax="1"))
    float DampingRatio = .5f;

    /** Captures the current posed cabin; CurrentOffset is its existing displacement from neutral. */
    UFUNCTION(BlueprintCallable, Category="Elevator|Weight")
    void StartResponse(float CurrentOffset = 0.f);

    UFUNCTION(BlueprintCallable, Category="Elevator|Weight")
    void StopResponse(bool bRestoreNeutral = false);

    /** Explicitly admits the director-owned MOVE_None cat, still requiring feet contact with the floor. */
    UFUNCTION(BlueprintCallable, Category="Elevator|Weight")
    void SetScriptedRider(ACharacter* Rider);

    UFUNCTION(BlueprintPure, Category="Elevator|Weight")
    bool IsResponding() const { return bResponding; }

    UFUNCTION(BlueprintPure, Category="Elevator|Weight")
    float GetCurrentOffset() const { return Spring.Offset; }

    UFUNCTION(BlueprintPure, Category="Elevator|Weight")
    float GetTargetOffset() const { return TargetOffset; }

    UFUNCTION(BlueprintPure, Category="Elevator|Weight")
    float GetSupportedMassKg() const { return SupportedMassKg; }

    UFUNCTION(BlueprintPure, Category="Elevator|Weight")
    bool HasSupportedRider(const ACharacter* Rider) const;

private:
    bool IsInsideVolume(const ACharacter& Rider) const;
    bool IsFloorActor(const AActor* Actor) const;
    void RefreshRiders();
    void ApplyOffset();
    void RemoveMovementPrerequisites();

    TMap<TWeakObjectPtr<AActor>, FTransform> NeutralTransforms;
    TSet<TWeakObjectPtr<UCharacterMovementComponent>> OrderedMovements;
    TWeakObjectPtr<ACharacter> ScriptedRider;
    CatrunElevatorWeight::FSpringState Spring;
    float TargetOffset = 0.f;
    float SupportedMassKg = 0.f;
    bool bResponding = false;
};
