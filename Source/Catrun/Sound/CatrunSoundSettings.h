#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "SoundTypes.h"
#include "CatrunSoundSettings.generated.h"

class UMaterialInterface;

/**
 * Every tunable value of the sound and monster-movement systems.
 *
 * Edit it in the Content Browser (DA_SoundSettings). Nothing here needs a code change.
 */
UCLASS(BlueprintType)
class CATRUN_API UCatrunSoundSettings : public UDataAsset
{
	GENERATED_BODY()

public:
	// ---- Grid ----------------------------------------------------------------
	// Cell size in cm. Must stay well below the cat-hole width (about 60cm).
	// Smaller cells give more exact paths but cost more memory and time.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Grid", meta = (ClampMin = "5.0"))
	float CellSize = 25.f;

	// Height (cm) of the traces used to find walls. Keep it inside the cat-hole height (65cm).
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Grid")
	float TraceHeight = 30.f;

	// Actors with this tag block sound and movement.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Grid")
	FName WallTag = TEXT("SoundWall");

	// Actors with this tag are the floor the grid is built on.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Grid")
	FName FloorTag = TEXT("SoundFloor");

	// Furniture and other things the armor must walk around. Sound ignores them completely;
	// only the armor path keeps its distance (see ArmorClearance).
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Grid")
	FName ObstacleTag = TEXT("SoundObstacle");

	// ---- Sound budget (cm of travel distance) --------------------------------
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Budget", meta = (ClampMin = "0.0"))
	float LargeBudget = 500.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Budget", meta = (ClampMin = "0.0"))
	float MediumBudget = 280.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Budget", meta = (ClampMin = "0.0"))
	float SmallBudget = 140.f;

	// How fast sound travels (cm per second). Listeners hear a sound when the wave reaches
	// them, and the ring on the floor expands at the same speed.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Budget", meta = (ClampMin = "10.0"))
	float SoundSpeed = 600.f;

	// ---- Floor material cost -------------------------------------------------
	// Travel cost multiplier for floors without a special tag (stone = 1).
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Floor")
	float DefaultFloorMultiplier = 1.f;

	// Extra floor tags (add the tag to a floor actor) mapped to a cost multiplier.
	// Example: "SoundFloor_Carpet" -> 2.0 makes sound travel half as far over carpet.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Floor")
	TMap<FName, float> FloorTagMultipliers;

	// ---- Player bell ---------------------------------------------------------
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Bell", meta = (ClampMin = "0.0"))
	float BellCooldown = 5.f;

	// ---- Wave visualization --------------------------------------------------
	// Material with the parameters of M_SoundWave. Assign M_SoundWave here.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visual")
	TObjectPtr<UMaterialInterface> WaveMaterial;

	// Size (cm) of one pixel of the distance picture the wave is drawn from.
	// 1 = one pixel per square centimetre: the edge of the wave is perfectly smooth. Only the part
	// of the picture around the wave is updated, so this stays cheap.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visual", meta = (ClampMin = "1.0"))
	float VisualTexelSize = 1.f;

	// One sound shows this many rings, one right after the other.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visual", meta = (ClampMin = "1", ClampMax = "6"))
	int32 WaveCount = 3;

	// Seconds between the rings of one sound (they travel at the same speed, so this sets the gap).
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visual", meta = (ClampMin = "0.01"))
	float WaveInterval = 0.12f;

	// Thickness (cm) of the visible ring behind the wave front.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visual", meta = (ClampMin = "1.0"))
	float RingWidth = 60.f;

	// Softness (cm) of the leading edge of the ring.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visual", meta = (ClampMin = "0.0"))
	float RingFeather = 8.f;

	// Seconds the finished ring stays before it fades out.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visual", meta = (ClampMin = "0.0"))
	float HoldDuration = 0.0f;

	// Seconds the ring needs to fade out after it reached its full size.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visual", meta = (ClampMin = "0.0"))
	float FadeDuration = 0.4f;

	// Colour of the wave. The alpha channel (A) is the transparency: 0 = invisible, 1 = solid.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visual")
	FLinearColor SoundColor = FLinearColor(1.f, 0.75f, 0.15f, 0.45f);

	// How much fainter the ring is at the far end of the budget (0 = same, 1 = invisible).
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visual", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float EdgeFade = 0.6f;

	// Height above the floor where the wave is drawn (avoids flickering with the floor).
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visual")
	float VisualHeight = 3.f;

