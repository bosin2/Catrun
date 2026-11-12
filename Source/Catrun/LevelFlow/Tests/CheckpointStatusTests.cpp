#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "CatrunCheckpointTestBackend.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunCheckpointPendingLabelTest, "Catrun.LevelFlow.PendingCheckpointIsVisibleToContinue", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunCheckpointPendingLabelTest::RunTest(const FString&)
{
    const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false);
    UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
    GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
    auto* Instance = NewObject<UGameInstance>(); World->SetGameInstance(Instance); Instance->Init();
    auto* Settings = GetMutableDefault<UCatrunLevelFlowSettings>();
    TGuardValue<TArray<FCatrunStageRoute>> RestoreRoutes(Settings->Stages, Settings->Stages);
    Settings->Stages.Reset();
    const FString Package = World->GetOutermost()->GetName();
    auto& Route = Settings->Stages.AddDefaulted_GetRef();
    Route.StageId = TEXT("Stage2"); Route.Map = TSoftObjectPtr<UWorld>(FSoftObjectPath(Package));
    FCheckpointBackend Backend; Backend.bExists = false;
    auto* Session = Instance->GetSubsystem<UCatrunFlowSession>();
    Session->SetSaveBackendForTest(&Backend);
    Session->AcceptTravel(Package, true, true, ECatrunArrivalRestart::Clear);
    TestTrue(TEXT("Fixture arrives before saving"), Session->Arrive(Package));
    Session->SaveCurrentCheckpoint(Package);
    TestTrue(TEXT("Controlled I/O remains pending"), Session->IsSavePending());
    TestEqual(TEXT("Continue explains why it cannot resume during save"),
        UCatrunLevelFlowLibrary::GetContinueStageLabel(World).ToString(), FString(TEXT("진행을 저장하고 있습니다.")));
    TestFalse(TEXT("Continue is disabled until the write queue has settled"), UCatrunLevelFlowLibrary::HasContinueGame(World));
    TestEqual(TEXT("Public state is pending while platform owns write"), Session->GetCheckpointState(), ECatrunCheckpointState::Pending);
    Backend.Drain();
    TestEqual(TEXT("Saved state follows queue completion"), Session->GetCheckpointState(), ECatrunCheckpointState::Saved);
    TestFalse(TEXT("A completed write is no longer pending"), Session->IsSavePending());
    Instance->Shutdown(); World->SetGameInstance(nullptr);
    GEngine->DestroyWorldContext(World); World->DestroyWorld(false);
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunArrivalCheckpointRetryTest, "Catrun.LevelFlow.ArrivalSaveRetriesOnceAndReportsFinalState", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunArrivalCheckpointRetryTest::RunTest(const FString&)
{
    AddExpectedError(TEXT("Checkpoint write failed; prior bytes restored."), EAutomationExpectedErrorFlags::Contains, 1);
    const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false);
    UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
    auto* Settings = GetMutableDefault<UCatrunLevelFlowSettings>();
    TGuardValue<TArray<FCatrunStageRoute>> RestoreRoutes(Settings->Stages, Settings->Stages);
    Settings->Stages.Reset();
    const FString Package = World->GetOutermost()->GetName();
    auto& Route = Settings->Stages.AddDefaulted_GetRef(); Route.StageId = TEXT("Tutorial"); Route.Map = TSoftObjectPtr<UWorld>(FSoftObjectPath(Package));
    for (const bool bRetrySucceeds : {true, false})
    {
        FCheckpointBackend Backend; Backend.bExists = false;
        Backend.WriteResults = bRetrySucceeds ? TArray<bool>{false, true} : TArray<bool>{false, false};
        auto* Session = NewObject<UCatrunFlowSession>(NewObject<UGameInstance>()); Session->SetSaveBackendForTest(&Backend);
        Session->AcceptTravel(Package, true, true, ECatrunArrivalRestart::Clear); Session->Arrive(Package);
        Session->SaveArrivalCheckpoint(*World);
        Backend.Step(); Backend.Step(); // existence, failed initial write
        TestEqual(TEXT("Failure remains pending until rollback and retry settle"), Session->GetCheckpointState(), ECatrunCheckpointState::Pending);
        Backend.Drain();
        TestEqual(TEXT("Exactly two writes, never an infinite retry"), Backend.Writes, 2);
        TestEqual(TEXT("Final state reports actual retry result"), Session->GetCheckpointState(), bRetrySucceeds ? ECatrunCheckpointState::Saved : ECatrunCheckpointState::Failed);
        TestFalse(TEXT("Final event observes an idle writer"), Session->IsSavePending());
    }
    World->DestroyWorld(false);
    return true;
}
#endif
