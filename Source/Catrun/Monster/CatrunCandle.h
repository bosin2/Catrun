#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CatrunCandle.generated.h"

class ASoundGridManager;
class UAnimationAsset;
class UCatrunAlertMarkComponent;
class UCatrunSoundSettings;
class UCatrunVisionFanComponent;
class USkeletalMeshComponent;
class ACatrunCandle;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnCandleSpottedCat, ACatrunCandle*, Candle, AActor*, Cat);

/**
 * Floating candle monster: it watches over a place and spots the cat. It never moves.
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
 *  - Patrol: the cone sweeps. Orange display.
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

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Candle")
	TObjectPtr<USkeletalMeshComponent> Body;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Candle")
	TObjectPtr<UCatrunVisionFanComponent> Sight;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Candle")
	TObjectPtr<UCatrunAlertMarkComponent> AlertMark;

	// True while the candle is following the cat with its view.
	UFUNCTION(BlueprintPure, Category = "Candle")
	bool IsTrackingCat() const { return bTracking; }

protected:
	virtual void BeginPlay() override;

private:
	// The settings of the level's sound system (found once, then remembered). nullptr until the
	// sound system exists.
	const UCatrunSoundSettings* GetSettings();
	TWeakObjectPtr<ASoundGridManager> CachedManager;

	// Patrol: moves the cone one step along its back-and-forth path.
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
