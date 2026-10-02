#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "Navigation/PathFollowingComponent.h"
#include "Sound/SoundTypes.h"
#include "CatrunArmor.generated.h"

class AAIController;
class UAnimationAsset;

/**
 * Empty armor, stage 1 version: walks to the place where a sound was made along the
 * shortest NavMesh path (engine A*).
 *
 * Implements the move/search rule of design doc 4.3:
 *  - while walking to a destination, only a LOUDER sound changes the destination;
 *  - once it has arrived, any sound changes the destination.
 * Search points, patrol, vision, catching and door opening come in later stages.
 */
UCLASS()
class CATRUN_API ACatrunArmor : public ACharacter, public ICatrunSoundListener
{
	GENERATED_BODY()

public:
	ACatrunArmor();

	// ICatrunSoundListener
	virtual ECatrunSoundTarget GetListenerGroup_Implementation() const override { return ECatrunSoundTarget::Minion; }
	virtual void OnSoundHeard_Implementation(const FCatrunSoundEvent& Event, float RemainingBudget) override;

	virtual void Tick(float DeltaSeconds) override;

	UFUNCTION(BlueprintPure, Category = "Armor")
	bool IsMovingToSound() const { return bMoving; }

	// Walking speed while heading to a sound (cm/s). Must exceed the cat's running speed.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor")
	float ChaseSpeed = 300.f;

	// Looping animation while standing still.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor|Animation")
	TObjectPtr<UAnimationAsset> IdleAnim;

	// Looping animation while moving to a sound.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor|Animation")
	TObjectPtr<UAnimationAsset> MoveAnim;

	// How close (cm) the armor must get to count as arrived.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor")
	float AcceptanceRadius = 60.f;

	// Draw the current path and destination in the viewport.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Debug")
	bool bDebugDrawPath = true;

protected:
	virtual void BeginPlay() override;
	virtual void PossessedBy(AController* NewController) override;

private:
	void SetMoving(bool bNewMoving);

	UFUNCTION()
	void HandleMoveCompleted(FAIRequestID RequestID, EPathFollowingResult::Type Result);

	bool bMoving = false;
	ECatrunSoundSize CurrentSoundSize = ECatrunSoundSize::Small;
	FVector Destination = FVector::ZeroVector;
};
