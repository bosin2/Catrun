#pragma once

#include "CoreMinimal.h"

#if PLATFORM_WINDOWS
#include "SaveGameSystem.h"

/** Windows writes for the generic UE save path. Reads still use the original slot format. */
class FCatrunAtomicSaveGameSystem : public FGenericSaveGameSystem
{
public:
	ESaveExistsResult DoesSaveGameExistWithResult(const TCHAR* Name, int32 UserIndex) override;
	bool SaveGame(bool bAttemptToUseUI, const TCHAR* Name, int32 UserIndex, const TArray<uint8>& Data) override;
	bool CommitIfUnchanged(const TCHAR* Name, const TArray<uint8>* Expected, const TArray<uint8>& Data);
	void CommitIfUnchangedAsync(FString Name, TSharedPtr<const TArray<uint8>> Expected,
		TSharedRef<const TArray<uint8>> Data, TFunction<void(bool)> Completion);
private:
	bool Commit(const TCHAR* Name, const TArray<uint8>& Data, bool bReplace, const TArray<uint8>* Expected = nullptr);
};
#endif
