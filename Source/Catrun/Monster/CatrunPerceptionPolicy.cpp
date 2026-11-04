#include "CatrunPerceptionPolicy.h"
#include "Components/CapsuleComponent.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "GameFramework/Character.h"

bool CatrunPerception::HasDirectSight(const AActor& Observer, const AActor& Target, float Height)
{
	if (!Observer.GetWorld() || Target.GetWorld() != Observer.GetWorld()) return false;
	float Floor = Target.GetActorLocation().Z;
	if (const auto* Character = Cast<ACharacter>(&Target))
		Floor -= Character->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
	FVector From = Observer.GetActorLocation(), To = Target.GetActorLocation();
	From.Z = To.Z = Floor + FMath::Max(1.f, Height);
	FCollisionQueryParams Params(SCENE_QUERY_STAT(CatrunDirectSight), true, &Observer);
	Params.AddIgnoredActor(&Target);
	return !Observer.GetWorld()->LineTraceTestByChannel(From, To, ECC_Visibility, Params);
}
