#pragma once
#include "CoreMinimal.h"
#include "Sound/SoundTypes.h"

namespace CatrunPerception
{
	inline bool AcceptSound(bool bNearOrCapture, bool bInvestigating, bool bLooking,
		ECatrunSoundSize Current, ECatrunSoundSize Incoming)
	{
		return !bNearOrCapture && (!bInvestigating || bLooking || uint8(Incoming) > uint8(Current));
	}
	CATRUN_API bool HasDirectSight(const AActor& Observer, const AActor& Target, float Height);
}
