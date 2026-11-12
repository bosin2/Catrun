#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "LevelFlow/CatrunProgressSave.h"
#include "CatrunCheckpointTestBackend.h"
#include "Engine/GameInstance.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunChapterUnlockTest, "Catrun.LevelFlow.ChapterUnlocksSurviveNewGameAndSelection", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunChapterUnlockTest::RunTest(const FString&)
{
    auto* Settings = GetMutableDefault<UCatrunLevelFlowSettings>();
    TGuardValue<TArray<FCatrunStageRoute>> Restore(Settings->Stages, Settings->Stages);
    Settings->Stages.Reset();
    for (const TCHAR* Name : {TEXT("Tutorial"), TEXT("Stage1"), TEXT("Stage2")})
    {
        auto& Route = Settings->Stages.AddDefaulted_GetRef(); Route.StageId = Name;
        Route.Map = TSoftObjectPtr<UWorld>(FSoftObjectPath(FString(TEXT("/Game/Test/")) + Name));
    }
    for (int32 Version : {1, 2})
    {
        FCheckpointBackend Backend;
        auto* Legacy = NewObject<UCatrunProgressSave>(); Legacy->SchemaVersion = Version; Legacy->StageId = TEXT("Stage1");
        UGameplayStatics::SaveGameToMemory(Legacy, Backend.Bytes);
        auto* Session = NewObject<UCatrunFlowSession>(NewObject<UGameInstance>()); Session->SetSaveBackendForTest(&Backend);
        TestEqual(TEXT("Legacy reached stage unlocks earlier chapters"), Session->GetHighestUnlockedStageIndex(), 1);
        Session->AcceptTravel(TEXT("/Game/Test/Stage2"), true, true, ECatrunArrivalRestart::Continue);
        TestEqual(TEXT("Accepted travel alone cannot unlock"), Session->GetHighestUnlockedStageIndex(), 1);
        Session->CancelTravel();
        TestEqual(TEXT("Cancelled travel cannot unlock"), Session->GetHighestUnlockedStageIndex(), 1);
        Session->AcceptTravel(TEXT("/Game/Test/Stage2"), true, true, ECatrunArrivalRestart::Clear);
        Session->Arrive(TEXT("/Game/Test/Stage2"));
        TestEqual(TEXT("Actual arrival unlocks chapter"), Session->GetHighestUnlockedStageIndex(), 2);
        Session->AcceptTravel(TEXT("/Game/Test/Tutorial"), true, true, ECatrunArrivalRestart::Clear, 0);
        Session->Arrive(TEXT("/Game/Test/Tutorial")); Session->SaveCurrentCheckpoint(TEXT("/Game/Test/Tutorial")); Backend.Drain();
        const auto* Save = Cast<UCatrunProgressSave>(UGameplayStatics::LoadGameFromMemory(Backend.Bytes));
        TestEqual(TEXT("New game writes fresh active stage"), Save->StageId, FName(TEXT("Tutorial")));
        TestEqual(TEXT("New game preserves high water"), Save->HighestUnlockedStageId, FName(TEXT("Stage2")));
        auto* Reloaded = NewObject<UCatrunFlowSession>(NewObject<UGameInstance>()); Reloaded->SetSaveBackendForTest(&Backend);
        TestEqual(TEXT("High water survives a new session"), Reloaded->GetHighestUnlockedStageIndex(), 2);
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunChapterTitleIntentTest, "Catrun.LevelFlow.StageTitleRequiresActualMatchingArrival", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunChapterTitleIntentTest::RunTest(const FString&)
{
    auto* Session = NewObject<UCatrunFlowSession>(NewObject<UGameInstance>());
    FCheckpointBackend Backend; Backend.bExists = false; Session->SetSaveBackendForTest(&Backend);
    const FString Package = GetDefault<UCatrunLevelFlowSettings>()->Stages[0].Map.ToSoftObjectPath().GetLongPackageName();
    for (auto Reason : {ECatrunArrivalRestart::Clear, ECatrunArrivalRestart::Continue, ECatrunArrivalRestart::SkipIntro})
    {
        Session->AcceptTravel(Package, true, true, Reason, -1, .5f, true);
        TestFalse(TEXT("Requesting a stage never shows a title in old world"), Session->ConsumeArrivalTitle(Package));
        Session->ResolveArrivalRestart(Package);
        TestEqual(TEXT("Title admission excludes capture/manual restart"), Session->ConsumeArrivalTitle(Package), Reason != ECatrunArrivalRestart::SkipIntro);
        TestFalse(TEXT("Title is consumed once"), Session->ConsumeArrivalTitle(Package));
        if (Reason != ECatrunArrivalRestart::Clear)
            TestTrue(TEXT("Capture checkpoint flag reaches restart intent"), Session->RestartIntent.bRestoreStage2EntryCheckpoint);
        Session->CancelTravel();
    }
    Session->AcceptTravel(Package, true, true, ECatrunArrivalRestart::Clear); Session->CancelTravel(); Session->ResolveArrivalRestart(Package);
    TestFalse(TEXT("Failed/cancelled arrival never displays title"), Session->ConsumeArrivalTitle(Package));
    Session->AcceptTravel(Package, true, true, ECatrunArrivalRestart::Clear); Session->Arrive(TEXT("/Game/Test/Other")); Session->ResolveArrivalRestart(Package);
    TestFalse(TEXT("Unexpected arrival cannot leak title to later world"), Session->ConsumeArrivalTitle(Package));
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunChapterSelectionTest, "Catrun.LevelFlow.ChapterSelectionUsesFreshRouteAndPreservesLocks", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunChapterSelectionTest::RunTest(const FString&)
{
    const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false);
    UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
    GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
    auto* Instance = NewObject<UGameInstance>(); World->SetGameInstance(Instance); Instance->Init();
    auto* Settings = GetMutableDefault<UCatrunLevelFlowSettings>();
    TGuardValue<TArray<FCatrunStageRoute>> Restore(Settings->Stages, Settings->Stages);
    Settings->Stages.Reset();
    for (const TCHAR* Name : {TEXT("Tutorial"), TEXT("Stage1"), TEXT("Stage2")})
    {
        auto& Route = Settings->Stages.AddDefaulted_GetRef(); Route.StageId = Name;
        Route.Map = TSoftObjectPtr<UWorld>(FSoftObjectPath(FString(TEXT("/Game/Maps/")) + Name));
    }
    FCheckpointBackend Backend;
    auto* Save = NewObject<UCatrunProgressSave>(); Save->SchemaVersion = 2; Save->StageId = TEXT("Stage1");
    UGameplayStatics::SaveGameToMemory(Save, Backend.Bytes);
    auto* Session = Instance->GetSubsystem<UCatrunFlowSession>(); Session->SetSaveBackendForTest(&Backend);
    auto Chapters = UCatrunLevelFlowLibrary::GetChapters(World);
    TestEqual(TEXT("Menu exposes all three screenshot cards"), Chapters.Num(), 3);
    TestTrue(TEXT("Reached and earlier chapters are unlocked"), Chapters[0].bUnlocked && Chapters[1].bUnlocked);
    TestFalse(TEXT("Unreached chapter stays locked"), Chapters[2].bUnlocked);
    TestFalse(TEXT("Locked stage rejects selection"), UCatrunLevelFlowLibrary::ContinueStage(World, TEXT("Stage2")));
    TestTrue(TEXT("Reached stage accepts fresh chapter travel"), UCatrunLevelFlowLibrary::ContinueStage(World, TEXT("Tutorial")));
    auto* Context = GEngine->GetWorldContextFromWorld(World);
    TestEqual(TEXT("Chapter selection is a fresh map URL with no puzzle/world state"), Context->TravelURL, FString(TEXT("/Game/Maps/Tutorial")));
    Session->ResolveArrivalRestart(TEXT("/Game/Maps/Tutorial"));
    TestTrue(TEXT("Selected chapter requests title on arrival"), Session->ConsumeArrivalTitle(TEXT("/Game/Maps/Tutorial")));
    TestFalse(TEXT("Chapter selection never carries the in-run capture checkpoint"), Session->RestartIntent.bRestoreStage2EntryCheckpoint);
    Context->TravelURL.Reset();
    Instance->Shutdown(); World->SetGameInstance(nullptr);
    GEngine->DestroyWorldContext(World); World->DestroyWorld(false);
    return true;
}
#endif
