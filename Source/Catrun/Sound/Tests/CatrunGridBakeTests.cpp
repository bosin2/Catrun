#if WITH_DEV_AUTOMATION_TESTS

#include "Components/BoxComponent.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Grid/CatrunGridData.h"
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include "Sound/CatrunSoundSettings.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunGridBakePreservationTest,
	"Catrun.Sound.GridBake.PreservesGridOnFailure",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCatrunGridBakePreservationTest::RunTest(const FString&)
{
	const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false)
		.CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false);
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
	if (!TestNotNull(TEXT("Test world"), World)) return false;
	ON_SCOPE_EXIT { World->DestroyWorld(false); };
	World->InitializeActorsForPlay(FURL());

	UCatrunSoundSettings* Settings = NewObject<UCatrunSoundSettings>(World);
	auto SpawnFloor = [&](const FVector& Location)
	{
		AActor* Floor = World->SpawnActor<AActor>();
		UBoxComponent* Shape = NewObject<UBoxComponent>(Floor);
		Floor->SetRootComponent(Shape);
		Shape->SetBoxExtent(FVector(50, 37.5, 5));
		Shape->SetCollisionProfileName(TEXT("BlockAll"));
		Shape->RegisterComponent();
		Floor->SetActorLocation(Location);
		Floor->Tags.Add(Settings->FloorTag);
		return Floor;
	};
	AActor* Floor = SpawnFloor(FVector(50, 37.5, -5));
	FCatrunGridData Grid;
	if (!TestTrue(TEXT("Initial grid bakes"), Grid.Bake(*World, *Settings))) return false;
	TestEqual(TEXT("Initial width"), Grid.Width, 4);
	TestEqual(TEXT("Initial height"), Grid.Height, 3);
	const FVector BlockedLocation(62.5, 37.5, 0);
	const int32 BlockedCell = Grid.WorldToCell(BlockedLocation);
	if (!TestTrue(TEXT("Obstacle location starts walkable"), Grid.IsWalkable(BlockedCell))) return false;
	Grid.PuzzleClearance.Init(MAX_flt, Grid.NumCells());
	Grid.PuzzleClearance[BlockedCell] = 0.f;
	const FCatrunGridData Previous = Grid;

	Settings->CellSize = 5.f;
	AActor* DistantFloor = SpawnFloor(FVector(-6000, -6000, 45));
	AddExpectedError(TEXT("Grid bake: the floors give"), EAutomationExpectedErrorFlags::Contains, 1);
	TestFalse(TEXT("Grid over the cell limit is rejected"), Grid.Bake(*World, *Settings));
	TestTrue(TEXT("Grid stays valid"), Grid.IsValid());
	TestEqual(TEXT("Origin is preserved"), Grid.Origin, Previous.Origin);
	TestEqual(TEXT("Cell size is preserved"), Grid.CellSize, Previous.CellSize);
	TestEqual(TEXT("Width is preserved"), Grid.Width, Previous.Width);
	TestEqual(TEXT("Height is preserved"), Grid.Height, Previous.Height);
	TestTrue(TEXT("Walkable cells are preserved"), Grid.Walkable == Previous.Walkable);
	TestTrue(TEXT("Floor costs are preserved"), Grid.CostMultiplier == Previous.CostMultiplier);
	TestTrue(TEXT("Edge masks are preserved"), Grid.EdgeMask == Previous.EdgeMask);
	TestTrue(TEXT("Wall distances are preserved"), Grid.WallDistance == Previous.WallDistance);
	TestEqual(TEXT("Wall probe length is preserved"), Grid.WallProbeLength, Previous.WallProbeLength);
	TestTrue(TEXT("Puzzle clearance is preserved"), Grid.PuzzleClearance == Previous.PuzzleClearance);
	TestEqual(TEXT("World location still maps to the same cell"), Grid.WorldToCell(BlockedLocation), BlockedCell);
	TestFalse(TEXT("Previously blocked cell stays blocked"), Grid.IsWalkable(BlockedCell));
	TestTrue(TEXT("Adjacent unblocked floor stays walkable"), Grid.IsWalkable(0));

	DistantFloor->Tags.Remove(Settings->FloorTag);
	Floor->Tags.Remove(Settings->FloorTag);
	AActor* FloorWithoutBounds = World->SpawnActor<AActor>();
	FloorWithoutBounds->Tags.Add(Settings->FloorTag);
	AddExpectedError(TEXT("Grid bake: no valid collision bounds for floor tag"), EAutomationExpectedErrorFlags::Contains, 2);
	TestFalse(TEXT("Rebake without floor bounds fails"), Grid.Bake(*World, *Settings));
	TestEqual(TEXT("Failed rebake keeps the old index"), Grid.WorldToCell(BlockedLocation), BlockedCell);
	TestTrue(TEXT("Failed rebake keeps the old obstacle cache"), Grid.PuzzleClearance == Previous.PuzzleClearance);
	FCatrunGridData EmptyGrid;
	TestFalse(TEXT("Initial bake without floor bounds fails"), EmptyGrid.Bake(*World, *Settings));
	TestFalse(TEXT("First failure leaves the grid invalid"), EmptyGrid.IsValid());

	FloorWithoutBounds->Tags.Remove(Settings->FloorTag);
	Floor->Tags.Add(Settings->FloorTag);
	Floor->SetActorLocation(FVector(150, 237.5, 15));
	Settings->CellSize = 20.f;
	Settings->DefaultFloorMultiplier = 2.f;
	Settings->ArmorClearance = 80.f;
	if (!TestTrue(TEXT("Rebake with valid floor bounds succeeds"), Grid.Bake(*World, *Settings))) return false;
	TestEqual(TEXT("Origin is replaced"), Grid.Origin, FVector(100, 200, 20));
	TestEqual(TEXT("Cell size is replaced"), Grid.CellSize, 20.f);
	TestEqual(TEXT("Width is replaced"), Grid.Width, 5);
	TestEqual(TEXT("Height is replaced"), Grid.Height, 4);
	TestEqual(TEXT("Old world location is outside the new grid"), Grid.WorldToCell(BlockedLocation), INDEX_NONE);
	TestTrue(TEXT("Old obstacle cache is cleared"), Grid.PuzzleClearance.IsEmpty());
	TestTrue(TEXT("First new cell is walkable"), Grid.IsWalkable(Grid.WorldToCell(FVector(110, 210, 20))));
	TestTrue(TEXT("New floor cost is recorded"), Grid.CostMultiplier.IsValidIndex(0) && Grid.CostMultiplier[0] == 2.f);
	TestEqual(TEXT("Wall probe length is replaced"), Grid.WallProbeLength, 120.f);
	return true;
}

#endif
