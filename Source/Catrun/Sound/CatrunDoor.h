#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CatrunDoor.generated.h"

class UBoxComponent;
class UStaticMeshComponent;

/**
 * Door placed in a wall opening. A closed door stops sound; a minion can open it.
 * The cat cannot open doors (design doc 3.2). Open doors stay open.
 *
 * GateBox must cover the opening (default 150 wide x 30 thick, matching the wall).
 * Visual open/close animation is done in a Blueprint child via OnDoorStateChanged.
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

	// Implement in a Blueprint child to play the open/close visuals.
	UFUNCTION(BlueprintImplementableEvent, Category = "Door")
	void OnDoorStateChanged(bool bNowOpen);

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Door")
	bool bStartOpen = false;

protected:
	virtual void BeginPlay() override;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Door")
	TObjectPtr<UStaticMeshComponent> DoorMesh;

	// Opening the sound grid treats as the doorway.
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Door")
	TObjectPtr<UBoxComponent> GateBox;

private:
	bool bIsOpen = false;
};
