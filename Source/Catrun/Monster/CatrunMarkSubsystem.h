#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "CatrunMarkSubsystem.generated.h"

class ACatrunArmor;
class ACatrunElevatorTransition;
class ACatrunStageExit;
class UPointLightComponent;
class UStaticMeshComponent;

/**
 * The candle mark (design doc 4.5). A candle that sees the cat puts a mark on it.
 *
 * While the cat is marked:
 *  - the closest armor knows where the cat really is and keeps coming for it,
 *  - a red orb floats above the cat so the player can see the mark.
 * A hideout or an accepted Stage1 portal departure clears the mark. Reloading the level
 * creates a fresh subsystem.
 *
 * Which armors follow, and the sound, are provisional (to be discussed with the team), so every
 * number is a setting in DA_SoundSettings ("Mark" category).
 */
UCLASS()
class CATRUN_API UCatrunMarkSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	static UCatrunMarkSubsystem* Get(const UObject* WorldContextObject);

	// Puts the mark on the cat (nothing happens if it is already marked).
    // Only the opted-in Stage1 doorway registers the local cat as a candidate.
    void ObserveCorridor(ACatrunStageExit& Exit, APawn& Cat);
    void LeaveCorridor(const ACatrunStageExit& Exit);
    void ObserveElevatorCorridor(ACatrunElevatorTransition& Elevator);
    void LeaveElevatorCorridor(const ACatrunElevatorTransition& Elevator);
    void RefreshCorridor();
    static bool IsExcludedFromPerception(const AActor* Subject);
    void ApplyMark(APawn& Cat);
	void ClearMark(const TCHAR* Reason);
	bool IsMarked() const { return bMarked; }
	/**
	 * Hides only the orb and its light while a presentation owns the screen (the capture close-up).
	 * The mark itself, the following armor and every timer are unchanged. Owners stack; the visual
	 * returns when the last live owner releases it.
	 */
	void SetVisualSuppressed(const UObject* Owner, bool bSuppressed);
	bool IsVisualSuppressed() const;
	bool IsVisualShown() const;

	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual bool IsTickable() const override { return bMarked && Super::IsTickable(); }
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;

private:
	friend class FCatrunPuzzleSuspensionTest;
	friend class FCatrunReleasedMarkFollowerTest;
	void CreateVisual(APawn& Cat);
	void DestroyVisual();
	void UpdateVisual();
	void ApplyVisualVisibility();
	void UpdateFollowingArmor(const APawn& Cat);
    void RefreshElevatorCorridor();
    void ForgetCorridorCat(APawn& Cat, const TCHAR* Reason);

    TWeakObjectPtr<ACatrunStageExit> Corridor;
    TWeakObjectPtr<APawn> CorridorCandidate;
    TWeakObjectPtr<ACatrunElevatorTransition> ElevatorCorridor;
    TWeakObjectPtr<APawn> ElevatorAdmittedCat;
    bool bCorridorAdmitted = false;
    bool bMarked = false;
	float FollowTimer = 0.f;

	TWeakObjectPtr<ACatrunArmor> FollowingArmor;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMeshComponent> Orb;

	UPROPERTY(Transient)
	TObjectPtr<UPointLightComponent> Light;

	float OrbHeight = 80.f;
	TArray<TWeakObjectPtr<const UObject>> VisualSuppressors;
};