	// ---- Armor movement ------------------------------------------------------
	// Half the width of the armor (cm). Cells closer to a wall than this are off limits.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Armor", meta = (ClampMin = "0.0"))
	float ArmorClearance = 35.f;

	// Extra path cost (cm) for every 90 degree turn. Higher = straighter paths with fewer corners.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Armor", meta = (ClampMin = "0.0"))
	float ArmorTurnPenalty = 100.f;

	// An armor this close (cm) to a closed door opens it.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Armor", meta = (ClampMin = "0.0"))
	float ArmorDoorOpenDistance = 120.f;

	// ---- Sight: shared by candles and armors --------------------------------
	// Material of the floor display of a view area (M_VisionFan).
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sight")
	TObjectPtr<UMaterialInterface> VisionMaterial;

	// Height (cm above the floor) of the rays that look for walls. Things lower than this do not
	// block the view (chairs, benches); taller things do (shelves, fireplaces, closed doors).
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sight", meta = (ClampMin = "1.0"))
	float VisionTraceHeight = 100.f;

	// Size (cm) of the cat for sight: a cat counts as seen when its edge is inside the view.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sight", meta = (ClampMin = "0.0"))
	float CatSightRadius = 15.f;

	// How long (seconds) the "!" stays above a monster that has noticed the cat.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sight", meta = (ClampMin = "0.0"))
	float AlertDuration = 1.5f;

