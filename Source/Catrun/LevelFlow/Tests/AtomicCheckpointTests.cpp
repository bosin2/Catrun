#if WITH_DEV_AUTOMATION_TESTS && PLATFORM_WINDOWS
#include "LevelFlow/CatrunAtomicSaveGame.h"
#include "HAL/FileManager.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Guid.h"
#include "Misc/Paths.h"
#include "Misc/ScopeExit.h"
#include "SaveGameSystem.h"
#include "Windows/WindowsHWrapper.h"

namespace
{
	class FTemporaryCheckpointSystem final : public FCatrunAtomicSaveGameSystem
	{
	public:
		explicit FTemporaryCheckpointSystem(const FString& InDirectory) : Directory(InDirectory) {}
		FString GetSaveGamePath(const TCHAR* Name) override
		{
			return Directory / (FString(Name) + TEXT(".sav"));
		}

	private:
		FString Directory;
	};

	FString GetNativeTestPath(const FString& Path)
	{
		FString Result = IFileManager::Get().ConvertToAbsolutePathForExternalAppForWrite(*Path);
		FPaths::MakePlatformFilename(Result);
		return Result;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunAtomicCheckpointReplaceTest, "Catrun.LevelFlow.CheckpointCommitReplacesFile", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunAtomicCheckpointReplaceTest::RunTest(const FString&)
{
	IFileManager& Files = IFileManager::Get();
	const FString Directory = FPaths::ProjectSavedDir() / (TEXT("CatrunCheckpointTest-") + FGuid::NewGuid().ToString(EGuidFormats::Digits));
	FTemporaryCheckpointSystem Backend(Directory);
	const TCHAR* SlotName = TEXT("Checkpoint");
	const FString SlotPath = Backend.GetSaveGamePath(SlotName);
	const FString ObserverPath = Directory / TEXT("Original.link");
	ON_SCOPE_EXIT
	{
		Files.Delete(*ObserverPath);
		Files.Delete(*SlotPath);
		Files.DeleteDirectory(*Directory);
	};

	const TArray<uint8> Previous = {1, 2, 3, 4};
	const TArray<uint8> Next = {5, 6};
	if (!TestTrue(TEXT("Seed an isolated existing save"), FFileHelper::SaveArrayToFile(Previous, *SlotPath))) return false;
	if (!TestTrue(TEXT("Observe the original file through a hard link"),
		CreateHardLinkW(*GetNativeTestPath(ObserverPath), *GetNativeTestPath(SlotPath), nullptr) != 0)) return false;

	TestTrue(TEXT("Commit succeeds"), Backend.SaveGame(false, SlotName, 0, Next));
	TArray<uint8> Bytes;
	TestTrue(TEXT("The slot exposes only the complete committed bytes"), Backend.LoadGame(false, SlotName, 0, Bytes) && Bytes == Next);
	TestTrue(TEXT("Commit leaves the original file's bytes intact"), FFileHelper::LoadFileToArray(Bytes, *ObserverPath) && Bytes == Previous);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunAtomicCheckpointFailureTest, "Catrun.LevelFlow.CheckpointPreCommitFailurePreservesSlot", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunAtomicCheckpointFailureTest::RunTest(const FString&)
{
	IFileManager& Files = IFileManager::Get();
	const FString Directory = FPaths::ProjectSavedDir() / (TEXT("CatrunCheckpointTest-") + FGuid::NewGuid().ToString(EGuidFormats::Digits));
	FTemporaryCheckpointSystem Backend(Directory);
	const TCHAR* SlotName = TEXT("Checkpoint");
	const FString SlotPath = Backend.GetSaveGamePath(SlotName);
	const FString AbandonedName = TEXT("CatrunCheckpoint-abandoned.tmp");
	const FString AbandonedPath = Directory / AbandonedName;
	ON_SCOPE_EXIT
	{
		Files.Delete(*AbandonedPath);
		Files.Delete(*SlotPath);
		Files.DeleteDirectory(*Directory);
	};

	const TArray<uint8> Previous = {1, 2, 3, 4};
	const TArray<uint8> Next = {5, 6};
	if (!TestTrue(TEXT("Stage bytes left by an interrupted process"), FFileHelper::SaveArrayToFile(Next, *AbandonedPath))) return false;
	TestFalse(TEXT("An abandoned temporary file is invisible to slot lookup"), Backend.DoesSaveGameExist(SlotName, 0));
	if (!TestTrue(TEXT("Create the first checkpoint through the atomic backend"), Backend.SaveGame(false, SlotName, 0, Previous))) return false;

	{
		// Readers may open the old slot, but the file cannot be replaced while this handle is open.
		const HANDLE Reader = ::CreateFileW(*GetNativeTestPath(SlotPath), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
		if (!TestTrue(TEXT("Hold an open slot without delete sharing"), Reader != INVALID_HANDLE_VALUE)) return false;
		ON_SCOPE_EXIT { ::CloseHandle(Reader); };
		TestFalse(TEXT("The rejected replacement reports failure"), Backend.SaveGame(false, SlotName, 0, Next));
	}
	TArray<uint8> Bytes;
	TestTrue(TEXT("Failure preserves all previously committed bytes"), Backend.LoadGame(false, SlotName, 0, Bytes) && Bytes == Previous);
	TArray<FString> TemporaryFiles;
	Files.FindFiles(TemporaryFiles, *(Directory / TEXT("*.tmp")), true, false);
	TestTrue(TEXT("Failed replacement cleans its own temporary file"), TemporaryFiles == TArray<FString>{AbandonedName});
	TestTrue(TEXT("A retry commits after the lock is released"), Backend.SaveGame(false, SlotName, 0, Next));
	TestTrue(TEXT("Retry makes the complete new payload visible"), Backend.LoadGame(false, SlotName, 0, Bytes) && Bytes == Next);
	return true;
}
#endif

#if WITH_DEV_AUTOMATION_TESTS
#include "LevelFlow/CatrunProgressWriter.h"
#include "Misc/AutomationTest.h"
#include "CatrunCheckpointTestBackend.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunCheckpointQueueIdleTest, "Catrun.LevelFlow.CheckpointIdleFollowsQueueCompletion", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunCheckpointQueueIdleTest::RunTest(const FString&)
{
	FCheckpointBackend Backend;
	Backend.bExists = false;
	const auto Writer = MakeShared<FCatrunProgressWriter>(&Backend);
	TArray<int32> Events;
	Writer->OnIdle.BindLambda([this, &Writer, &Events]
	{
		TestFalse(TEXT("Idle observers see the writer as available"), Writer->IsBusy());
		Events.Add(3);
	});
	Writer->Enqueue([](TArray<uint8>& Bytes) { Bytes = {1}; return true; }, [this, &Writer, &Events](bool bSuccess, const FString&)
	{
		TestTrue(TEXT("First write succeeds"), bSuccess);
		Events.Add(1);
		Writer->Enqueue([](TArray<uint8>& Bytes) { Bytes = {2}; return true; }, [this, &Events](bool bNextSuccess, const FString&)
		{
			TestTrue(TEXT("Write queued by the previous callback succeeds"), bNextSuccess);
			Events.Add(2);
		});
	});
	Backend.Drain();
	TestTrue(TEXT("Exactly one idle event follows all result callbacks"), Events == TArray<int32>({1, 2, 3}));
	return true;
}
#endif
