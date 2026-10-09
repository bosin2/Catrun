#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Grid/CatrunGridData.h"
#include "SoundTypes.h"
#include "SoundGridManager.generated.h"

class ACatrunDoor;
class UCatrunSoundSettings;
class USoundWaveVisual;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnCatrunSoundEmitted, const FCatrunSoundEvent&, Event, float, Budget);

// A sound that is on its way to a listener. It is delivered when the wave reaches the listener.
USTRUCT()
struct FPendingSound
{
	GENERATED_BODY()

	UPROPERTY()
	TWeakObjectPtr<AActor> Listener;

	UPROPERTY()
	FCatrunSoundEvent Event;

	// Sound budget left at the listener (always > 0).
	UPROPERTY()
	float RemainingBudget = 0.f;

	// World time at which the wave reaches the listener.
	double ArrivalTime = 0.0;
};

/**
 * The sound system of a level. Place exactly one in the level and assign DA_SoundSettings.
 *
 * It owns the baked grid and does four things:
 *  1. Bakes the grid from the level geometry (BuildGrid).
 *  2. Spreads a sound over the grid (EmitSound) and draws the wave (USoundWaveVisual).
 *  3. Tells every listener that can hear the sound, at the moment the wave reaches it.
 *  4. Keeps track of doors: closed doors block sound, armors open them.
 *
 * The heavy parts live in separate files: FCatrunGridData (grid), CatrunSoundPropagation
 * (spreading), USoundWaveVisual (drawing), CatrunArmorPath (armor walking).
 */
UCLASS()
class CATRUN_API ASoundGridManager : public AActor
{
	GENERATED_BODY()

public:
	ASoundGridManager();

	// The manager placed in the level, or nullptr.
	UFUNCTION(BlueprintPure, Category = "Sound", meta = (WorldContext = "WorldContextObject"))
	static ASoundGridManager* Get(const UObject* WorldContextObject);

	// Builds the grid from the level floors and walls. Run it again after moving walls/floors.
	UFUNCTION(CallInEditor, BlueprintCallable, Category = "Sound")
	void BuildGrid();

	// Makes a sound. Calculates where it reaches and starts the wave. Listeners are told
	// when the wave arrives at them, not instantly.
	UFUNCTION(BlueprintCallable, Category = "Sound")
	bool EmitSound(const FCatrunSoundEvent& Event);

	// Sound budget left at a location for the latest sound (<= 0 = not reached).
	UFUNCTION(BlueprintPure, Category = "Sound")
	float GetRemainingBudgetAt(const FVector& WorldLocation) const;

	UFUNCTION(BlueprintPure, Category = "Sound")
	bool HasGrid() const { return Grid.IsValid(); }

	// Called by ACatrunDoor when it opens or closes.
	void NotifyDoorStateChanged(ACatrunDoor* Door);

	// Adds every door that is currently closed to OutDoors.
	void GetClosedDoors(TArray<ACatrunDoor*>& OutDoors) const;

	const FCatrunGridData& GetGrid() const { return Grid; }
	const UCatrunSoundSettings* GetSettings() const { return Settings; }

	UPROPERTY(BlueprintAssignable, Category = "Sound")
	FOnCatrunSoundEmitted OnSoundEmitted;

	// Draw the grid (floor cells and wall edges) in the viewport. For checking the bake.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Debug")
	bool bDebugDrawGrid = false;

	// Debug: draw the detection circle of every armor on the floor. Off in the real game; the
	// armor's detection circle is not shown to the player.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Debug")
	bool bDebugShowArmorDetection = false;

	// Debug: show the current action as a text above every armor ("Walking", "Turning", ...).
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Debug")
	bool bDebugShowArmorLabel = false;

	// Add a bell component to the player's pawn automatically, so the player blueprint
	// does not have to be edited.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sound")
	bool bAutoAttachBell = true;

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual bool ShouldTickIfViewportsOnly() const override { return bDebugDrawGrid; }

	// Settings asset (DA_SoundSettings). Default values are used when empty.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sound")
	TObjectPtr<UCatrunSoundSettings> Settings;

private:
	void RefreshDoorGates();
	void DeliverPendingSounds();
	void AttachBellToPlayer();
	void DebugDrawGrid() const;

	// The baked grid, saved with the level.
	UPROPERTY()
	FCatrunGridData Grid;

	UPROPERTY(VisibleAnywhere, Category = "Sound")
	TObjectPtr<USoundWaveVisual> WaveVisual;

	UPROPERTY(Transient)
	TArray<FPendingSound> PendingSounds;

	// Path length from the latest sound to every cell (CatrunSoundPropagation::Unreached = not reached).
	TArray<float> LastDistance;
	TArray<float> PictureDistance; // like LastDistance, but reaches a little further (for the picture)
	float LastBudget = 0.f;

	// Number of closed doors covering each cell. > 0 blocks sound.
	TArray<uint8> ClosedGateCells;
	TMap<TWeakObjectPtr<ACatrunDoor>, TArray<int32>> DoorCells;

	bool bBellAttached = false;
};
