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

	UFUNCTION(BlueprintImplementableEvent, Category="Catrun|Progress")
	void RefreshContinue();

private:
	UFUNCTION()
	void CheckpointChanged(ECatrunCheckpointState State);
	void RetryProgressRead();
	void RefreshMenu();
	FTimerHandle ProgressReadTimer;

	TWeakObjectPtr<UCatrunFlowSession> BoundSession;
};
