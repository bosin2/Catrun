#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "CatrunCatStateComponent.generated.h"

/**
 * Watches what the cat is doing, without changing the cat's blueprints (it only reads the
 * blueprint variables by name). Added to the cat automatically by ASoundGridManager.
 *
 * It does two jobs:
 *  1. Footsteps (design doc 3.3). Sneaking (Ctrl) is silent, walking makes a small sound,
 *     running (Shift) a medium one. The bell (loudest) is made by UCatrunBellComponent.
 *  2. Hideout entry. While the cat plays the "get into a hideout" animation it cannot be
 *     caught (it is not hidden yet, but it must not be grabbed in the middle of hiding).
 */
UCLASS(ClassGroup = (Catrun))
class CATRUN_API UCatrunCatStateComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UCatrunCatStateComponent();

	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

	// True from the start of the "get into a hideout" animation until the cat is hidden.
	bool IsEnteringHideout() const { return bEnteringHideout; }

private:
	void UpdateFootsteps(float DeltaTime);
	void UpdateHideEntry();
	void EmitFootstep(bool bRunning);

	bool ReadCatBool(const TCHAR* VariableName) const;
	bool ReadActionsBool(const TCHAR* VariableName) const;
	bool HasBasket() const;
	UActorComponent* FindCatActions() const;

	TWeakObjectPtr<UActorComponent> CatActions;

	float StepTimer = 0.f;
	int32 LastMoveMode = -1; // for the log: 0 sneak, 1 walk, 2 run

	bool bEnteringHideout = false;
	bool bLeavingHideout = false; // hidden, or on the way out: not an entry
	bool bWasBusy = false;
};
