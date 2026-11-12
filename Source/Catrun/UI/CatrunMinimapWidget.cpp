#include "CatrunMinimapWidget.h"

#include "Camera/PlayerCameraManager.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/Image.h"
#include "Components/InputComponent.h"
#include "Components/SceneComponent.h"
#include "Engine/GameInstance.h"
#include "Engine/Texture2D.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Interaction/CatrunBasketInteractionComponent.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "Math/RotationMatrix.h"
#include "Monster/CatrunArmor.h"
#include "Monster/CatrunCandle.h"
#include "Monster/CatrunRestartSubsystem.h"
#include "Settings/CatrunSettingsSubsystem.h"
#include "Widgets/SWidget.h"

namespace
{
	constexpr float MarkerRefreshSeconds = .1f;
	const FVector2D MapSurfaceCenter(.5, .5);
}

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

bool UCatrunMinimapWidget::InitializeMap(UTexture2D* Texture, const FVector2D& CaptureSize, double CaptureYawDegrees)
{
	if (!Texture || !MapBackground || !MarkerLayer || !PlayerMarkerClass
		|| (!EnemyMarkerClass && (!ArmorMarkerClass || !CandleMarkerClass))
		|| !CatrunMinimap::FitCameraProjection(CaptureSize, CaptureYawDegrees,
			FRotator(-90., CaptureYawDegrees, 0.), MapProjection))
		return false;

	// Older panels have the same frame in the tree without the optional binding.
	UWidget* Frame = MinimapFrame ? MinimapFrame.Get() : GetWidgetFromName(TEXT("MinimapFrame"));
	FrameSlot = Frame ? Cast<UCanvasPanelSlot>(Frame->Slot) : nullptr;
	if (FrameSlot)
		CompactFrameLayout = FrameSlot->GetLayout();
	SetIsFocusable(false);
	SetVisibility(ESlateVisibility::HitTestInvisible);
	MapBackground->SetBrushFromTexture(Texture, false);
	MapBackground->SetRenderTransformPivot(MapSurfaceCenter);
	PlayerMarker = AddMarker(PlayerMarkerClass, 1);
	return PlayerMarker != nullptr;
}

void UCatrunMinimapWidget::SetExpanded(bool bInExpanded)
{
	bExpanded = bInExpanded;
	UpdateLayout();
}

void UCatrunMinimapWidget::NativeTick(const FGeometry& Geometry, float DeltaSeconds)
{
	Super::NativeTick(Geometry, DeltaSeconds);
	const bool bHide = UCatrunLevelFlowLibrary::ShouldHideGameplayHUD(this);
	// A cheap view/lease check before painting avoids a flash between the 10 Hz marker updates.
	// Keep this widget alive; the presenter owns removal and normal visibility restoration.
	SetRenderOpacity(bHide ? 0.f : 1.f);
}

FAnchorData UCatrunMinimapWidget::GetFrameLayout(const FAnchorData& CompactLayout, const FVector2D& ViewportSize,
	bool bIsExpanded, float ExpandedViewportFraction, float ExpandedMaxSize)
{
	FAnchorData Layout = CompactLayout;
	const double ViewportSide = FMath::Min(ViewportSize.X, ViewportSize.Y);
	if (bIsExpanded)
	{
		const float Side = ViewportSide > 1.
			? FMath::Min(ExpandedMaxSize, static_cast<float>(ViewportSide * ExpandedViewportFraction))
			: ExpandedMaxSize;
		Layout.Anchors = FAnchors(.5f);
		Layout.Alignment = FVector2D(.5, .5);
		Layout.Offsets = FMargin(0.f, 0.f, Side, Side);
	}
	else if (ViewportSide > 1.)
	{
		const double AvailableWidth = ViewportSize.X - 2. * FMath::Abs(Layout.Offsets.Left);
		const double AvailableHeight = ViewportSize.Y - 2. * FMath::Abs(Layout.Offsets.Top);
		const float AvailableSide = static_cast<float>(FMath::Max(1., FMath::Min(AvailableWidth, AvailableHeight)));
		Layout.Offsets.Right = FMath::Min(Layout.Offsets.Right, AvailableSide);
		Layout.Offsets.Bottom = FMath::Min(Layout.Offsets.Bottom, AvailableSide);
	}
	return Layout;
}

void UCatrunMinimapWidget::UpdateLayout()
{
	if (!FrameSlot)
		return;

	const FAnchorData Layout = GetFrameLayout(CompactFrameLayout, GetCachedGeometry().GetLocalSize(), bExpanded,
		ExpandedMapViewportFraction, ExpandedMapMaxSize);
	if (Layout != FrameSlot->GetLayout())
		FrameSlot->SetLayout(Layout);
}

