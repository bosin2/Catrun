#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Monster/CatrunArmor.h"
#include "Monster/CatrunCapturePresentationComponent.h"
#include "Monster/CatrunRestartSubsystem.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "Sound/CatrunSoundSettings.h"
#include "Camera/CameraActor.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/CapsuleComponent.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"

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
    void RequestRestart()
    {
        Armor->CapturePresentation->TickComponent(Settings->CatchFadeOutTime + Settings->CatchBlackHoldTime + .01f, LEVELTICK_All, nullptr);
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
        Armor->CapturePresentation->AbortCapture();
        World->EndPlay(EEndPlayReason::Quit);
        Instance->Shutdown(); World->SetGameInstance(nullptr);
        GEngine->DestroyWorldContext(World); World->DestroyWorld(false);
    }
};
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
    TestTrue(TEXT("A subsequent capture can acquire ownership"), F.Armor->CapturePresentation->BeginCapture(F.Cat, F.Settings));
    TestTrue(TEXT("Retry has a new capture session"), F.Armor->CapturePresentation->SessionId > FirstSession);
    GEngine->OnTravelFailure().Broadcast(F.World, ETravelFailure::InvalidURL, TEXT("Late duplicate failure"));
    TestTrue(TEXT("A late old failure cannot abort a new capture"), F.Armor->CapturePresentation->IsCapturing());
    return true;
}
#endif
