#include "Pathfinding/ArmorPathfinder.h"
#include "Sound/CatrunDoor.h"
#include "Sound/SoundPropagation.h"
#include "Grid/CatrunGridData.h"
#include "Components/BoxComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"

#if WITH_DEV_AUTOMATION_TESTS
namespace
{
// Model an arch whose floor grid admits a path 50 cm off center. Its upper
// frame clips a standing armor there, but an open door still passes sound.
FCatrunGridData MakeDoorGrid(const FVector& Center, const FVector& Normal)
{
	FCatrunGridData Grid;
	Grid.Width = 17;
	Grid.Height = 13;
	Grid.CellSize = 25.f;
	Grid.Walkable.Init(1, Grid.NumCells());
	Grid.EdgeMask.Init(0xff, Grid.NumCells());
	Grid.WallDistance.Init(100.f, Grid.NumCells());
	Grid.CostMultiplier.Init(1.f, Grid.NumCells());
	for (int32 Cell = 0; Cell < Grid.NumCells(); ++Cell)
	{
		const FVector Delta = Grid.CellCenter(Cell) - Center;
		if (FMath::Abs(Delta | Normal) < 1. && FMath::Abs((Delta ^ Normal).Z) > 60.)
			Grid.Walkable[Cell] = 0;
	}
	return Grid;
}

TOptional<double> CrossingOffset(const TArray<FVector>& Corners, const FVector& Center, const FVector& Normal)
{
	for (int32 Index = 1; Index < Corners.Num(); ++Index)
	{
		const double Start = (Corners[Index - 1] - Center) | Normal;
		const double End = (Corners[Index] - Center) | Normal;
		if (Start * End > 0. || FMath::IsNearlyEqual(Start, End)) continue;
		const FVector Where = FMath::Lerp(Corners[Index - 1], Corners[Index], Start / (Start - End));
		return FMath::Abs(((Where - Center) ^ Normal).Z);
	}
	return {};
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FArmorDoorLaneTest, "Catrun.Monsters.ArmorDoorFrameLanes",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FArmorDoorLaneTest::RunTest(const FString&)
{
	const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false);
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
	GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
	ON_SCOPE_EXIT { GEngine->DestroyWorldContext(World); World->DestroyWorld(false); };
	auto* Door = World->SpawnActor<ACatrunDoor>();
	if (!TestNotNull(TEXT("Spawn both-sided door fixture"), Door)) return false;

	const FVector Center(212.5, 162.5, 0.);
	Door->GetGateBox()->SetBoxExtent(FVector(60, 15, 105));
	for (const double Yaw : {0., 90.})
	{
		Door->SetActorLocationAndRotation(Center, FRotator(0., Yaw, 0.));
		const FVector Normal = Door->GetDoorNormal();
		const FVector Tangent = Door->GetActorForwardVector();
		const FVector A = Center + Tangent * 50. - Normal * 125.;
		const FVector B = Center + Tangent * 50. + Normal * 125.;
		const FCatrunGridData Grid = MakeDoorGrid(Center, Normal);
		CatrunArmorPath::FParams Params;
		CatrunArmorPath::FDoorLane Lane;
		Door->ArmorPassageHalfWidth = 0.f;
		TestFalse(TEXT("Default door keeps original paths"), Door->GetArmorPassageLane(29.75f, Grid.CellSize, Lane));
		TArray<FVector> Corners;
		if (!TestTrue(TEXT("Original fast path available"), CatrunArmorPath::FindPath(Grid, A, B, Params, Corners))) return false;
		const auto OriginalOffset = CrossingOffset(Corners, Center, Normal);
		TestTrue(TEXT("Floor-only path chooses clipped outer lane"), OriginalOffset.IsSet() && OriginalOffset.GetValue() > 45.);

		Door->ArmorPassageHalfWidth = 22.f;
		for (bool Open : {false, true})
		{
			Door->SetOpen(Open);
			TestEqual(TEXT("Fixture door state"), Door->IsOpen(), Open);
			if (!TestTrue(TEXT("Configured frame supplies a lane"), Door->GetArmorPassageLane(29.75f, Grid.CellSize, Lane))) return false;
			Params.DoorLanes = {Lane};
			for (bool Reverse : {false, true})
			{
				if (!TestTrue(TEXT("Reach either side through the same door"),
					CatrunArmorPath::FindPath(Grid, Reverse ? B : A, Reverse ? A : B, Params, Corners))) return false;
				const auto Offset = CrossingOffset(Corners, Center, Normal);
				TestTrue(TEXT("Take the central aperture"), Offset.IsSet() && Offset.GetValue() < 1.);
			}
			TestFalse(TEXT("The lane does not block a parallel route farther from the frame"),
				Lane.Blocks(FVector2D(Center + Tangent * 50. + Normal * 100.)));

			TArray<uint8> Closed;
			Closed.Init(0, Grid.NumCells());
			for (int32 Cell = 0; !Open && Cell < Grid.NumCells(); ++Cell)
			{
				if (FMath::Abs((Grid.CellCenter(Cell) - Center) | Normal) < 1.) Closed[Cell] = 1;
			}
			TArray<float> Distances;
			CatrunSoundPropagation::Run(Grid, Closed, Grid.WorldToCell(A), 700.f, Distances);
			TestEqual(TEXT("Sound at the other side still follows the gate state"),
				Distances[Grid.WorldToCell(B)] != CatrunSoundPropagation::Unreached, Open);
		}
	}
	return true;
}
#endif
