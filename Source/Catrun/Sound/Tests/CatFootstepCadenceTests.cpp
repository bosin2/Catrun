#if WITH_DEV_AUTOMATION_TESTS

#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include "Monster/Tests/CatrunCaptureCallbackProbe.h"
#include "Perception/CatrunCatStateComponent.h"
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
	ON_SCOPE_EXIT { World->DestroyWorld(false); };
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
	if (!TestNotNull(TEXT("Canonical cat spawns"), Cat) || !TestNotNull(TEXT("Sound listener spawns"), Listener) ||
		!TestNotNull(TEXT("Sound manager spawns"), Manager)) return false;

	auto* Settings = NewObject<UCatrunSoundSettings>(Manager);
	Settings->WalkStepInterval = 0.5f;
	Settings->RunStepInterval = 0.25f;
	const auto* SettingsProperty = FindFProperty<FObjectPropertyBase>(Manager->GetClass(), TEXT("Settings"));
	if (!TestNotNull(TEXT("Sound manager settings property"), SettingsProperty)) return false;
	SettingsProperty->SetObjectPropertyValue_InContainer(Manager, Settings);

	// Put both actors in the same cell so real deliveries have no propagation delay.
	auto& Grid = const_cast<FCatrunGridData&>(Manager->GetGrid());
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
	const FVector MovingVelocity(120.0, 0.0, 0.0);
	Movement->Velocity = MovingVelocity;
	const auto TickMode = [&](bool bRunning, bool bSneaking, float DeltaTime)
	{
		Running->SetPropertyValue_InContainer(Cat, bRunning);
		Sneaking->SetPropertyValue_InContainer(Cat, bSneaking);
		State->TickComponent(DeltaTime, LEVELTICK_All, nullptr);
	};

	constexpr float Frame = 0.0625f;
	TickMode(false, false, Frame);
	if (!TestEqual(TEXT("Starting to walk delivers one footstep immediately"), Listener->Received.Num(), 1)) return false;
	TestTrue(TEXT("The listener receives the cat's small walking footstep"),
		Listener->Received[0].Kind == ECatrunSoundKind::Footstep &&
		Listener->Received[0].Source == ECatrunSoundSource::Cat &&
		Listener->Received[0].Size == ECatrunSoundSize::Small);

	TickMode(true, false, Frame);
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

	Movement->Velocity = FVector::ZeroVector;
	TickMode(true, false, Frame);
	TestEqual(TEXT("The cat stays quiet while stopped"), Listener->Received.Num(), 2);
	Movement->Velocity = MovingVelocity;
	TickMode(true, false, Frame);
	TestEqual(TEXT("Moving after a genuine stop delivers an immediate footstep"), Listener->Received.Num(), 3);
	return true;
}

#endif
