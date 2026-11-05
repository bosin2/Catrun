#pragma once
#include "CoreMinimal.h"

class UCapsuleComponent;
struct FCollisionQueryParams;
struct FHitResult;

namespace CatrunGround
{
	// Pure vertical query using the actual capsule and responses, even while collision is disabled.
	// ProbeUp/Down bound capsule-center travel around ReferenceCenter. First blocking support must
	// be walkable, nonpenetrating, non-Pawn and inside the footprint. Center includes 2cm clearance.
	CATRUN_API bool FindSupport(const UCapsuleComponent& Capsule, const FVector& ReferenceCenter,
		float ProbeUp, float ProbeDown, const FCollisionQueryParams& Params,
		FHitResult& OutHit, FVector& OutCenter);
}
