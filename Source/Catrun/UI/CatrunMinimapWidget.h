#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "GameFramework/Actor.h"
#include "TimerManager.h"
#include "CatrunMinimapWidget.generated.h"

class UCanvasPanel;
class UCanvasPanelSlot;
class UImage;
class UTexture2D;

namespace CatrunMinimap
{
	/** Matches an orthographic top-down capture at pitch -90 and roll 0. */
	CATRUN_API bool Project(const FVector2D& WorldXY, const FVector2D& Center, const FVector2D& Size,
		double YawDegrees, FVector2D& OutUV);
}

/** The widget Blueprint owns the panel, background and marker appearance. */
UCLASS(Abstract, Blueprintable)
class CATRUN_API UCatrunMinimapWidget : public UUserWidget
{
	GENERATED_BODY()

protected:
	UPROPERTY(meta=(BindWidget)) TObjectPtr<UImage> MapBackground;
	UPROPERTY(meta=(BindWidget)) TObjectPtr<UCanvasPanel> MarkerLayer;
	UPROPERTY(EditDefaultsOnly, Category="Minimap") TSubclassOf<UUserWidget> PlayerMarkerClass;
	UPROPERTY(EditDefaultsOnly, Category="Minimap") TSubclassOf<UUserWidget> EnemyMarkerClass;

private:
	friend class ACatrunMinimapPresenter;

	bool InitializeMap(UTexture2D* Texture);
	void UpdatePlayer(const FVector2D* UV);
	void UpdateEnemy(int32 Index, const FVector2D& UV);
	void HideUnusedEnemies(int32 VisibleCount);
	UCanvasPanelSlot* AddMarker(TSubclassOf<UUserWidget> MarkerClass, int32 ZOrder);
	static void UpdateMarker(UCanvasPanelSlot& MarkerSlot, const FVector2D* UV);

	UPROPERTY(Transient) TObjectPtr<UCanvasPanelSlot> PlayerMarker;
	UPROPERTY(Transient) TArray<TObjectPtr<UCanvasPanelSlot>> EnemyMarkers;
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
	bool AttachWidget();
	void UpdateMinimap();
	bool ProjectActor(const AActor* Actor, FVector2D& OutUV) const;

	UPROPERTY(Transient) TObjectPtr<UCatrunMinimapWidget> MinimapWidget;
	TArray<TWeakObjectPtr<AActor>> Enemies;
	FDelegateHandle SpawnedHandle;
	FTimerHandle UpdateTimer;
};
