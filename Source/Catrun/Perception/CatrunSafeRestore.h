#pragma once
#include "CoreMinimal.h"
#include "Engine/EngineTypes.h"
class APawn;

namespace CatrunRestore
{
	// Queries the actual primitive even while ActorEnableCollision is false. Never ignores blockers.
	CATRUN_API bool IsPlacementClear(const APawn& Pawn, const FTransform& Transform);
	// Places the actual capsule on walkable support near a designated spawn.
	CATRUN_API bool TryPlaceOnSupport(APawn& Pawn, const FTransform& Reference);
	// Keeps collision off; local fallback requires same-floor support and a clear capsule transit.
	// False defers recovery until the caller has finished releasing the temporary action.
	CATRUN_API bool PlaceForCollision(APawn& Pawn, const FTransform& Desired, bool bRestoreCollision,
		EMovementMode RestoreMode = MOVE_MAX, uint8 RestoreCustomMode = 0);
}
