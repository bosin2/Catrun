#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include "Monster/CatrunArmor.h"
#include "Sound/CatrunDoor.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimMontage.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"

// The placed armor (BP_LivingArmor) presents the door clip through its AnimationRequested graph as
// PlaySlotAnimationAsDynamicMontage(DefaultSlot, blend in 0, blend out 0). That montage runs one
// frame ahead of ActionTime and, at its end, drops straight back to the slot's source pose at the
// actor. The handoff used to read that pose ("moved the body 0 cm" in every interactive PIE log),
// so the body jumped back to the door and walked through the doorway a second time.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunArmorDoorHandoffTest, "Catrun.Monsters.ArmorDoorHandoffKeepsBodyAfterMontageEnds",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCatrunArmorDoorHandoffTest::RunTest(const FString&)
{
	UClass* ArmorClass = LoadClass<ACatrunArmor>(nullptr, TEXT("/Game/Characters/LivingArmor/Blueprints/BP_LivingArmor.BP_LivingArmor_C"));
	if (!TestNotNull(TEXT("Placed armor blueprint loads"), ArmorClass)) return false;

	// Case 0: an ordinary run to the end of the clip. Case 1: the montage disappears mid-way
	// (hitch, skipped update) and the handoff must use the last pose that was on screen.
	for (int32 Case = 0; Case < 2; ++Case)
	{
		const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false);
		UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
		GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
		ON_SCOPE_EXIT { GEngine->DestroyWorldContext(World); World->DestroyWorld(false); };
		World->InitializeActorsForPlay(FURL());

		FActorSpawnParameters Params;
		Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		auto* Armor = World->SpawnActor<ACatrunArmor>(ArmorClass, FVector(0, 0, 100), FRotator::ZeroRotator, Params);
		auto* Door = World->SpawnActor<ACatrunDoor>(FVector(3000, 3000, 0), FRotator::ZeroRotator, Params);
		if (!TestNotNull(TEXT("Armor spawns"), Armor) || !TestNotNull(TEXT("Door spawns"), Door)) return false;
		Armor->DispatchBeginPlay();
		Door->DispatchBeginPlay();

		USkeletalMeshComponent* Mesh = Armor->GetMesh();
		UAnimInstance* Instance = Mesh->GetAnimInstance();
		if (!TestTrue(TEXT("Fixture uses the real Blueprint presentation"), Armor->bUseBlueprintAnimation && Armor->DoorOpenAnim && Instance && !Mesh->GetSingleNodeInstance()))
			return false;

		// Start exactly like the game does: OpeningDoor, already facing the door, so this tick's
		// Facing step calls BeginDoorAnimation (and the Blueprint starts the montage).
		Armor->SetAction(EArmorAction::OpeningDoor);
		Armor->DoorBeingOpened = Door;
		Armor->bDoorTriggered = false;
		Armor->bDoorHandDriven = false;
		Armor->bDoorReleased = false;
		Armor->DoorStep = ACatrunArmor::EDoorStep::Facing;
		Armor->TurnTargetRotation = Armor->GetActorRotation();

		// A frame length that does not divide the clip: whether the old timer ran late must not
		// depend on float rounding.
		const float Length = Armor->AnimationLength(Armor->DoorOpenAnim);
		const float Dt = Length / (FMath::RoundToFloat(Length * 60.f) + .5f);
		const FVector ActorStart = Armor->GetActorLocation();
		FVector StartBody = FVector::ZeroVector, LastShownBody = FVector::ZeroVector;
		bool bSawMontage = false;
		int32 Frames = 0;
		const int32 MaxFrames = FMath::CeilToInt(Length / Dt) + 30;
		for (; Frames < MaxFrames && Armor->GetAction() == EArmorAction::OpeningDoor; ++Frames)
		{
			// Game order: the actor ticks first, then its mesh updates and evaluates the pose.
			Armor->Tick(Dt);
			if (Frames == 0) StartBody = Armor->DoorAnimStartBoneLocation;
			if (Armor->GetAction() != EArmorAction::OpeningDoor) break;
			if (Case == 1 && Frames == FMath::RoundToInt(Length * .5f / Dt))
			{
				Instance->Montage_Stop(0.f); // the montage is gone before the actor notices
			}
			Mesh->TickAnimation(Dt, false);
			Mesh->RefreshBoneTransforms();

			const UAnimMontage* Montage = nullptr;
			float Position = 0.f, Rate = 0.f;
			if (Armor->GetDoorMontagePlayback(Montage, Position, Rate))
			{
				bSawMontage = true;
				LastShownBody = Mesh->GetBoneLocation(Armor->DoorAnimTrackedBone, EBoneSpaces::WorldSpace);
			}
		}
		if (!TestTrue(TEXT("Blueprint graph plays the door clip as a dynamic montage"), bSawMontage)) return false;
		TestTrue(TEXT("Door step finishes"), Armor->GetAction() != EArmorAction::OpeningDoor);

		FVector Shown = LastShownBody - StartBody;
		Shown.Z = 0.;
		const double Moved = FVector::Dist2D(ActorStart, Armor->GetActorLocation());
		AddInfo(FString::Printf(TEXT("Case %d: clip %.3fs, handoff after %d frames of %.4fs, body shown %.1f cm, actor moved %.1f cm"),
			Case, Length, Frames, Dt, Shown.Size(), Moved));
		if (Case == 0)
		{
			TestTrue(TEXT("The authored clip really walks the body (fixture sanity)"), Shown.Size() > 30. && Shown.Size() < 400.);
			TestTrue(TEXT("Handoff waits for the end of the clip"), (Frames + 1) * Dt >= Length - KINDA_SMALL_NUMBER);
		}
		// Old code: the montage had already ended, so the live pose sat at the actor and it moved 0 cm.
		TestTrue(TEXT("Actor takes the walk of the last pose on screen"),
			FVector::Dist2D(Armor->GetActorLocation(), ActorStart + Shown) < 5.);
		TestTrue(TEXT("Mirror is restored after the handoff"), Mesh->GetRelativeScale3D().Equals(Armor->MeshBaseScale));
		TestFalse(TEXT("Handoff consumes the recorded pose"), Armor->bDoorAnimPoseRecorded || Armor->bDoorMontageSeen);
	}
	return true;
}

#endif
