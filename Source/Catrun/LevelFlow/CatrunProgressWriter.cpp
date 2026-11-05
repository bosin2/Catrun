#include "CatrunProgressWriter.h"
#include "SaveGameSystem.h"
#include "HAL/PlatformMisc.h"

namespace
{
	constexpr const TCHAR* CatrunProgressSlotName = TEXT("CatrunProgress");
	FPlatformUserId User() { return FPlatformMisc::GetPlatformUserForUserIndex(0); }
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
	TArray<uint8> Bytes;
	if (!Backend || !Active.Payload(Bytes)) { Finish(false, TEXT("Checkpoint serialization or session eligibility failed.")); return; }
	Active.Data = MakeShared<const TArray<uint8>>(MoveTemp(Bytes));
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
	Backend->SaveGameAsync(false, CatrunProgressSlotName, User(), Active.Data.ToSharedRef(), [Self = AsShared()](const FString&, FPlatformUserId, bool bOK)
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
	FResult Result = MoveTemp(Active.Result);
	Active = FOperation();
	// Callback may enqueue; keep the writer locked until it has returned.
	if (Result) Result(bSuccess, Error);
	bBusy = false;
	StartNext();
}
