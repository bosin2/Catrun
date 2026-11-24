#if WITH_DEV_AUTOMATION_TESTS && PLATFORM_WINDOWS
#include "LevelFlow/CatrunAtomicSaveGame.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "LevelFlow/CatrunProgressSave.h"
#include "Engine/GameInstance.h"
#include "Async/Async.h"
#include "HAL/Event.h"
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
		TFunction<void()> AfterRead;
		bool LoadGame(bool bUI, const TCHAR* Name, int32 User, TArray<uint8>& Data) override
		{
			const bool bRead = FCatrunAtomicSaveGameSystem::LoadGame(bUI, Name, User, Data);
			if (AfterRead) AfterRead();
			return bRead;
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

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunConcurrentCheckpointTest, "Catrun.LevelFlow.ConcurrentCheckpointCommitRejectsStaleWriter", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunConcurrentCheckpointTest::RunTest(const FString&)
{
	const FString Directory = FPaths::ProjectSavedDir() / (TEXT("CatrunCheckpointTest-") + FGuid::NewGuid().ToString(EGuidFormats::Digits));
	FTemporaryCheckpointSystem First(Directory), Second(Directory);
	const TCHAR* Slot = TEXT("Checkpoint");
	const TArray<uint8> Previous{0}, Higher{2}, Lower{1};
	ON_SCOPE_EXIT { IFileManager::Get().Delete(*First.GetSaveGamePath(Slot)); IFileManager::Get().DeleteDirectory(*Directory); };
	if (!TestTrue(TEXT("Seed isolated slot"), First.SaveGame(false, Slot, 0, Previous))) return false;
	FEventRef FirstRead, ResumeFirst, SecondStarted;
	First.AfterRead = [&]() { FirstRead->Trigger(); ResumeFirst->Wait(5000); };
	auto FirstCommit = Async(EAsyncExecution::Thread, [&]() { return First.CommitIfUnchanged(Slot, &Previous, Higher); });
	TestTrue(TEXT("First writer has compared the previous slot"), FirstRead->Wait(5000));
	auto StaleCommit = Async(EAsyncExecution::Thread, [&]()
	{
		SecondStarted->Trigger();
		return Second.CommitIfUnchanged(Slot, &Previous, Lower);
	});
	TestTrue(TEXT("Second independent writer enters while the first owns its comparison"), SecondStarted->Wait(5000));
	TestFalse(TEXT("Second writer cannot commit between first comparison and rename"), StaleCommit.WaitFor(FTimespan::FromMilliseconds(200)));
	ResumeFirst->Trigger();
	TestTrue(TEXT("First checkpoint commits"), FirstCommit.Get());
	TestFalse(TEXT("Stale lower checkpoint rejected after first commit"), StaleCommit.Get());
	TArray<uint8> Actual;
	TestTrue(TEXT("Higher checkpoint survives concurrent stale writer"), Second.LoadGame(false, Slot, 0, Actual) && Actual == Higher);
	return true;
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
	TestFalse(TEXT("A slot created after the missing-slot check is preserved"), Backend.CommitIfUnchanged(SlotName, nullptr, Previous));
	TestFalse(TEXT("A slot changed after the backup read is preserved"), Backend.CommitIfUnchanged(SlotName, &Previous, Previous));
	TestTrue(TEXT("Conflicting commits preserve all bytes"), Backend.LoadGame(false, SlotName, 0, Bytes) && Bytes == Next);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunAtomicShutdownFlushTest, "Catrun.LevelFlow.PendingAtomicCheckpointFlushesOnShutdown", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunAtomicShutdownFlushTest::RunTest(const FString&)
{
	const FString Directory = FPaths::ProjectSavedDir() / (TEXT("CatrunCheckpointTest-") + FGuid::NewGuid().ToString(EGuidFormats::Digits));
	FTemporaryCheckpointSystem Backend(Directory), Observer(Directory);
	const TCHAR* Slot = TEXT("CatrunProgress");
	ON_SCOPE_EXIT { IFileManager::Get().Delete(*Backend.GetSaveGamePath(Slot)); IFileManager::Get().DeleteDirectory(*Directory); };
	auto* Session = NewObject<UCatrunFlowSession>(NewObject<UGameInstance>());
	Session->SetSaveBackendForTest(&Backend, {}, true);
	const FString Package(TEXT("/Game/Maps/Stage1"));
	Session->AcceptTravel(Package, true, true, ECatrunArrivalRestart::Continue);
	Session->Arrive(Package);
	Session->SaveCurrentCheckpoint(Package);
	TestTrue(TEXT("Atomic asynchronous checkpoint remains pending before shutdown"), Session->IsSavePending());
	Session->AdvanceClock(17.125f);
	const int32 ExpectedMs = FMath::RoundToInt32(double(Session->GetRemainingSeconds(TEXT("Stage1"))) * 1000.);
	Session->Deinitialize();
	TArray<uint8> Bytes;
	if (!TestTrue(TEXT("Independent slot observer reads immediately after shutdown"), Observer.LoadGame(false, Slot, 0, Bytes))) return false;
	const auto* Save = UCatrunProgressSave::Decode(Bytes);
	if (!TestNotNull(TEXT("Disk contains a valid last checkpoint"), Save)) return false;
	TestEqual(TEXT("Shutdown preserves the active chapter"), Save->StageId, FName(TEXT("Stage1")));
	TestEqual(TEXT("Shutdown synchronizes latest Stage1 remaining time to disk"), Save->Stage1RemainingMs, ExpectedMs);
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
	Writer->Enqueue([](const TArray<uint8>*, TArray<uint8>& Bytes) { Bytes = {1}; return true; }, [this, &Writer, &Events](bool bSuccess, const FString&)
	{
		TestTrue(TEXT("First write succeeds"), bSuccess);
		Events.Add(1);
		Writer->Enqueue([](const TArray<uint8>*, TArray<uint8>& Bytes) { Bytes = {2}; return true; }, [this, &Events](bool bNextSuccess, const FString&)
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
