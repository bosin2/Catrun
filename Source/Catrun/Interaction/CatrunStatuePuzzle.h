#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "GameFramework/Actor.h"
#include "CatrunStatuePuzzle.generated.h"

class ACharacter;
class UCatrunPuzzleRevealComponent;

UENUM(BlueprintType)
enum class ECatrunStatueEvent : uint8 { SnapStarted, Seated, GateOpening, Completed, Reset };
DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FCatrunStatueEvent, FName, PuzzleId, ECatrunStatueEvent, Event, int32, Revision);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FCatrunPuzzleCheckpointRestored, FName, PuzzleId);

/** Shared tuning for the Stage 2 statue puzzles; level links only contain placement references. */
UCLASS(BlueprintType)
class CATRUN_API UCatrunStatuePuzzleSettings : public UDataAsset
{
	GENERATED_BODY()
public:
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Push", meta=(ClampMin="1"))
	float PushSpeed = 100.f;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Push", meta=(ClampMin="1")) float PushAcceleration = 160.f;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Push", meta=(ClampMin="1")) float PushDeceleration = 240.f;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Push", meta=(ClampMin="0"))
	float ContactDistance = 12.f;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Push")
	bool bRequireInteractKey = false;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Plate", meta=(ClampMin="1"))
	float ActivationTolerance = 18.f;
	/** ActivationTolerance remains serialized for old assets; seating uses overlap and axis tolerances. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Plate", meta=(ClampMin="0.5", ClampMax="1")) float SeatingOverlap = .8f;
	/** Allows a full stop from a perpendicular push before aligning on the final push axis. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Plate", meta=(ClampMin="0")) float SocketAxisTolerance = 24.f;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Plate", meta=(ClampMin="0")) float SocketHeightTolerance = 12.f;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Plate", meta=(ClampMin="0"))
	float PlateTravel = 2.f;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Gate", meta=(ClampMin="1"))
	float GateTravel = 280.f;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Gate", meta=(ClampMin="1"))
	float GateSpeed = 140.f;
	/** GateTravel is a minimum downward distance; actual mesh height plus clearance wins. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Gate", meta=(ClampMin="0.1")) float GateFloorClearance = 4.f;
};

USTRUCT(BlueprintType)
struct FCatrunStatuePuzzleLink
{
	GENERATED_BODY()
	UPROPERTY(EditAnywhere, BlueprintReadOnly)
	FName PuzzleId;
	UPROPERTY(EditAnywhere, BlueprintReadOnly)
	TObjectPtr<AActor> Statue;
	UPROPERTY(EditAnywhere, BlueprintReadOnly)
	TObjectPtr<AActor> Plate;
	UPROPERTY(EditAnywhere, BlueprintReadOnly)
	TObjectPtr<AActor> Gate;
	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly)
	bool bPressed = false;
	/** Optional world XY half extents of the contact base; zero derives from the actor bounds. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly) FVector2D ContactHalfExtent = FVector2D::ZeroVector;
	/** Optional world cardinal seating axis. Zero derives from original statue -> plate. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly) FVector SocketAxis = FVector::ZeroVector;
	/** Offset from the gate's authored minimum Z to the floor/base plane. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly) float GateFloorOffset = 0.f;
	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly) float RequiredGateTravel = 0.f;
	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly) float GateOffset = 0.f;
	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly) bool bCompleted = false;
	/** A latched solve waits here while an ordinary bell/basket owns the player. */
	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly) bool bRevealPending = false;
	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly) int32 Revision = 0;

	FTransform InitialStatue;
	FVector InitialPlate = FVector::ZeroVector;
	FVector InitialGate = FVector::ZeroVector;
	FVector StatueExtent = FVector(60,60,75);
	FVector StatueCenterOffset = FVector(0,0,75);
	FBox InitialGateBounds = FBox(ForceInit);
	FBox InitialPlateBounds = FBox(ForceInit);
	FVector SeatLocation = FVector::ZeroVector;
	FVector SeatingAxis = FVector::ForwardVector;
	FVector PushVelocity = FVector::ZeroVector;
	bool bDrivenThisFrame = false;
	bool bSeating = false;
	bool bGateOpening = false;
};

/** Keeps existing Stage 2 meshes/placements. C++ owns push/plate/collision rules; BP owns effects. */
UCLASS()
class CATRUN_API ACatrunStatuePuzzle : public AActor
{
	GENERATED_BODY()
public:
	ACatrunStatuePuzzle();
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Puzzle")
	TObjectPtr<UCatrunStatuePuzzleSettings> Settings;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Puzzle")
	TArray<FCatrunStatuePuzzleLink> Links;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Puzzle") TObjectPtr<UCatrunPuzzleRevealComponent> Reveal;
	/** Revision changes on reset; callbacks must retain it to reject stale presentation. */
	UPROPERTY(BlueprintAssignable, Category="Puzzle") FCatrunStatueEvent OnPuzzleEvent;
	/** Refreshes persistent presentation after a checkpoint without replaying the solve. */
	UPROPERTY(BlueprintAssignable, Category="Puzzle") FCatrunPuzzleCheckpointRestored OnCheckpointRestored;

	UFUNCTION(BlueprintCallable, Category="Puzzle")
	void InitializePuzzle();
	UFUNCTION(BlueprintCallable, Category="Puzzle")
	bool TryPushStatue(int32 Index, ACharacter* Cat, FVector InputDirection, float DeltaSeconds);
	UFUNCTION(BlueprintCallable, Category="Puzzle")
	void UpdatePlatesAndGates(float DeltaSeconds);
	/** Restore all statues for scripted/debug resets; gates close only when clear. */
	UFUNCTION(BlueprintCallable, Category="Puzzle")
	bool ResetPuzzle();
	/** Restore only the statue linked to a room's recovery pedestal. */
	UFUNCTION(BlueprintCallable, Category="Puzzle")
	bool ResetStatue(FName PuzzleId);
	UFUNCTION(BlueprintImplementableEvent, Category="Puzzle")
	void OnPlateChanged(FName PuzzleId, bool bPressed);

	UFUNCTION(BlueprintPure, Category="Puzzle") float GetSeatingOverlap(int32 Index) const;
	UFUNCTION(BlueprintPure, Category="Puzzle") bool IsPuzzleSeated(FName PuzzleId) const;
	/** Exact integration of a constant acceleration segment, including reaching target speed mid-frame. */
	static float IntegratePushSpeed(float& Speed, float Target, float Acceleration, float DeltaSeconds);
	/** Current world boxes for both sound and armor routing. Fully recessed gates cease blocking. */
	void GetObstacleBounds(TArray<FBox>& OutBounds) const;
	/** Recreate the practice room solve on a capture restart without gameplay solve events. */
	bool RestoreStage2EntryCheckpoint(FVector& OutGateLocation);

private:
	bool ResetStatues(const TArray<int32>& Indices);
	bool CanMoveStatue(const FCatrunStatuePuzzleLink& Link, const FVector& Delta, const AActor* Cat) const;
	bool IsGateClear(const FCatrunStatuePuzzleLink& Link, float NewOffset) const;
	bool IsGameplayAvailable() const;
	bool TrySeat(int32 Index);
	bool MoveStatue(FCatrunStatuePuzzleLink& Link, const FVector& Delta, const AActor* IgnoredCat);
	bool Broadcast(int32 Index, ECatrunStatueEvent Event, int32 ExpectedRevision);
	void NotifyObstaclesChanged();
	bool bInitialized = false;
	bool bUpdating = false;
	bool bResetting = false;
};