void UCatrunMinimapWidget::UpdateMapProjection(const FVector2D& CaptureSize, double CaptureYawDegrees,
	const APlayerController& Controller)
{
	if (const APlayerCameraManager* Camera = Controller.PlayerCameraManager)
		CatrunMinimap::FitCameraProjection(CaptureSize, CaptureYawDegrees, Camera->GetCameraRotation(), MapProjection);

	// The map image uses the same affine matrix as the marker positions. The marker layer stays in screen space.
	if (const TSharedPtr<SWidget> Image = MapBackground->GetCachedWidget())
	{
		const auto& CurrentTransform = Image->GetRenderTransform();
		if (!CurrentTransform.IsSet() || CurrentTransform.GetValue() != MapProjection)
			Image->SetRenderTransform(MapProjection);
	}
}

UCanvasPanelSlot* UCatrunMinimapWidget::AddMarker(TSubclassOf<UUserWidget> MarkerClass, int32 ZOrder)
{
	UUserWidget* Marker = CreateWidget<UUserWidget>(GetOwningPlayer(), MarkerClass);
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

void UCatrunMinimapWidget::UpdateMarker(UCanvasPanelSlot& MarkerSlot, const FVector2D* UV)
{
	const ESlateVisibility MarkerVisibility = UV ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed;
	if (UV)
	{
		const FVector2D DisplayUV = CatrunMinimap::ToDisplayUV(*UV, MapProjection);
		const FAnchors Anchors(static_cast<float>(DisplayUV.X), static_cast<float>(DisplayUV.Y));
		if (MarkerSlot.GetAnchors() != Anchors)
			MarkerSlot.SetAnchors(Anchors);
	}
	if (UWidget* Marker = MarkerSlot.GetContent(); Marker && Marker->GetVisibility() != MarkerVisibility)
		Marker->SetVisibility(MarkerVisibility);
}

void UCatrunMinimapWidget::UpdatePlayer(const FVector2D* UV)
{
	UpdateMarker(*PlayerMarker, UV);
}

void UCatrunMinimapWidget::UpdateEnemies(ECatrunMinimapEnemyKind Kind, TConstArrayView<FVector2D> Positions)
{
	const bool bArmor = Kind == ECatrunMinimapEnemyKind::Armor;
	auto& Markers = bArmor ? ArmorMarkers : CandleMarkers;
	TSubclassOf<UUserWidget> MarkerClass = bArmor ? ArmorMarkerClass : CandleMarkerClass;
	if (!MarkerClass)
		MarkerClass = EnemyMarkerClass;

	for (int32 Index = 0; Index < Positions.Num(); ++Index)
	{
		if (Index == Markers.Num())
		{
			UCanvasPanelSlot* MarkerSlot = AddMarker(MarkerClass, 0);
			if (!MarkerSlot)
				break;
			Markers.Add(MarkerSlot);
		}
		UpdateMarker(*Markers[Index], &Positions[Index]);
	}
	for (int32 Index = Positions.Num(); Index < Markers.Num(); ++Index)
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
	CreateInputComponent(UInputComponent::StaticClass());
	FInputKeyBinding& TabBinding = InputComponent->BindKey(EKeys::Tab, IE_Pressed, this, &ThisClass::ToggleMap);
	TabBinding.bConsumeInput = false;
	StartTracking(*World);
}

void ACatrunMinimapPresenter::StartTracking(UWorld& World)
{
	if (SpawnedHandle.IsValid())
		return;

	SpawnedHandle = World.AddOnActorSpawnedHandler(FOnActorSpawned::FDelegate::CreateUObject(this, &ThisClass::TrackEnemy));
	if (auto* Settings = World.GetSubsystem<UCatrunSettingsSubsystem>())
		Settings->OnSettingsOpened.AddUObject(this, &ThisClass::HideMinimap);
	for (TActorIterator<ACatrunArmor> Armor(&World); Armor; ++Armor)
		TrackEnemy(*Armor);
	for (TActorIterator<ACatrunCandle> Candle(&World); Candle; ++Candle)
		TrackEnemy(*Candle);

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
			Actor->OnDestroyed.RemoveDynamic(this, &ThisClass::UntrackEnemy);
	}
	Enemies.Reset();
	DetachWidget();
	Super::EndPlay(Reason);
}

