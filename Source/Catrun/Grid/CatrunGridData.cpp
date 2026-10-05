#include "CatrunGridData.h"

#include "Catrun.h"
#include "Sound/CatrunSoundSettings.h"
#include "CollisionQueryParams.h"
#include "EngineUtils.h"
#include "Engine/World.h"

using namespace CatrunGrid;

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

FVector FCatrunGridData::CellCenter(int32 Cell) const
{
	return FVector(Origin.X + (CellX(Cell) + 0.5f) * CellSize, Origin.Y + (CellY(Cell) + 0.5f) * CellSize, Origin.Z);
}

int32 FCatrunGridData::WorldToCell(const FVector& WorldLocation) const
{
	if (!IsValid())
	{
		return INDEX_NONE;
	}
	const int32 X = FMath::FloorToInt((WorldLocation.X - Origin.X) / CellSize);
	const int32 Y = FMath::FloorToInt((WorldLocation.Y - Origin.Y) / CellSize);
	return InBounds(X, Y) ? CellIndex(X, Y) : INDEX_NONE;
}

int32 FCatrunGridData::Neighbor(int32 Cell, int32 Dir) const
{
	const int32 X = CellX(Cell) + DirX[Dir];
	const int32 Y = CellY(Cell) + DirY[Dir];
	return InBounds(X, Y) ? CellIndex(X, Y) : INDEX_NONE;
}

int32 FCatrunGridData::FindNearestCell(const FVector& WorldLocation, int32 MaxRing, TFunctionRef<bool(int32)> Accept) const
{
	if (!IsValid())
	{
		return INDEX_NONE;
	}
	const int32 CenterX = FMath::FloorToInt((WorldLocation.X - Origin.X) / CellSize);
	const int32 CenterY = FMath::FloorToInt((WorldLocation.Y - Origin.Y) / CellSize);

	int32 Best = INDEX_NONE;
	float BestDistSq = TNumericLimits<float>::Max();

	// Search square rings of growing size. Stop at the first ring that contains a match.
	for (int32 Ring = 0; Ring <= MaxRing && Best == INDEX_NONE; ++Ring)
	{
		for (int32 OffsetY = -Ring; OffsetY <= Ring; ++OffsetY)
		{
			for (int32 OffsetX = -Ring; OffsetX <= Ring; ++OffsetX)
			{
				const bool bOnRing = FMath::Max(FMath::Abs(OffsetX), FMath::Abs(OffsetY)) == Ring;
				if (!bOnRing || !InBounds(CenterX + OffsetX, CenterY + OffsetY))
				{
					continue;
				}
				const int32 Cell = CellIndex(CenterX + OffsetX, CenterY + OffsetY);
				if (!Accept(Cell))
				{
					continue;
				}
				const float DistSq = FVector::DistSquared2D(CellCenter(Cell), WorldLocation);
				if (DistSq < BestDistSq)
				{
					BestDistSq = DistSq;
					Best = Cell;
				}
			}
		}
	}
	return Best;
}

// ---------------------------------------------------------------------------
// Baking
// ---------------------------------------------------------------------------

