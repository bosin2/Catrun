#include "CatrunAtomicSaveGame.h"

#if PLATFORM_WINDOWS
#include "HAL/FileManager.h"
#include "HAL/CriticalSection.h"
#include "Misc/SecureHash.h"
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

ISaveGameSystem::ESaveExistsResult FCatrunAtomicSaveGameSystem::DoesSaveGameExistWithResult(const TCHAR* Name, int32)
{
	const FString Path = ToWindowsCheckpointPath(IFileManager::Get().ConvertToAbsolutePathForExternalAppForRead(*GetSaveGamePath(Name)));
	WIN32_FILE_ATTRIBUTE_DATA Attributes;
	if (::GetFileAttributesExW(*Path, GetFileExInfoStandard, &Attributes))
		return (Attributes.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) ? ESaveExistsResult::UnspecifiedError : ESaveExistsResult::OK;
	const auto Error = ::GetLastError();
	return (Error == ERROR_FILE_NOT_FOUND || Error == ERROR_PATH_NOT_FOUND) ? ESaveExistsResult::DoesNotExist : ESaveExistsResult::UnspecifiedError;
}

bool FCatrunAtomicSaveGameSystem::CommitIfUnchanged(const TCHAR* Name, const TArray<uint8>* Expected, const TArray<uint8>& Data)
{
	return Commit(Name, Data, Expected != nullptr, Expected);
}

bool FCatrunAtomicSaveGameSystem::SaveGame(bool, const TCHAR* Name, int32, const TArray<uint8>& Data)
{
	return Commit(Name, Data, true);
}

bool FCatrunAtomicSaveGameSystem::Commit(const TCHAR* Name, const TArray<uint8>& Data, bool bReplace, const TArray<uint8>* Expected)
{
	IFileManager& Files = IFileManager::Get();
	const FString LogicalSlotPath = GetSaveGamePath(Name);
	if (Data.IsEmpty() || !Files.MakeDirectory(*FPaths::GetPath(LogicalSlotPath), true))
	{
		return false;
	}

	const FString SlotPath = Files.ConvertToAbsolutePathForExternalAppForWrite(*LogicalSlotPath);
	FString CanonicalPath = FPaths::ConvertRelativePathToFull(SlotPath).ToLower();
	FPaths::NormalizeFilename(CanonicalPath);
	FPaths::CollapseRelativeDirectories(CanonicalPath);
	const FString MutexName = TEXT("CatrunCheckpoint-") + FSHA1::HashBuffer(*CanonicalPath, CanonicalPath.Len() * sizeof(TCHAR)).ToString();
	const FSystemWideCriticalSection SlotLock(MutexName, FTimespan::FromSeconds(5));
	if (!SlotLock.IsValid()) return false;
	if (Expected)
	{
		TArray<uint8> Current;
		if (!LoadGame(false, Name, 0, Current) || Current != *Expected) return false;
	}
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
	if (bComplete && bClosed && ::MoveFileExW(*TemporaryPath, *DestinationPath, MOVEFILE_WRITE_THROUGH | (bReplace ? MOVEFILE_REPLACE_EXISTING : 0)))
	{
		return true;
	}

	::DeleteFileW(*TemporaryPath);
	return false;
}
#endif
