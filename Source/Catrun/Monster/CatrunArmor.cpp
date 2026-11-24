#include "CatrunArmor.h"
#include "CatrunMarkSubsystem.h"
#include "Interaction/CatrunPuzzleSuspension.h"
#include "CatrunCapturePresentationComponent.h"
#include "CatrunPerceptionPolicy.h"
#include "Components/CapsuleComponent.h"

#include "Catrun.h"
#include "Perception/AlertMarkComponent.h"
#include "Perception/CatrunCatQueries.h"
#include "Perception/VisionFanComponent.h"
#include "CatrunPatrolPoint.h"
#include "CatrunRestartSubsystem.h"
#include "Pathfinding/ArmorPathfinder.h"
#include "Sound/CatrunDoor.h"
#include "Sound/CatrunSoundSettings.h"
#include "Sound/SoundGridManager.h"
#include "AIController.h"
#include "Animation/AnimationAsset.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimMontage.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/BoxComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "DrawDebugHelpers.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PawnMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	// Global opt-in also gates old BP/map overrides serialized with bDebugDrawPath=true.
	TAutoConsoleVariable<int32> CVarArmorPaths(TEXT("catrun.DebugArmorPaths"),0,
		TEXT("Show cyan armor routes/magenta targets for actors with DebugDrawPath enabled. 0: normal play, 1: diagnostic opt-in."),ECVF_Cheat);
	// Angle in degrees from direction From to direction To (both flat). Positive = turn right.
	float SignedAngleDegrees(const FVector& From, const FVector& To)
	{
		const float Cross = FVector::CrossProduct(From, To).Z;
		const float Dot = FVector::DotProduct(From, To);
		return FMath::RadiansToDegrees(FMath::Atan2(Cross, Dot));
	}

	// The closest of the four directions east, west, south, north (the grid axes).
	FVector SnapToAxis(const FVector& Direction)
	{
		if (FMath::Abs(Direction.X) >= FMath::Abs(Direction.Y))
		{
			return FVector(Direction.X >= 0.f ? 1.f : -1.f, 0.f, 0.f);
		}
		return FVector(0.f, Direction.Y >= 0.f ? 1.f : -1.f, 0.f);
	}

	// Yaw rounded to a multiple of 90 degrees.
	float SnapYaw(float Yaw)
	{
		return FMath::GridSnap(Yaw, 90.f);
	}
}

ACatrunArmor::ACatrunArmor()
{
	PrimaryActorTick.bCanEverTick = true;
	CapturePresentation = CreateDefaultSubobject<UCatrunCapturePresentationComponent>(TEXT("CapturePresentation"));
	GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Pawn, ECR_Block);

	// The AI controller is only needed so the character movement runs; it does no pathfinding.
	AIControllerClass = AAIController::StaticClass();
	AutoPossessAI = EAutoPossessAI::PlacedInWorldOrSpawned;

	// The armor faces only the four grid directions, so its body is turned by our own code
	// (FaceAxisToward), not by the character movement.
	bUseControllerRotationYaw = false;
	GetCharacterMovement()->bOrientRotationToMovement = false;

	// Debug text above the head showing the current action.
	ActionLabel = CreateDefaultSubobject<UTextRenderComponent>(TEXT("ActionLabel"));
	ActionLabel->SetupAttachment(RootComponent);
	ActionLabel->SetRelativeLocation(FVector(0.f, 0.f, 150.f));
	ActionLabel->SetHorizontalAlignment(EHTA_Center);
	ActionLabel->SetWorldSize(34.f);
	ActionLabel->SetTextRenderColor(FColor::Yellow);
	ActionLabel->SetCastShadow(false);

	Detection = CreateDefaultSubobject<UCatrunVisionFanComponent>(TEXT("Detection"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> DetectionRing(
		TEXT("/Game/Systems/Sound/M_ArmorDetectionRing.M_ArmorDetectionRing"));
	Detection->SetDisplayMaterialOverride(DetectionRing.Object);

	AlertMark = CreateDefaultSubobject<UCatrunAlertMarkComponent>(TEXT("AlertMark"));
	AlertMark->SetupAttachment(RootComponent);
	AlertMark->SetRelativeLocation(FVector(0.f, 0.f, 150.f)); // where the action text is
}

void ACatrunArmor::BeginPlay()
{
	Super::BeginPlay();
	GetCapsuleComponent()->SetCollisionObjectType(ECC_Pawn);
	GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Pawn, ECR_Block);
	ApplyMoveSpeed();
	SoundManager = ASoundGridManager::Get(this);
	MeshBaseScale = GetMesh()->GetRelativeScale3D();
	// The post is the starting place; its direction is rounded to one of the four directions.
	PostLocation = GetActorLocation();
	PostRotation = FRotator(0.f, SnapYaw(GetActorRotation().Yaw), 0.f);
	SetActorRotation(PostRotation);
	SetAction(EArmorAction::Idle);

	// With a patrol route the armor sets off at once toward the first point (as soon as the
	// sound grid is ready, see TickIdle).
	if (HasPatrol())
	{
		PatrolIndex = 0;
		bPatrolWaiting = true;
		PatrolWaitLeft = 0.f;
	}
	if (auto* Restart = UCatrunRestartSubsystem::Get(this))
	{
		CatchOwnerChangedHandle = Restart->OnCatchOwnerChanged.AddUObject(this, &ACatrunArmor::CatchOwnerChanged);
		CatchOwnerChanged(Restart->GetCatchOwner());
	}
}

void ACatrunArmor::EndPlay(const EEndPlayReason::Type Reason)
{
	if (auto* Restart = UCatrunRestartSubsystem::Get(this)) Restart->OnCatchOwnerChanged.Remove(CatchOwnerChangedHandle);
	Super::EndPlay(Reason);
}

void ACatrunArmor::CatchOwnerChanged(UObject* CaptureOwner)
{
	const bool bWait = CaptureOwner && CaptureOwner != CapturePresentation.Get();
	if (bWait == bWaitingForCapture) return;
	auto* Movement = GetCharacterMovement();
	if (bWait)
	{
		bWaitingForCapture = true;
		CaptureWaitAction = Action;
		Action = EArmorAction::WaitingForCapture;
		CaptureWaitMovementMode = Movement->MovementMode;
		CaptureWaitCustomMode = Movement->CustomMovementMode;
		bCaptureWaitMeshPaused = GetMesh()->bPauseAnims;
		GetMesh()->bPauseAnims = true;
		if (auto* CaptureController = GetController()) CaptureController->StopMovement();
		Movement->StopMovementImmediately();
		Movement->ConsumeInputVector();
		Movement->DisableMovement();
	}
	else
	{
		bWaitingForCapture = false;
		Action = CaptureWaitAction; // timers, path cursor, door/turn pose and patrol intent were frozen
		GetMesh()->bPauseAnims = bCaptureWaitMeshPaused;
		Movement->ConsumeInputVector();
		Movement->SetMovementMode(EMovementMode(CaptureWaitMovementMode), CaptureWaitCustomMode);
		MarkRepathTimer = 0.f;
		MarkTargetCell = FIntPoint(INT32_MIN, INT32_MIN);
		LastWalkLocation = GetActorLocation();
		StuckTimer = 0.f;
	}
}

