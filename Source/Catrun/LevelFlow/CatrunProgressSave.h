#pragma once

#include "CoreMinimal.h"
#include "GameFramework/SaveGame.h"
#include "CatrunProgressSave.generated.h"

/** Stage-start progress only. Unknown versions are deliberately not migrated implicitly. */
UCLASS()
class CATRUN_API UCatrunProgressSave : public USaveGame
{
	GENERATED_BODY()
public:
	UPROPERTY(SaveGame) int32 SchemaVersion = 3;
	UPROPERTY(SaveGame) FName StageId;
	UPROPERTY(SaveGame) FName HighestUnlockedStageId;
	UPROPERTY(SaveGame) FDateTime SavedAtUtc;
	UPROPERTY(SaveGame) bool bTutorialOnboardingCompleted = false;
	bool IsSupported() const { return SchemaVersion == 1 || SchemaVersion == 2 || SchemaVersion == 3; }
	bool HasCompletedOnboarding() const { return SchemaVersion >= 2 && bTutorialOnboardingCompleted; }
	static const UCatrunProgressSave* Decode(const TArray<uint8>& Data);
};
