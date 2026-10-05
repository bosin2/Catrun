#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "SoundWaveVisual.generated.h"

struct FCatrunGridData;
class UCatrunSoundSettings;
class UMaterialInstanceDynamic;
class UStaticMeshComponent;
class UTexture2D;

/**
 * Draws a sound wave on the floor: a thin ring that travels outward from the sound source
 * along the real propagation paths (so it stops at walls and continues through doors).
 *
 * How it works, in short:
 *  1. When a sound is made, the distance field (path length from the source to every cell)
 *     is copied into a small picture (texture). One pixel = VisualTexelSize cm of floor.
 *  2. One flat plane covers the whole map and uses the picture in its material (M_SoundWave).
 *  3. Every frame only one number changes: the radius of the ring. The graphics card draws
 *     the ring wherever "distance in the picture" is close to that radius.
 *
 * So the CPU work per frame is tiny, no matter how fine the picture is.
 */
UCLASS(ClassGroup = (Catrun))
class CATRUN_API USoundWaveVisual : public UActorComponent
{
	GENERATED_BODY()

public:
	USoundWaveVisual();

	// Creates the plane, the picture and the material instance. Call once at BeginPlay.
	void Initialize(const FCatrunGridData& Grid, const UCatrunSoundSettings& InSettings);

	// Starts a new wave. Distance has one entry per grid cell (see CatrunSoundPropagation).
	void Show(const FCatrunGridData& Grid, const TArray<float>& Distance, float Budget, double StartTime);

	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

private:
	// Copies the distance field into the picture, one pixel per VisualTexelSize cm.
	void FillTexture(const FCatrunGridData& Grid, const TArray<float>& Distance);

	// Shows or hides the plane.
	void SetPlaneVisible(bool bVisible);

	UPROPERTY(Transient)
	TObjectPtr<const UCatrunSoundSettings> Settings;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMeshComponent> Plane;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> Material;

	UPROPERTY(Transient)
	TObjectPtr<UTexture2D> DistanceTexture;

	int32 TextureWidth = 0;
	int32 TextureHeight = 0;

	bool bActive = false;
	double StartTime = 0.0;
	float Budget = 0.f;
};
