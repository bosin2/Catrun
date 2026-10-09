#include "CatrunArmor.h"

#include "Catrun.h"
#include "Perception/AlertMarkComponent.h"
#include "Perception/CatrunCatQueries.h"
#include "Perception/VisionFanComponent.h"
#include "Pathfinding/ArmorPathfinder.h"
#include "Sound/CatrunDoor.h"
#include "Sound/CatrunSoundSettings.h"
#include "Sound/SoundGridManager.h"
#include "AIController.h"
#include "Animation/AnimationAsset.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/BoxComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "DrawDebugHelpers.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"

namespace
{
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

	AlertMark = CreateDefaultSubobject<UCatrunAlertMarkComponent>(TEXT("AlertMark"));
	AlertMark->SetupAttachment(RootComponent);
	AlertMark->SetRelativeLocation(FVector(0.f, 0.f, 190.f)); // just above the head
}

void ACatrunArmor::BeginPlay()
{
	Super::BeginPlay();
	ApplyMoveSpeed();
	SoundManager = ASoundGridManager::Get(this);
	MeshBaseScale = GetMesh()->GetRelativeScale3D();
	// The post is the starting place; its direction is rounded to one of the four directions.
	PostLocation = GetActorLocation();
	PostRotation = FRotator(0.f, SnapYaw(GetActorRotation().Yaw), 0.f);
	SetActorRotation(PostRotation);
	SetAction(EArmorAction::Idle);
}

// ---------------------------------------------------------------------------
// Hearing
// ---------------------------------------------------------------------------

void ACatrunArmor::OnSoundHeard_Implementation(const FCatrunSoundEvent& Event, float RemainingBudget)
{
	// Rule 4.3: an armor on its way ignores sounds that are not louder than the one it follows.
	const bool bNotLouder = static_cast<uint8>(Event.Size) <= static_cast<uint8>(CurrentSoundSize);
	if (bHasDestination && bNotLouder)
	{
		UE_LOG(LogCatrunSound, Log, TEXT("%s ignores a sound (size %d is not louder than %d)."), *GetName(), (int32)Event.Size, (int32)CurrentSoundSize);
		return;
	}

	// The destination is where the sound was made (a snapshot), never the cat's live position.
	if (!PlanPath(Event.Location))
	{
		return;
	}
	CurrentSoundSize = Event.Size;
	Destination = Event.Location;
	UE_LOG(LogCatrunSound, Log, TEXT("%s heard a sound (size %d, remaining %.0f), path has %d corners."),
		*GetName(), (int32)Event.Size, RemainingBudget, PathCorners.Num());

	// A sound beats everything: stop returning to the post and go to the sound.
	const bool bWasStandingStill = !bHasDestination;
	bHasDestination = true;
	bReturningToPost = false;
	bRestorePostHeading = false;

	if (bWasStandingStill)
	{
		SetAction(EArmorAction::Reacting); // react first, then walk
	}
	else if (Action == EArmorAction::Walking)
	{
		BeginLeg(); // already walking: simply aim for the new path
	}
	// Other actions (reacting, turning, opening a door) finish first and then use the new path.
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

	TArray<FVector> Corners;
	if (!CatrunArmorPath::FindPath(Manager->GetGrid(), GetActorLocation(), NewDestination, Params, Corners))
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

void ACatrunArmor::PlayAnimation(UAnimationAsset* Anim, bool bLoop)
{
	if (Anim && GetMesh())
	{
		GetMesh()->PlayAnimation(Anim, bLoop);
	}
}

UAnimationAsset* ACatrunArmor::MoveAnimation() const
{
	// Walking back to the post uses the walk animation (if there is one); chasing a sound runs.
	return (bReturningToPost && WalkAnim) ? WalkAnim.Get() : RunAnim.Get();
}

void ACatrunArmor::ApplyMoveSpeed()
{
	GetCharacterMovement()->MaxWalkSpeed = bReturningToPost ? WalkSpeed : ChaseSpeed;
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
		UAnimationAsset* TurnAnim = bTurningRight ? TurnRightAnim : TurnLeftAnim;
		PlayAnimation(TurnAnim, false);
		ActionDuration = AnimationLength(TurnAnim);
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
		PlayAnimation(ArrivalLookAnim, false);
		ActionDuration = AnimationLength(ArrivalLookAnim);
		break;
	}
}

