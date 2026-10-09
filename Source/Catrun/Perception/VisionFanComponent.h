#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "VisionFanComponent.generated.h"

class ASoundGridManager;
class UCatrunSoundSettings;
class UMaterialInstanceDynamic;
class UStaticMeshComponent;
class UTexture2D;

/**
 * What a monster can see: a fan of rays seen from above.
 *
 * Every frame the owner calls Update with the direction and width of the fan. The component
 * shoots rays across the fan and stops each one at the first wall, tall piece of furniture or
 * closed door. The result is used for two things that always agree (design doc 10.1):
 *  - CanSee(): is a point (the cat) inside what the monster sees?
 *  - the floor display: the fan is drawn on the floor, cut off by the walls.
 *
 * A candle uses a narrow fan (a cone). An armor uses a full circle (half angle 180).
 *
 * Settings (heights, colors, opacity) come from the sound settings asset of the level.
 */
UCLASS(ClassGroup = (Catrun), meta = (BlueprintSpawnableComponent))
class CATRUN_API UCatrunVisionFanComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UCatrunVisionFanComponent();

	// Shape of the fan. Set once (usually in the owner's BeginPlay).
	void Configure(float InRange, int32 InRayCount, const FLinearColor& InColor);

	// Recomputes the fan. CenterAngle is a yaw in degrees (0 = east, 90 = south), HalfAngle is
	// half the width in degrees (180 = full circle).
	void Update(float CenterAngleDegrees, float HalfAngleDegrees);

	// True if a point is inside the fan and not hidden behind a wall. PointRadius makes the
	// test use the edge of the point's body instead of its centre.
	bool CanSee(const FVector& WorldPoint, float PointRadius = 0.f) const;

	// Shows or hides the floor display. The sight itself keeps working while hidden.
	void SetDisplayVisible(bool bVisible);

	// Changes the color of the floor display (for example orange -> red when the cat is spotted).
	void SetColor(const FLinearColor& NewColor);

private:
	// Waits until the sound system of the level is ready, then builds the floor display.
	bool EnsureReady();

	// Distance (cm) from Start along Direction to the first thing that blocks the view.
	float TraceRay(const FVector& Start, const FVector& Direction) const;

	void WriteTexture();

	UPROPERTY(Transient)
	TObjectPtr<const UCatrunSoundSettings> Settings;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMeshComponent> Plane;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> Material;

	UPROPERTY(Transient)
	TObjectPtr<UTexture2D> DistanceTexture;

	float Range = 500.f;
	int32 RayCount = 48;
	FLinearColor Color = FLinearColor::White;

	float FloorZ = 0.f;
	float CenterAngle = 0.f;
	float HalfAngle = 15.f;
	bool bReady = false;
	bool bDisplayVisible = true;

	// Distance to the first blocker for every ray (cm), left edge of the fan first.
	TArray<float> RayDistances;
};
