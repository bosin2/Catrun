#include "CatrunMinimapWidget.h"
#include "UI/CatrunHUDStyle.h"
#include "UI/CatrunMinimapMarkerWidget.h"
#include "Brushes/SlateRoundedBoxBrush.h"

#include "Camera/PlayerCameraManager.h"
#include "Components/Border.h"
#include "Components/BoxComponent.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/Image.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/Console.h"
#include "Engine/GameInstance.h"
#include "Engine/GameViewportClient.h"
#include "Engine/LocalPlayer.h"
#include "Engine/Texture2D.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Framework/Application/IInputProcessor.h"
#include "Framework/Application/SlateApplication.h"
#include "Framework/Application/SlateUser.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "Interaction/CatrunStatuePuzzle.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "LevelFlow/CatrunPlayHUD.h"
#include "Math/InverseRotationMatrix.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Monster/CatrunArmor.h"
#include "Monster/CatrunCandle.h"
#include "SceneView.h"
#include "Settings/CatrunSettingsSubsystem.h"
#include "Sound/CatrunDoor.h"
#include "Sound/CatrunNoBellZone.h"
#include "Slate/SceneViewport.h"
#include "Slate/SObjectWidget.h"
#include "Widgets/SViewport.h"

namespace
{
	constexpr float MarkerRefreshSeconds = .1f;
	constexpr float DefaultHoldTransitionSeconds = .18f;
	constexpr double MaxHeldWorldPixelScale = .90;
	const FVector2D MapSurfaceCenter(.5, .5);
	const FName ExitTag(TEXT("CatrunMapExit"));
	const FName HoleTag(TEXT("CatrunMapCatHole"));
	const FName FixedOpeningTag(TEXT("CatrunMapFixedOpening"));

	UGameViewportClient* GetViewportClient(const APlayerController* Controller)
	{
		const ULocalPlayer* LocalPlayer = Controller ? Controller->GetLocalPlayer() : nullptr;
		return LocalPlayer ? LocalPlayer->ViewportClient.Get() : nullptr;
	}

	bool GetCameraProjection(const APlayerController& Controller, FSceneViewport& Viewport, FSceneViewProjectionData& OutView)
	{
		const ULocalPlayer* LocalPlayer = Controller.GetLocalPlayer();
		const APlayerCameraManager* Camera = Controller.PlayerCameraManager;
		if (!LocalPlayer || !Camera)
			return false;

		const FIntPoint ViewportSize = Viewport.GetSizeXY();
		const FIntRect Rect(0, 0, FMath::TruncToInt(LocalPlayer->Size.X * ViewportSize.X),
			FMath::TruncToInt(LocalPlayer->Size.Y * ViewportSize.Y));
		FMinimalViewInfo View = Camera->GetCameraCacheView();
		if (Rect.Width() <= 0 || Rect.Height() <= 0 || View.Location.ContainsNaN() || View.Rotation.ContainsNaN()
			|| !FMath::IsFinite(View.AspectRatio) || View.AspectRatio <= 0.
			|| (View.ProjectionMode == ECameraProjectionMode::Orthographic
				&& (!FMath::IsFinite(View.OrthoWidth) || View.OrthoWidth <= 0.))
			|| (View.ProjectionMode == ECameraProjectionMode::Perspective
				&& (!FMath::IsFinite(View.FOV) || View.FOV <= 0. || View.FOV >= 180.)))
			return false;

		// Match the renderer's aspect/axis constraints without invoking view extensions from a widget tick.
		OutView.ViewOrigin = View.Location;
		OutView.ViewRotationMatrix = FInverseRotationMatrix(View.Rotation) * FMatrix(
			FPlane(0, 0, 1, 0), FPlane(1, 0, 0, 0), FPlane(0, 1, 0, 0), FPlane(0, 0, 0, 1));
		OutView.SetViewRectangle(Rect);
		FMinimalViewInfo::CalculateProjectionMatrixGivenView(View, LocalPlayer->AspectRatioAxisConstraint, &Viewport, OutView);
		return true;
	}
}

// Tab navigates away from SViewport during key-down, before the minimap's next layout tick.
class FCatrunMinimapTabInput final : public IInputProcessor
{
public:
	explicit FCatrunMinimapTabInput(ACatrunMinimapPresenter* InPresenter) : Presenter(InPresenter) {}

	virtual void Tick(float, FSlateApplication&, TSharedRef<ICursor>) override {}

	virtual bool HandleKeyDownEvent(FSlateApplication& Slate, const FKeyEvent& Event) override
	{
		if (Event.GetKey() != EKeys::Tab || Event.IsShiftDown() || Event.IsControlDown() || Event.IsAltDown() || Event.IsCommandDown())
			return false;
		const auto* Map = Presenter.Get();
		const auto* PC = Map ? Map->OwningController.Get() : nullptr;
		if (!PC || !Map->CanUseMinimap(PC) || !OwnsGameplayFocus(Slate, PC, Event.GetUserIndex()))
			return false;
		if (!Event.IsRepeat())
			HeldUser = Event.GetUserIndex();
		return true;
	}

	virtual bool HandleKeyUpEvent(FSlateApplication&, const FKeyEvent& Event) override
	{
		if (Event.GetKey() != EKeys::Tab || HeldUser != int32(Event.GetUserIndex()))
			return false;
		Cancel();
		return true;
	}

