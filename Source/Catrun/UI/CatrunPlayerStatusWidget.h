#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "CatrunPlayerStatusWidget.generated.h"

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
