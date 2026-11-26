#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "Components/BoxComponent.h"
#include "Engine/World.h"
#include "Misc/ScopeExit.h"
#include "Sound/CatrunSoundSettings.h"
#include "Sound/SoundGridManager.h"
#include "Sound/SoundPropagation.h"
#include "UObject/UnrealType.h"

// Stage2의 양면 책장(80x260x260)처럼 바닥에서 천장 가까이 막힌 가구는 소리가 통과하지 않고 돌아가야 한다.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSoundBlockerFurnitureTest, "Catrun.Sound.Blocker.TallShelfIsBypassedNotPenetrated",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FSoundBlockerFurnitureTest::RunTest(const FString&)
{
	const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false);
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
	if (!TestNotNull(TEXT("Test world"), World)) return false;
	ON_SCOPE_EXIT { World->DestroyWorld(false); };
	World->InitializeActorsForPlay(FURL());

	auto* Manager = World->SpawnActor<ASoundGridManager>();
	auto* Settings = NewObject<UCatrunSoundSettings>(Manager);
	Settings->LargeBudget = 500.f;
	FindFProperty<FObjectPropertyBase>(ASoundGridManager::StaticClass(), TEXT("Settings"))->SetObjectPropertyValue_InContainer(Manager, Settings);
	auto SpawnBox = [World](const FVector& Location, const FVector& Extent, const FRotator& Rotation, std::initializer_list<FName> Tags)
	{
		AActor* Actor = World->SpawnActor<AActor>();
		auto* Shape = NewObject<UBoxComponent>(Actor);
		Actor->SetRootComponent(Shape);
		Shape->SetBoxExtent(Extent);
		Shape->SetCollisionProfileName(TEXT("BlockAll"));
		Shape->RegisterComponent();
		Actor->SetActorLocationAndRotation(Location, Rotation);
		for (const FName Tag : Tags) Actor->Tags.Add(Tag);
		return Actor;
	};
	SpawnBox(FVector(0, 0, -5), FVector(500, 500, 5), FRotator::ZeroRotator, { Settings->FloorTag });
	AActor* Shelf = SpawnBox(FVector(0, 0, 130), FVector(40, 130, 130), FRotator::ZeroRotator, { Settings->ObstacleTag });
	Manager->BuildGrid();

	FCatrunSoundEvent Event; // 기본값: 고양이의 큰 방울
	Event.Location = FVector(-112.5, 12.5, 100);
	const FVector Behind(112.5, 12.5, 100);
	TestTrue(TEXT("Bell is emitted"), Manager->EmitSound(Event));
	TestTrue(TEXT("Ordinary furniture still lets sound pass straight"),
		FMath::IsNearlyEqual(Manager->GetRemainingBudgetAt(Behind), 275.f, 1.f));

	Shelf->Tags.Add(TEXT("SoundBlocker"));
	Manager->NotifyDoorStateChanged(nullptr);
	TestTrue(TEXT("Bell is emitted next to the shelf"), Manager->EmitSound(Event));
	const float Around = Manager->GetRemainingBudgetAt(Behind);
	TestTrue(TEXT("Sound bends around the shelf instead of crossing it"), Around > 0.f && Around < 200.f);

	float Budget = 0.f;
	const TArray<float>& Picture = Manager->GetLatestVisualDistances(Budget);
	const FCatrunGridData& Grid = Manager->GetGrid();
	TestEqual(TEXT("Ripple has no distance inside the shelf"), Picture[Grid.WorldToCell(FVector(12.5, 12.5, 0))], CatrunSoundPropagation::Unreached);
	TestTrue(TEXT("Ripple and hearing agree behind the shelf"),
		FMath::IsNearlyEqual(Budget - Picture[Grid.WorldToCell(Behind)], Around, 0.01f));
	TestTrue(TEXT("Shelf cells stay available to the armor grid"), Grid.IsWalkable(Grid.WorldToCell(FVector(12.5, 12.5, 0))));

	// 격자 칸 중심이 책장 안에 들어갈 만큼 붙어 있어도 소리가 사라지지 않는다.
	Event.Location = FVector(-38, 12.5, 100);
	TestTrue(TEXT("Bell touching the shelf is emitted"), Manager->EmitSound(Event));
	TestTrue(TEXT("Bell touching the shelf reaches its own side"), Manager->GetRemainingBudgetAt(FVector(-112.5, 12.5, 100)) > 350.f);
	TestTrue(TEXT("Bell touching the shelf does not leak to the other side"), Manager->GetRemainingBudgetAt(Behind) < 250.f);

	// 돌려 놓은 책장은 실제 몸체만 막는다(축 정렬 상자로 넓히지 않는다).
	Shelf->SetActorRotation(FRotator(0, 90, 0));
	Manager->NotifyDoorStateChanged(nullptr);
	Event.Location = FVector(-12.5, -112.5, 100);
	Manager->EmitSound(Event);
	TestTrue(TEXT("Rotated shelf blocks its own footprint"), Manager->GetRemainingBudgetAt(FVector(-12.5, 112.5, 100)) < 200.f);
	TestTrue(TEXT("Rotated shelf frees the old footprint"), Manager->GetRemainingBudgetAt(FVector(12.5, -87.5, 100)) > 440.f);
	return true;
}

#endif