	void OnFocusChanging(const FFocusEvent& Event, const FWeakWidgetPath&, const TSharedPtr<SWidget>& Previous,
		const FWidgetPath&, const TSharedPtr<SWidget>& Next)
	{
		if (HeldUser == int32(Event.GetUser()) && Previous != Next)
			Cancel();
	}

	void OnActivationChanged(bool bActive) { if (!bActive) Cancel(); }
	void Cancel() { HeldUser = INDEX_NONE; }

	bool IsHeld(const APlayerController* PC, bool bGameplayAllowed)
	{
		if (HeldUser != INDEX_NONE && (!bGameplayAllowed || !PC || !FSlateApplication::IsInitialized()
			|| !OwnsGameplayFocus(FSlateApplication::Get(), PC, HeldUser)))
			Cancel();
		return HeldUser != INDEX_NONE;
	}

private:
	static bool OwnsGameplayFocus(FSlateApplication& Slate, const APlayerController* PC, uint32 Index)
	{
		const ULocalPlayer* LocalPlayer = PC->GetLocalPlayer();
		const auto User = LocalPlayer ? LocalPlayer->GetSlateUser() : nullptr;
		UGameViewportClient* Viewport = GetViewportClient(PC);
		if (!User || int32(Index) != User->GetUserIndex() || int32(Index) != Slate.GetUserIndexForKeyboard()
			|| !Slate.IsActive() || !Viewport || Viewport->IgnoreInput()
			|| (Viewport->ViewportConsole && Viewport->ViewportConsole->ConsoleActive()))
			return false;
		const auto Focus = Slate.GetUserFocusedWidget(Index);
		const auto Window = Slate.GetActiveTopLevelWindow();
		if (!Focus || (Window && User->GetWeakFocusPath().Window.Pin() != Window))
			return false;
		if (Focus == Viewport->GetGameViewportWidget())
			return true;
		// A focused passive play HUD still belongs to gameplay. Its buttons and other UI own their navigation.
		if (Focus->GetWidgetClass().GetWidgetType() != SObjectWidget::StaticWidgetClass().GetWidgetType())
			return false;
		const auto* HUD = Cast<UCatrunPlayHUD>(StaticCastSharedPtr<SObjectWidget>(Focus)->GetWidgetObject());
		return HUD && !HUD->bMenuOpen && HUD->GetOwningPlayer() == PC && HUD->IsInViewport();
	}

	TWeakObjectPtr<ACatrunMinimapPresenter> Presenter;
	int32 HeldUser = INDEX_NONE;
};

bool CatrunMinimap::Project(const FVector2D& WorldXY, const FVector2D& Center, const FVector2D& Size,
	double YawDegrees, FVector2D& OutUV)
{
	if (WorldXY.ContainsNaN() || Center.ContainsNaN() || Size.ContainsNaN() || Size.X <= 0. || Size.Y <= 0.
		|| !FMath::IsFinite(YawDegrees))
		return false;

	double SinYaw, CosYaw;
	FMath::SinCos(&SinYaw, &CosYaw, FMath::DegreesToRadians(YawDegrees));
	const FVector2D Delta = WorldXY - Center;
	const double U = .5 + FVector2D::DotProduct(Delta, FVector2D(-SinYaw, CosYaw)) / Size.X;
	const double V = .5 - FVector2D::DotProduct(Delta, FVector2D(CosYaw, SinYaw)) / Size.Y;
	const FVector2D UV(U, V);
	constexpr double EdgeTolerance = UE_DOUBLE_SMALL_NUMBER;
	if (UV.ContainsNaN() || U < -EdgeTolerance || U > 1. + EdgeTolerance || V < -EdgeTolerance || V > 1. + EdgeTolerance)
		return false;

	OutUV = FVector2D(FMath::Clamp(U, 0., 1.), FMath::Clamp(V, 0., 1.));
	return true;
}

bool CatrunMinimap::FitCameraProjection(const FVector2D& CaptureSize, double CaptureYawDegrees,
	const FRotator& CameraRotation, FSlateRenderTransform& OutTransform)
{
	if (CaptureSize.ContainsNaN() || CaptureSize.X <= 0. || CaptureSize.Y <= 0.
		|| !FMath::IsFinite(CaptureYawDegrees) || CameraRotation.ContainsNaN())
		return false;

	const FRotationMatrix CameraBasis(CameraRotation);
	// A horizontal view can occur before the gameplay camera is ready. Keep the last usable transform.
	if (FMath::Abs(CameraBasis.GetUnitAxis(EAxis::X).Z) <= UE_DOUBLE_KINDA_SMALL_NUMBER)
		return false;

	double SinYaw, CosYaw;
	FMath::SinCos(&SinYaw, &CosYaw, FMath::DegreesToRadians(CaptureYawDegrees));
	const FVector CameraRight = CameraBasis.GetUnitAxis(EAxis::Y);
	const FVector CameraDown = -CameraBasis.GetUnitAxis(EAxis::Z);
	const auto ProjectAxis = [&](const FVector& Axis)
	{
		return FVector2D(FVector::DotProduct(Axis, CameraRight), FVector::DotProduct(Axis, CameraDown));
	};
	const FVector2D CaptureAspect = CaptureSize / FMath::Max(CaptureSize.X, CaptureSize.Y);
	const FVector2D ImageRight = ProjectAxis(FVector(-SinYaw, CosYaw, 0.)) * CaptureAspect.X;
	const FVector2D ImageDown = ProjectAxis(FVector(-CosYaw, -SinYaw, 0.)) * CaptureAspect.Y;
	// The two projected edges give the complete footprint bounds. Fit both with one scale.
	const FVector2D Span = ImageRight.GetAbs() + ImageDown.GetAbs();
	const double Fit = 1. / FMath::Max(Span.X, Span.Y);
	OutTransform = FSlateRenderTransform(FMatrix2x2(static_cast<float>(ImageRight.X * Fit),
		static_cast<float>(ImageRight.Y * Fit), static_cast<float>(ImageDown.X * Fit),
		static_cast<float>(ImageDown.Y * Fit)));
	return true;
}

