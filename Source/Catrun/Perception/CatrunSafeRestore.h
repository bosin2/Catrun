#pragma once
#include "CoreMinimal.h"
class APawn;

namespace CatrunRestore
{
	// Queries the actual primitive even while ActorEnableCollision is false. Never ignores blockers.
	CATRUN_API bool IsPlacementClear(const APawn& Pawn, const FTransform& Transform);
	// Keeps collision off; local fallback requires same-floor support and a clear capsule transit.
	// False queues clean stage recovery; callers keep collision/movement disabled until travel.
	CATRUN_API bool PlaceForCollision(APawn& Pawn, const FTransform& Desired, bool bRestoreCollision);
}