// ---------------------------------------------------------------------------
// Hearing
// ---------------------------------------------------------------------------

void ACatrunArmor::OnSoundHeard_Implementation(const FCatrunSoundEvent& Event, float RemainingBudget)
{
	if (bWaitingForCapture) return;
	if (UCatrunPuzzleSuspension::IsSuspended(this)) return;
    AActor* Source = Event.Instigator.Get();
    if (!Source && Event.Source == ECatrunSoundSource::Cat) Source = CatrunCat::Find(this);
    if (UCatrunMarkSubsystem::IsExcludedFromPerception(Source)) return;
    // Near detection/capture wins; sound investigations override the live mark target.
	if (!CatrunPerception::AcceptSound(Action == EArmorAction::Catching || bSeeingCat,
		bInvestigatingSound, Action == EArmorAction::Looking, CurrentSoundSize, Event.Size))
	{
		return;
	}

	// While travelling only a louder stimulus replaces the snapshot. Looking accepts any size.

	// The destination is where the sound was made (a snapshot), never the cat's live position.
	if (!PlanPath(Event.Location))
	{
		return;
	}
	bAwaitingDoorReplan = false;
	TravelIntent = ETravelIntent::Investigation;
	InvestigationSource = Source;
	bInvestigatingSound = true;
	CurrentSoundSize = Event.Size;
	RunCause = Event.Kind == ECatrunSoundKind::Bell ? ERunCause::Bell : ERunCause::Noise;
	ApplyMoveSpeed(); // a new sound may change the speed in the middle of a run
	Destination = Event.Location;
	UE_LOG(LogCatrunSound, Log, TEXT("%s heard a sound (size %d, remaining %.0f), path has %d corners."),
		*GetName(), (int32)Event.Size, RemainingBudget, PathCorners.Num());

	// A sound beats everything: stop returning to the post and go to the sound.
	// The reaction animation (a slow start) only plays for an armor that stands still at its post,
	// and never for the cat's footsteps. An armor that was lured away (looking around at the end
	// of a trip, or walking back to its post) is already alert: it goes straight to the new sound.
	const bool bAtPost = FVector::Dist2D(GetActorLocation(), PostLocation) <= 50.f;
	const bool bStandingAtPost = Action == EArmorAction::Idle && !bHasDestination && (bAtPost || bPatrolWaiting);
	const bool bPlayReaction = bStandingAtPost && Event.Kind != ECatrunSoundKind::Footstep;
	bHasDestination = true;
	bReturningToPost = false;
	bRestorePostHeading = false;
	bPatrolWaiting = false; // the patrol is interrupted; FinishTrip/StartReturnToPost resume it

	if (bPlayReaction)
	{
		SetAction(EArmorAction::Reacting); // react first, then walk
	}
	else if (Action == EArmorAction::Walking || Action == EArmorAction::Idle || Action == EArmorAction::Looking)
	{
		BeginLeg(); // aim for the new path at once (this also ends a look-around)
	}
	else if (Action == EArmorAction::Turning)
	{
		// A turn animation on the way back to the post is cut short: the body takes the part of the
		// turn that was already shown, then turns smoothly toward the new path while it runs
		// (FaceAxisToward in TickWalking), with no turn animation.
		CommitTurn(false);
		TurnsRemaining = 0;
		BeginLeg();
	}
	// Other actions (reacting, opening a door) finish first and then use the new path.
}

