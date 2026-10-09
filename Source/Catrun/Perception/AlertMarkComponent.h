#pragma once

#include "CoreMinimal.h"
#include "Components/TextRenderComponent.h"
#include "AlertMarkComponent.generated.h"

/**
 * The "!" that pops up above a monster when it notices the cat.
 *
 * It is a plain world text for now. When the team has an exclamation icon or animation, only
 * this component needs to change; the monsters just call Show().
 */
UCLASS(ClassGroup = (Catrun), meta = (BlueprintSpawnableComponent))
class CATRUN_API UCatrunAlertMarkComponent : public UTextRenderComponent
{
	GENERATED_BODY()

public:
	UCatrunAlertMarkComponent();

	// Shows the mark for Duration seconds.
	UFUNCTION(BlueprintCallable, Category = "Alert")
	void Show(float Duration);

	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

private:
	float TimeLeft = 0.f;
};
