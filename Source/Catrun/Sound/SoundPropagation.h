#pragma once

#include "CoreMinimal.h"

struct FCatrunGridData;

/**
 * How far a sound travels over the grid.
 *
 * The result is a "distance field": for every cell, the length of the shortest open path
 * from the sound source to that cell. Walls and closed doors cut the paths, so sound
 * bends around corners and continues through doors like a real wave would.
 */
namespace CatrunSoundPropagation
{
	// Distance value meaning "the sound never reaches this cell".
	constexpr float Unreached = MAX_flt;

	/**
	 * Dijkstra search from SourceCell.
	 *
	 * @param Grid            The baked grid.
	 * @param ClosedGateCells One entry per cell, non-zero where a closed door blocks sound.
	 * @param SourceCell      Cell where the sound is made.
	 * @param Budget          Travel limit in cm. Paths longer than this are not explored.
	 * @param OutDistance     One entry per cell: path length in cm, or Unreached.
	 * @return Number of cells the sound reaches.
	 */
	CATRUN_API int32 Run(const FCatrunGridData& Grid, const TArray<uint8>& ClosedGateCells,
		int32 SourceCell, float Budget, TArray<float>& OutDistance);
}