bool ACatrunArmor::PlanPath(const FVector& NewDestination)
{
	const ASoundGridManager* Manager = SoundManager.Get();
	const UCatrunSoundSettings* Settings = Manager ? Manager->GetSettings() : nullptr;
	if (!Settings || !Manager->HasGrid())
	{
		return false;
	}

	CatrunArmorPath::FParams Params;
	Params.ClearanceRadius = Settings->ArmorClearance;
	Params.TurnPenalty = Settings->ArmorTurnPenalty;
	const FCatrunGridData& Grid = Manager->GetGrid();
	const float CapsuleRadius = GetCapsuleComponent()->GetScaledCapsuleRadius();
	for (TActorIterator<ACatrunDoor> Door(GetWorld()); Door; ++Door)
	{
		CatrunArmorPath::FDoorLane Lane;
		if (Door->GetArmorPassageLane(CapsuleRadius, Grid.CellSize, Lane))
			Params.DoorLanes.Add(Lane);
	}

	TArray<FVector> Corners;
	if (!CatrunArmorPath::FindPath(Grid, GetActorLocation(), NewDestination, Params, Corners))
	{
		UE_LOG(LogCatrunSound, Warning, TEXT("%s found no path to %s."), *GetName(), *NewDestination.ToString());
		return false;
	}

	// The first corner is the cell the armor already stands on; walk straight to the next one.
	if (Corners.Num() > 1)
	{
		Corners.RemoveAt(0);
	}
	PathCorners = MoveTemp(Corners);
	NextCorner = 0;
	return true;
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

float ACatrunArmor::AnimationLength(const UAnimationAsset* Anim) const
{
	return Anim ? Anim->GetPlayLength() : 0.f;
}

void ACatrunArmor::PlayAnimation(UAnimationAsset* Anim, bool bLoop, float Rate)
{
	AnimationRequested(Anim, bLoop, Rate);
	if (!bUseBlueprintAnimation && Anim && GetMesh())
	{
		GetMesh()->PlayAnimation(Anim, bLoop);
		GetMesh()->SetPlayRate(Rate); // reset after fast turns
	}
}

UAnimationAsset* ACatrunArmor::MoveAnimation() const
{
	// Walking back to the post uses the walk animation (if there is one); chasing a sound runs.
	return (bReturningToPost && WalkAnim) ? WalkAnim.Get() : RunAnim.Get();
}

void ACatrunArmor::ApplyMoveSpeed()
{
	float RunSpeed = ChaseSpeed;
	if (const UCatrunSoundSettings* S = SoundManager.IsValid() ? SoundManager->GetSettings() : nullptr)
	{
		switch (RunCause)
		{
		case ERunCause::Mark:	RunSpeed = S->ArmorRunSpeedMark;	break;
		case ERunCause::Bell:	RunSpeed = S->ArmorRunSpeedBell;	break;
		case ERunCause::Noise:	RunSpeed = S->ArmorRunSpeedNoise;	break;
		}
	}
	GetCharacterMovement()->MaxWalkSpeed = bReturningToPost ? WalkSpeed : RunSpeed;
}

void ACatrunArmor::SetAction(EArmorAction NewAction)
{
	// Moving on to the next leg is not a new action: do not restart the animation.
	// (Switching from running to walking, or back, still restarts it.)
	if (NewAction == Action && NewAction == EArmorAction::Walking && bWalkingMode == bReturningToPost)
	{
		return;
	}
	Action = NewAction;
	ActionTime = 0.f;
	ActionDuration = 0.f;

	switch (NewAction)
	{
	case EArmorAction::Idle:
		PlayAnimation(IdleAnim, true);
		break;
	case EArmorAction::Reacting:
		PlayAnimation(SoundReactAnim, false);
		ActionDuration = AnimationLength(SoundReactAnim);
		break;
	case EArmorAction::Walking:
		bWalkingMode = bReturningToPost;
		ApplyMoveSpeed();
		PlayAnimation(MoveAnimation(), true);
		break;
	case EArmorAction::Turning:
	{
		TurnStartActorRotation = GetActorQuat();
		TurnMeshBasis = GetMesh()->GetRelativeRotation().Quaternion();
		bTurnCommitted = false;
		UAnimationAsset* TurnAnim = bTurningRight ? TurnRightAnim : TurnLeftAnim;
		PlayAnimation(TurnAnim, false, FMath::Max(.1f, TurnPlayRate));
		ActionDuration = AnimationLength(TurnAnim) / FMath::Max(.1f, TurnPlayRate);
		break;
	}
	case EArmorAction::OpeningDoor:
		// Move to the spot in front of the door first; the open-door animation starts at the end
		// of the last step (see TickOpeningDoor).
		ApplyMoveSpeed();
		PlayAnimation(MoveAnimation(), true);
		DoorStep = EDoorStep::Approach;
		break;
	case EArmorAction::Looking:
	{
		const float PlayRate = FMath::Max(.1f, ArrivalLookPlayRate);
		const auto* Sequence = Cast<UAnimSequenceBase>(ArrivalLookAnim.Get());
		const float AssetRate = Sequence ? FMath::Abs(Sequence->RateScale) : 1.f;
		if (!FMath::IsNearlyZero(AssetRate))
		{
			ActionDuration = AnimationLength(ArrivalLookAnim) / (PlayRate * AssetRate);
			PlayAnimation(ArrivalLookAnim, false, PlayRate);
		}
		break;
	}
	case EArmorAction::Catching:
		// Stands still until the camera has arrived; TickCatching starts the pick-up animation.
		PlayAnimation(IdleAnim, true);
		break;
	}
}

// Decides what to do next: turn on the spot if the next corner is far off the heading, else walk.
void ACatrunArmor::BeginLeg()
{
	bAwaitingDoorReplan = false;
	StuckTimer = 0.f;
	LastWalkLocation = GetActorLocation();
	// Skip corners we are already standing on.
	while (PathCorners.IsValidIndex(NextCorner) && FVector::Dist2D(GetActorLocation(), PathCorners[NextCorner]) <= CornerTolerance)
	{
		++NextCorner;
	}
	if (!PathCorners.IsValidIndex(NextCorner))
	{
		FinishTrip();
		return;
	}

	// Compare the two axis directions (the body only ever faces the four grid directions).
	const FVector Heading = SnapToAxis(PathCorners[NextCorner] - GetActorLocation());
	const float Angle = SignedAngleDegrees(SnapToAxis(GetActorForwardVector()), Heading);
	UE_LOG(LogCatrunSound, Log, TEXT("%s leg %d/%d: corner %s, heading change %.0f deg, action %d."),
		*GetName(), NextCorner, PathCorners.Num(), *PathCorners[NextCorner].ToString(), Angle, (int32)Action);

	// Turn on the spot with a turn animation only while walking back to the post. When running
	// to a sound the armor never stops: its body turns smoothly by itself (character movement).
	const bool bHasTurnAnimations = TurnLeftAnim || TurnRightAnim;
	if (bReturningToPost && bHasTurnAnimations && FMath::Abs(Angle) > TurnThreshold)
	{
		BeginTurn(Angle);
	}
	else
	{
		SetAction(EArmorAction::Walking);
	}
}

void ACatrunArmor::BeginTurn(float Angle)
{
	// One animation = one quarter turn. A heading change of about 180 degrees needs two.
	TurnsRemaining = FMath::Clamp(FMath::RoundToInt(FMath::Abs(Angle) / 90.f), 1, 2);
	bTurningRight = Angle > 0.f;
	SetAction(EArmorAction::Turning);
}

// Turns the body toward the closest axis direction at a fixed speed.
void ACatrunArmor::FaceAxisToward(const FVector& Direction, float DeltaSeconds)
{
	if (Direction.IsNearlyZero())
	{
		return;
	}
	const float TargetYaw = SnapToAxis(Direction).Rotation().Yaw;
	SetActorRotation(FMath::RInterpConstantTo(GetActorRotation(), FRotator(0.f, TargetYaw, 0.f), DeltaSeconds, 540.f));
}

void ACatrunArmor::BeginOpeningDoor(ACatrunDoor* Door)
{
	DoorBeingOpened = Door;
	bDoorTriggered = false;
	bDoorHandDriven = false;
	bDoorReleased = false;

	// Stand straight in front of the door, on the side the armor comes from, and face it.
	const FVector Center = Door->GetDoorwayCenter();
	const FVector ToArmor = GetActorLocation() - Center;
	FVector Normal = Door->GetDoorNormal();
	if (FVector::DotProduct(ToArmor, Normal) < 0.f)
	{
		Normal = -Normal; // make it point to the armor's side
	}
	const float StandDistance = SoundManager.IsValid() ? SoundManager->GetSettings()->ArmorDoorOpenDistance : 90.f;
	const float Depth = FMath::Clamp(FVector::DotProduct(ToArmor, Normal), StandDistance * 0.7f, StandDistance);
	DoorStandPoint = FVector(Center.X, Center.Y, GetActorLocation().Z) + Normal * Depth;
	TurnTargetRotation = FRotator(0.f, (-Normal).Rotation().Yaw, 0.f);
	SetAction(EArmorAction::OpeningDoor);
}

void ACatrunArmor::FinishTrip()
{
	// The current trip has finished. A prior failed door replan no longer owns Idle.
	bAwaitingDoorReplan = false;
	DoorReplanWait = 0.f;
	// Following the mark never ends by itself: wait here, the next path plan goes on.
	if (bFollowingMark && !bInvestigatingSound)
	{
		PathCorners.Reset();
		NextCorner = 0;
		MarkTargetCell = FIntPoint(INT32_MIN, INT32_MIN);
		SetAction(EArmorAction::Idle);
		return;
	}
	TravelIntent = ETravelIntent::None;
	PathCorners.Reset();
	NextCorner = 0;
	bHasDestination = false; // arrived: from now on any sound is followed (rule 4.3)

	if (bReturningToPost && HasPatrol())
	{
		bReturningToPost = false;
		UE_LOG(LogCatrunSound, Log, TEXT("%s reached patrol point %d."), *GetName(), PatrolIndex);
		OnPatrolPointReached();
		return;
	}

	if (bReturningToPost)
	{
		// Back at the post: stand there and turn to the original direction.
		bReturningToPost = false;
		bRestorePostHeading = true;
		SetAction(EArmorAction::Idle);
		UE_LOG(LogCatrunSound, Log, TEXT("%s is back at its post."), *GetName());
		return;
	}

	UE_LOG(LogCatrunSound, Log, TEXT("%s arrived at the sound."), *GetName());
	if (ArrivalLookAnim)
	{
		SetAction(EArmorAction::Looking); // look around once, then go back (see TickLooking)
	}
	else
	{
		StartReturnToPost();
	}
}

void ACatrunArmor::StartReturnToPost()
{
	// Select a replacement owner before planning: even a failed return must not revive the old trip.
	bAwaitingDoorReplan = false;
	DoorReplanWait = 0.f;
	TravelIntent = ETravelIntent::None;
	bInvestigatingSound = false;
	InvestigationSource.Reset();
	if (bFollowingMark)
    {
        InvestigationSource = CatrunCat::Find(this);
        TravelIntent = ETravelIntent::Mark;
		RunCause = ERunCause::Mark;
		ApplyMoveSpeed();
		MarkRepathTimer = 0.f;
		MarkTargetCell = FIntPoint(INT32_MIN, INT32_MIN);
		SetAction(EArmorAction::Idle);
		return;
	}
	// With a patrol route "back to the post" means: walk on toward the patrol point it was heading to.
	if (HasPatrol())
	{
		BeginPatrolLeg();
		return;
	}
	const bool bFarFromPost = FVector::Dist2D(GetActorLocation(), PostLocation) > 50.f;
	if (bReturnToPost && bFarFromPost && PlanPath(PostLocation))
	{
		TravelIntent = ETravelIntent::ReturnPost;
		bReturningToPost = true;
		BeginLeg(); // run back; this is no sound trip, so a new sound is still accepted
		return;
	}
	bRestorePostHeading = bReturnToPost;
	SetAction(EArmorAction::Idle);
}

// ---------------------------------------------------------------------------
// Patrol
// ---------------------------------------------------------------------------

bool ACatrunArmor::HasPatrol() const
{
	for (const ACatrunPatrolPoint* Point : PatrolPoints)
	{
		if (Point)
		{
			return true;
		}
	}
	return false;
}

void ACatrunArmor::OnPatrolPointReached()
{
	const ACatrunPatrolPoint* Point = PatrolPoints.IsValidIndex(PatrolIndex) ? PatrolPoints[PatrolIndex].Get() : nullptr;
	const UCatrunSoundSettings* S = SoundManager.IsValid() ? SoundManager->GetSettings() : nullptr;
	const float DefaultPause = S ? S->ArmorPatrolPause : 1.5f;
	PatrolWaitLeft = (Point && Point->PauseSeconds >= 0.f) ? Point->PauseSeconds : DefaultPause;

	// The next point of the route (empty slots are skipped).
	const int32 Count = PatrolPoints.Num();
	for (int32 Tries = 0; Tries < Count; ++Tries)
	{
		if (bPatrolLoop)
		{
			PatrolIndex = (PatrolIndex + 1) % Count;
		}
		else
		{
			int32 Next = PatrolIndex + PatrolStep;
			if (Next < 0 || Next >= Count)
			{
				PatrolStep = -PatrolStep;
				Next = PatrolIndex + PatrolStep;
			}
			PatrolIndex = FMath::Clamp(Next, 0, Count - 1);
		}
		if (PatrolPoints[PatrolIndex])
		{
			break;
		}
	}

	bPatrolWaiting = true;
	bRestorePostHeading = false;
	SetAction(EArmorAction::Idle);
}

void ACatrunArmor::BeginPatrolLeg()
{
	// Patrol's existing wait/retry owns a missing point or failed path, not a stale door retry.
	bAwaitingDoorReplan = false;
	DoorReplanWait = 0.f;
	TravelIntent = ETravelIntent::Patrol;
	const ACatrunPatrolPoint* Point = PatrolPoints.IsValidIndex(PatrolIndex) ? PatrolPoints[PatrolIndex].Get() : nullptr;
	if (!Point)
	{
		bPatrolWaiting = true;
		PatrolWaitLeft = 0.5f;
		SetAction(EArmorAction::Idle);
		return;
	}

	const FVector Target = Point->GetActorLocation();
	bRestorePostHeading = false;
	if (FVector::Dist2D(GetActorLocation(), Target) <= 50.f)
	{
		OnPatrolPointReached(); // already standing at it
		return;
	}
	if (!PlanPath(Target))
	{
		bPatrolWaiting = true; // no path yet (the sound grid may not be ready): try again soon
		PatrolWaitLeft = 0.5f;
		SetAction(EArmorAction::Idle);
		return;
	}
	bPatrolWaiting = false;
	bHasDestination = false; // a patrol walk is no sound trip: a new sound is accepted at once
	TravelIntent = ETravelIntent::Patrol;
	Destination = Target;
	bReturningToPost = true; // walking speed and walk animation
	BeginLeg();
}

// While standing at the post, slowly turn back to the direction the armor started with.
void ACatrunArmor::TickIdle(float DeltaSeconds)
{
	if (bAwaitingDoorReplan)
	{
		DoorReplanWait -= DeltaSeconds;
		if (DoorReplanWait <= 0.f) ReplanAfterDoor();
		return;
	}
	if (bPatrolWaiting)
	{
		PatrolWaitLeft -= DeltaSeconds;
		if (PatrolWaitLeft <= 0.f && !bHasDestination && !bFollowingMark)
		{
			BeginPatrolLeg();
		}
		return;
	}
	if (!bRestorePostHeading)
	{
		return;
	}
	SetActorRotation(FMath::RInterpConstantTo(GetActorRotation(), PostRotation, DeltaSeconds, 180.f));
	if (FMath::Abs(FMath::FindDeltaAngleDegrees(GetActorRotation().Yaw, PostRotation.Yaw)) < 1.f)
	{
		bRestorePostHeading = false;
	}
}

// ---------------------------------------------------------------------------
// Per-frame behaviour
// ---------------------------------------------------------------------------

void ACatrunArmor::Tick(float DeltaSeconds)
{
	if (bWaitingForCapture) { UpdateActionLabel(); return; }
	if (UCatrunPuzzleSuspension::IsSuspended(this)) return;
    Super::Tick(DeltaSeconds);
    if (auto* Marks = UCatrunMarkSubsystem::Get(this)) Marks->RefreshCorridor();
    if (bPendingMarkRelease)
	{
		bPendingMarkRelease = false;
		// A sound or capture may already have taken ownership since the suspension ended.
		if (TravelIntent == ETravelIntent::Mark && !bInvestigatingSound && Action != EArmorAction::Catching)
			FinishReleasedMark();
	}
	ActionTime += DeltaSeconds;

	switch (Action)
	{
	case EArmorAction::Idle:			TickIdle(DeltaSeconds);			break;
	case EArmorAction::Reacting:		TickReacting(DeltaSeconds);		break;
	case EArmorAction::Walking:			TickWalking(DeltaSeconds);		break;
	case EArmorAction::Turning:			TickTurning(DeltaSeconds);		break;
	case EArmorAction::OpeningDoor:		TickOpeningDoor(DeltaSeconds);	break;
	case EArmorAction::Looking:			TickLooking(DeltaSeconds);		break;
	case EArmorAction::Catching:		TickCatching(DeltaSeconds);		break;
	}
	UpdateMarkFollowing(DeltaSeconds);
	UpdateDetection();
	DrawDebug();
	UpdateActionLabel();
}

void ACatrunArmor::SetFollowingMark(bool bFollow)
{
	if (bFollow && (UCatrunPuzzleSuspension::IsSuspended(this) || UCatrunMarkSubsystem::IsExcludedFromPerception(CatrunCat::Find(this)))) return;
	if (bFollowingMark == bFollow)
	{
		return;
	}
	bFollowingMark = bFollow;
	MarkRepathTimer = 0.f;
	MarkTargetCell = FIntPoint(INT32_MIN, INT32_MIN);
	bPendingMarkRelease = false;
	if (bWaitingForCapture || UCatrunPuzzleSuspension::IsSuspended(this))
	{
		bPendingMarkRelease = !bFollow && TravelIntent == ETravelIntent::Mark;
		return;
	}
	UE_LOG(LogCatrunSound, Log, TEXT("%s %s the marked cat."), *GetName(), bFollow ? TEXT("starts following") : TEXT("stops following"));
	if (bInvestigatingSound || Action == EArmorAction::Catching) return;
	if (bFollow)
    {
        InvestigationSource = CatrunCat::Find(this);
        TravelIntent = ETravelIntent::Mark;
		RunCause = ERunCause::Mark;
		ApplyMoveSpeed();
		bHasDestination = true; // a trip is on, so the post is forgotten
		bReturningToPost = false;
		bPatrolWaiting = false;
		bRestorePostHeading = false;
	}
	else
	{
		FinishReleasedMark();
	}
}

void ACatrunArmor::FinishReleasedMark()
{
	// Moving followers finish their last known path. An idle follower has already arrived.
	CurrentSoundSize = ECatrunSoundSize::Small;
	const bool bWalkingOn = PathCorners.IsValidIndex(NextCorner) && Action != EArmorAction::Idle;
	if (!bWalkingOn && Action != EArmorAction::Looking) FinishTrip();
}

// While following, the way to the cat is planned again whenever the cat has moved to another grid
// cell (the grid cell is 25 cm, so this is cheap and keeps the armor from turning on the spot).
void ACatrunArmor::UpdateMarkFollowing(float DeltaSeconds)
{
	if (bWaitingForCapture) return;
	if (UCatrunPuzzleSuspension::IsSuspended(this)) return;
	if (!bFollowingMark || bInvestigatingSound || Action == EArmorAction::Catching)
	{
		return;
	}
	MarkRepathTimer -= DeltaSeconds;
	const UCatrunSoundSettings* S = SoundManager.IsValid() ? SoundManager->GetSettings() : nullptr;
	const APawn* Cat = CatrunCat::Find(this);
	if (!S || !Cat || MarkRepathTimer > 0.f)
	{
		return;
	}
	MarkRepathTimer = S->MarkRepathInterval;

	const FIntPoint Cell(FMath::FloorToInt(Cat->GetActorLocation().X / 25.f), FMath::FloorToInt(Cat->GetActorLocation().Y / 25.f));
	if (Cell == MarkTargetCell)
	{
		return;
	}
	// A door or a turn in progress finishes first.
	if (Action == EArmorAction::OpeningDoor || Action == EArmorAction::Turning)
	{
		return;
	}
	Destination = Cat->GetActorLocation(); // the real position: this is what the mark allows
	if (PlanPath(Destination))
	{
		MarkTargetCell = Cell;
		bHasDestination = true;
		BeginLeg();
	}
}

void ACatrunArmor::UpdateDetection()
{
	if (bWaitingForCapture) return;
	if (UCatrunPuzzleSuspension::IsSuspended(this)) return;
	const UCatrunSoundSettings* S = SoundManager.IsValid() ? SoundManager->GetSettings() : nullptr;
	if (!S)
	{
		return;
	}
	// Size and look of the circle come from the settings asset (read once, when it is available).
	if (!bDetectionConfigured)
	{
		Detection->Configure(S->ArmorDetectRadius, S->ArmorDetectRayCount, DetectionDisplayColor);
		Detection->SetDisplayStyle(DetectionDisplayOpacity, S->CatSightRadius);
		bDetectionConfigured = true;
	}

	// The circle is only drawn for debugging: by the level's switch or by this armor's own switch.
	const bool bShowCircle = bShowDetectionDisplay || (SoundManager.IsValid() && SoundManager->bDebugShowArmorDetection);
	if (bShowCircle != bDetectionDisplayShown)
	{
		Detection->SetDisplayVisible(bShowCircle);
		bDetectionDisplayShown = bShowCircle;
	}

	// The circle is centred on the armor. While the open-door animation plays, the body walks away
	// from the actor (the actor only catches up when the animation ends), so the circle follows
	// the body bone instead.
	bool bFollowBody = false;
	if (Action == EArmorAction::OpeningDoor && DoorStep == EDoorStep::Animation && GetMesh() &&
		GetMesh()->GetBoneIndex(DoorAnimTrackedBone) != INDEX_NONE)
	{
		const FVector Body = GetMesh()->GetBoneLocation(DoorAnimTrackedBone, EBoneSpaces::WorldSpace);
		if (FVector::Dist2D(Body, GetActorLocation()) <= 400.f) // same sanity limit as EndDoorAnimation
		{
			Detection->SetOriginOverride(Body);
			bFollowBody = true;
		}
	}
	if (!bFollowBody)
	{
		Detection->ClearOriginOverride();
	}
	// 180 degrees to each side = the whole circle.
	Detection->Update(0.f, 180.f);

	APawn* Cat = CatrunCat::Find(this);
	const bool bSees = Cat && !UCatrunMarkSubsystem::IsExcludedFromPerception(Cat) && !CatrunCat::IsSafeFromCatch(Cat) && Detection->CanSee(Cat->GetActorLocation(), S->CatSightRadius)
		&& CatrunPerception::HasDirectSight(*this, *Cat, S->VisionTraceHeight)
		&& HasBodyHeightSight(*Cat);

	// Refresh the short-lived alert as long as the cat is visible.
	if (bSees)
	{
		AlertMark->Show(0.2f);
	}

	if (bSees && Action != EArmorAction::Catching)
	{
		if (!bSeeingCat)
		{
			UE_LOG(LogCatrunSound, Log, TEXT("%s noticed the cat."), *GetName());
		}
		if (HasClearCapturePath(*Cat))
			StartCatch(*Cat);
	}
	bSeeingCat = bSees;
}

bool ACatrunArmor::HasBodyHeightSight(const APawn& Cat) const
{
	const auto* Character = Cast<ACharacter>(&Cat);
	const FVector Target = Character ? Character->GetCapsuleComponent()->GetComponentLocation() : Cat.GetActorLocation();
	FVector Start = GetCapsuleComponent()->GetComponentLocation();
	Start.Z = Target.Z;
	const float Distance = FVector::Distance(Start, Target);
	return CatrunPerception::SightDistance(*GetWorld(), Start, Target, this, &Cat) >= Distance - KINDA_SMALL_NUMBER;
}

bool ACatrunArmor::HasClearCapturePath(const APawn& Cat) const
{
	const auto* Body = Cast<UPrimitiveComponent>(Cat.GetRootComponent());
	if (!Body) return false;
	const FVector Target = Body->GetComponentLocation();
	const auto* ArmorCapsule = GetCapsuleComponent();
	FVector Start = ArmorCapsule->GetComponentLocation();
	const FCollisionShape Shape = Body->GetCollisionShape();
	// Carry the cat's footprint between the two standing positions, following the change in floor height.
	Start.Z = ArmorCapsule->GetComponentLocation().Z - ArmorCapsule->GetScaledCapsuleHalfHeight() + Shape.GetExtent().Z;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(ArmorCaptureReach), false, this);
	Params.AddIgnoredActor(&Cat);
	return !GetWorld()->SweepTestByChannel(Start, Target, Body->GetComponentQuat(), Body->GetCollisionObjectType(),
		Shape, Params, FCollisionResponseParams(Body->GetCollisionResponseToChannels()));
}