void ACatrunMinimapPresenter::TrackEnemy(AActor* Actor)
{
	if (!IsValid(Actor) || Actor->IsActorBeingDestroyed() || Actor->GetWorld() != GetWorld())
		return;

	const bool bArmor = Actor->IsA<ACatrunArmor>();
	if (!bArmor && !Actor->IsA<ACatrunCandle>())
		return;

	Enemies.Add(Actor, bArmor ? ECatrunMinimapEnemyKind::Armor : ECatrunMinimapEnemyKind::Candle);
	Actor->OnDestroyed.AddUniqueDynamic(this, &ThisClass::UntrackEnemy);
}

void ACatrunMinimapPresenter::UntrackEnemy(AActor* Actor)
{
	Enemies.Remove(Actor);
}

bool ACatrunMinimapPresenter::AttachWidget(APlayerController& Controller)
{
	UCatrunMinimapWidget* Widget = CreateWidget<UCatrunMinimapWidget>(&Controller, WidgetClass);
	if (Widget && Widget->InitializeMap(BackgroundTexture, MapSize, CaptureYawDegrees)
		&& Widget->AddToPlayerScreen() && Widget->IsInViewport())
	{
		MinimapWidget = Widget;
		InputController = &Controller;
		EnableInput(&Controller);
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
	if (APlayerController* Controller = InputController.Get())
		DisableInput(Controller);
	InputController.Reset();
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

	if (MinimapWidget->bExpanded)
		MinimapWidget->SetExpanded(false);
	if (MinimapWidget->GetVisibility() != ESlateVisibility::Collapsed)
		MinimapWidget->SetVisibility(ESlateVisibility::Collapsed);
}

bool ACatrunMinimapPresenter::CanUseMinimap(const APlayerController* Controller) const
{
	const UWorld* World = GetWorld();
	if (!World || World->bIsTearingDown || World->IsPaused() || !IsValid(Controller) || Controller->GetWorld() != World
		|| UCatrunLevelFlowLibrary::ShouldHideGameplayHUD(this))
		return false;

	const auto* Settings = World->GetSubsystem<UCatrunSettingsSubsystem>();
	const auto* Flow = World->GetSubsystem<UCatrunLevelFlowSubsystem>();
	const auto* Restart = World->GetSubsystem<UCatrunRestartSubsystem>();
	if ((Settings && Settings->GetCurrentSettingsWidget()) || (Flow && Flow->IsTransitioning())
		|| (Restart && Restart->IsCatching()))
		return false;

	// The opening sequence can lock character movement directly. Hiding in a basket remains gameplay.
	const auto* Character = Cast<ACharacter>(Controller->GetPawn());
	if (Character && Character->GetCharacterMovement()->MovementMode == MOVE_None)
	{
		const auto* Basket = Character->FindComponentByClass<UCatrunBasketInteractionComponent>();
		return Basket && (Basket->Busy || Basket->IsHidden);
	}
	return true;
}

void ACatrunMinimapPresenter::ToggleMap()
{
	if (MinimapWidget && MinimapWidget->IsInViewport() && CanUseMinimap(InputController.Get()))
		MinimapWidget->SetExpanded(!MinimapWidget->bExpanded);
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
	if (MinimapWidget && (Controller != InputController.Get() || !MinimapWidget->IsInViewport()))
		DetachWidget();
	if (!Controller || Controller->GetWorld() != World || !Controller->GetLocalPlayer()
		|| (!MinimapWidget && !AttachWidget(*Controller)))
		return;

	if (!CanUseMinimap(Controller))
	{
		// Cinematic visibility is temporary; retain the user's expanded/compact choice.
		// SettingsOpened separately owns its deliberate compact reset.
		MinimapWidget->SetVisibility(ESlateVisibility::Collapsed);
		return;
	}
	if (MinimapWidget->GetVisibility() != ESlateVisibility::HitTestInvisible)
		MinimapWidget->SetVisibility(ESlateVisibility::HitTestInvisible);
	MinimapWidget->UpdateLayout();
	MinimapWidget->UpdateMapProjection(MapSize, CaptureYawDegrees, *Controller);
	FVector2D UV;
	MinimapWidget->UpdatePlayer(ProjectActor(Controller->GetPawn(), UV) ? &UV : nullptr);
	TArray<FVector2D, TInlineAllocator<8>> ArmorPositions;
	TArray<FVector2D, TInlineAllocator<8>> CandlePositions;
	for (const auto& Enemy : Enemies)
	{
		if (ProjectActor(Enemy.Key.Get(), UV))
			(Enemy.Value == ECatrunMinimapEnemyKind::Armor ? ArmorPositions : CandlePositions).Add(UV);
	}
	MinimapWidget->UpdateEnemies(ECatrunMinimapEnemyKind::Armor, ArmorPositions);
	MinimapWidget->UpdateEnemies(ECatrunMinimapEnemyKind::Candle, CandlePositions);
}
