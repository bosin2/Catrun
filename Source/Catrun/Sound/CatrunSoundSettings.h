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
	// 5 gives a smooth ring. Larger values are cheaper but blockier.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visual", meta = (ClampMin = "1.0"))
	float VisualTexelSize = 5.f;

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