void ACatrunArmor::StartCatch(APawn& Cat)
{
	if (UCatrunPuzzleSuspension::IsSuspended(this)) return;
	UCatrunRestartSubsystem* Restart = UCatrunRestartSubsystem::Get(this);
	const UCatrunSoundSettings* S = SoundManager.IsValid() ? SoundManager->GetSettings() : nullptr;
	if (!Restart || !S || !CapturePresentation->BeginCapture(&Cat, S))
	{
		return; // another armor is already carrying the cat off
	}
}

void ACatrunArmor::ForgetCorridorCat(const APawn& Cat)
{
    const bool bCatTrip = InvestigationSource.Get() == &Cat || (!bInvestigatingSound
        && (bFollowingMark || bPendingMarkRelease || TravelIntent == ETravelIntent::Mark));
    bSeeingCat = false;
    AlertMark->SetVisibility(false);
    bFollowingMark = false;
    bPendingMarkRelease = false;
    MarkTargetCell = FIntPoint(INT32_MIN, INT32_MIN);
    MarkRepathTimer = 0.f;
    if (!bCatTrip) return; // Keep an unrelated device investigation, patrol or return trip.
    DiscardActiveTrip();
    Destination = FVector::ZeroVector;
    CurrentSoundSize = ECatrunSoundSize::Small;
    RunCause = ERunCause::Noise;
    GetCharacterMovement()->MaxWalkSpeed = WalkSpeed;
    StartReturnToPost();
}

