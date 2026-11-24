#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "Camera/CameraActor.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Engine/Engine.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "Interaction/CatrunBasketInteractionComponent.h"
#include "Perception/CatrunCatStateComponent.h"
#include "Player/CatrunSprintComponent.h"
#include "Sound/CatrunBellComponent.h"
#include "Sound/CatrunNoBellZone.h"
#include "UObject/UnrealType.h"

namespace
{
struct FPlayerResourceWorld
{
	UWorld* World = nullptr;
	ACharacter* Cat = nullptr;
	APlayerController* Controller = nullptr;

	FPlayerResourceWorld()
	{
		const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false);
		World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
		if (!World) return;
		GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
		World->InitializeActorsForPlay(FURL());
		UClass* CatClass = LoadClass<ACharacter>(nullptr, TEXT("/Game/Characters/BlackCat/Blueprints/BP_Cat.BP_Cat_C"));
		if (!CatClass) return;
		Cat = World->SpawnActor<ACharacter>(CatClass, FVector(0., 0., 100.), FRotator::ZeroRotator);
		if (!Cat) return;
		Controller = World->SpawnActor<APlayerController>();
		Controller->SetPlayer(NewObject<ULocalPlayer>(GEngine));
		Possess(Cat);
	}

	void Possess(ACharacter* Pawn) const
	{
		Controller->Possess(Pawn);
		Controller->SetViewTarget(Pawn);
	}

	AActor* Box(const FVector& Location, const FVector& Extent) const
	{
		auto* Actor = World->SpawnActor<AActor>();
		auto* Shape = NewObject<UBoxComponent>(Actor);
		Actor->SetRootComponent(Shape);
		Shape->SetBoxExtent(Extent);
		Shape->SetCollisionProfileName(TEXT("BlockAll"));
		Shape->RegisterComponent();
		Actor->SetActorLocation(Location);
		return Actor;
	}

