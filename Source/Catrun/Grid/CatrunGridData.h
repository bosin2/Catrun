#pragma once

#include "CoreMinimal.h"
#include "CatrunGridData.generated.h"

class UWorld;
class UCatrunSoundSettings;

/**
 * Shared definitions for moving around the grid.
 *
 * The grid is a set of square cells laid over the level floor (X = east, Y = south).
 * Every cell has 8 neighbours. Directions 0..3 are the straight ones, 4..7 are diagonals.
 */
namespace CatrunGrid
{
	constexpr int32 NumDirs = 8;
	constexpr int32 NumStraightDirs = 4;

	//                                   E   W   S   N  SE  SW  NE  NW
	inline constexpr int32 DirX[NumDirs] = { 1, -1,  0,  0,  1, -1,  1, -1 };
	inline constexpr int32 DirY[NumDirs] = { 0,  0,  1, -1,  1,  1, -1, -1 };

	// Direction that points back to where we came from.
	inline constexpr int32 Opposite[NumDirs] = { 1, 0, 3, 2, 7, 6, 5, 4 };

	constexpr int32 DirE = 0;
	constexpr int32 DirW = 1;
	constexpr int32 DirS = 2;
	constexpr int32 DirN = 3;
	constexpr int32 DirSE = 4;
	constexpr int32 DirSW = 5;

	inline bool IsDiagonal(int32 Dir) { return Dir >= NumStraightDirs; }
}

/**
 * The baked grid: where cells exist, which edges between cells are blocked by walls,
 * and how far every cell is from the nearest wall.
 *
 * It is built once from the level geometry (see Bake) and then only read. Sound travel
 * and the armor pathfinder both use it, so what the player sees and what the armor
 * walks on always agree.
 *
 * It is a USTRUCT only so that the baked arrays are saved with the level.
 */
USTRUCT()
struct CATRUN_API FCatrunGridData
{
	GENERATED_BODY()

	// ---- Baked data ---------------------------------------------------------

	// World position of the grid's north-west corner (Z = floor height).
	UPROPERTY()
	FVector Origin = FVector::ZeroVector;

	UPROPERTY()
	float CellSize = 25.f;

	UPROPERTY()
	int32 Width = 0;

	UPROPERTY()
	int32 Height = 0;

	// 1 = a floor cell. 0 = no floor here (outside the map or inside a wall).
	UPROPERTY()
	TArray<uint8> Walkable;

	// Sound travel cost multiplier of the floor material (stone = 1, carpet = 2, ...).
	UPROPERTY()
	TArray<float> CostMultiplier;

	// Bit i is set when the edge from this cell toward direction i is open (no wall between).
	UPROPERTY()
	TArray<uint8> EdgeMask;

	// Distance in cm from the cell centre to the nearest wall, measured with rays.
	// Never larger than WallProbeLength (the rays' length). Used to keep big monsters off walls.
	UPROPERTY()
	TArray<float> WallDistance;

	UPROPERTY()
	float WallProbeLength = 0.f;

	// ---- Queries ------------------------------------------------------------

	bool IsValid() const { return Width > 0 && Height > 0; }
	int32 NumCells() const { return Width * Height; }

	bool InBounds(int32 X, int32 Y) const { return X >= 0 && Y >= 0 && X < Width && Y < Height; }
	int32 CellIndex(int32 X, int32 Y) const { return Y * Width + X; }
	int32 CellX(int32 Cell) const { return Cell % Width; }
	int32 CellY(int32 Cell) const { return Cell / Width; }

	FVector CellCenter(int32 Cell) const;

	// Cell that contains a world location, or INDEX_NONE when outside the grid.
	int32 WorldToCell(const FVector& WorldLocation) const;

	bool IsWalkable(int32 Cell) const { return Walkable.IsValidIndex(Cell) && Walkable[Cell] != 0; }
	bool IsEdgeOpen(int32 Cell, int32 Dir) const { return EdgeMask.IsValidIndex(Cell) && (EdgeMask[Cell] & (1 << Dir)) != 0; }

	// The cell next to Cell in direction Dir, or INDEX_NONE when that leaves the grid.
	int32 Neighbor(int32 Cell, int32 Dir) const;

	// Nearest cell (searching outward ring by ring, at most MaxRing rings) that passes Accept.
	int32 FindNearestCell(const FVector& WorldLocation, int32 MaxRing, TFunctionRef<bool(int32)> Accept) const;

	// ---- Building -----------------------------------------------------------

	// Builds the grid from the level: actors tagged Settings.FloorTag define the floor,
	// actors tagged Settings.WallTag block edges. Returns false when no floor was found.
	bool Bake(UWorld& World, const UCatrunSoundSettings& Settings);

private:
	void BakeFloorCells(const TArray<TPair<FBox, float>>& Floors);
	void BakeEdges(UWorld& World, const UCatrunSoundSettings& Settings, int32& OutBlockedEdges);
	void BakeDiagonalEdges();
	void BakeWallDistance(UWorld& World, const UCatrunSoundSettings& Settings);
};