void ACatrunArmor::PrepareForCapture()
{
    DiscardActiveTrip();
    SetAction(EArmorAction::Catching);
}

void ACatrunArmor::DiscardActiveTrip()
{
	// Detection follows the animated body while opening a door. If it catches the cat
	// before that animation finishes, commit the body's current position and release
	// the hand-driven door before switching animations. Otherwise the capsule snaps
	// back, the mirrored mesh persists, and the door never finishes opening.
	if (Action == EArmorAction::OpeningDoor)
	{
		if (ACatrunDoor* Door = DoorBeingOpened.Get(); Door && bDoorHandDriven && !bDoorReleased)
		{
			Door->EndHandOpen();
		}
		if (DoorStep == EDoorStep::Animation)
		{
			EndDoorAnimation();
		}
		DoorBeingOpened.Reset();
		bDoorHandDriven = false;
		bDoorReleased = true;
	}

	if (Action == EArmorAction::Turning) CommitTurn(false);
	TurnsRemaining = 0;
	TravelIntent = ETravelIntent::None;
	bAwaitingDoorReplan = false;
	bHasDestination = false;
	bInvestigatingSound = false;
	bReturningToPost = false;
	bPatrolWaiting = false;
	PathCorners.Reset();
	NextCorner = 0;
    InvestigationSource.Reset();
    DoorReplanWait = 0.f;
    StuckTimer = 0.f;
    GetCharacterMovement()->ConsumeInputVector();
    GetCharacterMovement()->StopMovementImmediately();
}

