#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Monster/CatrunArmor.h"
#include "Sound/CatrunSoundSettings.h"
#include "Sound/SoundGridManager.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "UObject/UnrealType.h"

namespace
{
// Same initialized-world and open-grid setup used by PrototypeAIRegressionTests.
// No editor assets, private armor state injection, or gameplay Tick are needed.
struct FArmorHearingWorld
{
	UWorld* World;
	ASoundGridManager* Manager;
	FArmorHearingWorld()
	{
		const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false)
			.CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false);
		World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true,
			ERHIFeatureLevel::Num, &Init);
		GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
		World->InitializeActorsForPlay(FURL());
		Manager = World->SpawnActor<ASoundGridManager>();
		auto* Settings = NewObject<UCatrunSoundSettings>(Manager);
		FindFProperty<FObjectPropertyBase>(ASoundGridManager::StaticClass(), TEXT("Settings"))
			->SetObjectPropertyValue_InContainer(Manager, Settings);
		auto& Grid = const_cast<FCatrunGridData&>(Manager->GetGrid());
		Grid.Origin = FVector(-2000, -2000, 0);
		Grid.CellSize = 25;
		Grid.Width = Grid.Height = 160;
		Grid.Walkable.Init(1, Grid.NumCells());
		Grid.EdgeMask.Init(255, Grid.NumCells());
		Grid.WallDistance.Init(1000.f, Grid.NumCells());
		Grid.CostMultiplier.Init(1.f, Grid.NumCells());
	}

	ACatrunArmor* Spawn(const FVector& Location)
	{
		FActorSpawnParameters Params;
		Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		auto* Armor = World->SpawnActor<ACatrunArmor>(Location, FRotator::ZeroRotator, Params);
		Armor->DispatchBeginPlay();
		return Armor;
	}

	~FArmorHearingWorld()
	{
		GEngine->DestroyWorldContext(World);
		World->DestroyWorld(false);
	}
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunArmorFootstepHearingTest,
	"Catrun.Monsters.ArmorFootstepOptInPreservesBellAndDevice",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCatrunArmorFootstepHearingTest::RunTest(const FString&)
{
	FArmorHearingWorld F;
	auto* DefaultArmor = F.Spawn(FVector(400, 400, 90));
	auto* LureArmor = F.Spawn(FVector(400, -400, 90));
	if (!TestNotNull(TEXT("Default armor exists"), DefaultArmor)
		|| !TestNotNull(TEXT("Lure armor exists"), LureArmor)) return false;
	TestFalse(TEXT("Existing armor behavior remains the default"), DefaultArmor->bIgnoreFootstepSounds);
	LureArmor->bIgnoreFootstepSounds = true;

	FCatrunSoundEvent Footstep;
	Footstep.Kind = ECatrunSoundKind::Footstep;
	Footstep.Size = ECatrunSoundSize::Large;
	Footstep.Location = FVector(800, 400, 90);
	ICatrunSoundListener::Execute_OnSoundHeard(DefaultArmor, Footstep, 100.f);
	TestTrue(TEXT("Default armor still starts a real path to a footstep snapshot"),
		DefaultArmor->HasDestination() && DefaultArmor->IsInvestigatingSound()
		&& DefaultArmor->GetInvestigationLocation().Equals(Footstep.Location));

	const EArmorAction BeforeAction = LureArmor->GetAction();
	const FVector BeforeDestination = LureArmor->GetInvestigationLocation();
	ICatrunSoundListener::Execute_OnSoundHeard(LureArmor, Footstep, 100.f);
	TestFalse(TEXT("Opted-in armor does not acquire a footstep investigation"), LureArmor->IsInvestigatingSound());
	TestFalse(TEXT("Opted-in armor does not acquire a footstep destination"), LureArmor->HasDestination());
	TestEqual(TEXT("Ignored footstep preserves the existing action"), LureArmor->GetAction(), BeforeAction);
	TestTrue(TEXT("Ignored footstep preserves the destination snapshot"),
		LureArmor->GetInvestigationLocation().Equals(BeforeDestination));

	FCatrunSoundEvent Bell;
	Bell.Kind = ECatrunSoundKind::Bell;
	Bell.Size = ECatrunSoundSize::Medium;
	Bell.Location = FVector(800, -400, 90);
	ICatrunSoundListener::Execute_OnSoundHeard(LureArmor, Bell, 100.f);
	TestTrue(TEXT("A bell still starts a real investigation on opted-in armor"),
		LureArmor->HasDestination() && LureArmor->IsInvestigatingSound()
		&& LureArmor->GetInvestigationLocation().Equals(Bell.Location));
	const EArmorAction BellAction = LureArmor->GetAction();
	const float BellSpeed = LureArmor->GetCharacterMovement()->MaxWalkSpeed;
	ICatrunSoundListener::Execute_OnSoundHeard(LureArmor, Footstep, 100.f);
	TestTrue(TEXT("Even a louder footstep cannot redirect the active bell lure"),
		LureArmor->GetInvestigationLocation().Equals(Bell.Location));
	TestEqual(TEXT("Ignored footstep cannot change the bell action"), LureArmor->GetAction(), BellAction);
	TestEqual(TEXT("Ignored footstep cannot change bell run speed"),
		LureArmor->GetCharacterMovement()->MaxWalkSpeed, BellSpeed);

	FCatrunSoundEvent Device;
	Device.Source = ECatrunSoundSource::Device;
	Device.Kind = ECatrunSoundKind::Device;
	Device.Size = ECatrunSoundSize::Large;
	Device.Location = FVector(650, -250, 90);
	Device.Instigator = F.Manager;
	ICatrunSoundListener::Execute_OnSoundHeard(LureArmor, Device, 100.f);
	TestTrue(TEXT("Louder device keeps its normal sound priority on opted-in armor"),
		LureArmor->HasDestination() && LureArmor->IsInvestigatingSound()
		&& LureArmor->GetInvestigationLocation().Equals(Device.Location));
	return true;
}
#endif
