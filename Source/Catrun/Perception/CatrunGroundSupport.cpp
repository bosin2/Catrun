#include "CatrunGroundSupport.h"
#include "Components/CapsuleComponent.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"

bool CatrunGround::FindSupport(const UCapsuleComponent& Capsule, const FVector& ReferenceCenter,
	float ProbeUp, float ProbeDown, const FCollisionQueryParams& Params,
	FHitResult& OutHit, FVector& OutCenter)
{
	OutHit = FHitResult();
	OutCenter = FVector::ZeroVector;
	UWorld* World = Capsule.GetWorld();
	const float Radius = Capsule.GetScaledCapsuleRadius();
	const float HalfHeight = Capsule.GetScaledCapsuleHalfHeight();
	if (!World || ReferenceCenter.ContainsNaN() || !FMath::IsFinite(ProbeUp) || !FMath::IsFinite(ProbeDown)
		|| ProbeUp < 0.f || ProbeDown < 0.f || ProbeUp + ProbeDown <= UE_SMALL_NUMBER
		|| Radius <= 0.f || HalfHeight < Radius || FMath::Abs(Capsule.GetUpVector().Z) < .99f) return false;
	const FVector Start = ReferenceCenter + FVector(0,0,ProbeUp);
	const FVector End = ReferenceCenter - FVector(0,0,ProbeDown);
	const FCollisionResponseParams Responses(Capsule.GetCollisionResponseToChannels());
	if (!World->SweepSingleByChannel(OutHit, Start, End, Capsule.GetComponentQuat(),
		Capsule.GetCollisionObjectType(), FCollisionShape::MakeCapsule(Radius, HalfHeight), Params, Responses)
		|| !OutHit.IsValidBlockingHit() || OutHit.ImpactNormal.Z < .65f || Cast<APawn>(OutHit.GetActor())) return false;
	// A side/edge contact cannot provide an unrestricted fallback around a blocker or over a gap.
	const float SupportRadius = FMath::Max(0.f, Radius - .15f);
	if (FVector::DistSquared2D(OutHit.ImpactPoint, OutHit.Location) > FMath::Square(SupportRadius)
		|| OutHit.Location.Z < End.Z - .01f || OutHit.Location.Z > Start.Z + .01f) return false;
	// ImpactPoint can be off-center on a stone face; Location is the swept capsule center.
	OutCenter = FVector(ReferenceCenter.X, ReferenceCenter.Y, OutHit.Location.Z + 2.f);
	return true;
}
