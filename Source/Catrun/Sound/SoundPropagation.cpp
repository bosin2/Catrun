#include "SoundPropagation.h"

#include "Grid/CatrunGridData.h"

using namespace CatrunGrid;

namespace
{
	// 아직 확정하지 않은 칸 중 거리가 가장 짧은 칸부터 처리한다.
	struct FSoundSpreadNode
	{
		float Distance;
		int32 Cell;
		bool operator<(const FSoundSpreadNode& Other) const { return Distance < Other.Distance; }
	};
}

int32 CatrunSoundPropagation::Run(const FCatrunGridData& Grid, const TArray<uint8>& ClosedGateCells,
	int32 SourceCell, float Budget, TArray<float>& OutDistance)
{
	const int32 CellCount = Grid.NumCells();
	OutDistance.Init(Unreached, FMath::Max(CellCount, 0));
	if (!Grid.IsValid() || !OutDistance.IsValidIndex(SourceCell) ||
		Grid.Walkable.Num() != CellCount || Grid.EdgeMask.Num() != CellCount ||
		Grid.CostMultiplier.Num() != CellCount || !FMath::IsFinite(Grid.CellSize) ||
		Grid.CellSize <= 0.f || !FMath::IsFinite(Budget) || Budget < 0.f)
	{
		return 0;
	}

	// 바닥이 아니거나 닫힌 문이 차지한 칸은 통과하지 않는다.
	auto IsAvailable = [&](int32 Cell)
	{
		return Cell >= 0 && Cell < CellCount && Grid.IsWalkable(Cell) &&
			!(ClosedGateCells.IsValidIndex(Cell) && ClosedGateCells[Cell] > 0);
	};
	auto HasOpenEdge = [&](int32 Cell, int32 Dir)
	{
		if (!IsAvailable(Cell))
		{
			return false;
		}
		const int32 Next = Grid.Neighbor(Cell, Dir);
		return IsAvailable(Next) && Grid.IsEdgeOpen(Cell, Dir) &&
			Grid.IsEdgeOpen(Next, Opposite[Dir]);
	};
	auto CanTravel = [&](int32 Cell, int32 Dir)
	{
		if (!HasOpenEdge(Cell, Dir))
		{
			return false;
		}
		if (!IsDiagonal(Dir))
		{
			return true;
		}
		// 대각선으로 닫힌 문이나 벽 모서리를 가로지르지 않는다.
		const int32 HorizontalDir = DirX[Dir] > 0 ? 0 : 1;
		const int32 VerticalDir = DirY[Dir] > 0 ? 2 : 3;
		if (!HasOpenEdge(Cell, HorizontalDir) || !HasOpenEdge(Cell, VerticalDir))
		{
			return false;
		}
		return HasOpenEdge(Grid.Neighbor(Cell, HorizontalDir), VerticalDir) &&
			HasOpenEdge(Grid.Neighbor(Cell, VerticalDir), HorizontalDir);
	};
	if (!IsAvailable(SourceCell))
	{
		return 0;
	}

	TArray<uint8> Accepted;
	Accepted.Init(0, CellCount);
	auto CalculateDistance = [&](int32 Cell)
	{
		float Best = Unreached;
		float AxisDistance[4] = {};
		float AxisStep[4] = {};
		bool AxisValid[4] = {};
		for (int32 Dir = 0; Dir < NumDirs; ++Dir)
		{
			if (!CanTravel(Cell, Dir))
			{
				continue;
			}
			const int32 Neighbor = Grid.Neighbor(Cell, Dir);
			if (!Accepted[Neighbor])
			{
				continue;
			}
			const float HereCost = Grid.CostMultiplier[Cell];
			const float NeighborCost = Grid.CostMultiplier[Neighbor];
			if (!FMath::IsFinite(HereCost) || !FMath::IsFinite(NeighborCost) ||
				HereCost <= 0.f || NeighborCost <= 0.f)
			{
				continue;
			}
			// 기존의 바닥 평균 비용과 열린 대각선 경로를 유지한다.
			const float StepLength = IsDiagonal(Dir) ? Grid.CellSize * UE_SQRT_2 : Grid.CellSize;
			const float StepCost = StepLength * 0.5f * (HereCost + NeighborCost);
			const float NeighborDistance = OutDistance[Neighbor];
			Best = FMath::Min(Best, NeighborDistance + StepCost);
			if (Dir < NumStraightDirs)
			{
				AxisDistance[Dir] = NeighborDistance;
				AxisStep[Dir] = StepCost;
				AxisValid[Dir] = true;
			}
		}

		// 가로·세로의 도달 거리로 Eikonal 식을 풀어 8방향 편향을 줄인다.
		// 두 이웃보다 늦게 도착하는 해만 사용하여 확정 순서를 유지한다.
		for (int32 XDir = 0; XDir < 2; ++XDir)
		{
			for (int32 YDir = 2; YDir < 4; ++YDir)
			{
				if (!AxisValid[XDir] || !AxisValid[YDir])
				{
					continue;
				}
				const double A = AxisDistance[XDir];
				const double B = AxisDistance[YDir];
				const double HX = AxisStep[XDir];
				const double HY = AxisStep[YDir];
				const double WX = 1.0 / (HX * HX);
				const double WY = 1.0 / (HY * HY);
				const double Sum = WX + WY;
				const double Difference = A - B;
				const double Discriminant = Sum - WX * WY * Difference * Difference;
				if (Discriminant < 0.0)
				{
					continue;
				}
				const double Candidate = (WX * A + WY * B + FMath::Sqrt(Discriminant)) / Sum;
				if (Candidate >= FMath::Max(A, B))
				{
					Best = FMath::Min(Best, static_cast<float>(Candidate));
				}
			}
		}
		return Best;
	};

	OutDistance[SourceCell] = 0.f;
	TArray<FSoundSpreadNode> Heap;
	Heap.HeapPush(FSoundSpreadNode{ 0.f, SourceCell }, TLess<FSoundSpreadNode>());
	int32 NumReached = 0;
	while (!Heap.IsEmpty())
	{
		FSoundSpreadNode Node;
		Heap.HeapPop(Node, TLess<FSoundSpreadNode>(), EAllowShrinking::No);
		if (Accepted[Node.Cell] || Node.Distance > OutDistance[Node.Cell])
		{
			continue;
		}
		Accepted[Node.Cell] = 1;
		++NumReached;

		for (int32 Dir = 0; Dir < NumDirs; ++Dir)
		{
			if (!CanTravel(Node.Cell, Dir))
			{
				continue;
			}
			const int32 Next = Grid.Neighbor(Node.Cell, Dir);
			if (Accepted[Next])
			{
				continue;
			}
			const float NewDistance = CalculateDistance(Next);
			if (NewDistance != Unreached && FMath::IsFinite(NewDistance) &&
				NewDistance <= Budget && NewDistance < OutDistance[Next])
			{
				OutDistance[Next] = NewDistance;
				Heap.HeapPush(FSoundSpreadNode{ NewDistance, Next }, TLess<FSoundSpreadNode>());
			}
		}
	}
	return NumReached;
}
