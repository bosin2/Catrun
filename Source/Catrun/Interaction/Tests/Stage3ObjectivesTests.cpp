#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Interaction/CatrunStage3Objectives.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "LevelFlow/CatrunProgressSave.h"
#include "LevelFlow/Tests/CatrunCheckpointTestBackend.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FStage3AllLocksTest, "Catrun.Stage3.AllThreeLocksRequired", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FStage3AllLocksTest::RunTest(const FString&)
{
    const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false);
    UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
    GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
    auto* Objectives = World->SpawnActor<ACatrunStage3Objectives>();
    TestFalse(TEXT("An unwired objective never unlocks"), Objectives->AllReleased());
    Objectives->Devices.SetNum(3);
    for (int32 Mask = 0; Mask < 8; ++Mask)
    {
        for (int32 I = 0; I < 3; ++I) Objectives->Devices[I].bReleased = (Mask & (1 << I)) != 0;
        TestEqual(FString::Printf(TEXT("Release combination %d"), Mask), Objectives->AllReleased(), Mask == 7);
    }
    TestFalse(TEXT("Missing player cannot activate a device"), Objectives->TryRelease(0, nullptr));
    World->DestroyWorld(false);
    GEngine->DestroyWorldContext(World);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FStage3ClockTest, "Catrun.Stage3.FreshAttemptClock", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FStage3ClockTest::RunTest(const FString&)
{
    auto* Session = NewObject<UCatrunFlowSession>(NewObject<UGameInstance>());
    const FString Package(TEXT("/Game/Maps/Stage3"));
    const float Budget = GetDefault<UCatrunLevelFlowSettings>()->GetClockBudget(TEXT("Stage3"));
    Session->Arrive(Package);
    TestEqual(TEXT("Stage3 starts at its budget"), Session->GetRemainingSeconds(TEXT("Stage3")), Budget);
    Session->AdvanceClock(3.25f);
    TestEqual(TEXT("Stage3 countdown advances"), Session->GetRemainingSeconds(TEXT("Stage3")), Budget - 3.25f);
    Session->Arrive(Package);
    TestEqual(TEXT("Stage3 retry refills the timer"), Session->GetRemainingSeconds(TEXT("Stage3")), Budget);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FStage3CheckpointTest, "Catrun.Stage3.ChapterUnlockRoundTrip", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FStage3CheckpointTest::RunTest(const FString&)
{
    FCheckpointBackend Backend;
    Backend.bExists = false;
    auto* Session = NewObject<UCatrunFlowSession>(NewObject<UGameInstance>());
    Session->SetSaveBackendForTest(&Backend, FSimpleDelegate::CreateLambda([&Backend] { Backend.Drain(); }));
    const FString Package(TEXT("/Game/Maps/Stage3"));
    Session->AcceptTravel(Package, true, true, ECatrunArrivalRestart::Continue);
    Session->Arrive(Package);
    Session->SaveCurrentCheckpoint(Package);
    Backend.Drain();
    const auto* Save = UCatrunProgressSave::Decode(Backend.Bytes);
    if (!TestNotNull(TEXT("Stage3 chapter checkpoint decodes"), Save)) return false;
    TestEqual(TEXT("Continue points to Stage3"), Save->StageId, FName(TEXT("Stage3")));
    TestEqual(TEXT("Stage3 remains unlocked"), Save->HighestUnlockedStageId, FName(TEXT("Stage3")));
    return true;
}
#endif