void ACatrunArmor::TickCatching(float DeltaSeconds)
{
	if (!CapturePresentation->IsCapturing())
	{
		SetAction(EArmorAction::Idle);
		StartReturnToPost();
	}
}

// Shows the action name above the head and turns the text toward the camera.
void ACatrunArmor::UpdateActionLabel()
{
	// Shown only when the level's debug switch asks for it (not part of the real game).
	const bool bShowLabel = SoundManager.IsValid() && SoundManager->bDebugShowArmorLabel;
	ActionLabel->SetVisibility(bShowLabel);
	if (!bShowLabel)
	{
		return;
	}
	const FText ActionName = UEnum::GetDisplayValueAsText(Action);
	ActionLabel->SetText(bReturningToPost ? FText::Format(INVTEXT("{0} (returning)"), ActionName) : ActionName);
	if (const APlayerCameraManager* Camera = UGameplayStatics::GetPlayerCameraManager(this, 0))
	{
		const FVector TowardCamera = -Camera->GetCameraRotation().Vector();
		ActionLabel->SetWorldRotation(TowardCamera.Rotation());
	}
}

void ACatrunArmor::TickReacting(float DeltaSeconds)
{
	if (ActionTime >= ActionDuration)
	{
		BeginLeg();
	}
}

void ACatrunArmor::TickWalking(float DeltaSeconds)
{
	// A closed door on the way? Stop in front of it and open it (the cat cannot do this).
	if (ACatrunDoor* Door = FindDoorOnPath())
	{
		BeginOpeningDoor(Door);
		return;
	}

	// Corner reached? Then look at the next leg (it may need a turn).
	if (FVector::Dist2D(GetActorLocation(), PathCorners[NextCorner]) <= CornerTolerance)
	{
		++NextCorner;
		BeginLeg();
		return;
	}

	const FVector ToCorner = PathCorners[NextCorner] - GetActorLocation();
	FaceAxisToward(ToCorner, DeltaSeconds);
	AddMovementInput(ToCorner.GetSafeNormal2D(), 1.f);

	// Stuck? The body may be wider than the free space in front of furniture or a hideout, so the
	// last corner can be out of reach. Waiting there for ever would block the armor, so after a
	// short while it counts as arrived (the usual look around and walk back follows).
	const float Moved = FVector::Dist2D(GetActorLocation(), LastWalkLocation);
	LastWalkLocation = GetActorLocation();
	const bool bBarelyMoving = ActionTime > 0.3f && Moved < 0.05f * DeltaSeconds * 100.f;
	StuckTimer = bBarelyMoving ? StuckTimer + DeltaSeconds : 0.f;
	if (StuckTimer >= StuckTime)
	{
		const float ToEnd = FVector::Dist2D(GetActorLocation(), PathCorners.Last());
		if (ToEnd <= StuckArrivalDistance || StuckTimer >= StuckTime * 4.f)
		{
			UE_LOG(LogCatrunSound, Log, TEXT("%s is stuck %.0f cm from the end of its path: counts as arrived."), *GetName(), ToEnd);
			StuckTimer = 0.f;
			FinishTrip();
		}
	}
}

void ACatrunArmor::TickTurning(float DeltaSeconds)
{
	// The turn animation already turns the body 90 degrees by itself. The actor must NOT turn
	// during it, otherwise the two turns add up. When the animation ends, the actor takes the
	// quarter turn in one step, which matches the pose the animation ended in.
	if (ActionTime < ActionDuration)
	{
		return;
	}
	CommitTurn(true);

	if (--TurnsRemaining > 0)
	{
		SetAction(EArmorAction::Turning); // 180 degrees: play the turn animation once more
	}
	else
	{
		BeginLeg();
	}
}

