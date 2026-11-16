#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "Monster/CatrunRestartSubsystem.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "UObject/Package.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunArrivalTokenOwnerTest, "Catrun.LevelFlow.RestartArrivalCancellationHonorsTravelToken", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunArrivalTokenOwnerTest::RunTest(const FString&)
{
    auto* Session = NewObject<UCatrunFlowSession>(NewObject<UGameInstance>());
    const FString Package(TEXT("/Game/Maps/Tutorial"));
    Session->RestartIntent.Request(TEXT("/Game/Maps/Stage1"), .25f, true);
    const uint64 Failed = Session->AcceptTravel(Package, false, false, ECatrunArrivalRestart::SkipIntro, -1, .75f);
    TestEqual(TEXT("Accepting travel does not prematurely replace arrival intent"), Session->RestartIntent.MapPackage, FString(TEXT("/Game/Maps/Stage1")));
    Session->CancelTravel(Failed);
    Session->ResolveArrivalRestart(Package);
    TestEqual(TEXT("Cancelled travel does not publish a restart intent"), Session->RestartIntent.MapPackage, FString(TEXT("/Game/Maps/Stage1")));
    const uint64 Old = Session->AcceptTravel(Package, false, false, ECatrunArrivalRestart::SkipIntro, -1, .75f);
    const uint64 New = Session->AcceptTravel(Package, false, false, ECatrunArrivalRestart::SkipIntro, -1, .75f);
    TestTrue(TEXT("Identical restart values still receive different ownership tokens"), Old != New);
    Session->CancelTravel(Old);
    Session->ResolveArrivalRestart(Package);
    float Fade = 0.f;
    TestTrue(TEXT("An old failure cannot cancel a newer identical destination"), Session->RestartIntent.Consume(Package, Fade));
    TestEqual(TEXT("Arrival carries the original capture fade duration"), Fade, .75f);
    Session->ResolveArrivalRestart(Package);
    TestFalse(TEXT("Arrival intent is published and consumed once"), Session->RestartIntent.Consume(Package, Fade));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunPresentationTravelOwnerTest, "Catrun.LevelFlow.PresentationTravelFailureReturnsToOwningBlueprint", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunPresentationTravelOwnerTest::RunTest(const FString&)
{
    AddExpectedError(TEXT("Travel failed; progress retained:"), EAutomationExpectedErrorFlags::Contains, 0);
    const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false);
    UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
    GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
    World->InitializeActorsForPlay(FURL());
    auto* Routes = GetMutableDefault<UCatrunLevelFlowSettings>();
    TGuardValue<TArray<FCatrunStageRoute>> RestoreRoutes(Routes->Stages, Routes->Stages);
    Routes->Stages.Reset();
    auto& Tutorial = Routes->Stages.AddDefaulted_GetRef(); Tutorial.StageId = TEXT("Tutorial");
    Tutorial.Map = TSoftObjectPtr<UWorld>(FSoftObjectPath(World->GetOutermost()->GetName()));
    auto& Stage1 = Routes->Stages.AddDefaulted_GetRef(); Stage1.StageId = TEXT("Stage1");
    Stage1.Map = TSoftObjectPtr<UWorld>(FSoftObjectPath(TEXT("/Game/Maps/Stage1.Stage1")));
    auto* Owner = World->SpawnActor<AActor>();
    auto* OtherOwner = World->SpawnActor<AActor>();
    auto* Flow = World->GetSubsystem<UCatrunLevelFlowSubsystem>();
    int32 FailureCount = 0;
    TestTrue(TEXT("Original BP can reserve its travel while it plays its own sequence"), UCatrunLevelFlowLibrary::ReserveStagePresentation(Owner));
    TestFalse(TEXT("A competing presentation cannot take ownership"), UCatrunLevelFlowLibrary::ReserveStagePresentation(OtherOwner));
    TestFalse(TEXT("Capture cannot acquire during the original stair presentation"), World->GetSubsystem<UCatrunRestartSubsystem>()->TryBeginCatch());
    TestFalse(TEXT("An unrelated owner cannot complete the reserved transition"), Flow->CompleteStageWithFailure(OtherOwner, {}));
    TestTrue(TEXT("Reserved owner can submit normal tutorial travel"), Flow->CompleteStageWithFailure(Owner, [&](const FString&)
    {
        ++FailureCount;
        UCatrunLevelFlowLibrary::ReleaseStagePresentation(Owner);
        TestFalse(TEXT("Flow clears its travel before BP cleanup runs"), Flow->IsTransitioning());
    }));
    auto* Context = GEngine->GetWorldContextFromWorld(World);
    TestEqual(TEXT("Tutorial completion retains its original arrival option"), Context->TravelURL, FString(TEXT("/Game/Maps/Stage1?FromTutorial")));
    const FString Replacement(TEXT("/Game/Maps/Stage2?ReplacementOwner"));
    Context->TravelURL = Replacement;
    GEngine->OnTravelFailure().Broadcast(World, ETravelFailure::InvalidURL, TEXT("Injected original stair failure"));
    TestEqual(TEXT("Only this presentation receives one failure callback"), FailureCount, 1);
    // The default engine failure handler may choose its own recovery URL. The flow
    // must never clear a replacement URL while releasing its old request.
    TestFalse(TEXT("Replacement travel is not erased by owner cleanup"), Context->TravelURL.IsEmpty());
    GEngine->OnTravelFailure().Broadcast(World, ETravelFailure::InvalidURL, TEXT("Duplicate original stair failure"));
    TestEqual(TEXT("Duplicate engine notification does not repeat owner cleanup"), FailureCount, 1);
    Context->TravelURL.Reset();
    TestTrue(TEXT("BP can reserve a fresh attempt after cleanup"), UCatrunLevelFlowLibrary::ReserveStagePresentation(Owner));
    UCatrunLevelFlowLibrary::ReleaseStagePresentation(Owner);
    World->EndPlay(EEndPlayReason::Quit);
    GEngine->DestroyWorldContext(World); World->DestroyWorld(false);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunStage2PortalArrivalGateTest, "Catrun.LevelFlow.Stage2PortalArrivalRequiresExactMapAndFreshRoute", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunStage2PortalArrivalGateTest::RunTest(const FString&)
{
    struct FArrivalCase
    {
        const TCHAR* Name;
        const TCHAR* Option;
        ECatrunArrivalRestart Intent;
        bool bExactMap;
        bool bExpectedArrival;
    };
    const FArrivalCase Cases[] = {
        {TEXT("Qualified portal arrival"), TEXT("FromStage1Portal"), ECatrunArrivalRestart::Clear, true, true},
        {TEXT("Direct load"), nullptr, ECatrunArrivalRestart::Preserve, true, false},
        {TEXT("Similar option name"), TEXT("FromStage1PortalPreview"), ECatrunArrivalRestart::Preserve, true, false},
        {TEXT("Same short name in another directory"), TEXT("FromStage1Portal"), ECatrunArrivalRestart::Preserve, false, false},
        {TEXT("Restart with a stale portal option"), TEXT("FromStage1Portal"), ECatrunArrivalRestart::SkipIntro, true, false},
        {TEXT("Continue with a stale portal option"), TEXT("FromStage1Portal"), ECatrunArrivalRestart::Continue, true, false},
    };
    auto* Settings = GetMutableDefault<UCatrunLevelFlowSettings>();
    TGuardValue<TArray<FCatrunStageRoute>> RestoreRoutes(Settings->Stages, TArray<FCatrunStageRoute>());
    auto& Stage2 = Settings->Stages.AddDefaulted_GetRef();
    Stage2.StageId = TEXT("Stage2");
    const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false);
    for (const auto& Case : Cases)
    {
        const FString Directory = FString(TEXT("/Temp/CatrunPortalArrival/")) + FGuid::NewGuid().ToString(EGuidFormats::Digits);
        const FString Package = Directory + TEXT("/Stage2");
        Stage2.Map = TSoftObjectPtr<UWorld>(FSoftObjectPath(Case.bExactMap ? Package : FString(TEXT("/Game/Maps/Stage2"))));
        UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, CreatePackage(*(Directory + TEXT("/UEDPIE_0_Stage2"))),
            true, ERHIFeatureLevel::Num, &Init);
        GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
        auto* Instance = NewObject<UGameInstance>();
        World->SetGameInstance(Instance);
        Instance->Init();
        auto* Session = Instance->GetSubsystem<UCatrunFlowSession>();
        if (Case.Intent != ECatrunArrivalRestart::Preserve)
            Session->AcceptTravel(Package, false, false, Case.Intent);
        FURL ArrivalURL;
        if (Case.Option) ArrivalURL.AddOption(Case.Option);
        World->InitializeActorsForPlay(ArrivalURL);
        TestEqual(FString::Printf(TEXT("%s before restart intent resolution"), Case.Name),
            UCatrunLevelFlowLibrary::IsStage2PortalArrival(World), Case.bExpectedArrival);
        const bool bSkipIntro = Case.Intent == ECatrunArrivalRestart::SkipIntro || Case.Intent == ECatrunArrivalRestart::Continue;
        TestEqual(FString::Printf(TEXT("%s uses the normal restart intent"), Case.Name),
            UCatrunLevelFlowLibrary::ShouldSkipStageIntro(World), bSkipIntro);
        TestEqual(FString::Printf(TEXT("%s after restart intent resolution"), Case.Name),
            UCatrunLevelFlowLibrary::IsStage2PortalArrival(World), Case.bExpectedArrival);
        Instance->Shutdown();
        World->SetGameInstance(nullptr);
        GEngine->DestroyWorldContext(World);
        World->DestroyWorld(false);
    }
    return true;
}

#endif