FVector2D CatrunMinimap::ToDisplayUV(const FVector2D& CaptureUV, const FSlateRenderTransform& Transform)
{
	return TransformPoint(Transform, CaptureUV - MapSurfaceCenter) + MapSurfaceCenter;
}

bool CatrunMinimap::MakeLocalProjection(const FVector2D& CaptureCenter, const FVector2D& CaptureSize,
	double CaptureYawDegrees, const FVector& PlayerLocation, const FSceneViewProjectionData& View,
	double Coverage, FSlateRenderTransform& OutTransform)
{
	const FIntRect& Rect = View.GetConstrainedViewRect();
	const FMatrix ViewProjection = View.ViewRotationMatrix * View.ProjectionMatrix;
	const double Determinant = ViewProjection.Determinant();
	if (CaptureCenter.ContainsNaN() || CaptureSize.ContainsNaN() || CaptureSize.X <= 0. || CaptureSize.Y <= 0.
		|| !FMath::IsFinite(CaptureYawDegrees) || PlayerLocation.ContainsNaN() || View.ViewOrigin.ContainsNaN()
		|| !View.IsValidViewRectangle() || !FMath::IsFinite(Determinant) || Determinant == 0.
		|| !FMath::IsFinite(Coverage) || Coverage < 1.)
		return false;

	const FVector Right = View.ViewRotationMatrix.GetColumn(0);
	const FVector Down = -View.ViewRotationMatrix.GetColumn(1);
	const auto ProjectAxis = [&](const FVector& Axis)
	{
		return FVector2D(FVector::DotProduct(Axis, Right), FVector::DotProduct(Axis, Down));
	};

	// Unproject the four actual view corners onto the cat's horizontal plane, relative to its position.
	// This also accounts for perspective foreshortening and off-center camera framing.
	const FMatrix InverseViewProjection = ViewProjection.Inverse();
	const FVector CameraOffset = View.ViewOrigin - PlayerLocation;
	double HalfSide = 0.;
	for (const FIntPoint& Corner : { Rect.Min, FIntPoint(Rect.Max.X, Rect.Min.Y), Rect.Max, FIntPoint(Rect.Min.X, Rect.Max.Y) })
	{
		FVector Origin, Direction;
		FSceneView::DeprojectScreenToWorld(FVector2D(Corner.X, Corner.Y), Rect, InverseViewProjection, Origin, Direction);
		if (FMath::Abs(Direction.Z) <= UE_DOUBLE_KINDA_SMALL_NUMBER)
			return false;
		Origin += CameraOffset;
		const double Distance = -Origin.Z / Direction.Z;
		if (!FMath::IsFinite(Distance) || (View.IsPerspectiveProjection() && Distance <= 0.))
			return false;
		const FVector2D GroundCorner = ProjectAxis(Origin + Direction * Distance);
		if (GroundCorner.ContainsNaN())
			return false;
		HalfSide = FMath::Max(HalfSide, GroundCorner.GetAbsMax());
	}
	const double Side = 2. * HalfSide * Coverage;
	if (!FMath::IsFinite(Side) || Side <= UE_DOUBLE_KINDA_SMALL_NUMBER)
		return false;

	double SinYaw, CosYaw;
	FMath::SinCos(&SinYaw, &CosYaw, FMath::DegreesToRadians(CaptureYawDegrees));
	const FVector2f ImageRight(ProjectAxis(FVector(-SinYaw, CosYaw, 0.)) * (CaptureSize.X / Side));
	const FVector2f ImageDown(ProjectAxis(FVector(-CosYaw, -SinYaw, 0.)) * (CaptureSize.Y / Side));
	const FVector2f Translation(ProjectAxis(FVector(CaptureCenter.X - PlayerLocation.X, CaptureCenter.Y - PlayerLocation.Y, 0.)) / Side);
	if (ImageRight.ContainsNaN() || ImageDown.ContainsNaN() || Translation.ContainsNaN())
		return false;
	OutTransform = FSlateRenderTransform(FMatrix2x2(ImageRight.X, ImageRight.Y, ImageDown.X, ImageDown.Y), Translation);
	return true;
}

bool CatrunMinimap::TryGetDisplayUV(const FVector2D& CaptureUV, const FSlateRenderTransform& Transform, FVector2D& OutUV)
{
	const FVector2D UV = ToDisplayUV(CaptureUV, Transform);
	if (UV.ContainsNaN() || UV.X < 0. || UV.X > 1. || UV.Y < 0. || UV.Y > 1.)
		return false;
	OutUV = UV;
	return true;
}