void ACatrunArmor::TickLooking(float DeltaSeconds)
{
	// Look around once, then go back to the post.
	if (ActionTime >= ActionDuration)
	{
		StartReturnToPost();
	}
}

void ACatrunArmor::TickOpeningDoor(float DeltaSeconds)
{
	ACatrunDoor* Door = DoorBeingOpened.Get();
	if (!Door)
	{
		if (DoorStep == EDoorStep::Animation) EndDoorAnimation();
		bDoorHandDriven = false;
		bDoorReleased = true;
		ReplanAfterDoor(); // no mirrored or stale approach pose survives a destroyed door
		return;
	}

	// Step 1: walk to the spot straight in front of the door.
	if (DoorStep == EDoorStep::Approach)
	{
		const FVector ToStandPoint = DoorStandPoint - GetActorLocation();
		const bool bTimedOut = ActionTime > 4.f; // safety: never get stuck here
		if (ToStandPoint.Size2D() > 8.f && !bTimedOut)
		{
			FaceAxisToward(ToStandPoint, DeltaSeconds);
			AddMovementInput(ToStandPoint.GetSafeNormal2D(), 1.f);
			return;
		}
		DoorStep = EDoorStep::Facing;
		ActionTime = 0.f;
		PlayAnimation(IdleAnim, true);
	}

	// Step 2: turn to face the door. The open-door animation only starts when the armor faces it.
	if (DoorStep == EDoorStep::Facing)
	{
		SetActorRotation(FMath::RInterpConstantTo(GetActorRotation(), TurnTargetRotation, DeltaSeconds, 360.f));
		const float Missing = FMath::Abs(FMath::FindDeltaAngleDegrees(GetActorRotation().Yaw, TurnTargetRotation.Yaw));
		const bool bTimedOut = ActionTime > 2.f;
		if (Missing > 2.f && !bTimedOut)
		{
			return;
		}
		DoorStep = EDoorStep::Animation;
		BeginDoorAnimation();
	}

	// Step 3a: the hand takes hold of the door part-way through the animation.
	if (!bDoorTriggered && ActionTime >= ActionDuration * DoorOpenMoment)
	{
		StartOpeningDoor(*Door);
		bDoorTriggered = true;
	}

	// Step 3b: while the hand holds the door, the door follows the hand (always in sync).
	if (bDoorHandDriven && !bDoorReleased)
	{
		Door->DriveWithPoint(GetMesh()->GetBoneLocation(DoorGripBoneInUse, EBoneSpaces::WorldSpace));
		if (ActionTime >= ActionDuration * DoorReleaseMoment)
		{
			Door->EndHandOpen(); // the hand lets go, the door finishes opening by itself
			bDoorReleased = true;
		}
	}

	if (ActionTime >= ActionDuration)
	{
		if (!bDoorTriggered)
		{
			StartOpeningDoor(*Door);
		}
		if (bDoorHandDriven && !bDoorReleased)
		{
			Door->EndHandOpen();
		}
		// The animation ended with the body walked forward and turned. The actor takes both now
		// (in one step, so nothing jumps back).
		EndDoorAnimation();
		SetActorRotation(FRotator(0.f, SnapYaw(GetActorRotation().Yaw + DoorOpenAnimTurnDegrees), 0.f));

		// The body has moved through the doorway, so the old path (which still leads to the spot in
		// front of the door) is out of date: plan it again from here.
		DoorBeingOpened.Reset();
		bDoorHandDriven = false;
		bDoorReleased = true;
		ReplanAfterDoor();
	}
}

// Opens the door, either following the hand (exact sync) or by a timer.
void ACatrunArmor::StartOpeningDoor(ACatrunDoor& Door)
{
	if (!bDoorFollowsHand)
	{
		Door.OpenFrom(GetActorLocation());
		return;
	}

	// Which hand holds the door? The one closest to the door leaf at this moment (the mirroring
	// swaps the sides, so decide by looking). A bone name set in DoorGripBone overrides this.
	if (!DoorGripBone.IsNone())
	{
		DoorGripBoneInUse = DoorGripBone;
	}
	else
	{
		const FBox Leaf = Door.GetLeafBounds();
		const float LeftDistance = Leaf.ComputeSquaredDistanceToPoint(GetMesh()->GetBoneLocation(TEXT("hand_l"), EBoneSpaces::WorldSpace));
		const float RightDistance = Leaf.ComputeSquaredDistanceToPoint(GetMesh()->GetBoneLocation(TEXT("hand_r"), EBoneSpaces::WorldSpace));
		DoorGripBoneInUse = LeftDistance <= RightDistance ? FName(TEXT("hand_l")) : FName(TEXT("hand_r"));
	}
	UE_LOG(LogCatrunSound, Log, TEXT("%s opens a door with %s."), *GetName(), *DoorGripBoneInUse.ToString());

	Door.BeginHandOpen(GetActorLocation());
	bDoorHandDriven = true;
	bDoorReleased = false;
}

void ACatrunArmor::BeginDoorAnimation()
{
	GetCharacterMovement()->StopMovementImmediately();
	ActionTime = 0.f;
	ActionDuration = AnimationLength(DoorOpenAnim);

	// The animation is made for a door that swings the other way: mirror the body left-to-right.
	if (bMirrorDoorAnimation)
	{
		GetMesh()->SetRelativeScale3D(FVector(-MeshBaseScale.X, MeshBaseScale.Y, MeshBaseScale.Z));
	}
	PlayAnimation(DoorOpenAnim, false);

	// Evaluate the first frame right now so that the body position at the start can be measured.
	GetMesh()->TickAnimation(0.f, false);
	GetMesh()->RefreshBoneTransforms();
	DoorAnimStartBoneLocation = GetMesh()->GetBoneLocation(DoorAnimTrackedBone, EBoneSpaces::WorldSpace);
}

void ACatrunArmor::EndDoorAnimation()
{
	// How far did the body walk during the animation (flat)? Move the actor by that much.
	FVector Walked = GetMesh()->GetBoneLocation(DoorAnimTrackedBone, EBoneSpaces::WorldSpace) - DoorAnimStartBoneLocation;
	Walked.Z = 0.f;
	if (Walked.Size() > 400.f)
	{
		Walked = FVector::ZeroVector; // a bone that does not exist gives nonsense: ignore it
	}

	if (bMirrorDoorAnimation)
	{
		GetMesh()->SetRelativeScale3D(MeshBaseScale);
	}
	FHitResult HandoffHit;
	AddActorWorldOffset(Walked, true, &HandoffHit, ETeleportType::None);
	// A late blocker keeps only achieved travel. Never bypass collision to match a presentation pose.
	UE_LOG(LogCatrunSound, Log, TEXT("%s open-door animation moved the body %.0f cm."), *GetName(), Walked.Size());
}

