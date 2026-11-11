#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "CatrunRestartSubsystem.generated.h"

/**
 * Handles the failure restart when an armor catches the cat: fades the screen to black, starts the
 * level again and fades back in. One exists per game world.
 *
 * The game-instance flow session carries a single-use restart/fade request across level reloads.
 * It cannot leak into another PIE instance or a fresh game.
 */
UCLASS()
class CATRUN_API UCatrunRestartSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	static UCatrunRestartSubsystem* Get(const UObject* WorldContextObject);

	// The first armor to catch the cat gets true. Others get false, so only one catch plays.
	bool TryBeginCatch();
	bool IsCatching() const { return bCatching; }
	// Only the component that successfully acquired TryBeginCatch may release it.
	void CancelCatch() { bCatching = false; }

	// Recovery for an impossible safe placement. Queued after temporary-action cleanup.
	bool ScheduleRecoveryRestart(float FadeInDuration = .5f);
	bool HasRecoveryRestartPending() const { return bRecoveryScheduled; }

	// Fades the screen of the cat's player to black (and keeps it black).
	void FadeOut(APawn* Cat, float Duration);

	// Queue an owned same-map request. False means no request was accepted; Failure runs only for a later same-world failure.
	bool RestartLevel(float FadeInDuration, TFunction<void(const FString&)> Failure = {});

	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;

private:
	bool CanRecoverWorld() const;
	bool bRecoveryScheduled = false;
	FTimerHandle RecoveryTimer;
	bool bCatching = false;
};
