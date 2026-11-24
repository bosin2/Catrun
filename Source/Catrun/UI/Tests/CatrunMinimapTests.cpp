#if WITH_DEV_AUTOMATION_TESTS

#include "UI/CatrunMinimapWidget.h"

#if WITH_EDITOR
#include "AssetCompilingManager.h"
#endif
#include "Camera/CameraTypes.h"
#include "Components/Border.h"
#include "Components/BoxComponent.h"
#include "Components/Image.h"
#include "Engine/Engine.h"
#include "Engine/Texture2D.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Engine/World.h"
#include "Framework/Application/SlateApplication.h"
#include "HAL/FileManager.h"
#include "ImageUtils.h"
#include "Interaction/CatrunStatuePuzzle.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "Layout/Geometry.h"
#include "Math/InverseRotationMatrix.h"
#include "Misc/App.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/Guid.h"
#include "Misc/Paths.h"
#include "Misc/ScopeExit.h"
#include "Monster/CatrunArmor.h"
#include "Monster/CatrunCandle.h"
#include "SceneView.h"
#include "Settings/CatrunSettingsSubsystem.h"
#include "Sound/CatrunDoor.h"
#include "Sound/CatrunNoBellZone.h"
#include "Slate/WidgetRenderer.h"
#include "Widgets/Layout/SBorder.h"

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

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunMinimapNeighborhoodTest, "Catrun.UI.Minimap.NeighborhoodContainsGameplayViewAndRegisters",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCatrunMinimapNeighborhoodTest::RunTest(const FString&)
{
	const FVector2D CaptureCenter(120., -780.);
	const FVector2D CaptureSize(4500., 8000.);
	const double CaptureYaw = 37.;
	const FRotator Rotation(-55., -135., 0.);
	const FRotationMatrix Basis(Rotation);
	const FVector Right = Basis.GetUnitAxis(EAxis::Y);
	const FVector Down = -Basis.GetUnitAxis(EAxis::Z);
	const FVector Forward = Basis.GetUnitAxis(EAxis::X);
	constexpr double Coverage = 1.30;
	constexpr double OrthoWidth = 1200.;

	for (const FVector& Player : { FVector(340., -620., 75.), FVector(-240., 310., 205.) })
	{
		FMinimalViewInfo Camera;
		Camera.Location = Player - Forward * 900.;
		Camera.Rotation = Rotation;
		Camera.ProjectionMode = ECameraProjectionMode::Orthographic;
		Camera.OrthoWidth = OrthoWidth;
		Camera.AspectRatio = 16.f / 9.f;
		for (const FIntPoint& Viewport : { FIntPoint(1280, 720), FIntPoint(600, 800) })
		{
			const FIntRect Rect(0, 0, Viewport.X, Viewport.Y);
			FSceneViewProjectionData View;
			View.ViewOrigin = Camera.Location;
			View.ViewRotationMatrix = FInverseRotationMatrix(Rotation) * FMatrix(
				FPlane(0, 0, 1, 0), FPlane(1, 0, 0, 0), FPlane(0, 1, 0, 0), FPlane(0, 0, 0, 1));
			View.SetViewRectangle(Rect);
			FMinimalViewInfo MutableCamera = Camera;
			FMinimalViewInfo::CalculateProjectionMatrixGivenViewRectangle(
				MutableCamera, AspectRatio_MaintainXFOV, Rect, View);

			FSlateRenderTransform Projection;
			if (!TestTrue(TEXT("Camera footprint produces a local projection"),
				CatrunMinimap::MakeLocalProjection(CaptureCenter, CaptureSize, CaptureYaw, Player, View, Coverage, Projection)))
				continue;
			const auto CaptureUV = [&](const FVector& World)
			{
				FVector2D UV = FVector2D::ZeroVector;
				TestTrue(TEXT("Fixture point is on the source image"),
					CatrunMinimap::Project(FVector2D(World.X, World.Y), CaptureCenter, CaptureSize, CaptureYaw, UV));
				return UV;
			};
			TestTrue(TEXT("Cat remains centered at both world positions"),
				CatrunMinimap::ToDisplayUV(CaptureUV(Player), Projection).Equals(FVector2D(.5, .5), 1.e-6));

			const double OrthoHeight = OrthoWidth * Viewport.Y / Viewport.X;
			const double LocalSide = FMath::Max(OrthoWidth, OrthoHeight) * Coverage;
			const auto GroundCorner = [&](double CameraX, double CameraY)
			{
				const FVector Point = Player + Right * CameraX + Down * CameraY;
				return Point + Forward * ((Player.Z - Point.Z) / Forward.Z);
			};
			FVector2D DisplayUV;
			const FVector2D NearUV = CaptureUV(GroundCorner(OrthoWidth * .3, -OrthoHeight * .2));
			if (TestTrue(TEXT("Near enemy remains visible"), CatrunMinimap::TryGetDisplayUV(NearUV, Projection, DisplayUV)))
			{
				TestTrue(TEXT("Enemy offset follows the viewport's camera axes and real footprint"),
					DisplayUV.Equals(FVector2D(.5 + OrthoWidth * .3 / LocalSide, .5 - OrthoHeight * .2 / LocalSide), 1.e-6));
				for (const float Side : { 220.f, 280.f })
				{
					const FVector2D Size(Side, Side);
					const FGeometry MapSurface = FGeometry::MakeRoot(FVector2f(Size),
						FSlateLayoutTransform(1.25f, FVector2f(24.f, 18.f)));
					const FGeometry Image = MapSurface.MakeChild(CatrunMinimap::ToImageTransform(Projection, Size));
					TestTrue(TEXT("Enemy marker stays registered to the texel at both panel sizes"),
						MapSurface.LocalToAbsolute(FVector2f(DisplayUV * Size)).Equals(
							Image.LocalToAbsolute(FVector2f(NearUV * Size)), .001f));
				}
			}
			const FVector2D CornerUV = CaptureUV(GroundCorner(OrthoWidth * .5, OrthoHeight * .5));
			TestTrue(TEXT("Local square contains a camera corner with the configured extra coverage"),
				CatrunMinimap::TryGetDisplayUV(CornerUV, Projection, DisplayUV)
				&& DisplayUV.Equals(FVector2D(.5 + OrthoWidth * .5 / LocalSide, .5 + OrthoHeight * .5 / LocalSide), 1.e-6));
			const FVector2D FarUV = CaptureUV(GroundCorner(LocalSide * .51, 0.));
			TestFalse(TEXT("Enemy just outside the local window is hidden"),
				CatrunMinimap::TryGetDisplayUV(FarUV, Projection, DisplayUV));

			const FSlateRenderTransform PreviousProjection = Projection;
			TestFalse(TEXT("Invalid coverage is rejected"),
				CatrunMinimap::MakeLocalProjection(CaptureCenter, CaptureSize, CaptureYaw, Player, View, 0., Projection));
			TestTrue(TEXT("Invalid coverage cannot overwrite the usable transform"), Projection == PreviousProjection);
		}
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunMinimapLayoutTest, "Catrun.UI.Minimap.HeldLayoutPreservesCornerPlacement",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCatrunMinimapLayoutTest::RunTest(const FString&)
{
	FAnchorData Compact;
	Compact.Anchors = FAnchors(1.f, 0.f);
	Compact.Alignment = FVector2D(1., 0.);
	Compact.Offsets = FMargin(-24.f, 24.f, 232.f, 232.f);
	const FVector2D Desktop(1280., 720.);
	const FAnchorData Open = UCatrunMinimapWidget::GetFrameLayout(Compact, Desktop, 1., 1.25f);
	TestTrue(TEXT("Held map retains authored anchors, alignment and inset"),
		Open.Anchors == Compact.Anchors && Open.Alignment == Compact.Alignment
		&& Open.Offsets.Left == Compact.Offsets.Left && Open.Offsets.Top == Compact.Offsets.Top);
	TestTrue(TEXT("Holding Tab enlarges both authored dimensions by 25 percent"),
		Open.Offsets.Right == 290.f && Open.Offsets.Bottom == 290.f);
	TestTrue(TEXT("Closing restores the Blueprint compact placement"),
		UCatrunMinimapWidget::GetFrameLayout(Compact, Desktop, 0., 1.25f) == Compact);

	const FAnchorData Tall = UCatrunMinimapWidget::GetFrameLayout(Compact, FVector2D(200., 500.), 1., 1.25f);
	TestTrue(TEXT("Tall viewport fits by the width available from the authored right inset"),
		Tall.Offsets.Right == 176.f && Tall.Offsets.Bottom == 176.f);
	const FAnchorData Short = UCatrunMinimapWidget::GetFrameLayout(Compact, FVector2D(500., 270.), 1., 1.25f);
	TestTrue(TEXT("Short viewport fits by the height available from the authored top inset"),
		Short.Offsets.Right == 246.f && Short.Offsets.Bottom == 246.f);
	const FAnchorData Narrow = UCatrunMinimapWidget::GetFrameLayout(Compact, FVector2D(200., 500.), 0., 1.25f);
	TestTrue(TEXT("Compact map shrinks without clipping its authored inset"),
		Narrow.Anchors == Compact.Anchors && Narrow.Offsets.Right == 176.f && Narrow.Offsets.Bottom == 176.f);
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
	TestFalse(TEXT("Gameplay eligibility requires a player controller"), Presenter->CanUseMinimap(nullptr));
	TestNull(TEXT("Without a game viewport the presenter waits for its owner"), Presenter->MinimapWidget.Get());

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
	UCatrunMinimapWidget* Widget = Presenter->MinimapWidget;
	Widget->HoldTransitionDuration = .5f;
	Widget->AdvanceHoldAnimation(true, .125f);
	TestEqual(TEXT("Custom duration takes a quarter of a half-second transition"), Widget->HoldProgress, .25f);
	Widget->AdvanceHoldAnimation(true, .375f);
	TestEqual(TEXT("Custom duration reaches the held endpoint in half a second"), Widget->HoldProgress, 1.f);
	Widget->AdvanceHoldAnimation(true, 10.f);
	TestEqual(TEXT("Ten seconds of continued hold keep the endpoint expanded"), Widget->HoldProgress, 1.f);
	Widget->AdvanceHoldAnimation(false, .25f);
	TestEqual(TEXT("Release starts the reverse transition at the custom pace"), Widget->HoldProgress, .5f);
	Widget->AdvanceHoldAnimation(false, .25f);
	TestEqual(TEXT("Release restores the compact endpoint"), Widget->HoldProgress, 0.f);
	Widget->HoldTransitionDuration = 0.f;
	Widget->AdvanceHoldAnimation(true, 0.f);
	TestEqual(TEXT("Zero duration expands immediately"), Widget->HoldProgress, 1.f);
	Widget->AdvanceHoldAnimation(false, 0.f);
	TestEqual(TEXT("Zero duration collapses immediately"), Widget->HoldProgress, 0.f);
	// Input edges are covered through Slate in RoutedHoldAcrossStages. Prime only the detached layout here.
	Widget->HoldProgress = 1.f;
	Presenter->MinimapWidget->NativeTick(FGeometry(), 0.f);
	TestEqual(TEXT("An ineligible widget tick resets compact before the marker timer"), Widget->HoldProgress, 0.f);
	TestEqual(TEXT("Suppressed map is transparent before the next marker timer"), Presenter->MinimapWidget->GetRenderOpacity(), 0.f);
	TestTrue(TEXT("Settings interruption is subscribed before gameplay starts"), Settings->OnSettingsOpened.IsBoundToObject(Presenter));
	Widget->HoldProgress = 1.f;
	Widget->SetRenderOpacity(1.f);
	Settings->OnSettingsOpened.Broadcast();
	TestEqual(TEXT("Opening settings clears expanded state without waiting for the timer"), Widget->HoldProgress, 0.f);
	TestEqual(TEXT("Opening settings hides the map immediately"), Presenter->MinimapWidget->GetRenderOpacity(), 0.f);

	Presenter->EndPlay(EEndPlayReason::LevelTransition);
	TestFalse(TEXT("Leaving the level stops refreshes"), World->GetTimerManager().TimerExists(Presenter->UpdateTimer));
	TestFalse(TEXT("Candle destruction callback is unbound"), Candle->OnDestroyed.IsBound());
	TestFalse(TEXT("Leaving the level removes the settings callback"), Settings->OnSettingsOpened.IsBoundToObject(Presenter));
	World->SpawnActor<ACatrunCandle>();
	TestEqual(TEXT("Leaving the level clears cache and removes spawn hook"), Presenter->Enemies.Num(), 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunMinimapNavigationTest, "Catrun.UI.Minimap.NavigationSourcesAndSilentRestore",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCatrunMinimapNavigationTest::RunTest(const FString&)
{
	const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(true)
		.CreateNavigation(false).CreateAISystem(false);
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
	if (!TestNotNull(TEXT("Detached navigation world"), World)) return false;
	GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
	ON_SCOPE_EXIT { GEngine->DestroyWorldContext(World); World->DestroyWorld(false); };
	World->InitializeActorsForPlay(FURL());
	auto* Map = World->SpawnActor<ACatrunMinimapPresenter>();
	Map->MapSize = FVector2D(2000, 2000);
	auto* Hole = World->SpawnActor<ACatrunNoBellZone>();
	Hole->Tags.Add(TEXT("CatrunMapCatHole"));
	Hole->Box->SetWorldLocation(FVector(40, 120, 45));
	World->SpawnActor<ACatrunNoBellZone>(); // An unrelated no-bell volume is not a passage.
	auto* Exit = World->SpawnActor<ACatrunStageExit>();
	Exit->Trigger->SetWorldLocation(FVector(320, -150, 0));
	Map->StartTracking(*World);
	auto* Door = World->SpawnActor<ACatrunDoor>();
	auto* Puzzle = World->SpawnActor<ACatrunStatuePuzzle>();
	const auto Box = [World](FVector Location)
	{
		auto* Actor = World->SpawnActor<AActor>();
		auto* Component = NewObject<UBoxComponent>(Actor);
		Actor->SetRootComponent(Component);
		Component->SetBoxExtent(FVector(20));
		Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Component->RegisterComponent();
		Actor->SetActorLocation(Location);
		return Actor;
	};
	for (int32 Index = 0; Index < 2; ++Index)
	{
		auto& Link = Puzzle->Links.AddDefaulted_GetRef();
		Link.PuzzleId = Index == 0 ? TEXT("A") : TEXT("B");
		Link.Statue = Box(FVector(300 * Index, 150, 40));
		Link.Plate = Box(FVector(300 * Index, 250, 5));
		Link.Gate = Box(FVector(300 * Index, 350, 180));
	}
	Puzzle->InitializePuzzle();
	Map->SampleLandmarks();
	const auto Count = [Map](ECatrunMapLandmark Kind)
	{
		const auto* Found = Map->LandmarkPositions.Find(Kind);
		return Found ? Found->Num() : 0;
	};
	const auto At = [Map](ECatrunMapLandmark Kind, const FVector& Expected)
	{
		FVector2D UV;
		const auto* Found = Map->LandmarkPositions.Find(Kind);
		return Found && CatrunMinimap::Project(FVector2D(Expected), Map->MapCenter, Map->MapSize, Map->CaptureYawDegrees, UV)
			&& Found->ContainsByPredicate([&](const FVector2D& Value) { return Value.Equals(UV, 1.e-6); });
	};
	TestEqual(TEXT("Only an authored cat hole appears"), Count(ECatrunMapLandmark::CatHole), 1);
	TestTrue(TEXT("Hole uses the volume center"), At(ECatrunMapLandmark::CatHole, Hole->Box->GetComponentLocation()));
	TestTrue(TEXT("Exit uses the travel trigger"), At(ECatrunMapLandmark::Exit, Exit->Trigger->GetComponentLocation()));
	TestEqual(TEXT("New swing door and both unsolved links are closed"), Count(ECatrunMapLandmark::ClosedDoor), 3);
	Door->SetOpen(true);
	// This fixture exercises marker sampling from the live puzzle owner, not persistence.
	Puzzle->Links[0].bCompleted = true;
	Map->SampleLandmarks();
	TestTrue(TEXT("Open swing door stays at its doorway"), At(ECatrunMapLandmark::OpenDoor, Door->GetDoorwayCenter()));
	TestTrue(TEXT("Completed gate appears open at original threshold"), At(ECatrunMapLandmark::OpenDoor, Puzzle->Links[0].InitialGateBounds.GetCenter()));
	TestTrue(TEXT("Unsolved gate remains closed"), At(ECatrunMapLandmark::ClosedDoor, Puzzle->Links[1].InitialGateBounds.GetCenter()));
	World->DestroyActor(Exit);
	World->DestroyActor(Puzzle);
	Map->SampleLandmarks();
	TestEqual(TEXT("Destroyed exit removed"), Count(ECatrunMapLandmark::Exit), 0);
	TestEqual(TEXT("Destroyed puzzle owner removes both links"), Count(ECatrunMapLandmark::ClosedDoor), 0);
	Map->EndPlay(EEndPlayReason::LevelTransition);
	TestEqual(TEXT("World travel clears landmark sources"), Map->Landmarks.Num(), 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunMinimapOffscreenPreviewTest, "Catrun.UI.Minimap.OffscreenPreview",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCatrunMinimapOffscreenPreviewTest::RunTest(const FString&)
{
	if (!FParse::Param(FCommandLine::Get(), TEXT("CatrunMinimapRender")))
		return true;
	if (!TestTrue(TEXT("Preview requires an initialized Slate renderer and RHI"),
		FSlateApplication::IsInitialized() && FApp::CanEverRender() && FSlateApplication::Get().GetRenderer()))
		return false;

	UClass* PanelClass = LoadClass<UCatrunMinimapWidget>(nullptr, TEXT("/Game/UI/Minimap/WBP_Minimap_Floorplan.WBP_Minimap_Floorplan_C"));
	UTexture2D* Floorplan = LoadObject<UTexture2D>(nullptr, TEXT("/Game/UI/Minimap/T_Floorplan_Stage2.T_Floorplan_Stage2"));
	if (!TestNotNull(TEXT("Saved floorplan widget Blueprint"), PanelClass)
		|| !TestNotNull(TEXT("Saved Stage2 floorplan texture"), Floorplan))
		return false;

	const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(false)
		.CreateNavigation(false).CreateAISystem(false);
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
	if (!TestNotNull(TEXT("Detached widget world"), World))
		return false;
	ON_SCOPE_EXIT { World->DestroyWorld(false); };

	ACatrunMinimapPresenter* Presenter = World->SpawnActor<ACatrunMinimapPresenter>();
	UCatrunMinimapWidget* Widget = CreateWidget<UCatrunMinimapWidget>(World, PanelClass);
	if (!TestNotNull(TEXT("Preview presenter"), Presenter) || !TestNotNull(TEXT("Preview widget"), Widget))
		return false;
	Presenter->BackgroundTexture = Floorplan;
	Presenter->MapCenter = FVector2D(1450., 1795.);
	Presenter->MapSize = FVector2D(4862., 4862.);
	if (!TestTrue(TEXT("Saved widget uses the native minimap configuration"), Widget->InitializeMap(*Presenter))
		|| !TestNotNull(TEXT("Saved minimap frame slot"), Widget->FrameSlot.Get()))
		return false;

	const FVector2D DrawSize(1280., 720.);
	const FIntRect ViewRect(0, 0, 1280, 720);
	const FVector2D CatUV(.65, .40);
	const FVector Cat(Presenter->MapCenter.X + (.5 - CatUV.Y) * Presenter->MapSize.Y,
		Presenter->MapCenter.Y + (CatUV.X - .5) * Presenter->MapSize.X, 75.);
	FMinimalViewInfo Camera;
	Camera.Rotation = FRotator(-55., -135., 0.);
	Camera.Location = Cat - Camera.Rotation.Vector() * 900.;
	Camera.ProjectionMode = ECameraProjectionMode::Orthographic;
	Camera.OrthoWidth = 1375.f;
	Camera.AspectRatio = 16.f / 9.f;
	FSceneViewProjectionData View;
	View.ViewOrigin = Camera.Location;
	View.ViewRotationMatrix = FInverseRotationMatrix(Camera.Rotation) * FMatrix(
		FPlane(0, 0, 1, 0), FPlane(1, 0, 0, 0), FPlane(0, 1, 0, 0), FPlane(0, 0, 0, 1));
	View.SetViewRectangle(ViewRect);
	FMinimalViewInfo::CalculateProjectionMatrixGivenViewRectangle(Camera, AspectRatio_MaintainXFOV, ViewRect, View);
	// This point is 1,485 units to the right of the cat. The compact half-width is 1,237.5 units.
	const FVector Far = Cat + FRotationMatrix(Camera.Rotation).GetUnitAxis(EAxis::Y) * 1485.;
	FVector2D FarUV;
	if (!TestTrue(TEXT("Far armor lies within the source capture"),
		CatrunMinimap::Project(FVector2D(Far.X, Far.Y), Presenter->MapCenter, Presenter->MapSize,
			Presenter->CaptureYawDegrees, FarUV)))
		return false;

	const FVector2D CenterUV(.5, .5);
	const FVector2D ArmorUVs[] = { FVector2D(.70, .40), FarUV, FVector2D(.10, .15) };
	const FVector2D CandleUVs[] = { FVector2D(.64, .45) };

#if WITH_EDITOR
	FAssetCompilingManager::Get().FinishAllCompilation();
#endif
	const TSharedRef<SWidget> SlateWidget = Widget->TakeWidget();
	SlateWidget->SetCanTick(false);
	FWidgetRenderer Renderer(true, true);
	FString PreviewDirectory;
	if (!FParse::Value(FCommandLine::Get(), TEXT("CatrunMinimapPreviewDir="), PreviewDirectory))
	{
		PreviewDirectory = FPaths::ProjectSavedDir() / TEXT("MinimapPreviews") / FGuid::NewGuid().ToString(EGuidFormats::Digits);
	}
	IFileManager& Files = IFileManager::Get();
	if (!TestTrue(TEXT("Preview directory is new and writable"), !PreviewDirectory.IsEmpty()
		&& !Files.DirectoryExists(*PreviewDirectory) && Files.MakeDirectory(*PreviewDirectory, true)))
		return false;
	AddInfo(FString::Printf(TEXT("Preview output: %s"), *PreviewDirectory));

	struct FPreviewPhase
	{
		const TCHAR* Name;
		bool bHeld;
		float FrameSide;
		double Coverage;
		double MarkerSize;
		int32 VisibleArmor;
	};
	const FPreviewPhase Phases[] = {
		{ TEXT("compact"), false, 240.f, 1., 1., 1 },
		{ TEXT("expanding"), true, 270.f, 1.225, .925, 2 },
		{ TEXT("held"), true, 300.f, 1.45, .85, 2 },
		{ TEXT("collapsing"), false, 270.f, 1.225, .925, 2 },
		{ TEXT("released"), false, 240.f, 1., 1., 1 },
	};
	FVector2D CompactArmorSize = FVector2D::ZeroVector;
	FVector2D CompactCandleSize = FVector2D::ZeroVector;
	double CompactLandmarkWidth = 0.;
	for (const FPreviewPhase& Preview : Phases)
	{
		const TCHAR* Phase = Preview.Name;
		Widget->AdvanceHoldAnimation(Preview.bHeld, .09f);
		Widget->UpdateLayout(DrawSize);
		if (!TestTrue(TEXT("Fixture produces local gameplay projection"),
			CatrunMinimap::MakeLocalProjection(Presenter->MapCenter, Presenter->MapSize, Presenter->CaptureYawDegrees,
				Cat, View, Widget->GetNeighborhoodCoverage(DrawSize), Widget->MapProjection)))
			return false;
		Widget->ApplyImageProjection();
		Widget->UpdateMarker(*Widget->PlayerMarker, &CenterUV);
		Widget->UpdateEnemyMarkers(ECatrunMinimapEnemyKind::Armor, ArmorUVs);
		Widget->UpdateEnemyMarkers(ECatrunMinimapEnemyKind::Candle, CandleUVs);
		int32 VisibleArmor = 0;
		for (const UCanvasPanelSlot* Slot : Widget->ArmorMarkers)
			VisibleArmor += Slot->GetContent()->GetVisibility() == ESlateVisibility::HitTestInvisible;
		TestEqual(FString::Printf(TEXT("%s visible armor includes the far marker only while held"), Phase),
			VisibleArmor, Preview.VisibleArmor);
		TestTrue(FString::Printf(TEXT("%s nearby candle remains visible"), Phase), Widget->CandleMarkers.Num() == 1
			&& Widget->CandleMarkers[0]->GetContent()->GetVisibility() == ESlateVisibility::HitTestInvisible);
		UTextureRenderTarget2D* Target = Renderer.DrawWidget(SlateWidget, DrawSize);
		FImage Pixels;
		if (!TestNotNull(TEXT("Offscreen render target"), Target)
			|| !TestTrue(TEXT("Slate pixels were read back"), FImageUtils::GetRenderTargetImage(Target, Pixels)))
			return false;
		const FString Path = PreviewDirectory / FString::Printf(TEXT("%s.png"), Phase);
		if (!TestTrue(TEXT("Saved minimap preview as PNG"), FImageUtils::SaveImageByExtension(*Path, Pixels)))
			return false;

		const FAnchorData FrameLayout = Widget->FrameSlot->GetLayout();
		const FVector2D FrameSize(FrameLayout.Offsets.Right, FrameLayout.Offsets.Bottom);
		const FVector2D FrameOrigin = FrameLayout.Anchors.Minimum * DrawSize - FrameLayout.Alignment * FrameSize
			+ FVector2D(FrameLayout.Offsets.Left, FrameLayout.Offsets.Top);
		TestTrue(FString::Printf(TEXT("%s dimensions fit the animation phase"), Phase), FrameSize.Equals(FVector2D(Preview.FrameSide), .01));
		TestTrue(FString::Printf(TEXT("%s keeps the upper-right corner fixed"), Phase),
			(FrameOrigin + FVector2D(FrameSize.X, 0.)).Equals(FVector2D(1256., 24.), .01));
		const FGeometry& ImageGeometry = Widget->MapBackground->GetPaintSpaceGeometry();
		const FVector2D ImageSize = ImageGeometry.GetLocalSize();
		const auto Texel = [&](const FVector2D& UV) { return FVector2D(ImageGeometry.LocalToAbsolute(UV * ImageSize)); };
		const double LandmarkWidth = (Texel(FVector2D(.6, .5)) - Texel(FVector2D(.5, .5))).Size();
		if (&Preview == &Phases[0])
			CompactLandmarkWidth = LandmarkWidth;
		TestTrue(FString::Printf(TEXT("%s landmark follows the animated crop"), Phase),
			LandmarkWidth > 0. && FMath::IsNearlyEqual(LandmarkWidth,
				CompactLandmarkWidth * (Preview.FrameSide - 20.) / 220. / Preview.Coverage, .1));
		const auto CheckEnemyPaint = [&](const TCHAR* Kind, const UCanvasPanelSlot& Slot, const FVector2D& CaptureUV,
			FVector2D* CompactSize)
		{
			const FGeometry& MarkerGeometry = Slot.GetContent()->GetPaintSpaceGeometry();
			const FVector2D MarkerSize = MarkerGeometry.GetLocalSize();
			const FVector2D Center = MarkerGeometry.LocalToAbsolute(MarkerSize * .5);
			TestTrue(FString::Printf(TEXT("%s %s stays registered to its texel"), Phase, Kind), Center.Equals(Texel(CaptureUV), .5));
			if (CompactSize)
			{
				const FSlateRect Rect = MarkerGeometry.GetRenderBoundingRect();
				const FVector2D Painted(Rect.Right - Rect.Left, Rect.Bottom - Rect.Top);
				if (&Preview == &Phases[0])
					*CompactSize = Painted;
				TestTrue(FString::Printf(TEXT("%s %s scales about its center"), Phase, Kind),
					Painted.GetMin() > 0. && Painted.Equals(*CompactSize * Preview.MarkerSize, .1));
			}
		};
		if (Widget->ArmorMarkers.IsValidIndex(0))
			CheckEnemyPaint(TEXT("near armor"), *Widget->ArmorMarkers[0], ArmorUVs[0], &CompactArmorSize);
		if (Widget->CandleMarkers.IsValidIndex(0))
			CheckEnemyPaint(TEXT("near candle"), *Widget->CandleMarkers[0], CandleUVs[0], &CompactCandleSize);
		if (VisibleArmor == 2)
			CheckEnemyPaint(TEXT("far armor"), *Widget->ArmorMarkers[1], FarUV, nullptr);
		const int32 Left = FMath::RoundToInt(FrameOrigin.X);
		const int32 MidY = FMath::RoundToInt(FrameOrigin.Y + FrameSize.Y * .5);
		const FIntPoint RimPixel(Left + 1, MidY);
		const FIntPoint FillPixel(Left + 5, MidY);
		const FIntPoint BackdropPixel(Left + 15, MidY);
		const FIntRect PixelBounds(0, 0, Pixels.SizeX, Pixels.SizeY);
		if (!TestTrue(TEXT("Frame samples are inside the rendered viewport"),
			PixelBounds.Contains(RimPixel) && PixelBounds.Contains(FillPixel) && PixelBounds.Contains(BackdropPixel)))
			return false;

		if (const UBorder* Frame = Cast<UBorder>(Widget->FrameSlot->GetContent()))
		{
			const TSharedPtr<SWidget> FrameSlate = Frame->GetCachedWidget();
			const FSlateBrush* SlateBrush = FrameSlate && FrameSlate->GetType() == FName(TEXT("SBorder"))
				? StaticCastSharedPtr<SBorder>(FrameSlate)->GetBorderImage() : nullptr;
			const UObject* BrushResource = Frame->Background.GetResourceObject();
			const UObject* SlateResource = SlateBrush ? SlateBrush->GetResourceObject() : nullptr;
			const FGeometry& FrameGeometry = Frame->GetPaintSpaceGeometry();
			const FVector2D PaintedSize = FrameGeometry.GetLocalSize();
			AddInfo(FString::Printf(TEXT("%s frame draw=%d resource=%s class=%s Slate draw=%d resource=%s brush alpha=%.3f content alpha=%.3f paint bounds=%s local size=(%.1f,%.1f)"),
				Phase, int32(Frame->Background.GetDrawType()), *GetPathNameSafe(BrushResource),
				*GetNameSafe(BrushResource ? BrushResource->GetClass() : nullptr),
				SlateBrush ? int32(SlateBrush->GetDrawType()) : -1, *GetPathNameSafe(SlateResource),
				Frame->GetBrushColor().A, Frame->GetContentColorAndOpacity().A,
				*FrameGeometry.GetRenderBoundingRect().ToString(), PaintedSize.X, PaintedSize.Y));
		}
		const float RimAlpha = Pixels.GetOnePixelLinear(RimPixel.X, RimPixel.Y).A;
		const float FillAlpha = Pixels.GetOnePixelLinear(FillPixel.X, FillPixel.Y).A;
		AddInfo(FString::Printf(TEXT("%s frame rim alpha %.3f at (%d,%d), padding alpha %.3f at (%d,%d)"),
			Phase, RimAlpha, RimPixel.X, RimPixel.Y, FillAlpha, FillPixel.X, FillPixel.Y));
		TestTrue(FString::Printf(TEXT("%s metallic rim is visible"), Phase), RimAlpha >= .25f);
		TestTrue(FString::Printf(TEXT("%s frame padding has translucent fill"), Phase), FillAlpha >= .04f && FillAlpha <= .20f);

		const ESlateVisibility ImageVisibility = Widget->MapBackground->GetVisibility();
		Widget->MapBackground->SetVisibility(ESlateVisibility::Hidden);
		UTextureRenderTarget2D* BackdropTarget = Renderer.DrawWidget(SlateWidget, DrawSize);
		Widget->MapBackground->SetVisibility(ImageVisibility);
		FImage BackdropPixels;
		if (!TestNotNull(TEXT("Backdrop render target"), BackdropTarget)
			|| !TestTrue(TEXT("Backdrop pixels were read back"), FImageUtils::GetRenderTargetImage(BackdropTarget, BackdropPixels)))
			return false;
		const float BackdropAlpha = BackdropPixels.GetOnePixelLinear(BackdropPixel.X, BackdropPixel.Y).A;
		AddInfo(FString::Printf(TEXT("%s backdrop alpha %.3f at (%d,%d) with transparent map"),
			Phase, BackdropAlpha, BackdropPixel.X, BackdropPixel.Y));
		TestTrue(FString::Printf(TEXT("%s empty map has a stronger translucent backing than the frame padding"), Phase),
			BackdropAlpha > FillAlpha + .12f && BackdropAlpha < .50f);
	}
	Widget->HoldSizeMultiplier = 1.50f;
	Widget->HoldCoverageMultiplier = 1.05f;
	for (const FVector2D& ViewportSize : { DrawSize, FVector2D(304., 720.) })
	{
		Widget->AdvanceHoldAnimation(false, .18f);
		Widget->UpdateLayout(ViewportSize);
		const double CompactCoverage = Widget->GetNeighborhoodCoverage(ViewportSize);
		const double CompactSide = Widget->GetFrameInnerSize(Widget->FrameSlot->GetLayout()).X;
		Widget->AdvanceHoldAnimation(true, .18f);
		Widget->UpdateLayout(ViewportSize);
		const double HeldCoverage = Widget->GetNeighborhoodCoverage(ViewportSize);
		const double HeldSide = Widget->GetFrameInnerSize(Widget->FrameSlot->GetLayout()).X;
		TestTrue(TEXT("Custom low coverage still shrinks terrain for the available inner frame size"),
			FMath::IsNearlyEqual((HeldSide / HeldCoverage) / (CompactSide / CompactCoverage), .90, .001));
	}
	return true;
}

#endif
