#include "CatrunArmor.h"

#include "Catrun.h"
#include "Pathfinding/ArmorPathfinder.h"
#include "Sound/CatrunSoundSettings.h"
#include "Sound/SoundGridManager.h"
#include "AIController.h"
#include "Animation/AnimationAsset.h"
#include "Components/SkeletalMeshComponent.h"
#include "DrawDebugHelpers.h"
#include "GameFramework/CharacterMovementComponent.h"

ACatrunArmor::ACatrunArmor()
{
	PrimaryActorTick.bCanEverTick = true;

	// The AI controller is only needed so the character movement runs; it does no pathfinding.
	AIControllerClass = AAIController::StaticClass();
	AutoPossessAI = EAutoPossessAI::PlacedInWorldOrSpawned;

	// Turn the body toward the walking direction.
	bUseControllerRotationYaw = false;
	GetCharacterMovement()->bOrientRotationToMovement = true;
}

void ACatrunArmor::BeginPlay()
{
	Super::BeginPlay();
	GetCharacterMovement()->MaxWalkSpeed = ChaseSpeed;
	SoundManager = ASoundGridManager::Get(this);
	SetMoving(false);
}

// ---------------------------------------------------------------------------
// Hearing
// ---------------------------------------------------------------------------

void ACatrunArmor::OnSoundHeard_Implementation(const FCatrunSoundEvent& Event, float RemainingBudget)
{
	// Rule 4.3: a walking armor ignores sounds that are not louder than the one it follows.
	const bool bNotLouder = static_cast<uint8>(Event.Size) <= static_cast<uint8>(CurrentSoundSize);
	if (bMoving && bNotLouder)
	{
		UE_LOG(LogCatrunSound, Log, TEXT("%s ignores a sound (size %d is not louder than %d)."), *GetName(), (int32)Event.Size, (int32)CurrentSoundSize);
		return;
	}

	// The destination is where the sound was made (a snapshot), never the cat's live position.
	if (!StartWalkingTo(Event.Location))
	{
		return;
	}
	CurrentSoundSize = Event.Size;
	UE_LOG(LogCatrunSound, Log, TEXT("%s heard a sound (size %d, remaining %.0f) and walks to %s via %d corners."),
		*GetName(), (int32)Event.Size, RemainingBudget, *Event.Location.ToString(), PathCorners.Num());
}

// ---------------------------------------------------------------------------
// Walking
// ---------------------------------------------------------------------------

bool ACatrunArmor::StartWalkingTo(const FVector& NewDestination)
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

	PathCorners = MoveTemp(Corners);
	NextCorner = 0;
	Destination = NewDestination;
	SetMoving(true);
	return true;
}

void ACatrunArmor::FollowPath()
{
	// Closed doors near the armor are opened (the cat cannot do this).
	if (ASoundGridManager* Manager = SoundManager.Get())
	{
		Manager->OpenDoorsNear(GetActorLocation(), Manager->GetSettings()->ArmorDoorOpenDistance);
	}

	// Corner reached? Then aim for the next one.
	while (NextCorner < PathCorners.Num()
		&& FVector::Dist2D(GetActorLocation(), PathCorners[NextCorner]) <= CornerTolerance)
	{
		++NextCorner;
	}
	if (NextCorner >= PathCorners.Num())
	{
		StopWalking();
		return;
	}

	const FVector ToCorner = PathCorners[NextCorner] - GetActorLocation();
	AddMovementInput(ToCorner.GetSafeNormal2D(), 1.f);
}

void ACatrunArmor::StopWalking()
{
	PathCorners.Reset();
	NextCorner = 0;
	SetMoving(false);
	UE_LOG(LogCatrunSound, Log, TEXT("%s arrived."), *GetName());
}

void ACatrunArmor::SetMoving(bool bNewMoving)
{
	bMoving = bNewMoving;
	UAnimationAsset* Anim = bMoving ? MoveAnim : IdleAnim;
	if (Anim && GetMesh())
	{
		GetMesh()->PlayAnimation(Anim, /*bLooping*/ true);
	}
}

void ACatrunArmor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!bMoving)
	{
		return;
	}
	FollowPath();

#if ENABLE_DRAW_DEBUG
	if (bDebugDrawPath)
	{
		const FVector Lift(0.f, 0.f, 10.f);
		FVector Previous = GetActorLocation() + Lift;
		for (int32 i = NextCorner; i < PathCorners.Num(); ++i)
		{
			const FVector Corner = FVector(PathCorners[i].X, PathCorners[i].Y, GetActorLocation().Z) + Lift;
			DrawDebugLine(GetWorld(), Previous, Corner, FColor::Cyan, false, -1.f, 0, 4.f);
			Previous = Corner;
		}
		DrawDebugSphere(GetWorld(), FVector(Destination.X, Destination.Y, GetActorLocation().Z) + Lift, 20.f, 8, FColor::Magenta, false, -1.f);
	}
#endif
}
