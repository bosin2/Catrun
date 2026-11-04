#pragma once
#include "CoreMinimal.h"
#include "Monster/CatrunCapturePresentationComponent.h"
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
