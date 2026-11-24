#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "LevelFlow/CatrunProgressSave.h"
#include "LevelFlow/CatrunProgressWriter.h"
#include "SaveGameSystem.h"
#include "Engine/GameInstance.h"
#include "Kismet/GameplayStatics.h"

#include "CatrunCheckpointTestBackend.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunCheckpointRollbackTest, "Catrun.LevelFlow.CheckpointRollbackSerializesQueue", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunCheckpointRollbackTest::RunTest(const FString&)
{
    FCheckpointBackend Backend; Backend.Bytes = {1,2,3,4}; Backend.WriteResults = {false,true,true};
    auto Writer = MakeShared<FCatrunProgressWriter>(&Backend);
    TArray<bool> Results;
    int32 Built = 0;
    Writer->Enqueue([&Built](const TArray<uint8>*, TArray<uint8>& Bytes) { ++Built; Bytes = {5,6}; return true; }, [&Results](bool OK, const FString&) { Results.Add(OK); });
    Writer->Enqueue([&Built](const TArray<uint8>*, TArray<uint8>& Bytes) { ++Built; Bytes = {7,8}; return true; }, [&Results](bool OK, const FString&) { Results.Add(OK); });
    TestEqual(TEXT("Payload waits for the prior slot inspection"), Built, 0);
    Backend.Step(); Backend.Step(); Backend.Step();
    TestTrue(TEXT("Writer remains busy after failed write until rollback callback"), Writer->IsBusy());
    TestTrue(TEXT("Injected partial bytes exist before rollback"), Backend.Bytes == TArray<uint8>({99,0,99}));
    TestEqual(TEXT("No success/failure callback precedes rollback"), Results.Num(), 0);
    TestEqual(TEXT("Second payload cannot overtake rollback"), Built, 1);
    Backend.Step();
    TestTrue(TEXT("Rollback restores exact original bytes"), Backend.Bytes == TArray<uint8>({1,2,3,4}));
    TestEqual(TEXT("Primary failure remains failure after successful rollback"), Results.Num(), 1);
    TestFalse(TEXT("First result is failure"), Results[0]);
    Backend.Drain();
    TestTrue(TEXT("Later queued write commits after rollback"), Backend.Bytes == TArray<uint8>({7,8}));
    TestEqual(TEXT("Both callbacks delivered once"), Results.Num(), 2);
    TestTrue(TEXT("Second result succeeds"), Results[1]);
    TestFalse(TEXT("Writer releases only after complete operation"), Writer->IsBusy());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunCheckpointBackupTest, "Catrun.LevelFlow.CheckpointBackupAndNewSlotFailure", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunCheckpointBackupTest::RunTest(const FString&)
{
    for (bool ReadFailure : {false,true})
    {
        FCheckpointBackend Backend; Backend.Bytes = {21,22}; Backend.bReadFails = ReadFailure;
        if (!ReadFailure) Backend.Existence = ISaveGameSystem::ESaveExistsResult::UnspecifiedError;
        auto Writer = MakeShared<FCatrunProgressWriter>(&Backend);
        bool bCompleted = false;
        Writer->Enqueue([](const TArray<uint8>*, TArray<uint8>& Bytes) { Bytes = {42}; return true; }, [this,&bCompleted](bool OK, const FString&) { bCompleted = true; TestFalse(TEXT("Backup/inspection failure is reported"), OK); });
        Backend.Drain();
        TestTrue(TEXT("Backup failure finishes callback"), bCompleted);
        TestEqual(TEXT("Unreadable existing slot is never overwritten"), Backend.Writes, 0);
        TestTrue(TEXT("Previous bytes remain intact"), Backend.Bytes == TArray<uint8>({21,22}));
    }
    FCheckpointBackend Backend; Backend.bExists = false; Backend.WriteResults = {false};
    auto Writer = MakeShared<FCatrunProgressWriter>(&Backend);
    Writer->Enqueue([](const TArray<uint8>*, TArray<uint8>& Bytes) { Bytes = {42}; return true; }, [this](bool OK, const FString&) { TestFalse(TEXT("New slot failure is not reported as saved"), OK); });
    Backend.Drain();
    TestFalse(TEXT("A partially created new slot is removed"), Backend.bExists);
    TestEqual(TEXT("Exactly one owned partial slot cleanup"), Backend.Deletes, 1);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunCheckpointLifetimeTest, "Catrun.LevelFlow.CheckpointIOOutlivesPresentation", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunCheckpointLifetimeTest::RunTest(const FString&)
{
    FCheckpointBackend Backend; Backend.Bytes = {1,4,9}; Backend.WriteResults = {false,true};
    TSharedPtr<FCatrunProgressWriter> Writer = MakeShared<FCatrunProgressWriter>(&Backend);
    bool bCompleted = false;
    Writer->Enqueue([](const TArray<uint8>*, TArray<uint8>& Bytes) { Bytes = {16}; return true; }, [&bCompleted](bool, const FString&) { bCompleted = true; });
    Backend.Step(); Backend.Step(); // original write is in flight
    Writer.Reset(); // analogous to session/world UI lifetime ending; platform write cannot be canceled
    Backend.Drain();
    TestTrue(TEXT("In-flight operation still finishes rollback"), bCompleted);
    TestTrue(TEXT("Owner loss does not strand partial bytes"), Backend.Bytes == TArray<uint8>({1,4,9}));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunCheckpointArrivalTest, "Catrun.LevelFlow.ReachedStageOnboardingAndAcceptedArrival", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunCheckpointArrivalTest::RunTest(const FString&)
{
    auto* Settings = GetMutableDefault<UCatrunLevelFlowSettings>();
    TGuardValue<TArray<FCatrunStageRoute>> RestoreRoutes(Settings->Stages, Settings->Stages);
    Settings->Stages.Reset();
    for (const TCHAR* Name : {TEXT("Stage1"),TEXT("Stage2")})
    {
        auto& Route = Settings->Stages.AddDefaulted_GetRef(); Route.StageId = Name;
        Route.Map = TSoftObjectPtr<UWorld>(FSoftObjectPath(FString(TEXT("/Game/Test/")) + Name));
    }
    FCheckpointBackend Backend; Backend.bExists = false;
    auto* Session = NewObject<UCatrunFlowSession>(NewObject<UGameInstance>());
    Session->SetSaveBackendForTest(&Backend);
    TestEqual(TEXT("Direct editor launch cannot write a real slot"), Session->SaveCurrentCheckpoint(TEXT("/Game/Test/Stage1")), uint64(0));
    Session->AcceptTravel(TEXT("/Game/Test/Stage1"), true, true, ECatrunArrivalRestart::Clear, 0);
    TestTrue(TEXT("Only accepted arrival starts tracked progress"), Session->Arrive(TEXT("/Game/Test/Stage1")));
    Session->SaveCurrentCheckpoint(TEXT("/Game/Test/Stage1"));
    TestTrue(TEXT("Actual pending state covers queued/platform I/O"), Session->IsSavePending());
    Session->MarkOnboardingCompleted(TEXT("/Game/Test/Stage1"));
    Session->AcceptTravel(TEXT("/Game/Test/Stage2"), false, true, ECatrunArrivalRestart::Clear);
    Backend.Drain();
    TestFalse(TEXT("Actual pending state ends with writer completion"), Session->IsSavePending());
    auto* Save = Cast<UCatrunProgressSave>(UGameplayStatics::LoadGameFromMemory(Backend.Bytes));
    if (!TestNotNull(TEXT("Queued checkpoint deserializes"), Save)) return false;
    TestEqual(TEXT("Queued travel never manufactures destination checkpoint"), Save->StageId, FName(TEXT("Stage1")));
    TestTrue(TEXT("Queued onboarding is not reverted by older payload"), Save->HasCompletedOnboarding());
    Session->CancelTravel();
    TestTrue(TEXT("Failed/canceled travel retains reached-world tracking"), Session->IsTrackingWorld(TEXT("/Game/Test/Stage1")));
    const uint64 OldToken = Session->AcceptTravel(TEXT("/Game/Test/Stage1"), false, false, ECatrunArrivalRestart::Clear);
    Session->AcceptTravel(TEXT("/Game/Test/Stage2"), false, true, ECatrunArrivalRestart::Clear);
    Session->CancelTravel(OldToken);
    TestTrue(TEXT("Matching destination arrival permits checkpoint"), Session->Arrive(TEXT("/Game/Test/Stage2")));
    Session->SaveCurrentCheckpoint(TEXT("/Game/Test/Stage2")); Backend.Drain();
    Save = Cast<UCatrunProgressSave>(UGameplayStatics::LoadGameFromMemory(Backend.Bytes));
    TestEqual(TEXT("Destination checkpoint changes only after arrival"), Save->StageId, FName(TEXT("Stage2")));
    TestTrue(TEXT("Arrival preserves completed onboarding"), Save->HasCompletedOnboarding());
    Session->AcceptTravel(TEXT("/Game/Test/Stage1"), true, true, ECatrunArrivalRestart::Clear, 0);
    Session->CancelTravel();
    TestTrue(TEXT("Failed new game cannot reset onboarding"), Session->HasCompletedOnboarding());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunCheckpointMigrationTest, "Catrun.LevelFlow.SchemaMigrationAndContinueReason", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunCheckpointMigrationTest::RunTest(const FString&)
{
    for (FName Stage : {FName(TEXT("Tutorial")), FName(TEXT("Stage1")), FName(TEXT("Stage2"))})
    {
        auto* Save = NewObject<UCatrunProgressSave>(); Save->SchemaVersion = 1; Save->StageId = Stage;
        TArray<uint8> Bytes; TestTrue(TEXT("Old checkpoint serializes without migration writes"), UGameplayStatics::SaveGameToMemory(Save, Bytes));
        auto* Loaded = Cast<UCatrunProgressSave>(UGameplayStatics::LoadGameFromMemory(Bytes));
        TestTrue(TEXT("Schema1 remains supported"), Loaded && Loaded->IsSupported());
        TestEqual(TEXT("Legacy stage is retained"), Loaded->StageId, Stage);
        TestFalse(TEXT("Legacy save does not invent onboarding completion"), Loaded->HasCompletedOnboarding());
    }
    auto* Unknown = NewObject<UCatrunProgressSave>(); Unknown->SchemaVersion = 99;
    TestFalse(TEXT("Future/unknown schema still rejected"), Unknown->IsSupported());
    FCatrunRestartIntent Intent; Intent.Request(TEXT("/Game/Tutorial"), 0, true);
    TestTrue(TEXT("Continue has separate guidance reason"), Intent.bContinue);
    float Fade; TestTrue(TEXT("Continue still skips original cinematic"), Intent.Consume(TEXT("/Game/Tutorial"), Fade));
    TestFalse(TEXT("Consumed Continue reason cannot leak into another retry"), Intent.bContinue);
    Intent.Request(TEXT("/Game/Tutorial"), .5f);
    TestFalse(TEXT("Existing capture retry API remains Retry by default"), Intent.bContinue);
    return true;
}
#endif
