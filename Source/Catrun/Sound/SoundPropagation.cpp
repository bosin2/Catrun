#include "SoundPropagation.h"

#include "Grid/CatrunGridData.h"

using namespace CatrunGrid;

namespace
{
	// Entry of the priority queue: always process the closest unfinished cell first.
	struct FHeapNode
	{
		float Distance;
		int32 Cell;
		bool operator<(const FHeapNode& Other) const { return Distance < Other.Distance; }
	};
}

int32 CatrunSoundPropagation::Run(const FCatrunGridData& Grid, const TArray<uint8>& ClosedGateCells,
	int32 SourceCell, float Budget, TArray<float>& OutDistance)
{
	OutDistance.Init(Unreached, Grid.NumCells());
	OutDistance[SourceCell] = 0.f;

	TArray<FHeapNode> Heap;
	Heap.HeapPush(FHeapNode{ 0.f, SourceCell }, TLess<FHeapNode>());
	int32 NumReached = 0;

	while (!Heap.IsEmpty())
	{
		FHeapNode Node;
		Heap.HeapPop(Node, TLess<FHeapNode>(), EAllowShrinking::No);

		// The same cell can be queued several times; skip entries that are already outdated.
		if (Node.Distance > OutDistance[Node.Cell])
		{
			continue;
		}
		++NumReached;

		for (int32 Dir = 0; Dir < NumDirs; ++Dir)
		{
			if (!Grid.IsEdgeOpen(Node.Cell, Dir))
			{
				continue; // a wall is in the way
			}
			const int32 Next = Grid.Neighbor(Node.Cell, Dir);
			if (Next == INDEX_NONE || (ClosedGateCells.IsValidIndex(Next) && ClosedGateCells[Next] > 0))
			{
				continue; // outside the map, or a closed door
			}

			// Cost of one step = length * average floor cost of the two cells (carpet is "longer").
			const float StepLength = IsDiagonal(Dir) ? Grid.CellSize * UE_SQRT_2 : Grid.CellSize;
			const float StepCost = StepLength * 0.5f * (Grid.CostMultiplier[Node.Cell] + Grid.CostMultiplier[Next]);
			const float NewDistance = Node.Distance + StepCost;

			if (NewDistance <= Budget && NewDistance < OutDistance[Next])
			{
				OutDistance[Next] = NewDistance;
				Heap.HeapPush(FHeapNode{ NewDistance, Next }, TLess<FHeapNode>());
			}
		}
	}
	return NumReached;
}
