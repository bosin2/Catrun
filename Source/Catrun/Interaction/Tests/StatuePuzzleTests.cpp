#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Interaction/CatrunStatuePuzzle.h"
#include "Interaction/CatrunBasketInteractionComponent.h"
#include "Interaction/CatrunPuzzleRevealComponent.h"
#include "Interaction/CatrunPuzzleSuspension.h"
#include "Interaction/CatrunPuzzleReset.h"
#include "CatrunPuzzleCallbackProbe.h"
#include "Monster/CatrunArmor.h"
#include "Monster/CatrunCandle.h"
#include "Monster/CatrunMarkSubsystem.h"
#include "Monster/CatrunRestartSubsystem.h"
#include "Sound/CatrunBellComponent.h"
#include "Sound/CatrunSoundSettings.h"
#include "Sound/CatrunDoor.h"
#include "Sound/SoundGridManager.h"
#include "Components/StaticMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/InputComponent.h"
#include "Camera/CameraActor.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/LocalPlayer.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/PlayerState.h"
#include "GameFramework/WorldSettings.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "LevelFlow/CatrunProgressSave.h"
#include "LevelFlow/Tests/CatrunCheckpointTestBackend.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Grid/CatrunGridData.h"
#include "Pathfinding/ArmorPathfinder.h"
#include "Sound/SoundPropagation.h"
#include "TimerManager.h"

