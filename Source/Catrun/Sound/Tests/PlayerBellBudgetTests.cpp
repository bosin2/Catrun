#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "Components/BoxComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "Misc/ScopeExit.h"
#include "Sound/CatrunBellComponent.h"
#include "Sound/CatrunDoor.h"
#include "Sound/CatrunSoundSettings.h"
#include "Sound/SoundGridManager.h"
#include "UObject/UnrealType.h"
#include <limits>

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FPlayerBellBudgetTest, "Catrun.Sound.PlayerBellBudgetAcrossOpenAndClosedPaths",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FPlayerBellBudgetTest::RunTest(const FString&)
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
	auto* Floor = World->SpawnActor<AActor>();
	auto* Shape = NewObject<UBoxComponent>(Floor);
	Floor->SetRootComponent(Shape);
	Shape->SetBoxExtent(FVector(350, 12.5, 5));
	Shape->SetCollisionProfileName(TEXT("BlockAll"));
	Shape->RegisterComponent();
	Floor->SetActorLocation(FVector(350, 12.5, -5));
	Floor->Tags.Add(Settings->FloorTag);
	Manager->BuildGrid();
	if (!TestTrue(TEXT("One-cell-wide floor baked"), Manager->GetGrid().Height == 1)) return false;

	FCatrunSoundEvent Event;
	Event.Location = FVector(12.5, 12.5, 100);
	const FVector Destination(587.5, 12.5, 100);
	TestTrue(TEXT("Default event emitted"), Manager->EmitSound(Event));
	TestEqual(TEXT("575 cm exceeds the shared 500 cm budget"), Manager->GetRemainingBudgetAt(Destination), -1.f);

	Manager->PlayerBellBudgetOverride = 650.f;
	auto* Cat = World->SpawnActor<ACharacter>(Event.Location, FRotator::ZeroRotator);
	if (!TestNotNull(TEXT("Cat spawned"), Cat)) return false;
	auto* Bell = NewObject<UCatrunBellComponent>(Cat);
	Cat->AddInstanceComponent(Bell);
	Bell->RegisterComponent();
	TestTrue(TEXT("Player's bell rings"), Bell->TryRing());
	TestEqual(TEXT("Actual bell reaches the destination with 75 cm remaining"), Manager->GetRemainingBudgetAt(Destination), 75.f);
	float VisualBudget = 0.f;
	Manager->GetLatestVisualDistances(VisualBudget);
	TestEqual(TEXT("Ripple observes the same bell budget"), VisualBudget, 650.f);

	Event.Kind = ECatrunSoundKind::Footstep;
	Manager->EmitSound(Event);
	TestEqual(TEXT("Same size footstep still uses shared settings"), Manager->GetRemainingBudgetAt(Destination), -1.f);
	Event.Kind = ECatrunSoundKind::Bell;
	Manager->PlayerBellBudgetOverride = std::numeric_limits<float>::quiet_NaN();
	Manager->EmitSound(Event);
	Manager->GetLatestVisualDistances(VisualBudget);
	TestEqual(TEXT("Invalid override falls back to shared settings"), VisualBudget, Settings->LargeBudget);

	Manager->PlayerBellBudgetOverride = 650.f;
	auto* Door = World->SpawnActor<ACatrunDoor>(FVector(300, 12.5, 100), FRotator::ZeroRotator);
	Manager->NotifyDoorStateChanged(Door);
	Manager->EmitSound(Event);
	TestEqual(TEXT("A closed gate still isolates the destination"), Manager->GetRemainingBudgetAt(Destination), -1.f);
	Door->SetOpen(true);
	Manager->EmitSound(Event);
	TestEqual(TEXT("Opening the gate restores the route"), Manager->GetRemainingBudgetAt(Destination), 75.f);
	return true;
}

#endif
