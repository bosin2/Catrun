#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Monster/CatrunArmor.h"
#include "Monster/CatrunCapturePresentationComponent.h"
#include "Monster/CatrunRestartSubsystem.h"
#include "Monster/Tests/CatrunCaptureCallbackProbe.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "Sound/CatrunSoundSettings.h"
#include "Camera/CameraActor.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/PlayerStart.h"
#include "TimerManager.h"

namespace
{
struct FCaptureTravelFixture
{
    UWorld* World;
    UGameInstance* Instance;
    ACharacter* Cat;
    APlayerController* PC;
    ACameraActor* OriginalView;
    ACatrunArmor* Armor;
    UCatrunSoundSettings* Settings;
    FTransform Original;
    FCaptureTravelFixture()
    {
        const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false);
        World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
        GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
        Instance = NewObject<UGameInstance>(); World->SetGameInstance(Instance); Instance->Init();
        World->InitializeActorsForPlay(FURL());
        Cat = World->SpawnActor<ACharacter>(); Cat->GetCapsuleComponent()->SetCapsuleSize(20.f, 30.f);
        Cat->SetActorLocation(FVector(0,0,90));
        PC = World->SpawnActor<APlayerController>(); PC->Possess(Cat);
        // Possession dispatches ACharacter::Restart and resets the movement mode.
        // Establish the scenario only after that normal controller setup finishes.
        Cat->GetCharacterMovement()->SetMovementMode(MOVE_Flying);
        Original = Cat->GetActorTransform();
        OriginalView = World->SpawnActor<ACameraActor>(); PC->SetViewTarget(OriginalView);
        // These two input-lock layers belong to a separate presentation owner.
        PC->SetIgnoreMoveInput(true); PC->SetIgnoreLookInput(true);
        Armor = World->SpawnActor<ACatrunArmor>(); Armor->SetActorLocation(FVector(100,0,90));
        Armor->DispatchBeginPlay();
        Settings = NewObject<UCatrunSoundSettings>(Armor);
        Armor->CapturePresentation->bUseBlueprintPresentation = true;
    }
    bool ReachFade()
    {
        auto* Capture = Armor->CapturePresentation.Get();
        if (!Capture->BeginCapture(Cat, Settings)) return false;
        Capture->TickComponent(Settings->CatchCameraBlendTime + .01f, LEVELTICK_All, nullptr);
        return Capture->NotifyGrab(Capture->SessionId) && Capture->NotifyFinished(Capture->SessionId);
    }
    ACatrunArmor* SpawnWaiter()
    {
        auto* Other = World->SpawnActor<ACatrunArmor>();
        Other->SetActorLocation(FVector(500,0,90));
        Other->DispatchBeginPlay();
        Other->GetCharacterMovement()->SetMovementMode(MOVE_Flying);
        return Other;
    }
    void RequestRestart()
    {
        Armor->CapturePresentation->TickComponent(Settings->CatchFadeOutTime + Settings->CatchBlackHoldTime + .01f, LEVELTICK_All, nullptr);
    }
    void BlockOriginalReturn(FVector SafeStart)
    {
        auto AddBlock = [this](FVector Location, FVector Extent)
        {
            auto* Actor = World->SpawnActor<AActor>();
            auto* Box = NewObject<UBoxComponent>(Actor);
            Actor->SetRootComponent(Box);
            Box->SetBoxExtent(Extent);
            Box->SetCollisionProfileName(TEXT("BlockAllDynamic"));
            Box->RegisterComponent();
            Actor->SetActorLocation(Location);
        };
        AddBlock(Original.GetLocation(), FVector(35,35,50));
        AddBlock(SafeStart - FVector(0,0,42), FVector(100,100,10));
        FActorSpawnParameters Spawn;
        Spawn.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        PC->StartSpot = World->SpawnActor<APlayerStart>(SafeStart, FRotator::ZeroRotator, Spawn);
    }
    void CheckEmergencyRestored(FAutomationTestBase& Test, FVector SafeStart)
    {
        Test.TestFalse(TEXT("Recovery failure leaves capture inactive"), Armor->CapturePresentation->IsCapturing());
        Test.TestFalse(TEXT("Recovery failure clears its black fade"), PC->PlayerCameraManager->bEnableFading);
        Test.TestTrue(TEXT("Safe authored start restores collision"), Cat->GetActorEnableCollision());
        Test.TestTrue(TEXT("Cat is placed on walkable support at the authored start"), Cat->GetActorLocation().Equals(SafeStart, .1));
        Test.TestEqual(TEXT("Recovery restores the movement captured before capture"), Cat->GetCharacterMovement()->MovementMode, TEnumAsByte<EMovementMode>(MOVE_Flying));
        Test.TestTrue(TEXT("Recovery preserves input locks belonging to other owners"), PC->IsMoveInputIgnored() && PC->IsLookInputIgnored());
        PC->SetIgnoreMoveInput(false); PC->SetIgnoreLookInput(false);
        Test.TestFalse(TEXT("Recovery leaves no additional input locks"), PC->IsMoveInputIgnored() || PC->IsLookInputIgnored());
    }
    void CheckRestored(FAutomationTestBase& Test)
    {
        Test.TestFalse(TEXT("Failed travel ends capture"), Armor->CapturePresentation->IsCapturing());
        Test.TestFalse(TEXT("Failed travel releases catch reservation"), World->GetSubsystem<UCatrunRestartSubsystem>()->IsCatching());
        Test.TestTrue(TEXT("Failed travel restores the original safe transform"), Cat->GetActorTransform().Equals(Original));
        Test.TestTrue(TEXT("Failed travel restores collision"), Cat->GetActorEnableCollision());
        Test.TestEqual(TEXT("Failed travel restores movement mode"), Cat->GetCharacterMovement()->MovementMode, TEnumAsByte<EMovementMode>(MOVE_Flying));
        Test.TestTrue(TEXT("Failed travel restores the previous view"), PC->GetViewTarget() == OriginalView);
        Test.TestFalse(TEXT("Failed travel clears its black fade"), PC->PlayerCameraManager->bEnableFading);
        Test.TestTrue(TEXT("External input-lock layers survive failure"), PC->IsMoveInputIgnored() && PC->IsLookInputIgnored());
        PC->SetIgnoreMoveInput(false); PC->SetIgnoreLookInput(false);
        Test.TestFalse(TEXT("No capture move-lock layer remains"), PC->IsMoveInputIgnored());
        Test.TestFalse(TEXT("No capture look-lock layer remains"), PC->IsLookInputIgnored());
    }
    ~FCaptureTravelFixture()
    {
        if (IsValid(Armor)) Armor->CapturePresentation->AbortCapture();
        World->EndPlay(EEndPlayReason::Quit);
        Instance->Shutdown(); World->SetGameInstance(nullptr);
        GEngine->DestroyWorldContext(World); World->DestroyWorld(false);
    }
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunCaptureSingleOwnerTest, "Catrun.PrototypeAI.CaptureSingleOwnerSameFrameAndStaggeredWait", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunCaptureSingleOwnerTest::RunTest(const FString&)
{
    FCaptureTravelFixture F;
    auto* Other = F.SpawnWaiter();
    auto* Restart = F.World->GetSubsystem<UCatrunRestartSubsystem>();
    auto* First = F.Armor->CapturePresentation.Get();
    auto* Second = Other->CapturePresentation.Get();
    const FVector OtherLocation = Other->GetActorLocation();
    Other->AddMovementInput(FVector(-1,0,0));
    Other->GetCharacterMovement()->Velocity = FVector(-300,0,0);
    if (!TestTrue(TEXT("First valid captor acquires synchronously"), First->BeginCapture(F.Cat, F.Settings))) return false;
    AActor* CaptureView = F.PC->GetViewTarget();
    TestTrue(TEXT("Acquisition immediately puts other AI in WAIT"), Other->IsWaitingForCapture());
    TestFalse(TEXT("Same-frame contender is rejected"), Second->BeginCapture(F.Cat, F.Settings));
    TestEqual(TEXT("Rejected contender never begins a presentation session"), Second->SessionId, 0);
    TestEqual(TEXT("Waiter movement disabled before next movement tick"), Other->GetCharacterMovement()->MovementMode, TEnumAsByte<EMovementMode>(MOVE_None));
    Other->Tick(.5f);
    Other->GetCharacterMovement()->TickComponent(.1f, LEVELTICK_All, nullptr);
    TestTrue(TEXT("Queued input and path velocity cannot push into captured cat"), Other->GetActorLocation().Equals(OtherLocation));
    Restart->CancelCatch(Second);
    Restart->CancelCatch();
    TestTrue(TEXT("Neither rejected component nor legacy caller can release first owner"), Restart->IsCatchOwner(First));
    First->TickComponent(F.Settings->CatchCameraBlendTime + .01f, LEVELTICK_All, nullptr);
    TestTrue(TEXT("Owner alone reaches its grab"), First->NotifyGrab(First->SessionId));
    const FTransform Held = F.Cat->GetActorTransform();
    TestFalse(TEXT("Staggered contender also rejected during hold"), Second->BeginCapture(F.Cat, F.Settings));
    TestFalse(TEXT("Non-owner grab notify rejected"), Second->NotifyGrab(First->SessionId));
    TestFalse(TEXT("Non-owner finish cannot issue restart"), Second->NotifyFinished(First->SessionId));
    Second->AbortCapture();
    TestTrue(TEXT("Contender cannot change cat pose or camera"), F.Cat->GetActorTransform().Equals(Held) && F.PC->GetViewTarget() == CaptureView);
    TestEqual(TEXT("Cat movement remains owned by first capture"), F.Cat->GetCharacterMovement()->MovementMode, TEnumAsByte<EMovementMode>(MOVE_None));
    First->AbortCapture();
    TestFalse(TEXT("Cancellation releases waiter immediately"), Other->IsWaitingForCapture());
    TestEqual(TEXT("Waiter restores prior movement mode"), Other->GetCharacterMovement()->MovementMode, TEnumAsByte<EMovementMode>(MOVE_Flying));
    TestFalse(TEXT("Waiter restores animation tick state"), Other->GetMesh()->bPauseAnims);
    TestTrue(TEXT("Previously rejected contender can capture after cancellation"), Second->BeginCapture(F.Cat, F.Settings));
    Restart->CancelCatch(First);
    TestTrue(TEXT("Former owner's late release cannot cancel new owner"), Restart->IsCatchOwner(Second));
    Second->AbortCapture();
    F.CheckRestored(*this);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunCaptureFailedStartWaitTest, "Catrun.PrototypeAI.CaptureFailedStartRestoresWaitersAndAllowsRetry", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunCaptureFailedStartWaitTest::RunTest(const FString&)
{
    FCaptureTravelFixture F;
    auto* Other = F.SpawnWaiter();
    auto* Capture = F.Armor->CapturePresentation.Get();
    TestFalse(TEXT("Invalid start cannot reserve cat"), Capture->BeginCapture(nullptr, F.Settings));
    TestFalse(TEXT("Invalid start never freezes other AI"), Other->IsWaitingForCapture());
    auto* Probe = NewObject<UCatrunCaptureCallbackProbe>(F.Armor);
    Probe->Capture = Capture; Probe->AbortAt = ECatrunCapturePhase::Framing;
    Capture->OnPhaseChanged.AddDynamic(Probe, &UCatrunCaptureCallbackProbe::PhaseChanged);
    TestFalse(TEXT("Synchronous presentation cancellation reports failed start"), Capture->BeginCapture(F.Cat, F.Settings));
    TestEqual(TEXT("Initial callback actually cancelled setup"), Probe->Calls, 1);
    TestFalse(TEXT("Failed setup releases all waiting AI"), Other->IsWaitingForCapture());
    TestTrue(TEXT("Failed setup restores original view"), F.PC->GetViewTarget() == F.OriginalView);
    TestTrue(TEXT("Contender may retry after failed setup"), Other->CapturePresentation->BeginCapture(F.Cat, F.Settings));
    Other->CapturePresentation->AbortCapture();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunCaptureOwnerDestroyedTest, "Catrun.PrototypeAI.CaptureOwnerRemovalReleasesWaiters", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunCaptureOwnerDestroyedTest::RunTest(const FString&)
{
    FCaptureTravelFixture F;
    auto* Other = F.SpawnWaiter();
    if (!TestTrue(TEXT("Owner reaches hold/fade"), F.ReachFade())) return false;
    F.Armor->Destroy();
    TestFalse(TEXT("Destroying owner clears its reservation"), F.World->GetSubsystem<UCatrunRestartSubsystem>()->IsCatching());
    TestFalse(TEXT("Destroying owner resumes other AI"), Other->IsWaitingForCapture());
    TestTrue(TEXT("Owner destruction restores playable cat and view"), F.Cat->GetActorEnableCollision() && F.PC->GetViewTarget() == F.OriginalView);
    TestFalse(TEXT("Owner destruction stops owned fade"), F.PC->PlayerCameraManager->bEnableFading);
    TestTrue(TEXT("Surviving armor can acquire after owner destruction"), Other->CapturePresentation->BeginCapture(F.Cat, F.Settings));
    Other->CapturePresentation->AbortCapture();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunCaptureQueuedCancelTest, "Catrun.PrototypeAI.CaptureQueuedRestartCancelAndTravelTeardown", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunCaptureQueuedCancelTest::RunTest(const FString&)
{
    FCaptureTravelFixture F;
    auto* Other = F.SpawnWaiter();
    auto* Restart = F.World->GetSubsystem<UCatrunRestartSubsystem>();
    auto* Flow = F.World->GetSubsystem<UCatrunLevelFlowSubsystem>();
    auto* Context = GEngine->GetWorldContextFromWorld(F.World);
    if (!TestTrue(TEXT("Capture reaches fade"), F.ReachFade())) return false;
    F.RequestRestart();
    const FString FirstURL = Context->TravelURL;
    TestFalse(TEXT("Single restart was queued"), FirstURL.IsEmpty());
    F.RequestRestart();
    TestEqual(TEXT("Repeated ticks retain the same owned restart"), Context->TravelURL, FirstURL);
    TestFalse(TEXT("Other owner cannot cancel restart"), Flow->AbortOwnedTravel(Other));
    F.Armor->CapturePresentation->AbortCapture();
    TestTrue(TEXT("Explicit cancellation removes its queued URL"), Context->TravelURL.IsEmpty());
    TestFalse(TEXT("Explicit cancellation releases travel state"), Flow->IsTransitioning());
    TestFalse(TEXT("Explicit cancellation releases waiting AI"), Other->IsWaitingForCapture());
    TestFalse(TEXT("Explicit cancellation clears black fade"), F.PC->PlayerCameraManager->bEnableFading);
    if (!TestTrue(TEXT("Cancelled queued capture can retry"), F.ReachFade())) return false;
    F.RequestRestart();
    const FString ForeignURL(TEXT("/Game/Maps/Stage1?ForeignOwner"));
    Context->TravelURL = ForeignURL;
    F.Armor->CapturePresentation->AbortCapture();
    TestEqual(TEXT("Cancellation preserves subsequent foreign travel URL"), Context->TravelURL, ForeignURL);
    TestFalse(TEXT("Pending foreign travel prevents another catch"), Other->CapturePresentation->BeginCapture(F.Cat, F.Settings));
    Context->TravelURL.Reset();
    if (!TestTrue(TEXT("Final capture can acquire"), F.ReachFade())) return false;
    F.RequestRestart();
    const FString TravelURL = Context->TravelURL;
    F.Armor->CapturePresentation->EndPlay(EEndPlayReason::LevelTransition);
    TestFalse(TEXT("World exit releases capture lease"), Restart->IsCatching());
    TestEqual(TEXT("Successful world exit keeps accepted restart URL"), Context->TravelURL, TravelURL);
    TestTrue(TEXT("Successful world exit keeps travel intent"), Flow->IsTransitioning());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunCaptureQueuedOwnerDestroyedTest, "Catrun.PrototypeAI.CaptureOwnerRemovalCancelsOnlyItsQueuedRestart", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunCaptureQueuedOwnerDestroyedTest::RunTest(const FString&)
{
    FCaptureTravelFixture F;
    auto* Other = F.SpawnWaiter();
    if (!TestTrue(TEXT("Capture reaches fade"), F.ReachFade())) return false;
    F.RequestRestart();
    F.Armor->Destroy();
    TestTrue(TEXT("Removed captor's queued URL is cancelled"), GEngine->GetWorldContextFromWorld(F.World)->TravelURL.IsEmpty());
    TestFalse(TEXT("Removed captor leaves no transition lock"), F.World->GetSubsystem<UCatrunLevelFlowSubsystem>()->IsTransitioning());
    TestFalse(TEXT("Removed captor leaves no capture lease"), F.World->GetSubsystem<UCatrunRestartSubsystem>()->IsCatching());
    TestFalse(TEXT("Other AI resumes after queued owner's removal"), Other->IsWaitingForCapture());
    TestTrue(TEXT("Cat view and movement restore after queued owner's removal"), F.PC->GetViewTarget()==F.OriginalView && F.Cat->GetCharacterMovement()->MovementMode==MOVE_Flying);
    TestFalse(TEXT("Removed captor cannot leave black fade"), F.PC->PlayerCameraManager->bEnableFading);
    F.PC->SetIgnoreMoveInput(false); F.PC->SetIgnoreLookInput(false);
    TestFalse(TEXT("Capture and travel released exactly their own input layers"), F.PC->IsMoveInputIgnored() || F.PC->IsLookInputIgnored());
    TestTrue(TEXT("Surviving contender can retry"), Other->CapturePresentation->BeginCapture(F.Cat, NewObject<UCatrunSoundSettings>(Other)));
    Other->CapturePresentation->AbortCapture();
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunCaptureRejectedTravelTest, "Catrun.PrototypeAI.CaptureRestartRejectionRestoresOnlyOwnedState", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunCaptureRejectedTravelTest::RunTest(const FString&)
{
    FCaptureTravelFixture F;
    TestEqual(TEXT("Fixture is flying before capture snapshots movement"), F.Cat->GetCharacterMovement()->MovementMode, TEnumAsByte<EMovementMode>(MOVE_Flying));
    if (!TestTrue(TEXT("Fixture reaches the existing capture fade"), F.ReachFade())) return false;
    auto* Context = GEngine->GetWorldContextFromWorld(F.World);
    auto* Session = F.Instance->GetSubsystem<UCatrunFlowSession>();
    const FString OtherURL(TEXT("/Game/Maps/Stage1?ExternalOwner"));
    Context->TravelURL = OtherURL;
    Session->RestartIntent.Request(TEXT("/Game/Maps/Stage1"), .75f, true);
    F.RequestRestart();
    TestEqual(TEXT("Rejected restart does not overwrite an existing travel URL"), Context->TravelURL, OtherURL);
    TestEqual(TEXT("Rejected restart does not overwrite another arrival intent"), Session->RestartIntent.MapPackage, FString(TEXT("/Game/Maps/Stage1")));
    TestEqual(TEXT("Other arrival fade survives"), Session->RestartIntent.FadeInDuration, .75f);
    TestTrue(TEXT("Other continue intent survives"), Session->RestartIntent.bContinue);
    F.CheckRestored(*this);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunCaptureFailedTravelTest, "Catrun.PrototypeAI.CaptureRestartSameWorldFailureRestoresAndRetries", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunCaptureFailedTravelTest::RunTest(const FString&)
{
    // A recoverable injected engine failure is expected; zero permits no log on the pre-fix path.
    AddExpectedError(TEXT("Travel failed; progress retained:"), EAutomationExpectedErrorFlags::Contains, 0);
    AddExpectedError(TEXT("Injected foreign-world failure"), EAutomationExpectedErrorFlags::Contains, 1);
    FCaptureTravelFixture F;
    auto* Other = F.SpawnWaiter();
    TestEqual(TEXT("Fixture is flying before capture snapshots movement"), F.Cat->GetCharacterMovement()->MovementMode, TEnumAsByte<EMovementMode>(MOVE_Flying));
    if (!TestTrue(TEXT("Fixture reaches the existing capture fade"), F.ReachFade())) return false;
    const int32 FirstSession = F.Armor->CapturePresentation->SessionId;
    F.RequestRestart();
    TestFalse(TEXT("Restart request queues a URL; this is not arrival proof"), GEngine->GetWorldContextFromWorld(F.World)->TravelURL.IsEmpty());
    GEngine->OnTravelFailure().Broadcast(nullptr, ETravelFailure::InvalidURL, TEXT("Injected foreign-world failure"));
    TestTrue(TEXT("Foreign-world failure leaves pending capture untouched"), F.Armor->CapturePresentation->IsCapturing());
    // The engine clears its failed URL before notifying listeners. Keep that ordering explicit.
    GEngine->GetWorldContextFromWorld(F.World)->TravelURL.Reset();
    GEngine->OnTravelFailure().Broadcast(F.World, ETravelFailure::InvalidURL, TEXT("Injected same-world failure"));
    F.CheckRestored(*this);
    TestFalse(TEXT("Same-world travel failure restores waiting AI"), Other->IsWaitingForCapture());
    // Engine failure handling may queue its own fallback after the flow listener returns.
    // Retry here models the old world surviving after that fallback was cancelled.
    GEngine->GetWorldContextFromWorld(F.World)->TravelURL.Reset();
    TestTrue(TEXT("A subsequent capture can acquire ownership"), F.Armor->CapturePresentation->BeginCapture(F.Cat, F.Settings));
    TestTrue(TEXT("Retry has a new capture session"), F.Armor->CapturePresentation->SessionId > FirstSession);
    GEngine->OnTravelFailure().Broadcast(F.World, ETravelFailure::InvalidURL, TEXT("Late duplicate failure"));
    TestTrue(TEXT("A late old failure cannot abort a new capture"), F.Armor->CapturePresentation->IsCapturing());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunEmergencyRejectedTravelTest, "Catrun.PrototypeAI.EmergencyRecoveryRejectionRestoresSupportedStart", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunEmergencyRejectedTravelTest::RunTest(const FString&)
{
    FCaptureTravelFixture F;
    if (!TestTrue(TEXT("Fixture reaches capture fade"), F.ReachFade())) return false;
    const FVector SafeStart(800,0,90);
    F.BlockOriginalReturn(SafeStart);
    auto* Context = GEngine->GetWorldContextFromWorld(F.World);
    const FString OtherURL(TEXT("/Game/Maps/Stage1?ExternalOwner"));
    Context->TravelURL = OtherURL;
    F.RequestRestart();
    TestFalse(TEXT("Blocked original position initially keeps collision off"), F.Cat->GetActorEnableCollision());
    F.World->GetTimerManager().Tick(.01f);
    TestEqual(TEXT("Emergency recovery never takes over competing travel"), Context->TravelURL, OtherURL);
    F.CheckEmergencyRestored(*this, SafeStart);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunEmergencyFailedTravelTest, "Catrun.PrototypeAI.EmergencyRecoveryTravelFailureRestoresSupportedStart", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunEmergencyFailedTravelTest::RunTest(const FString&)
{
    AddExpectedError(TEXT("Travel failed; progress retained:"), EAutomationExpectedErrorFlags::Contains, 2);
    FCaptureTravelFixture F;
    if (!TestTrue(TEXT("Fixture reaches capture fade"), F.ReachFade())) return false;
    const FVector SafeStart(800,0,90);
    F.BlockOriginalReturn(SafeStart);
    F.RequestRestart();
    auto* Context = GEngine->GetWorldContextFromWorld(F.World);
    Context->TravelURL.Reset();
    GEngine->OnTravelFailure().Broadcast(F.World, ETravelFailure::InvalidURL, TEXT("Injected capture travel failure"));
    // The engine's own listener schedules a fallback URL after broadcasting. This
    // case isolates a surviving world without that fallback; the rejection test
    // above verifies that recovery respects a competing travel owner.
    Context->TravelURL.Reset();
    F.World->GetTimerManager().Tick(.01f);
    TestEqual(TEXT("Blocked original placement queued this world's emergency travel"), Context->TravelURL,
        F.World->GetOutermost()->GetName());
    TestFalse(TEXT("Collision remains off while emergency travel owns the world"), F.Cat->GetActorEnableCollision());
    Context->TravelURL.Reset();
    GEngine->OnTravelFailure().Broadcast(F.World, ETravelFailure::InvalidURL, TEXT("Injected emergency travel failure"));
    F.CheckEmergencyRestored(*this, SafeStart);
    return true;
}
#endif
