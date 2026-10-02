#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "InputCoreTypes.h"
#include "CatrunBellComponent.generated.h"

/**
 * Put on the player cat. Pressing BellKey shakes the bell: a Large sound is emitted at the
 * cat's current location (design doc 1.1). Cooldown comes from the sound settings asset.
 */
UCLASS(ClassGroup = (Catrun), meta = (BlueprintSpawnableComponent))
class CATRUN_API UCatrunBellComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UCatrunBellComponent();

	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

	// Tries to ring the bell. Fails during the cooldown or when bCanRing is false.
	UFUNCTION(BlueprintCallable, Category = "Bell")
	bool TryRing();

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bell")
	FKey BellKey = EKeys::Q;

	// Set false while hiding (design doc 5: no bell inside a hideout).
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bell")
	bool bCanRing = true;

	UFUNCTION(BlueprintPure, Category = "Bell")
	float GetCooldownRemaining() const;

private:
	double LastRingTime = -1000.0;
};