bool FCatrunGridData::Bake(UWorld& World, const UCatrunSoundSettings& Settings)
{
	// 1) Collect the floors. Each floor is a world-space box plus its sound cost multiplier.
	TArray<TPair<FBox, float>> Floors;
	FBox AllFloors(ForceInit);
	for (TActorIterator<AActor> It(&World); It; ++It)
	{
		AActor* Actor = *It;
		if (!Actor->ActorHasTag(Settings.FloorTag))
		{
			continue;
		}
		float Cost = Settings.DefaultFloorMultiplier;
		for (const TPair<FName, float>& TagCost : Settings.FloorTagMultipliers)
		{
			if (Actor->ActorHasTag(TagCost.Key))
			{
				Cost = TagCost.Value;
			}
		}
		const FBox Box = Actor->GetComponentsBoundingBox(false);
		Floors.Emplace(Box, Cost);
		AllFloors += Box;
	}
	if (Floors.IsEmpty())
	{
		UE_LOG(LogCatrunSound, Error, TEXT("Grid bake: no actor has the floor tag '%s'."), *Settings.FloorTag.ToString());
		return false;
	}

	// 2) Size the grid so that it covers every floor, aligned to whole cells.
	CellSize = FMath::Max(Settings.CellSize, 5.f);
	Origin = FVector(FMath::FloorToFloat(AllFloors.Min.X / CellSize) * CellSize,
		FMath::FloorToFloat(AllFloors.Min.Y / CellSize) * CellSize, AllFloors.Max.Z);
	Width = FMath::CeilToInt((AllFloors.Max.X - Origin.X) / CellSize);
	Height = FMath::CeilToInt((AllFloors.Max.Y - Origin.Y) / CellSize);

	Walkable.Init(0, NumCells());
	CostMultiplier.Init(1.f, NumCells());
	EdgeMask.Init(0, NumCells());
	WallDistance.Init(TNumericLimits<float>::Max(), NumCells());

	BakeFloorCells(Floors);

	int32 BlockedEdges = 0;
	BakeEdges(World, Settings, BlockedEdges);
	BakeDiagonalEdges();
	BakeWallDistance(World, Settings);

	int32 NumWalkable = 0;
	for (const uint8 Flag : Walkable)
	{
		NumWalkable += Flag;
	}
	UE_LOG(LogCatrunSound, Log, TEXT("Grid bake: %dx%d cells (%.0fcm), %d walkable, %d wall-blocked edges."),
		Width, Height, CellSize, NumWalkable, BlockedEdges);
	return true;
}

// A cell exists where its centre lies on top of a floor.
void FCatrunGridData::BakeFloorCells(const TArray<TPair<FBox, float>>& Floors)
{
	for (int32 Cell = 0; Cell < NumCells(); ++Cell)
	{
		const FVector Center = CellCenter(Cell);
		for (const TPair<FBox, float>& Floor : Floors)
		{
			const FBox& Box = Floor.Key;
			if (Center.X >= Box.Min.X && Center.X <= Box.Max.X && Center.Y >= Box.Min.Y && Center.Y <= Box.Max.Y)
			{
				Walkable[Cell] = 1;
				CostMultiplier[Cell] = Floor.Value;
				break;
			}
		}
	}
}

// Two neighbouring floor cells are connected unless a wall stands between their centres.
// The line trace runs at cat height, so low openings (cat-holes) count as open.
void FCatrunGridData::BakeEdges(UWorld& World, const UCatrunSoundSettings& Settings, int32& OutBlockedEdges)
{
	FCollisionQueryParams QueryParams(SCENE_QUERY_STAT(CatrunGridBake), /*bTraceComplex*/ true);
	const FCollisionObjectQueryParams ObjectParams(ECC_WorldStatic);
	const float TraceZ = Origin.Z + Settings.TraceHeight;

	auto HitsWall = [&](const FVector& From, const FVector& To)
	{
		TArray<FHitResult> Hits;
		World.LineTraceMultiByObjectType(Hits, From, To, ObjectParams, QueryParams);
		for (const FHitResult& Hit : Hits)
		{
			if (Hit.GetActor() && Hit.GetActor()->ActorHasTag(Settings.WallTag))
			{
				return true;
			}
		}
		return false;
	};

	// Each edge is shared by two cells, so only look east and south and set both sides.
	for (int32 Cell = 0; Cell < NumCells(); ++Cell)
	{
		if (!IsWalkable(Cell))
		{
			continue;
		}
		for (const int32 Dir : { DirE, DirS })
		{
			const int32 Other = Neighbor(Cell, Dir);
			if (Other == INDEX_NONE || !IsWalkable(Other))
			{
				continue;
			}
			FVector From = CellCenter(Cell);
			FVector To = CellCenter(Other);
			From.Z = To.Z = TraceZ;

			if (HitsWall(From, To))
			{
				++OutBlockedEdges;
			}
			else
			{
				EdgeMask[Cell] |= (1 << Dir);
				EdgeMask[Other] |= (1 << Opposite[Dir]);
			}
		}
	}
}

