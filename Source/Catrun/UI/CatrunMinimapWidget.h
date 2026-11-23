#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "Components/CanvasPanelSlot.h"
#include "GameFramework/Actor.h"
#include "Rendering/SlateRenderTransform.h"
#include "TimerManager.h"
#include "CatrunMinimapWidget.generated.h"

class ACatrunMinimapPresenter;
class FCatrunMinimapTabInput;
class UCanvasPanel;
class UImage;
class UTexture2D;
class UWidget;
struct FSceneViewProjectionData;

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
	/** Fits a square centered on the player around the camera's footprint on the horizontal map plane. */
	CATRUN_API bool MakeLocalProjection(const FVector2D& CaptureCenter, const FVector2D& CaptureSize,
		double CaptureYawDegrees, const FVector& PlayerLocation, const FSceneViewProjectionData& View,
		double Coverage, FSlateRenderTransform& OutTransform);
	CATRUN_API FVector2D ToDisplayUV(const FVector2D& CaptureUV, const FSlateRenderTransform& Transform);
	CATRUN_API bool TryGetDisplayUV(const FVector2D& CaptureUV, const FSlateRenderTransform& Transform, FVector2D& OutUV);
	CATRUN_API FSlateRenderTransform ToImageTransform(const FSlateRenderTransform& Transform, const FVector2D& LocalSize);
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
	UPROPERTY(EditDefaultsOnly, Category="Minimap", meta=(ClampMin="1.0"))
	float HoldSizeMultiplier = 1.25f;
	UPROPERTY(EditDefaultsOnly, Category="Minimap", meta=(ClampMin="1.0"))
	float NeighborhoodCoverage = 1.80f;
	/** Target multiplier on normal world coverage. It increases as needed to keep terrain smaller in the fitted held frame. */
	UPROPERTY(EditDefaultsOnly, Category="Minimap", meta=(ClampMin="1.0"))
	float HoldCoverageMultiplier = 1.45f;
	/** Multiplies the authored marker sizes while Tab is held. */
	UPROPERTY(EditDefaultsOnly, Category="Minimap", meta=(ClampMin="0.01", ClampMax="1.0"))
	float HoldMarkerSizeMultiplier = .85f;
	/** Seconds for the expand or collapse transition only. Tab stays expanded while held. Zero snaps each transition. */
	UPROPERTY(EditDefaultsOnly, Category="Minimap", meta=(ClampMin="0.0", ClampMax="1.0", Units="s"))
	float HoldTransitionDuration = .18f;

private:
	friend class ACatrunMinimapPresenter;
#if WITH_DEV_AUTOMATION_TESTS
	friend class FCatrunMinimapLayoutTest;
	friend class FCatrunMinimapEnemyLifecycleTest;
	friend class FCatrunMinimapOffscreenPreviewTest;
#endif

	bool InitializeMap(ACatrunMinimapPresenter& InPresenter);
	void AdvanceHoldAnimation(bool bHeld, float DeltaSeconds);
	double GetHoldBlend() const;
	void UpdateLayout(const FVector2D& ViewportSize);
	static FAnchorData GetFrameLayout(const FAnchorData& CompactLayout, const FVector2D& ViewportSize,
		double HoldBlend, float InHoldSizeMultiplier);
	double GetNeighborhoodCoverage(const FVector2D& ViewportSize) const;
	FVector2D GetFrameInnerSize(const FAnchorData& Layout) const;
	void ApplyImageProjection() const;
	void UpdateEnemyMarkers(ECatrunMinimapEnemyKind Kind, TConstArrayView<FVector2D> Positions);
	UCanvasPanelSlot* AddMarker(TSubclassOf<UUserWidget> MarkerClass, int32 ZOrder);
	void UpdateMarker(UCanvasPanelSlot& MarkerSlot, const FVector2D* DisplayUV);

	TWeakObjectPtr<ACatrunMinimapPresenter> Presenter;
	UPROPERTY(Transient) TObjectPtr<UCanvasPanelSlot> FrameSlot;
	UPROPERTY(Transient) TObjectPtr<UCanvasPanelSlot> PlayerMarker;
	UPROPERTY(Transient) TArray<TObjectPtr<UCanvasPanelSlot>> ArmorMarkers;
	UPROPERTY(Transient) TArray<TObjectPtr<UCanvasPanelSlot>> CandleMarkers;
	FAnchorData CompactFrameLayout;
	FSlateRenderTransform MapProjection;
	FSlateRenderTransform FallbackProjection;
	float HoldProgress = 0.f;
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
	friend class UCatrunMinimapWidget;
	friend class FCatrunMinimapTabInput;
	TSharedPtr<FCatrunMinimapTabInput> TabInput;
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
	bool CanUseMinimap(const APlayerController* Controller) const;
	bool ProjectActor(const AActor* Actor, FVector2D& OutUV) const;

	UPROPERTY(Transient) TObjectPtr<UCatrunMinimapWidget> MinimapWidget;
	TWeakObjectPtr<APlayerController> OwningController;
	TMap<TWeakObjectPtr<AActor>, ECatrunMinimapEnemyKind> Enemies;
	TArray<FVector2D, TInlineAllocator<8>> ArmorPositions;
	TArray<FVector2D, TInlineAllocator<8>> CandlePositions;
	FDelegateHandle SpawnedHandle;
	FTimerHandle UpdateTimer;
};
