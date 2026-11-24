#if WITH_DEV_AUTOMATION_TESTS

#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Engine/Engine.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include "Monster/Tests/CatrunCaptureCallbackProbe.h"
#include "Perception/CatrunCatStateComponent.h"
#include "Player/CatrunSprintComponent.h"
#include "Sound/CatrunSoundSettings.h"
#include "Sound/SoundGridManager.h"
#include "UObject/UnrealType.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunCatFootstepCadenceTest, "Catrun.Sound.FootstepsKeepCadenceAcrossMovementModes",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCatrunCatFootstepCadenceTest::RunTest(const FString&)
{
	const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false);
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
	if (!TestNotNull(TEXT("Test world"), World)) return false;
	GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
	ON_SCOPE_EXIT { GEngine->DestroyWorldContext(World); World->DestroyWorld(false); };
	World->InitializeActorsForPlay(FURL());

	auto* CatClass = LoadClass<ACharacter>(nullptr, TEXT("/Game/Characters/BlackCat/Blueprints/BP_Cat.BP_Cat_C"));
	if (!TestNotNull(TEXT("Canonical cat Blueprint loads"), CatClass)) return false;
	const auto* Running = FindFProperty<FBoolProperty>(CatClass, TEXT("IsRunning"));
	const auto* Sneaking = FindFProperty<FBoolProperty>(CatClass, TEXT("IsSneaking"));
	if (!TestNotNull(TEXT("Run flag"), Running) || !TestNotNull(TEXT("Sneak flag"), Sneaking)) return false;

	const FVector Source(12.5, 12.5, 120.0);
	FActorSpawnParameters SpawnParams;
	SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	auto* Cat = World->SpawnActor<ACharacter>(CatClass, Source, FRotator::ZeroRotator, SpawnParams);
	auto* Listener = World->SpawnActor<ACatrunSoundDeliveryProbe>(Source, FRotator::ZeroRotator, SpawnParams);
	auto* Manager = World->SpawnActor<ASoundGridManager>();
	auto* Controller = World->SpawnActor<APlayerController>();
	if (!TestNotNull(TEXT("Canonical cat spawns"), Cat) || !TestNotNull(TEXT("Sound listener spawns"), Listener) ||
		!TestNotNull(TEXT("Sound manager spawns"), Manager) || !TestNotNull(TEXT("Controller spawns"), Controller)) return false;
	Controller->SetPlayer(NewObject<ULocalPlayer>(GEngine));
	Controller->Possess(Cat);
	Controller->SetViewTarget(Cat);
	if (!TestTrue(TEXT("The fixture has a local controller"), Controller->IsLocalController())) return false;
	auto* Sprint = Cat->FindComponentByClass<UCatrunSprintComponent>();
	auto* UpdateSpeed = Cat->FindFunction(TEXT("UpdateMovementSpeed"));
	if (!TestNotNull(TEXT("The cat owns sprint stamina"), Sprint) || !TestNotNull(TEXT("The cat owns the authored speed selector"), UpdateSpeed)) return false;
	Sprint->BeginPlay();

	auto* Floor = World->SpawnActor<AActor>();
	auto* Shape = NewObject<UBoxComponent>(Floor);
	Floor->SetRootComponent(Shape);
	Shape->SetBoxExtent(FVector(1000., 1000., 10.));
	Shape->SetCollisionProfileName(TEXT("BlockAll"));
	Shape->RegisterComponent();
	Floor->SetActorLocation(FVector(0., 0., -10.));
	Cat->SetActorLocation(FVector(Source.X, Source.Y, Cat->GetCapsuleComponent()->GetScaledCapsuleHalfHeight() + 2.));

	auto* Settings = NewObject<UCatrunSoundSettings>(Manager);
	Settings->WalkStepInterval = 0.5f;
	Settings->RunStepInterval = 0.25f;
	const auto* SettingsProperty = FindFProperty<FObjectPropertyBase>(Manager->GetClass(), TEXT("Settings"));
	if (!TestNotNull(TEXT("Sound manager settings property"), SettingsProperty)) return false;
	SettingsProperty->SetObjectPropertyValue_InContainer(Manager, Settings);

	// Put both actors in the same cell so real deliveries have no propagation delay.
	auto& Grid = const_cast<FCatrunGridData&>(Manager->GetGrid());
	Grid.Origin = FVector(-1000., -1000., 0.);
	Grid.CellSize = 2000.f;
	Grid.Width = 1;
	Grid.Height = 1;
	Grid.Walkable = {1};
	Grid.EdgeMask = {0};
	Grid.CostMultiplier = {1.f};
	Grid.WallDistance = {1000.f};

	auto* State = NewObject<UCatrunCatStateComponent>(Cat);
	Cat->AddInstanceComponent(State);
	State->RegisterComponent();
	auto* Movement = Cat->GetCharacterMovement();
	Movement->SetMovementMode(MOVE_Walking);
	constexpr float Frame = 0.0625f;
	const auto Move = [&](float DeltaTime, bool bMoving)
	{
		if (bMoving) Cat->AddMovementInput(FVector::ForwardVector);
		Sprint->TickComponent(DeltaTime, LEVELTICK_All, nullptr);
		Movement->TickComponent(DeltaTime, LEVELTICK_All, nullptr);
	};
	const auto TickMode = [&](bool bRunning, bool bSneaking, float DeltaTime, bool bMoving = true)
	{
		Running->SetPropertyValue_InContainer(Cat, bRunning);
		Sneaking->SetPropertyValue_InContainer(Cat, bSneaking);
		Cat->ProcessEvent(UpdateSpeed, nullptr);
		while (DeltaTime > 0.f)
		{
			const float Step = FMath::Min(DeltaTime, Frame);
			Move(Step, bMoving);
			State->TickComponent(Step, LEVELTICK_All, nullptr);
			DeltaTime -= Step;
		}
	};

	TickMode(false, false, Frame);
	if (!TestEqual(TEXT("Starting to walk delivers one footstep immediately"), Listener->Received.Num(), 1)) return false;
	TestTrue(TEXT("The listener receives the cat's small walking footstep"),
		Listener->Received[0].Kind == ECatrunSoundKind::Footstep &&
		Listener->Received[0].Source == ECatrunSoundSource::Cat &&
		Listener->Received[0].Size == ECatrunSoundSize::Small);

	TickMode(true, false, Frame);
	if (!TestTrue(TEXT("The cadence transition follows an actual sprint movement update"), Sprint->IsSprinting())) return false;
	TickMode(true, true, 1.f);
	TickMode(false, false, Frame);
	TickMode(true, false, Frame);
	TickMode(false, true, 1.f);
	TickMode(true, false, Frame / 2.f);
	TestEqual(TEXT("Toggling run and sneak while moving adds no premature footsteps"), Listener->Received.Num(), 1);

	TickMode(true, false, Frame / 2.f);
	TickMode(true, false, Frame / 2.f);
	if (!TestEqual(TEXT("The next footstep arrives on the shorter running cadence"), Listener->Received.Num(), 2)) return false;
	TestTrue(TEXT("The listener receives a medium running footstep"),
		Listener->Received[1].Kind == ECatrunSoundKind::Footstep && Listener->Received[1].Size == ECatrunSoundSize::Medium);

	Movement->StopMovementImmediately();
	TickMode(true, false, Frame, false);
	TestEqual(TEXT("The cat stays quiet while stopped"), Listener->Received.Num(), 2);
	TickMode(true, false, Frame);
	TestEqual(TEXT("Moving after a genuine stop delivers an immediate footstep"), Listener->Received.Num(), 3);

	// Preserve the held input and exhaust actual movement before sampling the next departure.
	for (int32 Index = 0; Index < 88 && !Sprint->IsExhausted(); ++Index) Move(Frame, true);
	if (!TestTrue(TEXT("Actual sprint movement exhausts stamina"), Sprint->IsExhausted())) return false;
	Movement->StopMovementImmediately();
	TickMode(true, false, Frame, false);
	TickMode(true, false, Frame);
	if (!TestEqual(TEXT("Moving with run held at exhaustion still delivers a footstep"), Listener->Received.Num(), 4)) return false;
	TestEqual(TEXT("An exhausted cat makes a walking footstep with run held"), Listener->Received[3].Size, ECatrunSoundSize::Small);
	return true;
}

#endif
