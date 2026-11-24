#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "CatrunRestartSubsystem.generated.h"

class APawn;
class APlayerController;
DECLARE_MULTICAST_DELEGATE_OneParam(FCatrunCatchOwnerChanged, UObject*);

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
	bool TryBeginCatch(UObject* Owner);
	bool TryBeginCatch() { return TryBeginCatch(this); }
	bool IsCatching() const { return bCatching; }
	bool IsCatchOwner(const UObject* Owner) const { return bCatching && Owner && CatchOwner.Get(true) == Owner; }
	UObject* GetCatchOwner() const { return CatchOwner.Get(); }
	// A rejected or stale contender cannot release another presentation's reservation.
	void CancelCatch(UObject* Owner);
	void CancelCatch() { CancelCatch(this); }
	void CancelCaptureRestart(UObject* Owner);
	FCatrunCatchOwnerChanged OnCatchOwnerChanged;
	virtual void Deinitialize() override;

	// Recovery for an impossible safe placement. Queued after temporary-action cleanup.
	bool ScheduleRecoveryRestart(float FadeInDuration = .5f, TFunction<void()> RestoreAfterFailure = {});
	bool HasRecoveryRestartPending() const { return bRecoveryScheduled; }
	bool HasBlockedPawnRecovery() const;
	bool HasBlockedPawnRecovery(const APawn* Pawn) const;
	void ReportBlockedPawnRecovery(APawn& Pawn);

	bool BeginStageTimeout();

	// Fades the screen of the cat's player to black (and keeps it black).
	void FadeOut(APawn* Cat, float Duration);

	// Queue an owned same-map request. False means no request was accepted; Failure runs only for a later same-world failure.
	bool RestartLevel(float FadeInDuration, TFunction<void(const FString&)> Failure = {}, bool bIsCaptureRestart = false);

	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;

private:
	bool CanRecoverWorld() const;
	void StartTimeoutFade();
	void CommitTimeoutRestart();
	void ReleaseTimeoutPresentation();
	bool bRecoveryScheduled = false;
	FTimerHandle RecoveryTimer;
	TWeakObjectPtr<APawn> BlockedRecoveryPawn;
	bool bCatching = false;
	TWeakObjectPtr<UObject> CatchOwner;
	FTimerHandle TimeoutTimer;
	TWeakObjectPtr<APlayerController> TimeoutController;
	bool bTimeoutFadeStarted = false;
};
