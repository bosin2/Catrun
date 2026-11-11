#include "CatrunAtomicSaveGame.h"

#if PLATFORM_WINDOWS
#include "HAL/FileManager.h"
#include "Misc/Guid.h"
#include "Misc/Paths.h"
#include "Windows/WindowsHWrapper.h"

namespace
{
	FString ToWindowsCheckpointPath(FString Path)
	{
		FPaths::MakePlatformFilename(Path);
		if (Path.Len() < MAX_PATH || Path.StartsWith(TEXT("\\\\?\\")))
		{
			return Path;
		}
		if (Path.StartsWith(TEXT("\\\\")))
		{
			return TEXT("\\\\?\\UNC\\") + Path.RightChop(2);
		}
		return TEXT("\\\\?\\") + Path;
	}
}

bool FCatrunAtomicSaveGameSystem::SaveGame(bool, const TCHAR* Name, int32, const TArray<uint8>& Data)
{
	IFileManager& Files = IFileManager::Get();
	const FString LogicalSlotPath = GetSaveGamePath(Name);
	if (Data.IsEmpty() || !Files.MakeDirectory(*FPaths::GetPath(LogicalSlotPath), true))
	{
		return false;
	}

	const FString SlotPath = Files.ConvertToAbsolutePathForExternalAppForWrite(*LogicalSlotPath);
	const FString TemporaryName = TEXT("CatrunCheckpoint-") + FGuid::NewGuid().ToString(EGuidFormats::Digits) + TEXT(".tmp");
	const FString TemporaryPath = ToWindowsCheckpointPath(FPaths::GetPath(SlotPath) / TemporaryName);
	const FString DestinationPath = ToWindowsCheckpointPath(SlotPath);
	const HANDLE File = ::CreateFileW(*TemporaryPath, GENERIC_WRITE, 0, nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
	if (File == INVALID_HANDLE_VALUE)
	{
		return false;
	}

	const ::DWORD ByteCount = static_cast<::DWORD>(Data.Num());
	::DWORD BytesWritten = 0;
	const bool bComplete = ::WriteFile(File, Data.GetData(), ByteCount, &BytesWritten, nullptr)
		&& BytesWritten == ByteCount && ::FlushFileBuffers(File);
	const bool bClosed = ::CloseHandle(File) != 0;
	// Commit through a same-volume rename, with cross-volume copy fallback disabled.
	if (bComplete && bClosed && ::MoveFileExW(*TemporaryPath, *DestinationPath, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH))
	{
		return true;
	}

	::DeleteFileW(*TemporaryPath);
	return false;
}
#endif
