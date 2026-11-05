#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "InputCoreTypes.h"
#include "CatrunBellComponent.generated.h"

class UInputAction;
class UEnhancedInputComponent;
class UEnhancedInputLocalPlayerSubsystem;
class UInputMappingContext;
class UCatrunSoundSettings;
class UWidgetComponent;

/**
 * Turns the cat's bell into a sound the monsters can hear.
 *
 * The cat blueprint already has a component (BP_CatActions) that plays the bell animation and
 * sound and then calls its event dispatcher "OnBellRung". This component listens to that
 * dispatcher, so the existing blueprints stay untouched and their cooldown and "no bell while
 * hiding" rules apply automatically.
 *
 * If the cat has no such component (for example an older cat blueprint), the bell key below
 * is used instead.
 *
 * ASoundGridManager adds this component to the player pawn at runtime.
 */
UCLASS(ClassGroup = (Catrun), meta = (BlueprintSpawnableComponent))
class CATRUN_API UCatrunBellComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UCatrunBellComponent();

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

	// Makes the bell sound at the cat's position. Fails during the cooldown (key mode only).
	UFUNCTION(BlueprintCallable, Category = "Bell")
	bool TryRing();

	// Legacy serialized field retained for asset compatibility. Runtime fallback uses the effective Bell settings key.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bell")
	FKey FallbackBellKey = EKeys::SpaceBar;

	// Set false to mute the bell from code (key mode only).
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Bell")
	bool bCanRing = true;

	UFUNCTION(BlueprintPure, Category = "Bell")
	float GetCooldownRemaining() const;

	UFUNCTION(BlueprintPure, Category = "Bell")
	bool IsListeningToCatActions() const { return bListeningToCatActions; }

private:
	// Called by the cat's OnBellRung dispatcher (no parameters).
	UFUNCTION()
	void HandleBellRung();

	// Finds the cat's BP_CatActions component and subscribes to OnBellRung.
	bool BindToCatActions();

	// True when the cat's own hiding logic says it is hiding right now.
	bool IsCatHiding() const;

	// Emits the Large "Minion" bell sound at the cat's position.
	bool EmitBellSound();
	void ShowBellIndicator(const UCatrunSoundSettings& Settings);
	void UpdateBellIndicator(float DeltaTime);
	void HideBellIndicator();
	bool ShouldSuppressBellIndicator() const;

	UPROPERTY(Transient)
	TObjectPtr<UWidgetComponent> BellIndicator;

	float BellIndicatorRemaining = 0.f;
	float BellIndicatorFadeDuration = 0.f;

	// No-bell zones (the cat hole): while the cat is inside one, the bell key is taken over by a
	// context of our own that does nothing but show the notice. The cat's blueprint then never
	// receives the bell input, so there is no bell animation, sound or wave either.
	void UpdateBellBlock();
	void BuildBlockContext();

	UFUNCTION()
	void HandleBlockedBellPressed();

	UPROPERTY(Transient)
	TObjectPtr<UInputMappingContext> BlockContext;

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> BlockAction;

	FKey CachedBlockBellKey;
	TWeakObjectPtr<UEnhancedInputLocalPlayerSubsystem> BlockInputSubsystem;
	TWeakObjectPtr<UEnhancedInputComponent> BlockInputComponent;
	uint32 BlockBindingHandle = 0;
	bool bBlockContextBuilt = false;
	bool bBlockActive = false;
	FDelegateHandle BindingsChangedHandle;

	TWeakObjectPtr<UActorComponent> CatActions;
	bool bListeningToCatActions = false;
	double LastRingTime = -1000.0;
};
