#pragma once

#include "Blueprint/UserWidget.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "CatrunMenuProgressWidget.generated.h"

/** Refreshes the main menu when asynchronous checkpoint work changes state. */
UCLASS(Abstract, Blueprintable)
class CATRUN_API UCatrunMenuProgressWidget : public UUserWidget
{
	GENERATED_BODY()

protected:
	virtual void NativeConstruct() override;
	virtual void NativeDestruct() override;
	virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;

	UFUNCTION(BlueprintImplementableEvent, Category="Catrun|Progress")
	void RefreshContinue();

private:
	UFUNCTION()
	void CheckpointChanged(ECatrunCheckpointState State);
	void RetryProgressRead();
	void RefreshMenu();
	/** Keeps one menu button focused for keyboard and gamepad. The highlight still appears only after navigation input. */
	void RestoreMenuFocus();
	TWeakObjectPtr<UWidget> LastFocusedButton;
	FTimerHandle ProgressReadTimer;

	TWeakObjectPtr<UCatrunFlowSession> BoundSession;
};
