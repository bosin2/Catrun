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
	virtual void NativeConstruct() override;
	virtual void NativeTick(const FGeometry& Geometry, float DeltaSeconds) override;

	UPROPERTY(meta=(BindWidgetOptional)) TObjectPtr<UProgressBar> StaminaBar;
	UPROPERTY(meta=(BindWidgetOptional)) TObjectPtr<UProgressBar> BellProgress;
	UPROPERTY(meta=(BindWidgetOptional)) TObjectPtr<UTextBlock> StaminaText;
	UPROPERTY(meta=(BindWidgetOptional)) TObjectPtr<UTextBlock> BellRemainingText;
	UPROPERTY(meta=(BindWidgetOptional)) TObjectPtr<UTextBlock> BellReasonText;
	UPROPERTY(meta=(BindWidgetOptional)) TObjectPtr<UTextBlock> ClockText;
	UPROPERTY(EditDefaultsOnly, Category="Appearance") FLinearColor StaminaColor = FLinearColor(.44f,.65f,.46f,1.f);
	UPROPERTY(EditDefaultsOnly, Category="Appearance") FLinearColor BellColor = FLinearColor(.84f,.65f,.34f,1.f);
	UPROPERTY(EditDefaultsOnly, Category="Appearance") FLinearColor BlockedColor = FLinearColor(.42f,.35f,.32f,1.f);
	UPROPERTY(EditDefaultsOnly, Category="Appearance") FLinearColor ClockColor = FLinearColor(.91f,.87f,.77f,1.f);
	UPROPERTY(EditDefaultsOnly, Category="Appearance") FLinearColor WarningColor = FLinearColor(1.f,.64f,.24f,1.f);
	UPROPERTY(EditDefaultsOnly, Category="Appearance") FLinearColor UrgentColor = FLinearColor(1.f,.27f,.24f,1.f);
private:
	float RefreshDelay = 0.f;
};
