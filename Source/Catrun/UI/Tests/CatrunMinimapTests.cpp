#if WITH_DEV_AUTOMATION_TESTS

#include "UI/CatrunMinimapWidget.h"

#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Layout/Geometry.h"
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include "Monster/CatrunArmor.h"
#include "Monster/CatrunCandle.h"
#include "Settings/CatrunSettingsSubsystem.h"

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

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunMinimapCameraProjectionTest, "Catrun.UI.Minimap.CameraProjectionFitsAndRegisters",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCatrunMinimapCameraProjectionTest::RunTest(const FString&)
{
	const FVector2D Center(120., -780.);
	const FVector2D CaptureSize(600., 600.);
	const FRotator Stage2View(-55., -135., 0.);
	FSlateRenderTransform Projection;
	if (!TestTrue(TEXT("Stage2 gameplay camera angle is usable"),
		CatrunMinimap::FitCameraProjection(CaptureSize, 0., Stage2View, Projection)))
		return false;

	const double HalfHeight = .5 * FMath::Sin(FMath::DegreesToRadians(55.));
	const auto CheckUV = [&](const TCHAR* Label, const FVector2D& CaptureUV, const FVector2D& Expected)
	{
		TestTrue(Label, CatrunMinimap::ToDisplayUV(CaptureUV, Projection).Equals(Expected, 1.e-6));
	};
	CheckUV(TEXT("Capture center stays centered"), FVector2D(.5, .5), FVector2D(.5, .5));
	CheckUV(TEXT("Top-left corner is screen right"), FVector2D(0., 0.), FVector2D(1., .5));
	CheckUV(TEXT("Top-right corner is down and foreshortened by the camera pitch"),
		FVector2D(1., 0.), FVector2D(.5, .5 + HalfHeight));
	CheckUV(TEXT("Bottom-left corner is up and foreshortened by the camera pitch"),
		FVector2D(0., 1.), FVector2D(.5, .5 - HalfHeight));
	CheckUV(TEXT("Bottom-right corner is screen left"), FVector2D(1., 1.), FVector2D(0., .5));

	FVector2D CaptureUV;
	if (TestTrue(TEXT("World marker maps onto an interior texel"),
		CatrunMinimap::Project(Center + FVector2D(90., -210.), Center, CaptureSize, 0., CaptureUV)))
	{
		for (const float Side : { 220.f, 527.2f })
		{
			const FGeometry MapSurface = FGeometry::MakeRoot(FVector2f(Side, Side),
				FSlateLayoutTransform(1.25f, FVector2f(24.f, 18.f)));
			const FGeometry Background = MapSurface.MakeChild(Projection);
			const FVector2f Texel = Background.LocalToAbsolute(FVector2f(CaptureUV * Side));
			const FVector2f Marker = MapSurface.LocalToAbsolute(
				FVector2f(CatrunMinimap::ToDisplayUV(CaptureUV, Projection) * Side));
			TestTrue(TEXT("Unwarped marker center agrees with the rendered image in both map sizes"),
				Marker.Equals(Texel, 1.e-4f));
		}
	}

	const FSlateRenderTransform PreviousProjection = Projection;
	TestFalse(TEXT("Edge-on camera view is unusable"),
		CatrunMinimap::FitCameraProjection(CaptureSize, 0., FRotator(0., -135., 0.), Projection));
	TestTrue(TEXT("An unusable view retains the previous transform"), Projection == PreviousProjection);
	TestFalse(TEXT("Invalid capture bounds are rejected"),
		CatrunMinimap::FitCameraProjection(FVector2D(0., 600.), 0., Stage2View, Projection));

	const FVector2D RectangularSize(300., 600.);
	if (TestTrue(TEXT("Nonzero capture yaw and non-square capture bounds are usable"),
		CatrunMinimap::FitCameraProjection(RectangularSize, 90., FRotator(-90., 90., 0.), Projection)))
	{
		CheckUV(TEXT("Narrow capture is centered at its left edge"), FVector2D(0., 0.), FVector2D(.25, 0.));
		CheckUV(TEXT("Narrow capture is centered at its right edge"), FVector2D(1., 1.), FVector2D(.75, 1.));
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunMinimapLayoutTest, "Catrun.UI.Minimap.ExpandedLayoutPreservesMapProjection",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCatrunMinimapLayoutTest::RunTest(const FString&)
{
	FAnchorData Compact;
	Compact.Anchors = FAnchors(1.f, 0.f);
	Compact.Alignment = FVector2D(1., 0.);
	Compact.Offsets = FMargin(-24.f, 24.f, 232.f, 232.f);
	const FVector2D Desktop(1280., 720.);
	const FAnchorData Open = UCatrunMinimapWidget::GetFrameLayout(Compact, Desktop, true, .75f, 700.f);
	TestTrue(TEXT("Expanded map is centered in the player screen"),
		Open.Anchors == FAnchors(.5f) && Open.Alignment == FVector2D(.5, .5)
		&& Open.Offsets.Left == 0.f && Open.Offsets.Top == 0.f);
	TestTrue(TEXT("Expansion fits the smaller screen axis and preserves the square map surface"),
		Open.Offsets.Right == 540.f && Open.Offsets.Bottom == 540.f);
	TestTrue(TEXT("Closing restores the Blueprint compact placement"),
		UCatrunMinimapWidget::GetFrameLayout(Compact, Desktop, false, .75f, 700.f) == Compact);

	const FAnchorData Tall = UCatrunMinimapWidget::GetFrameLayout(Compact, FVector2D(200., 500.), true, .75f, 700.f);
	TestTrue(TEXT("Tall viewport fits by its width"), Tall.Offsets.Right == 150.f && Tall.Offsets.Bottom == 150.f);
	const FAnchorData Large = UCatrunMinimapWidget::GetFrameLayout(Compact, FVector2D(1920., 1080.), true, .75f, 700.f);
	TestTrue(TEXT("Large viewport respects the authored limit"), Large.Offsets.Right == 700.f && Large.Offsets.Bottom == 700.f);
	const FAnchorData Narrow = UCatrunMinimapWidget::GetFrameLayout(Compact, FVector2D(200., 500.), false, .75f, 700.f);
	TestTrue(TEXT("Compact map shrinks without clipping its authored inset"),
		Narrow.Anchors == Compact.Anchors && Narrow.Offsets.Right == 152.f && Narrow.Offsets.Bottom == 152.f);
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
	const auto* ArmorKind = Presenter->Enemies.Find(TWeakObjectPtr<AActor>(Armor));
	TestTrue(TEXT("Armor uses its own marker pool"), ArmorKind && *ArmorKind == ECatrunMinimapEnemyKind::Armor);
	TestFalse(TEXT("No player controller cannot toggle a map"), Presenter->CanUseMinimap(nullptr));
	Presenter->ToggleMap();
	TestNull(TEXT("Tab without a game viewport leaves the presenter waiting for its owner"), Presenter->MinimapWidget.Get());

	ACatrunCandle* Candle = World->SpawnActor<ACatrunCandle>();
	World->SpawnActor<AActor>();
	if (!TestNotNull(TEXT("Spawned candle"), Candle))
		return false;
	Presenter->StartTracking(*World);
	TestEqual(TEXT("New candle tracked and other actor ignored"), Presenter->Enemies.Num(), 2);
	const auto* CandleKind = Presenter->Enemies.Find(TWeakObjectPtr<AActor>(Candle));
	TestTrue(TEXT("Candle uses its own marker pool"), CandleKind && *CandleKind == ECatrunMinimapEnemyKind::Candle);
	TestTrue(TEXT("Destroy succeeds"), World->DestroyActor(Armor));
	TestEqual(TEXT("Destroyed armor removed from the cache"), Presenter->Enemies.Num(), 1);
	TestTrue(TEXT("Candle is still tracked"), Presenter->Enemies.Contains(TWeakObjectPtr<AActor>(Candle)));

	auto* Settings = World->GetSubsystem<UCatrunSettingsSubsystem>();
	UClass* PanelClass = LoadClass<UCatrunMinimapWidget>(nullptr, TEXT("/Game/UI/Minimap/WBP_Minimap.WBP_Minimap_C"));
	if (!TestNotNull(TEXT("World settings subsystem"), Settings) || !TestNotNull(TEXT("Concrete minimap panel class"), PanelClass))
		return false;
	Presenter->MinimapWidget = NewObject<UCatrunMinimapWidget>(World, PanelClass);
	Presenter->MinimapWidget->SetExpanded(true);
	Presenter->MinimapWidget->NativeTick(FGeometry(), 0.f);
	TestTrue(TEXT("Cinematic suppression retains the user's expanded map choice"), Presenter->MinimapWidget->bExpanded);
	TestEqual(TEXT("Suppressed map is transparent before the next marker timer"), Presenter->MinimapWidget->GetRenderOpacity(), 0.f);
	TestTrue(TEXT("Settings interruption is subscribed before gameplay starts"), Settings->OnSettingsOpened.IsBoundToObject(Presenter));
	Settings->OnSettingsOpened.Broadcast();
	TestFalse(TEXT("Opening settings clears expanded state without waiting for the timer"), Presenter->MinimapWidget->bExpanded);
	TestEqual(TEXT("Opening settings hides the map immediately"), Presenter->MinimapWidget->GetVisibility(), ESlateVisibility::Collapsed);

	Presenter->EndPlay(EEndPlayReason::LevelTransition);
	TestFalse(TEXT("Leaving the level stops refreshes"), World->GetTimerManager().TimerExists(Presenter->UpdateTimer));
	TestFalse(TEXT("Candle destruction callback is unbound"), Candle->OnDestroyed.IsBound());
	TestFalse(TEXT("Leaving the level removes the settings callback"), Settings->OnSettingsOpened.IsBoundToObject(Presenter));
	World->SpawnActor<ACatrunCandle>();
	TestEqual(TEXT("Leaving the level clears cache and removes spawn hook"), Presenter->Enemies.Num(), 0);
	return true;
}

#endif