FSlateRenderTransform CatrunMinimap::ToImageTransform(const FSlateRenderTransform& Transform, const FVector2D& LocalSize)
{
	if (LocalSize.ContainsNaN() || LocalSize.X <= 0. || LocalSize.Y <= 0.)
		return FSlateRenderTransform();

	// Slate applies the matrix around the image's center pivot in local units, not UVs.
	const FVector2f PixelX(TransformVector(Transform, FVector2D(1. / LocalSize.X, 0.)) * LocalSize);
	const FVector2f PixelY(TransformVector(Transform, FVector2D(0., 1. / LocalSize.Y)) * LocalSize);
	const FVector2f Translation(Transform.GetTranslation() * LocalSize);
	return FSlateRenderTransform(FMatrix2x2(PixelX.X, PixelX.Y, PixelY.X, PixelY.Y), Translation);
}

bool UCatrunMinimapWidget::InitializeMap(ACatrunMinimapPresenter& InPresenter)
{
	// Migrate all saved panels to the same legible glyphs without rewriting map packages.
	PlayerMarkerClass = UCatrunMinimapCatMarker::StaticClass();
	ArmorMarkerClass = UCatrunMinimapArmorMarker::StaticClass();
	CandleMarkerClass = UCatrunMinimapCandleMarker::StaticClass();
	if (!InPresenter.BackgroundTexture || !MapBackground || !MarkerLayer || !PlayerMarkerClass
		|| (!EnemyMarkerClass && (!ArmorMarkerClass || !CandleMarkerClass))
		|| !CatrunMinimap::FitCameraProjection(InPresenter.MapSize, InPresenter.CaptureYawDegrees,
			FRotator(-90., InPresenter.CaptureYawDegrees, 0.), FallbackProjection))
		return false;

	Presenter = &InPresenter;
	MapProjection = FallbackProjection;
	// Older panels have the same frame in the tree without the optional binding.
	UWidget* Frame = MinimapFrame ? MinimapFrame.Get() : GetWidgetFromName(TEXT("MinimapFrame"));
	FrameSlot = Frame ? Cast<UCanvasPanelSlot>(Frame->Slot) : nullptr;
	if (UBorder* Border = Cast<UBorder>(Frame))
	{
		FSlateRoundedBoxBrush FrameBrush(CatrunHUDStyle::Ink.CopyWithNewOpacity(.42f),
			4.f, CatrunHUDStyle::Rim.CopyWithNewOpacity(.55f), 1.f);
		// Rounded outlines ignore inherited opacity by default. Without this the rim stays on screen while the map is hidden.
		FrameBrush.OutlineSettings.bUseBrushTransparency = true;
		Border->SetBrush(FrameBrush);
		Border->SetBrushColor(FLinearColor::White);
	}
	if (UBorder* Backdrop = Cast<UBorder>(GetWidgetFromName(TEXT("MinimapBackdrop"))))
		Backdrop->SetBrushColor(CatrunHUDStyle::Ink.CopyWithNewOpacity(.08f));
	MapBackground->SetRenderOpacity(.72f);
	if (FrameSlot)
		CompactFrameLayout = FrameSlot->GetLayout();
	if (UPanelWidget* MapSurface = MapBackground->GetParent(); MapSurface && MapSurface == MarkerLayer->GetParent())
		MapSurface->SetClipping(EWidgetClipping::ClipToBounds);
	SetIsFocusable(false);
	SetVisibility(ESlateVisibility::HitTestInvisible);
	MapBackground->SetBrushFromTexture(InPresenter.BackgroundTexture, false);
	if (FloorplanMaterial)
	{
		MapBackground->SetBrushFromMaterial(FloorplanMaterial);
		if (auto* Material = MapBackground->GetDynamicMaterial())
		{
			Material->SetTextureParameterValue(TEXT("Floorplan"), InPresenter.BackgroundTexture);
			Material->SetVectorParameterValue(TEXT("WarmGray"), CatrunHUDStyle::Parchment);
		}
	}
	MapBackground->SetRenderTransformPivot(MapSurfaceCenter);
	PlayerMarker = AddMarker(PlayerMarkerClass, 1);
	return PlayerMarker != nullptr;
}

void UCatrunMinimapWidget::NativeTick(const FGeometry& Geometry, float DeltaSeconds)
{
	Super::NativeTick(Geometry, DeltaSeconds);
	const ACatrunMinimapPresenter* Map = Presenter.Get();
	const APlayerController* Controller = GetOwningPlayer();
	UGameViewportClient* ViewportClient = GetViewportClient(Controller);
	FSceneViewport* Viewport = ViewportClient ? ViewportClient->GetGameViewport() : nullptr;
	const bool bShow = Map && Map->CanUseMinimap(Controller);
	const bool bHeld = Map && Map->TabInput && Map->TabInput->IsHeld(Controller, bShow);
	if (bShow)
		AdvanceHoldAnimation(bHeld, DeltaSeconds);
	else
		HoldProgress = 0.f;
	const FVector2D ViewportSize = Geometry.GetLocalSize();
	UpdateLayout(ViewportSize);
	// Opacity leaves this widget ticking while game timers are paused.
	SetRenderOpacity(bShow ? 1.f : 0.f);
	if (!bShow)
		return;

	MapProjection = FallbackProjection;
	const APawn* Pawn = Controller->GetPawn();
	FSceneViewProjectionData View;
	const bool bLocalProjection = IsValid(Pawn) && Viewport
		&& GetCameraProjection(*Controller, *Viewport, View)
		&& CatrunMinimap::MakeLocalProjection(Map->MapCenter, Map->MapSize, Map->CaptureYawDegrees,
			Pawn->GetActorLocation(), View, GetNeighborhoodCoverage(ViewportSize), MapProjection);
	ApplyImageProjection();

	FVector2D PlayerUV = MapSurfaceCenter;
	if (bLocalProjection)
		UpdateMarker(*PlayerMarker, &PlayerUV);
	else
	{
		FVector2D CaptureUV;
		const bool bPlayerVisible = Map->ProjectActor(Pawn, CaptureUV)
			&& CatrunMinimap::TryGetDisplayUV(CaptureUV, MapProjection, PlayerUV);
		UpdateMarker(*PlayerMarker, bPlayerVisible ? &PlayerUV : nullptr);
	}
	UpdateEnemyMarkers(ECatrunMinimapEnemyKind::Armor, Map->ArmorPositions);
	UpdateEnemyMarkers(ECatrunMinimapEnemyKind::Candle, Map->CandlePositions);
	for (const auto& Style : LandmarkMarkerClasses)
	{
		const TArray<FVector2D>* Positions = Map->LandmarkPositions.Find(Style.Key);
		const TConstArrayView<FVector2D> ViewPositions = Positions ? MakeArrayView(*Positions) : TConstArrayView<FVector2D>();
		UpdateMarkerPool(LandmarkPools.FindOrAdd(Style.Key).Slots, Style.Value, ViewPositions,
			Style.Key == ECatrunMapLandmark::Exit ? -1 : -2);
	}
}

