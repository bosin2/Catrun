#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CatrunPatrolPoint.generated.h"

class UStaticMeshComponent;

/**
 * A stop on an armor's patrol route. Place these in the level where the armor should walk and
 * list them (in walking order) in the armor's PatrolPoints. Only the location matters; the point
 * is invisible in the game.
 */
UCLASS()
class CATRUN_API ACatrunPatrolPoint : public AActor
{
	GENERATED_BODY()

public:
	ACatrunPatrolPoint();

	// How long (seconds) the armor waits here. Negative = use ArmorPatrolPause of the sound settings.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Patrol")
	float PauseSeconds = -1.f;

	// Marker that shows the point in the editor.
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Patrol")
	TObjectPtr<UStaticMeshComponent> Marker;
};
