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
	// Pawn object channels (cat, armor, candle capsules) intentionally do not occlude either LOS or display.
	// Components registered in UCatrunSightBlockerSubsystem also occlude by their simple collision.
	CATRUN_API float SightDistance(const UWorld& World, const FVector& From, const FVector& To, const AActor* Observer, const AActor* Target = nullptr);
	CATRUN_API bool HasDirectSight(const AActor& Observer, const AActor& Target, float Height);
}
