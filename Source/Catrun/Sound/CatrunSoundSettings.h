#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "SoundTypes.h"
#include "CatrunSoundSettings.generated.h"

class UMaterialInterface;

// Every tunable value of the sound system lives here so it can be edited in one place
// (Content Browser -> double click the asset) without touching code.
UCLASS(BlueprintType)
class CATRUN_API UCatrunSoundSettings : public UDataAsset
{
	GENERATED_BODY()

public:
	// ---- Grid ----------------------------------------------------------------
	// Cell size in cm. Must stay well below the cat-hole width (about 60cm).
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Grid", meta = (ClampMin = "10.0"))
	float CellSize = 25.f;

	// Height (cm) of the traces used to find walls. Keep it inside the cat-hole height (65cm).
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Grid")
	float TraceHeight = 30.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Grid")
	FName WallTag = TEXT("SoundWall");

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Grid")
	FName FloorTag = TEXT("SoundFloor");

	// ---- Sound budget (cm of travel distance) --------------------------------
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Budget", meta = (ClampMin = "0.0"))
	float LargeBudget = 1500.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Budget", meta = (ClampMin = "0.0"))
	float MediumBudget = 800.f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Budget", meta = (ClampMin = "0.0"))
	float SmallBudget = 400.f;

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

	// ---- Visualization -------------------------------------------------------
	// How fast the ring expands along the propagation path (cm per second).
	// Expansion time = budget / speed, so every sound size spreads at the same speed.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visual", meta = (ClampMin = "10.0"))
	float ExpandSpeed = 600.f;

	// Seconds the finished area stays visible before it fades out.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visual", meta = (ClampMin = "0.0"))
	float HoldDuration = 0.3f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visual", meta = (ClampMin = "0.0"))
	float FadeDuration = 0.7f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visual")
	FLinearColor SoundColor = FLinearColor(1.f, 0.75f, 0.15f, 0.45f);

	// Height above the floor where the visualization is drawn (avoids z-fighting).
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visual")
	float VisualHeight = 3.f;

	// Material with a "SoundColor" vector parameter and per-instance custom data 0 as opacity.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visual")
	TObjectPtr<UMaterialInterface> VisualMaterial;

	// Cells at the edge of the budget are drawn this much fainter than cells near the source (0..1).
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Visual", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float EdgeFade = 0.6f;

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
