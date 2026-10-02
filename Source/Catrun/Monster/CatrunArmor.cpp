#include "CatrunArmor.h"

#include "../Catrun.h"
#include "AIController.h"
#include "Animation/AnimationAsset.h"
#include "Components/SkeletalMeshComponent.h"
#include "DrawDebugHelpers.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "NavigationData.h"
#include "NavigationSystem.h"
#include "NavMesh/RecastNavMesh.h"

ACatrunArmor::ACatrunArmor()
{
	PrimaryActorTick.bCanEverTick = true;
	AIControllerClass = AAIController::StaticClass();
	AutoPossessAI = EAutoPossessAI::PlacedInWorldOrSpawned;
	bUseControllerRotationYaw = false;
	GetCharacterMovement()->bOrientRotationToMovement = true;
}

void ACatrunArmor::BeginPlay()
{
	Super::BeginPlay();
	GetCharacterMovement()->MaxWalkSpeed = ChaseSpeed;
	SetMoving(false);
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

void ACatrunArmor::PossessedBy(AController* NewController)
{
	Super::PossessedBy(NewController);
	if (AAIController* AI = Cast<AAIController>(NewController))
	{
		AI->ReceiveMoveCompleted.AddUniqueDynamic(this, &ACatrunArmor::HandleMoveCompleted);
	}
}

void ACatrunArmor::OnSoundHeard_Implementation(const FCatrunSoundEvent& Event, float RemainingBudget)
{
	// Design doc 4.3: walking armor only follows a louder sound; arrived armor follows any sound.
	if (bMoving && static_cast<uint8>(Event.Size) <= static_cast<uint8>(CurrentSoundSize))
	{
		UE_LOG(LogCatrunSound, Log, TEXT("%s ignores sound (size %d <= current %d)."), *GetName(), (int32)Event.Size, (int32)CurrentSoundSize);
		return;
	}

	AAIController* AI = Cast<AAIController>(GetController());
	if (!AI)
	{
		return;
	}

	// Destination is the sound's location snapshot, never the cat's live position.
	const EPathFollowingRequestResult::Type Result = AI->MoveToLocation(Event.Location, AcceptanceRadius,
		/*bStopOnOverlap*/ true, /*bUsePathfinding*/ true, /*bProjectDestinationToNavigation*/ true, /*bCanStrafe*/ false);
	if (Result == EPathFollowingRequestResult::Failed)
	{
		// Report why: most failures are an empty NavMesh or a start/goal point that is not on it.
		UNavigationSystemV1* Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld());
		const ANavigationData* NavData = Nav ? Nav->GetDefaultNavDataInstance(FNavigationSystem::DontCreate) : nullptr;
		const ARecastNavMesh* Recast = Cast<ARecastNavMesh>(NavData);
		FNavLocation Projected;
		const FVector Extent(150.f, 150.f, 400.f);
		const bool bStartOnNav = Nav && Nav->ProjectPointToNavigation(GetActorLocation(), Projected, Extent);
		const bool bGoalOnNav = Nav && Nav->ProjectPointToNavigation(Event.Location, Projected, Extent);
		UE_LOG(LogCatrunSound, Warning, TEXT("%s could not find a path to %s. NavSystem=%d NavData=%s tiles=%d startOnNav=%d goalOnNav=%d"),
			*GetName(), *Event.Location.ToString(), Nav != nullptr, NavData ? *NavData->GetName() : TEXT("none"),
			Recast ? Recast->GetNavMeshTilesCount() : -1, bStartOnNav, bGoalOnNav);
		return;
	}

	SetMoving(Result != EPathFollowingRequestResult::AlreadyAtGoal);
	CurrentSoundSize = Event.Size;
	Destination = Event.Location;
	UE_LOG(LogCatrunSound, Log, TEXT("%s heard sound (size %d, remaining %.0f) and moves to %s."), *GetName(), (int32)Event.Size, RemainingBudget, *Event.Location.ToString());
}

void ACatrunArmor::HandleMoveCompleted(FAIRequestID RequestID, EPathFollowingResult::Type Result)
{
	SetMoving(false);
	UE_LOG(LogCatrunSound, Log, TEXT("%s finished moving (result %d)."), *GetName(), (int32)Result);
}

void ACatrunArmor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
#if ENABLE_DRAW_DEBUG
	if (!bDebugDrawPath || !bMoving)
	{
		return;
	}
	const AAIController* AI = Cast<AAIController>(GetController());
	const UPathFollowingComponent* Follow = AI ? AI->GetPathFollowingComponent() : nullptr;
	if (Follow && Follow->GetPath().IsValid())
	{
		const TArray<FNavPathPoint>& Points = Follow->GetPath()->GetPathPoints();
		for (int32 i = 0; i + 1 < Points.Num(); ++i)
		{
			DrawDebugLine(GetWorld(), Points[i].Location + FVector(0, 0, 10), Points[i + 1].Location + FVector(0, 0, 10), FColor::Cyan, false, -1.f, 0, 4.f);
		}
	}
	DrawDebugSphere(GetWorld(), Destination + FVector(0, 0, 10), 20.f, 8, FColor::Magenta, false, -1.f);
#endif
}
