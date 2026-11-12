#pragma once
#if WITH_DEV_AUTOMATION_TESTS
#include "SaveGameSystem.h"
namespace
{
    /** Controllable platform callbacks; never touches CatrunProgress on disk. */
    struct FCheckpointBackend final : ISaveGameSystem
    {
        TArray<uint8> Bytes;
        bool bExists = true, bReadFails = false;
        ESaveExistsResult Existence = ESaveExistsResult::OK;
        TArray<bool> WriteResults;
        TArray<TFunction<void()>> Pending;
        int32 Writes = 0, Deletes = 0, Reads = 0;
        bool PlatformHasNativeUI() override { return false; }
        bool DoesSaveSystemSupportMultipleUsers() override { return false; }
        bool DoesSaveGameExist(const TCHAR*, int32) override { checkNoEntry(); return false; }
        ESaveExistsResult DoesSaveGameExistWithResult(const TCHAR*, int32) override { checkNoEntry(); return Existence; }
        bool SaveGame(bool, const TCHAR*, int32, const TArray<uint8>&) override { checkNoEntry(); return false; }
        bool LoadGame(bool, const TCHAR*, int32, TArray<uint8>& Out) override { if (!bExists || bReadFails) return false; Out = Bytes; return true; }
        bool DeleteGame(bool, const TCHAR*, int32) override { checkNoEntry(); return false; }
        void DoesSaveGameExistAsync(const TCHAR* Slot, FPlatformUserId User, FSaveGameAsyncExistsCallback Callback) override
        {
            Pending.Add([this, Name = FString(Slot), User, Callback = MoveTemp(Callback)]() mutable
            { Callback(Name, User, bExists ? Existence : ESaveExistsResult::DoesNotExist); });
        }
        void LoadGameAsync(bool, const TCHAR* Slot, FPlatformUserId User, FSaveGameAsyncLoadCompleteCallback Callback) override
        {
            ++Reads;
            Pending.Add([this, Name = FString(Slot), User, Callback = MoveTemp(Callback)]() mutable { Callback(Name, User, !bReadFails, Bytes); });
        }
        void SaveGameAsync(bool, const TCHAR* Slot, FPlatformUserId User, TSharedRef<const TArray<uint8>> Data, FSaveGameAsyncOpCompleteCallback Callback) override
        {
            ++Writes;
            const bool bResult = WriteResults.IsEmpty() ? true : WriteResults[0];
            if (!WriteResults.IsEmpty()) WriteResults.RemoveAt(0);
            Pending.Add([this, Name = FString(Slot), User, Data, bResult, Callback = MoveTemp(Callback)]() mutable
            { bExists = true; Bytes = bResult ? *Data : TArray<uint8>{99,0,99}; Callback(Name, User, bResult); });
        }
        void DeleteGameAsync(bool, const TCHAR* Slot, FPlatformUserId User, FSaveGameAsyncOpCompleteCallback Callback) override
        {
            ++Deletes;
            Pending.Add([this, Name = FString(Slot), User, Callback = MoveTemp(Callback)]() mutable
            { bExists = false; Bytes.Reset(); Callback(Name, User, true); });
        }
        void Step() { check(!Pending.IsEmpty()); auto Callback = MoveTemp(Pending[0]); Pending.RemoveAt(0); Callback(); }
        void Drain() { for (int32 i = 0; !Pending.IsEmpty() && i < 100; ++i) Step(); check(Pending.IsEmpty()); }
    };
}

#endif
