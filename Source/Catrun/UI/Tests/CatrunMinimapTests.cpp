#if WITH_DEV_AUTOMATION_TESTS

#include "UI/CatrunMinimapWidget.h"

#if WITH_EDITOR
#include "AssetCompilingManager.h"
#endif
#include "Camera/CameraTypes.h"
#include "Components/Border.h"
#include "Components/Image.h"
#include "Engine/Engine.h"
#include "Engine/Texture2D.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Engine/World.h"
#include "Framework/Application/SlateApplication.h"
#include "HAL/FileManager.h"
#include "ImageUtils.h"
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
	const FAnchorData Open = UCatrunMinimapWidget::GetFrameLayout(Compact, Desktop, true, 1.25f);
	TestTrue(TEXT("Held map retains authored anchors, alignment and inset"),
		Open.Anchors == Compact.Anchors && Open.Alignment == Compact.Alignment
		&& Open.Offsets.Left == Compact.Offsets.Left && Open.Offsets.Top == Compact.Offsets.Top);
	TestTrue(TEXT("Holding Tab enlarges both authored dimensions by 25 percent"),
		Open.Offsets.Right == 290.f && Open.Offsets.Bottom == 290.f);
	TestTrue(TEXT("Closing restores the Blueprint compact placement"),
		UCatrunMinimapWidget::GetFrameLayout(Compact, Desktop, false, 1.25f) == Compact);

	const FAnchorData Tall = UCatrunMinimapWidget::GetFrameLayout(Compact, FVector2D(200., 500.), true, 1.25f);
	TestTrue(TEXT("Tall viewport fits by the width available from the authored right inset"),
		Tall.Offsets.Right == 176.f && Tall.Offsets.Bottom == 176.f);
	const FAnchorData Short = UCatrunMinimapWidget::GetFrameLayout(Compact, FVector2D(500., 270.), true, 1.25f);
	TestTrue(TEXT("Short viewport fits by the height available from the authored top inset"),
		Short.Offsets.Right == 246.f && Short.Offsets.Bottom == 246.f);
	const FAnchorData Narrow = UCatrunMinimapWidget::GetFrameLayout(Compact, FVector2D(200., 500.), false, 1.25f);
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
	// Input edges are covered through Slate in RoutedHoldAcrossStages. Prime only the detached layout here.
	Widget->bExpanded = true;
	Presenter->MinimapWidget->NativeTick(FGeometry(), 0.f);
	TestFalse(TEXT("An ineligible widget tick resets compact before the marker timer"), Widget->bExpanded);
	TestEqual(TEXT("Suppressed map is transparent before the next marker timer"), Presenter->MinimapWidget->GetRenderOpacity(), 0.f);
	TestTrue(TEXT("Settings interruption is subscribed before gameplay starts"), Settings->OnSettingsOpened.IsBoundToObject(Presenter));
	Widget->bExpanded = true;
	Widget->SetRenderOpacity(1.f);
	Settings->OnSettingsOpened.Broadcast();
	TestFalse(TEXT("Opening settings clears expanded state without waiting for the timer"), Presenter->MinimapWidget->bExpanded);
	TestEqual(TEXT("Opening settings hides the map immediately"), Presenter->MinimapWidget->GetRenderOpacity(), 0.f);

	Presenter->EndPlay(EEndPlayReason::LevelTransition);
	TestFalse(TEXT("Leaving the level stops refreshes"), World->GetTimerManager().TimerExists(Presenter->UpdateTimer));
	TestFalse(TEXT("Candle destruction callback is unbound"), Candle->OnDestroyed.IsBound());
	TestFalse(TEXT("Leaving the level removes the settings callback"), Settings->OnSettingsOpened.IsBoundToObject(Presenter));
	World->SpawnActor<ACatrunCandle>();
	TestEqual(TEXT("Leaving the level clears cache and removes spawn hook"), Presenter->Enemies.Num(), 0);
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
	if (!TestTrue(TEXT("Fixture produces normal local gameplay projection"),
		CatrunMinimap::MakeLocalProjection(Presenter->MapCenter, Presenter->MapSize, Presenter->CaptureYawDegrees,
			Cat, View, Widget->NeighborhoodCoverage, Widget->MapProjection)))
		return false;

	const FVector2D CenterUV(.5, .5);
	Widget->UpdateMarker(*Widget->PlayerMarker, &CenterUV);
	const FVector2D ArmorUVs[] = { FVector2D(.70, .40), FVector2D(.10, .15) };
	const FVector2D CandleUVs[] = { FVector2D(.64, .45) };
	Widget->UpdateEnemyMarkers(ECatrunMinimapEnemyKind::Armor, ArmorUVs);
	Widget->UpdateEnemyMarkers(ECatrunMinimapEnemyKind::Candle, CandleUVs);
	TestEqual(TEXT("Only the in-window armor is painted"), Widget->ArmorMarkers.Num(), 1);
	TestEqual(TEXT("The nearby candle is painted"), Widget->CandleMarkers.Num(), 1);

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

	for (const bool bHeld : { false, true })
	{
		Widget->bExpanded = bHeld;
		Widget->UpdateLayout(DrawSize);
		Widget->ApplyImageProjection();
		UTextureRenderTarget2D* Target = Renderer.DrawWidget(SlateWidget, DrawSize);
		FImage Pixels;
		if (!TestNotNull(TEXT("Offscreen render target"), Target)
			|| !TestTrue(TEXT("Slate pixels were read back"), FImageUtils::GetRenderTargetImage(Target, Pixels)))
			return false;
		const FString Path = PreviewDirectory / (bHeld ? TEXT("held.png") : TEXT("compact.png"));
		if (!TestTrue(TEXT("Saved minimap preview as PNG"), FImageUtils::SaveImageByExtension(*Path, Pixels)))
			return false;

		const FAnchorData FrameLayout = Widget->FrameSlot->GetLayout();
		const FVector2D FrameSize(FrameLayout.Offsets.Right, FrameLayout.Offsets.Bottom);
		const FVector2D FrameOrigin = FrameLayout.Anchors.Minimum * DrawSize - FrameLayout.Alignment * FrameSize
			+ FVector2D(FrameLayout.Offsets.Left, FrameLayout.Offsets.Top);
		const int32 Left = FMath::RoundToInt(FrameOrigin.X);
		const int32 MidY = FMath::RoundToInt(FrameOrigin.Y + FrameSize.Y * .5);
		const FIntPoint RimPixel(Left + 1, MidY);
		const FIntPoint FillPixel(Left + 5, MidY);
		const FIntPoint BackdropPixel(Left + 15, MidY);
		const FIntRect PixelBounds(0, 0, Pixels.SizeX, Pixels.SizeY);
		if (!TestTrue(TEXT("Frame samples are inside the rendered viewport"),
			PixelBounds.Contains(RimPixel) && PixelBounds.Contains(FillPixel) && PixelBounds.Contains(BackdropPixel)))
			return false;

		const TCHAR* State = bHeld ? TEXT("Held") : TEXT("Compact");
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
				State, int32(Frame->Background.GetDrawType()), *GetPathNameSafe(BrushResource),
				*GetNameSafe(BrushResource ? BrushResource->GetClass() : nullptr),
				SlateBrush ? int32(SlateBrush->GetDrawType()) : -1, *GetPathNameSafe(SlateResource),
				Frame->GetBrushColor().A, Frame->GetContentColorAndOpacity().A,
				*FrameGeometry.GetRenderBoundingRect().ToString(), PaintedSize.X, PaintedSize.Y));
		}
		const float RimAlpha = Pixels.GetOnePixelLinear(RimPixel.X, RimPixel.Y).A;
		const float FillAlpha = Pixels.GetOnePixelLinear(FillPixel.X, FillPixel.Y).A;
		AddInfo(FString::Printf(TEXT("%s frame rim alpha %.3f at (%d,%d), padding alpha %.3f at (%d,%d)"),
			State, RimAlpha, RimPixel.X, RimPixel.Y, FillAlpha, FillPixel.X, FillPixel.Y));
		TestTrue(FString::Printf(TEXT("%s metallic rim is visible"), State), RimAlpha >= .25f);
		TestTrue(FString::Printf(TEXT("%s frame padding has translucent fill"), State), FillAlpha >= .04f && FillAlpha <= .20f);

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
			State, BackdropAlpha, BackdropPixel.X, BackdropPixel.Y));
		TestTrue(FString::Printf(TEXT("%s empty map has a stronger translucent backing than the frame padding"), State),
			BackdropAlpha > FillAlpha + .12f && BackdropAlpha < .50f);
	}
	return true;
}

#endif