namespace
{
	struct FStatueFixture
	{
		UWorld* World;
		ACatrunStatuePuzzle* Puzzle;
		ACharacter* Cat;
		AActor* Statue;
		AActor* Plate;
		AActor* Gate;
		AActor* Box(FVector Location,FVector Extent, bool Collision=true)
		{
			AActor* Actor=World->SpawnActor<AActor>();
			UBoxComponent* Shape=NewObject<UBoxComponent>(Actor);
			Actor->SetRootComponent(Shape);
			Shape->SetBoxExtent(Extent);
			Shape->SetCollisionProfileName(Collision ? TEXT("BlockAllDynamic") : TEXT("NoCollision"));
			Shape->RegisterComponent();
			Actor->SetActorLocation(Location);
			return Actor;
		}
		FStatueFixture(float GateHeight=246.f, bool bStage2Checkpoint=false)
		{
			const auto Init=UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false);
			UPackage* Package = bStage2Checkpoint ? CreatePackage(*FString::Printf(TEXT("/Temp/CatrunCheckpoint_%s/Stage2"),
				*FGuid::NewGuid().ToString(EGuidFormats::Digits))) : nullptr;
			World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,Package,true,ERHIFeatureLevel::Num,&Init);
			GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
			if (bStage2Checkpoint)
			{
				auto* Instance = NewObject<UGameInstance>();
				World->SetGameInstance(Instance);
				Instance->Init();
			}
			Box(FVector(0,0,-10),FVector(2000,2000,10));
			Statue=Box(FVector(0,0,0),FVector(60,60,75));
			Statue->GetRootComponent()->SetRelativeLocation(FVector(0,0,0));
			Cast<UBoxComponent>(Statue->GetRootComponent())->SetBoxExtent(FVector(60,60,75));
			// Actual assets have a floor-level pivot and a 150cm tall body.
			UBoxComponent* Body=Cast<UBoxComponent>(Statue->GetRootComponent());
			USceneComponent* Root=NewObject<USceneComponent>(Statue);
			Root->RegisterComponent();
			Statue->SetRootComponent(Root);
			Body->AttachToComponent(Root,FAttachmentTransformRules::KeepRelativeTransform);
			Body->SetRelativeLocation(FVector(0,0,75));
			Plate=Box(FVector(0,200,5),FVector(65,65,1),false);
			Gate=Box(FVector(500,0,GateHeight*.5),FVector(72,3,GateHeight*.5));
			Cat=World->SpawnActor<ACharacter>();
			Cat->GetCapsuleComponent()->SetCapsuleSize(20,26);
			Cat->SetActorLocation(FVector(0,-88,26));
			Cat->GetCharacterMovement()->SetMovementMode(MOVE_Walking);
			Puzzle=World->SpawnActor<ACatrunStatuePuzzle>();
			Puzzle->Settings=NewObject<UCatrunStatuePuzzleSettings>(Puzzle);
			auto& Link=Puzzle->Links.AddDefaulted_GetRef();
			Link.PuzzleId=bStage2Checkpoint ? TEXT("C") : TEXT("Test"); Link.Statue=Statue; Link.Plate=Plate; Link.Gate=Gate;
			if (bStage2Checkpoint)
			{
				auto& Later = Puzzle->Links.AddDefaulted_GetRef();
				Later.PuzzleId = TEXT("A");
				Later.Statue = Box(FVector(850,0,75), FVector(60,60,75));
				Later.Plate = Box(FVector(850,200,5), FVector(65,65,1), false);
				Later.Gate = Box(FVector(1100,0,GateHeight*.5), FVector(72,3,GateHeight*.5));
			}
			Puzzle->InitializePuzzle();
		}
		~FStatueFixture()
		{
			Puzzle->Reveal->CancelReveal();
			if (auto* Instance = World->GetGameInstance())
			{
				World->EndPlay(EEndPlayReason::Quit);
				Instance->Shutdown();
				World->SetGameInstance(nullptr);
			}
			GEngine->DestroyWorldContext(World);
			World->DestroyWorld(false);
		}
		APlayerController* AddPlayer()
		{
			World->InitializeActorsForPlay(FURL());
			auto* PC=World->SpawnActor<APlayerController>();
			PC->Possess(Cat); PC->SetViewTarget(Cat);
			return PC;
		}
	};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FStage2ChapterStartTest,"Catrun.Stage2.SolvesStayInCurrentAttemptAndArrivalsStartFresh",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FStage2ChapterStartTest::RunTest(const FString&)
{
	for (const auto Arrival : {ECatrunProgressArrival::Resume, ECatrunProgressArrival::FailureRefill, ECatrunProgressArrival::ResetStage})
	{
		FCheckpointBackend Backend;
		auto* Legacy = NewObject<UCatrunProgressSave>();
		Legacy->SchemaVersion = UCatrunProgressSave::CurrentSchemaVersion;
		Legacy->StageId = Legacy->HighestUnlockedStageId = TEXT("Stage2");
		Legacy->Stage2RemainingMs = 123456;
		Legacy->Stage2SolvedMask = UCatrunProgressSave::AllPuzzleBits;
		UGameplayStatics::SaveGameToMemory(Legacy, Backend.Bytes);
		const TArray<uint8> Original = Backend.Bytes;
		FStatueFixture F(246.f, true);
		F.AddPlayer();
		auto* Session = F.World->GetGameInstance()->GetSubsystem<UCatrunFlowSession>();
		Session->SetSaveBackendForTest(&Backend);
		const FString Package = F.World->GetOutermost()->GetName();
		Session->AcceptTravel(Package, true, false, ECatrunArrivalRestart::Continue);
		TestFalse(TEXT("Tracking an existing Stage2 chapter needs no arrival write"), Session->Arrive(Package));
		TestTrue(TEXT("Fixture has tracked chapter progress"), Session->IsTrackingWorld(Package));
		F.Puzzle->Reveal->bEnabled = false;
		F.Statue->SetActorLocation(FVector(0,200,0));
		F.Puzzle->UpdatePlatesAndGates(.5f);
		TestTrue(TEXT("C seats before its gate fully opens"), F.Puzzle->Links[0].bPressed);
		TestFalse(TEXT("An opening gate has not completed the solve"), F.Puzzle->Links[0].bCompleted);
		F.Puzzle->UpdatePlatesAndGates(3.f);
		TestTrue(TEXT("The fully recessed C gate completes the local attempt"), F.Puzzle->Links[0].bCompleted);
		TestTrue(TEXT("A live Stage2 solve enqueues no save"), !Session->IsSavePending() && Backend.Writes == 0 && Backend.Bytes == Original);
		const float Budget = GetDefault<UCatrunLevelFlowSettings>()->GetClockBudget(TEXT("Stage2"));
		Session->AdvanceClock(Budget * .25f);

		auto* FreshPuzzle = F.World->SpawnActor<ACatrunStatuePuzzle>();
		for (const FName PuzzleId : {FName(TEXT("A")), FName(TEXT("B")), FName(TEXT("C"))})
		{
			const double X = -950. - 350. * FreshPuzzle->Links.Num();
			auto& Link = FreshPuzzle->Links.AddDefaulted_GetRef();
			Link.PuzzleId = PuzzleId;
			Link.Statue = F.Box(FVector(X,0,75), FVector(60,60,75));
			Link.Plate = F.Box(FVector(X,200,5), FVector(65,65,1), false);
			Link.Gate = F.Box(FVector(X,450,123), FVector(72,3,123));
		}
		// The fixture lacks a game mode to call actor BeginPlay automatically.
		FreshPuzzle->InitializePuzzle();
		auto* Probe = NewObject<UCatrunPuzzleCallbackProbe>(FreshPuzzle);
		Probe->Puzzle = FreshPuzzle;
		FreshPuzzle->OnPuzzleEvent.AddDynamic(Probe, &UCatrunPuzzleCallbackProbe::PuzzleEvent);
		FreshPuzzle->OnCheckpointRestored.AddDynamic(Probe, &UCatrunPuzzleCallbackProbe::CheckpointRestored);
		const FVector Start = F.Cat->GetActorLocation();
		const bool bContinue = Arrival == ECatrunProgressArrival::Resume;
		Session->AcceptTravel(Package, bContinue, false,
			bContinue ? ECatrunArrivalRestart::Continue : ECatrunArrivalRestart::SkipIntro, -1, 0.f, Arrival);
		F.World->BeginPlay();

		for (int32 Index = 0; Index < FreshPuzzle->Links.Num(); ++Index)
		{
			const auto& Link = FreshPuzzle->Links[Index];
			const double X = -950. - 350. * Index;
			TestFalse(TEXT("Arrival leaves each link unsolved"), Link.bPressed || Link.bCompleted);
			TestEqual(TEXT("Each statue remains at its authored start"), Link.Statue->GetActorLocation(), FVector(X,0,75));
			TestEqual(TEXT("Each plate remains raised"), Link.Plate->GetActorLocation(), FVector(X,200,5));
			TestEqual(TEXT("Each gate starts in its authored location"), Link.Gate->GetActorLocation(), FVector(X,450,123));
		}
		TestEqual(TEXT("Arrival grants the full Stage2 clock"), Session->GetRemainingSeconds(TEXT("Stage2")), Budget);
		TestTrue(TEXT("Arrival preserves ordinary start and pawn collision"), F.Cat->GetActorLocation().Equals(Start, .1) && F.Cat->GetActorEnableCollision());
		TestTrue(TEXT("Arrival emits no reveal, restore or solve event"), FreshPuzzle->Reveal->Phase == ECatrunPuzzleRevealPhase::Inactive
			&& Probe->Counts[static_cast<int32>(ECatrunStatueEvent::Completed)] == 0 && Probe->CheckpointRestoreCount == 0);
		TestTrue(TEXT("Arrival did not rewrite legacy bytes"), !Session->IsSavePending() && Backend.Writes == 0 && Backend.Bytes == Original);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunStageClockAdmissionTest,"Catrun.LevelFlow.StageClockPausesAndOwnsTimeoutOnce",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FCatrunStageClockAdmissionTest::RunTest(const FString&)
{
	FStatueFixture F(246.f, true);
	auto* PC = F.AddPlayer();
	PC->SetPlayer(NewObject<ULocalPlayer>(GEngine));
	if (!TestTrue(TEXT("The fixture controller owns a local player"), PC->GetLocalPlayer() && PC->IsLocalController())) return false;
	F.World->BeginPlay();
	auto* Flow = F.World->GetSubsystem<UCatrunLevelFlowSubsystem>();
	auto* Restart = F.World->GetSubsystem<UCatrunRestartSubsystem>();
	const float Budget = Flow->GetStageClockState().BudgetSeconds;
	TestTrue(TEXT("Recognized Stage2 has a timed allocation"), Budget > 0.f);
	PC->SetIgnoreMoveInput(true);
	Flow->Tick(20.f);
	TestEqual(TEXT("Arrival control lock freezes remaining time"), Flow->GetStageClockState().RemainingSeconds, Budget);
	PC->SetIgnoreMoveInput(false);
	Flow->Tick(20.f);
	TestEqual(TEXT("First settled frame omits prior cinematic delta"), Flow->GetStageClockState().RemainingSeconds, Budget);
	Flow->Tick(1.f);
	TestEqual(TEXT("Ordinary control consumes elapsed game time"), Flow->GetStageClockState().RemainingSeconds, Budget - 1.f);

	F.World->GetWorldSettings()->SetPauserPlayerState(F.World->SpawnActor<APlayerState>());
	Flow->Tick(9.f);
	TestEqual(TEXT("World pause freezes the stage clock"), Flow->GetStageClockState().RemainingSeconds, Budget - 1.f);
	F.World->GetWorldSettings()->SetPauserPlayerState(nullptr);
	auto* Suspension = F.World->GetSubsystem<UCatrunPuzzleSuspension>();
	TestTrue(TEXT("Puzzle reveal can acquire suspension"), Suspension->Acquire(F.Puzzle));
	Flow->Tick(9.f);
	TestEqual(TEXT("Puzzle reveal freezes the stage clock"), Flow->GetStageClockState().RemainingSeconds, Budget - 1.f);
	Suspension->Release(F.Puzzle);

	TestTrue(TEXT("Exit can reserve before timeout"), Flow->ReserveExitTransition(F.Puzzle));
	Flow->Tick(Budget + 1.f);
	TestFalse(TEXT("Clock cannot take ownership from a qualified exit"), Restart->IsCatching());
	Flow->ReleaseExitTransition(F.Puzzle);
	TestTrue(TEXT("An armor catch can reserve before timeout"), Restart->TryBeginCatch(F.Puzzle));
	Flow->Tick(Budget + 1.f);
	TestTrue(TEXT("Clock cannot take ownership from an admitted capture"), Restart->IsCatchOwner(F.Puzzle));
	Restart->CancelCatch(F.Puzzle);
	Flow->Tick(.01f);
	Flow->Tick(Budget + 1.f);
	TestTrue(TEXT("Zero time acquires the same failure reservation"), Restart->IsCatchOwner(Restart));
	TestEqual(TEXT("Time clamps to zero"), Flow->GetStageClockState().RemainingSeconds, 0.f);
	TestFalse(TEXT("Capture cannot interrupt timeout"), Restart->TryBeginCatch(F.Puzzle));
	TestFalse(TEXT("Exit cannot interrupt timeout"), Flow->ReserveExitTransition(F.Puzzle));
	Restart->CancelCatch();
	Flow->Tick(1.f);
	TestFalse(TEXT("Same surviving world cannot replay timeout"), Restart->IsCatching());
	TestFalse(TEXT("Timeout cleanup releases move and look locks"), PC->IsMoveInputIgnored() || PC->IsLookInputIgnored());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FStatuePlateGateTest,"Catrun.Stage2.PlateGateAndSafeClosing",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FStatuePlateGateTest::RunTest(const FString&)
{
	FStatueFixture F;
	F.Cat->SetActorLocation(FVector(0,200,31));
	F.Puzzle->UpdatePlatesAndGates(3);
	TestFalse(TEXT("Cat alone cannot press the statue plate"),F.Puzzle->Links[0].bPressed);
	F.Cat->SetActorLocation(FVector(800,0,26));
	F.Statue->SetActorLocation(FVector(0,200,0));
	F.Puzzle->UpdatePlatesAndGates(3);
	TestTrue(TEXT("Statue centred on plate activates it"),F.Puzzle->Links[0].bPressed);
	TestEqual(TEXT("Gate fully sinks"),F.Puzzle->Links[0].GateOffset,-280.f);
	TestTrue(TEXT("Gate top is completely below the floor"),F.Gate->GetComponentsBoundingBox(true).Max.Z<0);
	TestTrue(TEXT("Plate visibly depresses"),F.Plate->GetActorLocation().Equals(FVector(0,200,3)));
	F.Statue->SetActorLocation(FVector(0,0,0));
	F.Cat->SetActorLocation(FVector(500,0,26));
	F.Puzzle->UpdatePlatesAndGates(3);
	TestTrue(TEXT("Seat remains latched until reset"),F.Puzzle->Links[0].bPressed);
	TestTrue(TEXT("Room reset restores statue and unlatches"),F.Puzzle->ResetStatue(TEXT("Test")));
	F.Puzzle->UpdatePlatesAndGates(3);
	TestEqual(TEXT("Closing cannot materialize gate around cat"),F.Puzzle->Links[0].GateOffset,-280.f);
	F.Cat->SetActorLocation(FVector(800,0,26));
	F.Puzzle->UpdatePlatesAndGates(3);
	TestEqual(TEXT("Gate closes after doorway clears"),F.Puzzle->Links[0].GateOffset,0.f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FStatuePushTest,"Catrun.Stage2.PushContactCollisionAndBusy",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FStatuePushTest::RunTest(const FString&)
{
	FStatueFixture F;
	TestFalse(TEXT("Cannot pull a statue by moving away"),F.Puzzle->TryPushStatue(0,F.Cat,FVector(0,-1,0),.05f));
	TestTrue(TEXT("Cat behind the statue can push it"),F.Puzzle->TryPushStatue(0,F.Cat,FVector(0,1,0),.05f));
	TestTrue(TEXT("Weighted push accelerates from rest"),F.Statue->GetActorLocation().Equals(FVector(0,.2,0),.001));
	F.Cat->SetActorLocation(FVector(0,-87.8,26));
	UCatrunBasketInteractionComponent* Actions=NewObject<UCatrunBasketInteractionComponent>(F.Cat);
	Actions->RegisterComponent();
	Actions->Busy=true;
	TestFalse(TEXT("Bell/basket busy state prevents pushing"),F.Puzzle->TryPushStatue(0,F.Cat,FVector(0,1,0),.05f));
	Actions->Busy=false;
	F.Box(FVector(0,64,75),FVector(100,3,75));
	TestFalse(TEXT("Solid wall stops a complete large-frame sweep"),F.Puzzle->TryPushStatue(0,F.Cat,FVector(0,1,0),.5f));
	F.Cat->SetActorLocation(FVector(0,-500,26));
	TestFalse(TEXT("Remote input cannot move a statue"),F.Puzzle->TryPushStatue(0,F.Cat,FVector(0,1,0),.05f));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FStatueCornerTest, "Catrun.Stage2.WrongPushPreservesReverseContact",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FStatueCornerTest::RunTest(const FString&)
{
	FStatueFixture F;
	// The inside faces are at X=170 and Y=170. Neither blocks the initial statue.
	F.Box(FVector(175,0,75), FVector(5,400,75));
	F.Box(FVector(0,175,75), FVector(400,5,75));
	auto Push = [&](const FVector& Direction)
	{
		F.Cat->SetActorLocation(F.Statue->GetActorLocation() - Direction*83. + FVector(0,0,26));
		return F.Puzzle->TryPushStatue(0, F.Cat, Direction, .05f);
	};
	for (const FVector Direction : {FVector::ForwardVector, FVector::RightVector})
	{
		const FVector Start = F.Statue->GetActorLocation();
		for (int32 Step = 0; Step < 50 && Push(Direction); ++Step) {}
		const FVector End = F.Statue->GetActorLocation();
		TestTrue(TEXT("Open space still permits ordinary progress"), FVector::DotProduct(End-Start,Direction) > 40.);
		const double Gap = 170. - FVector::DotProduct(End,Direction) - 60.;
		TestTrue(TEXT("Approaching a wall leaves room for the 40 cm cat"), Gap > 40.);
	}
	for (const FVector Direction : {-FVector::ForwardVector, -FVector::RightVector})
	{
		const FVector Contact = F.Statue->GetActorLocation() - Direction*82. + FVector(0,0,28);
		const UCapsuleComponent* Capsule = F.Cat->GetCapsuleComponent();
		FCollisionQueryParams Params(SCENE_QUERY_STAT(StatueReverseControl),false,F.Cat);
		TestFalse(TEXT("The reverse push begins from a real capsule-clear position"),
			F.World->OverlapBlockingTestByChannel(Contact,FQuat::Identity,Capsule->GetCollisionObjectType(),
				Capsule->GetCollisionShape(),Params,FCollisionResponseParams(Capsule->GetCollisionResponseToChannels())));
		F.Cat->SetActorLocation(Contact);
		TestTrue(TEXT("The player can push back out on each axis"), F.Puzzle->TryPushStatue(0,F.Cat,Direction,.1f));
	}
	// A released statue must respect the same margin as a driven one.
	F.Statue->SetActorLocation(FVector(0.,62.,0.));
	F.Puzzle->Links[0].PushVelocity = FVector(0,100,0);
	F.Cat->SetActorLocation(FVector(-300,0,26));
	F.Puzzle->Tick(.25f);
	TestTrue(TEXT("Coasting cannot consume the reverse contact space"), 170.-F.Statue->GetActorLocation().Y-60. > 40.);
	TestTrue(TEXT("Blocked coast clears momentum"), F.Puzzle->Links[0].PushVelocity.IsNearlyZero());
	// A narrow post covers the middle of a face but leaves usable side contacts.
	F.Statue->SetActorLocation(FVector::ZeroVector);
	F.Box(FVector(86,0,50),FVector(3,3,50));
	TestTrue(TEXT("One accessible off-center reverse contact permits the push"), Push(FVector::ForwardVector));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FStatueResetTest,"Catrun.Stage2.ResetDoesNotTeleportOntoPlayer",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FStatueResetTest::RunTest(const FString&)
{
	FStatueFixture F;
	F.Statue->SetActorLocation(FVector(0,200,0));
	F.Cat->SetActorLocation(FVector(0,0,26));
	TestFalse(TEXT("Reset rejected while cat occupies initial position"),F.Puzzle->ResetPuzzle());
	TestTrue(TEXT("Rejected reset leaves statue unchanged"),F.Statue->GetActorLocation().Equals(FVector(0,200,0)));
	F.Cat->SetActorLocation(FVector(800,0,26));
	TestTrue(TEXT("Reset succeeds after moving clear"),F.Puzzle->ResetPuzzle());
	TestTrue(TEXT("Statue returns to saved placement"),F.Statue->GetActorLocation().Equals(FVector::ZeroVector));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FLocalStatueResetTest,"Catrun.Stage2.RoomRecoveryIsLocalAndCollisionSafe",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FLocalStatueResetTest::RunTest(const FString&)
{
	FStatueFixture F;
	AActor* Other = F.Box(FVector(700,700,75),FVector(60,60,75));
	auto& Link = F.Puzzle->Links.AddDefaulted_GetRef();
	Link.PuzzleId=TEXT("Other"); Link.Statue=Other;
	Link.InitialStatue=FTransform(FVector(1000,1000,75));
	F.Statue->SetActorLocation(FVector(0,200,0));
	F.Cat->SetActorLocation(FVector(900,0,26));
	TestFalse(TEXT("Unknown room cannot reset any statue"),F.Puzzle->ResetStatue(TEXT("Missing")));
	TestTrue(TEXT("Room recovery succeeds"),F.Puzzle->ResetStatue(TEXT("Test")));
	TestTrue(TEXT("Other room's statue is unchanged"),Other->GetActorLocation().Equals(FVector(700,700,75)));
	TestTrue(TEXT("Player is not teleported"),F.Cat->GetActorLocation().Equals(FVector(900,0,26)));
	F.Statue->SetActorLocation(FVector(0,200,0));
	Other->SetActorLocation(FVector(0,0,75));
	TestFalse(TEXT("Another statue blocks the recovery destination"),F.Puzzle->ResetStatue(TEXT("Test")));
	TestTrue(TEXT("Blocked recovery preserves the moved statue"),F.Statue->GetActorLocation().Equals(FVector(0,200,0)));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FPuzzleRoutingTest,"Catrun.Stage2.DynamicObstaclesAffectSoundAndArmor",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FPuzzleRoutingTest::RunTest(const FString&)
{
	FCatrunGridData G;
	G.Width=G.Height=9; G.CellSize=25;
	G.Walkable.Init(1,81); G.EdgeMask.Init(255,81); G.CostMultiplier.Init(1,81); G.WallDistance.Init(1000,81);
	G.PuzzleClearance.Init(1000,81);
	for(int32 Y=0;Y<9;++Y) G.PuzzleClearance[G.CellIndex(4,Y)]=0;
	TArray<uint8> Gates; TArray<float> Distance; TArray<FVector> Corners;
	const int32 Start=G.CellIndex(1,4), End=G.CellIndex(7,4);
	CatrunSoundPropagation::Run(G,Gates,Start,2000,Distance);
	TestEqual(TEXT("Closed puzzle gate blocks sound"),Distance[End],CatrunSoundPropagation::Unreached);
	CatrunArmorPath::FParams Params; Params.ClearanceRadius=20;
	TestFalse(TEXT("Armor cannot path through a puzzle gate"),CatrunArmorPath::FindPath(G,G.CellCenter(Start),G.CellCenter(End),Params,Corners));
	G.PuzzleClearance.Init(1000,81);
	CatrunSoundPropagation::Run(G,Gates,Start,2000,Distance);
	TestTrue(TEXT("Opening restores sound, without rebaking walls"),Distance[End]<CatrunSoundPropagation::Unreached);
	TestTrue(TEXT("Opening restores armor route"),CatrunArmorPath::FindPath(G,G.CellCenter(Start),G.CellCenter(End),Params,Corners));
	return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FStatueSeatThresholdTest,"Catrun.Stage2.SeatingThresholdAxisHeightAndBlockedSweep",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FStatueSeatThresholdTest::RunTest(const FString&)
{
	FStatueFixture F;
	F.Cat->SetActorLocation(FVector(800,0,26));
	F.Statue->SetActorLocation(FVector(0,170.9,0));
	TestTrue(TEXT("Footprint overlap is just below eighty percent"),F.Puzzle->GetSeatingOverlap(0)<.8f);
	F.Puzzle->UpdatePlatesAndGates(0);
	TestFalse(TEXT("Below-threshold contact cannot seat"),F.Puzzle->Links[0].bPressed);
	F.Statue->SetActorLocation(FVector(29,200,0));
	TestTrue(TEXT("Sideways contact has eighty percent overlap"),FMath::IsNearlyEqual(F.Puzzle->GetSeatingOverlap(0),.8f));
	F.Puzzle->UpdatePlatesAndGates(0);
	TestFalse(TEXT("Wrong socket axis cannot seat"),F.Puzzle->Links[0].bPressed);
	F.Statue->SetActorLocation(FVector(0,200,20));
	F.Puzzle->UpdatePlatesAndGates(0);
	TestFalse(TEXT("Different height cannot seat"),F.Puzzle->Links[0].bPressed);
	F.Statue->SetActorLocation(FVector(0,171,0));
	AActor* Wall=F.Box(FVector(0,252,75),FVector(70,2,75));
	F.Puzzle->UpdatePlatesAndGates(0);
	TestFalse(TEXT("A thin blocker in the snap sweep prevents seating"),F.Puzzle->Links[0].bPressed);
	TestTrue(TEXT("Blocked snap leaves exact previous transform"),F.Statue->GetActorLocation().Equals(FVector(0,171,0)));
	Wall->Destroy();
	F.Statue->SetActorLocation(FVector(0,229,0));
	F.Cat->SetActorLocation(FVector(0,141,26));
	F.Puzzle->UpdatePlatesAndGates(0);
	TestFalse(TEXT("Backward snap cannot overlap the pushing cat"),F.Puzzle->Links[0].bPressed);
	TestTrue(TEXT("Pawn-blocked snap preserves position"),F.Statue->GetActorLocation().Equals(FVector(0,229,0)));
	F.Cat->SetActorLocation(FVector(800,0,26));
	F.Statue->SetActorLocation(FVector(0,171,0));
	auto* Probe=NewObject<UCatrunPuzzleCallbackProbe>(F.Puzzle); Probe->Puzzle=F.Puzzle;
	F.Puzzle->OnPuzzleEvent.AddDynamic(Probe,&UCatrunPuzzleCallbackProbe::PuzzleEvent);
	F.Puzzle->UpdatePlatesAndGates(0);
	TestTrue(TEXT("Exact eighty percent seats"),F.Puzzle->Links[0].bPressed);
	TestTrue(TEXT("Seat is exact socket center"),F.Statue->GetActorLocation().Equals(FVector(0,200,0)));
	F.Puzzle->UpdatePlatesAndGates(10);
	F.Puzzle->UpdatePlatesAndGates(10);
	TestEqual(TEXT("Snap event happens once"),Probe->Counts[0],1);
	TestEqual(TEXT("Seat event happens once"),Probe->Counts[1],1);
	TestEqual(TEXT("Gate-opening event happens once"),Probe->Counts[2],1);
	TestEqual(TEXT("Completion event happens once"),Probe->Counts[3],1);
	TestFalse(TEXT("Latched statue rejects further pushing"),F.Puzzle->TryPushStatue(0,F.Cat,FVector::RightVector,1));
	TArray<FBox> Obstacles; F.Puzzle->GetObstacleBounds(Obstacles);
	TestEqual(TEXT("Fully recessed gate leaves only statue in routing obstacles"),Obstacles.Num(),1);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FStatueSeatAfterCrossAxisCoastTest,
	"Catrun.Stage2.SeatsAfterCrossAxisCoast", EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FStatueSeatAfterCrossAxisCoastTest::RunTest(const FString&)
{
	FStatueFixture F;
	F.Cat->SetActorLocation(FVector(800,0,26));
	const auto& Link = F.Puzzle->Links[0];
	// Use the measured B statue and plate offsets, with the final push on the fixture's Y axis.
	const FVector ObservedOffset(1050.289 - 1070., 398.988 - 410., 0.);
	F.Statue->SetActorLocation(Link.SeatLocation + ObservedOffset);
	TestTrue(TEXT("Observed footprint overlap is 83.345 percent"),
		FMath::IsNearlyEqual(F.Puzzle->GetSeatingOverlap(0), .8334502f, .0001f));

	F.Puzzle->UpdatePlatesAndGates(0);
	TestTrue(TEXT("An eligible statue seats after coasting across the socket axis"), Link.bPressed);
	TestTrue(TEXT("Seating centers the statue exactly"), F.Statue->GetActorLocation().Equals(Link.SeatLocation));
	F.Puzzle->UpdatePlatesAndGates(10);
	TestTrue(TEXT("The connected gate finishes opening"), Link.bCompleted);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FStatueWeightTest,"Catrun.Stage2.WeightedPushIsFrameIndependentAndDecelerates",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FStatueWeightTest::RunTest(const FString&)
{
	auto Simulate=[this](int32 Frames)
	{
		FStatueFixture F;
		for (int32 N=0;N<Frames;++N)
		{
			F.Cat->SetActorLocation(F.Statue->GetActorLocation()+FVector(0,-88,26));
			TestTrue(TEXT("Continuous contact can push"),F.Puzzle->TryPushStatue(0,F.Cat,FVector::RightVector,1.f/Frames));
		}
		const double Driven=F.Statue->GetActorLocation().Y;
		F.Cat->SetActorLocation(FVector(800,0,26));
		for (int32 N=0;N<Frames;++N) F.Puzzle->Tick(1.f/Frames);
		TestTrue(TEXT("Released statue stops"),F.Puzzle->Links[0].PushVelocity.IsNearlyZero());
		TestTrue(TEXT("Deceleration adds the physical stopping distance"),FMath::IsNearlyEqual(float(F.Statue->GetActorLocation().Y-Driven),10000.f/480.f,.01f));
		return Driven;
	};
	const double At30=Simulate(30), At120=Simulate(120);
	TestTrue(TEXT("30 and 120Hz travel agree"),FMath::Abs(At30-At120)<.01);
	TestTrue(TEXT("One second includes acceleration then capped cruise"),FMath::Abs(At30-68.75)<.01);
	float Speed=0;
	TestTrue(TEXT("A long frame integrates the full duration"),FMath::IsNearlyEqual(ACatrunStatuePuzzle::IntegratePushSpeed(Speed,100,160,1),68.75f));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FStatueGateRecessTest,"Catrun.Stage2.GateUsesActualHeightAndChecksBothDirections",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FStatueGateRecessTest::RunTest(const FString&)
{
	FStatueFixture F(500);
	F.Cat->SetActorLocation(FVector(800,0,26));
	TestEqual(TEXT("Tall gate derives height plus clearance"),F.Puzzle->Links[0].RequiredGateTravel,504.f);
	F.Statue->SetActorLocation(FVector(0,200,0));
	AActor* Blocker=F.Box(FVector(500,0,40),FVector(10,10,20));
	F.Puzzle->UpdatePlatesAndGates(10);
	TestTrue(TEXT("Seat latches even if gate is blocked"),F.Puzzle->Links[0].bPressed);
	TestEqual(TEXT("Dynamic blocker stops downward travel"),F.Puzzle->Links[0].GateOffset,0.f);
	TestTrue(TEXT("Visible blocked gate retains collision"),F.Gate->GetActorEnableCollision());
	Blocker->Destroy();
	F.Puzzle->UpdatePlatesAndGates(10);
	TestEqual(TEXT("Authored dynamic floor does not veto sinking"),F.Puzzle->Links[0].GateOffset,-504.f);
	TestTrue(TEXT("Tall gate top clears floor by configured margin"),FMath::IsNearlyEqual(float(F.Gate->GetComponentsBoundingBox(true).Max.Z),-4.f));
	F.Cat->SetActorLocation(FVector(500,0,26));
	TestTrue(TEXT("Reset can restore statue while doorway is occupied"),F.Puzzle->ResetPuzzle());
	F.Puzzle->UpdatePlatesAndGates(10);
	TestEqual(TEXT("Upward return remains blocked until pawn leaves"),F.Puzzle->Links[0].GateOffset,-504.f);
	F.Cat->SetActorLocation(FVector(800,0,26));
	F.Puzzle->UpdatePlatesAndGates(10);
	TestEqual(TEXT("Gate returns to authored transform after clearance"),F.Puzzle->Links[0].GateOffset,0.f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FStatueCallbackTest,"Catrun.Stage2.SnapCallbackResetCancelsOldRevision",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FStatueCallbackTest::RunTest(const FString&)
{
	FStatueFixture F;
	F.Cat->SetActorLocation(FVector(800,0,26));
	auto* Probe=NewObject<UCatrunPuzzleCallbackProbe>(F.Puzzle); Probe->Puzzle=F.Puzzle; Probe->bResetOnSnap=true;
	F.Puzzle->OnPuzzleEvent.AddDynamic(Probe,&UCatrunPuzzleCallbackProbe::PuzzleEvent);
	F.Statue->SetActorLocation(FVector(0,171,0));
	F.Puzzle->UpdatePlatesAndGates(10);
	TestFalse(TEXT("Reset from SnapStarted prevents old stack seating"),F.Puzzle->Links[0].bPressed);
	TestEqual(TEXT("Reset invalidates presentation revision"),F.Puzzle->Links[0].Revision,1);
	TestEqual(TEXT("No stale seated event"),Probe->Counts[1],0);
	TestEqual(TEXT("No stale gate-opening event"),Probe->Counts[2],0);
	TestTrue(TEXT("Reset restores exact authored transform"),F.Statue->GetActorTransform().Equals(F.Puzzle->Links[0].InitialStatue));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FStatueRevealTest,"Catrun.Stage2.RevealTimeoutResetCallbacksAndOwnedLocks",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FStatueRevealTest::RunTest(const FString&)
{
	FStatueFixture F;
	auto* PC=F.AddPlayer(); F.Cat->SetActorLocation(FVector(800,0,26));
	PC->SetIgnoreMoveInput(true); PC->SetIgnoreLookInput(true);
	auto* R=F.Puzzle->Reveal.Get();
	TestTrue(TEXT("Native reveal starts without BP effects"),R->BeginReveal(TEXT("Test"),F.Gate,F.Puzzle->Links[0].InitialGateBounds));
	TestTrue(TEXT("Owned action blocker is on controller stack"),R->InputBlocker && PC->IsInputComponentInStack(R->InputBlocker));
	UInputComponent* OwnedBlocker=R->InputBlocker;
	TestTrue(TEXT("Action blocker consumes lower priority BP input"),OwnedBlocker && OwnedBlocker->bBlockInput && OwnedBlocker->Priority==MAX_int32);
	const int32 OldSession=R->SessionId;
	TestTrue(TEXT("Hostiles suspend for reveal"),UCatrunPuzzleSuspension::IsSuspended(F.Puzzle));
	TestFalse(TEXT("Gate waits for camera"),R->CanOpenGate(TEXT("Test")));
	R->NotifyCameraAtGate(OldSession-1);
	TestEqual(TEXT("Stale callback is ignored"),R->Phase,ECatrunPuzzleRevealPhase::ToGate);
	R->TickComponent(20,LEVELTICK_All,nullptr);
	TestEqual(TEXT("Missing BP or blocked gate cannot trap input"),R->Phase,ECatrunPuzzleRevealPhase::Inactive);
	TestFalse(TEXT("Timeout releases suspension"),UCatrunPuzzleSuspension::IsSuspended(F.Puzzle));
	TestFalse(TEXT("Timeout removes its exact input component"),PC->IsInputComponentInStack(OwnedBlocker));
	TestTrue(TEXT("Unrelated move lock is preserved"),PC->IsMoveInputIgnored());
	TestTrue(TEXT("Unrelated look lock is preserved"),PC->IsLookInputIgnored());
	PC->SetIgnoreMoveInput(false); PC->SetIgnoreLookInput(false);
	TestFalse(TEXT("Exactly one reveal move lock was removed"),PC->IsMoveInputIgnored());
	TestTrue(TEXT("Original view restored"),PC->GetViewTarget()==F.Cat);
	R->BeginReveal(TEXT("Test"),F.Gate,F.Puzzle->Links[0].InitialGateBounds);
	AActor* NewView=F.World->SpawnActor<ACameraActor>(); PC->SetViewTarget(NewView);
	R->TickComponent(.01f,LEVELTICK_All,nullptr);
	TestTrue(TEXT("External view takeover is preserved"),PC->GetViewTarget()==NewView);
	TestFalse(TEXT("Takeover still releases own input lock"),PC->IsMoveInputIgnored());
	PC->SetViewTarget(F.Cat);
	auto* Probe=NewObject<UCatrunPuzzleCallbackProbe>(F.Puzzle); Probe->Puzzle=F.Puzzle; Probe->bCancelOnFraming=true;
	R->OnPhaseChanged.AddDynamic(Probe,&UCatrunPuzzleCallbackProbe::RevealEvent);
	TestFalse(TEXT("Framing listener can cancel synchronously"),R->BeginReveal(TEXT("Test"),F.Gate,F.Puzzle->Links[0].InitialGateBounds));
	TestFalse(TEXT("Callback cleanup releases input"),PC->IsMoveInputIgnored());
	TestFalse(TEXT("Callback cleanup releases suspension"),UCatrunPuzzleSuspension::IsSuspended(F.Puzzle));
	Probe->bCancelOnFraming=false;
	R->BeginReveal(TEXT("Test"),F.Gate,F.Puzzle->Links[0].InitialGateBounds);
	TestTrue(TEXT("Room reset succeeds during scripted reveal"),F.Puzzle->ResetStatue(TEXT("Test")));
	TestEqual(TEXT("Reset cancels reveal"),R->Phase,ECatrunPuzzleRevealPhase::Inactive);
	R->BeginReveal(TEXT("Test"),F.Gate,F.Puzzle->Links[0].InitialGateBounds);
	F.World->GetSubsystem<UCatrunLevelFlowSubsystem>()->bStageComplete=true;
	R->TickComponent(.01f,LEVELTICK_All,nullptr);
	TestEqual(TEXT("Stage completion takes precedence"),R->Phase,ECatrunPuzzleRevealPhase::Inactive);
	TestFalse(TEXT("Completion restores own input"),PC->IsMoveInputIgnored());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunPuzzleSuspensionTest,"Catrun.Stage2.SuspensionGuardsEventsTimersAndPlayerActions",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FCatrunPuzzleSuspensionTest::RunTest(const FString&)
{
	FStatueFixture F; F.AddPlayer();
	FActorSpawnParameters Spawn; Spawn.SpawnCollisionHandlingOverride=ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	auto* Armor=F.World->SpawnActor<ACatrunArmor>(FVector(300,300,100),FRotator::ZeroRotator,Spawn);
	if (!TestNotNull(TEXT("Suspension fixture armor exists"),Armor)) return false;
	auto* Candle=F.World->SpawnActor<ACatrunCandle>();
	auto* Door=F.World->SpawnActor<ACatrunDoor>();
	Door->SetOpen(true);
	Door->TickActor(.2f,LEVELTICK_All,Door->PrimaryActorTick);
	auto* Leaf=Door->FindComponentByClass<UStaticMeshComponent>();
	const FRotator DoorRotation=Leaf->GetRelativeRotation();
	auto* Manager=F.World->SpawnActor<ASoundGridManager>();
	auto* SoundSettings=NewObject<UCatrunSoundSettings>(Manager);
	FindFProperty<FObjectPropertyBase>(ASoundGridManager::StaticClass(),TEXT("Settings"))->SetObjectPropertyValue_InContainer(Manager,SoundSettings);
	auto& Grid=const_cast<FCatrunGridData&>(Manager->GetGrid());
	Grid.Origin=FVector(-2000,-2000,0); Grid.CellSize=25; Grid.Width=Grid.Height=160;
	Grid.Walkable.Init(1,Grid.NumCells()); Grid.EdgeMask.Init(255,Grid.NumCells());
	Grid.WallDistance.Init(1000.f,Grid.NumCells()); Grid.CostMultiplier.Init(1.f,Grid.NumCells());
	Armor->SoundManager=Manager;
	Armor->Action=EArmorAction::OpeningDoor; Armor->ActionTime=.25f;
	Armor->MarkRepathTimer=.18f;
	Armor->GetCharacterMovement()->SetComponentTickEnabled(true);
	Armor->GetCharacterMovement()->Velocity=FVector(100,0,0);
	Candle->PauseLeft=.7f; Candle->ReactTimeLeft=.4f;
	auto* Marks=F.World->GetSubsystem<UCatrunMarkSubsystem>();
	Marks->FollowTimer=.2f;
	auto* Guard=F.World->GetSubsystem<UCatrunPuzzleSuspension>();
	TestTrue(TEXT("First reveal owns suspension"),Guard->Acquire(F.Puzzle));
	TestFalse(TEXT("Second owner cannot overlap reveal"),Guard->Acquire(F.Gate));
	TestFalse(TEXT("Movement component is frozen"),Armor->GetCharacterMovement()->IsComponentTickEnabled());
	TestTrue(TEXT("Armor animation is frozen"),Armor->GetMesh()->bPauseAnims);
	FCatrunSoundEvent Sound; Sound.Location=FVector(1000,0,0); Sound.Size=ECatrunSoundSize::Large;
	Armor->OnSoundHeard_Implementation(Sound,1000);
	Armor->SetFollowingMark(true); Armor->StartCatch(*F.Cat); Armor->Tick(20);
	Door->TickActor(20,LEVELTICK_All,Door->PrimaryActorTick);
	TestTrue(TEXT("Independent door leaf timeline is frozen too"),Leaf->GetRelativeRotation().Equals(DoorRotation));
	TestFalse(TEXT("Direct capture acquisition is rejected too"),F.World->GetSubsystem<UCatrunRestartSubsystem>()->TryBeginCatch());
	Candle->CheckForCat(20,F.Cat,*SoundSettings); Candle->StartTracking(*F.Cat,*SoundSettings); Candle->Tick(20);
	Marks->ApplyMark(*F.Cat); Marks->UpdateFollowingArmor(*F.Cat); Marks->Tick(20);
	TestFalse(TEXT("Sound callback cannot alter investigation"),Armor->IsInvestigatingSound());
	TestFalse(TEXT("Mark callback cannot acquire pursuit"),Armor->IsFollowingMark());
	TestEqual(TEXT("Capture callback cannot acquire cat"),Armor->GetAction(),EArmorAction::OpeningDoor);
	TestEqual(TEXT("Door/action timeline retains elapsed time"),Armor->ActionTime,.25f);
	TestEqual(TEXT("Mark repath timer retains remaining time"),Armor->MarkRepathTimer,.18f);
	TestEqual(TEXT("Candle sweep timer retains remaining time"),Candle->PauseLeft,.7f);
	TestEqual(TEXT("Candle reaction timer retains remaining time"),Candle->ReactTimeLeft,.4f);
	TestFalse(TEXT("Candle discovery callback is suppressed"),Candle->IsTrackingCat());
	TestFalse(TEXT("Direct mark application is suppressed"),Marks->IsMarked());
	TestEqual(TEXT("Mark selection timer retains remaining time"),Marks->FollowTimer,.2f);
	TestFalse(TEXT("Global world is not paused"),F.World->IsPaused());
	auto* Recovery=F.World->SpawnActor<ACatrunPuzzleReset>(); Recovery->Puzzle=F.Puzzle; Recovery->PuzzleId=TEXT("Test"); Recovery->SetActorLocation(F.Cat->GetActorLocation());
	TestFalse(TEXT("Recovery input is rejected during reveal"),Recovery->TryUse(F.Cat));
	auto* Basket=NewObject<UCatrunBasketInteractionComponent>(F.Cat); Basket->RegisterComponent(); Basket->CatOwner=F.Cat;
	Basket->BasketPhase=ECatrunBasketPhase::Hidden; Basket->TryInteract();
	TestEqual(TEXT("Basket direct input cannot leave hidden state"),Basket->BasketPhase,ECatrunBasketPhase::Hidden);
	Basket->BasketPhase=ECatrunBasketPhase::Outside;
	auto* Bell=NewObject<UCatrunBellComponent>(F.Cat); Bell->RegisterComponent();
	auto* Probe=NewObject<UCatrunPuzzleCallbackProbe>(F.Puzzle);
	Manager->OnSoundEmitted.AddDynamic(Probe,&UCatrunPuzzleCallbackProbe::SoundEvent);
	TestFalse(TEXT("Direct bell input is rejected"),Bell->TryRing());
	Bell->ProcessEvent(Bell->FindFunction(TEXT("HandleBellRung")),nullptr);
	TestEqual(TEXT("Delayed bell dispatcher emits nothing"),Probe->SoundCount,0);
	Guard->Release(F.Gate);
	TestTrue(TEXT("Unrelated release cannot unlock hostiles"),UCatrunPuzzleSuspension::IsSuspended(F.Puzzle));
	Guard->Release(F.Puzzle);
	Door->TickActor(.2f,LEVELTICK_All,Door->PrimaryActorTick);
	TestFalse(TEXT("Door leaf resumes from preserved angle"),Leaf->GetRelativeRotation().Equals(DoorRotation));
	TestTrue(TEXT("Bell actually works again after suspension"),Bell->TryRing());
	TestEqual(TEXT("Positive control broadcasts a real bell event"),Probe->SoundCount,1);
	TestTrue(TEXT("Owned movement tick is restored"),Armor->GetCharacterMovement()->IsComponentTickEnabled());
	TestTrue(TEXT("Movement velocity survives suspension"),Armor->GetCharacterMovement()->Velocity.Equals(FVector(100,0,0)));
	TestFalse(TEXT("Owned animation pause is restored"),Armor->GetMesh()->bPauseAnims);
	Armor->GetCharacterMovement()->SetComponentTickEnabled(false); Armor->GetMesh()->bPauseAnims=true;
	Guard->Acquire(F.Puzzle); Guard->Release(F.Puzzle);
	TestFalse(TEXT("Previously disabled movement is preserved"),Armor->GetCharacterMovement()->IsComponentTickEnabled());
	TestTrue(TEXT("Previously paused animation is preserved"),Armor->GetMesh()->bPauseAnims);
	return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FStatueBusySeatTest,"Catrun.Stage2.CoastingBusySeatWaitsThenRevealsExactlyOnce",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FStatueBusySeatTest::RunTest(const FString&)
{
	FStatueFixture F; auto* PC=F.AddPlayer();
	TestTrue(TEXT("A player push starts the coast"),F.Puzzle->TryPushStatue(0,F.Cat,FVector::RightVector,.05f));
	F.Cat->SetActorLocation(FVector(800,0,26));
	auto* Actions=NewObject<UCatrunBasketInteractionComponent>(F.Cat); Actions->RegisterComponent(); Actions->CatOwner=F.Cat; Actions->Busy=true;
	auto* Probe=NewObject<UCatrunPuzzleCallbackProbe>(F.Puzzle); Probe->Puzzle=F.Puzzle;
	F.Puzzle->OnPuzzleEvent.AddDynamic(Probe,&UCatrunPuzzleCallbackProbe::PuzzleEvent);
	auto& Link=F.Puzzle->Links[0]; auto* R=F.Puzzle->Reveal.Get();
	F.Statue->SetActorLocation(FVector(0,170.9,0)); Link.PushVelocity=FVector(0,100,0);
	F.Puzzle->Tick(.02f); // actual friction crosses threshold while the action remains Busy
	TestTrue(TEXT("Coasting crosses threshold and seats exactly"),Link.bPressed && F.Statue->GetActorLocation().Equals(Link.SeatLocation));
	TestTrue(TEXT("Rejected acquisition is retained"),Link.bRevealPending);
	TestEqual(TEXT("Busy action keeps gate shut"),Link.GateOffset,0.f);
	TestEqual(TEXT("No reveal begins over legitimate bell"),R->SessionId,0);
	TestFalse(TEXT("Waiting does not take input lock"),PC->IsMoveInputIgnored());
	for(int32 I=0;I<10;++I) F.Puzzle->UpdatePlatesAndGates(1);
	TestEqual(TEXT("Waiting cannot silently time out into gate opening"),Link.GateOffset,0.f);
	TestEqual(TEXT("Seat event is not repeated while waiting"),Probe->Counts[1],1);
	Actions->Busy=false; F.Puzzle->UpdatePlatesAndGates(.1f);
	TestFalse(TEXT("Request is consumed on acquisition"),Link.bRevealPending);
	TestEqual(TEXT("One reveal starts after Busy ends"),R->SessionId,1);
	TestEqual(TEXT("Camera travels before gate opens"),R->Phase,ECatrunPuzzleRevealPhase::ToGate);
	TestEqual(TEXT("Gate still waits for camera"),Link.GateOffset,0.f);
	R->TickComponent(1,LEVELTICK_All,nullptr); F.Puzzle->UpdatePlatesAndGates(3);
	TestEqual(TEXT("Downward gate reaches exact recess"),Link.GateOffset,-Link.RequiredGateTravel);
	TestEqual(TEXT("Camera returns"),R->Phase,ECatrunPuzzleRevealPhase::Returning);
	R->TickComponent(1,LEVELTICK_All,nullptr); F.Puzzle->UpdatePlatesAndGates(10);
	TestEqual(TEXT("Exactly one complete reveal session"),R->SessionId,1);
	for(int32 I=0;I<4;++I) TestEqual(TEXT("Each solve event happens exactly once"),Probe->Counts[I],1);
	TestFalse(TEXT("Controls return after deferred presentation"),PC->IsMoveInputIgnored() || PC->IsLookInputIgnored());
	TestFalse(TEXT("Suspension is released"),UCatrunPuzzleSuspension::IsSuspended(F.Puzzle));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FStatuePendingResetTest,"Catrun.Stage2.PendingRevealResetAndMissingPresentationFallback",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FStatuePendingResetTest::RunTest(const FString&)
{
	FStatueFixture F; F.AddPlayer(); F.Cat->SetActorLocation(FVector(800,0,26));
	auto* Actions=NewObject<UCatrunBasketInteractionComponent>(F.Cat); Actions->RegisterComponent(); Actions->Busy=true;
	auto& Link=F.Puzzle->Links[0]; auto* R=F.Puzzle->Reveal.Get();
	F.Statue->SetActorLocation(FVector(0,171,0)); F.Puzzle->UpdatePlatesAndGates(1);
	TestTrue(TEXT("Fixture has pending solve"),Link.bRevealPending);
	TestTrue(TEXT("Reset cancels a pending solve"),F.Puzzle->ResetStatue(TEXT("Test")));
	Actions->Busy=false; F.Puzzle->UpdatePlatesAndGates(10);
	TestFalse(TEXT("No stale pending request survives reset"),Link.bRevealPending || Link.bPressed);
	TestEqual(TEXT("Reset cannot start stale presentation"),R->SessionId,0);
	R->bEnabled=false; F.Statue->SetActorLocation(FVector(0,171,0)); F.Puzzle->UpdatePlatesAndGates(3);
	TestTrue(TEXT("Explicitly disabled presentation retains gameplay fallback"),Link.bCompleted);
	TestFalse(TEXT("Missing presentation does not retain an unbounded request"),Link.bRevealPending);
	F.Puzzle->ResetPuzzle(); R->bEnabled=true; F.Statue->SetActorLocation(FVector(0,171,0)); F.Puzzle->UpdatePlatesAndGates(0);
	R->TickComponent(20,LEVELTICK_All,nullptr); F.Puzzle->UpdatePlatesAndGates(3);
	TestTrue(TEXT("Accepted reveal missing callbacks retains bounded fallback"),Link.bCompleted);
	return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FStage3ExternalGateTest,"Catrun.Stage3.ExternalLocksPreserveSeatingAndGateSafety",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FStage3ExternalGateTest::RunTest(const FString&)
{
	FStatueFixture F;
	F.Puzzle->Reveal->bEnabled=false;
	auto& Link=F.Puzzle->Links[0];
	TestTrue(TEXT("Existing maps default to unlocked"),Link.bExternalGateUnlocked);
	Link.bExternalGateUnlocked=false;
	F.Statue->SetActorLocation(FVector(0,200,0));
	F.Puzzle->UpdatePlatesAndGates(10.f);
	TestTrue(TEXT("A locked puzzle still latches the seated statue"),Link.bPressed);
	TestFalse(TEXT("Seating alone cannot finish the locked gate"),Link.bCompleted);
	TestEqual(TEXT("External lock keeps the gate shut"),Link.GateOffset,0.f);
	Link.bExternalGateUnlocked=true;
	F.Puzzle->UpdatePlatesAndGates(10.f);
	TestTrue(TEXT("Releasing the locks opens an already seated puzzle"),Link.bCompleted);
	TestTrue(TEXT("Normal safe downward travel is preserved"),Link.GateOffset<=-280.f);
	return true;
}
#endif
