#pragma once

#include "CoreMinimal.h"

#if PLATFORM_WINDOWS
#include "SaveGameSystem.h"

/** Windows writes for the generic UE save path. Reads still use the original slot format. */
class FCatrunAtomicSaveGameSystem : public FGenericSaveGameSystem
{
public:
	bool SaveGame(bool bAttemptToUseUI, const TCHAR* Name, int32 UserIndex, const TArray<uint8>& Data) override;
};
#endif