	// Floor display: opacity, softness of the wall edge (cm) and how much it fades with distance (0..1).
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sight", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float VisionOpacity = 0.35f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sight", meta = (ClampMin = "0.0"))
	float VisionEdgeSoftness = 20.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sight", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float VisionRangeFade = 0.5f;

	// ---- Candle (fixed direction, sweeping view) ------------------------------
	// How far (cm) the candle sees.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Candle", meta = (ClampMin = "10.0"))
	float CandleRange = 500.f;

	// Total angle (degrees) the candle can look over. It is centred on the direction the candle
	// actor faces in the level.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Candle", meta = (ClampMin = "1.0", ClampMax = "360.0"))
	float CandleTotalAngle = 70.f;

	// Width (degrees) of the real view cone. It sweeps back and forth inside the total angle.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Candle", meta = (ClampMin = "1.0", ClampMax = "360.0"))
	float CandleConeAngle = 30.f;

	// How fast the cone sweeps (degrees per second) and how long it waits at each end (seconds).
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Candle", meta = (ClampMin = "0.0"))
	float CandleSweepSpeed = 20.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Candle", meta = (ClampMin = "0.0"))
	float CandleSweepEndPause = 0.6f;

	// Number of rays that make up the cone. More = smoother edges next to walls.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Candle", meta = (ClampMin = "4"))
	int32 CandleRayCount = 48;

	// Color of the view cone while patrolling, and while it has spotted the cat (red).
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Candle")
	FLinearColor CandleSightColor = FLinearColor(1.f, 0.35f, 0.1f, 1.f);

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Candle")
	FLinearColor CandleAlertSightColor = FLinearColor(1.f, 0.02f, 0.02f, 1.f);

	// After spotting the cat the view follows it. This is how fast the cone turns (degrees per
	// second). The cone never leaves the total angle, so a cat far outside it is lost.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Candle", meta = (ClampMin = "1.0"))
	float CandleTrackSpeed = 120.f;

	// The candle gives up and goes back to patrolling when the cat has been out of its view for
	// this long (seconds). 0 = at once. A little delay avoids flicker at the edge of the cone.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Candle", meta = (ClampMin = "0.0"))
	float CandleLoseSightDelay = 0.3f;

	// ---- Armor detection (a small circle around the armor) ---------------------
	// Radius (cm) of the circle around the armor. The cat is caught when it touches this circle.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Armor", meta = (ClampMin = "10.0"))
	float ArmorDetectRadius = 60.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Armor", meta = (ClampMin = "8"))
	int32 ArmorDetectRayCount = 72;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Armor")
	FLinearColor ArmorDetectColor = FLinearColor(0.3f, 0.6f, 1.f, 1.f);

	// ---- Armor catch (what happens when the cat touches the circle) -------------
	// The cat is caught the moment it touches the detection circle. Then the camera moves in front
	// of the armor, the armor lifts the cat, the screen fades to black and the level starts again.

	// The camera cuts to the front of the armor at once. The armor waits this long (seconds)
	// before the pick-up animation starts.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Armor Catch", meta = (ClampMin = "0.0"))
	float CatchCameraBlendTime = 0.5f;

	// Where the camera ends up, measured from the armor: distance in front (cm), to the right (cm),
	// and height above the floor (cm).
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Armor Catch", meta = (ClampMin = "50.0"))
	float CatchCameraDistance = 450.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Armor Catch")
	float CatchCameraSideOffset = 100.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Armor Catch")
	float CatchCameraHeight = 220.f;

	// Height (cm) of the point the camera looks at, above the armor's feet.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Armor Catch")
	float CatchLookAtHeight = 90.f;

	// The final camera (and the point it looks at) is moved this far down (cm), so that some of
	// the floor below the armor's feet is visible.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Armor Catch", meta = (ClampMin = "0.0"))
	float CatchCameraLowering = 35.f;

	// The armor picks the cat up when its hands are this close to the cat (cm). If the hands never
	// get that close, the cat is picked up after CatchGrabLatestTime anyway.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Armor Catch", meta = (ClampMin = "1.0"))
	float CatchGrabDistance = 35.f;

	// Latest moment (seconds after the pick-up animation starts) at which the cat is grabbed.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Armor Catch", meta = (ClampMin = "0.0"))
	float CatchGrabLatestTime = 3.f;

	// The cat moves from where it stands into the hands this fast (seconds).
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Armor Catch", meta = (ClampMin = "0.0"))
	float CatchGrabBlendTime = 0.3f;

	// Where the cat is held, measured from the middle between the armor's two hands (cm, in the
	// armor's own directions: forward, right, up).
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Armor Catch")
	FVector CatchHoldOffset = FVector(0.f, 0.f, -10.f);

	// The fade to black takes this long (seconds) and ends together with the pick-up animation.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Armor Catch", meta = (ClampMin = "0.1"))
	float CatchFadeOutTime = 1.f;

	// The screen stays black this long (seconds) before the level starts again.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Armor Catch", meta = (ClampMin = "0.0"))
	float CatchBlackHoldTime = 0.3f;

	// The fade in from black after the restart takes this long (seconds).
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Armor Catch", meta = (ClampMin = "0.1"))
	float RestartFadeInTime = 1.f;

	// ---- Footsteps -----------------------------------------------------------
	// Sneaking (Ctrl) makes no sound. Walking makes a small sound, running (Shift) a medium one;
	// the bell is the loudest. The sound is made every few moments while the cat moves.

	// The cat counts as moving when it is faster than this (cm/s).
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Footsteps", meta = (ClampMin = "0.0"))
	float FootstepMinSpeed = 20.f;

	// Seconds between two walking sounds.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Footsteps", meta = (ClampMin = "0.1"))
	float WalkStepInterval = 0.5f;

	// Seconds between two running sounds.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Footsteps", meta = (ClampMin = "0.1"))
	float RunStepInterval = 0.3f;

	// ---- Candle mark (design doc 4.5) ------------------------------------------
	// Provisional: the rules are to be discussed with the team, so keep everything here.

	// The armor that follows the mark plans its way to the cat this often (seconds).
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Mark", meta = (ClampMin = "0.1"))
	float MarkRepathInterval = 0.4f;

	// Another armor takes over the following only when it is closer than this fraction of the
	// distance of the armor that follows now (0.8 = 20% closer).
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Mark", meta = (ClampMin = "0.1", ClampMax = "1.0"))
	float MarkSwitchRatio = 0.8f;

	// The red orb above the cat: its material, size (1 = 100 cm), height above the cat (cm),
	// and the glow it gives.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Mark")
	TObjectPtr<UMaterialInterface> MarkMaterial;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Mark", meta = (ClampMin = "0.01"))
	float MarkOrbScale = 0.15f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Mark")
	float MarkHeight = 80.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Mark")
	FLinearColor MarkLightColor = FLinearColor(1.f, 0.05f, 0.05f, 1.f);

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Mark", meta = (ClampMin = "0.0"))
	float MarkLightIntensity = 800.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Mark", meta = (ClampMin = "10.0"))
	float MarkLightRadius = 250.f;

	float GetBudget(ECatrunSoundSize Size) const
	{
		switch (Size)
		{
		case ECatrunSoundSize::Small:	return SmallBudget;
		case ECatrunSoundSize::Medium:	return MediumBudget;
		default:						return LargeBudget;
		}
	}
};