	~FPlayerResourceWorld()
	{
		if (!World) return;
		GEngine->DestroyWorldContext(World);
		World->DestroyWorld(false);
	}
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunSprintResourceTest, "Catrun.Player.Sprint.StaminaAndRecovery",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCatrunSprintResourceTest::RunTest(const FString&)
{
	auto* Sprint = NewObject<UCatrunSprintComponent>();
	Sprint->ResetStamina();
	TestEqual(TEXT("A fresh pawn begins with full stamina"), Sprint->GetStaminaNormalized(), 1.f);
	for (int32 Index = 0; Index < 19; ++Index) Sprint->AdvanceStamina(.25, true);
	TestEqual(TEXT("After 4.75 seconds of sprinting"), Sprint->GetStamina(), 5.f);
	TestFalse(TEXT("A cat above zero can still sprint"), Sprint->IsExhausted());
	Sprint->AdvanceStamina(.25, true);
	TestEqual(TEXT("Five seconds of sprinting empties the pool"), Sprint->GetStamina(), 0.f);
	TestTrue(TEXT("An empty pool prevents sprinting"), Sprint->IsExhausted());
	Sprint->AdvanceStamina(.75, false);
	TestEqual(TEXT("No recovery during cooldown"), Sprint->GetStamina(), 0.f);
	Sprint->AdvanceStamina(.5, false);
	TestEqual(TEXT("Only the quarter second after the delay recovers stamina"), Sprint->GetStamina(), 6.25f);
	Sprint->AdvanceStamina(.5, false);
	TestTrue(TEXT("18.75 stamina cannot rearm sprint"), Sprint->IsExhausted());
	Sprint->AdvanceStamina(.05, false);
	TestEqual(TEXT("20 stamina is the rearm threshold"), Sprint->GetStamina(), 20.f);
	TestFalse(TEXT("Sprint rearms at the threshold"), Sprint->IsExhausted());
	Sprint->AdvanceStamina(3.2, false);
	TestEqual(TEXT("Four recovery seconds refill the pool"), Sprint->GetStamina(), 100.f);
	Sprint->AdvanceStamina(2., true);
	Sprint->ResetStamina();
	TestEqual(TEXT("A gameplay reset refills the pool"), Sprint->GetStamina(), 100.f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunSprintTravelTest, "Catrun.Player.Sprint.VoluntaryHorizontalTravel",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCatrunSprintTravelTest::RunTest(const FString&)
{
	const auto IsVoluntary = UCatrunSprintComponent::IsVoluntaryHorizontalTravel;
	const FVector Input = FVector::ForwardVector;
	const FVector Travel(2., 0., 1.);
	TestTrue(TEXT("Ground displacement along consumed input spends stamina"), IsVoluntary(Input, Travel, true, false));
	TestFalse(TEXT("Holding run with no movement input spends none"), IsVoluntary(FVector::ZeroVector, Travel, true, false));
	TestFalse(TEXT("Holding run against a wall spends none"), IsVoluntary(Input, FVector::ZeroVector, true, false));
	TestFalse(TEXT("An unrelated sideways displacement spends none"), IsVoluntary(Input, FVector(0., 2., 0.), true, false));
	TestFalse(TEXT("Vertical displacement spends none"), IsVoluntary(Input, FVector(0., 0., 2.), true, false));
	TestFalse(TEXT("Airborne movement spends none"), IsVoluntary(Input, Travel, false, false));
	TestFalse(TEXT("Root motion or forced travel spends none even along input"), IsVoluntary(Input, Travel, true, true));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunSprintMovementCapTest, "Catrun.Player.Sprint.CharacterMovementDrivesStaminaAndSpeedCap",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCatrunSprintMovementCapTest::RunTest(const FString&)
{
	FPlayerResourceWorld Fixture;
	auto* Cat = Fixture.Cat;
	if (!TestNotNull(TEXT("Canonical player pawn"), Cat)) return false;
	auto* Sprint = Cat->FindComponentByClass<UCatrunSprintComponent>();
	auto* Movement = Cat->GetCharacterMovement();
	auto* SpeedUpdate = Cat->FindFunction(TEXT("UpdateMovementSpeed"));
	const auto* Run = FindFProperty<FBoolProperty>(Cat->GetClass(), TEXT("IsRunning"));
	if (!TestNotNull(TEXT("Authored sprint component"), Sprint) || !TestNotNull(TEXT("Existing cap owner"), SpeedUpdate)
		|| !TestNotNull(TEXT("Existing run input field"), Run)) return false;
	if (!TestTrue(TEXT("Fixture controller is local"), Fixture.Controller->IsLocalController())) return false;
	Sprint->BeginPlay();

	Fixture.Box(FVector(0., 0., -10.), FVector(3000., 3000., 10.));
	Cat->SetActorLocation(FVector(0., 0., Cat->GetCapsuleComponent()->GetScaledCapsuleHalfHeight() + 2.));
	Movement->SetMovementMode(MOVE_Walking);
	Run->SetPropertyValue_InContainer(Cat, true);
	Cat->ProcessEvent(SpeedUpdate, nullptr);
	TestEqual(TEXT("Run uses the authored 134 cm/s cap"), Movement->MaxWalkSpeed, 134.f);

	const auto Step = [&](bool bMove)
	{
		if (bMove) Cat->AddMovementInput(FVector::ForwardVector);
		Sprint->TickComponent(.05f, LEVELTICK_All, nullptr);
		Movement->TickComponent(.05f, LEVELTICK_All, nullptr);
	};
	for (int32 Index = 0; Index < 8; ++Index) Step(false);
	TestEqual(TEXT("Run held at rest spends no stamina"), Sprint->GetStamina(), 100.f);

	// Allow the capsule to settle against the wall before comparing repeated blocked moves.
	auto* Wall = Fixture.Box(Cat->GetActorLocation() + FVector(Cat->GetCapsuleComponent()->GetScaledCapsuleRadius() + 11., 0., 0.),
		FVector(10., 100., 100.));
	for (int32 Index = 0; Index < 4; ++Index) Step(true);
	const double BlockedX = Cat->GetActorLocation().X;
	const float BlockedStamina = Sprint->GetStamina();
	for (int32 Index = 0; Index < 6; ++Index) Step(true);
	TestTrue(TEXT("The real wall holds the capsule in place"), FMath::IsNearlyEqual(Cat->GetActorLocation().X, BlockedX, .01));
	TestEqual(TEXT("Continuous movement input into the wall spends no stamina"), Sprint->GetStamina(), BlockedStamina);
	Wall->Destroy();
	for (int32 Index = 0; Index < 25; ++Index) Step(false);

	Movement->StopMovementImmediately();
	const double BeforeImpulseX = Cat->GetActorLocation().X;
	const float BeforeImpulseStamina = Sprint->GetStamina();
	Movement->AddImpulse(FVector(12., 0., 0.), true);
	Step(true);
	TestTrue(TEXT("The capsule moved in the impulse frame"), Cat->GetActorLocation().X > BeforeImpulseX);
	TestEqual(TEXT("A queued impulse excludes its movement frame even with input"), Sprint->GetStamina(), BeforeImpulseStamina);

	Fixture.Controller->SetCinematicMode(true, false, false, false, false);
	const double BeforeCinematicX = Cat->GetActorLocation().X;
	const float BeforeCinematicStamina = Sprint->GetStamina();
	for (int32 Index = 0; Index < 5; ++Index) Step(true);
	TestTrue(TEXT("The cinematic flag leaves this fixture physically moving"), Cat->GetActorLocation().X > BeforeCinematicX + 1.);
	TestEqual(TEXT("Cinematic displacement spends no stamina"), Sprint->GetStamina(), BeforeCinematicStamina);
	Fixture.Controller->SetCinematicMode(false, false, false, false, false);

	for (int32 Index = 0; Index < 110 && !Sprint->IsExhausted(); ++Index) Step(true);
	TestTrue(TEXT("Real horizontal movement exhausts the sprint"), Sprint->IsExhausted());
	TestTrue(TEXT("The capsule moved substantially in the fixture"), Cat->GetActorLocation().X > 500.);
	TestEqual(TEXT("Depletion uses the existing Blueprint writer to select walk"), Movement->MaxWalkSpeed, 79.f);
	TestEqual(TEXT("Held run preserves the statue's pre-stamina cap"), UCatrunCatStateComponent::GetStatuePushSpeedLimit(*Cat), 119.f);

	auto* Replacement = Fixture.World->SpawnActor<ACharacter>(Cat->GetClass(), FVector(-400., 0., 100.), FRotator::ZeroRotator);
	if (!TestNotNull(TEXT("Replacement canonical pawn"), Replacement)) return false;
	auto* ReplacementSprint = Replacement->FindComponentByClass<UCatrunSprintComponent>();
	if (!TestNotNull(TEXT("Replacement has its authored sprint component"), ReplacementSprint)) return false;
	Fixture.Possess(Replacement);
	ReplacementSprint->BeginPlay();
	TestEqual(TEXT("A newly possessed pawn begins full after the old pawn depleted"), ReplacementSprint->GetStamina(), 100.f);
	TestFalse(TEXT("Exhaustion does not carry to a replacement pawn"), ReplacementSprint->IsExhausted());
	TestTrue(TEXT("Replacement left the old pawn's pool at zero"), Sprint->IsExhausted());
	Fixture.Possess(Cat);

	for (int32 Index = 0; Index < 20; ++Index) Step(false);
	TestTrue(TEXT("Wait one second before starting to rearm"), Sprint->IsExhausted());
	for (int32 Index = 0; Index < 17; ++Index) Step(false);
	TestFalse(TEXT("Recovering past 20 rearms run without a second press"), Sprint->IsExhausted());
	TestEqual(TEXT("Rearm restores 134 through the same writer"), Movement->MaxWalkSpeed, 134.f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunBlueprintBellStatusTest, "Catrun.Player.Bell.AcceptedBlueprintClockAndDenials",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCatrunBlueprintBellStatusTest::RunTest(const FString&)
{
	FPlayerResourceWorld Fixture;
	UWorld* World = Fixture.World;
	auto* Cat = Fixture.Cat;
	if (!TestNotNull(TEXT("Canonical cat pawn"), Cat)) return false;
	auto* Controller = Fixture.Controller;
	auto* Actions = Cat->FindComponentByClass<UCatrunBasketInteractionComponent>();
	auto* Bell = Cat->FindComponentByClass<UCatrunBellComponent>();
	if (!TestNotNull(TEXT("Canonical cat actions"), Actions) || !TestNotNull(TEXT("Authored bell component"), Bell)) return false;
	Actions->CatOwner = Cat;
	Bell->BeginPlay();
	const auto* Last = FindFProperty<FNumericProperty>(Actions->GetClass(), TEXT("LastBellTime"));
	const auto* Cooldown = FindFProperty<FNumericProperty>(Actions->GetClass(), TEXT("BellCooldownSeconds"));
	auto* TryBell = Actions->FindFunction(TEXT("TryBell"));
	if (!TestNotNull(TEXT("Blueprint accepted timestamp"), Last) || !TestNotNull(TEXT("Blueprint cooldown input"), Cooldown)
		|| !TestNotNull(TEXT("Blueprint bell action"), TryBell)) return false;
	const auto ReadLast = [&] { return Last->GetFloatingPointPropertyValue(Last->ContainerPtrToValuePtr<void>(Actions)); };
	auto* Move = Cat->GetCharacterMovement();
	Move->SetMovementMode(MOVE_Walking);
	TestTrue(TEXT("Fresh bell is ready"), Bell->GetBellStatus().bCanRing);
	TestEqual(TEXT("Shipping duration is five seconds"), Bell->GetCooldownDuration(), 5.f);
	Actions->ProcessEvent(TryBell, nullptr);
	if (!TestTrue(TEXT("The playable graph accepted the action"), Actions->bBellActive)) return false;
	TestEqual(TEXT("The graph stamped world time immediately on acceptance"), ReadLast(), World->GetTimeSeconds());
	TestEqual(TEXT("HUD sees all five seconds before emission"), Bell->GetBellStatus().RemainingSeconds, 5.f);
	TestEqual(TEXT("Active bell action reports busy"), Bell->GetBellStatus().Reason, ECatrunBellBlockReason::Busy);
	Actions->CancelBellAction();
	TestEqual(TEXT("Cooldown survives bell action recovery"), Bell->GetBellStatus().Reason, ECatrunBellBlockReason::Cooldown);
	const double AcceptedAt = ReadLast();
	Actions->ProcessEvent(TryBell, nullptr);
	TestFalse(TEXT("The playable graph also blocks during the displayed cooldown"), Actions->bBellActive);
	TestEqual(TEXT("Denied requests cannot update the accepted timestamp"), ReadLast(), AcceptedAt);
	Last->SetFloatingPointPropertyValue(Last->ContainerPtrToValuePtr<void>(Actions), World->GetTimeSeconds() - 4.999);
	TestEqual(TEXT("Just before the boundary stays locked"), Bell->GetBellStatus().Reason, ECatrunBellBlockReason::Cooldown);
	Last->SetFloatingPointPropertyValue(Last->ContainerPtrToValuePtr<void>(Actions), World->GetTimeSeconds() - 5.);
	TestTrue(TEXT("The exact cooldown boundary rings again"), Bell->GetBellStatus().bCanRing);
	Actions->ProcessEvent(TryBell, nullptr);
	TestTrue(TEXT("The playable graph also accepts at the exact boundary"), Actions->bBellActive);
	Actions->CancelBellAction();
	Cooldown->SetFloatingPointPropertyValue(Cooldown->ContainerPtrToValuePtr<void>(Actions), 7.);
	Last->SetFloatingPointPropertyValue(Last->ContainerPtrToValuePtr<void>(Actions), World->GetTimeSeconds() - 6.);
	TestEqual(TEXT("An edited Blueprint duration is the displayed duration"), Bell->GetBellStatus().CooldownSeconds, 7.f);
	TestEqual(TEXT("The same edited duration has one second remaining"), Bell->GetBellStatus().RemainingSeconds, 1.f);
	Actions->ProcessEvent(TryBell, nullptr);
	TestFalse(TEXT("The real graph shares the edited duration"), Actions->bBellActive);
	Last->SetFloatingPointPropertyValue(Last->ContainerPtrToValuePtr<void>(Actions), World->GetTimeSeconds() - 7.);
	const auto ExpectDenied = [&](const TCHAR* Description, ECatrunBellBlockReason Reason)
	{
		const double Before = ReadLast();
		const auto Status = Bell->GetBellStatus();
		TestEqual(Description, Status.Reason, Reason);
		TestFalse(TEXT("Status reports the current action unavailable"), Status.bCanRing);
		Actions->ProcessEvent(TryBell, nullptr);
		TestFalse(TEXT("The canonical action rejects the same request"), Actions->bBellActive);
		TestEqual(TEXT("The rejected action preserves the accepted timestamp"), ReadLast(), Before);
	};

	Actions->IsHidden = true;
	ExpectDenied(TEXT("Hidden denial"), ECatrunBellBlockReason::Hidden);
	Actions->IsHidden = false;
	Actions->Busy = true;
	ExpectDenied(TEXT("Independent busy denial"), ECatrunBellBlockReason::Busy);
	Actions->Busy = false;
	Move->SetMovementMode(MOVE_Falling);
	ExpectDenied(TEXT("Independent airborne denial"), ECatrunBellBlockReason::Airborne);
	Move->SetMovementMode(MOVE_Walking);
	auto* Zone = World->SpawnActor<ACatrunNoBellZone>(Cat->GetActorLocation(), FRotator::ZeroRotator);
	if (!TestNotNull(TEXT("Cat-hole area"), Zone)) return false;
	Bell->TickComponent(0.f, LEVELTICK_All, nullptr);
	ExpectDenied(TEXT("Independent cat-hole denial after the input router updates"), ECatrunBellBlockReason::CatHole);
	Zone->SetActorLocation(FVector(2000., 2000., 2000.));
	Bell->TickComponent(0.f, LEVELTICK_All, nullptr);
	Controller->SetCinematicMode(true, false, false, false, false);
	ExpectDenied(TEXT("Independent cinematic denial"), ECatrunBellBlockReason::Cinematic);
	Controller->SetCinematicMode(false, false, false, false, false);
	Controller->SetViewTarget(World->SpawnActor<ACameraActor>());
	TestTrue(TEXT("View target change without a gameplay lock leaves the bell ready"), Bell->GetBellStatus().bCanRing);
	Actions->ProcessEvent(TryBell, nullptr);
	TestTrue(TEXT("The canonical action accepts again after the cinematic unlocks"), Actions->bBellActive);
	TestEqual(TEXT("The accepted action updates the timestamp after unlocking"), ReadLast(), World->GetTimeSeconds());
	Actions->CancelBellAction();
	return true;
}

#endif
