#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "CatrunRestartSubsystem.generated.h"

/**
 * Handles the failure restart when an armor catches the cat: fades the screen to black, starts the
 * level again and fades back in. One exists per game world.
 *
 * The level is opened again, so a new world (and a new subsystem) is created. The "fade in
 * after the restart" request is therefore kept in a static variable that survives the level change.
 */
UCLASS()
class CATRUN_API UCatrunRestartSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	static UCatrunRestartSubsystem* Get(const UObject* WorldContextObject);

	// The first armor to catch the cat gets true. Others get false, so only one catch plays.
	bool TryBeginCatch();

	// Fades the screen of the cat's player to black (and keeps it black).
	void FadeOut(APawn* Cat, float Duration);

	// Opens the current level again; the new level fades in from black.
	void RestartLevel(float FadeInDuration);

	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;

private:
	bool bCatching = false;
};
