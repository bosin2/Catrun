#include "CatrunProgressWriter.h"
#include "CatrunAtomicSaveGame.h"
#include "PlatformFeatures.h"
#include "SaveGameSystem.h"
#include "HAL/PlatformMisc.h"

namespace
{
	constexpr const TCHAR* CatrunProgressSlotName = TEXT("CatrunProgress");
	FPlatformUserId User() { return FPlatformMisc::GetPlatformUserForUserIndex(0); }
}

FCatrunProgressWriter::FCatrunProgressWriter()
{
	Backend = GetPlatformBackend(&bWritesAtomically);
}

ISaveGameSystem* FCatrunProgressWriter::GetPlatformBackend(bool* OutAtomic)
{
	IPlatformFeaturesModule& Features = IPlatformFeaturesModule::Get();
	auto* Result = Features.GetSaveGameSystem();
	if (OutAtomic) *OutAtomic = false;
#if PLATFORM_WINDOWS
	// Only the generic platform backend uses the inherited local SaveGames path.
	if (Result && Result == Features.IPlatformFeaturesModule::GetSaveGameSystem())
	{
		static FCatrunAtomicSaveGameSystem AtomicBackend;
		Result = &AtomicBackend;
		if (OutAtomic) *OutAtomic = true;
	}
#endif
	return Result;
}

uint64 FCatrunProgressWriter::Enqueue(FPayload Payload, FResult Result)
{
	const uint64 Id = ++NextId;
	FOperation& Op = Queue.AddDefaulted_GetRef();
	Op.Id = Id; Op.Payload = MoveTemp(Payload); Op.Result = MoveTemp(Result);
	StartNext();
	return Id;
}

void FCatrunProgressWriter::StartNext()
{
	if (bBusy || Queue.IsEmpty()) return;
	bBusy = true;
	Active = MoveTemp(Queue[0]); Queue.RemoveAt(0);
	OnStarted.ExecuteIfBound();
	if (!Backend) { Finish(false, TEXT("Existing checkpoint cannot be inspected; no save backend.")); return; }
	Backend->DoesSaveGameExistAsync(CatrunProgressSlotName, User(), [Self = AsShared()](const FString&, FPlatformUserId, ISaveGameSystem::ESaveExistsResult Result)
	{
		if (Result == ISaveGameSystem::ESaveExistsResult::DoesNotExist) { Self->Write(); return; }
		if (Result != ISaveGameSystem::ESaveExistsResult::OK) { Self->Finish(false, TEXT("Existing checkpoint cannot be inspected; no write attempted.")); return; }
		Self->Active.bHadPrevious = true;
		Self->Backend->LoadGameAsync(false, CatrunProgressSlotName, User(), [Self](const FString&, FPlatformUserId, bool bOK, const TArray<uint8>& Previous)
		{
			if (!bOK) { Self->Finish(false, TEXT("Existing checkpoint backup failed; no write attempted.")); return; }
			Self->Active.Previous = Previous;
			Self->Write();
		});
	});
}

void FCatrunProgressWriter::Write()
{
	TArray<uint8> Bytes;
	if (!Active.Payload(Active.bHadPrevious ? &Active.Previous : nullptr, Bytes))
	{
		Finish(false, TEXT("Existing checkpoint or new payload could not be validated; no write attempted."));
		return;
	}
	const auto NewData = MakeShared<const TArray<uint8>>(MoveTemp(Bytes));
#if PLATFORM_WINDOWS
	if (bWritesAtomically)
	{
		TSharedPtr<const TArray<uint8>> Expected;
		if (Active.bHadPrevious) Expected = MakeShared<const TArray<uint8>>(MoveTemp(Active.Previous));
		static_cast<FCatrunAtomicSaveGameSystem*>(Backend)->CommitIfUnchangedAsync(CatrunProgressSlotName, MoveTemp(Expected), NewData,
			[Self = AsShared()](bool bOK) { Self->Finish(bOK, bOK ? FString() : TEXT("Checkpoint file could not be committed.")); });
		return;
	}
#endif
	Backend->SaveGameAsync(false, CatrunProgressSlotName, User(), NewData, [Self = AsShared()](const FString&, FPlatformUserId, bool bOK)
	{
		if (bOK) { Self->Finish(true, FString()); return; }
		auto RolledBack = [Self](const FString&, FPlatformUserId, bool bRestored)
		{
			Self->Finish(false, bRestored ? TEXT("Checkpoint write failed; prior bytes restored.") : TEXT("Checkpoint write AND rollback failed."));
		};
		if (Self->Active.bHadPrevious)
			Self->Backend->SaveGameAsync(false, CatrunProgressSlotName, User(), MakeShared<const TArray<uint8>>(Self->Active.Previous), MoveTemp(RolledBack));
		else Self->Backend->DeleteGameAsync(false, CatrunProgressSlotName, User(), MoveTemp(RolledBack));
	});
}

void FCatrunProgressWriter::Finish(bool bSuccess, const FString& Error)
{
	const TSharedRef<FCatrunProgressWriter> KeepAlive = AsShared();
	FResult Result = MoveTemp(Active.Result);
	Active = FOperation();
	// Callback may enqueue; keep the writer locked until it has returned.
	if (Result) Result(bSuccess, Error);
	bBusy = false;
	if (Queue.IsEmpty()) OnIdle.ExecuteIfBound();
	else StartNext();
}
