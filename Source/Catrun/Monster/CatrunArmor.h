#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "Sound/SoundTypes.h"
#include "CatrunArmor.generated.h"

class UCatrunCapturePresentationComponent;
class ACatrunDoor;
class ACatrunPatrolPoint;
class ASoundGridManager;
class UAnimationAsset;
class UCatrunAlertMarkComponent;
class UCatrunSoundSettings;
class UCatrunVisionFanComponent;
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
	Looking		UMETA(DisplayName = "Looking around"),
	Catching	UMETA(DisplayName = "Picking up the cat"),
	WaitingForCapture UMETA(DisplayName = "Waiting for the captor")
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
 * animation assets with optional Blueprint presentation requests. Patrol, near perception,
 * candle mark pursuit and capture use the same action state.
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

	// Called by the mark system (UCatrunMarkSubsystem). While following, this armor knows where
	// the cat really is; a sound investigation temporarily takes priority.
	void SetFollowingMark(bool bFollow);
	bool IsFollowingMark() const { return bFollowingMark; }
	bool IsCatching() const { return Action == EArmorAction::Catching; }
	bool IsWaitingForCapture() const { return bWaitingForCapture; }

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Armor|Capture")
	TObjectPtr<UCatrunCapturePresentationComponent> CapturePresentation;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Armor|Animation", meta=(ClampMin="0.1"))
	float TurnPlayRate = 3.333333f;

	// BP/AnimBP can play presentation without replacing native state/path safety.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Armor|Animation")
	bool bUseBlueprintAnimation = false;
	UFUNCTION(BlueprintImplementableEvent, Category="Armor|Animation")
	void AnimationRequested(UAnimationAsset* Animation, bool bLoop, float PlayRate);

	bool IsInvestigatingSound() const { return bInvestigatingSound; }
	FVector GetInvestigationLocation() const { return Destination; }
	// ---- Movement ----
	// Only used when the level has no sound settings. The real running speeds are in
	// DA_SoundSettings ("Armor Speed": ArmorRunSpeedMark / Bell / Noise).
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor")
	float ChaseSpeed = 300.f;

	// Walking speed while going back to the post (cm/s).
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor")
	float WalkSpeed = 150.f;

	// A corner of the path counts as reached when the armor is this close (cm).
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor")
	float CornerTolerance = 10.f;

	// The armor is "stuck" when it hardly moves while walking for this long (seconds), for example
	// when furniture or a hideout stands in the way of the last step of the path.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor", meta = (ClampMin = "0.1"))
	float StuckTime = 0.6f;

	// A stuck armor counts as arrived when it is this close to the end of its path (cm).
	// (It cannot enter hideouts, so waiting in front of one is as far as it gets.)
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor", meta = (ClampMin = "0.0"))
	float StuckArrivalDistance = 100.f;

	// After looking around at the sound, go back to the place where the armor started
	// (its post) and face the original direction.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor")
	bool bReturnToPost = true;

	// ---- Patrol ----
	// Patrol route, in walking order (set per armor in the level; empty = the armor stays at its
	// post). The armor walks point to point, waits at each (ArmorPatrolPause), and goes back and
	// forth along the route (or around it, see bPatrolLoop). A sound interrupts the patrol; after
	// checking it the armor walks on toward the point it was heading to.
	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "Armor|Patrol")
	TArray<TObjectPtr<ACatrunPatrolPoint>> PatrolPoints;

	// Off = back and forth (A-B-C-B-A...). On = around (A-B-C-A...).
	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category = "Armor|Patrol")
	bool bPatrolLoop = false;

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

	// Playback rate for the arrival search only. Its state ends with the clip.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor|Animation", meta = (ClampMin = "0.1"))
	float ArrivalLookPlayRate = 1.f;

	// Played once when the armor catches the cat (it lifts the cat). The level restarts after it.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor|Animation")
	TObjectPtr<UAnimationAsset> PickupAnim;

	// ---- Detection (design doc 4.2, as changed by the designer) ----
	// ArmorDetectRadius in the sound settings defines the detection circle. Obstacles can block
	// detection at sight height or at the cat's body height.
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Armor|Detection")
	TObjectPtr<UCatrunVisionFanComponent> Detection;

	// The "!" above the armor when it notices the cat.
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Armor|Detection")
	TObjectPtr<UCatrunAlertMarkComponent> AlertMark;

	// Draw the detection circle of this armor on the floor (debug only). The level's sound system
	// has a switch (bDebugShowArmorDetection) that shows the circles of all armors at once.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor|Detection")
	bool bShowDetectionDisplay = false;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor|Detection", meta=(ClampMin="0", ClampMax="1"))
	float DetectionDisplayOpacity = .12f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Armor|Detection")
	FLinearColor DetectionDisplayColor = FLinearColor(.015f, .035f, .12f, 1.f);

	// True while the cat is inside the detection circle.
	UFUNCTION(BlueprintPure, Category = "Armor|Detection")
    bool IsSeeingCat() const { return bSeeingCat; }
    void ForgetCorridorCat(const APawn& Cat);

	// Show the current action above the armor and draw its path and destination.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Debug")
	bool bDebugDrawPath = false;
	/** Effective opt-in, including the process-wide catrun.DebugArmorPaths console switch. */
	UFUNCTION(BlueprintPure, Category="Debug") bool IsPathDebugEnabled() const;

	// Text above the head that shows the current action (a world text, so it needs no HUD).
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Debug")
	TObjectPtr<UTextRenderComponent> ActionLabel;

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;

