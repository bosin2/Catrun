#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CatrunCandle.generated.h"

class UCapsuleComponent;
class ASoundGridManager;
class UAnimationAsset;
class UCatrunAlertMarkComponent;
class UCatrunSoundSettings;
class UCatrunVisionFanComponent;
class USkeletalMeshComponent;
class ACatrunCandle;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnCandleSpottedCat, ACatrunCandle*, Candle, AActor*, Cat);

/**
 * Floating candle monster: stationary by default, with optional per-instance patrol.
 *
 * Sight (design doc 4.1, as changed by the designer):
 *  - The candle faces ONE direction: the direction the actor faces in the level. That direction
 *    is the middle of a total view range (CandleTotalAngle, about 70 degrees).
 *  - The real view is a narrower cone (CandleConeAngle, about 30 degrees) that sweeps back and
 *    forth inside the total range, like a lighthouse beam. The candle's eyes look along the cone.
 *  - Walls, tall furniture and closed doors block the view.
 *  - Sound does not draw the candle's view any more.
 *
 * Two modes:
 *  - Patrol: the cone sweeps. Orange display. A candle that walks a route (bPatrolEnabled) does not
 *    sweep: it looks straight ahead along its walking direction, and turns back to the previous patrol
 *    point when a statue or an armor is in front of it.
 *  - Tracking: the moment the cone sees the cat it is spotted at once (no gauge): a "!" shows,
 *    the candle reacts, the cone turns red and FOLLOWS the cat (never beyond the total range).
 *    When the cat has been out of the cone for CandleLoseSightDelay seconds the candle goes back
 *    to patrol.
 *
 * All numbers are in the sound settings asset (DA_SoundSettings, categories "Candle" and "Sight").
 * What happens after spotting (mark, armors that come) is added later; the candle already tells
 * everybody through OnCatSpotted.
 */
UCLASS()
class CATRUN_API ACatrunCandle : public AActor
{
	GENERATED_BODY()

public:
	ACatrunCandle();

    virtual void Tick(float DeltaSeconds) override;
    void ForgetCorridorCat();
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Candle|Sight", meta=(ClampMin="-1", ClampMax="180", Units="Degrees"))
    float SweepHalfAngleOverride = -1.f;

	// Called once each time the candle starts to track the cat.
	UPROPERTY(BlueprintAssignable, Category = "Candle")
	FOnCandleSpottedCat OnCatSpotted;

	// Looping animation while watching.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Candle|Animation")
	TObjectPtr<UAnimationAsset> IdleAnim;

	// Played once when the cat is spotted.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Candle|Animation")
	TObjectPtr<UAnimationAsset> SpotReactAnim;

	// Turns the body so that its eyes look along the view cone. The eye bones (eye_l, eye_r) are
	// measured once at the start. Switch off to use BodyYawOffset only.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Candle")
	bool bAutoAlignEyes = true;

	// Extra turn (degrees) of the body on top of the automatic alignment, for fine tuning.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Candle")
	float BodyYawOffset = 0.f;

	// Turn off for candles that must not cause penalties (the tutorial bedroom, design doc 7.2).
	// The candle still spots the cat and reacts; only the consequences (mark, armors) are skipped.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Candle")
	bool bPenaltiesEnabled = true;

	// Show the floor display of the view cone.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Candle")
	bool bShowSightDisplay = true;

	// Attached to the original root: changing collision never shifts the authored mesh/origin.
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Candle|Collision")
	TObjectPtr<UCapsuleComponent> BlockingCapsule;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Candle")
	TObjectPtr<USkeletalMeshComponent> Body;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Candle")
	TObjectPtr<UCatrunVisionFanComponent> Sight;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Candle")
	TObjectPtr<UCatrunAlertMarkComponent> AlertMark;

