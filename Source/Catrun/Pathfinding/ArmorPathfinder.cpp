#include "ArmorPathfinder.h"

#include "Grid/CatrunGridData.h"
#include "Algo/Reverse.h"

using namespace CatrunGrid;

namespace
{
	// The search remembers not only the cell but also the direction the armor entered it from,
	// because turning costs extra. One cell therefore has 4 "states" (one per direction)
	// plus one extra state for the start cell, where the armor has no direction yet.
	constexpr int32 StatesPerCell = NumStraightDirs + 1;
	constexpr int32 NoDirection = NumStraightDirs;

	int32 StateOf(int32 Cell, int32 Direction) { return Cell * StatesPerCell + Direction; }
	int32 CellOf(int32 State) { return State / StatesPerCell; }
	int32 DirectionOf(int32 State) { return State % StatesPerCell; }

	// Entry of the priority queue: the state with the lowest "cost so far + estimate to goal" first.
	struct FHeapNode
	{
		float EstimatedTotal;
		int32 State;
		bool operator<(const FHeapNode& Other) const { return EstimatedTotal < Other.EstimatedTotal; }
	};

	// Estimated remaining cost: Manhattan distance to the goal. Never too high, so A* stays exact.
	float EstimateToGoal(const FCatrunGridData& Grid, int32 Cell, int32 GoalCell)
	{
		const int32 DeltaX = FMath::Abs(Grid.CellX(Cell) - Grid.CellX(GoalCell));
		const int32 DeltaY = FMath::Abs(Grid.CellY(Cell) - Grid.CellY(GoalCell));
		return (DeltaX + DeltaY) * Grid.CellSize;
	}
}

bool CatrunArmorPath::CanStand(const FCatrunGridData& Grid, int32 Cell, float ClearanceRadius)
{
	return Grid.IsWalkable(Cell) && Grid.WallDistance[Cell] >= ClearanceRadius;
}

bool CatrunArmorPath::FindPath(const FCatrunGridData& Grid, const FVector& Start, const FVector& Goal,
	const FParams& Params, TArray<FVector>& OutCorners)
{
	OutCorners.Reset();
	if (!Grid.IsValid())
	{
		return false;
	}

	// Start and goal may be outside the allowed area (next to a wall); use the closest allowed cell.
	const int32 SearchRings = FMath::CeilToInt(Params.ClearanceRadius / Grid.CellSize) + 3;
	auto IsAllowed = [&](int32 Cell) { return CatrunArmorPath::CanStand(Grid, Cell, Params.ClearanceRadius); };
	const int32 StartCell = Grid.FindNearestCell(Start, SearchRings, IsAllowed);
	const int32 GoalCell = Grid.FindNearestCell(Goal, SearchRings, IsAllowed);
	if (StartCell == INDEX_NONE || GoalCell == INDEX_NONE)
	{
		return false;
	}

	const int32 NumStates = Grid.NumCells() * StatesPerCell;
	TArray<float> CostSoFar;
	TArray<int32> CameFrom;
	CostSoFar.Init(MAX_flt, NumStates);
	CameFrom.Init(INDEX_NONE, NumStates);

	TArray<FHeapNode> Heap;
	const int32 StartState = StateOf(StartCell, NoDirection);
	CostSoFar[StartState] = 0.f;
	Heap.HeapPush(FHeapNode{ EstimateToGoal(Grid, StartCell, GoalCell), StartState }, TLess<FHeapNode>());

	int32 FinalState = INDEX_NONE;
	while (!Heap.IsEmpty())
	{
		FHeapNode Node;
		Heap.HeapPop(Node, TLess<FHeapNode>(), EAllowShrinking::No);

		const int32 Cell = CellOf(Node.State);
		const int32 ArrivedFrom = DirectionOf(Node.State);

		// Skip queue entries that were replaced by a cheaper route in the meantime.
		if (Node.EstimatedTotal > CostSoFar[Node.State] + EstimateToGoal(Grid, Cell, GoalCell) + KINDA_SMALL_NUMBER)
		{
			continue;
		}
		if (Cell == GoalCell)
		{
			FinalState = Node.State;
			break;
		}

		// Move one cell up, down, left or right.
		for (int32 Dir = 0; Dir < NumStraightDirs; ++Dir)
		{
			const int32 Next = Grid.Neighbor(Cell, Dir);
			if (Next == INDEX_NONE || !Grid.IsEdgeOpen(Cell, Dir) || !IsAllowed(Next))
			{
				continue;
			}
			const bool bTurn = (ArrivedFrom != NoDirection && ArrivedFrom != Dir);
			const float NewCost = CostSoFar[Node.State] + Grid.CellSize + (bTurn ? Params.TurnPenalty : 0.f);
			const int32 NextState = StateOf(Next, Dir);

			if (NewCost < CostSoFar[NextState])
			{
				CostSoFar[NextState] = NewCost;
				CameFrom[NextState] = Node.State;
				Heap.HeapPush(FHeapNode{ NewCost + EstimateToGoal(Grid, Next, GoalCell), NextState }, TLess<FHeapNode>());
			}
		}
	}
	if (FinalState == INDEX_NONE)
	{
		return false;
	}

	// Walk back from the goal to the start, then reverse.
	TArray<int32> Cells;
	for (int32 State = FinalState; State != INDEX_NONE; State = CameFrom[State])
	{
		Cells.Add(CellOf(State));
	}
	Algo::Reverse(Cells);

	// Keep only the corners: the first cell, the last cell, and every cell where the direction changes.
	OutCorners.Add(Grid.CellCenter(Cells[0]));
	for (int32 i = 1; i + 1 < Cells.Num(); ++i)
	{
		const int32 DirectionIn = Cells[i] - Cells[i - 1];
		const int32 DirectionOut = Cells[i + 1] - Cells[i];
		if (DirectionIn != DirectionOut)
		{
			OutCorners.Add(Grid.CellCenter(Cells[i]));
		}
	}
	if (Cells.Num() > 1)
	{
		OutCorners.Add(Grid.CellCenter(Cells.Last()));
	}
	return true;
}
