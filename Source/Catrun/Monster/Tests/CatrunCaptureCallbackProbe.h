#pragma once
#include "CoreMinimal.h"
#include "Monster/CatrunCapturePresentationComponent.h"
#include "Sound/SoundTypes.h"
#include "GameFramework/Actor.h"
#include "CatrunCaptureCallbackProbe.generated.h"

// Reflection receiver for automation exercising the real BlueprintAssignable multicast boundary.
UCLASS(Transient)
class UCatrunCaptureCallbackProbe : public UObject
{
	GENERATED_BODY()
public:
	UPROPERTY() TObjectPtr<UCatrunCapturePresentationComponent> Capture;
	UPROPERTY() TObjectPtr<APawn> Cat;
	UPROPERTY() TObjectPtr<UCatrunSoundSettings> Settings;
	ECatrunCapturePhase AbortAt = ECatrunCapturePhase::Fading;
	bool bArmed = true;
	bool bReplaceSession = false;
	bool bReplacementAccepted = false;
	int32 Calls = 0;
	UFUNCTION() void PhaseChanged(ECatrunCapturePhase Phase, int32 SessionId)
	{
		if (!bArmed || Phase != AbortAt) return;
		bArmed = false;
		++Calls;
		Capture->AbortCapture();
		if (bReplaceSession) bReplacementAccepted = Capture->BeginCapture(Cat, Settings);
	}
};

// Real reflected listener lets queue tests observe deliveries through Execute_OnSoundHeard.
UCLASS(Transient)
class ACatrunSoundDeliveryProbe : public AActor, public ICatrunSoundListener
{
	GENERATED_BODY()
public:
	ACatrunSoundDeliveryProbe() { SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root"))); }
	virtual ECatrunSoundTarget GetListenerGroup_Implementation() const override { return ECatrunSoundTarget::Minion; }
	TArray<FCatrunSoundEvent> Received;
	TArray<float> Budgets;
	TFunction<void()> OnDelivery;
	virtual void OnSoundHeard_Implementation(const FCatrunSoundEvent& Event, float Budget) override
	{
		Received.Add(Event); Budgets.Add(Budget);
		if (OnDelivery) OnDelivery();
	}
};
