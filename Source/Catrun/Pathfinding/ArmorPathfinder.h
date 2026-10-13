#pragma once

#include "CoreMinimal.h"

struct FCatrunGridData;

/**
 * Path finding for the armor: A* on the grid that moves only up, down, left and right.
 *
 * Why not diagonals: the armor walks like a heavy machine in straight lines and turns by
 * 90 degrees, so a path is just a list of corners.
 *
 * Rules the search follows:
 *  - The armor may only stand on cells that are at least ClearanceRadius away from walls.
 *    This keeps the big armor off walls and makes it too wide for cat-holes.
 *  - Closed doors do not stop the armor (it opens them), so they are not checked here.
 *  - Every 90 degree turn costs TurnPenalty extra, so paths prefer long straight lines.
 */
namespace CatrunArmorPath
{
	struct FParams
	{
		// Half the armor width in cm. Cells with less wall distance are off limits.
		float ClearanceRadius = 35.f;

		// Extra cost in cm added at every 90 degree turn.
		float TurnPenalty = 100.f;
	};

	// True if the armor can stand on this cell (floor cell with enough room around it).
	CATRUN_API bool CanStand(const FCatrunGridData& Grid, int32 Cell, float ClearanceRadius);

	/**
	 * Finds the cheapest path from Start to Goal.
	 *
	 * @param OutCorners  Points to walk through in order: the start cell, every corner, the goal cell.
	 *                    Between two corners the path is a straight line along the X or Y axis.
	 * @return false when no path exists.
	 */
	CATRUN_API bool FindPath(const FCatrunGridData& Grid, const FVector& Start, const FVector& Goal,
		const FParams& Params, TArray<FVector>& OutCorners);
}
