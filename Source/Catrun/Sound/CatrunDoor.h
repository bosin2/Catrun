#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CatrunDoor.generated.h"

class UBoxComponent;
class UStaticMeshComponent;

/**
 * A door that is closed at the start. While closed it blocks sound and the cat's way.
 * A minion (the armor) opens it by walking up to it; the cat cannot open doors (design doc 3.2).
 * An opened door stays open.
 *
 * Setup:
 *  - Place the actor so that its origin is at the LEFT edge of the closed door (the pivot of
 *    the door leaf mesh), seen from the side where the actor stands when it faces the door.
 *  - Set the mesh of DoorMesh (and its scale, if the leaf needs one).
 *  - Move GateBox so that it covers the doorway; the sound grid uses it to find the doorway.
 *
 * How it opens: the door swings AWAY from whoever opens it, counter-clockwise seen from
 * above, with the hinge on the opener's LEFT hand side (the right part of the door moves to
 * the left in an arc). When the door is opened from a side (OpenFrom), the hinge is placed
 * accordingly and the leaf turns OpenYaw degrees. A closed door looks the same either way.
 * The armor's body is mirrored during its open-door animation so that it turns the same way.
 */
UCLASS()
class CATRUN_API ACatrunDoor : public AActor
{
	GENERATED_BODY()

public:
	ACatrunDoor();

	UFUNCTION(BlueprintPure, Category = "Door")
	bool IsOpen() const { return bIsOpen; }

	// Opens or closes the door without caring about who does it.
	UFUNCTION(BlueprintCallable, Category = "Door")
	void SetOpen(bool bNewOpen);

	// Opens the door for someone standing at OpenerLocation: the door swings away from them,
	// with its hinge on their right.
	void OpenFrom(const FVector& OpenerLocation);

	// Hand-driven opening: the door follows a point (the armor's hand) instead of a timer, so it
	// always matches the animation. BeginHandOpen starts it (hinge on the opener's left),
	// DriveWithPoint is called every frame with the hand's world position, and EndHandOpen lets
	// go: the door then finishes opening by itself.
	void BeginHandOpen(const FVector& OpenerLocation);
	void DriveWithPoint(const FVector& PointWorld);
	void EndHandOpen();

	// World box around the leaf (used to see which hand is close to the door).
	FBox GetLeafBounds() const;

	UBoxComponent* GetGateBox() const { return GateBox; }

	// World position of the middle of the doorway.
	FVector GetDoorwayCenter() const;

	// Direction (flat, length 1) that points straight out of the door leaf, perpendicular to
	// the doorway. Stand in front of the door along this line to face it head-on.
	FVector GetDoorNormal() const;

	// Implement in a Blueprint child for extra effects (sound, particles).
	UFUNCTION(BlueprintImplementableEvent, Category = "Door")
	void OnDoorStateChanged(bool bNowOpen);

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Door")
	bool bStartOpen = false;

	// Angle (degrees) the leaf turns around the hinge when opened. Negative = counter-clockwise
	// seen from above (the right part of the door swings to the left, away from the opener).
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Door")
	float OpenYaw = -90.f;

	// Seconds the door needs to open. The default matches the armor's open-door animation:
	// the door starts to move when the hand takes hold (frame 55) and is fully open when the
	// armor has pulled it open (frame 136): 81 frames at 30 fps = 2.7 seconds.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Door", meta = (ClampMin = "0.01"))
	float OpenDuration = 2.7f;

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Door")
	TObjectPtr<UStaticMeshComponent> DoorMesh;

	// The doorway the sound grid blocks while the door is closed.
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Door")
	TObjectPtr<UBoxComponent> GateBox;

private:
	// Turns the leaf to the closed or open angle at once.
	void SnapToState();

	// Puts the hinge on the left or the right edge of the doorway. The closed door looks the same.
	void SetHingeOnRight(bool bOnRight);

	bool bIsOpen = false;

	// Hand-driven opening state.
	bool bHandDriven = false;
	bool bHandReferenceSet = false;
	float HandReferenceAngle = 0.f;	// direction hinge -> hand when the hand took hold (degrees)
	float HandProgress = 0.f;		// 0 (closed) .. 1 (open); never goes back

	// The door mesh as placed in the level (hinge on the left), remembered at BeginPlay.
	FVector ClosedScale = FVector::OneVector;
	float LeafWidth = 150.f;
};
