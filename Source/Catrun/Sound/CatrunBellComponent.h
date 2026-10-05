#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "InputCoreTypes.h"
#include "CatrunBellComponent.generated.h"

/**
 * Turns the cat's bell into a sound the monsters can hear.
 *
 * The cat blueprint already has a component (BP_CatActions) that plays the bell animation and
 * sound and then calls its event dispatcher "OnBellRung". This component listens to that
 * dispatcher, so the existing blueprints stay untouched and their cooldown and "no bell while
 * hiding" rules apply automatically.
 *
 * If the cat has no such component (for example an older cat blueprint), the bell key below
 * is used instead.
 *
 * ASoundGridManager adds this component to the player pawn at runtime.
 */
UCLASS(ClassGroup = (Catrun), meta = (BlueprintSpawnableComponent))
class CATRUN_API UCatrunBellComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UCatrunBellComponent();

	virtual void BeginPlay() override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

	// Makes the bell sound at the cat's position. Fails during the cooldown (key mode only).
	UFUNCTION(BlueprintCallable, Category = "Bell")
	bool TryRing();

	// Fallback bell key, only used when the cat has no BP_CatActions component.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bell")
	FKey FallbackBellKey = EKeys::Q;

	// Set false to mute the bell from code (key mode only).
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bell")
	bool bCanRing = true;

	UFUNCTION(BlueprintPure, Category = "Bell")
	float GetCooldownRemaining() const;

	UFUNCTION(BlueprintPure, Category = "Bell")
	bool IsListeningToCatActions() const { return bListeningToCatActions; }

private:
	// Called by the cat's OnBellRung dispatcher (no parameters).
	UFUNCTION()
	void HandleBellRung();

	// Finds the cat's BP_CatActions component and subscribes to OnBellRung.
	bool BindToCatActions();

	// True when the cat's own hiding logic says it is hiding right now.
	bool IsCatHiding() const;

	// Emits the Large "Minion" bell sound at the cat's position.
	bool EmitBellSound();

	TWeakObjectPtr<UActorComponent> CatActions;
	bool bListeningToCatActions = false;
	double LastRingTime = -1000.0;
};
