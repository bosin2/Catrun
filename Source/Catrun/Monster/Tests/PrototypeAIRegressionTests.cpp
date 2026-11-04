#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "CoreGlobals.h"
#include "Animation/AnimationAsset.h"
#include "Materials/MaterialInterface.h"
#include "Monster/CatrunArmor.h"
#include "Monster/CatrunCandle.h"
#include "Monster/CatrunCapturePresentationComponent.h"
#include "Monster/Tests/CatrunCaptureCallbackProbe.h"
#include "Perception/CatrunSafeRestore.h"
#include "Monster/CatrunPerceptionPolicy.h"
#include "Monster/CatrunRestartSubsystem.h"
#include "Monster/CatrunMarkSubsystem.h"
#include "Interaction/CatrunBasketInteractionComponent.h"
#include "Interaction/CatrunHideBasket.h"
#include "Perception/CatrunCatStateComponent.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "Sound/SoundGridManager.h"
#include "Sound/CatrunSoundSettings.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "TimerManager.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "Camera/CameraActor.h"
#include "UObject/UnrealType.h"
#include "HAL/IConsoleManager.h"
#include "Interaction/CatrunPuzzleSuspension.h"

namespace
{
struct FPrototypeWorld
{
	UWorld* World;
	ACharacter* Cat;
	APlayerController* PC;
	UCatrunSoundSettings* Settings;
	ASoundGridManager* Manager;
	FPrototypeWorld()
	{
		const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false);
		World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
		GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
		World->InitializeActorsForPlay(FURL());
		Cat = Spawn<ACharacter>(FVector(0,0,90));
		Cat->GetCapsuleComponent()->SetCapsuleSize(20.f, 30.f);
		Cat->GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Pawn, ECR_Block);
		PC = World->SpawnActor<APlayerController>();
		PC->Possess(Cat);
		Manager = World->SpawnActor<ASoundGridManager>();
		Settings = NewObject<UCatrunSoundSettings>(Manager);
		Settings->VisionMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/EngineMaterials/DefaultMaterial.DefaultMaterial"));
		FindFProperty<FObjectPropertyBase>(ASoundGridManager::StaticClass(), TEXT("Settings"))->SetObjectPropertyValue_InContainer(Manager, Settings);
		auto& Grid = const_cast<FCatrunGridData&>(Manager->GetGrid());
		Grid.Origin = FVector(-2000,-2000,0); Grid.CellSize = 25; Grid.Width = Grid.Height = 160;
		Grid.Walkable.Init(1, Grid.NumCells()); Grid.EdgeMask.Init(255, Grid.NumCells());
		Grid.WallDistance.Init(1000.f, Grid.NumCells()); Grid.CostMultiplier.Init(1.f, Grid.NumCells());
	}
	template<class T> T* Spawn(const FVector& Location)
	{
		FActorSpawnParameters P; P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		return World->SpawnActor<T>(Location, FRotator::ZeroRotator, P);
	}
	AActor* Box(const FVector& Location, const FVector& Extent)
	{
		auto* Actor = World->SpawnActor<AActor>();
		auto* Shape = NewObject<UBoxComponent>(Actor); Actor->SetRootComponent(Shape);
		Shape->SetBoxExtent(Extent); Shape->SetCollisionProfileName(TEXT("BlockAll")); Shape->RegisterComponent();
		Actor->SetActorLocation(Location); return Actor;
	}
	~FPrototypeWorld()
	{
		GEngine->DestroyWorldContext(World); World->DestroyWorld(false);
	}
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunSoundPriorityTest, "Catrun.PrototypeAI.SoundSnapshotPriorityAndResume", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunSoundPriorityTest::RunTest(const FString&)
{
	FPrototypeWorld F;
	auto* Armor = F.Spawn<ACatrunArmor>(FVector(400,400,90));
	Armor->DispatchBeginPlay();
	Armor->SetFollowingMark(true);
	Armor->UpdateMarkFollowing(.1f);
	FCatrunSoundEvent Sound; Sound.Kind = ECatrunSoundKind::Bell; Sound.Size = ECatrunSoundSize::Medium; Sound.Location = FVector(800,400,90);
	Armor->OnSoundHeard_Implementation(Sound, 100.f);
	TestTrue(TEXT("Sound overrides an active mark"), Armor->IsInvestigatingSound());
	TestTrue(TEXT("Accepted location is the sound snapshot"), Armor->GetInvestigationLocation().Equals(Sound.Location));
	F.Cat->SetActorLocation(FVector(-500,-500,90));
	Armor->UpdateMarkFollowing(2.f);
	TestTrue(TEXT("Mark repath cannot replace the sound snapshot"), Armor->GetInvestigationLocation().Equals(Sound.Location));
	Sound.Size = ECatrunSoundSize::Small; Sound.Location = FVector(600,500,90);
	Armor->OnSoundHeard_Implementation(Sound, 100.f);
	TestFalse(TEXT("Quieter sound cannot interrupt travel"), Armor->GetInvestigationLocation().Equals(Sound.Location));
	Sound.Size = ECatrunSoundSize::Large;
	Armor->OnSoundHeard_Implementation(Sound, 100.f);
	TestTrue(TEXT("Louder sound can interrupt travel"), Armor->GetInvestigationLocation().Equals(Sound.Location));
	Armor->SetAction(EArmorAction::Looking); Sound.Size = ECatrunSoundSize::Small; Sound.Location = FVector(500,600,90);
	Armor->OnSoundHeard_Implementation(Sound, 100.f);
	TestTrue(TEXT("Looking accepts a small sound"), Armor->GetInvestigationLocation().Equals(Sound.Location));
	Armor->StartReturnToPost(); Armor->UpdateMarkFollowing(.1f);
	TestFalse(TEXT("Completed investigation releases sound priority"), Armor->IsInvestigatingSound());
	TestTrue(TEXT("Valid mark resumes at current cat position"), Armor->GetInvestigationLocation().Equals(F.Cat->GetActorLocation()));
	Armor->TurnRightAnim = LoadObject<UAnimationAsset>(nullptr, TEXT("/Game/Characters/LivingArmor/Final/Animations/AN_LivingArmor_TurnRight90.AN_LivingArmor_TurnRight90"));
	TestNotNull(TEXT("Authored turn animation loads"), Armor->TurnRightAnim.Get());
	Armor->SetActorRotation(FRotator::ZeroRotator); Armor->BeginTurn(90.f);
	TestTrue(TEXT("Fast turn duration honors editable playback rate"), FMath::IsNearlyEqual(Armor->ActionDuration, Armor->TurnRightAnim->GetPlayLength()/Armor->TurnPlayRate));
	Armor->ActionTime = Armor->ActionDuration*.5f; Armor->TickTurning(.01f);
	TestTrue(TEXT("Actor rotation does not double the authored body turn"), FMath::IsNearlyZero(Armor->GetActorRotation().Yaw));
	Armor->ActionTime = Armor->ActionDuration; Armor->TickTurning(.01f);
	TestTrue(TEXT("Quarter-turn actor commit happens once at animation end"), FMath::IsNearlyEqual(Armor->GetActorRotation().Yaw, 90.f));
	Armor->bSeeingCat = true; Sound.Location = FVector(100,100,90);
	Armor->OnSoundHeard_Implementation(Sound, 100.f);
	TestFalse(TEXT("Near detection dominates sound"), Armor->GetInvestigationLocation().Equals(Sound.Location));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunCandleOcclusionTest, "Catrun.PrototypeAI.CandleTouchRequiresActualLOS", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunCandleOcclusionTest::RunTest(const FString&)
{
	FPrototypeWorld F;
	F.Settings->CandleTouchRadius = 100.f;
	auto* Candle = F.Spawn<ACatrunCandle>(FVector(60,0,60)); Candle->bAutoAlignEyes = false;
	auto* Wall = F.Box(FVector(30,0,110), FVector(3,200,200));
	TestFalse(TEXT("Direct LOS is blocked by a real wall"), CatrunPerception::HasDirectSight(*Candle, *F.Cat, F.Settings->VisionTraceHeight));
	Candle->Tick(.016f);
	TestFalse(TEXT("Touch radius cannot mark across a wall"), F.World->GetSubsystem<UCatrunMarkSubsystem>()->IsMarked());
	Wall->Destroy(); Candle->Tick(.016f);
	TestTrue(TEXT("Removing wall allows touching candle to mark"), F.World->GetSubsystem<UCatrunMarkSubsystem>()->IsMarked());
	TestEqual(TEXT("Candle capsule blocks cat/armor Pawn"), Candle->BlockingCapsule->GetCollisionResponseToChannel(ECC_Pawn), ECR_Block);
	auto* Armor = F.Spawn<ACatrunArmor>(FVector(200,0,90));
	TestEqual(TEXT("Armor capsule blocks Pawn"), Armor->GetCapsuleComponent()->GetCollisionResponseToChannel(ECC_Pawn), ECR_Block);
	FHitResult Hit; FCollisionQueryParams Params; Params.AddIgnoredActor(F.Cat);
	TestTrue(TEXT("Cat capsule sweep is physically blocked by candle"), F.World->SweepSingleByChannel(Hit, FVector(0,0,90), FVector(120,0,90), FQuat::Identity, ECC_Pawn, FCollisionShape::MakeCapsule(20,30), Params));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunCaptureCancelTest, "Catrun.PrototypeAI.CaptureSessionAbortRestoresOwnedState", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunCaptureCancelTest::RunTest(const FString&)
{
	FPrototypeWorld F;
	auto* Armor = F.Spawn<ACatrunArmor>(FVector(100,0,90));
	auto* Other = F.Spawn<ACatrunArmor>(FVector(250,0,90));
	auto* Capture = Armor->CapturePresentation.Get();
	auto* OriginalView = F.Spawn<ACameraActor>(FVector(400,400,400)); F.PC->SetViewTarget(OriginalView);
	F.PC->SetIgnoreMoveInput(true); F.PC->SetIgnoreLookInput(true); // another owner's existing locks
	F.Cat->GetCharacterMovement()->SetMovementMode(MOVE_Flying);
	F.Cat->GetMesh()->SetAnimationMode(EAnimationMode::AnimationSingleNode);
	const FTransform Original = F.Cat->GetActorTransform();
	TestTrue(TEXT("First owner acquires capture"), Capture->BeginCapture(F.Cat, F.Settings));
	TestFalse(TEXT("Second armor cannot capture concurrently"), Other->CapturePresentation->BeginCapture(F.Cat, F.Settings));
	const int32 Id = Capture->SessionId;
	TestFalse(TEXT("Early grab rejected before pickup phase"), Capture->NotifyGrab(Id));
	Capture->TickComponent(F.Settings->CatchCameraBlendTime + .01f, LEVELTICK_All, nullptr);
	TestFalse(TEXT("Stale notify rejected"), Capture->NotifyGrab(Id-1));
	TestTrue(TEXT("Matching pickup notify accepted"), Capture->NotifyGrab(Id));
	TestFalse(TEXT("Duplicate grab is harmless"), Capture->NotifyGrab(Id));
	TestFalse(TEXT("Intentional carry disables cat collision"), F.Cat->GetActorEnableCollision());
	Capture->AbortCapture();
	TestTrue(TEXT("Abort restores original transform"), F.Cat->GetActorTransform().Equals(Original));
	TestTrue(TEXT("Abort restores collision"), F.Cat->GetActorEnableCollision());
	TestEqual(TEXT("Abort restores movement mode"), F.Cat->GetCharacterMovement()->MovementMode, TEnumAsByte<EMovementMode>(MOVE_Flying));
	TestEqual(TEXT("Abort restores single node mode"), F.Cat->GetMesh()->GetAnimationMode(), EAnimationMode::AnimationSingleNode);
	TestTrue(TEXT("Abort restores original view target"), F.PC->GetViewTarget() == OriginalView);
	TestTrue(TEXT("Other owner's input locks survive"), F.PC->IsMoveInputIgnored() && F.PC->IsLookInputIgnored());
	F.PC->SetIgnoreMoveInput(false); F.PC->SetIgnoreLookInput(false);
	TestFalse(TEXT("Capture left no extra move lock"), F.PC->IsMoveInputIgnored());
	TestFalse(TEXT("Capture left no extra look lock"), F.PC->IsLookInputIgnored());
	TestFalse(TEXT("Abort releases per-world acquisition"), F.World->GetSubsystem<UCatrunRestartSubsystem>()->IsCatching());
	TestFalse(TEXT("Notify after abort cannot restart"), Capture->NotifyFinished(Id));
	TestTrue(TEXT("Can capture again after abort"), Capture->BeginCapture(F.Cat, F.Settings));
	TestTrue(TEXT("Session changes on repeated capture"), Capture->SessionId != Id);
	F.World->GetSubsystem<UCatrunLevelFlowSubsystem>()->bStageComplete = true;
	Capture->TickComponent(.01f, LEVELTICK_All, nullptr);
	TestFalse(TEXT("Stage completion cancels capture"), Capture->IsCapturing());
	return true;
}

// Real component ticks: the old implementation jumped to the target on the first tick.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunCaptureGrabHeadingTest, "Catrun.PrototypeAI.CaptureGrabHeadingContinuity", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunCaptureGrabHeadingTest::RunTest(const FString&)
{
	FPrototypeWorld F;
	auto* Armor = F.Spawn<ACatrunArmor>(FVector(200,0,90));
	auto* Capture = Armor->CapturePresentation.Get();
	F.Cat->GetCharacterMovement()->SetMovementMode(MOVE_Flying);
	F.Settings->CatchCameraBlendTime = 0.f;
	F.Settings->CatchGrabBlendTime = .4f;
	F.Settings->CatchGrabLatestTime = 10.f;
	Capture->MissingAnimationDuration = 20.f;
	Capture->bUseBlueprintPresentation = true; // drive the authored notify explicitly
	auto Begin = [&](float StartYaw, float TargetYaw)
	{
		Armor->SetActorRotation(FRotator(0.f, TargetYaw, 0.f));
		F.Cat->SetActorRotation(FRotator(0.f, StartYaw + 15.f, 0.f));
		if (!Capture->BeginCapture(F.Cat, F.Settings)) return false;
		Capture->TickComponent(.01f, LEVELTICK_All, nullptr);
		// The grab pose can differ from acquisition; use the actual notify-time heading.
		F.Cat->SetActorRotation(FRotator(0.f, StartYaw, 0.f));
		return Capture->NotifyGrab(Capture->SessionId);
	};
	TestTrue(TEXT("Cross-facing pickup starts"), Begin(-90.f, 0.f));
	const int32 FirstSession = Capture->SessionId;
	Capture->TickComponent(.04f, LEVELTICK_All, nullptr);
	const float FirstYaw = F.Cat->GetActorRotation().Yaw;
	TestTrue(TEXT("First carry frame moves gently, without a quarter-turn snap"), FirstYaw > -90.f && FirstYaw < -85.f);
	Capture->TickComponent(.16f, LEVELTICK_All, nullptr);
	TestTrue(TEXT("Half of the lift is half of the heading change"), FMath::IsNearlyEqual(F.Cat->GetActorRotation().Yaw, -45.f, .01f));
	Capture->TickComponent(.2f, LEVELTICK_All, nullptr);
	TestTrue(TEXT("Lift endpoint exactly reaches the armor heading"), FMath::IsNearlyZero(F.Cat->GetActorRotation().Yaw, .01f));
	TestTrue(TEXT("Carry preserves upright pitch and roll"), FMath::IsNearlyZero(F.Cat->GetActorRotation().Pitch) && FMath::IsNearlyZero(F.Cat->GetActorRotation().Roll));
	Capture->AbortCapture();

	TestTrue(TEXT("New session starts at its own wrap-boundary heading"), Begin(179.f, -179.f));
	TestTrue(TEXT("Session provenance advanced"), Capture->SessionId > FirstSession);
	TestFalse(TEXT("Old grab cannot replace the new start heading"), Capture->NotifyGrab(FirstSession));
	Capture->TickComponent(.2f, LEVELTICK_All, nullptr);
	TestTrue(TEXT("179 to -179 follows the two-degree arc through 180"), FMath::Abs(FMath::FindDeltaAngleDegrees(179.f, F.Cat->GetActorRotation().Yaw) - 1.f) < .01f);
	Capture->TickComponent(.2f, LEVELTICK_All, nullptr);
	TestTrue(TEXT("Wrapped endpoint is the requested heading"), FMath::Abs(FMath::FindDeltaAngleDegrees(-179.f, F.Cat->GetActorRotation().Yaw)) < .01f);
	Capture->AbortCapture();

	F.Settings->CatchGrabBlendTime = 0.f;
	TestTrue(TEXT("Zero-duration pickup starts"), Begin(110.f, -35.f));
	Capture->TickComponent(.01f, LEVELTICK_All, nullptr);
	TestTrue(TEXT("Explicit zero duration still completes immediately"), FMath::IsNearlyEqual(F.Cat->GetActorRotation().Yaw, -35.f, .01f));
	Capture->AbortCapture();
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunBasketRestoreTest, "Catrun.PrototypeAI.BasketTransitLateBlockerAndRestore", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunBasketRestoreTest::RunTest(const FString&)
{
	FPrototypeWorld F;
	auto* Actions = NewObject<UCatrunBasketInteractionComponent>(F.Cat); Actions->RegisterComponent(); F.Cat->DispatchBeginPlay(); Actions->CatOwner = F.Cat;
	auto* Basket = F.Spawn<ACatrunHideBasket>(FVector::ZeroVector);
	Actions->ActiveBasket = Basket;
	const FVector Origin(0,0,90), Destination(150,0,90);
	TestTrue(TEXT("Empty path initially clear"), Actions->IsExitPathClear(Origin, Destination));
	auto* Blocker = F.Box(FVector(75,0,90), FVector(5,30,40));
	TestFalse(TEXT("Thin midpath obstacle blocks clear destination"), Actions->IsExitPathClear(Origin, Destination));
	Blocker->Destroy();
	auto* Armor = F.Spawn<ACatrunArmor>(FVector(75,0,90));
	TestFalse(TEXT("Real Pawn capsule blocks exit path"), Actions->IsExitPathClear(Origin, Destination));
	Armor->Destroy();
	F.Cat->GetMesh()->SetAnimationMode(EAnimationMode::AnimationSingleNode);
	F.Cat->GetCharacterMovement()->SetMovementMode(MOVE_Flying);
	Actions->EnterAnimation = nullptr; Actions->ExitAnimation = nullptr;
	Actions->EnterBasket(Basket, Origin); Actions->FinishEnter();
	Actions->BasketPhase = ECatrunBasketPhase::Exiting; Actions->Busy = true;
	F.Cat->SetActorLocation(Destination);
	Blocker = F.Box(Destination, FVector(25,25,40));
	Actions->FinishExit();
	TestEqual(TEXT("Late blocker returns cat to hidden state"), Actions->BasketPhase, ECatrunBasketPhase::Hidden);
	TestFalse(TEXT("Late blocker never restores overlapping collision"), F.Cat->GetActorEnableCollision());
	// A second late blocker occupies the saved entry while the component is removed.
	F.Box(FVector(0,0,48), FVector(1000,1000,10));
	F.Spawn<ACatrunArmor>(Actions->SavedEntryTransform.GetLocation());
	Actions->EndPlay(EEndPlayReason::Destroyed);
	TestFalse(TEXT("Blocked basket origin selects a different restoration position"), F.Cat->GetActorLocation().Equals(Actions->SavedEntryTransform.GetLocation()));
	TestTrue(TEXT("Basket EndPlay fallback has no capsule encroachment"), CatrunRestore::IsPlacementClear(*F.Cat, F.Cat->GetActorTransform()));
	TestTrue(TEXT("Component removal restores surviving cat collision"), F.Cat->GetActorEnableCollision());
	TestEqual(TEXT("Component removal restores movement"), F.Cat->GetCharacterMovement()->MovementMode, TEnumAsByte<EMovementMode>(MOVE_Flying));
	TestEqual(TEXT("Component removal restores animation mode even without class"), F.Cat->GetMesh()->GetAnimationMode(), EAnimationMode::AnimationSingleNode);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunCaptureCallbackAbortTest, "Catrun.PrototypeAI.CaptureCallbacksCanAbortOrReplaceSession", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunCaptureCallbackAbortTest::RunTest(const FString&)
{
	FPrototypeWorld F;
	auto* Armor = F.Spawn<ACatrunArmor>(FVector(100,0,90));
	auto* Capture = Armor->CapturePresentation.Get();
	for (auto Phase : {ECatrunCapturePhase::Framing, ECatrunCapturePhase::Pickup, ECatrunCapturePhase::Holding, ECatrunCapturePhase::Fading})
	{
		auto* Probe = NewObject<UCatrunCaptureCallbackProbe>();
		Probe->Capture = Capture; Probe->Cat = F.Cat; Probe->Settings = F.Settings; Probe->AbortAt = Phase;
		Capture->OnPhaseChanged.AddDynamic(Probe, &UCatrunCaptureCallbackProbe::PhaseChanged);
		const bool bStarted = Capture->BeginCapture(F.Cat, F.Settings);
		TestEqual(TEXT("Begin returns false if its callback aborted framing"), bStarted, Phase != ECatrunCapturePhase::Framing);
		if (bStarted) Capture->TickComponent(F.Settings->CatchCameraBlendTime+.01f, LEVELTICK_All, nullptr);
		if (Capture->IsCapturing()) TestFalse(TEXT("Nested grab/fading abort rejects old completion"), Capture->NotifyFinished(Capture->SessionId));
		TestEqual(TEXT("Real dynamic callback fired exactly once"), Probe->Calls, 1);
		TestFalse(TEXT("Phase callback never resurrects an aborted session"), Capture->IsCapturing());
		TestFalse(TEXT("Callback abort releases guard"), F.World->GetSubsystem<UCatrunRestartSubsystem>()->IsCatching());
		TestFalse(TEXT("Callback abort releases its move lock"), F.PC->IsMoveInputIgnored());
		Capture->OnPhaseChanged.RemoveDynamic(Probe, &UCatrunCaptureCallbackProbe::PhaseChanged);
	}
	for (auto Phase : {ECatrunCapturePhase::Holding, ECatrunCapturePhase::Fading})
	{
		auto* Probe = NewObject<UCatrunCaptureCallbackProbe>();
		Probe->Capture = Capture; Probe->Cat = F.Cat; Probe->Settings = F.Settings; Probe->AbortAt = Phase; Probe->bReplaceSession = true;
		Capture->OnPhaseChanged.AddDynamic(Probe, &UCatrunCaptureCallbackProbe::PhaseChanged);
		Capture->BeginCapture(F.Cat, F.Settings);
		const int32 OldSession = Capture->SessionId;
		Capture->TickComponent(F.Settings->CatchCameraBlendTime+.01f, LEVELTICK_All, nullptr);
		TestFalse(TEXT("Old finish cannot act on callback replacement session"), Capture->NotifyFinished(OldSession));
		TestTrue(TEXT("Replacement has a fresh session ID"), Capture->SessionId > OldSession);
		TestEqual(TEXT("Old call cannot advance replacement to fading"), Capture->Phase, ECatrunCapturePhase::Framing);
		TestTrue(TEXT("Replacement retains its own acquisition"), F.World->GetSubsystem<UCatrunRestartSubsystem>()->IsCatching());
		Capture->AbortCapture();
		Capture->OnPhaseChanged.RemoveDynamic(Probe, &UCatrunCaptureCallbackProbe::PhaseChanged);
	}
	// Exercise auto-notify from inside Tick, not only direct BP notify entry points.
	for (auto Phase : {ECatrunCapturePhase::Holding, ECatrunCapturePhase::Fading})
	{
		auto* Probe = NewObject<UCatrunCaptureCallbackProbe>();
		Probe->Capture = Capture; Probe->AbortAt = Phase;
		Capture->OnPhaseChanged.AddDynamic(Probe, &UCatrunCaptureCallbackProbe::PhaseChanged);
		Capture->MissingAnimationDuration = .1f;
		Capture->BeginCapture(F.Cat, F.Settings);
		Capture->TickComponent(F.Settings->CatchCameraBlendTime+.2f, LEVELTICK_All, nullptr);
		TestEqual(TEXT("Tick auto-notify executes callback"), Probe->Calls, 1);
		TestFalse(TEXT("Tick stops after callback invalidates capture"), Capture->IsCapturing());
		Capture->OnPhaseChanged.RemoveDynamic(Probe, &UCatrunCaptureCallbackProbe::PhaseChanged);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunCaptureInitialSetupTest, "Catrun.PrototypeAI.CaptureInitialSetupRejectsReentrantRestart", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunCaptureInitialSetupTest::RunTest(const FString&)
{
	FPrototypeWorld F;
	auto* Armor = F.Spawn<ACatrunArmor>(FVector(100,0,90));
	Armor->DispatchBeginPlay();
	Armor->SetAction(EArmorAction::Walking);
	Armor->bHasDestination = true;
	Armor->PathCorners.Add(FVector(400,0,90));
	Armor->GetCharacterMovement()->Velocity = FVector(100,0,0);
	auto* Capture = Armor->CapturePresentation.Get();
	auto* Probe = NewObject<UCatrunCaptureCallbackProbe>();
	Probe->Capture = Capture; Probe->Cat = F.Cat; Probe->Settings = F.Settings;
	Probe->AbortAt = ECatrunCapturePhase::Framing; Probe->bReplaceSession = true;
	Capture->OnPhaseChanged.AddDynamic(Probe, &UCatrunCaptureCallbackProbe::PhaseChanged);

	Armor->StartCatch(*F.Cat);
	TestEqual(TEXT("Actual armor start invokes initial Framing listener"), Probe->Calls, 1);
	TestFalse(TEXT("Initial setup rejects synchronous abort-and-retry"), Probe->bReplacementAccepted);
	TestFalse(TEXT("No active capture escapes the armor's action transition"), Capture->IsCapturing());
	TestEqual(TEXT("Aborted setup leaves prior Walking action intact"), Armor->GetAction(), EArmorAction::Walking);
	TestFalse(TEXT("Aborted setup releases restart acquisition"), F.World->GetSubsystem<UCatrunRestartSubsystem>()->IsCatching());
	TestFalse(TEXT("Aborted setup releases input lock"), F.PC->IsMoveInputIgnored());
	TestTrue(TEXT("Walking path remains available after canceled setup"), Armor->HasDestination() && Armor->PathCorners.Num() == 1);

	const int32 AbortedSession = Capture->SessionId;
	Armor->StartCatch(*F.Cat); // Listener is disarmed; outer setup has now fully returned.
	TestTrue(TEXT("Later retry starts a fresh capture"), Capture->IsCapturing() && Capture->SessionId > AbortedSession);
	TestEqual(TEXT("Successful retry enters owner Catching action"), Armor->GetAction(), EArmorAction::Catching);
	TestFalse(TEXT("Successful retry clears prior walking destination"), Armor->HasDestination());
	TestTrue(TEXT("Successful retry clears prior walking path"), Armor->PathCorners.IsEmpty());
	TestTrue(TEXT("Successful retry stops armor movement"), Armor->GetCharacterMovement()->Velocity.IsNearlyZero());
	Capture->OnPhaseChanged.RemoveDynamic(Probe, &UCatrunCaptureCallbackProbe::PhaseChanged);
	Capture->AbortCapture();
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunCaptureBlockedRestoreTest, "Catrun.PrototypeAI.CaptureAbortFindsClearPositionWhenOriginOccupied", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunCaptureBlockedRestoreTest::RunTest(const FString&)
{
	FPrototypeWorld F;
	auto* Armor = F.Spawn<ACatrunArmor>(FVector(100,0,90));
	auto* Capture = Armor->CapturePresentation.Get();
	F.Cat->GetCharacterMovement()->SetMovementMode(MOVE_Flying);
	const FVector Original = F.Cat->GetActorLocation();
	Capture->BeginCapture(F.Cat, F.Settings);
	Capture->TickComponent(F.Settings->CatchCameraBlendTime+.01f, LEVELTICK_All, nullptr);
	Capture->NotifyGrab(Capture->SessionId);
	F.Cat->SetActorLocation(FVector(100,0,160));
	F.Box(FVector(0,0,48), FVector(1000,1000,10));
	auto* Occupant = F.Spawn<ACatrunArmor>(Original);
	const FVector KnownCandidate(-88,0,90);
	TestTrue(TEXT("Fixture has a collision-clear supported candidate"), CatrunRestore::IsPlacementClear(*F.Cat, FTransform(FRotator::ZeroRotator, KnownCandidate)));
	FHitResult DiagnosticHit;
	FCollisionQueryParams DiagnosticParams(SCENE_QUERY_STAT(RestoreFixture), false, F.Cat); DiagnosticParams.AddIgnoredActor(Occupant);
	const bool bDiagnosticBlocked = F.World->SweepSingleByChannel(DiagnosticHit, Original, KnownCandidate, FQuat::Identity, ECC_Pawn, F.Cat->GetCapsuleComponent()->GetCollisionShape(), DiagnosticParams);
	TestFalse(TEXT("Fixture provides a clear swept route with normal 2cm floor clearance"), bDiagnosticBlocked);
	TestFalse(TEXT("Origin really became occupied while cat collision was off"), CatrunRestore::IsPlacementClear(*F.Cat, FTransform(FRotator::ZeroRotator, Original)));
	Capture->AbortCapture();
	TestFalse(TEXT("Capture abort does not teleport into occupied origin"), F.Cat->GetActorLocation().Equals(Original));
	TestTrue(TEXT("Capture fallback fits actual cat capsule"), CatrunRestore::IsPlacementClear(*F.Cat, F.Cat->GetActorTransform()));
	TestTrue(TEXT("Collision is restored only after clear placement"), F.Cat->GetActorEnableCollision());
	TestEqual(TEXT("Safe fallback restores original movement mode"), F.Cat->GetCharacterMovement()->MovementMode, TEnumAsByte<EMovementMode>(MOVE_Flying));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunRestoreRecoveryTest, "Catrun.PrototypeAI.ExhaustedRestoreQueuesSessionRestartAndHonorsTeardown", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunRestoreRecoveryTest::RunTest(const FString&)
{
	{
		FPrototypeWorld F;
		auto* Instance = NewObject<UGameInstance>();
		F.World->SetGameInstance(Instance); Instance->Init();
		auto* Session = Instance->GetSubsystem<UCatrunFlowSession>();
		if (!TestNotNull(TEXT("Recovery fixture has session-owned restart intent"), Session)) return false;
		F.Box(F.Cat->GetActorLocation(), FVector(3000,3000,3000));
		auto* Restart = F.World->GetSubsystem<UCatrunRestartSubsystem>();
		TestFalse(TEXT("Fully occupied bounded search cannot enable collision"), CatrunRestore::PlaceForCollision(*F.Cat, F.Cat->GetActorTransform(), true));
		TestTrue(TEXT("Exhaustion schedules playable recovery"), Restart->HasRecoveryRestartPending());
		TestFalse(TEXT("Recovery scheduling is idempotent"), Restart->ScheduleRecoveryRestart());
		TestFalse(TEXT("Cat remains non-colliding until recovery"), F.Cat->GetActorEnableCollision());
		// OpenLevel queues client travel; the live temporary world is recognized without loading a map.
		F.World->GetTimerManager().Tick(.01f);
		const FString Package = UWorld::RemovePIEPrefix(F.World->GetOutermost()->GetName());
		TestEqual(TEXT("Existing RestartLevel receives same-map recovery travel"), GEngine->GetWorldContextFromWorld(F.World)->TravelURL, Package);
		float Fade = 0.f;
		TestTrue(TEXT("Recovery uses Task1 token to skip tutorial intro"), Session->RestartIntent.Consume(Package, Fade));
		TestEqual(TEXT("Recovery retains requested fade"), Fade, .5f);
		Instance->Shutdown(); F.World->SetGameInstance(nullptr);
	}
	{
		FPrototypeWorld F;
		auto* Restart = F.World->GetSubsystem<UCatrunRestartSubsystem>();
		TestTrue(TEXT("Live world initially accepts recovery"), Restart->ScheduleRecoveryRestart());
		F.World->bIsTearingDown = true;
		F.World->GetTimerManager().Tick(.01f);
		TestTrue(TEXT("Teardown cancels queued recovery before travel"), GEngine->GetWorldContextFromWorld(F.World)->TravelURL.IsEmpty());
		TestFalse(TEXT("Teardown refuses a new recovery request"), Restart->ScheduleRecoveryRestart());
		F.World->bIsTearingDown = false;
		GEngine->GetWorldContextFromWorld(F.World)->TravelURL = TEXT("/Game/Maps/Stage1");
		TestFalse(TEXT("Existing pending travel cannot be replaced by recovery"), Restart->ScheduleRecoveryRestart());
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunRestoreReachabilityTest, "Catrun.PrototypeAI.RestoreRejectsUnsupportedAndThroughWallFallbacks", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunRestoreReachabilityTest::RunTest(const FString&)
{
	for (bool bFloorBeyondWall : {false, true})
	{
		FPrototypeWorld F;
		const FTransform Original = F.Cat->GetActorTransform();
		F.Spawn<ACatrunArmor>(Original.GetLocation());
		// A tiny original platform is now occupied. Empty air around it is not a playable fallback.
		F.Box(FVector(0,0,48), FVector(22,22,10));
		if (bFloorBeyondWall)
		{
			F.Box(FVector(140,0,48), FVector(50,80,10));
			F.Box(FVector(60,0,100), FVector(5,1000,1000));
			TestTrue(TEXT("Far side of wall has a collision-clear capsule destination"), CatrunRestore::IsPlacementClear(*F.Cat, FTransform(FRotator::ZeroRotator, FVector(140,0,92))));
		}
		TestFalse(bFloorBeyondWall ? TEXT("Cannot teleport through closed wall to supported destination") : TEXT("Cannot restore onto unsupported air"),
			CatrunRestore::PlaceForCollision(*F.Cat, Original, true));
		TestTrue(TEXT("Unsafe local returns schedule clean restart"), F.World->GetSubsystem<UCatrunRestartSubsystem>()->HasRecoveryRestartPending());
		TestTrue(TEXT("Failed search does not move the cat through geometry"), F.Cat->GetActorTransform().Equals(Original));
	}
	return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunBellCaptureTest,"Catrun.PrototypeAI.BellCaptureTransfersStableStateAndRejectsLateCallbacks",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FCatrunBellCaptureTest::RunTest(const FString&)
{
	FPrototypeWorld F;
	F.Box(FVector(0,0,48),FVector(2000,2000,10));
	F.Cat->GetCharacterMovement()->SetMovementMode(MOVE_Walking);
	auto* Actions=NewObject<UCatrunBasketInteractionComponent>(F.Cat); Actions->RegisterComponent(); Actions->CatOwner=F.Cat;
	auto* Armor=F.Spawn<ACatrunArmor>(FVector(300,0,90));
	auto* Capture=Armor->FindComponentByClass<UCatrunCapturePresentationComponent>();
	const auto StableMode=F.Cat->GetMesh()->GetAnimationMode();
	F.PC->SetIgnoreLookInput(true); // unrelated ownership must survive both actions
	int32 OtherTimerCount=0; FTimerHandle OtherTimer;
	F.World->GetTimerManager().SetTimer(OtherTimer,[&OtherTimerCount]{++OtherTimerCount;},.1f,false);
	TestTrue(TEXT("Ordinary bell acquires grounded player"),Actions->BeginBellAction());
	const int32 OldSession=Actions->BellSessionId;
	F.Cat->GetMesh()->SetAnimationMode(EAnimationMode::AnimationSingleNode); // BP's temporary clip mode
	TestTrue(TEXT("Bell owns Busy"),Actions->Busy);
	TestTrue(TEXT("Capture can interrupt ringing; no immunity"),Capture->BeginCapture(F.Cat,F.Settings));
	TestFalse(TEXT("Capture cancels bell before snapshot"),Actions->bBellActive);
	TestFalse(TEXT("Only bell Busy is released"),Actions->Busy);
	TestFalse(TEXT("Canceled emit timer is removed"),F.World->GetTimerManager().TimerExists(Actions->BellEmitTimer));
	TestFalse(TEXT("Canceled finish timer is removed"),F.World->GetTimerManager().TimerExists(Actions->BellFinishTimer));
	F.Cat->GetMesh()->SetAnimationMode(EAnimationMode::AnimationSingleNode);
	TestTrue(TEXT("Unrelated timer survives bell cancellation"),F.World->GetTimerManager().TimerExists(OtherTimer));
	F.World->GetTimerManager().Tick(0.f); // activate pending timers before advancing their deadlines
	++GFrameCounter; // TimerManager intentionally ignores a second Tick in the same engine frame
	F.World->GetTimerManager().Tick(3.f); // beyond both former BP timer deadlines
	Actions->EmitBellAction(OldSession); Actions->FinishBellAction(OldSession);
	TestEqual(TEXT("Unrelated timer still fires"),OtherTimerCount,1);
	TestEqual(TEXT("Late bell cannot re-enable capture-owned movement"),F.Cat->GetCharacterMovement()->MovementMode,TEnumAsByte<EMovementMode>(MOVE_None));
	TestEqual(TEXT("Late bell cannot replace capture presentation"),F.Cat->GetMesh()->GetAnimationMode(),EAnimationMode::AnimationSingleNode);
	TestFalse(TEXT("Late emission is not accepted"),Actions->bBellEmitted);
	Capture->AbortCapture();
	TestEqual(TEXT("Abort restores pre-bell movement"),F.Cat->GetCharacterMovement()->MovementMode,TEnumAsByte<EMovementMode>(MOVE_Walking));
	TestEqual(TEXT("Abort restores pre-bell animation"),F.Cat->GetMesh()->GetAnimationMode(),StableMode);
	TestTrue(TEXT("Abort restores collision"),F.Cat->GetActorEnableCollision());
	TestTrue(TEXT("Unrelated look lock remains"),F.PC->IsLookInputIgnored());
	TestFalse(TEXT("Capture move lock released"),F.PC->IsMoveInputIgnored());
	TestTrue(TEXT("Bell can run after abort"),Actions->BeginBellAction());
	const int32 NewSession=Actions->BellSessionId;
	Actions->EmitBellAction(OldSession); Actions->FinishBellAction(OldSession);
	TestTrue(TEXT("Old completion cannot cancel new bell"),Actions->bBellActive);
	TestFalse(TEXT("Old emission cannot emit new bell"),Actions->bBellEmitted);
	Actions->EmitBellAction(NewSession);
	TestTrue(TEXT("Current emission remains accepted"),Actions->bBellEmitted);
	TestTrue(TEXT("Capture after emission is also allowed"),Capture->BeginCapture(F.Cat,F.Settings));
	Actions->FinishBellAction(NewSession); Capture->AbortCapture();
	TestEqual(TEXT("Second interruption restores playable movement"),F.Cat->GetCharacterMovement()->MovementMode,TEnumAsByte<EMovementMode>(MOVE_Walking));
	auto* Guard=F.World->GetSubsystem<UCatrunPuzzleSuspension>(); Guard->Acquire(Armor);
	TestFalse(TEXT("Reveal suspension refuses new bell"),Actions->BeginBellAction()); Guard->Release(Armor);
	Actions->Busy=true; Actions->CancelBellAction();
	TestTrue(TEXT("No active bell cannot clear another action's Busy"),Actions->Busy); Actions->Busy=false;
	F.PC->SetIgnoreLookInput(false);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunArmorDebugTest,"Catrun.PrototypeAI.ArmorPathDiagnosticsRequireExplicitOptIn",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FCatrunArmorDebugTest::RunTest(const FString&)
{
	auto* Switch=IConsoleManager::Get().FindConsoleVariable(TEXT("catrun.DebugArmorPaths"));
	if (!TestNotNull(TEXT("Documented debug console switch exists"),Switch)) return false;
	TestEqual(TEXT("Normal process starts with diagnostics off"),Switch->GetInt(),0);
	FPrototypeWorld F; auto* Armor=F.Spawn<ACatrunArmor>(FVector(300,0,90));
	TestFalse(TEXT("Native actor default is off"),Armor->bDebugDrawPath);
	Armor->bDebugDrawPath=true;
	TestFalse(TEXT("Old serialized true cannot enable normal-play diagnostics"),Armor->IsPathDebugEnabled());
	Switch->Set(1,ECVF_SetByCode);
	TestTrue(TEXT("Deliberate opt-in enables selected actor"),Armor->IsPathDebugEnabled());
	Armor->bDebugDrawPath=false;
	TestFalse(TEXT("Per-actor disable is honored"),Armor->IsPathDebugEnabled());
	Switch->Set(0,ECVF_SetByCode);
	return true;
}
#endif