// A closed door counts only if the path really goes through its doorway soon. A door the armor
// merely walks past must stay closed.
ACatrunDoor* ACatrunArmor::FindDoorOnPath() const
{
	const ASoundGridManager* Manager = SoundManager.Get();
	if (!Manager || !Manager->GetSettings())
	{
		return nullptr;
	}
	const float TriggerDistance = Manager->GetSettings()->ArmorDoorOpenDistance + 100.f;

	TArray<ACatrunDoor*> ClosedDoors;
	Manager->GetClosedDoors(ClosedDoors);
	for (ACatrunDoor* Door : ClosedDoors)
	{
		const bool bNear = FVector::Dist2D(Door->GetDoorwayCenter(), GetActorLocation()) <= TriggerDistance;
		if (bNear && PathCrossesDoorway(*Door, TriggerDistance + 150.f))
		{
			return Door;
		}
	}
	return nullptr;
}

bool ACatrunArmor::PathCrossesDoorway(const ACatrunDoor& Door, float LookAhead) const
{
	// The doorway as a tall box (height does not matter), slightly widened.
	FBox Doorway = Door.GetGateBox()->Bounds.GetBox();
	Doorway.Min.Z = -100000.f;
	Doorway.Max.Z = 100000.f;
	Doorway = Doorway.ExpandBy(FVector(10.f, 10.f, 0.f));

	// Follow the path from the armor's position through the next corners, for LookAhead cm.
	FVector Previous = GetActorLocation();
	float Travelled = 0.f;
	for (int32 i = NextCorner; i < PathCorners.Num() && Travelled < LookAhead; ++i)
	{
		const FVector Corner(PathCorners[i].X, PathCorners[i].Y, Previous.Z);
		const FVector Segment = Corner - Previous;
		FVector HitLocation, HitNormal;
		float HitTime;
		if (FMath::LineExtentBoxIntersection(Doorway, Previous, Corner, FVector::ZeroVector, HitLocation, HitNormal, HitTime))
		{
			return true;
		}
		Travelled += Segment.Size2D();
		Previous = Corner;
	}
	return false;
}

bool ACatrunArmor::IsPathDebugEnabled() const
{
	return bDebugDrawPath && CVarArmorPaths.GetValueOnGameThread() != 0;
}

void ACatrunArmor::DrawDebug() const
{
#if ENABLE_DRAW_DEBUG
	if (!IsPathDebugEnabled())
	{
		return;
	}
	if (!bHasDestination)
	{
		return;
	}
	const FVector Lift(0.f, 0.f, 10.f);
	FVector Previous = GetActorLocation() + Lift;
	for (int32 i = NextCorner; i < PathCorners.Num(); ++i)
	{
		const FVector Corner = FVector(PathCorners[i].X, PathCorners[i].Y, GetActorLocation().Z) + Lift;
		DrawDebugLine(GetWorld(), Previous, Corner, FColor::Cyan, false, -1.f, 0, 4.f);
		Previous = Corner;
	}
	DrawDebugSphere(GetWorld(), FVector(Destination.X, Destination.Y, GetActorLocation().Z) + Lift, 20.f, 8, FColor::Magenta, false, -1.f);
#endif
}


bool ACatrunArmor::TryGetActiveTravelDestination(FVector& OutDestination) const
{
	switch (TravelIntent)
	{
	case ETravelIntent::Patrol:
		if (!PatrolPoints.IsValidIndex(PatrolIndex) || !IsValid(PatrolPoints[PatrolIndex])) return false;
		OutDestination = PatrolPoints[PatrolIndex]->GetActorLocation(); return true;
	case ETravelIntent::ReturnPost: OutDestination = PostLocation; return true;
	case ETravelIntent::Investigation:
	case ETravelIntent::Mark: OutDestination = Destination; return true;
	default: return false;
	}
}

void ACatrunArmor::ReplanAfterDoor()
{
	FVector Target;
	if (TryGetActiveTravelDestination(Target) && PlanPath(Target)) { bAwaitingDoorReplan = false; BeginLeg(); return; }
	PathCorners.Reset(); NextCorner = 0;
	// Retain travel/sound intent on temporary path failure; retry at bounded intervals, never follow stale corners.
	bAwaitingDoorReplan = TravelIntent != ETravelIntent::None;
	DoorReplanWait = .5f;
	SetAction(EArmorAction::Idle);
}

bool ACatrunArmor::GetTurnPlaybackTime(float& OutTime) const
{
	const UAnimationAsset* Expected = bTurningRight ? TurnRightAnim.Get() : TurnLeftAnim.Get();
	if (auto* Single = GetMesh()->GetSingleNodeInstance(); Single && Single->GetCurrentAsset() == Expected)
	{
		OutTime = Single->GetCurrentTime(); return true;
	}
	if (auto* Instance = GetMesh()->GetAnimInstance())
	{
		// Dynamic montage segment conversion respects start offsets, looping and segment play rate.
		if (const UAnimMontage* Montage = Instance->GetCurrentActiveMontage())
		{
			const float Position = Instance->Montage_GetPosition(Montage);
			for (const auto& Slot : Montage->SlotAnimTracks)
			{
				if (const FAnimSegment* Segment = Slot.AnimTrack.GetSegmentAtTime(Position); Segment && Segment->GetAnimReference() == Expected)
				{ OutTime = Segment->ConvertTrackPosToAnimPos(Position); return true; }
			}
		}
	}
	return false;
}

void ACatrunArmor::CommitTurn(bool bCompleted)
{
	if (bTurnCommitted) return;
	bTurnCommitted = true; // exactly once, including capture/sound interruption and 180-degree chains
	const auto* Sequence = Cast<UAnimSequence>(bTurningRight ? TurnRightAnim.Get() : TurnLeftAnim.Get());
	float SampleTime = 0.f;
	const bool bHasPlayback = GetTurnPlaybackTime(SampleTime);
	FQuat LocalDelta = FQuat::Identity;
	if (Sequence)
	{
		if (bCompleted) SampleTime = Sequence->GetPlayLength();
		else if (!bHasPlayback)
		{
			// No matching player: explicitly sample the actual curve at the native clock. Never estimate yaw linearly.
			SampleTime = ActionTime*FMath::Max(.1f,TurnPlayRate)*Sequence->RateScale;
			UE_LOG(LogCatrunSound, Warning, TEXT("%s turn has no matching playback; using native time for curve sample."), *GetName());
		}
		SampleTime = FMath::Clamp(SampleTime, 0.f, Sequence->GetPlayLength());
		LocalDelta = Sequence->ExtractRootMotionFromRange(0.0, SampleTime, FAnimExtractContext(SampleTime, true)).GetRotation();
	}
	else
	{
		// Missing clips never synthesize a partial turn. At completion retain the documented axis fallback.
		if (bCompleted) LocalDelta = FRotator(0.f, bTurningRight ? 90.f : -90.f, 0.f).Quaternion();
		UE_LOG(LogCatrunSound, Warning, TEXT("%s missing turn sequence; %s fallback."), *GetName(), bCompleted ? TEXT("axis endpoint") : TEXT("retain heading"));
	}
	const FQuat ActorDelta = Sequence ? TurnMeshBasis*LocalDelta*TurnMeshBasis.Inverse() : LocalDelta;
	SetActorRotation((TurnStartActorRotation*ActorDelta).GetNormalized());
	// Authored BP dynamic montages have zero outgoing blend: next action removes the old root pose.
}