// A diagonal step is allowed only when all four straight edges around it are open,
// so nothing can squeeze through the corner of a wall.
void FCatrunGridData::BakeDiagonalEdges()
{
	for (int32 Cell = 0; Cell < NumCells(); ++Cell)
	{
		if (!IsWalkable(Cell))
		{
			continue;
		}
		for (const int32 Dir : { DirSE, DirSW })
		{
			const int32 Diagonal = Neighbor(Cell, Dir);
			const int32 Side = Neighbor(Cell, Dir == DirSE ? DirE : DirW);
			const int32 Down = Neighbor(Cell, DirS);
			if (Diagonal == INDEX_NONE || Side == INDEX_NONE || Down == INDEX_NONE || !IsWalkable(Diagonal))
			{
				continue;
			}
			const int32 SideDir = (Dir == DirSE) ? DirE : DirW;
			const bool bOpen = IsEdgeOpen(Cell, SideDir) && IsEdgeOpen(Cell, DirS)
				&& IsEdgeOpen(Side, DirS) && IsEdgeOpen(Down, SideDir);
			if (bOpen)
			{
				EdgeMask[Cell] |= (1 << Dir);
				EdgeMask[Diagonal] |= (1 << Opposite[Dir]);
			}
		}
	}
}

// Fills WallDistance by shooting rays in many directions from the centre of every cell and
// taking the shortest distance to a wall or an obstacle (furniture). Measuring the real
// geometry (instead of counting cells) matters for narrow gaps: a 60cm cat-hole must read
// as "about 30cm to the wall". Obstacles only count here, never for sound (see BakeEdges).
void FCatrunGridData::BakeWallDistance(UWorld& World, const UCatrunSoundSettings& Settings)
{
	constexpr int32 NumRays = 16;

	// Rays only need to be as long as the widest clearance anybody asks for.
	WallProbeLength = FMath::Max(Settings.ArmorClearance * 1.5f, CellSize);

	FCollisionQueryParams QueryParams(SCENE_QUERY_STAT(CatrunWallDistance), /*bTraceComplex*/ true);
	const FCollisionObjectQueryParams ObjectParams(ECC_WorldStatic);
	const float TraceZ = Origin.Z + Settings.TraceHeight;

	for (int32 Cell = 0; Cell < NumCells(); ++Cell)
	{
		if (!IsWalkable(Cell))
		{
			continue;
		}
		const FVector Start(CellCenter(Cell).X, CellCenter(Cell).Y, TraceZ);
		float Nearest = WallProbeLength; // "no wall within reach"

		for (int32 Ray = 0; Ray < NumRays; ++Ray)
		{
			const float Angle = (2.f * PI * Ray) / NumRays;
			const FVector End = Start + FVector(FMath::Cos(Angle), FMath::Sin(Angle), 0.f) * WallProbeLength;

			TArray<FHitResult> Hits;
			World.LineTraceMultiByObjectType(Hits, Start, End, ObjectParams, QueryParams);
			for (const FHitResult& Hit : Hits)
			{
				const AActor* HitActor = Hit.GetActor();
				const bool bBlocksArmor = HitActor && (HitActor->ActorHasTag(Settings.WallTag) || HitActor->ActorHasTag(Settings.ObstacleTag));
				if (bBlocksArmor)
				{
					Nearest = FMath::Min(Nearest, Hit.Distance);
					break; // hits are sorted by distance, the first one is the nearest
				}
			}
		}
		WallDistance[Cell] = Nearest;
	}
}
