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
 *  - Place the actor so that its origin is at the HINGE of the door (like the door leaf mesh).
 *  - Set the mesh of DoorMesh (and its scale, if the leaf needs one).
 *  - Move GateBox so that it covers the doorway; the sound grid uses it to find the doorway.
 *  - OpenYaw is the angle the leaf swings to. Use the other sign to swing it the other way.
 */
UCLASS()
class CATRUN_API ACatrunDoor : public AActor
{
	GENERATED_BODY()

public:
	ACatrunDoor();

	UFUNCTION(BlueprintPure, Category = "Door")
	bool IsOpen() const { return bIsOpen; }

	UFUNCTION(BlueprintCallable, Category = "Door")
	void SetOpen(bool bNewOpen);

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

	// Angle (degrees) the leaf turns around the hinge when opened.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Door")
	float OpenYaw = -90.f;

	// Seconds the door needs to open.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Door", meta = (ClampMin = "0.01"))
	float OpenDuration = 0.7f;

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

	bool bIsOpen = false;
};
