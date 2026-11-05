#include "CatrunPerceptionPolicy.h"
#include "Components/CapsuleComponent.h"
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
