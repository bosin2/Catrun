#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "SoundTypes.h"
#include "SoundGridManager.generated.h"

class UCatrunSoundSettings;
class ACatrunDoor;
class UInstancedStaticMeshComponent;
class UMaterialInstanceDynamic;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnCatrunSoundEmitted, const FCatrunSoundEvent&, Event, float, Budget);

// Result of the latest sound propagation. Plain struct: read by the visualizer every frame.
struct FSoundField
{
	// Travel cost from the source to each cell. MAX_flt means "not reached".
	TArray<float> Dist;
	FCatrunSoundEvent Event;
	float Budget = 0.f;
	int32 SourceCell = INDEX_NONE;
	double EmitTime = 0.0;

	bool IsValid() const { return SourceCell != INDEX_NONE; }
};

/**
 * Grid based sound propagation (design doc 3.1 / 3.2 / 12.1).
 *
 * The level floor is sampled into square cells. Neighbouring cells are connected unless a
 * wall (actor tagged with Settings->WallTag) stands between them, so sound follows open
 * paths (doors, arches, cat-holes) and is stopped by walls. Propagation is a Dijkstra
 * search limited by the budget of the sound size.
 *
 * Put exactly one of these in the level and assign a UCatrunSoundSettings asset.
 */
UCLASS()
class CATRUN_API ASoundGridManager : public AActor
{
	GENERATED_BODY()

public:
	ASoundGridManager();

	// Finds the manager placed in the world (nullptr if none).
	UFUNCTION(BlueprintPure, Category = "Sound", meta = (WorldContext = "WorldContextObject"))
	static ASoundGridManager* Get(const UObject* WorldContextObject);

	// Samples the level floor and walls into the grid. Run again after moving walls/floors.
	UFUNCTION(CallInEditor, BlueprintCallable, Category = "Sound")
	void BuildGrid();

	// Makes a sound. Fills the propagation field and notifies every listener that can hear it.
	UFUNCTION(BlueprintCallable, Category = "Sound")
	bool EmitSound(const FCatrunSoundEvent& Event);

	// Budget left at a world location for the latest sound. <= 0 means the sound did not reach it.
	UFUNCTION(BlueprintPure, Category = "Sound")
	float GetRemainingBudgetAt(const FVector& WorldLocation) const;

	UFUNCTION(BlueprintPure, Category = "Sound")
	bool HasGrid() const { return GridWidth > 0 && GridHeight > 0; }

	// Called by ACatrunDoor when a door opens or closes.
	void NotifyDoorStateChanged(ACatrunDoor* Door);

	// Query helpers used by the visualizer and debug drawing.
	const FSoundField& GetLastField() const { return LastField; }
	FVector CellToWorld(int32 CellIndex) const;
	int32 WorldToCell(const FVector& WorldLocation) const;
	float GetCellSize() const;
	float GetFloorZ() const { return FloorZ; }
	int32 GetGridWidth() const { return GridWidth; }
	int32 GetGridHeight() const { return GridHeight; }
	bool IsCellWalkable(int32 CellIndex) const { return CellFlags.IsValidIndex(CellIndex) && CellFlags[CellIndex] != 0; }

	const UCatrunSoundSettings* GetSettings() const { return Settings; }

	UPROPERTY(BlueprintAssignable, Category = "Sound")
	FOnCatrunSoundEmitted OnSoundEmitted;

	// Draw walkable cells and blocked cell edges in the viewport while the game runs.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Debug")
	bool bDebugDrawGrid = false;

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual bool ShouldTickIfViewportsOnly() const override { return bDebugDrawGrid; }

	// Settings asset (DA_SoundSettings). A default object with default values is used when empty.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sound")
	TObjectPtr<UCatrunSoundSettings> Settings;

private:
	static constexpr int32 NumDirs = 8;

	bool IsEdgeOpen(int32 CellIndex, int32 Dir) const;
	bool IsCellBlocked(int32 CellIndex) const;
	int32 FindNearestWalkableCell(const FVector& WorldLocation, int32 MaxRing) const;
	void RunDijkstra(int32 SourceCell, float Budget, TArray<float>& OutDist) const;
	void RefreshDoorGates();
	void DebugDrawGrid() const;
	void CreateVisual();
	void UpdateVisual();

	// One flat quad per walkable cell. Opacity is driven per instance (custom data 0).
	UPROPERTY(Transient)
	TObjectPtr<UInstancedStaticMeshComponent> VisualISM;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> VisualMID;

	// Cell index -> instance index (INDEX_NONE for non-walkable cells).
	TArray<int32> CellToInstance;
	bool bVisualActive = false;

	// ---- Baked grid (serialized with the level) ----
	UPROPERTY()
	FVector GridOrigin = FVector::ZeroVector;

	UPROPERTY()
	float BakedCellSize = 25.f;

	UPROPERTY()
	float FloorZ = 0.f;

	UPROPERTY()
	int32 GridWidth = 0;

	UPROPERTY()
	int32 GridHeight = 0;

	// 1 = floor cell that is not inside a wall.
	UPROPERTY()
	TArray<uint8> CellFlags;

	// Travel cost multiplier per cell (floor material).
	UPROPERTY()
	TArray<float> CellCost;

	// Bit i set = the edge from this cell toward direction i is open (no wall between).
	UPROPERTY()
	TArray<uint8> EdgeMask;

	// ---- Runtime ----
	// Number of closed doors covering each cell. > 0 means the cell is blocked for sound.
	TArray<uint8> GateClosedCount;
	TMap<TWeakObjectPtr<ACatrunDoor>, TArray<int32>> DoorCells;

	FSoundField LastField;
};
