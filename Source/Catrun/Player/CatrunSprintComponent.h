#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "CatrunSprintComponent.generated.h"

class ACharacter;

/** Stamina for voluntary grounded sprinting. BP_Cat retains its movement speed selector. */
UCLASS(ClassGroup=(Catrun), meta=(BlueprintSpawnableComponent))
class CATRUN_API UCatrunSprintComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UCatrunSprintComponent();
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

	UFUNCTION(BlueprintPure, Category="Sprint", meta=(DefaultToSelf="Cat"))
	static bool ResolveSprintIntent(ACharacter* Cat, bool bSprintHeld);
	UFUNCTION(BlueprintPure, Category="Sprint")
	float GetStamina() const { return static_cast<float>(Stamina); }
	UFUNCTION(BlueprintPure, Category="Sprint")
	float GetMaxStamina() const { return FMath::Max(1.f, MaxStamina); }
	UFUNCTION(BlueprintPure, Category="Sprint")
	float GetStaminaNormalized() const { return FMath::Clamp(GetStamina() / GetMaxStamina(), 0.f, 1.f); }
	UFUNCTION(BlueprintPure, Category="Sprint")
	bool IsExhausted() const { return bExhausted; }
	UFUNCTION(BlueprintPure, Category="Sprint")
	bool IsSprinting() const;

	// The old run intent remains useful to the separate statue push cap.
	bool IsRunInputHeld() const;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Sprint", meta=(ClampMin="1"))
	float MaxStamina = 100.f;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Sprint", meta=(ClampMin="0"))
	float DrainPerSecond = 20.f;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Sprint", meta=(ClampMin="0"))
	float RecoveryDelaySeconds = 1.f;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Sprint", meta=(ClampMin="0"))
	float RecoveryPerSecond = 25.f;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Sprint", meta=(ClampMin="1"))
	float RearmStamina = 20.f;

private:
	friend class FCatrunSprintResourceTest;
	friend class FCatrunSprintTravelTest;
	friend class FCatrunInfiniteStaminaTest;
	void ResetStamina();
	void AdvanceStamina(double DeltaSeconds, bool bDraining);
	void ApplyExhaustion(bool bNewExhausted);
	static bool IsVoluntaryHorizontalTravel(const FVector& Input, const FVector& Travel, bool bGrounded, bool bForced);

	UFUNCTION()
	void HandleMovementUpdated(float DeltaSeconds, FVector OldLocation, FVector OldVelocity);

	double Stamina = 100.;
	double SecondsWithoutDrain = 0.;
	bool bExhausted = false;
	bool bSprinting = false;
	bool bForcedAtMovementStart = false;
	bool bGroundedAtMovementStart = false;
};
