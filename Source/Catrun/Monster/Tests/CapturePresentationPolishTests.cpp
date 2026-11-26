#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Monster/CatrunArmor.h"
#include "Monster/CatrunCapturePresentationComponent.h"
#include "Monster/CatrunMarkSubsystem.h"
#include "Sound/CatrunSoundSettings.h"
#include "Sound/SoundGridManager.h"
#include "Camera/CameraActor.h"
#include "Components/CapsuleComponent.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "UObject/UnrealType.h"

namespace
{
// A played world with a marked cat, a settings source for the orb and one armor that can capture.
struct FCaptureMarkFixture
{
    UWorld* World;
    UGameInstance* Instance;
    ACharacter* Cat;
    APlayerController* PC;
    ACatrunArmor* Armor;
    UCatrunSoundSettings* Settings;
    UCatrunMarkSubsystem* Marks;
    FCaptureMarkFixture()
    {
        const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false);
        World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
        GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
        Instance = NewObject<UGameInstance>(); World->SetGameInstance(Instance); Instance->Init();
        World->InitializeActorsForPlay(FURL());
        Cat = World->SpawnActor<ACharacter>(); Cat->GetCapsuleComponent()->SetCapsuleSize(20.f, 30.f);
        Cat->SetActorLocation(FVector(0, 0, 90));
        PC = World->SpawnActor<APlayerController>(); PC->Possess(Cat);
        Cat->GetCharacterMovement()->SetMovementMode(MOVE_Flying);
        PC->SetViewTarget(World->SpawnActor<ACameraActor>());
        auto* Manager = World->SpawnActor<ASoundGridManager>();
        Settings = NewObject<UCatrunSoundSettings>(Manager);
        FindFProperty<FObjectPropertyBase>(ASoundGridManager::StaticClass(), TEXT("Settings"))->SetObjectPropertyValue_InContainer(Manager, Settings);
        Armor = World->SpawnActor<ACatrunArmor>(); Armor->SetActorLocation(FVector(100, 0, 90));
        Armor->DispatchBeginPlay();
        Armor->CapturePresentation->bUseBlueprintPresentation = true;
        Marks = World->GetSubsystem<UCatrunMarkSubsystem>();
    }
    ~FCaptureMarkFixture()
    {
        if (IsValid(Armor)) Armor->CapturePresentation->AbortCapture();
        Marks->ClearMark(TEXT("test teardown"));
        World->EndPlay(EEndPlayReason::Quit);
        Instance->Shutdown(); World->SetGameInstance(nullptr);
        GEngine->DestroyWorldContext(World); World->DestroyWorld(false);
    }
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunMarkVisualSuppressionTest, "Catrun.Monsters.MarkVisualSuppressionKeepsMark", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunMarkVisualSuppressionTest::RunTest(const FString&)
{
    FCaptureMarkFixture F;
    F.Marks->ApplyMark(*F.Cat);
    if (!TestTrue(TEXT("Mark applies"), F.Marks->IsMarked())) return false;
    if (!TestTrue(TEXT("Mark orb and light are shown"), F.Marks->IsVisualShown())) return false;
    UObject* First = NewObject<UCatrunSoundSettings>(GetTransientPackage());
    UObject* Second = NewObject<UCatrunSoundSettings>(GetTransientPackage());
    F.Marks->SetVisualSuppressed(First, true);
    TestFalse(TEXT("Suppressed orb is hidden"), F.Marks->IsVisualShown());
    TestTrue(TEXT("Suppression keeps the mark"), F.Marks->IsMarked());
    F.Marks->SetVisualSuppressed(Second, true);
    F.Marks->SetVisualSuppressed(First, false);
    TestFalse(TEXT("Another owner still hides the orb"), F.Marks->IsVisualShown());
    F.Marks->ClearMark(TEXT("test"));
    F.Marks->ApplyMark(*F.Cat);
    TestFalse(TEXT("A mark applied while suppressed starts hidden"), F.Marks->IsVisualShown());
    F.Marks->SetVisualSuppressed(Second, false);
    TestTrue(TEXT("The last release shows the orb again"), F.Marks->IsVisualShown());
    UObject* Lost = NewObject<UCatrunSoundSettings>(GetTransientPackage());
    F.Marks->SetVisualSuppressed(Lost, true);
    Lost->MarkAsGarbage();
    F.Marks->SetVisualSuppressed(First, false); // any refresh prunes owners that no longer exist
    TestFalse(TEXT("A destroyed owner no longer suppresses"), F.Marks->IsVisualSuppressed());
    TestTrue(TEXT("A destroyed owner cannot keep the orb hidden"), F.Marks->IsVisualShown());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunCaptureHidesMarkTest, "Catrun.PrototypeAI.CaptureHidesMarkVisualOnlyWhileOwning", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunCaptureHidesMarkTest::RunTest(const FString&)
{
    FCaptureMarkFixture F;
    F.Marks->ApplyMark(*F.Cat);
    if (!TestTrue(TEXT("Orb shown before capture"), F.Marks->IsVisualShown())) return false;
    auto* Capture = F.Armor->CapturePresentation.Get();
    if (!TestTrue(TEXT("Capture begins"), Capture->BeginCapture(F.Cat, F.Settings))) return false;
    TestFalse(TEXT("Capture hides the orb and its light"), F.Marks->IsVisualShown());
    TestTrue(TEXT("Capture does not clear the mark"), F.Marks->IsMarked());
    Capture->TickComponent(F.Settings->CatchCameraBlendTime + .01f, LEVELTICK_All, nullptr);
    TestFalse(TEXT("Orb stays hidden through framing"), F.Marks->IsVisualShown());
    Capture->AbortCapture();
    TestFalse(TEXT("Capture ended"), Capture->IsCapturing());
    TestTrue(TEXT("Ended capture restores the orb"), F.Marks->IsVisualShown());
    TestTrue(TEXT("Mark is still there after capture"), F.Marks->IsMarked());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunCaptureCameraCutRuleTest, "Catrun.PrototypeAI.CaptureCameraCutsOnlyJumps", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunCaptureCameraCutRuleTest::RunTest(const FString&)
{
    using C = UCatrunCapturePresentationComponent;
    const float Cut = GetDefault<C>()->CameraCutDistance;
    TestTrue(TEXT("Default cut distance is small next to the measured 68 cm jump"), Cut > 2.5f && Cut < 68.f);
    TestTrue(TEXT("A 68 cm snap past an obstacle is a cut"), C::ShouldCutCameraMove(68.f, true, 1.f, Cut));
    TestTrue(TEXT("A settled shot that jumps is a cut"), C::ShouldCutCameraMove(68.f, false, 1.f, Cut));
    TestFalse(TEXT("Normal settled drift (2.4 cm) is not a cut"), C::ShouldCutCameraMove(2.4f, false, 1.f, Cut));
    TestFalse(TEXT("The fast entry blend (62 cm) is not a cut"), C::ShouldCutCameraMove(62.f, false, .5f, Cut));
    TestTrue(TEXT("A snap during the entry blend is a cut"), C::ShouldCutCameraMove(62.f, true, .5f, Cut));
    TestFalse(TEXT("A short snap is not a cut"), C::ShouldCutCameraMove(Cut * .5f, true, 1.f, Cut));
    return true;
}
#endif