// Decides what to do next: turn on the spot if the next corner is far off the heading, else walk.
void ACatrunArmor::BeginLeg()
{
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
	PathCorners.Reset();
	NextCorner = 0;
	bHasDestination = false; // arrived: from now on any sound is followed (rule 4.3)

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
	const bool bFarFromPost = FVector::Dist2D(GetActorLocation(), PostLocation) > 50.f;
	if (bReturnToPost && bFarFromPost && PlanPath(PostLocation))
	{
		bReturningToPost = true;
		BeginLeg(); // run back; this is no sound trip, so a new sound is still accepted
		return;
	}
	bRestorePostHeading = bReturnToPost;
	SetAction(EArmorAction::Idle);
}

// While standing at the post, slowly turn back to the direction the armor started with.
void ACatrunArmor::TickIdle(float DeltaSeconds)
{
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
	Super::Tick(DeltaSeconds);
	ActionTime += DeltaSeconds;

	switch (Action)
	{
	case EArmorAction::Idle:			TickIdle(DeltaSeconds);			break;
	case EArmorAction::Reacting:		TickReacting(DeltaSeconds);		break;
	case EArmorAction::Walking:			TickWalking(DeltaSeconds);		break;
	case EArmorAction::Turning:			TickTurning(DeltaSeconds);		break;
	case EArmorAction::OpeningDoor:		TickOpeningDoor(DeltaSeconds);	break;
	case EArmorAction::Looking:			TickLooking(DeltaSeconds);		break;
	}
	UpdateDetection();
	DrawDebug();
	UpdateActionLabel();
}

void ACatrunArmor::UpdateDetection()
{
	const UCatrunSoundSettings* S = SoundManager.IsValid() ? SoundManager->GetSettings() : nullptr;
	if (!S)
	{
		return;
	}
	// Size and look of the circle come from the settings asset (read once, when it is available).
	if (!bDetectionConfigured)
	{
		Detection->Configure(S->ArmorDetectRadius, S->ArmorDetectRayCount, S->ArmorDetectColor);
		bDetectionConfigured = true;
	}

	// The circle is only drawn for debugging: by the level's switch or by this armor's own switch.
	const bool bShowCircle = bShowDetectionDisplay || (SoundManager.IsValid() && SoundManager->bDebugShowArmorDetection);
	if (bShowCircle != bDetectionDisplayShown)
	{
		Detection->SetDisplayVisible(bShowCircle);
		bDetectionDisplayShown = bShowCircle;
	}

	// The circle is centred on the armor. 180 degrees to each side = the whole circle.
	Detection->Update(0.f, 180.f);

	APawn* Cat = CatrunCat::Find(this);
	const bool bSees = Cat && !CatrunCat::IsHiding(Cat) && Detection->CanSee(Cat->GetActorLocation(), S->CatSightRadius);

	// Notice the cat the moment it enters the circle. What the armor does next (chase, catch)
	// is added in the next step.
	if (bSees && !bSeeingCat)
	{
		UE_LOG(LogCatrunSound, Log, TEXT("%s noticed the cat."), *GetName());
	}
	// While the cat is inside the circle the "!" stays on. (Show keeps it visible for a short
	// time, so renewing it every frame holds it until the cat leaves.)
	if (bSees)
	{
		AlertMark->Show(0.2f);
	}
	bSeeingCat = bSees;
}

// Shows the action name above the head and turns the text toward the camera.
void ACatrunArmor::UpdateActionLabel()
{
	ActionLabel->SetVisibility(bDebugDrawPath);
	if (!bDebugDrawPath)
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
	const float Step = bTurningRight ? 90.f : -90.f;
	SetActorRotation(FRotator(0.f, SnapYaw(GetActorRotation().Yaw + Step), 0.f));

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
		BeginLeg(); // the door is gone, carry on
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
		PlanPath(bReturningToPost ? PostLocation : Destination);
		BeginLeg();
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
	AddActorWorldOffset(Walked, /*bSweep*/ false, nullptr, ETeleportType::TeleportPhysics);
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

void ACatrunArmor::DrawDebug() const
{
#if ENABLE_DRAW_DEBUG
	if (!bDebugDrawPath)
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
