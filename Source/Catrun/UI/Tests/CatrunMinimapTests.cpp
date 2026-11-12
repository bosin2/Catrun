#if WITH_DEV_AUTOMATION_TESTS

#include "UI/CatrunMinimapWidget.h"

#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include "Monster/CatrunArmor.h"
#include "Monster/CatrunCandle.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunMinimapProjectionTest, "Catrun.UI.Minimap.ProjectionMatchesCapture",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCatrunMinimapProjectionTest::RunTest(const FString&)
{
	const FVector2D Center(120., -780.);
	const FVector2D Size(300., 500.);
	FVector2D UV;
	auto Check = [&](const TCHAR* Label, const FVector2D& Offset, double Yaw, const FVector2D& Expected)
	{
		if (TestTrue(Label, CatrunMinimap::Project(Center + Offset, Center, Size, Yaw, UV)))
			TestTrue(FString::Printf(TEXT("%s UV"), Label), UV.Equals(Expected, UE_DOUBLE_SMALL_NUMBER));
	};
	Check(TEXT("Offset map center"), FVector2D::ZeroVector, 0., FVector2D(.5, .5));
	Check(TEXT("Top left"), FVector2D(250., -150.), 0., FVector2D(0., 0.));
	Check(TEXT("Top right"), FVector2D(250., 150.), 0., FVector2D(1., 0.));
	Check(TEXT("Bottom left"), FVector2D(-250., -150.), 0., FVector2D(0., 1.));
	Check(TEXT("Bottom right"), FVector2D(-250., 150.), 0., FVector2D(1., 1.));
	Check(TEXT("Yaw 90 rotates world +Y to top"), FVector2D(0., 250.), 90., FVector2D(.5, 0.));
	Check(TEXT("Yaw 90 rotates world -X to right"), FVector2D(-150., 0.), 90., FVector2D(1., .5));
	const double Diagonal = FMath::Sqrt(.5);
	Check(TEXT("Yaw 45 preserves the rotated corner"), FVector2D(100., 400.) * Diagonal, 45., FVector2D(1., 0.));
	TestFalse(TEXT("Actors beyond the image bounds are hidden"),
		CatrunMinimap::Project(Center + FVector2D(251., 0.), Center, Size, 0., UV));
	TestFalse(TEXT("Invalid bounds are rejected"),
		CatrunMinimap::Project(Center, Center, FVector2D(0., 500.), 0., UV));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunMinimapEnemyLifecycleTest, "Catrun.UI.Minimap.EnemyCacheFollowsWorldLifetime",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCatrunMinimapEnemyLifecycleTest::RunTest(const FString&)
{
	const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(false)
		.CreateNavigation(false).CreateAISystem(false);
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
	if (!TestNotNull(TEXT("Detached test world"), World))
		return false;
	GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
	ON_SCOPE_EXIT
	{
		GEngine->DestroyWorldContext(World);
		World->DestroyWorld(false);
	};
	// AActor::ProcessEvent dispatches the destruction delegate after play initialization.
	World->InitializeActorsForPlay(FURL());

	ACatrunArmor* Armor = World->SpawnActor<ACatrunArmor>();
	ACatrunMinimapPresenter* Presenter = World->SpawnActor<ACatrunMinimapPresenter>();
	if (!TestNotNull(TEXT("Preplaced armor"), Armor) || !TestNotNull(TEXT("Presenter"), Presenter))
		return false;
	Presenter->StartTracking(*World);
	TestEqual(TEXT("Preplaced armor tracked exactly once"), Presenter->Enemies.Num(), 1);
	TestTrue(TEXT("Tracking starts the scheduled refresh"), World->GetTimerManager().TimerExists(Presenter->UpdateTimer));

	ACatrunCandle* Candle = World->SpawnActor<ACatrunCandle>();
	World->SpawnActor<AActor>();
	if (!TestNotNull(TEXT("Spawned candle"), Candle))
		return false;
	Presenter->StartTracking(*World);
	TestEqual(TEXT("New candle tracked and other actor ignored"), Presenter->Enemies.Num(), 2);
	TestTrue(TEXT("Destroy succeeds"), World->DestroyActor(Armor));
	TestEqual(TEXT("Destroyed armor removed from the cache"), Presenter->Enemies.Num(), 1);
	TestTrue(TEXT("Candle is still tracked"), Presenter->Enemies.Contains(TWeakObjectPtr<AActor>(Candle)));

	Presenter->EndPlay(EEndPlayReason::LevelTransition);
	TestFalse(TEXT("Leaving the level stops refreshes"), World->GetTimerManager().TimerExists(Presenter->UpdateTimer));
	TestFalse(TEXT("Candle destruction callback is unbound"), Candle->OnDestroyed.IsBound());
	World->SpawnActor<ACatrunCandle>();
	TestEqual(TEXT("Leaving the level clears cache and removes spawn hook"), Presenter->Enemies.Num(), 0);
	return true;
}

#endif
