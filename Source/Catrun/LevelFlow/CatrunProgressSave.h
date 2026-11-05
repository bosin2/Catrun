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
	UPROPERTY(SaveGame) int32 SchemaVersion = 2;
	UPROPERTY(SaveGame) FName StageId;
	UPROPERTY(SaveGame) FDateTime SavedAtUtc;
	UPROPERTY(SaveGame) bool bTutorialOnboardingCompleted = false;
	bool IsSupported() const { return SchemaVersion == 1 || SchemaVersion == 2; }
	bool HasCompletedOnboarding() const { return SchemaVersion >= 2 && bTutorialOnboardingCompleted; }
};
