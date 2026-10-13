#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "Grid/CatrunGridData.h"
#include "Sound/SoundPropagation.h"

namespace
{
	// 레벨이나 액터 없이 전파 계산만 검증하는 평평한 격자.
	FCatrunGridData MakeSoundTestGrid(int32 Size, float Cost = 1.f)
	{
		FCatrunGridData Grid;
		Grid.Width = Grid.Height = Size;
		Grid.CellSize = 25.f;
		Grid.Walkable.Init(1, Grid.NumCells());
		Grid.EdgeMask.Init(255, Grid.NumCells());
		Grid.CostMultiplier.Init(Cost, Grid.NumCells());
		return Grid;
	}

	void BlockSoundTestEdge(FCatrunGridData& Grid, int32 X, int32 Y)
	{
		Grid.EdgeMask[Grid.CellIndex(X, Y)] &= ~(1 << CatrunGrid::DirE);
		Grid.EdgeMask[Grid.CellIndex(X + 1, Y)] &= ~(1 << CatrunGrid::DirW);
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSoundPropagationCircularityTest,
	"Catrun.Sound.Propagation.CircularityAndBudget",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FSoundPropagationCircularityTest::RunTest(const FString& Parameters)
{
	const FCatrunGridData Grid = MakeSoundTestGrid(41);
	const int32 Source = Grid.CellIndex(20, 20);
	TArray<uint8> Gates;
	TArray<float> Full, Limited, Slow;
	CatrunSoundPropagation::Run(Grid, Gates, Source, 2000.f, Full);
	float MaxError = 0.f;
	for (int32 Y = 0; Y < Grid.Height; ++Y)
	{
		for (int32 X = 0; X < Grid.Width; ++X)
		{
			const float Radius = FMath::Sqrt(float(FMath::Square(X - 20) + FMath::Square(Y - 20)));
			if (Radius >= 9.5f && Radius <= 10.5f)
			{
				MaxError = FMath::Max(MaxError, FMath::Abs(Full[Grid.CellIndex(X, Y)] / (Radius * Grid.CellSize) - 1.f));
			}
		}
	}
	AddInfo(FString::Printf(TEXT("10-cell radius maximum distance error: %.3f%%"), MaxError * 100.f));
	TestTrue(TEXT("Open-floor distance error below 4% (old octile metric exceeds 8%)"), MaxError < 0.04f);
	TestTrue(TEXT("Straight-axis distance is unchanged"), FMath::IsNearlyEqual(Full[Grid.CellIndex(30, 20)], 250.f));
	TestTrue(TEXT("X/Y symmetry"), FMath::IsNearlyEqual(Full[Grid.CellIndex(28, 24)], Full[Grid.CellIndex(24, 28)], 0.001f));

	CatrunSoundPropagation::Run(Grid, Gates, Source, 200.f, Limited);
	bool bSameInsideBudget = true;
	for (int32 Cell = 0; Cell < Limited.Num(); ++Cell)
	{
		if (Limited[Cell] != CatrunSoundPropagation::Unreached)
		{
			bSameInsideBudget &= Limited[Cell] <= 200.f && FMath::IsNearlyEqual(Limited[Cell], Full[Cell], 0.001f);
		}
	}
	TestTrue(TEXT("Hearing and extended visual budget agree inside the hearing range"), bSameInsideBudget);
	const FCatrunGridData SlowGrid = MakeSoundTestGrid(41, 2.f);
	CatrunSoundPropagation::Run(SlowGrid, Gates, Source, 4000.f, Slow);
	bool bScaled = true;
	for (int32 Cell = 0; Cell < Full.Num(); ++Cell)
	{
		bScaled &= FMath::IsNearlyEqual(Slow[Cell], Full[Cell] * 2.f, 0.01f);
	}
	TestTrue(TEXT("Uniform floor cost doubles distances"), bScaled);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSoundPropagationWallsTest,
	"Catrun.Sound.Propagation.WallsAndDoors",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FSoundPropagationWallsTest::RunTest(const FString& Parameters)
{
	FCatrunGridData Grid = MakeSoundTestGrid(31);
	const int32 Source = Grid.CellIndex(10, 10);
	const int32 Target = Grid.CellIndex(20, 10);
	TArray<uint8> Gates;
	Gates.Init(0, Grid.NumCells());
	TArray<float> Distance;
	for (int32 Y = 0; Y < Grid.Height; ++Y)
	{
		if (Y != 10)
		{
			BlockSoundTestEdge(Grid, 14, Y);
		}
	}
	CatrunSoundPropagation::Run(Grid, Gates, Source, 2000.f, Distance);
	TestTrue(TEXT("Open doorway passes sound"), FMath::IsNearlyEqual(Distance[Target], 250.f, 0.001f));
	Gates[Grid.CellIndex(15, 10)] = 1;
	CatrunSoundPropagation::Run(Grid, Gates, Source, 2000.f, Distance);
	TestEqual(TEXT("Closed doorway blocks the opposite room"), Distance[Target], CatrunSoundPropagation::Unreached);

	Grid = MakeSoundTestGrid(31);
	Gates.Init(0, Grid.NumCells());
	for (int32 Y = 7; Y <= 13; ++Y)
	{
		BlockSoundTestEdge(Grid, 14, Y);
	}
	CatrunSoundPropagation::Run(Grid, Gates, Source, 2000.f, Distance);
	TestTrue(TEXT("Partial wall is bypassed, not penetrated"), Distance[Target] > 275.f && Distance[Target] < CatrunSoundPropagation::Unreached);

	Grid = MakeSoundTestGrid(3);
	Gates.Init(0, Grid.NumCells());
	Gates[Grid.CellIndex(1, 0)] = Gates[Grid.CellIndex(0, 1)] = 1;
	CatrunSoundPropagation::Run(Grid, Gates, Grid.CellIndex(0, 0), 1000.f, Distance);
	TestEqual(TEXT("Closed corner cannot be crossed diagonally"), Distance[Grid.CellIndex(1, 1)], CatrunSoundPropagation::Unreached);
	TestEqual(TEXT("Invalid source is rejected"), CatrunSoundPropagation::Run(Grid, Gates, INDEX_NONE, 1000.f, Distance), 0);
	return true;
}

#endif
