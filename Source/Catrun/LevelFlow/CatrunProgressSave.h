#pragma once

#include "CoreMinimal.h"
#include "GameFramework/SaveGame.h"
#include "CatrunProgressSave.generated.h"

/** Stage-start progress, chapter unlocks and the Stage1 clock. */
UCLASS()
class CATRUN_API UCatrunProgressSave : public USaveGame
{
	GENERATED_BODY()
public:
	// UE delta serialization omitted the default version in existing schema 3 slots.
	static constexpr int32 CurrentSchemaVersion = 4;
	static constexpr int32 MaxRemainingMs = 86400000;
	static constexpr int32 AllPuzzleBits = 7;
	UPROPERTY(SaveGame) int32 SchemaVersion = 3;
	UPROPERTY(SaveGame) FName StageId;
	UPROPERTY(SaveGame) FName HighestUnlockedStageId;
	UPROPERTY(SaveGame) FDateTime SavedAtUtc;
	UPROPERTY(SaveGame) bool bTutorialOnboardingCompleted = false;
	UPROPERTY(SaveGame) int32 Stage1RemainingMs = -1;
	// Legacy v4 tags stay readable. New checkpoints leave them at these defaults.
	UPROPERTY(SaveGame) int32 Stage2RemainingMs = -1;
	UPROPERTY(SaveGame) int32 Stage2SolvedMask = 0;
	bool IsSupported() const;
	bool HasCompletedOnboarding() const { return SchemaVersion >= 2 && bTutorialOnboardingCompleted; }
	static const UCatrunProgressSave* Decode(const TArray<uint8>& Data);
};
