#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CatrunNoBellZone.generated.h"

class UBoxComponent;

/**
 * An area where the bell may not be rung (for example the cat hole). Place it in the level and
 * scale the box over the area. The bell is blocked as soon as any part of the cat's body is
 * inside the box. The box is invisible in the game.
 */
UCLASS()
class CATRUN_API ACatrunNoBellZone : public AActor
{
	GENERATED_BODY()

public:
	ACatrunNoBellZone();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "NoBellZone")
	TObjectPtr<UBoxComponent> Box;

	// True when Cat touches any no-bell zone of its world.
	static bool IsBellForbidden(const AActor& Cat);

	// True when the cat's body (a circle seen from above) touches this zone.
	bool Touches(const AActor& Cat) const;
};