void UCatrunMinimapWidget::AdvanceHoldAnimation(bool bHeld, float DeltaSeconds)
{
	const float Target = bHeld ? 1.f : 0.f;
	const float Duration = FMath::IsFinite(HoldTransitionDuration)
		? FMath::Clamp(HoldTransitionDuration, 0.f, 1.f) : DefaultHoldTransitionSeconds;
	HoldProgress = Duration > UE_SMALL_NUMBER
		? FMath::FInterpConstantTo(HoldProgress, Target, DeltaSeconds, 1.f / Duration) : Target;
}

double UCatrunMinimapWidget::GetHoldBlend() const
{
	return FMath::SmoothStep(0., 1., double(HoldProgress));
}

FAnchorData UCatrunMinimapWidget::GetFrameLayout(const FAnchorData& CompactLayout, const FVector2D& ViewportSize,
	double HoldBlend, float InHoldSizeMultiplier)
{
	FAnchorData Layout = CompactLayout;
	// Stretched CanvasPanel slots use these offsets as margins rather than dimensions.
	if (Layout.Anchors.Minimum != Layout.Anchors.Maximum || Layout.Offsets.Right <= 0.f || Layout.Offsets.Bottom <= 0.f)
		return Layout;
	double HeldScale = FMath::IsFinite(InHoldSizeMultiplier) ? FMath::Max(1.f, InHoldSizeMultiplier) : 1.;
	if (!ViewportSize.ContainsNaN() && ViewportSize.X > 0. && ViewportSize.Y > 0.)
	{
		const auto Available = [](double Extent, double Anchor, double Offset, double Alignment)
		{
			const double Pivot = Extent * Anchor + Offset;
			const double Start = Alignment > 0. ? Pivot / Alignment : Extent;
			const double End = Alignment < 1. ? (Extent - Pivot) / (1. - Alignment) : Extent;
			return FMath::Max(0., FMath::Min(Start, End));
		};
		const double Width = Available(ViewportSize.X, Layout.Anchors.Minimum.X, Layout.Offsets.Left, Layout.Alignment.X);
		const double Height = Available(ViewportSize.Y, Layout.Anchors.Minimum.Y, Layout.Offsets.Top, Layout.Alignment.Y);
		HeldScale = FMath::Min3(HeldScale, Width / Layout.Offsets.Right, Height / Layout.Offsets.Bottom);
	}
	const double Scale = FMath::Lerp(FMath::Min(1., HeldScale), HeldScale, HoldBlend);
	Layout.Offsets.Right *= Scale;
	Layout.Offsets.Bottom *= Scale;
	return Layout;
}

void UCatrunMinimapWidget::UpdateLayout(const FVector2D& ViewportSize)
{
	if (!FrameSlot)
		return;

	const FAnchorData Layout = GetFrameLayout(CompactFrameLayout, ViewportSize, GetHoldBlend(), HoldSizeMultiplier);
	if (Layout != FrameSlot->GetLayout())
		FrameSlot->SetLayout(Layout);
}

FVector2D UCatrunMinimapWidget::GetFrameInnerSize(const FAnchorData& Layout) const
{
	FVector2D Size(Layout.Offsets.Right, Layout.Offsets.Bottom);
	if (const UBorder* Border = Cast<UBorder>(FrameSlot->GetContent()))
		Size -= FVector2D(Border->GetPadding().GetDesiredSize2f());
	return Size;
}

double UCatrunMinimapWidget::GetNeighborhoodCoverage(const FVector2D& ViewportSize) const
{
	const double Blend = GetHoldBlend();
	if (Blend == 0.)
		return NeighborhoodCoverage;

	double PixelGrowth = 1.;
	if (FrameSlot && CompactFrameLayout.Anchors.Minimum == CompactFrameLayout.Anchors.Maximum)
	{
		const FVector2D CompactSize = GetFrameInnerSize(GetFrameLayout(CompactFrameLayout, ViewportSize, 0., HoldSizeMultiplier));
		if (CompactSize.GetMin() > 0.)
		{
			const FVector2D HeldSize = GetFrameInnerSize(GetFrameLayout(CompactFrameLayout, ViewportSize, 1., HoldSizeMultiplier));
			PixelGrowth = (HeldSize / CompactSize).GetMax();
		}
	}
	const double Requested = FMath::IsFinite(HoldCoverageMultiplier) ? HoldCoverageMultiplier : 1.;
	const double HeldMultiplier = FMath::Max(Requested, PixelGrowth / MaxHeldWorldPixelScale);
	return NeighborhoodCoverage * FMath::Lerp(1., HeldMultiplier, Blend);
}

