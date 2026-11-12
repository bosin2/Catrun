#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "Components/CanvasPanelSlot.h"
#include "GameFramework/Actor.h"
#include "Rendering/SlateRenderTransform.h"
#include "TimerManager.h"
#include "CatrunMinimapWidget.generated.h"

class UCanvasPanel;
class UImage;
class UTexture2D;
class UWidget;

enum class ECatrunMinimapEnemyKind : uint8
{
	Armor,
	Candle,
};

namespace CatrunMinimap
{
	/** Matches an orthographic top-down capture at pitch -90 and roll 0. */
	CATRUN_API bool Project(const FVector2D& WorldXY, const FVector2D& Center, const FVector2D& Size,
		double YawDegrees, FVector2D& OutUV);
	/** Fits the capture footprint in the square map surface, with a pivot at its center. */
	CATRUN_API bool FitCameraProjection(const FVector2D& CaptureSize, double CaptureYawDegrees,
		const FRotator& CameraRotation, FSlateRenderTransform& OutTransform);
	CATRUN_API FVector2D ToDisplayUV(const FVector2D& CaptureUV, const FSlateRenderTransform& Transform);
}

/** The widget Blueprint owns the panel, background and marker appearance. */
UCLASS(Abstract, Blueprintable)
class CATRUN_API UCatrunMinimapWidget : public UUserWidget
{
	GENERATED_BODY()

protected:
	virtual void NativeTick(const FGeometry& Geometry, float DeltaSeconds) override;
	UPROPERTY(meta=(BindWidget)) TObjectPtr<UImage> MapBackground;
	UPROPERTY(meta=(BindWidget)) TObjectPtr<UCanvasPanel> MarkerLayer;
	UPROPERTY(meta=(BindWidgetOptional)) TObjectPtr<UWidget> MinimapFrame;
	UPROPERTY(EditDefaultsOnly, Category="Minimap") TSubclassOf<UUserWidget> PlayerMarkerClass;
	UPROPERTY(EditDefaultsOnly, Category="Minimap") TSubclassOf<UUserWidget> EnemyMarkerClass;
	UPROPERTY(EditDefaultsOnly, Category="Minimap") TSubclassOf<UUserWidget> ArmorMarkerClass;
	UPROPERTY(EditDefaultsOnly, Category="Minimap") TSubclassOf<UUserWidget> CandleMarkerClass;
	UPROPERTY(EditDefaultsOnly, Category="Minimap", meta=(ClampMin=".1", ClampMax="1.0"))
	float ExpandedMapViewportFraction = .76f;
	UPROPERTY(EditDefaultsOnly, Category="Minimap", meta=(ClampMin="1.0"))
	float ExpandedMapMaxSize = 700.f;

private:
	friend class ACatrunMinimapPresenter;
#if WITH_DEV_AUTOMATION_TESTS
	friend class FCatrunMinimapLayoutTest;
	friend class FCatrunMinimapEnemyLifecycleTest;
#endif

	bool InitializeMap(UTexture2D* Texture, const FVector2D& CaptureSize, double CaptureYawDegrees);
	void SetExpanded(bool bInExpanded);
	void UpdateLayout();
	static FAnchorData GetFrameLayout(const FAnchorData& CompactLayout, const FVector2D& ViewportSize,
		bool bIsExpanded, float ExpandedViewportFraction, float ExpandedMaxSize);
	void UpdateMapProjection(const FVector2D& CaptureSize, double CaptureYawDegrees, const APlayerController& Controller);
	void UpdatePlayer(const FVector2D* UV);
	void UpdateEnemies(ECatrunMinimapEnemyKind Kind, TConstArrayView<FVector2D> Positions);
	UCanvasPanelSlot* AddMarker(TSubclassOf<UUserWidget> MarkerClass, int32 ZOrder);
	void UpdateMarker(UCanvasPanelSlot& MarkerSlot, const FVector2D* UV);

	UPROPERTY(Transient) TObjectPtr<UCanvasPanelSlot> FrameSlot;
	UPROPERTY(Transient) TObjectPtr<UCanvasPanelSlot> PlayerMarker;
	UPROPERTY(Transient) TArray<TObjectPtr<UCanvasPanelSlot>> ArmorMarkers;
	UPROPERTY(Transient) TArray<TObjectPtr<UCanvasPanelSlot>> CandleMarkers;
	FAnchorData CompactFrameLayout;
	FSlateRenderTransform MapProjection;
	bool bExpanded = false;
};

/** One placed instance per playable map. Its widget and marker cache belong to that world. */
UCLASS(Blueprintable)
class CATRUN_API ACatrunMinimapPresenter : public AActor
{
	GENERATED_BODY()

public:
	ACatrunMinimapPresenter();

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Minimap")
	TSubclassOf<UCatrunMinimapWidget> WidgetClass;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Minimap")
	TObjectPtr<UTexture2D> BackgroundTexture;

	/** World XY at the center of the image. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Minimap")
	FVector2D MapCenter = FVector2D::ZeroVector;

	/** World units from image left to right and top to bottom, respectively. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Minimap")
	FVector2D MapSize = FVector2D::ZeroVector;

	/** Zero yaw puts world +Y at image right and +X at image top. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Minimap")
	double CaptureYawDegrees = 0.;

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;

private:
#if WITH_DEV_AUTOMATION_TESTS
	friend class FCatrunMinimapEnemyLifecycleTest;
#endif

	void StartTracking(UWorld& World);
	void TrackEnemy(AActor* Actor);
	UFUNCTION() void UntrackEnemy(AActor* Actor);
	bool AttachWidget(APlayerController& Controller);
	void DetachWidget();
	void HideMinimap();
	void UpdateMinimap();
	void ToggleMap();
	bool CanUseMinimap(const APlayerController* Controller) const;
	bool ProjectActor(const AActor* Actor, FVector2D& OutUV) const;

	UPROPERTY(Transient) TObjectPtr<UCatrunMinimapWidget> MinimapWidget;
	TWeakObjectPtr<APlayerController> InputController;
	TMap<TWeakObjectPtr<AActor>, ECatrunMinimapEnemyKind> Enemies;
	FDelegateHandle SpawnedHandle;
	FTimerHandle UpdateTimer;
};
