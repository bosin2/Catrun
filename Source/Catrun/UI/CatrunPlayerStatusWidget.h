#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "CatrunPlayerStatusWidget.generated.h"

class ACatrunElevatorTransition;
class APawn;
class UProgressBar;
class UTextBlock;

/** Passive readout. Resource rules, cooldown and stage time belong to the gameplay owners. */
UCLASS(Abstract, Blueprintable)
class CATRUN_API UCatrunPlayerStatusWidget : public UUserWidget
{
	GENERATED_BODY()
protected:
	virtual void NativePreConstruct() override;
	virtual void NativeConstruct() override;
	virtual void NativeTick(const FGeometry& Geometry, float DeltaSeconds) override;
	virtual int32 NativePaint(const FPaintArgs& Args, const FGeometry& Geometry,
		const FSlateRect& CullingRect, FSlateWindowElementList& Elements, int32 LayerId,
		const FWidgetStyle& Style, bool bParentEnabled) const override;

	UPROPERTY(meta=(BindWidgetOptional)) TObjectPtr<UProgressBar> StaminaBar;
	UPROPERTY(meta=(BindWidgetOptional)) TObjectPtr<UProgressBar> BellProgress;
	UPROPERTY(meta=(BindWidgetOptional)) TObjectPtr<UTextBlock> StaminaText;
	UPROPERTY(meta=(BindWidgetOptional)) TObjectPtr<UTextBlock> BellRemainingText;
	UPROPERTY(meta=(BindWidgetOptional)) TObjectPtr<UTextBlock> BellReasonText;
	UPROPERTY(meta=(BindWidgetOptional)) TObjectPtr<UTextBlock> ClockText;
private:
	friend class FCatrunStatusPresentationTest;
	friend class FCatrunStatusClockPlacementTest;
	void UpdateClockPlacement(const APawn* Pawn, float DeltaSeconds);
	void ScanOverlays();
	void AnnounceTimeLimit(const APawn& Pawn);
	TWeakObjectPtr<AActor> TutorialExit;
	bool bTimeLimitAnnounced = false;
	TArray<TWeakObjectPtr<ACatrunElevatorTransition>> Elevators;
	TWeakObjectPtr<UUserWidget> LabelledKeyHint;
	float OverlayScanSeconds = 0.f;
	float ClockHoldSeconds = 0.f;
	float ClockOpacity = 1.f;
	float ClockDock = 0.f;
	bool bClockSpaceTaken = false;
	float StaminaFraction = 1.f;
	float BellFraction = 1.f;
	float TimeFraction = 1.f;
	float ClockWarningFraction = .25f;
	float ClockUrgentFraction = .10f;
	bool bTimed = false;
	bool bExhausted = false;
	bool bBellBlocked = false;
	bool bShowStatus = false;
};
