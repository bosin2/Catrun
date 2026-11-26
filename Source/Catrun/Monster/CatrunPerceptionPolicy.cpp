#include "CatrunPerceptionPolicy.h"
#include "CatrunSightBlockerSubsystem.h"
#include "Components/CapsuleComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "GameFramework/Character.h"

float CatrunPerception::SightDistance(const UWorld& World, const FVector& From, const FVector& To, const AActor* Observer, const AActor* Target)
{
	FCollisionQueryParams Params(SCENE_QUERY_STAT(CatrunSight), true, Observer);
	if (Target) Params.AddIgnoredActor(Target);
	FCollisionObjectQueryParams Objects(FCollisionObjectQueryParams::AllObjects);
	Objects.RemoveObjectTypesToQuery(ECC_Pawn);
	TArray<FHitResult> Hits;
	World.LineTraceMultiByObjectType(Hits, From, To, Objects, Params);
	float Distance = FVector::Distance(From, To);
	for (const FHitResult& Hit : Hits)
	{
		if (const auto* Component = Hit.GetComponent(); Component && Component->GetCollisionResponseToChannel(ECC_Visibility) == ECR_Block)
			Distance = FMath::Min(Distance, Hit.Distance);
	}
	// Complex traces see render triangles. A hidden gameplay proxy narrower than its simple collision
	// (Stage 3 counterweights use a statue mesh inside a 120x120x150 box) would otherwise leak sight beside
	// the visible weight. Registered proxies also occlude by simple collision. Nothing registered: no cost.
	UCatrunSightBlockerSubsystem* Registry = UCatrunSightBlockerSubsystem::Get(&World);
	if (!Registry || Registry->Num() == 0) return Distance;
	const FVector Direction = (To - From).GetSafeNormal();
	if (Direction.IsNearlyZero()) return Distance;
	FCollisionQueryParams SimpleParams(SCENE_QUERY_STAT(CatrunSightSimple), false, Observer);
	for (const TWeakObjectPtr<UPrimitiveComponent>& Weak : Registry->GetBlockers())
	{
		UPrimitiveComponent* Component = Weak.Get();
		if (!IsValid(Component) || !Component->IsRegistered() || Component->GetWorld() != &World
			|| !Component->IsQueryCollisionEnabled() || Component->GetCollisionObjectType() == ECC_Pawn
			|| Component->GetCollisionResponseToChannel(ECC_Visibility) != ECR_Block)
			continue;
		const AActor* Owner = Component->GetOwner();
		if (Owner && (Owner == Observer || Owner == Target)) continue;
		FHitResult Hit;
		if (Component->LineTraceComponent(Hit, From, From + Direction * Distance, SimpleParams))
			Distance = FMath::Min(Distance, Hit.Distance);
	}
	return Distance;
}

bool CatrunPerception::HasDirectSight(const AActor& Observer, const AActor& Target, float Height)
{
	if (!Observer.GetWorld() || Target.GetWorld() != Observer.GetWorld()) return false;
	float Floor = Target.GetActorLocation().Z;
	if (const auto* Character = Cast<ACharacter>(&Target))
		Floor -= Character->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
	FVector From = Observer.GetActorLocation(), To = Target.GetActorLocation();
	From.Z = To.Z = Floor + FMath::Max(1.f, Height);
	return SightDistance(*Observer.GetWorld(), From, To, &Observer, &Target) >= FVector::Distance(From, To)-KINDA_SMALL_NUMBER;
}
