#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "CoreGlobals.h"
#include "Animation/AnimationAsset.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimMontage.h"
#include "Engine/SkeletalMesh.h"
#include "Monster/CatrunPatrolPoint.h"
#include "Sound/CatrunDoor.h"
#include "Perception/AlertMarkComponent.h"
#include "Perception/VisionFanComponent.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Math/Float16Color.h"
#include "Monster/CatrunArmor.h"
#include "Monster/CatrunCandle.h"
#include "Monster/CatrunCapturePresentationComponent.h"
#include "Monster/Tests/CatrunCaptureCallbackProbe.h"
#include "Perception/CatrunSafeRestore.h"
#include "Perception/CatrunGroundSupport.h"
#include "Monster/CatrunPerceptionPolicy.h"
#include "Monster/CatrunRestartSubsystem.h"
#include "Monster/CatrunMarkSubsystem.h"
#include "Interaction/CatrunBasketInteractionComponent.h"
#include "Interaction/CatrunHideBasket.h"
#include "Interaction/CatrunStatuePuzzle.h"
#include "Perception/CatrunCatStateComponent.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "Sound/SoundGridManager.h"
#include "Sound/CatrunSoundSettings.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/Texture2D.h"
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
	Armor->GetMesh()->SetSkeletalMeshAsset(LoadObject<USkeletalMesh>(nullptr,
		TEXT("/Game/Characters/LivingArmor/Final/Meshes/SK_LivingArmor_Final.SK_LivingArmor_Final")));
	Armor->ArrivalLookAnim = LoadObject<UAnimSequence>(nullptr,
		TEXT("/Game/Characters/LivingArmor/Final/Animations/AN_LivingArmor_SoundReact.AN_LivingArmor_SoundReact"));
	if (!TestNotNull(TEXT("Arrival search clip loads"), Armor->ArrivalLookAnim.Get())) return false;
	Armor->ArrivalLookPlayRate = .8f;
	Armor->FinishTrip();
	const auto* SearchClip = CastChecked<UAnimSequence>(Armor->ArrivalLookAnim.Get());
	const float SearchDuration = SearchClip->GetPlayLength() / (.8f * FMath::Abs(SearchClip->RateScale));
	TestEqual(TEXT("Sound arrival enters Looking"), Armor->GetAction(), EArmorAction::Looking);
	TestTrue(TEXT("Search duration matches the slowed clip"), FMath::IsNearlyEqual(Armor->ActionDuration, SearchDuration));
	const auto* SearchPlayer = Armor->GetMesh()->GetSingleNodeInstance();
	if (TestNotNull(TEXT("Search runs through the animation player"), SearchPlayer))
	{
		TestEqual(TEXT("Search player uses the same local rate"), SearchPlayer->GetPlayRate(), .8f);
		TestFalse(TEXT("Search plays one cycle"), SearchPlayer->IsLooping());
	}
	Armor->ActionTime = SearchDuration - .01f;
	Armor->TickLooking(.01f);
	TestEqual(TEXT("Search remains active just before clip completion"), Armor->GetAction(), EArmorAction::Looking);
	Sound.Size = ECatrunSoundSize::Small; Sound.Location = FVector(500,600,90);
	Armor->OnSoundHeard_Implementation(Sound, 100.f);
	TestTrue(TEXT("Looking accepts a small sound"), Armor->GetInvestigationLocation().Equals(Sound.Location));
	TestNotEqual(TEXT("A new sound immediately ends the search"), Armor->GetAction(), EArmorAction::Looking);
	Armor->FinishTrip();
	Armor->ActionTime = SearchDuration;
	Armor->TickLooking(.01f);
	TestNotEqual(TEXT("Looking exits at the actual clip end"), Armor->GetAction(), EArmorAction::Looking);
	Armor->UpdateMarkFollowing(.1f);
	TestFalse(TEXT("Completed investigation releases sound priority"), Armor->IsInvestigatingSound());
	TestTrue(TEXT("Valid mark resumes at current cat position"), Armor->GetInvestigationLocation().Equals(F.Cat->GetActorLocation()));
	Armor->TurnRightAnim = LoadObject<UAnimationAsset>(nullptr, TEXT("/Game/Characters/LivingArmor/Final/Animations/AN_LivingArmor_TurnRight90.AN_LivingArmor_TurnRight90"));
	TestNotNull(TEXT("Authored turn animation loads"), Armor->TurnRightAnim.Get());
	Armor->SetActorRotation(FRotator::ZeroRotator); Armor->BeginTurn(90.f);
	TestTrue(TEXT("Fast turn duration honors editable playback rate"), FMath::IsNearlyEqual(Armor->ActionDuration, Armor->TurnRightAnim->GetPlayLength()/Armor->TurnPlayRate));
	Armor->ActionTime = Armor->ActionDuration*.5f; Armor->TickTurning(.01f);
	TestTrue(TEXT("Actor rotation does not double the authored body turn"), FMath::IsNearlyZero(Armor->GetActorRotation().Yaw));
	const auto* EndpointSequence=CastChecked<UAnimSequence>(Armor->TurnRightAnim.Get());
	const FQuat EndpointRoot=EndpointSequence->ExtractRootMotionFromRange(0.,EndpointSequence->GetPlayLength(),FAnimExtractContext(EndpointSequence->GetPlayLength(),true)).GetRotation();
	const FQuat ExpectedEndpoint=(Armor->TurnStartActorRotation*Armor->TurnMeshBasis*EndpointRoot*Armor->TurnMeshBasis.Inverse()).GetNormalized();
	Armor->ActionTime = Armor->ActionDuration; Armor->TickTurning(.01f);
	AddInfo(FString::Printf(TEXT("Turn endpoint actual yaw %.9f extracted yaw %.9f"),Armor->GetActorRotation().Yaw,ExpectedEndpoint.Rotator().Yaw));
	TestTrue(TEXT("Quarter-turn actor commit matches actual extracted endpoint"),Armor->GetActorQuat().Equals(ExpectedEndpoint,1.e-5f));
	// Root extraction measured 90.072517548 in Task2Fix1Task3Tests01. Sanity-check near a quarter,
	// while the strict quaternion assertion above governs correctness against the actual asset.
	TestTrue(TEXT("Authored extracted quarter stays within one tenth degree of axis"),FMath::Abs(FMath::FindDeltaAngleDegrees(Armor->GetActorRotation().Yaw,90.f)) < .1f);
	Armor->bSeeingCat = true; Sound.Location = FVector(100,100,90);
	Armor->OnSoundHeard_Implementation(Sound, 100.f);
	TestFalse(TEXT("Near detection dominates sound"), Armor->GetInvestigationLocation().Equals(Sound.Location));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunArmorCaptureObstructionTest, "Catrun.PrototypeAI.ArmorCaptureRequiresClearBodyPath", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunArmorCaptureObstructionTest::RunTest(const FString&)
{
	FPrototypeWorld F;
	auto* Armor = F.Spawn<ACatrunArmor>(FVector(70, 0, 90));
	Armor->GetCapsuleComponent()->SetCapsuleRadius(35.f);
	Armor->DispatchBeginPlay();
	auto* Capture = Armor->CapturePresentation.Get();
	auto* LowBlocker = F.Box(FVector(32, 0, 47.5), FVector(2, 80, 47.5));

	const FVector ArmorCenter = Armor->GetCapsuleComponent()->GetComponentLocation();
	const FVector CatCenter = F.Cat->GetCapsuleComponent()->GetComponentLocation();
	TestTrue(TEXT("Low obstacle blocks the actual body-height line"),
		CatrunPerception::SightDistance(*F.World, ArmorCenter, CatCenter, Armor, F.Cat) < FVector::Distance(ArmorCenter, CatCenter));
	TestTrue(TEXT("The existing direct sight ray clears the low obstacle"),
		CatrunPerception::HasDirectSight(*Armor, *F.Cat, F.Settings->VisionTraceHeight));

	FCatrunSoundEvent Bell;
	Bell.Kind = ECatrunSoundKind::Bell;
	Bell.Size = ECatrunSoundSize::Medium;
	Bell.Location = FVector(400, 200, 90);
	Armor->OnSoundHeard_Implementation(Bell, 100.f);
	const EArmorAction InvestigationAction = Armor->GetAction();
	TestTrue(TEXT("The medium bell starts an investigation"),
		Armor->IsInvestigatingSound() && Armor->GetInvestigationLocation().Equals(Bell.Location));

	Armor->UpdateDetection();
	TestTrue(TEXT("The existing detection fan clears the low obstacle"),
		Armor->Detection->CanSee(F.Cat->GetActorLocation(), F.Settings->CatSightRadius));
	TestFalse(TEXT("Low obstacle prevents the armor seeing the cat"), Armor->bSeeingCat);
	TestFalse(TEXT("Low obstacle prevents the alert mark"), Armor->AlertMark->IsVisible());
	TestFalse(TEXT("Low obstacle prevents normal capture"), Capture->IsCapturing());
	TestEqual(TEXT("Blocked detection preserves the current action"), Armor->GetAction(), InvestigationAction);
	TestTrue(TEXT("Blocked detection preserves the investigation and goal"),
		Armor->IsInvestigatingSound() && Armor->GetInvestigationLocation().Equals(Bell.Location));

	Bell.Size = ECatrunSoundSize::Large;
	Bell.Location = FVector(450, -200, 90);
	Armor->OnSoundHeard_Implementation(Bell, 100.f);
	TestTrue(TEXT("A louder bell is still accepted with the cat behind the obstacle"),
		Armor->IsInvestigatingSound() && Armor->GetInvestigationLocation().Equals(Bell.Location));

	// Clear an unexpected capture so the controls still exercise normal detection on the old code.
	if (Capture->IsCapturing())
	{
		Capture->AbortCapture();
		Armor->TickCatching(0.f);
	}
	LowBlocker->Destroy();
	auto* Gate = F.Box(FVector(32, 0, 100), FVector(2, 80, 100));
	auto* GateCollision = CastChecked<UBoxComponent>(Gate->GetRootComponent());
	GateCollision->SetCollisionObjectType(ECC_WorldDynamic);
	TestFalse(TEXT("The tall gate blocks the existing direct sight ray"),
		CatrunPerception::HasDirectSight(*Armor, *F.Cat, F.Settings->VisionTraceHeight));
	Armor->UpdateDetection();
	TestFalse(TEXT("An opaque closed gate prevents detection, alert and capture"),
		Armor->bSeeingCat || Armor->AlertMark->IsVisible() || Capture->IsCapturing());

	GateCollision->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	// A ray through the opening clears both bars, but a 40 cm wide cat cannot pass.
	auto* BarLeft = F.Box(FVector(32,-16,100), FVector(3,4,100));
	auto* BarRight = F.Box(FVector(32,16,100), FVector(3,4,100));
	TestTrue(TEXT("The slit has clear body-height sight"), FMath::IsNearlyEqual(
		CatrunPerception::SightDistance(*F.World, ArmorCenter, CatCenter, Armor, F.Cat), float(FVector::Distance(ArmorCenter,CatCenter))));
	TestFalse(TEXT("A sight slit too narrow for the cat prevents capture"), Armor->HasClearCapturePath(*F.Cat));
	Armor->UpdateDetection();
	TestTrue(TEXT("A visible cat behind narrow bars is detected and the alert is shown"),
		Armor->bSeeingCat && Armor->AlertMark->IsVisible());
	TestFalse(TEXT("Detection through the slit does not start a capture"), Capture->IsCapturing());
	for (AActor* Bar : {BarLeft, BarRight})
		CastChecked<UBoxComponent>(Bar->GetRootComponent())->SetCollisionResponseToChannel(ECC_Pawn, ECR_Overlap);
	TestTrue(TEXT("Bars that allow pawn movement permit the reach"), Armor->HasClearCapturePath(*F.Cat));
	Armor->UpdateDetection();
	TestTrue(TEXT("Clearing physical access starts capture while the cat is still visible"),
		Armor->bSeeingCat && Capture->IsCapturing());
	Capture->AbortCapture();
	Armor->TickCatching(0.f);
	BarLeft->Destroy();
	BarRight->Destroy();

	auto* BasketActions = NewObject<UCatrunBasketInteractionComponent>(F.Cat);
	BasketActions->RegisterComponent();
	BasketActions->BasketPhase = ECatrunBasketPhase::Hidden;
	Armor->UpdateDetection();
	TestFalse(TEXT("Hidden cat stays safe on a clear path"), Armor->bSeeingCat || Capture->IsCapturing());

	BasketActions->BasketPhase = ECatrunBasketPhase::Outside;
	Armor->SetAction(EArmorAction::Looking);
	Armor->UpdateDetection();
	TestTrue(TEXT("An exposed cat is seen and capture interrupts Looking"),
		Armor->bSeeingCat && Armor->AlertMark->IsVisible() && Capture->IsCapturing() && Armor->IsCatching());
	Capture->AbortCapture();

	auto* Ramp = F.Box(FVector(500,0,140), FVector(180,90,10));
	Ramp->SetActorRotation(FRotator(12,0,0));
	FCollisionQueryParams SupportParams(SCENE_QUERY_STAT(CaptureSlopeFixture), false, Armor);
	SupportParams.AddIgnoredActor(F.Cat);
	for (ACharacter* Body : {static_cast<ACharacter*>(Armor), F.Cat})
	{
		const auto* Capsule = Body->GetCapsuleComponent();
		const double X = Body == Armor ? 550. : 450.;
		FHitResult Floor;
		FVector Supported;
		if (!TestTrue(TEXT("Each character stands on the ramp with its own capsule"), CatrunGround::FindSupport(
			*Capsule, FVector(X,0,160.+Capsule->GetScaledCapsuleHalfHeight()), 60.f, 130.f,
			SupportParams, Floor, Supported))) return false;
		Body->SetActorLocation(Supported);
	}
	TestTrue(TEXT("Different capsule heights on an unobstructed slope permit a catch"), Armor->HasClearCapturePath(*F.Cat));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunCanonicalLocomotionTuningTest, "Catrun.Tuning.CanonicalLocomotion", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunCanonicalLocomotionTuningTest::RunTest(const FString&)
{
	FPrototypeWorld F;
	auto* CatClass = LoadClass<ACharacter>(nullptr, TEXT("/Game/Characters/BlackCat/Blueprints/BP_Cat.BP_Cat_C"));
	const auto* PushSettings = LoadObject<UCatrunStatuePuzzleSettings>(nullptr,
		TEXT("/Game/Systems/Interaction/Puzzles/DA_StatuePuzzleSettings.DA_StatuePuzzleSettings"));
	if (!TestNotNull(TEXT("Canonical cat Blueprint loads"), CatClass) || !TestNotNull(TEXT("Statue puzzle settings load"), PushSettings)) return false;
	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	auto* Cat = F.World->SpawnActor<ACharacter>(CatClass, FVector(0, 300, 90), FRotator::ZeroRotator, Params);
	if (!TestNotNull(TEXT("Canonical cat spawns"), Cat)) return false;
	auto* UpdateSpeed = Cat->FindFunction(TEXT("UpdateMovementSpeed"));
	const auto* Running = FindFProperty<FBoolProperty>(CatClass, TEXT("IsRunning"));
	const auto* Sneaking = FindFProperty<FBoolProperty>(CatClass, TEXT("IsSneaking"));
	if (!TestNotNull(TEXT("Normal speed update is callable"), UpdateSpeed) ||
		!TestNotNull(TEXT("Run flag is reflected"), Running) || !TestNotNull(TEXT("Sneak flag is reflected"), Sneaking)) return false;

	auto* Movement = Cat->GetCharacterMovement();
	Movement->SetMovementMode(MOVE_Walking);
	struct FMode { bool bRun; bool bSneak; float Speed; float OriginalSpeed; };
	for (const FMode& Mode : { FMode{false, false, 79.f, 74.f}, FMode{true, false, 134.f, 119.f},
		FMode{true, true, 53.f, 48.f}, FMode{false, true, 53.f, 48.f}, FMode{false, false, 79.f, 74.f} })
	{
		Running->SetPropertyValue_InContainer(Cat, Mode.bRun);
		Sneaking->SetPropertyValue_InContainer(Cat, Mode.bSneak);
		Cat->ProcessEvent(UpdateSpeed, nullptr);
		Cat->ProcessEvent(UpdateSpeed, nullptr);
		TestEqual(TEXT("The Blueprint selects the authored movement cap"), Movement->GetMaxSpeed(), Mode.Speed);
		const float PushLimit = UCatrunCatStateComponent::GetStatuePushSpeedLimit(*Cat);
		TestEqual(TEXT("Statue push uses the prior player locomotion limit"), PushLimit, Mode.OriginalSpeed);
		TestEqual(TEXT("The effective puzzle push cap is preserved"), FMath::Min(PushSettings->PushSpeed, PushLimit),
			FMath::Min(PushSettings->PushSpeed, Mode.OriginalSpeed));
	}
	Cat->SetIsCrouched(true);
	TestEqual(TEXT("Native crouch bypasses the Blueprint locomotion offset"),
		UCatrunCatStateComponent::GetStatuePushSpeedLimit(*Cat), Movement->MaxWalkSpeedCrouched);
	F.Cat->GetCharacterMovement()->SetMovementMode(MOVE_Walking);
	TestEqual(TEXT("Characters without the authored offset retain their original cap"),
		UCatrunCatStateComponent::GetStatuePushSpeedLimit(*F.Cat), F.Cat->GetCharacterMovement()->GetMaxSpeed());
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
		// Framing now aligns to the cat. This test isolates notify-time carry heading.
		Armor->SetActorRotation(FRotator(0.f, TargetYaw, 0.f));
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

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunCaptureCarryClearanceTest, "Catrun.PrototypeAI.CaptureCarryRespectsActualCapsuleWhileCollisionDisabled", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunCaptureCarryClearanceTest::RunTest(const FString&)
{
	// Include a non-Pawn object channel and a disabled component: neither actor sweeps nor
	// hardcoded ECC_Pawn/default response queries can enforce this carry contract.
	for (bool bDisableCapsuleQuery : {false, true})
	{
		FPrototypeWorld F;
		auto* Capsule = F.Cat->GetCapsuleComponent();
		Capsule->SetCollisionObjectType(ECC_WorldDynamic);
		Capsule->SetCollisionResponseToChannel(ECC_WorldStatic, ECR_Block);
		if (bDisableCapsuleQuery) Capsule->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		F.Cat->SetActorLocation(FVector(0, 0, 92));
		F.Cat->SetActorRotation(FRotator(0, -90, 0));
		F.Cat->GetCharacterMovement()->SetMovementMode(MOVE_Flying);
		F.Box(FVector(0, 0, 55), FVector(500, 500, 5)); // capsule bottom is 2cm above support
		auto* Armor = F.Spawn<ACatrunArmor>(FVector(70, 0, 92));
		// The native armor's tall default capsule intersects this low fixture floor. Give
		// both participants the same supported center, and make hand fallback explicit.
		Armor->GetCapsuleComponent()->SetCapsuleSize(20.f, 30.f);
		Armor->SetActorLocation(FVector(70, 0, 92));
		Armor->GetMesh()->SetSkeletalMesh(nullptr);
		auto* Capture = Armor->CapturePresentation.Get();
		Capture->bUseBlueprintPresentation = true;
		Capture->MissingAnimationDuration = 20.f;
		F.Settings->CatchCameraBlendTime = 0.f;
		F.Settings->CatchGrabBlendTime = .4f;
		F.Settings->CatchGrabLatestTime = 10.f;
		F.Settings->CatchHoldOffset = FVector(0, 0, -10);
		F.Settings->CatchFadeOutTime = 10.f; // exercise Fading without issuing travel
		auto* Overhang = F.Box(FVector(35, 0, 142), FVector(6, 60, 5));
		auto* OverhangShape = CastChecked<UBoxComponent>(Overhang->GetRootComponent());
		OverhangShape->SetCollisionResponseToChannel(ECC_Pawn, ECR_Ignore);
		OverhangShape->SetCollisionResponseToChannel(ECC_WorldDynamic, ECR_Block);
		FCollisionQueryParams Params(SCENE_QUERY_STAT(CaptureCarryFixture), false, F.Cat);
		Params.AddIgnoredActor(Armor);
		const FCollisionResponseParams Responses(Capsule->GetCollisionResponseToChannels());
		const auto Shape = Capsule->GetCollisionShape();
		auto IsBlocked = [&](const FVector& Location)
		{
			return F.World->OverlapBlockingTestByChannel(Location, FQuat::Identity,
				Capsule->GetCollisionObjectType(), Shape, Params, Responses);
		};
		TestFalse(TEXT("Supported initial cat capsule clears the overhang"), IsBlocked(F.Cat->GetActorLocation()));
		FVector BodyFrom = Armor->GetCapsuleComponent()->GetComponentLocation();
		const FVector BodyTo = Capsule->GetComponentLocation();
		BodyFrom.Z = BodyTo.Z; // same body-height contract as HasClearCapturePath
		TestTrue(TEXT("Overhang leaves initial body-height capture LOS clear"),
			CatrunPerception::SightDistance(*F.World, BodyFrom, BodyTo, Armor, F.Cat)
				>= FVector::Distance(BodyFrom, BodyTo) - KINDA_SMALL_NUMBER);
		if (!TestTrue(TEXT("Supported capture starts"), Capture->BeginCapture(F.Cat, F.Settings))) continue;
		Capture->TickComponent(0.f, LEVELTICK_All, nullptr);
		TestEqual(TEXT("Zero framing still reaches authored Pickup phase"), Capture->Phase, ECatrunCapturePhase::Pickup);
		const FVector Hold = Armor->GetActorLocation() + Armor->GetActorForwardVector()*35.f
			+ FVector(0, 0, 40) + Armor->GetActorTransform().TransformVectorNoScale(F.Settings->CatchHoldOffset);
		AddInfo(FString::Printf(TEXT("Carry fixture disabledQuery=%d cat=%s armor=%s hold=%s capsuleRadius=%.3f halfHeight=%.3f"),
			bDisableCapsuleQuery, *F.Cat->GetActorLocation().ToString(), *Armor->GetActorLocation().ToString(),
			*Hold.ToString(), Capsule->GetScaledCapsuleRadius(), Capsule->GetScaledCapsuleHalfHeight()));
		TestTrue(TEXT("Real overhang blocks the intended hand endpoint"), IsBlocked(Hold));
		TestFalse(TEXT("Hardcoded Pawn query would incorrectly miss this blocker"),
			F.World->OverlapBlockingTestByChannel(Hold, FQuat::Identity, ECC_Pawn, Shape, Params, Responses));
		TestTrue(TEXT("Matching BP grab starts Holding"), Capture->NotifyGrab(Capture->SessionId));
		TestFalse(TEXT("Carry intentionally keeps actor collision disabled"), F.Cat->GetActorEnableCollision());
		for (int32 Step = 1; Step <= 8; ++Step)
		{
			const FVector Previous = F.Cat->GetActorLocation();
			Capture->TickComponent(.05f, LEVELTICK_All, nullptr);
			FHitResult Hit;
			TestFalse(TEXT("Every carried capsule endpoint stays outside solid scenery"), IsBlocked(F.Cat->GetActorLocation()));
			TestFalse(TEXT("Every carried segment stays on the clear side of the overhang"),
				F.World->SweepSingleByChannel(Hit, Previous, F.Cat->GetActorLocation(), FQuat::Identity,
					Capsule->GetCollisionObjectType(), Shape, Params, Responses));
			if (Step == 4) TestTrue(TEXT("Obstruction preserves half-time heading interpolation"),
				FMath::Abs(FMath::FindDeltaAngleDegrees(F.Cat->GetActorRotation().Yaw, -135.f)) < .01f);
		}
		TestTrue(TEXT("Obstruction preserves original heading completion time"),
			FMath::Abs(FMath::FindDeltaAngleDegrees(F.Cat->GetActorRotation().Yaw, 180.f)) < .01f);
		TestEqual(TEXT("Obstruction does not abort or finish the BP pickup"), Capture->Phase, ECatrunCapturePhase::Holding);
		TestTrue(TEXT("Original BP finish notify still starts fade"), Capture->NotifyFinished(Capture->SessionId));
		Capture->TickComponent(.05f, LEVELTICK_All, nullptr);
		TestEqual(TEXT("Obstructed carry continues through original Fading phase"), Capture->Phase, ECatrunCapturePhase::Fading);
		TestFalse(TEXT("Fading also keeps the actual capsule outside scenery"), IsBlocked(F.Cat->GetActorLocation()));
		OverhangShape->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Capture->TickComponent(.05f, LEVELTICK_All, nullptr);
		TestTrue(TEXT("Cleared route reaches the unchanged authored hand target"), F.Cat->GetActorLocation().Equals(Hold, .01f));
		TestFalse(TEXT("Open-route control remains collision clear"), IsBlocked(F.Cat->GetActorLocation()));
		Capture->AbortCapture();

		// A clear endpoint alone is insufficient: an instant authored lift can cross a thin lintel.
		Overhang->SetActorLocation(FVector(35, 0, 125));
		OverhangShape->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
		F.Settings->CatchGrabBlendTime = 0.f;
		F.Settings->CatchHoldOffset = FVector(-70, 0, -10);
		if (!TestTrue(TEXT("Transit-only blocker capture starts"), Capture->BeginCapture(F.Cat, F.Settings))) continue;
		Capture->TickComponent(0.f, LEVELTICK_All, nullptr);
		const FVector FarHold = Armor->GetActorLocation() + Armor->GetActorForwardVector()*35.f
			+ FVector(0, 0, 40) + Armor->GetActorTransform().TransformVectorNoScale(F.Settings->CatchHoldOffset);
		TestFalse(TEXT("Transit fixture begins clear"), IsBlocked(F.Cat->GetActorLocation()));
		TestFalse(TEXT("Transit fixture destination is clear beyond the lintel"), IsBlocked(FarHold));
		FHitResult TransitHit;
		const FVector TransitStart = F.Cat->GetActorLocation();
		TestTrue(TEXT("Actual capsule sweep proves a blocker between clear endpoints"),
			F.World->SweepSingleByChannel(TransitHit, TransitStart, FarHold, FQuat::Identity,
				Capsule->GetCollisionObjectType(), Shape, Params, Responses));
		Capture->NotifyGrab(Capture->SessionId);
		Capture->TickComponent(.01f, LEVELTICK_All, nullptr);
		TestFalse(TEXT("Zero-duration carry cannot tunnel through the lintel"),
			F.World->SweepSingleByChannel(TransitHit, TransitStart, F.Cat->GetActorLocation(), FQuat::Identity,
				Capsule->GetCollisionObjectType(), Shape, Params, Responses));
		TestFalse(TEXT("Zero-duration blocked carry endpoint remains clear"), IsBlocked(F.Cat->GetActorLocation()));
		OverhangShape->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Capture->TickComponent(.01f, LEVELTICK_All, nullptr);
		TestTrue(TEXT("Zero-duration clear carry still completes immediately"), F.Cat->GetActorLocation().Equals(FarHold, .01f));
		Capture->AbortCapture();
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunBasketEntryHeightTest, "Catrun.PrototypeAI.BasketEntryHeightKeepsCapsuleUpright", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunBasketEntryHeightTest::RunTest(const FString&)
{
	for (double EntryZ : {-90.,90.})
	{
		FPrototypeWorld F;
		auto* Actions=NewObject<UCatrunBasketInteractionComponent>(F.Cat); Actions->RegisterComponent(); Actions->CatOwner=F.Cat;
		auto* Basket=F.Spawn<ACatrunHideBasket>(FVector::ZeroVector);
		const FTransform Original(FRotator(0,37,0),FVector(-80,0,EntryZ));
		F.Cat->SetActorTransform(Original); F.Cat->GetCharacterMovement()->SetMovementMode(MOVE_Flying);
		Actions->EnterAnimation=nullptr; Actions->ExitAnimation=nullptr;
		TestTrue(TEXT("Entry height regression has a real horizontal and vertical offset"),
			FMath::Abs((Basket->GetHiddenLocation()-Original.GetLocation()).Rotation().Pitch)>45.);
		Actions->EnterBasket(Basket,Original.GetLocation());
		TestTrue(TEXT("Ascending and descending entry headings keep the actual capsule upright"),
			F.Cat->GetCapsuleComponent()->GetUpVector().Equals(FVector::UpVector,.001));
		TestTrue(TEXT("Entry still faces the actual horizontal basket direction"),FMath::IsNearlyZero(F.Cat->GetActorRotation().Yaw,.001));
		Actions->FinishEnter();
		TestTrue(TEXT("Elevated hidden anchor does not change capsule orientation"),F.Cat->GetCapsuleComponent()->GetUpVector().Equals(FVector::UpVector,.001));
		Actions->AbortBasket();
		TestTrue(TEXT("Abort restores exact original location and heading"),F.Cat->GetActorTransform().Equals(Original,.001));
		TestTrue(TEXT("Height-only entry correction preserves restored collision and movement"),
			F.Cat->GetActorEnableCollision() && F.Cat->GetCharacterMovement()->MovementMode==MOVE_Flying);
	}
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
	F.Cat->SetActorRotation(FRotator(0,37,0));
	const FQuat EntryRotation=F.Cat->GetActorQuat();
	TestTrue(TEXT("Regression fixture has a vertical hidden-anchor offset"),FMath::IsNearlyEqual(FMath::Abs(Basket->GetHiddenLocation().Z-Origin.Z),90.));
	Actions->EnterBasket(Basket, Origin);
	TestTrue(TEXT("Vertical entry retains yaw and never tips the gameplay capsule"),
		F.Cat->GetCapsuleComponent()->GetUpVector().Equals(FVector::UpVector,.001) && F.Cat->GetActorQuat().Equals(EntryRotation,.001));
	Actions->FinishEnter();
	TestTrue(TEXT("Hidden phase retains upright support-query capsule"),F.Cat->GetCapsuleComponent()->GetUpVector().Equals(FVector::UpVector,.001));
	Actions->BasketPhase = ECatrunBasketPhase::Exiting; Actions->Busy = true;
	F.Cat->SetActorLocation(Destination);
	Blocker = F.Box(Destination, FVector(25,25,40));
	Actions->FinishExit();
	TestEqual(TEXT("Late blocker returns cat to hidden state"), Actions->BasketPhase, ECatrunBasketPhase::Hidden);
	TestFalse(TEXT("Late blocker never restores overlapping collision"), F.Cat->GetActorEnableCollision());
	// A second late blocker occupies the saved entry while the component is removed.
	F.Box(FVector(0,0,48), FVector(1000,1000,10));
	auto* EntryOccupant=F.Spawn<ACatrunArmor>(Actions->SavedEntryTransform.GetLocation());
	// Record the real fallback geometry, rather than treating a collision-disabled pawn
	// as proof that the full capsule can be restored at the fixture's assumed height.
	const auto* Capsule=F.Cat->GetCapsuleComponent();
	TestEqual(TEXT("Restore fixture uses its intended capsule radius"),Capsule->GetScaledCapsuleRadius(),20.f);
	TestEqual(TEXT("Restore fixture uses its intended capsule halfheight"),Capsule->GetScaledCapsuleHalfHeight(),30.f);
	const float Step=FMath::Max(20.f,Capsule->GetScaledCapsuleRadius()*2.f+4.f);
	for (int32 Ring=1;Ring<=3 && Step*Ring<=150.f;++Ring)
	{
		const FVector Reference=Actions->SavedEntryTransform.GetLocation()+FVector(Step*Ring,0,0);
		FCollisionQueryParams Params(SCENE_QUERY_STAT(BasketRestoreFixtureSupport),false,F.Cat);
		FHitResult Hit; FVector Center;
		const bool bSupport=CatrunGround::FindSupport(*Capsule,Reference+FVector(0,0,Capsule->GetScaledCapsuleHalfHeight()),
			20.f,Capsule->GetScaledCapsuleHalfHeight()+22.f,Params,Hit,Center);
		FTransform Candidate=Actions->SavedEntryTransform; Candidate.SetLocation(Center);
		FHitResult TransitHit; Params.AddIgnoredActor(EntryOccupant);
		const bool bTransitBlocked=F.World->SweepSingleByChannel(TransitHit,Actions->SavedEntryTransform.GetLocation(),Center,
			Candidate.GetRotation(),ECC_Pawn,Capsule->GetCollisionShape(),Params,FCollisionResponseParams(Capsule->GetCollisionResponseToChannels()));
		AddInfo(FString::Printf(TEXT("Restore ring=%d reference=%s support=%d center=%s floor=%s penetrating=%d normal=%s impact=%s endpointClear=%d transitBlocker=%s"),
			Ring,*Reference.ToString(),bSupport,*Center.ToString(),*GetNameSafe(Hit.GetActor()),Hit.bStartPenetrating,
			*Hit.ImpactNormal.ToString(),*Hit.ImpactPoint.ToString(),bSupport && CatrunRestore::IsPlacementClear(*F.Cat,Candidate),
			bTransitBlocked ? *GetNameSafe(TransitHit.GetActor()) : TEXT("none")));
	}
	Actions->EndPlay(EEndPlayReason::Destroyed);
	TestFalse(TEXT("Blocked basket origin selects a different restoration position"), F.Cat->GetActorLocation().Equals(Actions->SavedEntryTransform.GetLocation()));
	TestTrue(TEXT("Basket EndPlay fallback has no capsule encroachment"), CatrunRestore::IsPlacementClear(*F.Cat, F.Cat->GetActorTransform()));
	TestTrue(TEXT("Component removal restores surviving cat collision"), F.Cat->GetActorEnableCollision());
	TestTrue(TEXT("Safe fallback restores the exact pre-entry facing"),F.Cat->GetActorQuat().Equals(EntryRotation,.001));
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
	TestEqual(TEXT("Framing callback sees stable prepared Catching action"), Armor->GetAction(), EArmorAction::Catching);
	TestFalse(TEXT("Aborted setup releases restart acquisition"), F.World->GetSubsystem<UCatrunRestartSubsystem>()->IsCatching());
	TestFalse(TEXT("Aborted setup releases input lock"), F.PC->IsMoveInputIgnored());
	TestTrue(TEXT("Aborted prepared setup has no half-restored walking path"), !Armor->HasDestination() && Armor->PathCorners.IsEmpty());
	Armor->TickCatching(.01f);
	TestFalse(TEXT("Canceled framing exits Catching on the next owner tick"), Armor->IsCatching());

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
		// Queue acceptance does not publish an arrival intent. Resolve the destination
		// boundary explicitly here; this temporary-world test never loads a level.
		Session->ResolveArrivalRestart(Package);
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
	TestTrue(TEXT("Short bell begins after capture cleanup"),Actions->BeginBellAction());
	const int32 ShortSession=Actions->BellSessionId;
	++GFrameCounter; F.World->GetTimerManager().Tick(0.f);
	++GFrameCounter; F.World->GetTimerManager().Tick(.6f);
	TestTrue(TEXT("Emission precedes the shorter recovery deadline"),Actions->bBellEmitted && Actions->bBellActive);
	Actions->EmitBellAction(ShortSession);
	TestTrue(TEXT("Repeated emission callback retains the emitted session"),Actions->bBellEmitted && Actions->BellSessionId==ShortSession);
	++GFrameCounter; F.World->GetTimerManager().Tick(.41f);
	TestFalse(TEXT("Default bell releases Busy and its action by 1.01 seconds"),Actions->Busy || Actions->bBellActive);
	TestEqual(TEXT("Short recovery restores walking"),F.Cat->GetCharacterMovement()->MovementMode,TEnumAsByte<EMovementMode>(MOVE_Walking));
	TestEqual(TEXT("Short recovery restores the previous animation mode"),F.Cat->GetMesh()->GetAnimationMode(),StableMode);
	Actions->Busy=true;
	Actions->FinishBellAction(ShortSession);
	TestTrue(TEXT("Late recovery cannot clear a subsequent action's Busy"),Actions->Busy); Actions->Busy=false;
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

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunCandlePatrolSafetyTest,"Catrun.PrototypeAI.CandlePatrolUsesOffsetCapsuleAndFloor",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FCatrunCandlePatrolSafetyTest::RunTest(const FString&)
{
	FPrototypeWorld F;
	F.Cat->SetActorLocation(FVector(-1000,-1000,90));
	auto* Floor = F.Box(FVector(300,100,-12),FVector(600,500,10)); // top -2, capsule bottom 0
	auto* Candle = F.Spawn<ACatrunCandle>(FVector::ZeroVector);
	Candle->BlockingCapsule->SetRelativeLocation(FVector(0,80,60));
	Candle->BlockingCapsule->SetRelativeScale3D(FVector(1.5f,1.f,1.f));
	Candle->PatrolRelativePoints = {FVector(300,0,0)};
	Candle->PatrolSpeed = 100.f;
	Candle->ResetPatrol();
	Candle->UpdatePatrol(1.f);
	TestTrue(TEXT("Default-disabled route remains stationary"), Candle->GetActorLocation().IsNearlyZero());
	Candle->bPatrolEnabled = true;
	// Real WorldDynamic trigger above the floor overlaps Pawn but cannot support its capsule.
	auto* Trigger = F.Box(FVector(100,80,6),FVector(200,100,2));
	auto* TriggerShape = CastChecked<UBoxComponent>(Trigger->GetRootComponent());
	TriggerShape->SetCollisionObjectType(ECC_WorldDynamic);
	TriggerShape->SetCollisionResponseToChannel(ECC_Pawn,ECR_Overlap);
	Candle->UpdatePatrol(.1f);
	TestTrue(TEXT("Nonblocking trigger does not conceal supporting solid floor"),Candle->GetActorLocation().X > 5.f);
	Candle->SetActorLocation(FVector::ZeroVector); Candle->ResetPatrol();
	auto* Blocker = F.Box(FVector(70,80,60),FVector(5,15,50));
	Candle->UpdatePatrol(1.f);
	TestTrue(TEXT("Offset capsule stops before obstruction actor-centered query would miss"), Candle->GetActorLocation().X < 50.f);
	TestTrue(TEXT("Authoring attachment offset is unchanged"), Candle->BlockingCapsule->GetRelativeLocation().Equals(FVector(0,80,60)));
	const FVector BlockedAt = Candle->GetActorLocation();
	Candle->UpdatePatrol(1.f);
	TestTrue(TEXT("Blocked patrol retains position and waypoint"), Candle->GetActorLocation().Equals(BlockedAt) && Candle->PatrolIndex == 0);
	Blocker->Destroy(); Candle->UpdatePatrol(.2f);
	TestTrue(TEXT("Removal safely resumes the original destination"), Candle->GetActorLocation().X > BlockedAt.X);
	Candle->bTracking = true;
	Candle->PatrolWaitLeft = .8f;
	const FVector TrackingAt = Candle->GetActorLocation();
	Candle->UpdatePatrol(.5f);
	TestTrue(TEXT("Tracking freezes route and pause countdown"), Candle->GetActorLocation().Equals(TrackingAt) && FMath::IsNearlyEqual(Candle->PatrolWaitLeft,.8f));
	Candle->bTracking = false;
	auto* Guard = F.World->GetSubsystem<UCatrunPuzzleSuspension>(); Guard->Acquire(Candle);
	Candle->UpdatePatrol(10.f);
	TestTrue(TEXT("Puzzle reveal also preserves route wait"), FMath::IsNearlyEqual(Candle->PatrolWaitLeft,.8f)); Guard->Release(Candle);
	Candle->SetActorLocation(FVector::ZeroVector); Candle->ResetPatrol();
	Floor->Destroy();
	F.Box(FVector(-60,80,-12),FVector(90,100,10)); // floor ends x30
	F.Box(FVector(270,80,-12),FVector(70,100,10)); // resumes x200; target itself is supported
	Candle->UpdatePatrol(5.f);
	TestTrue(TEXT("Large delta cannot bridge a floor gap to a supported endpoint"), Candle->GetActorLocation().X < 40.f);
	Candle->ResetPatrol();
	TestTrue(TEXT("New patrol lifecycle resets route and timers"), Candle->PatrolIndex == 0 && Candle->PatrolStep == 1 && Candle->PatrolWaitLeft == 0.f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunSuspendedSoundDeliveryTest,"Catrun.PrototypeAI.SuspendedSoundPreservesDelayAndStableBoundedDrain",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FCatrunSuspendedSoundDeliveryTest::RunTest(const FString&)
{
	FPrototypeWorld F;
	auto* Listener = F.Spawn<ACatrunSoundDeliveryProbe>(FVector(112.5,12.5,90));
	F.Settings->SoundSpeed = 100.f;
	FCatrunSoundEvent Event; Event.Location = FVector(12.5,12.5,0);
	TestTrue(TEXT("Actual grid emission schedules the listener"), F.Manager->EmitSound(Event));
	if (!TestEqual(TEXT("One live listener queued"),F.Manager->PendingSounds.Num(),1)) return false;
	const double Arrival = F.Manager->PendingSounds[0].ArrivalTime;
	const float Strength = F.Manager->PendingSounds[0].RemainingBudget;
	TestTrue(TEXT("Propagation has nonzero travel delay"), Arrival > .1);
	F.Manager->Tick(float(Arrival*.3));
	auto* Guard = F.World->GetSubsystem<UCatrunPuzzleSuspension>(); Guard->Acquire(Listener);
	const double Frozen = F.Manager->ListenerClock;
	F.Manager->Tick(20.f);
	TestTrue(TEXT("Reveal freezes logical arrival clock before deliveries"), F.Manager->ListenerClock == Frozen && Listener->Received.IsEmpty());
	TestTrue(TEXT("Emission during reveal is retained too"),F.Manager->EmitSound(Event));
	Guard->Release(Listener);
	const float Remaining = float(Arrival-Frozen);
	F.Manager->Tick(Remaining-.01f);
	TestTrue(TEXT("Original remaining delay survives long reveal"),Listener->Received.IsEmpty());
	F.Manager->Tick(.02f);
	TestEqual(TEXT("Original event delivered once at preserved deadline"),Listener->Received.Num(),1);
	TestTrue(TEXT("Saved propagation strength is unchanged"),FMath::IsNearlyEqual(Listener->Budgets[0],Strength));
	F.Manager->Tick(float(Arrival));
	TestEqual(TEXT("Event emitted during reveal keeps its own full delay"),Listener->Received.Num(),2);
	// Due-at-acquire plus 40 equal arrivals prove queue order and retained bounded remainder.
	Listener->SetActorLocation(Event.Location);
	Guard->Acquire(Listener);
	for (int32 Index=0; Index<40; ++Index) { Event.Location.Z = float(Index); F.Manager->EmitSound(Event); }
	TestEqual(TEXT("Due sounds remain queued during suspension"),F.Manager->PendingSounds.Num(),40);
	Guard->Release(Listener); F.Manager->Tick(0.f);
	TestEqual(TEXT("At most 32 callbacks in a manager tick"),Listener->Received.Num(),34);
	TestEqual(TEXT("Excess notifications are retained"),F.Manager->PendingSounds.Num(),8);
	for (int32 Index=0; Index<32; ++Index) TestEqual(TEXT("Equal-arrival callbacks retain insertion order"),Listener->Received[Index+2].Location.Z,double(Index));
	F.Manager->Tick(0.f); TestEqual(TEXT("Retained remainder drains next tick"),Listener->Received.Num(),42);
	// Reentrant emission plus acquiring reveal must not invalidate the drain or lose the appended sound.
	bool bFirst = true;
	Listener->OnDelivery = [&] { if (bFirst) { bFirst=false; Guard->Acquire(Listener); F.Manager->EmitSound(Event); } };
	F.Manager->EmitSound(Event);
	TestEqual(TEXT("Callback reentrancy leaves appended event pending"),F.Manager->PendingSounds.Num(),1);
	Guard->Release(Listener); F.Manager->Tick(0.f);
	TestEqual(TEXT("Reentrant event eventually delivered exactly once"),Listener->Received.Num(),44);
	Guard->Acquire(Listener); F.Manager->EmitSound(Event); Guard->Release(Listener); Listener->Destroy(); F.Manager->Tick(0.f);
	TestTrue(TEXT("Destroyed listener is safely removed"),F.Manager->PendingSounds.IsEmpty());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunDynamicSightCoverageTest,"Catrun.PrototypeAI.DynamicSightMatchesFanAndIgnoresPawnBodies",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FCatrunDynamicSightCoverageTest::RunTest(const FString&)
{
	FPrototypeWorld F;
	auto* Candle = F.Spawn<ACatrunCandle>(FVector(-200,0,60));
	Candle->bAutoAlignEyes=false; Candle->bPenaltiesEnabled=false;
	Candle->Tick(.01f); // configure actual fan from actual manager
	auto* PawnBody = F.Spawn<ACatrunArmor>(FVector(-100,0,90));
	auto* Gate = F.Box(FVector(-50,0,100),FVector(5,100,100));
	auto* Shape = CastChecked<UBoxComponent>(Gate->GetRootComponent()); Shape->SetCollisionObjectType(ECC_WorldDynamic);
	TestFalse(TEXT("Movable untagged gate blocks direct LOS behind a Pawn"),CatrunPerception::HasDirectSight(*Candle,*F.Cat,F.Settings->VisionTraceHeight));
	TestTrue(TEXT("Same gate clips visual fan behind a Pawn"),Candle->Sight->GetFreeDistance(Candle->GetActorLocation(),FVector::ForwardVector,300.f)<200.f);
	Gate->SetActorLocation(FVector(-50,500,100));
	TestTrue(TEXT("Moving gate away clears direct LOS"),CatrunPerception::HasDirectSight(*Candle,*F.Cat,F.Settings->VisionTraceHeight));
	TestTrue(TEXT("Armor Pawn body does not cut fan holes"),FMath::IsNearlyEqual(Candle->Sight->GetFreeDistance(Candle->GetActorLocation(),FVector::ForwardVector,300.f),300.f));
	auto* OtherCandle=F.Spawn<ACatrunCandle>(FVector(-50,0,0));
	TestTrue(TEXT("Candle AActor Pawn capsule is also intentionally excluded"),CatrunPerception::HasDirectSight(*Candle,*F.Cat,F.Settings->VisionTraceHeight));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunArmorPatrolSlotsAndFirstSoundTest,"Catrun.PrototypeAI.PatrolSkipsEmptySlotsAndReactsToFirstSound",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FCatrunArmorPatrolSlotsAndFirstSoundTest::RunTest(const FString&)
{
	FPrototypeWorld F;
	auto* Armor = F.Spawn<ACatrunArmor>(FVector(300,300,90));
	auto* Point = F.Spawn<ACatrunPatrolPoint>(FVector(900,300,90));
	Armor->PatrolPoints.Add(nullptr); // an empty first slot used to make the armor wait for ever
	Armor->PatrolPoints.Add(Point);
	Armor->DispatchBeginPlay();
	TestEqual(TEXT("BeginPlay moves past the empty first slot"),Armor->PatrolIndex,1);
	Armor->PatrolIndex=0; Armor->BeginPatrolLeg();
	TestTrue(TEXT("A leg toward an empty slot walks to the next filled point"),Armor->PatrolIndex==1 && Armor->GetAction()==EArmorAction::Walking && !Armor->PathCorners.IsEmpty());

	FCatrunSoundEvent Device; Device.Location=FVector(700,700,90); Device.Kind=ECatrunSoundKind::Device; Device.Size=ECatrunSoundSize::Medium;
	Armor->OnSoundHeard_Implementation(Device,100.f);
	TestEqual(TEXT("First sound on a patrol walk plays the reaction"),Armor->GetAction(),EArmorAction::Reacting);
	Armor->ActionTime = Armor->ActionDuration;
	Armor->TickReacting(0.f);
	FCatrunSoundEvent Bell; Bell.Location=FVector(700,300,90); // louder, so it replaces the destination
	Armor->OnSoundHeard_Implementation(Bell,100.f);
	TestTrue(TEXT("The louder sound is accepted"),Armor->Destination.Equals(Bell.Location));
	TestNotEqual(TEXT("An alerted armor runs to the next sound without reacting again"),Armor->GetAction(),EArmorAction::Reacting);

	// Reach the bell while the grid is unavailable. The patrol retries away from its post and waypoint.
	Armor->SetActorLocation(Bell.Location);
	auto& Grid = const_cast<FCatrunGridData&>(F.Manager->GetGrid());
	Grid.Walkable.Init(0, Grid.NumCells());
	Armor->FinishTrip();
	Armor->TickIdle(.6f);
	if (!TestTrue(TEXT("A failed patrol retry waits away from the waypoint"),
		Armor->bPatrolWaiting && Armor->GetAction() == EArmorAction::Idle && Armor->PathCorners.IsEmpty()))
		return false;

	Grid.Walkable.Init(1, Grid.NumCells());
	Device.Location = FVector(500,300,90);
	Armor->OnSoundHeard_Implementation(Device, 100.f);
	TestTrue(TEXT("A reachable sound during retry immediately starts a walk to the new location"),
		Armor->GetAction() == EArmorAction::Walking && Armor->IsInvestigatingSound()
		&& Armor->Destination.Equals(Device.Location));

	Armor->SetActorLocation(Device.Location);
	Armor->FinishTrip();
	if (!TestTrue(TEXT("Investigation resumes the interrupted patrol"),
		Armor->GetAction() == EArmorAction::Walking && Armor->bReturningToPost && !Armor->PathCorners.IsEmpty()))
		return false;

	// Trigger the normal stuck timeout while still far from the point. The route may advance its wait.
	Armor->ActionTime = 1.f;
	Armor->TickWalking(Armor->StuckTime * 4.f + .1f);
	TestTrue(TEXT("A stuck leg ending short of the waypoint keeps the patrol alerted"),
		Armor->bPatrolWaiting && Armor->bPatrolAlerted);
	Armor->TickIdle(Armor->PatrolWaitLeft + .01f);
	if (!TestTrue(TEXT("The straight return leg resumes after the wait"),
		Armor->GetAction() == EArmorAction::Walking && Armor->PathCorners.Num() == 1 && Armor->NextCorner == 0))
		return false;

	// Move the fixture to its planned final corner and let ordinary walking process the arrival.
	const FVector End = Armor->PathCorners.Last();
	Armor->SetActorLocation(FVector(End.X, End.Y, Armor->GetActorLocation().Z));
	Armor->TickWalking(.01f);
	TestTrue(TEXT("Reaching the patrol point rearms the reaction"),
		Armor->GetAction() == EArmorAction::Idle && Armor->bPatrolWaiting && !Armor->bPatrolAlerted);
	Armor->OnSoundHeard_Implementation(Device, 100.f);
	TestEqual(TEXT("The first sound after waypoint arrival plays the reaction again"),
		Armor->GetAction(), EArmorAction::Reacting);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunArmorTravelSafetyTest,"Catrun.PrototypeAI.DoorReplansActivePatrolAndSweepsHandoff",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FCatrunArmorTravelSafetyTest::RunTest(const FString&)
{
	FPrototypeWorld F;
	auto* Armor = F.Spawn<ACatrunArmor>(FVector(300,300,90)); Armor->DispatchBeginPlay();
	auto* Point = F.Spawn<ACatrunPatrolPoint>(FVector(900,300,90)); Armor->PatrolPoints.Add(Point);
	Armor->BeginPatrolLeg();
	FVector Target;
	TestTrue(TEXT("Patrol intent resolves current waypoint"),Armor->TryGetActiveTravelDestination(Target) && Target.Equals(Point->GetActorLocation()));
	Armor->ReplanAfterDoor();
	TestTrue(TEXT("Actual post-door path ends at patrol instead of spawn"),!Armor->PathCorners.IsEmpty() && FVector::Dist2D(Armor->PathCorners.Last(),Point->GetActorLocation())<40.f);
	Armor->Action=EArmorAction::OpeningDoor;
	FCatrunSoundEvent Sound; Sound.Location=FVector(700,700,90); Armor->OnSoundHeard_Implementation(Sound,100.f);
	TestTrue(TEXT("Sound while opening replaces active travel intent"),Armor->TryGetActiveTravelDestination(Target) && Target.Equals(Sound.Location));
	Armor->ReplanAfterDoor();
	TestTrue(TEXT("Replan follows new sound snapshot"),!Armor->PathCorners.IsEmpty() && FVector::Dist2D(Armor->PathCorners.Last(),Sound.Location)<40.f);
	// Missing tracked bone resolves component location; its synthetic start makes a real 200cm desired handoff.
	Armor->DoorAnimTrackedBone=TEXT("MissingTestBone");
	Armor->DoorAnimStartBoneLocation=Armor->GetMesh()->GetBoneLocation(Armor->DoorAnimTrackedBone)-FVector(200,0,0);
	Armor->GetMesh()->SetRelativeScale3D(FVector(-1,1,1)); Armor->MeshBaseScale=FVector::OneVector;
	F.Box(Armor->GetActorLocation()+FVector(100,0,0),FVector(10,80,100));
	const FVector Before=Armor->GetActorLocation(); Armor->EndDoorAnimation();
	TestTrue(TEXT("Swept capsule cannot cross late handoff blocker"),Armor->GetActorLocation().X<Before.X+100.f);
	TestTrue(TEXT("Blocked handoff restores mirror state"),Armor->GetMesh()->GetRelativeScale3D().Equals(FVector::OneVector));
	Armor->Action=EArmorAction::Walking;
	TestTrue(TEXT("Another capture can acquire shared guard"),F.World->GetSubsystem<UCatrunRestartSubsystem>()->TryBeginCatch());
	Armor->StartCatch(*F.Cat);
	TestEqual(TEXT("Other owner's acquisition freezes approach"),Armor->GetAction(),EArmorAction::WaitingForCapture);
	F.World->GetSubsystem<UCatrunRestartSubsystem>()->CancelCatch();
	TestEqual(TEXT("Release restores prior AI action"),Armor->GetAction(),EArmorAction::Walking);
	auto* Door=F.Spawn<ACatrunDoor>(FVector(1000,1000,0));
	Door->BeginHandOpen(Armor->GetActorLocation());
	Armor->DoorBeingOpened=Door; Armor->bDoorHandDriven=true; Armor->bDoorReleased=false;
	Armor->Action=EArmorAction::OpeningDoor; Armor->DoorStep=ACatrunArmor::EDoorStep::Animation;
	Armor->DoorAnimStartBoneLocation=Armor->GetMesh()->GetBoneLocation(Armor->DoorAnimTrackedBone)-FVector(200,0,0);
	Armor->GetMesh()->SetRelativeScale3D(FVector(-1,1,1));
	TestTrue(TEXT("Capture acquires during blocked door presentation"),Armor->CapturePresentation->BeginCapture(F.Cat,F.Settings));
	TestTrue(TEXT("Capture preparation releases door, mirror, and hand ownership"),!Armor->DoorBeingOpened.IsValid() && !Armor->bDoorHandDriven && Armor->bDoorReleased && Armor->GetMesh()->GetRelativeScale3D().Equals(FVector::OneVector));
	TestTrue(TEXT("Released door timer can finish independently"),Door->IsActorTickEnabled());
	Armor->CapturePresentation->AbortCapture(); Armor->TickCatching(.01f);
	TestFalse(TEXT("Canceled door capture cannot strand armor Catching"),Armor->IsCatching());
	TestTrue(TEXT("Abort does not restore old mirrored door snapshot"),Armor->GetMesh()->GetRelativeScale3D().Equals(FVector::OneVector));

	// Reproduce real post-door path failure and mark expiry, including replacement paths that fail too.
	// Modes: live-mark control, return disabled, already at post, failed return, failed patrol.
	for (int32 Mode=0; Mode<5; ++Mode)
	{
		FPrototypeWorld Retry;
		auto* Guard=Retry.Spawn<ACatrunArmor>(FVector(300,300,90)); Guard->DispatchBeginPlay();
		if (Mode!=2) Guard->SetActorLocation(FVector(500,300,90));
		Retry.Cat->SetActorLocation(FVector(900,300,90));
		if (Mode==1) Guard->bReturnToPost=false;
		ACatrunPatrolPoint* Replacement=nullptr;
		if (Mode==4)
		{
			Replacement=Retry.Spawn<ACatrunPatrolPoint>(FVector(500,900,90));
			Guard->PatrolPoints.Add(Replacement);
		}
		Guard->SetFollowingMark(true); Guard->UpdateMarkFollowing(.1f);
		TestTrue(TEXT("Fixture first establishes a real mark path"),!Guard->PathCorners.IsEmpty());
		const FVector ExpiringTarget=Guard->Destination;
		auto& Grid=const_cast<FCatrunGridData&>(Retry.Manager->GetGrid());
		Grid.Walkable.Init(0,Grid.NumCells());
		Guard->Action=EArmorAction::OpeningDoor; Guard->ReplanAfterDoor();
		TestTrue(TEXT("Unwalkable grid causes actual post-door failure and bounded retry"),Guard->bAwaitingDoorReplan && Guard->PathCorners.IsEmpty() && Guard->GetAction()==EArmorAction::Idle);
		if (Mode==0)
		{
			Grid.Walkable.Init(1,Grid.NumCells()); Guard->TickIdle(.6f);
			TestTrue(TEXT("A still-active mark retains and resumes its legitimate door retry"),!Guard->bAwaitingDoorReplan && Guard->GetAction()==EArmorAction::Walking && !Guard->PathCorners.IsEmpty() && FVector::Dist2D(Guard->PathCorners.Last(),ExpiringTarget)<40.f);
			Guard->SetFollowingMark(false);
			TestTrue(TEXT("Mark loss preserves an already valid last-known-position walking path"),Guard->GetAction()==EArmorAction::Walking && !Guard->PathCorners.IsEmpty());
			continue;
		}
		Guard->SetFollowingMark(false); // no current corner: FinishTrip has explicitly ended the old trip
		TestFalse(TEXT("An ended mark trip cannot retain door retry ownership"),Guard->bAwaitingDoorReplan);
		if (Replacement)
			TestTrue(TEXT("Failed replacement patrol owns its ordinary wait"),Guard->bPatrolWaiting && Guard->TravelIntent==ACatrunArmor::ETravelIntent::Patrol);
		else
			TestTrue(TEXT("Idle or failed-return branch has no old travel intent"),Guard->TravelIntent==ACatrunArmor::ETravelIntent::None);
		Grid.Walkable.Init(1,Grid.NumCells()); Guard->TickIdle(.6f);
		if (Replacement)
			TestTrue(TEXT("Restored grid resumes replacement patrol instead of expired mark"),Guard->GetAction()==EArmorAction::Walking && !Guard->PathCorners.IsEmpty() && FVector::Dist2D(Guard->PathCorners.Last(),Replacement->GetActorLocation())<40.f && FVector::Dist2D(Guard->PathCorners.Last(),ExpiringTarget)>100.f);
		else
			TestTrue(TEXT("Making old mark reachable cannot resurrect an ended idle trip"),Guard->GetAction()==EArmorAction::Idle && Guard->PathCorners.IsEmpty() && !Guard->bAwaitingDoorReplan);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunTurnCurveHandoffTest,"Catrun.PrototypeAI.AuthoredTurnCurveHandoffIsNonlinearAndOnceOnly",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FCatrunTurnCurveHandoffTest::RunTest(const FString&)
{
	FPrototypeWorld F;
	auto* Armor=F.Spawn<ACatrunArmor>(FVector(500,500,90));
	Armor->TurnRightAnim=LoadObject<UAnimationAsset>(nullptr,TEXT("/Game/Characters/LivingArmor/Final/Animations/AN_LivingArmor_TurnRight90.AN_LivingArmor_TurnRight90"));
	Armor->TurnLeftAnim=LoadObject<UAnimationAsset>(nullptr,TEXT("/Game/Characters/LivingArmor/Final/Animations/AN_LivingArmor_TurnLeft90.AN_LivingArmor_TurnLeft90"));
	for (bool bRight : {false,true})
	{
		const auto* Sequence=Cast<UAnimSequence>(bRight ? Armor->TurnRightAnim.Get() : Armor->TurnLeftAnim.Get());
		if (!TestNotNull(TEXT("Actual authored turn sequence exists"),Sequence)) return false;
		for (float Fraction : {.1f,.25f,.5f,.75f,.9f})
		{
			Armor->SetActorRotation(FRotator(0,170,0));
			Armor->GetMesh()->SetRelativeRotation(FRotator(0,-90,0));
			Armor->BeginTurn(bRight ? 90.f : -90.f);
			const float Time=Sequence->GetPlayLength()*Fraction;
			// This fixture has no mesh. Use explicit missing-player clock fallback, still sample compressed curve.
			Armor->ActionTime=Time/(Armor->TurnPlayRate*Sequence->RateScale);
			const FQuat Root=Sequence->ExtractRootMotionFromRange(0.,Time,FAnimExtractContext(Time,true)).GetRotation();
			const FQuat Expected=FRotator(0,170,0).Quaternion()*FRotator(0,-90,0).Quaternion()*Root*FRotator(0,-90,0).Quaternion().Inverse();
			Armor->CommitTurn(false);
			TestTrue(TEXT("Interrupted heading matches actual compressed root curve and mesh basis"),Armor->GetActorQuat().Equals(Expected,1.e-3f));
			const FQuat Once=Armor->GetActorQuat(); Armor->CommitTurn(false);
			TestTrue(TEXT("Repeated interruption never applies accumulated root twice"),Armor->GetActorQuat().Equals(Once));
			if (Fraction==.25f) TestTrue(TEXT("Early clip root is measurably nonlinear"),FMath::Abs(FMath::Abs(Root.Rotator().Yaw)-22.5f)>5.f);
		}
	}
	// Verify playback position wins over native ActionTime for BOTH real native and BP players.
	auto* MeshAsset=LoadObject<USkeletalMesh>(nullptr,TEXT("/Game/Characters/LivingArmor/Final/Meshes/SK_LivingArmor_Final.SK_LivingArmor_Final"));
	if (!TestNotNull(TEXT("Actual armor mesh exists for playback test"),MeshAsset)) return false;
	Armor->GetMesh()->SetSkeletalMesh(MeshAsset);
	for (bool bBlueprint : {false,true})
	{
		Armor->bUseBlueprintAnimation=bBlueprint;
		Armor->SetActorRotation(FRotator::ZeroRotator);
		if (bBlueprint) Armor->GetMesh()->SetAnimInstanceClass(UAnimInstance::StaticClass());
		Armor->BeginTurn(90.f);
		auto* Sequence=CastChecked<UAnimSequence>(Armor->TurnRightAnim.Get());
		const float ActualTime=Sequence->GetPlayLength()*.25f;
		if (bBlueprint)
		{
			auto* Instance=Armor->GetMesh()->GetAnimInstance();
			if (!TestNotNull(TEXT("Actual animation instance initialized"),Instance)) return false;
			auto* Montage=Instance->PlaySlotAnimationAsDynamicMontage(Sequence,TEXT("DefaultSlot"),0.f,0.f,Armor->TurnPlayRate);
			if (!TestNotNull(TEXT("Actual dynamic montage initialized"),Montage)) return false;
			Instance->Montage_SetPosition(Montage,ActualTime);
		}
		else Armor->GetMesh()->SetPosition(ActualTime,false);
		Armor->ActionTime=Armor->ActionDuration*.9f; // deliberately disagrees with actual quarter-position
		float ReadTime=-1.f;
		TestTrue(TEXT("Matching playback time is available"),Armor->GetTurnPlaybackTime(ReadTime));
		TestTrue(TEXT("Native/single and dynamic montage yield actual sequence position"),FMath::IsNearlyEqual(ReadTime,ActualTime,.001f));
		Armor->CommitTurn(false);
		TestTrue(TEXT("Handoff uses actual nonlinear early root, not later native timer"),FMath::IsNearlyEqual(Armor->GetActorRotation().Yaw,7.447f,.25f));
	}
	Armor->bUseBlueprintAnimation=false;
	Armor->SetActorRotation(FRotator::ZeroRotator); Armor->BeginTurn(180.f);
	const auto* ChainSequence=CastChecked<UAnimSequence>(Armor->TurnRightAnim.Get());
	const FQuat ChainRoot=ChainSequence->ExtractRootMotionFromRange(0.,ChainSequence->GetPlayLength(),FAnimExtractContext(ChainSequence->GetPlayLength(),true)).GetRotation();
	const FQuat ChainBasis=Armor->TurnMeshBasis;
	const FQuat QuarterDelta=(ChainBasis*ChainRoot*ChainBasis.Inverse()).GetNormalized();
	Armor->ActionTime=Armor->ActionDuration; Armor->TickTurning(.01f);
	AddInfo(FString::Printf(TEXT("Chain first yaw %.9f remaining %d committed %d basis yaw %.9f duration %.9f"),Armor->GetActorRotation().Yaw,Armor->TurnsRemaining,Armor->bTurnCommitted,Armor->TurnStartActorRotation.Rotator().Yaw,Armor->ActionDuration));
	TestTrue(TEXT("First 180 chain handoff is one quarter turn"),FMath::IsNearlyEqual(Armor->GetActorRotation().Yaw,90.f,.1f));
	TestTrue(TEXT("Second quarter starts with fresh basis and commit guard"),Armor->TurnsRemaining==1 && !Armor->bTurnCommitted && Armor->TurnStartActorRotation.Equals(QuarterDelta,1.e-5f));
	Armor->ActionTime=Armor->ActionDuration; Armor->TickTurning(.01f);
	AddInfo(FString::Printf(TEXT("Chain second yaw %.9f remaining %d committed %d action %d expected yaw %.9f actual quaternion %s expected quaternion %s"),Armor->GetActorRotation().Yaw,Armor->TurnsRemaining,Armor->bTurnCommitted,int32(Armor->Action),(QuarterDelta*QuarterDelta).Rotator().Yaw,*Armor->GetActorQuat().ToString(),*(QuarterDelta*QuarterDelta).ToString()));
	TestTrue(TEXT("Second handoff equals two actual compressed endpoint deltas"),Armor->GetActorQuat().Equals((QuarterDelta*QuarterDelta).GetNormalized(),1.e-5f));
	// Two measured extracted deltas accumulate ~.145 degrees; retain a small .2-degree axis sanity bound.
	TestTrue(TEXT("Two authored extracted quarters remain within two tenths degree of half-turn"),FMath::Abs(FMath::FindDeltaAngleDegrees(Armor->GetActorRotation().Yaw,180.f))<.2f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunCaptureFramingYawTest,"Catrun.PrototypeAI.CaptureFramingSmoothShortestYawAndCancel",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FCatrunCaptureFramingYawTest::RunTest(const FString&)
{
	FPrototypeWorld F;
	auto* Armor=F.Spawn<ACatrunArmor>(FVector(300,0,90));
	Armor->SetActorRotation(FRotator(0,179,0));
	auto* Capture=Armor->CapturePresentation.Get(); Capture->bUseBlueprintPresentation=true;
	F.Settings->CatchCameraBlendTime=1.f;
	TestTrue(TEXT("Capture acquired"),Capture->BeginCapture(F.Cat,F.Settings));
	TestTrue(TEXT("Acquisition does not snap yaw"),FMath::IsNearlyEqual(Armor->GetActorRotation().Yaw,179.f));
	Capture->TickComponent(.5f,LEVELTICK_All,nullptr);
	TestTrue(TEXT("Framing crosses wrap via shortest half degree"),FMath::IsNearlyEqual(FMath::FindDeltaAngleDegrees(179.f,Armor->GetActorRotation().Yaw),.5f,.01f));
	Capture->AbortCapture();
	TestFalse(TEXT("Cancel releases capture"),Capture->IsCapturing());
	Armor->Tick(.01f);
	TestFalse(TEXT("Cancel owner leaves prepared catching action"),Armor->IsCatching());
	Capture->BeginCapture(F.Cat,F.Settings); Capture->TickComponent(1.f,LEVELTICK_All,nullptr);
	TestEqual(TEXT("Pickup still begins at original framing deadline"),Capture->Phase,ECatrunCapturePhase::Pickup);
	TestTrue(TEXT("Exact target yaw reached before pickup"),FMath::Abs(FMath::FindDeltaAngleDegrees(Armor->GetActorRotation().Yaw,180.f))<.01f);
	Capture->AbortCapture();
	F.Settings->CatchCameraBlendTime=0.f;
	Armor->SetActorRotation(FRotator(0,90,0)); Capture->BeginCapture(F.Cat,F.Settings); Capture->TickComponent(0.f,LEVELTICK_All,nullptr);
	TestTrue(TEXT("Explicit zero framing reaches target immediately"),Capture->Phase==ECatrunCapturePhase::Pickup && FMath::Abs(FMath::FindDeltaAngleDegrees(Armor->GetActorRotation().Yaw,180.f))<.01f);
	Capture->AbortCapture();
	return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunArmorDetectionDisplayTest,"Catrun.PrototypeAI.ArmorDisplayUsesCatCenterBoundaryWithoutChangingPerception",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FCatrunArmorDetectionDisplayTest::RunTest(const FString&)
{
	FPrototypeWorld F;
	const TCHAR* RingPath = TEXT("/Game/Systems/Sound/M_ArmorDetectionRing.M_ArmorDetectionRing");
	auto* Ring = LoadObject<UMaterialInterface>(nullptr, RingPath);
	F.Settings->VisionMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Systems/Sound/M_VisionFan.M_VisionFan"));
	if (!TestNotNull(TEXT("Armor ring material loads"), Ring) ||
		!TestNotNull(TEXT("Original candle fan material loads"), F.Settings->VisionMaterial.Get())) return false;
	F.Settings->ArmorDetectRadius = 150.f;
	F.Settings->CatSightRadius = 15.f;
	auto* Armor = F.Spawn<ACatrunArmor>(FVector(800,800,90));
	Armor->DispatchBeginPlay();
	Armor->bShowDetectionDisplay = true;
	Armor->Tick(.01f);
	auto* Fan = Armor->Detection.Get();
	TestEqual(TEXT("Display radius includes actual cat body overlap threshold"),Fan->GetDisplayRange(),165.f);
	TestEqual(TEXT("Armor display uses its own faint opacity"),Fan->GetDisplayOpacity(),.12f);
	auto* ArmorPlane = FindObject<UStaticMeshComponent>(Armor, TEXT("Detection_VisionPlane"));
	if (!TestNotNull(TEXT("Armor created a visible floor plane"), ArmorPlane)) return false;
	TestTrue(TEXT("Armor actor opts in to its display"), ArmorPlane->IsVisible());
	auto* RingMID = Cast<UMaterialInstanceDynamic>(ArmorPlane->GetMaterial(0));
	if (!TestNotNull(TEXT("Armor uses a dynamic display material"), RingMID)) return false;
	TestTrue(TEXT("Armor floor display uses the dedicated ring parent"), RingMID->Parent.Get() == Ring);
	TestEqual(TEXT("Rendered ring receives the display radius"), RingMID->K2_GetScalarParameterValue(TEXT("Range")), 165.f);
	TestEqual(TEXT("Rendered ring receives the actor opacity"), RingMID->K2_GetScalarParameterValue(TEXT("Opacity")), .12f);
	const FVector DisplayCenter = ArmorPlane->GetComponentLocation();
	TestEqual(TEXT("Armor floor display retains its authored height"), DisplayCenter.Z, F.Manager->GetGrid().Origin.Z + F.Settings->VisualHeight);
	auto* DistTex = Cast<UTexture2D>(RingMID->K2_GetTextureParameterValue(TEXT("DistTex")));
	if (!TestNotNull(TEXT("Ring has the runtime obstacle-distance texture"), DistTex) ||
		!TestTrue(TEXT("Distance texture stores a row of float samples"), DistTex->GetSizeX() >= 4 &&
			DistTex->GetSizeY() == 1 && DistTex->GetPixelFormat() == PF_FloatRGBA)) return false;
	const FVector Origin=Armor->GetActorLocation();
	TestTrue(TEXT("Cat at the visible outer boundary remains detectable"),Fan->CanSee(Origin+FVector(165,0,0),15.f));
	TestFalse(TEXT("Display padding never increases detection range"),Fan->CanSee(Origin+FVector(166,0,0),15.f));
	TestFalse(TEXT("Point-sized target is still outside original radius"),Fan->CanSee(Origin+FVector(151,0,0),0.f));
	auto* Candle = F.Spawn<ACatrunCandle>(FVector(-800,-800,90));
	Candle->bPenaltiesEnabled=false;
	Candle->Tick(.01f);
	auto* CandlePlane = FindObject<UStaticMeshComponent>(Candle, TEXT("Sight_VisionPlane"));
	if (!TestNotNull(TEXT("Candle created its floor plane"), CandlePlane)) return false;
	auto* CandleMID = Cast<UMaterialInstanceDynamic>(CandlePlane->GetMaterial(0));
	if (!TestNotNull(TEXT("Candle uses a dynamic display material"), CandleMID)) return false;
	TestTrue(TEXT("Candle floor display uses the original fan parent"), CandleMID->Parent.Get() == F.Settings->VisionMaterial.Get());
	TestEqual(TEXT("Rendered candle uses authored opacity"), CandleMID->K2_GetScalarParameterValue(TEXT("Opacity")), F.Settings->VisionOpacity);
	TestEqual(TEXT("Candle continues using shared authored opacity"),Candle->Sight->GetDisplayOpacity(),-1.f);
	TestEqual(TEXT("Shared opacity not changed by armor styling"),F.Settings->VisionOpacity,.35f);
	F.Box(Origin+FVector(80,0,0),FVector(5,100,100));
	Armor->Tick(.01f);
	TestFalse(TEXT("Display style still respects blocking geometry for detection"),Fan->CanSee(Origin+FVector(140,0,0),15.f));
	TestTrue(TEXT("Opposite side remains detectable"), Fan->CanSee(Origin - FVector(165,0,0), 15.f));
	// Ray order covers [-180, 180] degrees. East is at the middle, west at the seam.
	FTexture2DMipMap& Mip = DistTex->GetPlatformData()->Mips[0];
	const auto* Samples = static_cast<const FFloat16Color*>(Mip.BulkData.LockReadOnly());
	const float Blocked = Samples[DistTex->GetSizeX() / 2].R.GetFloat();
	const float Open = Samples[0].R.GetFloat();
	Mip.BulkData.Unlock();
	TestTrue(TEXT("Ring samples the wall distance on its blocked side"), Blocked >= 75.f && Blocked < 80.f);
	TestEqual(TEXT("Ring samples the padded boundary on its open side"), Open, 165.f);
	Armor->bShowDetectionDisplay = false;
	Armor->Tick(.01f);
	TestFalse(TEXT("Actor can hide the ring"), ArmorPlane->IsVisible());
	TestTrue(TEXT("Hiding the ring keeps detection active"), Fan->CanSee(Origin - FVector(165,0,0), 15.f));
	return true;
}
#endif
