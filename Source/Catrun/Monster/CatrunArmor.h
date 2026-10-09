#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "Sound/SoundTypes.h"
#include "CatrunArmor.generated.h"

class ACatrunDoor;
class ASoundGridManager;
class UAnimationAsset;
class UTextRenderComponent;

// What the armor is doing right now. Only one action at a time.
UENUM(BlueprintType)
enum class EArmorAction : uint8
{
	Idle		UMETA(DisplayName = "Idle"),
	Reacting	UMETA(DisplayName = "Reacting to a sound"),
	Walking		UMETA(DisplayName = "Running along the path"),
	Turning		UMETA(DisplayName = "Turning 90 degrees"),
	OpeningDoor	UMETA(DisplayName = "Opening a door"),
	Looking		UMETA(DisplayName = "Looking around")
};

/**
 * Empty armor, stage 1: walks to the place where a sound was made.
 *
 * Behaviour (design doc 4.3):
 *  - While it has a destination, only a LOUDER sound changes the destination.
 *  - Once it has arrived, any sound changes the destination.
 *
 * Flow of one trip:
 *   Idle -> (sound heard) [Reacting] -> Walking (running) -> [Turning at corners] -> [OpeningDoor] -> Idle
 * Reacting and Turning only happen when their animation slots are filled; with the slots
 * empty the armor runs straight to the sound and its body turns smoothly by itself.
 *
 * The path comes from CatrunArmorPath (A* on the sound grid, up/down/left/right only), so a
 * path is a list of corners. Each action plays its own animation; the animations are plain
 * animation assets, set per armor blueprint (no animation blueprint needed yet).
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
	EArmorAction GetAction() const { return Action; }

	// True from the moment a sound was heard until the armor has arrived.
	UFUNCTION(BlueprintPure, Category = "Armor")
	bool HasDestination() const { return bHasDestination; }

	// ---- Movement ----
	// Running speed while heading to a sound (cm/s). Must exceed the cat's running speed.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor")
	float ChaseSpeed = 300.f;

	// Walking speed while going back to the post (cm/s).
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor")
	float WalkSpeed = 150.f;

	// A corner of the path counts as reached when the armor is this close (cm).
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor")
	float CornerTolerance = 10.f;

	// After looking around at the sound, go back to the place where the armor started
	// (its post) and face the original direction.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor")
	bool bReturnToPost = true;

	// A heading change larger than this (degrees) is done with a turn animation.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor")
	float TurnThreshold = 45.f;

	// The door leaf starts to open this far (0..1) into the open-door animation
	// (frame where the hand takes hold of the door / total frames).
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float DoorOpenMoment = 0.306f;

	// The door follows the armor's hand while it holds the door (exact sync with the animation).
	// Off = the door turns on its own timer (OpenDuration on the door).
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor")
	bool bDoorFollowsHand = true;

	// The hand lets go of the door this far (0..1) into the open-door animation
	// (frame 144 of 180).
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float DoorReleaseMoment = 0.8f;

	// Bone of the hand that holds the door. Empty = the hand closest to the door is used.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor")
	FName DoorGripBone;

	// The open-door animation turns the armor's body by this many degrees by itself (like the
	// turn animations do). Positive = to its right (clockwise seen from above), negative = left.
	// When the animation ends, the armor actor takes the same turn at once, so that the pose and
	// the actor direction agree. This is the turn AFTER mirroring (see bMirrorDoorAnimation).
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor")
	float DoorOpenAnimTurnDegrees = -90.f;

	// Flip the armor's body left-to-right while the open-door animation plays. The animation was
	// made for a door that swings clockwise; the doors here swing counter-clockwise, so the
	// whole animation is mirrored (its turn becomes a left turn). Switch off to play it as made.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor")
	bool bMirrorDoorAnimation = true;

	// The open-door animation walks the body forward without moving the armor actor. This bone
	// is measured at the start and the end of the animation, and the actor is moved by the
	// difference, so the armor continues from where its body ended up (no jump back).
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor")
	FName DoorAnimTrackedBone = TEXT("pelvis");

	// ---- Animations (all optional; an empty slot just keeps the previous pose) ----
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor|Animation")
	TObjectPtr<UAnimationAsset> IdleAnim;

	// Looping animation while running to a sound (also used while walking up to a door).
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor|Animation")
	TObjectPtr<UAnimationAsset> RunAnim;

	// Looping animation while walking back to the post. Empty = RunAnim is used.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor|Animation")
	TObjectPtr<UAnimationAsset> WalkAnim;

	// Optional, left empty for now: played once when a sound is heard while standing still,
	// before the armor starts to run. Empty = the armor runs at once.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor|Animation")
	TObjectPtr<UAnimationAsset> SoundReactAnim;

	// 90 degree turns on the spot at corners. Used only while walking back to the post. While
	// running to a sound the armor never stops to turn; its body turns smoothly by itself.
	// Empty = no turn on the spot at all.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor|Animation")
	TObjectPtr<UAnimationAsset> TurnLeftAnim;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor|Animation")
	TObjectPtr<UAnimationAsset> TurnRightAnim;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor|Animation")
	TObjectPtr<UAnimationAsset> DoorOpenAnim;

	// Played once when the armor has arrived at the sound ("looking around"), then it goes idle.
	// A new sound interrupts it at once.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor|Animation")
	TObjectPtr<UAnimationAsset> ArrivalLookAnim;

	// Show the current action above the armor and draw its path and destination.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Debug")
	bool bDebugDrawPath = true;

	// Text above the head that shows the current action (a world text, so it needs no HUD).
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Debug")
	TObjectPtr<UTextRenderComponent> ActionLabel;

protected:
	virtual void BeginPlay() override;

private:
	// ---- Path ----
	// Asks the pathfinder for a path to NewDestination. Returns false when there is none.
	bool PlanPath(const FVector& NewDestination);

	// ---- Actions ----
	// Switches to a new action and plays its animation. Looping animations repeat, others play once.
	void SetAction(EArmorAction NewAction);
	void PlayAnimation(UAnimationAsset* Anim, bool bLoop);

	// Moving animation and speed of the current trip: running to a sound, or walking back to the post.
	UAnimationAsset* MoveAnimation() const;
	void ApplyMoveSpeed();
	float AnimationLength(const UAnimationAsset* Anim) const;

	// Per-frame behaviour of each action.
	void TickReacting(float DeltaSeconds);
	void TickWalking(float DeltaSeconds);
	void TickTurning(float DeltaSeconds);
	void TickOpeningDoor(float DeltaSeconds);
	void TickLooking(float DeltaSeconds);

	// Lets the hand take hold of the door (see bDoorFollowsHand).
	void StartOpeningDoor(ACatrunDoor& Door);

	// Starts and ends the open-door animation: mirror the body, measure how far the body walks.
	void BeginDoorAnimation();
	void EndDoorAnimation();

	// Called when the armor should aim for the next corner: turns first if the heading is far off.
	void BeginLeg();
	// Starts the turn animation(s) for a heading change. A turn animation turns exactly 90 degrees,
	// so a 180 degree change plays it twice.
	void BeginTurn(float SignedAngleDegrees);

	// Turns the body toward the nearest of the four axis directions of Direction (never diagonal).
	void FaceAxisToward(const FVector& Direction, float DeltaSeconds);
	void BeginOpeningDoor(ACatrunDoor* Door);

	// A closed door that the current path really goes through and that is close enough to open.
	ACatrunDoor* FindDoorOnPath() const;

	// True when the next LookAhead cm of the path cross the doorway of Door.
	bool PathCrossesDoorway(const ACatrunDoor& Door, float LookAhead) const;
	void FinishTrip();

	// Plans the way back to the post. Falls back to standing still when it is not needed or possible.
	void StartReturnToPost();
	void TickIdle(float DeltaSeconds);

	void DrawDebug() const;
	void UpdateActionLabel();

	TWeakObjectPtr<ASoundGridManager> SoundManager;
	TWeakObjectPtr<ACatrunDoor> DoorBeingOpened;

	EArmorAction Action = EArmorAction::Idle;
	float ActionTime = 0.f;		// seconds since the current action started
	float ActionDuration = 0.f;	// how long the current action lasts (0 = until finished by logic)
	bool bDoorTriggered = false;

	bool bDoorHandDriven = false;	// the door is following the hand
	bool bDoorReleased = false;		// the hand has let go
	FName DoorGripBoneInUse;

	// Body position at the start of the open-door animation, and the mesh scale to restore after it.
	FVector DoorAnimStartBoneLocation = FVector::ZeroVector;
	FVector MeshBaseScale = FVector::OneVector;

	// Opening a door has three steps: walk to the spot in front of it, face it, play the animation.
	enum class EDoorStep : uint8 { Approach, Facing, Animation };
	EDoorStep DoorStep = EDoorStep::Approach;
	FVector DoorStandPoint = FVector::ZeroVector;

	// Corners of the current path and the index of the corner we are walking to.
	TArray<FVector> PathCorners;
	int32 NextCorner = 0;

	// Heading we turn toward while opening a door.
	FRotator TurnTargetRotation = FRotator::ZeroRotator;

	// Turn animations still to play for the current heading change (1 = 90 degrees, 2 = 180).
	int32 TurnsRemaining = 0;
	bool bTurningRight = false;

	// Where the armor started: it goes back here after checking a sound.
	FVector PostLocation = FVector::ZeroVector;
	FRotator PostRotation = FRotator::ZeroRotator;
	bool bReturningToPost = false;	// the current trip leads back to the post (no sound destination)
	bool bWalkingMode = false;		// the walk animation currently plays (false = running)
	bool bRestorePostHeading = false;	// turn to PostRotation while standing at the post

	bool bHasDestination = false;
	ECatrunSoundSize CurrentSoundSize = ECatrunSoundSize::Small;
	FVector Destination = FVector::ZeroVector;
};