void UCatrunMinimapWidget::ApplyImageProjection() const
{
	if (const TSharedPtr<SWidget> Image = MapBackground->GetCachedWidget())
	{
		FVector2D LocalSize = MapBackground->GetCachedGeometry().GetLocalSize();
		if (FrameSlot && CompactFrameLayout.Anchors.Minimum == CompactFrameLayout.Anchors.Maximum)
		{
			// Match the new canvas layout in the same paint that changes the held size.
			LocalSize = GetFrameInnerSize(FrameSlot->GetLayout());
		}
		const FSlateRenderTransform ImageTransform = CatrunMinimap::ToImageTransform(MapProjection, LocalSize);
		const auto& CurrentTransform = Image->GetRenderTransform();
		if (!CurrentTransform.IsSet() || CurrentTransform.GetValue() != ImageTransform)
			Image->SetRenderTransform(ImageTransform);
	}
}

UCanvasPanelSlot* UCatrunMinimapWidget::AddMarker(TSubclassOf<UUserWidget> MarkerClass, int32 ZOrder)
{
	UUserWidget* Marker = CreateWidget<UUserWidget>(this, MarkerClass);
	if (!Marker)
		return nullptr;

	Marker->SetVisibility(ESlateVisibility::Collapsed);
	UCanvasPanelSlot* MarkerSlot = MarkerLayer->AddChildToCanvas(Marker);
	if (MarkerSlot)
	{
		MarkerSlot->SetAlignment(FVector2D(.5, .5));
		MarkerSlot->SetPosition(FVector2D::ZeroVector);
		MarkerSlot->SetAutoSize(true);
		MarkerSlot->SetZOrder(ZOrder);
	}
	return MarkerSlot;
}

void UCatrunMinimapWidget::UpdateMarker(UCanvasPanelSlot& MarkerSlot, const FVector2D* DisplayUV)
{
	UWidget* Marker = MarkerSlot.GetContent();
	if (!Marker)
		return;

	const ESlateVisibility MarkerVisibility = DisplayUV ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed;
	if (DisplayUV)
	{
		const FAnchors Anchors(static_cast<float>(DisplayUV->X), static_cast<float>(DisplayUV->Y));
		if (MarkerSlot.GetAnchors() != Anchors)
			MarkerSlot.SetAnchors(Anchors);
		if (const TSharedPtr<SWidget> SlateMarker = Marker->GetCachedWidget())
		{
			// Scale the paint about the authored pivot, keeping the Canvas slot centered and auto-sized.
			const double HeldMultiplier = FMath::IsFinite(HoldMarkerSizeMultiplier)
				? FMath::Clamp(HoldMarkerSizeMultiplier, .01f, 1.f) : 1.f;
			FWidgetTransform Transform = Marker->GetRenderTransform();
			Transform.Scale *= FMath::Lerp(1., HeldMultiplier, GetHoldBlend());
			const TOptional<FSlateRenderTransform> MarkerRenderTransform = Transform.IsIdentity()
				? TOptional<FSlateRenderTransform>() : TOptional<FSlateRenderTransform>(Transform.ToSlateRenderTransform());
			if (SlateMarker->GetRenderTransform() != MarkerRenderTransform)
				SlateMarker->SetRenderTransform(MarkerRenderTransform);
		}
	}
	if (Marker->GetVisibility() != MarkerVisibility)
		Marker->SetVisibility(MarkerVisibility);
}

void UCatrunMinimapWidget::UpdateEnemyMarkers(ECatrunMinimapEnemyKind Kind, TConstArrayView<FVector2D> Positions)
{
	const bool bArmor = Kind == ECatrunMinimapEnemyKind::Armor;
	auto& Markers = bArmor ? ArmorMarkers : CandleMarkers;
	TSubclassOf<UUserWidget> MarkerClass = bArmor ? ArmorMarkerClass : CandleMarkerClass;
	if (!MarkerClass)
		MarkerClass = EnemyMarkerClass;
	UpdateMarkerPool(Markers, MarkerClass, Positions, 0);
}

void UCatrunMinimapWidget::UpdateMarkerPool(TArray<TObjectPtr<UCanvasPanelSlot>>& Markers,
	TSubclassOf<UUserWidget> MarkerClass, TConstArrayView<FVector2D> Positions, int32 ZOrder)
{
	int32 Index = 0;
	for (const FVector2D& Position : Positions)
	{
		FVector2D DisplayUV;
		if (!CatrunMinimap::TryGetDisplayUV(Position, MapProjection, DisplayUV))
			continue;
		if (Index == Markers.Num())
		{
			UCanvasPanelSlot* MarkerSlot = MarkerClass ? AddMarker(MarkerClass, ZOrder) : nullptr;
			if (!MarkerSlot)
				break;
			Markers.Add(MarkerSlot);
		}
		UpdateMarker(*Markers[Index++], &DisplayUV);
	}
	for (; Index < Markers.Num(); ++Index)
		UpdateMarker(*Markers[Index], nullptr);
}

ACatrunMinimapPresenter::ACatrunMinimapPresenter()
{
	SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
	PrimaryActorTick.bCanEverTick = false;
}

