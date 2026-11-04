#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Monster/CatrunArmor.h"
#include "Monster/CatrunCandle.h"
#include "Monster/CatrunMarkSubsystem.h"
#include "Sound/SoundGridManager.h"
#include "Sound/CatrunSoundSettings.h"
#include "Components/BoxComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"

namespace
{
struct FMarkFixture
{
	UWorld* World;
	ACharacter* Cat;
	ASoundGridManager* Manager;
	UCatrunSoundSettings* Settings;
	UCatrunMarkSubsystem* Marks;
	FMarkFixture()
	{
		const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false);
		World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
		GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
		Cat = World->SpawnActor<ACharacter>();
		auto* Controller = World->SpawnActor<APlayerController>();
		World->AddController(Controller); // This isolated world does not initialize actors for play.
		Controller->Possess(Cat);
		Manager = World->SpawnActor<ASoundGridManager>();
		Settings = NewObject<UCatrunSoundSettings>(Manager);
		FindFProperty<FObjectPropertyBase>(ASoundGridManager::StaticClass(), TEXT("Settings"))
			->SetObjectPropertyValue_InContainer(Manager, Settings);
		Marks = World->GetSubsystem<UCatrunMarkSubsystem>();
	}
	~FMarkFixture()
	{
		Marks->ClearMark(TEXT("test teardown"));
		GEngine->DestroyWorldContext(World);
		World->DestroyWorld(false);
	}
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FMarkCallRangeTest, "Catrun.Monsters.MarkCallRangeAndWalls", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FMarkCallRangeTest::RunTest(const FString&)
{
	FMarkFixture F;
	F.Settings->MarkCallRadius = 1500.f;
	if (!TestTrue(TEXT("Fixture has the real player pawn"), UGameplayStatics::GetPlayerPawn(F.World, 0) == F.Cat)) return false;
	auto* Armor = F.World->SpawnActor<ACatrunArmor>();
	Armor->SetActorLocation(FVector(1600, 0, 100));
	F.Marks->ApplyMark(*F.Cat);
	F.Marks->Tick(.3f);
	TestFalse(TEXT("A mark does not summon armor beyond the initial 1500cm call range"), Armor->IsFollowingMark());
	Armor->SetActorLocation(FVector(600, 0, 100));
	auto* Wall = F.World->SpawnActor<AActor>();
	Wall->Tags.Add(F.Settings->WallTag);
	auto* Shape = NewObject<UBoxComponent>(Wall);
	Wall->SetRootComponent(Shape);
	Shape->SetBoxExtent(FVector(20, 500, 200));
	Shape->SetCollisionProfileName(TEXT("BlockAll"));
	Shape->RegisterComponent();
	Wall->SetActorLocation(FVector(300, 0, 100));
	F.Marks->Tick(.3f);
	TestTrue(TEXT("A wall does not block a mark calling nearby armor"), Armor->IsFollowingMark());
	Armor->SetActorLocation(FVector(1600, 0, 100));
	F.Marks->Tick(.3f);
	TestFalse(TEXT("An armor outside the call range is released"), Armor->IsFollowingMark());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCandleRemarkTest, "Catrun.Monsters.CandleRemarksVisibleCat", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCandleRemarkTest::RunTest(const FString&)
{
	FMarkFixture F;
	F.Settings->CandleTouchRadius = 45.f;
	auto* Candle = F.World->SpawnActor<ACatrunCandle>();
	Candle->bAutoAlignEyes = false;
	Candle->SetActorLocation(FVector(10, 0, 0));
	Candle->Tick(.016f);
	TestTrue(TEXT("Candle sees and marks the nearby cat"), F.Marks->IsMarked());
	F.Marks->ClearMark(TEXT("hideout cleared mark before sight hysteresis expired"));
	TestFalse(TEXT("Mark was actually cleared"), F.Marks->IsMarked());
	Candle->Tick(.016f);
	TestTrue(TEXT("Still-visible cat can be marked again without waiting for StopTracking"), F.Marks->IsMarked());
	F.Marks->ClearMark(TEXT("disable penalties"));
	Candle->bPenaltiesEnabled = false;
	Candle->Tick(.016f);
	TestFalse(TEXT("A demonstration candle with penalties disabled does not mark"), F.Marks->IsMarked());
	return true;
}
#endif
