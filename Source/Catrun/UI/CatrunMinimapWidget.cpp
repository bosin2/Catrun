#include "CatrunMinimapWidget.h"

#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/Image.h"
#include "Components/SceneComponent.h"
#include "Engine/GameInstance.h"
#include "Engine/Texture2D.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Monster/CatrunArmor.h"
#include "Monster/CatrunCandle.h"

namespace
{
	constexpr float MarkerRefreshSeconds = .1f;
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

bool UCatrunMinimapWidget::InitializeMap(UTexture2D* Texture)
{
	if (!Texture || !MapBackground || !MarkerLayer || !PlayerMarkerClass || !EnemyMarkerClass)
		return false;

	SetIsFocusable(false);
	SetVisibility(ESlateVisibility::HitTestInvisible);
	MapBackground->SetBrushFromTexture(Texture, false);
	PlayerMarker = AddMarker(PlayerMarkerClass, 1);
	return PlayerMarker != nullptr;
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
	const ESlateVisibility Visibility = UV ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed;
	if (UV)
	{
		const FAnchors Anchors(static_cast<float>(UV->X), static_cast<float>(UV->Y));
		if (MarkerSlot.GetAnchors() != Anchors)
			MarkerSlot.SetAnchors(Anchors);
	}
	if (UWidget* Marker = MarkerSlot.GetContent(); Marker && Marker->GetVisibility() != Visibility)
		Marker->SetVisibility(Visibility);
}

void UCatrunMinimapWidget::UpdatePlayer(const FVector2D* UV)
{
	UpdateMarker(*PlayerMarker, UV);
}

void UCatrunMinimapWidget::UpdateEnemy(int32 Index, const FVector2D& UV)
{
	if (Index == EnemyMarkers.Num())
	{
		if (UCanvasPanelSlot* MarkerSlot = AddMarker(EnemyMarkerClass, 0))
			EnemyMarkers.Add(MarkerSlot);
	}
	if (EnemyMarkers.IsValidIndex(Index))
		UpdateMarker(*EnemyMarkers[Index], &UV);
}

void UCatrunMinimapWidget::HideUnusedEnemies(int32 VisibleCount)
{
	for (int32 Index = VisibleCount; Index < EnemyMarkers.Num(); ++Index)
		UpdateMarker(*EnemyMarkers[Index], nullptr);
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

	SpawnedHandle = World.AddOnActorSpawnedHandler(FOnActorSpawned::FDelegate::CreateUObject(this, &ThisClass::TrackEnemy));
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
	}
	SpawnedHandle.Reset();
	for (const TWeakObjectPtr<AActor>& Enemy : Enemies)
	{
		if (AActor* Actor = Enemy.Get())
			Actor->OnDestroyed.RemoveDynamic(this, &ThisClass::UntrackEnemy);
	}
	Enemies.Reset();
	if (MinimapWidget)
	{
		MinimapWidget->RemoveFromParent();
		MinimapWidget = nullptr;
	}
	Super::EndPlay(Reason);
}

void ACatrunMinimapPresenter::TrackEnemy(AActor* Actor)
{
	if (IsValid(Actor) && !Actor->IsActorBeingDestroyed() && Actor->GetWorld() == GetWorld()
		&& (Actor->IsA<ACatrunArmor>() || Actor->IsA<ACatrunCandle>()))
	{
		Enemies.AddUnique(Actor);
		Actor->OnDestroyed.AddUniqueDynamic(this, &ThisClass::UntrackEnemy);
	}
}

void ACatrunMinimapPresenter::UntrackEnemy(AActor* Actor)
{
	Enemies.RemoveSingleSwap(TWeakObjectPtr<AActor>(Actor), EAllowShrinking::No);
}

bool ACatrunMinimapPresenter::AttachWidget()
{
	UWorld* World = GetWorld();
	const UGameInstance* GameInstance = World->GetGameInstance();
	if (!GameInstance || !World->GetGameViewport())
		return false;

	APlayerController* Controller = GameInstance->GetFirstLocalPlayerController(World);
	if (!Controller || Controller->GetWorld() != World || !Controller->GetLocalPlayer())
		return false;

	UCatrunMinimapWidget* Widget = CreateWidget<UCatrunMinimapWidget>(Controller, WidgetClass);
	if (Widget && Widget->InitializeMap(BackgroundTexture) && Widget->AddToPlayerScreen() && Widget->IsInViewport())
	{
		MinimapWidget = Widget;
		return true;
	}

	if (Widget)
		Widget->RemoveFromParent();
	UE_LOG(LogTemp, Warning, TEXT("Minimap presenter %s could not attach its configured widget."), *GetPathName());
	World->GetTimerManager().ClearTimer(UpdateTimer);
	return false;
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
	if (!MinimapWidget && !AttachWidget())
		return;

	FVector2D UV;
	MinimapWidget->UpdatePlayer(ProjectActor(MinimapWidget->GetOwningPlayerPawn(), UV) ? &UV : nullptr);
	int32 VisibleCount = 0;
	for (const TWeakObjectPtr<AActor>& Enemy : Enemies)
	{
		if (ProjectActor(Enemy.Get(), UV))
			MinimapWidget->UpdateEnemy(VisibleCount++, UV);
	}
	MinimapWidget->HideUnusedEnemies(VisibleCount);
}