void ACatrunMinimapPresenter::BeginPlay()
{
	Super::BeginPlay();
	UWorld* World = GetWorld();
	if (!World || !World->IsGameWorld() || World->GetNetMode() == NM_DedicatedServer)
		return;

	FVector2D UnusedUV;
	if (!WidgetClass || !BackgroundTexture || !CatrunMinimap::Project(MapCenter, MapCenter, MapSize, CaptureYawDegrees, UnusedUV))
	{
		UE_LOG(LogTemp, Warning, TEXT("Minimap presenter %s is missing a widget, map texture or valid capture bounds."), *GetPathName());
		return;
	}
	StartTracking(*World);
}

void ACatrunMinimapPresenter::StartTracking(UWorld& World)
{
	if (SpawnedHandle.IsValid())
		return;

	SpawnedHandle = World.AddOnActorSpawnedHandler(FOnActorSpawned::FDelegate::CreateUObject(this, &ThisClass::TrackActor));
	if (auto* Settings = World.GetSubsystem<UCatrunSettingsSubsystem>())
		Settings->OnSettingsOpened.AddUObject(this, &ThisClass::HideMinimap);
	for (TActorIterator<AActor> It(&World); It; ++It)
		TrackActor(*It);

	FTimerManagerTimerParameters TimerParameters;
	TimerParameters.bLoop = true;
	TimerParameters.bMaxOncePerFrame = true;
	World.GetTimerManager().SetTimer(UpdateTimer, this, &ThisClass::UpdateMinimap, MarkerRefreshSeconds, TimerParameters);
	UpdateMinimap();
}

void ACatrunMinimapPresenter::EndPlay(const EEndPlayReason::Type Reason)
{
	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().ClearTimer(UpdateTimer);
		World->RemoveOnActorSpawnedHandler(SpawnedHandle);
		if (auto* Settings = World->GetSubsystem<UCatrunSettingsSubsystem>())
			Settings->OnSettingsOpened.RemoveAll(this);
	}
	SpawnedHandle.Reset();
	for (const auto& Enemy : Enemies)
	{
		if (AActor* Actor = Enemy.Key.Get())
			Actor->OnDestroyed.RemoveDynamic(this, &ThisClass::UntrackActor);
	}
	for (const auto& Landmark : Landmarks)
		if (AActor* Actor = Landmark.Key.Get())
			Actor->OnDestroyed.RemoveDynamic(this, &ThisClass::UntrackActor);
	Enemies.Reset();
	Landmarks.Reset();
	LandmarkPositions.Reset();
	DetachWidget();
	Super::EndPlay(Reason);
}

void ACatrunMinimapPresenter::TrackActor(AActor* Actor)
{
	if (!IsValid(Actor) || Actor->IsActorBeingDestroyed() || Actor->GetWorld() != GetWorld())
		return;

	const bool bArmor = Actor->IsA<ACatrunArmor>();
	if (bArmor || Actor->IsA<ACatrunCandle>())
		Enemies.Add(Actor, bArmor ? ECatrunMinimapEnemyKind::Armor : ECatrunMinimapEnemyKind::Candle);
	else if (auto* Exit = Cast<ACatrunStageExit>(Actor))
		Landmarks.Add(Actor, Exit->Trigger.Get());
	else if (Actor->ActorHasTag(ExitTag))
	{
		if (auto* Trigger = Actor->FindComponentByClass<UBoxComponent>())
			Landmarks.Add(Actor, Trigger);
		else
			return;
	}
	else if (auto* Zone = Cast<ACatrunNoBellZone>(Actor); Zone && Zone->ActorHasTag(HoleTag))
		Landmarks.Add(Actor, Zone->Box.Get());
	else if (Actor->IsA<ACatrunDoor>() || Actor->IsA<ACatrunStatuePuzzle>() || Actor->ActorHasTag(FixedOpeningTag))
		Landmarks.Add(Actor, Actor->GetRootComponent());
	else
		return;

	Actor->OnDestroyed.AddUniqueDynamic(this, &ThisClass::UntrackActor);
}

void ACatrunMinimapPresenter::UntrackActor(AActor* Actor)
{
	Enemies.Remove(Actor);
	Landmarks.Remove(Actor);
}

void ACatrunMinimapPresenter::SampleLandmarks()
{
	for (auto& Bucket : LandmarkPositions)
		Bucket.Value.Reset();
	const auto Add = [this](ECatrunMapLandmark Kind, const FVector& Location)
	{
		FVector2D UV;
		if (CatrunMinimap::Project(FVector2D(Location), MapCenter, MapSize, CaptureYawDegrees, UV))
			LandmarkPositions.FindOrAdd(Kind).Add(UV);
	};
	for (const auto& Item : Landmarks)
	{
		AActor* Actor = Item.Key.Get();
		if (!Actor) continue;
		if (const auto* Door = Cast<ACatrunDoor>(Actor))
		{
			const auto Kind = Door->ActorHasTag(FixedOpeningTag) ? ECatrunMapLandmark::FixedOpening :
				(Door->IsOpen() ? ECatrunMapLandmark::OpenDoor : ECatrunMapLandmark::ClosedDoor);
			Add(Kind, Door->GetDoorwayCenter());
		}
		else if (const auto* Puzzle = Cast<ACatrunStatuePuzzle>(Actor))
		{
			for (const auto& Link : Puzzle->Links)
			{
				if (!IsValid(Link.Gate) || !Link.InitialGateBounds.IsValid) continue;
				// Reset can clear the solve latch before the physical bars rise through the floor.
				const bool bRecessed = Link.InitialGateBounds.Max.Z + Link.GateOffset
					<= Link.InitialGateBounds.Min.Z + Link.GateFloorOffset;
				Add(Link.bCompleted || bRecessed ? ECatrunMapLandmark::OpenDoor : ECatrunMapLandmark::ClosedDoor,
					Link.InitialGateBounds.GetCenter());
			}
		}
		else if (const auto* Anchor = Item.Value.Get())
		{
			const auto Kind = Actor->ActorHasTag(FixedOpeningTag) ? ECatrunMapLandmark::FixedOpening :
				(Actor->IsA<ACatrunNoBellZone>() ? ECatrunMapLandmark::CatHole : ECatrunMapLandmark::Exit);
			const auto* FrameMesh = Cast<UStaticMeshComponent>(Anchor);
			Add(Kind, FrameMesh ? FrameMesh->Bounds.Origin : Anchor->GetComponentLocation());
		}
	}
}