	// Actor waypoints take precedence over relative points. Relative points use the BeginPlay transform.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Candle|Patrol") bool bPatrolEnabled = false;
	UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Candle|Patrol") TArray<TObjectPtr<AActor>> PatrolPoints;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Candle|Patrol", meta=(MakeEditWidget=true)) TArray<FVector> PatrolRelativePoints;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Candle|Patrol", meta=(ClampMin="0")) float PatrolSpeed = 65.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Candle|Patrol", meta=(ClampMin="0")) float PatrolPauseSeconds = 1.5f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Candle|Patrol") bool bPatrolLoop = false;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Candle|Patrol", meta=(ClampMin="1")) float PatrolFloorProbeDistance = 200.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Candle|Patrol", meta=(ClampMin="0")) float PatrolMaxFloorHeightChange = 12.f;
	// While walking a patrol route (bPatrolEnabled) the view does not sweep: it looks straight ahead.
	// On: "ahead" is the walking direction, and the candle turns in place toward its next point.
	// Off: "ahead" is the direction the actor was placed with in the level.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Candle|Patrol") bool bPatrolFaceTravelDirection = true;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Candle|Patrol", meta=(ClampMin="1", Units="DegreesPerSecond")) float PatrolTurnSpeed = 180.f;
	// A statue or armor this close ahead (cm, in front of the collision capsule) makes the candle turn
	// back and walk to the patrol point it came from, instead of waiting in front of it.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Candle|Patrol", meta=(ClampMin="0")) float PatrolEncounterDistance = 40.f;
	// Short stop when turning back from a statue/armor (the turn happens during this stop).
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Candle|Patrol", meta=(ClampMin="0")) float PatrolEncounterPause = .3f;

	// True while the candle is following the cat with its view.
	UFUNCTION(BlueprintPure, Category = "Candle")
	bool IsTrackingCat() const { return bTracking; }

protected:
	virtual void BeginPlay() override;

private:
	friend class FCatrunPuzzleSuspensionTest;
	friend class FCatrunCandlePatrolSafetyTest;
	friend class FCatrunCandleLocalSweepTest;
	friend class FCatrunCandlePatrolFacingTest;
	void ResetPatrol();
	void UpdatePatrol(float DeltaSeconds);
	bool TryPatrolStep(const FVector& Delta, AActor** OutBlocker = nullptr);
	// True when the candle walks a route (patrol enabled and at least one point).
	bool HasPatrolRoute() const;
	// The point the candle is walking to now (false when there is none).
	bool GetPatrolTarget(FVector& OutTarget) const;
	// Statues of the statue puzzles and armors make a patrolling candle turn back.
	bool IsPatrolEncounter(const AActor* Actor) const;
	// Looks PatrolEncounterDistance ahead along Direction for a statue or an armor.
	AActor* FindPatrolEncounter(const FVector& Direction) const;
	// Turn back toward the previous patrol point.
	void ReversePatrol();
	// Turns the actor toward Yaw at PatrolTurnSpeed. Returns true when it faces Yaw.
	bool TurnPatrolFacing(float Yaw, float DeltaSeconds);
	bool FindPatrolFloor(const FVector& CapsuleCenter, float& OutFloor) const;
	FTransform PatrolOrigin;
	int32 PatrolIndex = 0, PatrolStep = 1;
	float PatrolWaitLeft = 0.f;
	// The settings of the level's sound system (found once, then remembered). nullptr until the
	// sound system exists.
	const UCatrunSoundSettings* GetSettings();
	TWeakObjectPtr<ASoundGridManager> CachedManager;

	// How far behind the candle the point of the view cone is (cm), from CandleBodyWidth.
	float GetConeBackOffset(const UCatrunSoundSettings& Settings) const;

	// Patrol: moves the cone one step along its back-and-forth path.
    float GetSweepHalfAngle(const UCatrunSoundSettings& Settings) const;
    void UpdateSweep(float DeltaSeconds, const UCatrunSoundSettings& Settings);

	// Tracking: turns the cone toward the cat, but never beyond the total range.
	void TrackCat(float DeltaSeconds, const APawn& Cat, const UCatrunSoundSettings& Settings);

	// Checks if the cone sees the cat; starts and stops tracking.
	void CheckForCat(float DeltaSeconds, APawn* Cat, const UCatrunSoundSettings& Settings);
	void StartTracking(APawn& Cat, const UCatrunSoundSettings& Settings);
	void StopTracking(const UCatrunSoundSettings& Settings);

	// Measures where the eyes are on the mesh and sets AutoBodyYaw so they face the cone.
	void AlignBodyToEyes();

	void PlayAnimation(UAnimationAsset* Anim, bool bLoop);

	// Where the cone is now, as an angle (degrees) away from the candle's own direction.
	float SweepOffset = 0.f;
	float SweepDirection = 1.f;	// +1 or -1
	float PauseLeft = 0.f;		// seconds left to wait at the end of the sweep

	bool bTracking = false;
	float LoseSightTimer = 0.f;	// seconds the cat has been out of the cone while tracking
	bool bCatInView = false;	// the cat was inside the cone at the last check
	float LastTurnDirection = 0.f;	// which way the cone last turned while following the cat (+1 / -1)

	float AutoBodyYaw = 0.f;	// body turn that puts the eyes on the cone (from AlignBodyToEyes)
	bool bEyesAligned = false;
	bool bSightConfigured = false;
	float ReactTimeLeft = 0.f;	// time left of the spot reaction animation
};
