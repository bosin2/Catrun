#if WITH_DEV_AUTOMATION_TESTS

#include "LevelFlow/CatrunLevelFlow.h"
#include "Interaction/CatrunBasketInteractionComponent.h"
#include "Interaction/CatrunPuzzleSuspension.h"
#include "Monster/CatrunRestartSubsystem.h"
#include "Camera/PlayerCameraManager.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunGameplayHUDPresentationTest,
    "Catrun.UI.GameplayHUD.FollowsExistingPresentationOwners",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCatrunGameplayHUDPresentationTest::RunTest(const FString&)
{
    const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(true)
        .CreateNavigation(false).CreateAISystem(false);
    UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
    if (!TestNotNull(TEXT("Detached presentation world"), World)) return false;
    GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
    ON_SCOPE_EXIT { GEngine->DestroyWorldContext(World); World->DestroyWorld(false); };
    World->InitializeActorsForPlay(FURL());
    auto* PC = World->SpawnActor<APlayerController>();
    auto* Cat = World->SpawnActor<ACharacter>();
    auto* Camera = World->SpawnActor<AActor>();
    auto* LeaseOwner = World->SpawnActor<AActor>();
    PC->Possess(Cat);
    PC->SetViewTarget(Cat);
    Cat->GetCharacterMovement()->SetMovementMode(MOVE_Walking);
    auto Hide = [World] { return UCatrunLevelFlowLibrary::ShouldHideGameplayHUD(World); };
    TestFalse(TEXT("Normal gameplay permits the user's HUD"), Hide());
    if (!PC->PlayerCameraManager) PC->PlayerCameraManager = World->SpawnActor<APlayerCameraManager>();
    auto* Fade = PC->PlayerCameraManager.Get();
    if (!TestNotNull(TEXT("Presentation camera manager"), Fade)) return false;
    Fade->SetManualCameraFade(1.f, FLinearColor::Black, false);
    TestTrue(TEXT("Full arrival blackout hides overlays even with gameplay view and free input"), Hide());
    Fade->SetManualCameraFade(.4f, FLinearColor::Black, false);
    TestTrue(TEXT("Visible partial fade also hides overlays"), Hide());
    Fade->SetManualCameraFade(0.f, FLinearColor::Black, false);
    TestFalse(TEXT("Enabled but transparent fade restores overlays"), Hide());
    Fade->StartCameraFade(0.f, 1.f, 1.f, FLinearColor::Black, false, true);
    Fade->StopCameraFade();
    TestEqual(TEXT("Engine retains the stopped fade's endpoint"), Fade->FadeAmount, 1.f);
    TestFalse(TEXT("Stopped fade cannot latch overlays off"), Hide());
    PC->SetViewTarget(Camera);
    TestTrue(TEXT("An intro camera hides gameplay UI without rewriting its preferences"), Hide());
    PC->SetViewTarget(Cat);
    TestFalse(TEXT("Camera return restores eligibility"), Hide());
    PC->SetIgnoreMoveInput(true);
    TestTrue(TEXT("Input lease hides UI immediately"), Hide());
    PC->SetIgnoreMoveInput(false);
    Cat->GetCharacterMovement()->DisableMovement();
    TestTrue(TEXT("Opening BP's movement lock hides HUD"), Hide());
    auto* Basket = NewObject<UCatrunBasketInteractionComponent>(Cat);
    Cat->AddInstanceComponent(Basket);
    Basket->RegisterComponent();
    Basket->IsHidden = true;
    TestFalse(TEXT("Ordinary basket hiding remains gameplay"), Hide());
    Fade->SetManualCameraFade(1.f, FLinearColor::Black, false);
    TestTrue(TEXT("An active fade still hides basket overlays"), Hide());
    Fade->StopCameraFade();
    TestFalse(TEXT("Ending fade restores ordinary basket overlays"), Hide());
    Basket->IsHidden = false;
    Basket->Busy = true;
    TestFalse(TEXT("Ordinary bell action keeps overlays without a visible fade"), Hide());
    Fade->SetManualCameraFade(.4f, FLinearColor::Black, false);
    TestTrue(TEXT("An active fade also hides busy-action overlays"), Hide());
    Fade->StopCameraFade();
    TestFalse(TEXT("Ending fade restores ordinary bell overlays"), Hide());
    Basket->Busy = false;
    Cat->GetCharacterMovement()->SetMovementMode(MOVE_Walking);

    auto* Flow = World->GetSubsystem<UCatrunLevelFlowSubsystem>();
    TestTrue(TEXT("Exit takes the existing reservation"), Flow->ReserveExitTransition(LeaseOwner));
    TestTrue(TEXT("Exit remains hidden even before its sequence starts"), Hide());
    Flow->ReleaseExitTransition(LeaseOwner);
    TestFalse(TEXT("Cancelled exit restores normal eligibility"), Hide());
    auto* Suspension = World->GetSubsystem<UCatrunPuzzleSuspension>();
    TestTrue(TEXT("Puzzle reveal takes existing suspension"), Suspension->Acquire(LeaseOwner));
    TestTrue(TEXT("Puzzle camera reveal hides HUD"), Hide());
    Suspension->Release(LeaseOwner);
    TestFalse(TEXT("Puzzle reveal completion restores eligibility"), Hide());

    auto* Settings = GetMutableDefault<UCatrunLevelFlowSettings>();
    const auto PreviousMenu = Settings->MainMenuMap;
    Settings->MainMenuMap = TSoftObjectPtr<UWorld>(FSoftObjectPath(World->GetOutermost()->GetName()));
    TestTrue(TEXT("Main menu suppresses gameplay and saving notices regardless of input state"), Hide());
    TestTrue(TEXT("Existing world identity refreshes after a settings change"), Flow->IsMainMenuWorld());
    UWorld* OtherWorld = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
    if (TestNotNull(TEXT("Replacement world has its own identity"), OtherWorld))
    {
        TestFalse(TEXT("Replacement world does not inherit prior menu identity"), OtherWorld->GetSubsystem<UCatrunLevelFlowSubsystem>()->IsMainMenuWorld());
        OtherWorld->DestroyWorld(false);
    }
    Settings->MainMenuMap = PreviousMenu;
    TestFalse(TEXT("Settings restoration invalidates the static menu identity only"), Flow->IsMainMenuWorld());
    TestFalse(TEXT("Map policy does not latch hidden state into later gameplay"), Hide());
    return true;
}

#endif