bool ACatrunMinimapPresenter::AttachWidget(APlayerController& Controller)
{
	UCatrunMinimapWidget* Widget = CreateWidget<UCatrunMinimapWidget>(&Controller, WidgetClass);
	if (Widget && Widget->InitializeMap(*this)
		&& Widget->AddToPlayerScreen() && Widget->IsInViewport())
	{
		MinimapWidget = Widget;
		OwningController = &Controller;
		if (FSlateApplication::IsInitialized())
		{
			auto& Slate = FSlateApplication::Get();
			TabInput = MakeShared<FCatrunMinimapTabInput>(this);
			Slate.RegisterInputPreProcessor(TabInput);
			Slate.OnFocusChanging().AddSP(TabInput.ToSharedRef(), &FCatrunMinimapTabInput::OnFocusChanging);
			Slate.OnApplicationActivationStateChanged().AddSP(TabInput.ToSharedRef(), &FCatrunMinimapTabInput::OnActivationChanged);
		}
		return true;
	}

	if (Widget)
		Widget->RemoveFromParent();
	UE_LOG(LogTemp, Warning, TEXT("Minimap presenter %s could not attach its configured widget."), *GetPathName());
	GetWorld()->GetTimerManager().ClearTimer(UpdateTimer);
	return false;
}

void ACatrunMinimapPresenter::DetachWidget()
{
	if (TabInput && FSlateApplication::IsInitialized())
	{
		auto& Slate = FSlateApplication::Get();
		Slate.OnApplicationActivationStateChanged().RemoveAll(TabInput.Get());
		Slate.OnFocusChanging().RemoveAll(TabInput.Get());
		Slate.UnregisterInputPreProcessor(TabInput);
	}
	TabInput.Reset();
	OwningController.Reset();
	ArmorPositions.Reset();
	CandlePositions.Reset();
	if (MinimapWidget)
	{
		MinimapWidget->RemoveFromParent();
		MinimapWidget = nullptr;
	}
}

void ACatrunMinimapPresenter::HideMinimap()
{
	if (!MinimapWidget)
		return;

	if (TabInput)
		TabInput->Cancel();
	MinimapWidget->HoldProgress = 0.f;
	MinimapWidget->UpdateLayout(MinimapWidget->GetCachedGeometry().GetLocalSize());
	MinimapWidget->SetRenderOpacity(0.f);
}

bool ACatrunMinimapPresenter::CanUseMinimap(const APlayerController* Controller) const
{
	const UWorld* World = GetWorld();
	if (!World || World->bIsTearingDown || World->IsPaused() || !IsValid(Controller) || Controller->GetWorld() != World
		|| UCatrunLevelFlowLibrary::ShouldHideGameplayHUD(this))
		return false;

	const auto* Settings = World->GetSubsystem<UCatrunSettingsSubsystem>();
	return !Settings || !Settings->GetCurrentSettingsWidget();
}

bool ACatrunMinimapPresenter::ProjectActor(const AActor* Actor, FVector2D& OutUV) const
{
	if (!IsValid(Actor) || Actor->GetWorld() != GetWorld())
		return false;

	const FVector Location = Actor->GetActorLocation();
	return CatrunMinimap::Project(FVector2D(Location.X, Location.Y), MapCenter, MapSize, CaptureYawDegrees, OutUV);
}

void ACatrunMinimapPresenter::UpdateMinimap()
{
	UWorld* World = GetWorld();
	const UGameInstance* GameInstance = World->GetGameInstance();
	APlayerController* Controller = GameInstance && World->GetGameViewport()
		? GameInstance->GetFirstLocalPlayerController(World) : nullptr;
	if (MinimapWidget && (Controller != OwningController.Get() || !MinimapWidget->IsInViewport()))
		DetachWidget();
	if (!Controller || Controller->GetWorld() != World || !Controller->GetLocalPlayer()
		|| (!MinimapWidget && !AttachWidget(*Controller)))
		return;

	if (!CanUseMinimap(Controller))
	{
		HideMinimap();
		return;
	}
	ArmorPositions.Reset();
	CandlePositions.Reset();
	FVector2D UV;
	SampleLandmarks();
	for (const auto& Enemy : Enemies)
	{
		if (ProjectActor(Enemy.Key.Get(), UV))
			(Enemy.Value == ECatrunMinimapEnemyKind::Armor ? ArmorPositions : CandlePositions).Add(UV);
	}
}
