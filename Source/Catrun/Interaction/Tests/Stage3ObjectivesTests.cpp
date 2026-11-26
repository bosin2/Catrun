#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Interaction/CatrunStage3Objectives.h"
#include "Interaction/CatrunPuzzleRevealComponent.h"
#include "Interaction/CatrunPuzzleSuspension.h"
#include "Components/CapsuleComponent.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "Camera/CameraActor.h"
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

namespace Stage3FinalGateTest
{
    constexpr float GateCurveTolerance = 1e-4f;

    AActor* SpawnLeaf(UWorld* World, const FVector& Location)
    {
        AActor* Leaf = World->SpawnActor<AActor>();
        USceneComponent* Root = NewObject<USceneComponent>(Leaf, TEXT("Root"));
        Root->SetMobility(EComponentMobility::Movable);
        Leaf->SetRootComponent(Root);
        Root->RegisterComponent();
        Leaf->SetActorLocation(Location);
        return Leaf;
    }

    struct FRig
    {
        UWorld* World = nullptr;
        ACatrunStage3Objectives* Objectives = nullptr;
        AActor* Left = nullptr;
        AActor* Right = nullptr;
        FVector Start = FVector(100.f, 50.f, 0.f);

        FRig()
        {
            const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false);
            World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
            GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
            Left = SpawnLeaf(World, Start);
            Right = SpawnLeaf(World, Start);
            // Leaves must be assigned before BeginPlay, which records their start positions.
            Objectives = World->SpawnActorDeferred<ACatrunStage3Objectives>(ACatrunStage3Objectives::StaticClass(), FTransform::Identity);
            Objectives->FinalLeafLeft = Left;
            Objectives->FinalLeafRight = Right;
            Objectives->FinishSpawning(FTransform::Identity);
            if (!Objectives->HasActorBegunPlay()) Objectives->DispatchBeginPlay();
        }
        ~FRig()
        {
            World->DestroyWorld(false);
            GEngine->DestroyWorldContext(World);
        }
        float LeftOffset() const { return Start.X - Left->GetActorLocation().X; }
        float RightOffset() const { return Right->GetActorLocation().X - Start.X; }
    };
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FStage3FinalGateCurveTest, "Catrun.Stage3.FinalGateCurve", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FStage3FinalGateCurveTest::RunTest(const FString&)
{
    using T = ACatrunStage3Objectives;
    TestEqual(TEXT("Closed at start"), T::FinalGateOffsetAt(0.f), 0.f);
    TestEqual(TEXT("Still during the unlatch hold"), T::FinalGateOffsetAt(T::FinalGateHold), 0.f);
    TestEqual(TEXT("Fully open at 3.45 s"), T::FinalGateOffsetAt(T::FinalGateDuration), T::FinalGateTravel);
    TestEqual(TEXT("Stays open afterwards"), T::FinalGateOffsetAt(10.f), T::FinalGateTravel);
    float Previous = 0.f;
    bool bMonotonicOutward = true;
    for (int32 Ms = 0; Ms <= 3450; ++Ms)
    {
        const float Offset = T::FinalGateOffsetAt(Ms * .001f);
        if (Offset < 0.f || Offset + Stage3FinalGateTest::GateCurveTolerance < Previous || Offset > T::FinalGateTravel) bMonotonicOutward = false;
        Previous = Offset;
    }
    TestTrue(TEXT("Leaves only move outward (no seam overlap) and never overshoot"), bMonotonicOutward);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FStage3FinalGateTimingTest, "Catrun.Stage3.FinalGateReachesStopsAt345", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FStage3FinalGateTimingTest::RunTest(const FString&)
{
    Stage3FinalGateTest::FRig Rig;
    Rig.Objectives->bFinalGateOpen = true;
    constexpr float Dt = 1.f / 60.f;
    int32 Ticks = 0;
    while (Rig.Objectives->IsActorTickEnabled() && Ticks < 208)
    {
        Rig.Objectives->Tick(Dt);
        ++Ticks;
        if (Ticks == 206)
            TestTrue(TEXT("Not yet at the stops just before 3.45 s"), Rig.LeftOffset() < ACatrunStage3Objectives::FinalGateTravel);
    }
    TestFalse(TEXT("Tick disabled by tick 208"), Rig.Objectives->IsActorTickEnabled());
    TestTrue(TEXT("Reached the stops at 207 ticks (3.45 s) +/- 1"), Ticks >= 206 && Ticks <= 208);
    TestEqual(TEXT("Left leaf fully open"), Rig.LeftOffset(), ACatrunStage3Objectives::FinalGateTravel, .01f);
    TestEqual(TEXT("Right leaf fully open"), Rig.RightOffset(), ACatrunStage3Objectives::FinalGateTravel, .01f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FStage3FinalGateIndependentTest, "Catrun.Stage3.FinalGateIgnoresCatStateAndSeat", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FStage3FinalGateIndependentTest::RunTest(const FString&)
{
    // No player pawn (GameplayAvailable == false, the same early-out as a Busy/hidden/input-blocked cat),
    // no released devices and no seated statue: an opening that has started must still finish on time.
    Stage3FinalGateTest::FRig Rig;
    Rig.Objectives->Devices.SetNum(3);
    Rig.Objectives->Puzzle = nullptr;
    Rig.Objectives->bFinalGateOpen = true;
    for (int32 I = 0; I < 10; ++I) Rig.Objectives->Tick(.1f);
    TestEqual(TEXT("Progress at 1.0 s follows the curve"), Rig.LeftOffset(), ACatrunStage3Objectives::FinalGateOffsetAt(1.f), .05f);
    TestTrue(TEXT("Still opening at 1.0 s"), Rig.Objectives->IsActorTickEnabled());
    for (int32 I = 0; I < 49; ++I) Rig.Objectives->Tick(.05f);
    TestFalse(TEXT("Finished at 3.45 s total"), Rig.Objectives->IsActorTickEnabled());
    TestEqual(TEXT("Left leaf fully open"), Rig.LeftOffset(), ACatrunStage3Objectives::FinalGateTravel, .01f);
    TestEqual(TEXT("Right leaf fully open"), Rig.RightOffset(), ACatrunStage3Objectives::FinalGateTravel, .01f);
    return true;
}
namespace Stage3FinalGateTest
{
    /** Final gate with a possessed cat, so the native reveal camera can take the screen. */
    struct FRevealRig
    {
        UWorld* World = nullptr;
        ACatrunStage3Objectives* Objectives = nullptr;
        AActor* Left = nullptr;
        AActor* Right = nullptr;
        ACharacter* Cat = nullptr;
        APlayerController* PC = nullptr;
        FVector Start = FVector(100.f, 50.f, 0.f);

        FRevealRig()
        {
            const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false);
            World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
            GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
            Left = SpawnLeaf(World, Start);
            Right = SpawnLeaf(World, Start);
            Cat = World->SpawnActor<ACharacter>();
            Cat->GetCapsuleComponent()->SetCapsuleSize(20, 26);
            Cat->SetActorLocation(Start + FVector(0, 320, 26));
            Cat->GetCharacterMovement()->SetMovementMode(MOVE_Walking);
            World->InitializeActorsForPlay(FURL());
            PC = World->SpawnActor<APlayerController>();
            PC->Possess(Cat); PC->SetViewTarget(Cat);
            Objectives = World->SpawnActorDeferred<ACatrunStage3Objectives>(ACatrunStage3Objectives::StaticClass(), FTransform::Identity);
            Objectives->FinalLeafLeft = Left;
            Objectives->FinalLeafRight = Right;
            Objectives->FinishSpawning(FTransform::Identity);
            if (!Objectives->HasActorBegunPlay()) Objectives->DispatchBeginPlay();
        }
        ~FRevealRig()
        {
            Objectives->FinalReveal->CancelReveal();
            GEngine->DestroyWorldContext(World);
            World->DestroyWorld(false);
        }
        float LeftOffset() const { return Start.X - Left->GetActorLocation().X; }
    };
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FStage3FinalGateRevealTest, "Catrun.Stage3.FinalGateWaitsForRevealCameraThenReturns", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FStage3FinalGateRevealTest::RunTest(const FString&)
{
    using T = ACatrunStage3Objectives;
    Stage3FinalGateTest::FRevealRig Rig;
    auto* R = Rig.Objectives->FinalReveal.Get();
    if (!TestNotNull(TEXT("Final gate owns a native reveal"), R)) return false;
    TestTrue(TEXT("Lock bound covers travel, opening, hold and return"),
        R->MaximumLockTime >= T::FinalRevealTravel + T::FinalGateDuration + T::FinalRevealHoldAfterOpen + T::FinalRevealReturn && R->MaximumLockTime <= 15.f);
    Rig.Objectives->BeginFinalGate();
    TestTrue(TEXT("Final gate waits for the camera"), Rig.Objectives->bFinalRevealPending);
    TestEqual(TEXT("Camera travels first"), R->Phase, ECatrunPuzzleRevealPhase::ToGate);
    TestTrue(TEXT("Reveal is tagged as the final gate"), R->PuzzleId == T::FinalRevealId());
    TestFalse(TEXT("Presenter edge has not risen yet"), Rig.Objectives->bFinalGateOpen);
    TestTrue(TEXT("Player movement is locked like D1/D2"), Rig.PC->IsMoveInputIgnored() && Rig.PC->IsLookInputIgnored());
    TestTrue(TEXT("Hostiles and exits are suspended"), UCatrunPuzzleSuspension::IsSuspended(Rig.Objectives));
    TestFalse(TEXT("Final gate pans without camera collision probes"), R->bProbeCameraCollision);
    const FVector CameraBefore = R->GetRevealCamera() ? R->GetRevealCamera()->GetActorLocation() : FVector::ZeroVector;
    for (int32 I = 0; I < 15; ++I) Rig.Objectives->Tick(.1f);
    TestEqual(TEXT("Leaves stay shut while the camera travels"), Rig.LeftOffset(), 0.f);
    TestFalse(TEXT("Still not open during travel"), Rig.Objectives->bFinalGateOpen);
    R->TickComponent(T::FinalRevealTravel + .01f, LEVELTICK_All, nullptr);
    TestEqual(TEXT("Camera arrived"), R->Phase, ECatrunPuzzleRevealPhase::Opening);
    if (R->GetRevealCamera())
        TestTrue(TEXT("Camera actually moved toward the gate"), FVector::Dist(R->GetRevealCamera()->GetActorLocation(), CameraBefore) > 10.f);
    constexpr float Dt = 1.f / 60.f;
    Rig.Objectives->Tick(Dt);
    TestTrue(TEXT("Opening starts on arrival"), Rig.Objectives->bFinalGateOpen && !Rig.Objectives->bFinalRevealPending);
    TestEqual(TEXT("Opening starts from the closed pose"), Rig.LeftOffset(), 0.f);
    for (int32 I = 0; I < 206; ++I) Rig.Objectives->Tick(Dt);
    TestTrue(TEXT("Not at the stops just before 3.45 s"), Rig.LeftOffset() < T::FinalGateTravel);
    Rig.Objectives->Tick(Dt);
    TestEqual(TEXT("The 3.45 s opening profile is unchanged"), Rig.LeftOffset(), T::FinalGateTravel, .01f);
    TestEqual(TEXT("Camera holds on the open gate"), R->Phase, ECatrunPuzzleRevealPhase::Opening);
    TestTrue(TEXT("Hold keeps ticking"), Rig.Objectives->IsActorTickEnabled());
    int32 HoldTicks = 0;
    while (Rig.Objectives->IsActorTickEnabled() && HoldTicks < 200) { Rig.Objectives->Tick(Dt); ++HoldTicks; }
    TestTrue(TEXT("Hold lasts about one second"), FMath::Abs(HoldTicks * Dt - T::FinalRevealHoldAfterOpen) <= 3.f * Dt);
    TestEqual(TEXT("Camera returns after the hold"), R->Phase, ECatrunPuzzleRevealPhase::Returning);
    TestTrue(TEXT("Input still locked during the return"), Rig.PC->IsMoveInputIgnored());
    R->TickComponent(T::FinalRevealReturn + .01f, LEVELTICK_All, nullptr);
    TestEqual(TEXT("Reveal finished"), R->Phase, ECatrunPuzzleRevealPhase::Inactive);
    TestFalse(TEXT("Controls return to the player"), Rig.PC->IsMoveInputIgnored() || Rig.PC->IsLookInputIgnored());
    TestFalse(TEXT("Suspension is released"), UCatrunPuzzleSuspension::IsSuspended(Rig.Objectives));
    TestTrue(TEXT("View is back on the cat"), Rig.PC->GetViewTarget() == Rig.Cat);
    TestTrue(TEXT("Gate stays open"), Rig.Objectives->bFinalGateOpen && FMath::IsNearlyEqual(Rig.LeftOffset(), T::FinalGateTravel, .01f));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FStage3FinalGateRevealFallbackTest, "Catrun.Stage3.FinalGateRevealFallbacks", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FStage3FinalGateRevealFallbackTest::RunTest(const FString&)
{
    using T = ACatrunStage3Objectives;
    {
        // Disabled presentation: open at once, never lock the player.
        Stage3FinalGateTest::FRevealRig Rig;
        Rig.Objectives->FinalReveal->bEnabled = false;
        Rig.Objectives->BeginFinalGate();
        TestTrue(TEXT("Disabled reveal opens immediately"), Rig.Objectives->bFinalGateOpen && !Rig.Objectives->bFinalRevealPending);
        TestFalse(TEXT("No input lock without a reveal"), Rig.PC->IsMoveInputIgnored());
        for (int32 I = 0; I < 40; ++I) Rig.Objectives->Tick(.1f);
        TestFalse(TEXT("No hold without a reveal"), Rig.Objectives->IsActorTickEnabled());
        TestEqual(TEXT("Fully open"), Rig.LeftOffset(), T::FinalGateTravel, .01f);
    }
    {
        // Reveal cancelled during travel (capture, stage end, external view): the gate still opens.
        Stage3FinalGateTest::FRevealRig Rig;
        Rig.Objectives->BeginFinalGate();
        TestTrue(TEXT("Pending before cancel"), Rig.Objectives->bFinalRevealPending);
        Rig.Objectives->FinalReveal->CancelReveal();
        Rig.Objectives->Tick(.1f);
        TestTrue(TEXT("Cancelled travel falls back to opening"), Rig.Objectives->bFinalGateOpen && !Rig.Objectives->bFinalRevealPending);
        TestFalse(TEXT("Cancel released input"), Rig.PC->IsMoveInputIgnored());
        for (int32 I = 0; I < 40; ++I) Rig.Objectives->Tick(.1f);
        TestFalse(TEXT("Finishes without waiting for a dead reveal"), Rig.Objectives->IsActorTickEnabled());
        Rig.Objectives->BeginFinalGate();
        TestEqual(TEXT("An open gate never starts a second reveal"), Rig.Objectives->FinalReveal->SessionId, 1);
    }
    return true;
}
#endif