private:
	friend class FCatrunPuzzleSuspensionTest;
	friend class FCatrunReleasedMarkFollowerTest;
	friend class FCatrunArmorTravelSafetyTest;
	friend class FCatrunTurnCurveHandoffTest;
	friend class UCatrunCapturePresentationComponent;
    void PrepareForCapture();
    void DiscardActiveTrip();
    TWeakObjectPtr<AActor> InvestigationSource;
    friend class FCatrunCorridorFreeWalkTest;
	void CatchOwnerChanged(UObject* CaptureOwner);
	bool bWaitingForCapture = false;
	bool bCaptureWaitMeshPaused = false;
	EArmorAction CaptureWaitAction = EArmorAction::Idle;
	uint8 CaptureWaitMovementMode = 0, CaptureWaitCustomMode = 0;
	FDelegateHandle CatchOwnerChangedHandle;
	// bReturningToPost remains a walk-speed legacy flag; target intent is explicit.
	enum class ETravelIntent : uint8 { None, Patrol, ReturnPost, Investigation, Mark };
	ETravelIntent TravelIntent = ETravelIntent::None;
	bool TryGetActiveTravelDestination(FVector& OutDestination) const;
	void ReplanAfterDoor();
	bool bAwaitingDoorReplan = false;
	float DoorReplanWait = 0.f;
	void CommitTurn(bool bCompleted);
	bool GetTurnPlaybackTime(float& OutTime) const;
	FQuat TurnStartActorRotation = FQuat::Identity;
	FQuat TurnMeshBasis = FQuat::Identity;
	bool bTurnCommitted = true;
	friend class FCatrunSoundPriorityTest;
	friend class FCatrunArmorCaptureObstructionTest;
	friend class FCatrunCaptureInitialSetupTest;
	// ---- Path ----
	// Asks the pathfinder for a path to NewDestination. Returns false when there is none.
	bool PlanPath(const FVector& NewDestination);

	// ---- Actions ----
	// Switches to a new action and plays its animation. Looping animations repeat, others play once.
	void SetAction(EArmorAction NewAction);
	void PlayAnimation(UAnimationAsset* Anim, bool bLoop, float Rate = 1.f);

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

	// ---- Patrol ----
	bool HasPatrol() const;
	// Arrived at the patrol point PatrolIndex: choose the next one and wait here for a while.
	void OnPatrolPointReached();
	// Walks to the patrol point PatrolIndex (waits and tries again when no path can be planned).
	void BeginPatrolLeg();

	int32 PatrolIndex = 0;			// the patrol point the armor is heading to (or waiting at, then the next)
	int32 PatrolStep = 1;			// +1 / -1 along the route
	bool bPatrolWaiting = false;	// standing still between two patrol points
	float PatrolWaitLeft = 0.f;

	void DrawDebug() const;
	void UpdateActionLabel();

	// Checks for a nearby cat with clear sight and a clear body-height capture path.
	void UpdateDetection();
	bool HasBodyHeightSight(const APawn& Cat) const;
	bool HasClearCapturePath(const APawn& Cat) const;
	bool bSeeingCat = false;

	// ---- Following the candle mark ----
	void UpdateMarkFollowing(float DeltaSeconds);
	void FinishReleasedMark();
	bool bFollowingMark = false;
	bool bPendingMarkRelease = false;
	bool bInvestigatingSound = false;

	// Stuck detection while walking (see TickWalking).
	float StuckTimer = 0.f;
	FVector LastWalkLocation = FVector::ZeroVector;
	float MarkRepathTimer = 0.f;
	FIntPoint MarkTargetCell = FIntPoint(INT32_MIN, INT32_MIN);	// where the cat was at the last path plan

	// ---- Catch ----
	// Moves the camera in front of the armor, plays the pick-up animation, fades to black and
	// starts the level again.
	void StartCatch(APawn& Cat);
	void TickCatching(float DeltaSeconds);
	bool bDetectionConfigured = false;
	bool bDetectionDisplayShown = true;	// the display starts visible until the first update decides

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

	// What the armor is running for: decides the running speed (see ArmorRunSpeed* in the settings).
	enum class ERunCause : uint8 { Noise, Bell, Mark };
	ERunCause RunCause = ERunCause::Noise;
	FVector Destination = FVector::ZeroVector;
};
