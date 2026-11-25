#if WITH_DEV_AUTOMATION_TESTS
#include "LevelFlow/CatrunElevatorWeightComponent.h"
#include "Misc/AutomationTest.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunElevatorLoadResponseTest,
    "Catrun.LevelFlow.ElevatorWeightSettlesAndReboundsWithinSafeTravel",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunElevatorLoadResponseTest::RunTest(const FString&)
{
    CatrunElevatorWeight::FSpringState State;
    for (int32 Frame = 0; Frame < 240; ++Frame)
        CatrunElevatorWeight::AdvanceSpring(State, -4.f, 1.15f, .5f, 1.f / 60.f, -6.f, 1.25f);
    TestTrue(TEXT("A grounded reference rider settles four centimetres below the landing"),
        FMath::Abs(State.Offset + 4.f) < .01f && FMath::Abs(State.Velocity) < .01f);
    float Peak = State.Offset;
    for (int32 Frame = 0; Frame < 240; ++Frame)
    {
        CatrunElevatorWeight::AdvanceSpring(State, 0.f, 1.15f, .5f, 1.f / 60.f, -6.f, 1.25f);
        Peak = FMath::Max(Peak, State.Offset);
        TestTrue(TEXT("Unloading never exposes an unsafe step"), State.Offset >= -6.f && State.Offset <= 1.25f);
    }
    TestTrue(TEXT("Stepping out produces a small readable rise above neutral"), Peak > .15f && Peak <= 1.25f);
    TestTrue(TEXT("The empty cabin stops moving at the landing"), FMath::Abs(State.Offset) < .01f && FMath::Abs(State.Velocity) < .01f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunElevatorFrameRateResponseTest,
    "Catrun.LevelFlow.ElevatorWeightPauseAndFrameRateIndependence",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunElevatorFrameRateResponseTest::RunTest(const FString&)
{
    CatrunElevatorWeight::FSpringState At30, At120;
    for (int32 Frame = 0; Frame < 30; ++Frame)
        CatrunElevatorWeight::AdvanceSpring(At30, -4.f, 1.15f, .5f, 1.f / 30.f, -6.f, 1.25f);
    for (int32 Frame = 0; Frame < 120; ++Frame)
        CatrunElevatorWeight::AdvanceSpring(At120, -4.f, 1.15f, .5f, 1.f / 120.f, -6.f, 1.25f);
    TestTrue(TEXT("30 and 120 FPS produce the same displacement and velocity"),
        FMath::Abs(At30.Offset - At120.Offset) < .001f && FMath::Abs(At30.Velocity - At120.Velocity) < .001f);
    const auto BeforePause = At30;
    CatrunElevatorWeight::AdvanceSpring(At30, 0.f, 1.15f, .5f, 0.f, -6.f, 1.25f);
    TestEqual(TEXT("Paused offset is unchanged"), At30.Offset, BeforePause.Offset);
    TestEqual(TEXT("Paused velocity is unchanged"), At30.Velocity, BeforePause.Velocity);
    CatrunElevatorWeight::AdvanceSpring(At30, -100.f, 1.15f, .5f, 5.f, -6.f, 1.25f);
    TestTrue(TEXT("Large mass and long frame remain within authored cabin travel"),
        FMath::IsFinite(At30.Offset) && At30.Offset >= -6.f && At30.Offset <= 1.25f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunElevatorGroundedWeightTest,
    "Catrun.LevelFlow.ElevatorWeightRequiresActualFloorContact",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunElevatorGroundedWeightTest::RunTest(const FString&)
{
    const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(true)
        .CreateNavigation(false).CreateAISystem(false);
    UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
    GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
    World->InitializeActorsForPlay(FURL());
    auto* Floor = World->SpawnActor<AActor>();
    auto* FloorShape = NewObject<UBoxComponent>(Floor);
    Floor->SetRootComponent(FloorShape);
    FloorShape->SetMobility(EComponentMobility::Movable);
    FloorShape->SetBoxExtent(FVector(110., 100., 5.));
    FloorShape->SetCollisionProfileName(TEXT("BlockAllDynamic"));
    FloorShape->RegisterComponent();
    Floor->SetActorLocation(FVector(0., 0., -9.)); // Initial loaded surface: -4 cm.
    auto* Owner = World->SpawnActor<AActor>();
    auto* Weight = NewObject<UCatrunElevatorWeightComponent>(Owner);
    Owner->AddInstanceComponent(Weight); Weight->RegisterComponent();
    Weight->MovingActors.Add(Floor); Weight->SupportActors.Add(Floor);
    auto* Cat = World->SpawnActor<ACharacter>();
    Cat->GetCapsuleComponent()->SetCapsuleSize(18.f, 24.f);
    Cat->SetActorLocation(FVector(0., 0., 22.));
    Cat->GetCharacterMovement()->SetMovementMode(MOVE_Walking);
    Weight->StartResponse(-4.f);
    TestTrue(TEXT("Adopting an already-loaded cabin preserves its pose"),
        Floor->GetActorLocation().Equals(FVector(0., 0., -9.)) && Weight->GetCurrentOffset() == -4.f);
    TestTrue(TEXT("A grounded cat on the cabin floor contributes weight"), Weight->HasSupportedRider(Cat));
    Cat->GetCharacterMovement()->SetMovementMode(MOVE_Falling);
    TestFalse(TEXT("An airborne cat within the volume never weighs down the cabin"), Weight->HasSupportedRider(Cat));
    Cat->GetCharacterMovement()->SetMovementMode(MOVE_None);
    TestFalse(TEXT("An unrelated movement-disabled cat does not claim the cabin"), Weight->HasSupportedRider(Cat));
    Weight->SetScriptedRider(Cat);
    TestTrue(TEXT("The explicit cinematic rider still has verifiable foot contact"), Weight->HasSupportedRider(Cat));
    Cat->SetActorLocation(FVector(0., 0., 100.));
    TestFalse(TEXT("Scripted admission does not bypass floor contact"), Weight->HasSupportedRider(Cat));
    Cat->SetActorLocation(FVector(250., 0., 22.));
    TestFalse(TEXT("A cat on the landing outside the floor cannot load the lift"), Weight->HasSupportedRider(Cat));
    Weight->StopResponse(true);
    TestTrue(TEXT("Explicit neutral restore returns only the cabin to the landing"),
        Floor->GetActorLocation().Equals(FVector(0., 0., -5.)) && Cat->GetActorLocation().Equals(FVector(250., 0., 22.)));
    World->EndPlay(EEndPlayReason::Quit);
    GEngine->DestroyWorldContext(World); World->DestroyWorld(false);
    return true;
}
#endif
