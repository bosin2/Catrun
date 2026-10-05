#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "Sound/SoundTypes.h"
#include "CatrunArmor.generated.h"

class ASoundGridManager;
class UAnimationAsset;

/**
 * Empty armor, stage 1: walks to the place where a sound was made.
 *
 * Behaviour (design doc 4.3):
 *  - While walking to a destination, only a LOUDER sound changes the destination.
 *  - Once it has arrived, any sound changes the destination.
 *
 * Movement: the path comes from CatrunArmorPath (A* on the sound grid, up/down/left/right
 * only). The armor walks from corner to corner of that path and opens closed doors on the way.
 *
 * Not included yet: patrol, search points, vision, catching the cat.
 */
UCLASS()
class CATRUN_API ACatrunArmor : public ACharacter, public ICatrunSoundListener
{
	GENERATED_BODY()

public:
	ACatrunArmor();

	// ICatrunSoundListener: armors hear the "Minion" sounds.
	virtual ECatrunSoundTarget GetListenerGroup_Implementation() const override { return ECatrunSoundTarget::Minion; }
	virtual void OnSoundHeard_Implementation(const FCatrunSoundEvent& Event, float RemainingBudget) override;

	virtual void Tick(float DeltaSeconds) override;

	UFUNCTION(BlueprintPure, Category = "Armor")
	bool IsMovingToSound() const { return bMoving; }

	// Walking speed while heading to a sound (cm/s). Must exceed the cat's running speed.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor")
	float ChaseSpeed = 150.f;

	// A corner of the path counts as reached when the armor is this close (cm).
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor")
	float CornerTolerance = 10.f;

	// Looping animation while standing still.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor|Animation")
	TObjectPtr<UAnimationAsset> IdleAnim;

	// Looping animation while walking.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor|Animation")
	TObjectPtr<UAnimationAsset> MoveAnim;

	// Draw the current path and destination in the viewport.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Debug")
	bool bDebugDrawPath = true;

protected:
	virtual void BeginPlay() override;

private:
	// Asks the pathfinder for a path to Destination. Returns false when there is none.
	bool StartWalkingTo(const FVector& Destination);

	// Walks to the next corner of the path, opens doors, and stops at the end.
	void FollowPath();

	void StopWalking();
	void SetMoving(bool bNewMoving);

	TWeakObjectPtr<ASoundGridManager> SoundManager;

	// Corners of the current path and the index of the corner we are walking to.
	TArray<FVector> PathCorners;
	int32 NextCorner = 0;

	bool bMoving = false;
	ECatrunSoundSize CurrentSoundSize = ECatrunSoundSize::Small;
	FVector Destination = FVector::ZeroVector;
};
