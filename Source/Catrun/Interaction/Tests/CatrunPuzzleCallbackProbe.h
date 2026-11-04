#pragma once
#include "CoreMinimal.h"
#include "Interaction/CatrunStatuePuzzle.h"
#include "Interaction/CatrunPuzzleRevealComponent.h"
#include "Sound/SoundTypes.h"
#include "CatrunPuzzleCallbackProbe.generated.h"

/** Reflection receiver exercises actual synchronous BP-style delegate reentrancy. */
UCLASS()
class UCatrunPuzzleCallbackProbe : public UObject
{
	GENERATED_BODY()
public:
	UPROPERTY() TObjectPtr<ACatrunStatuePuzzle> Puzzle;
	bool bResetOnSnap = false;
	bool bCancelOnFraming = false;
	int32 Counts[5] = {};
	int32 SoundCount = 0;
	UFUNCTION() void PuzzleEvent(FName Id, ECatrunStatueEvent Event, int32 Revision)
	{
		++Counts[static_cast<int32>(Event)];
		if (bResetOnSnap && Event==ECatrunStatueEvent::SnapStarted) Puzzle->ResetStatue(Id);
	}
	UFUNCTION() void RevealEvent(FName Id, ECatrunPuzzleRevealPhase Phase, int32 Session)
	{
		if (bCancelOnFraming && Phase==ECatrunPuzzleRevealPhase::ToGate) Puzzle->Reveal->CancelReveal();
	}
	UFUNCTION() void SoundEvent(const FCatrunSoundEvent& Event,float Budget) { ++SoundCount; }
};
