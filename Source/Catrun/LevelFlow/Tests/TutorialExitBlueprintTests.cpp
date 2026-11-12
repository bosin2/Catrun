#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "UObject/StructOnScope.h"
#include "UObject/UnrealType.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunTutorialExitBlueprintTest,
    "Catrun.LevelFlow.TutorialExitBlueprintFailureRecoversAndRearms",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCatrunTutorialExitBlueprintTest::RunTest(const FString&)
{
    AddExpectedError(TEXT("Travel failed; progress retained: Injected tutorial BP travel failure"),
        EAutomationExpectedErrorFlags::Contains, 1);
    // The failure notice can be created, but this world intentionally has no viewport.
    AddExpectedError(TEXT("No game viewport was found."), EAutomationExpectedErrorFlags::Contains, 0);
    UClass* ExitClass = LoadClass<AActor>(nullptr, TEXT("/Game/Systems/LevelFlow/BP_LevelExit.BP_LevelExit_C"));
    if (!TestNotNull(TEXT("Saved tutorial exit class"), ExitClass)) return false;

    const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false)
        .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false);
    UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
    if (!TestNotNull(TEXT("Detached game world"), World)) return false;
    FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
    Context.SetCurrentWorld(World);
    auto* Instance = NewObject<UGameInstance>();
    World->SetGameInstance(Instance);
    Instance->Init();
    ON_SCOPE_EXIT
    {
        Context.TravelURL.Reset();
        World->EndPlay(EEndPlayReason::Quit);
        Instance->Shutdown();
        World->SetGameInstance(nullptr);
        GEngine->DestroyWorldContext(World);
        World->DestroyWorld(false);
    };

    auto* Settings = GetMutableDefault<UCatrunLevelFlowSettings>();
    TGuardValue<TArray<FCatrunStageRoute>> RestoreRoutes(Settings->Stages, Settings->Stages);
    Settings->Stages.Reset();
    auto& Tutorial = Settings->Stages.AddDefaulted_GetRef();
    Tutorial.StageId = TEXT("Tutorial");
    Tutorial.Map = TSoftObjectPtr<UWorld>(FSoftObjectPath(World->GetOutermost()->GetName()));
    auto& Stage1 = Settings->Stages.AddDefaulted_GetRef();
    Stage1.StageId = TEXT("Stage1");
    Stage1.Map = TSoftObjectPtr<UWorld>(FSoftObjectPath(TEXT("/Game/Maps/Stage1.Stage1")));
    World->InitializeActorsForPlay(FURL());

    auto* Cat = World->SpawnActor<ACharacter>();
    auto* PC = World->SpawnActor<APlayerController>();
    auto* Exit = World->SpawnActor<AActor>(ExitClass, FVector(1000, 0, 0), FRotator::ZeroRotator);
    auto* CompetingOwner = World->SpawnActor<AActor>();
    auto* FloorActor = World->SpawnActor<AActor>();
    auto* Flow = World->GetSubsystem<UCatrunLevelFlowSubsystem>();
    if (!TestNotNull(TEXT("Player pawn"), Cat) || !TestNotNull(TEXT("Controller"), PC)
        || !TestNotNull(TEXT("Tutorial exit instance"), Exit) || !TestNotNull(TEXT("Competing owner"), CompetingOwner)
        || !TestNotNull(TEXT("Test floor"), FloorActor) || !TestNotNull(TEXT("Travel subsystem"), Flow)) return false;

    auto* Floor = NewObject<UBoxComponent>(FloorActor);
    FloorActor->SetRootComponent(Floor);
    Floor->SetBoxExtent(FVector(300, 300, 10));
    Floor->SetCollisionProfileName(TEXT("BlockAll"));
    Floor->RegisterComponent();
    FloorActor->SetActorLocation(FVector(0, 0, -10));
    Cat->GetCapsuleComponent()->SetCapsuleSize(20.f, 30.f);
    Cat->SetActorLocation(FVector(0, 0, 34));
    PC->SetPlayer(NewObject<ULocalPlayer>(GEngine));
    PC->Possess(Cat);
    const FTransform OriginalPose = Cat->GetActorTransform();
    auto* Camera = PC->PlayerCameraManager.Get();
    if (!TestNotNull(TEXT("Player camera manager"), Camera)
        || !TestTrue(TEXT("BP finds the possessed pawn via player index zero"),
            UGameplayStatics::GetPlayerPawn(Exit, 0) == Cat)) return false;

    auto* Started = FindFProperty<FBoolProperty>(ExitClass, TEXT("TransitionStarted"));
    auto* Requested = FindFProperty<FBoolProperty>(ExitClass, TEXT("ExitTravelRequested"));
    auto* Recovering = FindFProperty<FBoolProperty>(ExitClass, TEXT("RestoringExit"));
    auto* Begin = Exit->FindFunction(TEXT("BeginTransition"));
    auto* Complete = Exit->FindFunction(TEXT("CompleteTransition"));
    auto* Recover = Exit->FindFunction(TEXT("RecoverFailedStageExit"));
    if (!TestNotNull(TEXT("TransitionStarted"), Started) || !TestNotNull(TEXT("ExitTravelRequested"), Requested)
        || !TestNotNull(TEXT("RestoringExit"), Recovering) || !TestNotNull(TEXT("BeginTransition"), Begin)
        || !TestNotNull(TEXT("CompleteTransition"), Complete) || !TestNotNull(TEXT("RecoverFailedStageExit"), Recover)) return false;
    const auto Invoke = [Exit](UFunction* Function)
    {
        FStructOnScope Params(Function);
        Exit->ProcessEvent(Function, Params.GetStructMemory());
    };

    if (!TestTrue(TEXT("A separate owner reserves presentation"),
        UCatrunLevelFlowLibrary::ReserveStagePresentation(CompetingOwner))) return false;
    Camera->SetManualCameraFade(.4f, FLinearColor::Black, false);
    Invoke(Begin);
    TestFalse(TEXT("Denied reservation does not start the exit"), Started->GetPropertyValue_InContainer(Exit));
    TestFalse(TEXT("Denied reservation does not lock input"), PC->IsMoveInputIgnored());
    TestTrue(TEXT("Denied reservation keeps the existing fade"), Camera->bEnableFading && FMath::IsNearlyEqual(Camera->FadeAmount, .4f));
    TestTrue(TEXT("Denied reservation leaves the other owner intact"), Flow->IsTransitioning());
    UCatrunLevelFlowLibrary::ReleaseStagePresentation(CompetingOwner);
    Camera->StopCameraFade();

    Invoke(Begin);
    if (!TestTrue(TEXT("The saved BP reserves the exit before presenting"),
        Flow->IsTransitioning() && Started->GetPropertyValue_InContainer(Exit))
        || !TestTrue(TEXT("The exit acquires its movement lock and fade"), PC->IsMoveInputIgnored() && Camera->bEnableFading)) return false;
    PC->SetIgnoreMoveInput(true);
    PC->SetIgnoreLookInput(true);
    const FString OtherURL(TEXT("/Game/Maps/Stage1?ExternalOwner"));
    Context.TravelURL = OtherURL;
    Invoke(Complete);
    TestEqual(TEXT("Synchronous rejection preserves the other travel URL"), Context.TravelURL, OtherURL);
    TestFalse(TEXT("Synchronous rejection releases the exit"), Flow->IsTransitioning() || Started->GetPropertyValue_InContainer(Exit));
    TestFalse(TEXT("Synchronous rejection clears the exit fade"), Camera->bEnableFading);
    Invoke(Recover);
    TestTrue(TEXT("Repeated cleanup leaves unrelated input locks intact"), PC->IsMoveInputIgnored() && PC->IsLookInputIgnored());
    PC->SetIgnoreMoveInput(false);
    PC->SetIgnoreLookInput(false);
    TestFalse(TEXT("Exactly one movement-lock layer was released"), PC->IsMoveInputIgnored());
    Context.TravelURL.Reset();

    Invoke(Begin);
    Invoke(Complete);
    if (!TestTrue(TEXT("Retry queues tutorial travel with the existing arrival option"),
        Context.TravelURL.StartsWith(TEXT("/Game/Maps/Stage1?")) && Context.TravelURL.Contains(TEXT("?FromTutorial")))) return false;
    TestTrue(TEXT("Accepted travel keeps the BP active pending arrival"),
        Started->GetPropertyValue_InContainer(Exit) && Requested->GetPropertyValue_InContainer(Exit));
    AddExpectedError(TEXT("TravelFailure: InvalidURL, Reason for Failure: 'Injected foreign-world failure' with a NULL UWorld"),
        EAutomationExpectedErrorFlags::Contains, 1);
    GEngine->OnTravelFailure().Broadcast(nullptr, ETravelFailure::InvalidURL, TEXT("Injected foreign-world failure"));
    TestTrue(TEXT("Foreign-world failure cannot release this BP"),
        Flow->IsTransitioning() && PC->IsMoveInputIgnored() && Camera->bEnableFading);

    Cat->SetActorEnableCollision(false);
    Cat->SetActorLocation(FVector(100, 100, 70), false, nullptr, ETeleportType::TeleportPhysics);
    PC->SetIgnoreMoveInput(true);
    Context.TravelURL.Reset();
    GEngine->OnTravelFailure().Broadcast(World, ETravelFailure::InvalidURL, TEXT("Injected tutorial BP travel failure"));
    TestFalse(TEXT("Same-world failure releases the travel reservation"), Flow->IsTransitioning());
    TestFalse(TEXT("Same-world failure rearms the BP"), Started->GetPropertyValue_InContainer(Exit)
        || Requested->GetPropertyValue_InContainer(Exit) || Recovering->GetPropertyValue_InContainer(Exit));
    TestFalse(TEXT("Same-world failure removes the exit fade"), Camera->bEnableFading);
    TestTrue(TEXT("Same-world failure restores the pawn pose and collision"),
        Cat->GetActorTransform().Equals(OriginalPose) && Cat->GetActorEnableCollision());
    GEngine->OnTravelFailure().Broadcast(World, ETravelFailure::InvalidURL, TEXT("Duplicate tutorial BP travel failure"));
    TestTrue(TEXT("Duplicate engine failure cannot remove the external lock"), PC->IsMoveInputIgnored());
    PC->SetIgnoreMoveInput(false);
    TestFalse(TEXT("No extra exit movement lock remains"), PC->IsMoveInputIgnored());

    // The engine may queue its fallback after the injected failure notification.
    Context.TravelURL.Reset();
    Invoke(Begin);
    TestTrue(TEXT("The recovered BP can acquire a fresh attempt"),
        Flow->IsTransitioning() && Started->GetPropertyValue_InContainer(Exit) && PC->IsMoveInputIgnored());
    Invoke(Recover);
    TestFalse(TEXT("Explicit final cleanup leaves no owned state"),
        Flow->IsTransitioning() || PC->IsMoveInputIgnored() || Camera->bEnableFading);
    return true;
}
#endif
