#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Interaction/BasketExitMath.h"
#include "Interaction/CatrunHideBasket.h"
#include "Components/SceneComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "Engine/Engine.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "PhysicsEngine/BodySetup.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/PlayerInput.h"
#include "InputKeyEventArgs.h"
#include "Interaction/CatrunBasketInteractionComponent.h"
#include "Perception/CatrunSafeRestore.h"
#include "Perception/CatrunGroundSupport.h"
#include "Settings/CatrunInputBindings.h"
#include "Settings/CatrunUserSettings.h"
#include "Interaction/CatrunPuzzleSuspension.h"

namespace
{
	struct FBasketCollisionFixture
	{
		UWorld* World;
		ACharacter* Cat;
		APlayerController* PC;
		ACatrunHideBasket* Basket;
		UCatrunBasketInteractionComponent* Actions;
		AActor* Floor;
		FBasketCollisionFixture()
		{
			const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false)
				.CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false);
			World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
			GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
			World->InitializeActorsForPlay(FURL());
			Floor = Box(FVector(0,0,-10), FVector(500,500,10));
			FActorSpawnParameters Spawn;
			Spawn.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
			Cat = World->SpawnActor<ACharacter>(FVector(200,0,100), FRotator::ZeroRotator, Spawn);
			Cat->GetCapsuleComponent()->SetCapsuleSize(20.f,24.f);
			Cat->SetActorLocation(FVector(200,0,26));
			PC = World->SpawnActor<APlayerController>();
			PC->Possess(Cat);
			// Possession restarts a Character and resets its default movement mode.
			Cat->GetCharacterMovement()->SetMovementMode(MOVE_Flying);
			PC->PlayerInput = NewObject<UPlayerInput>(PC);
			if (!PC->PlayerCameraManager) PC->PlayerCameraManager = World->SpawnActor<APlayerCameraManager>();
			FMinimalViewInfo View;
			View.Rotation = FRotator(-55,-135,0);
			PC->PlayerCameraManager->SetCameraCachePOV(View);
			Basket = World->SpawnActor<ACatrunHideBasket>();
			auto* Root = NewObject<USceneComponent>(Basket);
			Basket->SetRootComponent(Root);
			Root->RegisterComponent();
			Basket->SetActorLocation(FVector(0,0,26));
			Basket->OpenDirectionLocal = FVector(-1,1,0);
			Actions = NewObject<UCatrunBasketInteractionComponent>(Cat);
			Actions->RegisterComponent();
			Actions->CatOwner = Cat;
			Actions->EnterAnimation = nullptr;
			Actions->ExitAnimation = nullptr;
		}
		~FBasketCollisionFixture()
		{
			GEngine->DestroyWorldContext(World);
			World->DestroyWorld(false);
		}
		AActor* Box(const FVector& Location, const FVector& Extent)
		{
			auto* Actor = World->SpawnActor<AActor>();
			auto* Shape = NewObject<UBoxComponent>(Actor);
			Actor->SetRootComponent(Shape);
			Shape->SetBoxExtent(Extent);
			Shape->SetCollisionProfileName(TEXT("BlockAllDynamic"));
			Shape->RegisterComponent();
			Actor->SetActorLocation(Location);
			return Actor;
		}
		AActor* MeshFloor(UStaticMesh* Mesh, const FVector& Location)
		{
			Mesh->GetBodySetup()->CreatePhysicsMeshes();
			auto* Actor = World->SpawnActor<AActor>();
			auto* Shape = NewObject<UStaticMeshComponent>(Actor);
			Actor->SetRootComponent(Shape);
			Shape->SetStaticMesh(Mesh);
			Shape->SetCollisionProfileName(TEXT("BlockAll"));
			Actor->SetActorLocation(Location);
			Shape->RegisterComponent();
			return Actor;
		}
		bool SweepCapsule(FHitResult& Hit, const FVector& From, const FVector& To, const FCollisionQueryParams& Params) const
		{
			const auto* Capsule = Cat->GetCapsuleComponent();
			return World->SweepSingleByChannel(Hit, From, To, Capsule->GetComponentQuat(), Capsule->GetCollisionObjectType(),
				Capsule->GetCollisionShape(), Params, FCollisionResponseParams(Capsule->GetCollisionResponseToChannels()));
		}
		void Keys(std::initializer_list<FKey> Pressed)
		{
			PC->PlayerInput->FlushPressedKeys();
			for (const FKey Key : Pressed)
				PC->PlayerInput->InputKey(FInputKeyEventArgs(nullptr, INPUTDEVICEID_NONE, Key, IE_Pressed, 1.f, false, 0));
			PC->PlayerInput->ProcessInputStack(TArray<UInputComponent*>(), .016f, false);
		}
	};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunCapsuleGroundSupportTest, "Catrun.Basket.CommonCapsuleSupportSafety",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunCapsuleGroundSupportTest::RunTest(const FString&)
{
	FBasketCollisionFixture F;
	auto* Capsule = F.Cat->GetCapsuleComponent();
	FCollisionQueryParams Params(SCENE_QUERY_STAT(CapsuleSupportRegression), false, F.Cat);
	FHitResult Hit;
	FVector Center;
	const FVector Reference(0,0,26);
	TestTrue(TEXT("Actual capsule finds supported center at unchanged XY"),
		CatrunGround::FindSupport(*Capsule, Reference, 50, 100, Params, Hit, Center) && Center.Equals(Reference,.01));
	TestFalse(TEXT("Support outside the bounded center sweep is rejected"),
		CatrunGround::FindSupport(*Capsule, Reference, 0, 1, Params, Hit, Center));
	auto* FloorShape = Cast<UBoxComponent>(F.Floor->GetRootComponent());
	FloorShape->SetCollisionObjectType(ECC_WorldStatic);
	FloorShape->SetCollisionResponseToChannel(ECC_Pawn,ECR_Ignore);
	FloorShape->SetCollisionResponseToChannel(ECC_PhysicsBody,ECR_Block);
	Capsule->SetCollisionObjectType(ECC_PhysicsBody);
	TestTrue(TEXT("Support uses actual capsule object channel rather than a Pawn profile"),
		CatrunGround::FindSupport(*Capsule, Reference, 50, 100, Params, Hit, Center));
	Capsule->SetCollisionResponseToChannel(ECC_WorldStatic,ECR_Ignore);
	TestFalse(TEXT("Actual custom capsule response can exclude otherwise blocking floor"),
		CatrunGround::FindSupport(*Capsule, Reference, 50, 100, Params, Hit, Center));
	Capsule->SetCollisionObjectType(ECC_Pawn);
	Capsule->SetCollisionResponseToChannel(ECC_WorldStatic,ECR_Block);
	Capsule->SetCollisionResponseToChannel(ECC_Pawn,ECR_Block);
	FloorShape->SetCollisionResponseToChannel(ECC_Pawn,ECR_Block);
	FActorSpawnParameters Spawn; Spawn.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	auto* PawnFloor = F.World->SpawnActor<ACharacter>(FVector(0,0,50),FRotator::ZeroRotator,Spawn);
	PawnFloor->GetCapsuleComponent()->SetCapsuleSize(30,30);
	PawnFloor->GetCapsuleComponent()->SetCollisionResponseToAllChannels(ECR_Block);
	TestFalse(TEXT("A Pawn cannot become walkable support or be searched through for floor below"),
		CatrunGround::FindSupport(*Capsule,FVector(0,0,120),50,150,Params,Hit,Center));
	TestTrue(TEXT("No-Pawn rejection exercised an actual Pawn support hit"),Hit.GetActor()==PawnFloor);
	PawnFloor->Destroy();
	auto* Penetrating = F.Box(FVector(0,0,76),FVector(30,30,30));
	TestFalse(TEXT("Initial sweep penetration cannot enable support"),
		CatrunGround::FindSupport(*Capsule,Reference,50,100,Params,Hit,Center));
	TestTrue(TEXT("Penetration fixture actually starts inside geometry"),Hit.bStartPenetrating);
	Penetrating->Destroy();
	F.Floor->Destroy();
	auto* Steep = F.Box(FVector::ZeroVector,FVector(500,500,5));
	Steep->SetActorRotation(FRotator(60,0,0));
	TestFalse(TEXT("Wholly steep support cannot enable a landing"),
		CatrunGround::FindSupport(*Capsule,Reference,50,100,Params,Hit,Center));
	TestTrue(TEXT("Steep rejection exercises a real nonpenetrating sloped hit"),
		Hit.IsValidBlockingHit() && Hit.ImpactNormal.Z<.65f);
	Steep->Destroy();
	auto* Movement = F.Cat->GetCharacterMovement();
	Movement->SetWalkableFloorZ(.71f);
	auto* MarginalSlope = F.Box(FVector::ZeroVector,FVector(500,500,5));
	MarginalSlope->SetActorRotation(FRotator(47,0,0));
	const bool bAcceptsMarginalSlope = CatrunGround::FindSupport(*Capsule,Reference,50,100,Params,Hit,Center);
	TestTrue(TEXT("Actual nonpenetrating face meets the shared .65 threshold but not the movement limit"),
		Hit.IsValidBlockingHit() && Hit.GetActor()==MarginalSlope && Hit.ImpactNormal.Z>=.65f && Hit.ImpactNormal.Z<.71f
		&& !Movement->IsWalkable(Hit));
	TestFalse(TEXT("A slope the owner cannot walk on cannot support a landing"), bAcceptsMarginalSlope);
	Movement->SetWalkableFloorZ(.65f);
	TestTrue(TEXT("The same face supports a character whose movement can walk on it"),
		CatrunGround::FindSupport(*Capsule,Reference,50,100,Params,Hit,Center) && Movement->IsWalkable(Hit));
	MarginalSlope->Destroy();
	TestFalse(TEXT("Absent floor is rejected"),CatrunGround::FindSupport(*Capsule,Reference,50,100,Params,Hit,Center));
	F.Box(FVector(-100,0,-10),FVector(50,100,10));
	F.Box(FVector(100,0,-10),FVector(50,100,10));
	TestFalse(TEXT("A real opening wider than the capsule footprint is not bridged"),
		CatrunGround::FindSupport(*Capsule,Reference,50,100,Params,Hit,Center));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunBasketComplexSupportTest, "Catrun.Basket.ComplexFloorEntryExitAndOrigin",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunBasketComplexSupportTest::RunTest(const FString&)
{
	FBasketCollisionFixture F;
	auto* Mesh = LoadObject<UStaticMesh>(nullptr,TEXT("/Game/Environment/Stage1/Meshes/Floors/SM_Stage01_Floor_Storage.SM_Stage01_Floor_Storage"));
	if (!TestNotNull(TEXT("Existing complex storage-floor mesh loads without editing any saved map"),Mesh)
		|| !TestNotNull(TEXT("Storage floor has its actual collision body"),Mesh->GetBodySetup())) return false;
	F.Floor->Destroy();
	F.Floor = F.MeshFloor(Mesh,FVector(800,1750,-20));
	const FVector Origin(772.5,1770,25.35), Reference(772.5,1852,25.35);
	F.Basket->SetActorLocation(Origin);
	F.Basket->OpenDirectionLocal = FVector(-1,1,0);
	F.Cat->SetActorLocation(FVector(772.5,1872,25.35));
	FCollisionQueryParams Params(SCENE_QUERY_STAT(StorageSeamRegression),false,F.Cat);
	FHitResult Ray, Support;
	FVector Landing;
	TestTrue(TEXT("Old center ray really hits the storage stone seam"),F.World->LineTraceSingleByChannel(
		Ray,Reference+FVector(0,0,50),Reference-FVector(0,0,100),ECC_Visibility,Params));
	TestTrue(TEXT("Center ray's steep detail normal reproduces the old rejection"),Ray.ImpactNormal.Z<.65f);
	TestTrue(TEXT("Full actual capsule finds a walkable stone face at the same XY"),
		CatrunGround::FindSupport(*F.Cat->GetCapsuleComponent(),Reference,50,100,Params,Support,Landing));
	TestTrue(TEXT("Grounding preserves exact target XY and uses center-at-contact plus 2cm"),
		FMath::IsNearlyEqual(Landing.X,Reference.X,.001) && FMath::IsNearlyEqual(Landing.Y,Reference.Y,.001)
		&& FMath::IsNearlyEqual(Landing.Z,Support.Location.Z+2,.001));
	TestTrue(TEXT("Support matches the calibrated saved mesh landing"),FMath::IsNearlyEqual(Landing.Z,24.771014,.05));
	FVector Entry;
	TestTrue(TEXT("Common entry query accepts the supported rough-floor point"),F.Actions->TestEntry(F.Basket,Entry));
	TestTrue(TEXT("Entry approach is checked to the exact grounded center"),Entry.Equals(Landing,.01));
	F.Basket->TryOccupy(F.Cat);
	F.Actions->EnterBasket(F.Basket,Entry);
	F.Actions->FinishEnter();
	F.Keys({UCatrunInputBindings::GetEffectiveKey(ECatrunInputSlot::Back),UCatrunInputBindings::GetEffectiveKey(ECatrunInputSlot::Left)});
	F.Actions->UpdateExitCandidate(true);
	TestTrue(TEXT("Same AS semantic input selects world +Y under the explicit A-front"),F.Actions->ExitWorldDirection.Equals(FVector(0,1,0),.001));
	TestTrue(TEXT("Actual complex-floor AS exit is available rather than seam-rejected"),F.Actions->CanExit);
	TestTrue(TEXT("Component commits the same shape-supported exact XY/Z"),F.Actions->ExitWorldLocation.Equals(Landing,.01));
	TestTrue(TEXT("Preview landing stays centered despite an off-center support contact"),
		FMath::IsNearlyEqual(F.Actions->FloorLocation.X,Reference.X,.001) && FMath::IsNearlyEqual(F.Actions->FloorLocation.Y,Reference.Y,.001));
	FVector OriginalSupport;
	TestTrue(TEXT("Hidden origin is independently supported by the same actual mesh"),
		CatrunGround::FindSupport(*F.Cat->GetCapsuleComponent(),Origin,50,100,Params,Support,OriginalSupport));
	// Move only this transient basket so its hidden origin is now the proven center-ray seam.
	F.Basket->SetActorLocation(Reference);
	TestTrue(TEXT("Production grounded-origin query also accepts capsule support on the seam"),F.Actions->IsBasketExitPathClear(OriginalSupport));
	F.Basket->SetActorLocation(Origin);
	F.Actions->ExitBasket();
	TestEqual(TEXT("Normal confirmation accepts the exact rough-floor landing"),F.Actions->BasketPhase,ECatrunBasketPhase::Exiting);
	F.Actions->FinishExit();
	TestEqual(TEXT("Clear rough-floor exit completes with collision restored"),F.Actions->BasketPhase,ECatrunBasketPhase::Outside);
	TestTrue(TEXT("Successful rough-floor exit retains exact accepted placement"),F.Cat->GetActorLocation().Equals(Landing,.01) && F.Cat->GetActorEnableCollision());
	{
		FBasketCollisionFixture Bounds;
		Bounds.Basket->OpenDirectionLocal=FVector(1,0,0);
		FVector BoundedEntry;
		// Hidden reference Z26: the original entry ray accepts surface Z[-24,26].
		Bounds.Floor->SetActorLocation(FVector(0,0,-44)); // surface -34, outside that window
		TestFalse(TEXT("Entry cannot extend its former surface window downward by a capsule halfheight"),
			Bounds.Actions->TestEntry(Bounds.Basket,BoundedEntry));
		Bounds.Floor->SetActorLocation(FVector(0,0,-33)); // surface -23, inside the original lower bound
		TestTrue(TEXT("Entry still accepts supported floor inside its original surface range"),
			Bounds.Actions->TestEntry(Bounds.Basket,BoundedEntry));
		TestTrue(TEXT("Entry uses the exact grounded center after preserving its surface range"),BoundedEntry.Equals(FVector(82,0,3),.01));
		Bounds.Floor->SetActorLocation(FVector(0,0,-100)); // surface -90, below exit/origin's -74 lower bound
		Bounds.Basket->TryOccupy(Bounds.Cat);
		Bounds.Actions->EnterBasket(Bounds.Basket,FVector(82,0,26));
		Bounds.Keys({});
		Bounds.Actions->FinishEnter();
		TestFalse(TEXT("Exit candidate cannot extend the former floor range through its capsule height"),Bounds.Actions->CanExit);
		TestFalse(TEXT("Grounded origin retains the same former surface range"),
			Bounds.Actions->IsBasketExitPathClear(FVector(-82,0,-64)));
		Bounds.Floor->SetActorLocation(FVector(0,0,-83)); // surface -73, just inside the old range
		Bounds.Actions->UpdateExitCandidate(true);
		TestTrue(TEXT("Exit and origin still accept a supported floor inside the old lower bound"),Bounds.Actions->CanExit);
		Bounds.Actions->AbortBasket();
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunRoughRestoreSupportTest, "Catrun.Basket.CommonRestoreFallbackOnComplexFloor",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunRoughRestoreSupportTest::RunTest(const FString&)
{
	FBasketCollisionFixture F;
	auto* Mesh = LoadObject<UStaticMesh>(nullptr,TEXT("/Game/Environment/Stage1/Meshes/Floors/SM_Stage01_Floor_Storage.SM_Stage01_Floor_Storage"));
	if (!TestNotNull(TEXT("Actual storage floor loads for shared restoration regression"),Mesh)
		|| !TestNotNull(TEXT("Actual floor collision body exists"),Mesh->GetBodySetup())) return false;
	F.Floor->Destroy();
	F.Floor = F.MeshFloor(Mesh,FVector(800,1750,-20));
	F.Cat->GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Pawn,ECR_Block);
	const FVector FirstFallback(772.5,1852,24.771014);
	const FTransform Desired(FRotator::ZeroRotator,FirstFallback-FVector(44,0,0));
	F.Cat->SetActorTransform(Desired);
	FActorSpawnParameters Spawn; Spawn.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	auto* Occupant = F.World->SpawnActor<ACharacter>(Desired.GetLocation(),FRotator::ZeroRotator,Spawn);
	Occupant->GetCapsuleComponent()->SetCapsuleSize(20,24);
	Occupant->GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Pawn,ECR_Block);
	TestFalse(TEXT("The desired return footprint is actually occupied by a Pawn"),CatrunRestore::IsPlacementClear(*F.Cat,Desired));
	TestTrue(TEXT("First fallback endpoint is collision-clear on the actual stone floor"),
		CatrunRestore::IsPlacementClear(*F.Cat,FTransform(FRotator::ZeroRotator,FirstFallback)));
	TestTrue(TEXT("Shared restoration finds the reachable rough-floor fallback"),CatrunRestore::PlaceForCollision(*F.Cat,Desired,true));
	TestTrue(TEXT("Fallback retains bounded-ring ordering and accepts supported seam XY"),F.Cat->GetActorLocation().Equals(FirstFallback,.05));
	TestTrue(TEXT("Restoration's final accepted capsule remains collision-clear"),CatrunRestore::IsPlacementClear(*F.Cat,F.Cat->GetActorTransform()));
	Occupant->Destroy();
	const FTransform Airborne(FRotator::ZeroRotator,FVector(1100,1900,500));
	TestTrue(TEXT("Initial desired airborne placement semantics remain intact without requiring floor"),CatrunRestore::PlaceForCollision(*F.Cat,Airborne,true));
	TestTrue(TEXT("Clear initial desired placement is committed exactly"),F.Cat->GetActorTransform().Equals(Airborne,.001));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunBasketEntryTransitProfileTest, "Catrun.Basket.EntryRespectsPhysicalCapsuleProfile",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunBasketEntryTransitProfileTest::RunTest(const FString&)
{
	FBasketCollisionFixture F;
	F.Basket->OpenDirectionLocal=FVector(1,0,0);
	const FVector Start(200,0,26), Approach(82,0,26);
	FVector Entry;
	if (!TestTrue(TEXT("Clear entry is available at the exact approach"), F.Actions->TestEntry(F.Basket,Entry) && Entry.Equals(Approach,.01)))
		return false;
	auto* Wall = F.Box(FVector(140,0,26),FVector(2,30,26));
	auto* WallShape = CastChecked<UBoxComponent>(Wall->GetRootComponent());
	WallShape->SetCollisionResponseToChannel(ECC_Pawn,ECR_Block);
	TestFalse(TEXT("A wall blocking Pawn and Visibility prevents entry"), F.Actions->TestEntry(F.Basket,Entry));
	WallShape->SetCollisionResponseToChannel(ECC_Visibility,ECR_Ignore);
	FHitResult Hit;
	const FCollisionQueryParams Params(SCENE_QUERY_STAT(BasketEntryPhysicalFixture),false,F.Cat);
	if (!TestTrue(TEXT("Actual capsule sweep hits the wall that ignores Visibility"),
		F.SweepCapsule(Hit,Start,Approach,Params) && Hit.IsValidBlockingHit() && Hit.GetActor()==Wall)) return false;
	TestFalse(TEXT("Entry rejects a physically blocked approach even when the wall ignores Visibility"),
		F.Actions->TestEntry(F.Basket,Entry));
	Wall->SetActorLocation(FVector(41,0,26));
	WallShape->SetCollisionResponseToChannel(ECC_Pawn,ECR_Ignore);
	WallShape->SetCollisionResponseToChannel(ECC_Visibility,ECR_Block);
	TestFalse(TEXT("The independent visual guard still rejects a blocked view into the basket"),
		F.Actions->TestEntry(F.Basket,Entry));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunBasketProximityTest, "Catrun.Basket.ProximityPromptMatchesReachableEntry",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunBasketProximityTest::RunTest(const FString&)
{
	FBasketCollisionFixture F;
	auto* Anchor = NewObject<USceneComponent>(F.Basket,TEXT("HiddenPoint"));
	Anchor->SetupAttachment(F.Basket->GetRootComponent());
	Anchor->RegisterComponent();
	F.Basket->PostInitializeComponents();
	F.Basket->OpenDirectionLocal=FVector(1,0,0);
	F.Cat->GetCharacterMovement()->SetMovementMode(MOVE_Walking);
	for (int32 Sector=0; Sector<8; ++Sector)
	{
		const FVector Direction=FRotator(0,Sector*45.f,0).Vector();
		const bool bExpected=Sector<=2 || Sector>=6;
		for (const float Distance : {40.f, 100.f})
		{
			F.Cat->SetActorLocation(F.Basket->GetHiddenLocation()+Direction*Distance);
			for (const float Yaw : {0.f,180.f})
			{
				F.Cat->SetActorRotation(FRotator(0,Yaw,0));
				TestEqual(TEXT("Position decides front/side versus hinge rear; cat heading never does"),F.Actions->CanEnterNearbyBasket(),bExpected);
			}
		}
	}
	F.Cat->SetActorLocation(FVector(100,0,26));
	F.Actions->Busy=true;
	TestFalse(TEXT("Busy suppresses prompt eligibility"),F.Actions->CanEnterNearbyBasket()); F.Actions->Busy=false;
	F.Actions->IsHidden=true;
	TestFalse(TEXT("Hidden suppresses prompt eligibility"),F.Actions->CanEnterNearbyBasket()); F.Actions->IsHidden=false;
	F.PC->SetIgnoreMoveInput(true);
	TestFalse(TEXT("Cinematic input lock suppresses prompt eligibility"),F.Actions->CanEnterNearbyBasket()); F.PC->SetIgnoreMoveInput(false);
	auto* Guard=F.World->GetSubsystem<UCatrunPuzzleSuspension>(); Guard->Acquire(F.Basket);
	TestFalse(TEXT("Reveal suspension suppresses prompt eligibility"),F.Actions->CanEnterNearbyBasket()); Guard->Release(F.Basket);
	F.Basket->TryOccupy(F.Cat);
	TestFalse(TEXT("Occupied basket cannot advertise interaction"),F.Actions->CanEnterNearbyBasket()); F.Basket->Release(F.Cat);
	F.Cat->SetActorLocation(FVector(120,0,26));
	TestFalse(TEXT("Leaving range removes eligibility"),F.Actions->CanEnterNearbyBasket());
	F.Cat->SetActorLocation(FVector(100,0,26));
	auto* Rear = F.Box(FVector(82,0,26),FVector(2,30,26));
	F.Basket->ExternalBody=Rear;
	TestFalse(TEXT("Basket body still blocks the physical approach outside the authored jump"),F.Actions->CanEnterNearbyBasket());
	Rear->SetActorLocation(FVector(50,0,26));
	TestTrue(TEXT("An allowed front jump may cross its own shell only after the clear approach"),F.Actions->CanEnterNearbyBasket());
	auto* Wall=F.Box(FVector(25,0,26),FVector(2,30,26));
	CastChecked<UBoxComponent>(Wall->GetRootComponent())->SetCollisionResponseToChannel(ECC_Visibility,ECR_Ignore);
	TestFalse(TEXT("Basket body cannot mask a separate physical blocker toward the hidden point"),F.Actions->CanEnterNearbyBasket());
	Wall->Destroy(); Rear->Destroy();
	F.Cat->SetActorLocation(FVector(40,0,26));
	F.Actions->TryInteract();
	TestEqual(TEXT("F commits the same close eligible basket advertised by the prompt"),F.Actions->BasketPhase,ECatrunBasketPhase::Entering);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunBasketExitTransitProfileTest, "Catrun.Basket.ExitRespectsCustomCapsuleChannel",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunBasketExitTransitProfileTest::RunTest(const FString&)
{
	FBasketCollisionFixture F;
	constexpr ECollisionChannel CustomChannel = ECC_GameTraceChannel1;
	auto* Capsule = F.Cat->GetCapsuleComponent();
	Capsule->SetCollisionObjectType(CustomChannel);
	Capsule->SetCollisionResponseToChannel(ECC_WorldDynamic,ECR_Block);
	CastChecked<UBoxComponent>(F.Floor->GetRootComponent())->SetCollisionResponseToChannel(CustomChannel,ECR_Block);
	F.Basket->OpenDirectionLocal = FVector(-1,0,0);
	F.Keys({});
	F.Basket->TryOccupy(F.Cat);
	F.Actions->EnterBasket(F.Basket,FVector(82,0,26));
	F.Actions->FinishEnter();
	const FVector Origin(0,0,26), Landing(-82,0,26);
	if (!TestTrue(TEXT("Clear custom-channel exit selects the exact supported landing"),
		F.Actions->CanExit && F.Actions->ExitWorldLocation.Equals(Landing,.01))) return false;
	auto* Wall = F.Box(FVector(-41,0,26),FVector(2,30,26));
	auto* WallShape = CastChecked<UBoxComponent>(Wall->GetRootComponent());
	WallShape->SetCollisionResponseToChannel(ECC_Pawn,ECR_Ignore);
	WallShape->SetCollisionResponseToChannel(CustomChannel,ECR_Block);
	TestTrue(TEXT("Both ends of the custom-channel exit remain clear"),
		CatrunRestore::IsPlacementClear(*F.Cat,FTransform(Origin)) && CatrunRestore::IsPlacementClear(*F.Cat,FTransform(Landing)));
	FHitResult Hit;
	const FCollisionQueryParams Params(SCENE_QUERY_STAT(BasketExitPhysicalFixture),false,F.Cat);
	if (!TestTrue(TEXT("The actual custom capsule sweeps into the wall that ignores Pawn"),
		F.SweepCapsule(Hit,Origin,Landing,Params) && Hit.IsValidBlockingHit() && Hit.GetActor()==Wall)) return false;
	F.Actions->UpdateExitCandidate(true);
	TestFalse(TEXT("A custom capsule transit wall rejects the supported exit candidate"),F.Actions->CanExit);
	F.Actions->ExitBasket();
	TestEqual(TEXT("Confirming a physically blocked exit keeps the cat hidden"),F.Actions->BasketPhase,ECatrunBasketPhase::Hidden);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunRestoreTransitProfileTest, "Catrun.Basket.RestoreRespectsCustomCapsuleChannel",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunRestoreTransitProfileTest::RunTest(const FString&)
{
	FBasketCollisionFixture F;
	constexpr ECollisionChannel CustomChannel = ECC_GameTraceChannel1;
	const FVector Origin(0,0,26), FirstFallback(44,0,26);
	const FTransform Desired(Origin);
	auto* Capsule = F.Cat->GetCapsuleComponent();
	Capsule->SetCollisionObjectType(CustomChannel);
	Capsule->SetCollisionResponseToChannel(ECC_Pawn,ECR_Block);
	Capsule->SetCollisionResponseToChannel(ECC_WorldDynamic,ECR_Block);
	CastChecked<UBoxComponent>(F.Floor->GetRootComponent())->SetCollisionResponseToChannel(CustomChannel,ECR_Block);
	F.Cat->SetActorTransform(Desired);
	FActorSpawnParameters Spawn; Spawn.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	auto* Occupant = F.World->SpawnActor<ACharacter>(Origin,FRotator::ZeroRotator,Spawn);
	Occupant->GetCapsuleComponent()->SetCapsuleSize(20,24);
	Occupant->GetCapsuleComponent()->SetCollisionResponseToChannel(CustomChannel,ECR_Block);
	if (!TestFalse(TEXT("A real Pawn occupies the requested restore position"),CatrunRestore::IsPlacementClear(*F.Cat,Desired)))
		return false;
	if (!TestTrue(TEXT("Without a wall the first ring placement is the +X fallback"),
		CatrunRestore::PlaceForCollision(*F.Cat,Desired,true) && F.Cat->GetActorLocation().Equals(FirstFallback,.01))) return false;
	auto* Wall = F.Box(FVector(22,0,26),FVector(.5,12,24));
	auto* WallShape = CastChecked<UBoxComponent>(Wall->GetRootComponent());
	WallShape->SetCollisionResponseToChannel(ECC_Pawn,ECR_Ignore);
	WallShape->SetCollisionResponseToChannel(CustomChannel,ECR_Block);
	FHitResult Hit;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(RestorePhysicalFixture),false,F.Cat);
	Params.AddIgnoredActor(Occupant);
	TestTrue(TEXT("The wall leaves the first fallback endpoint clear"),
		CatrunRestore::IsPlacementClear(*F.Cat,FTransform(FirstFallback)));
	if (!TestTrue(TEXT("Actual custom capsule hits the wall only after leaving the occupied origin"),
		F.SweepCapsule(Hit,Origin,FirstFallback,Params) && Hit.IsValidBlockingHit() && Hit.GetActor()==Wall)) return false;
	if (!TestTrue(TEXT("An unobstructed alternative is available"),CatrunRestore::PlaceForCollision(*F.Cat,Desired,true))) return false;
	TestFalse(TEXT("Restoration does not take the first fallback through the custom-channel wall"),
		F.SweepCapsule(Hit,Origin,F.Cat->GetActorLocation(),Params));
	TestTrue(TEXT("The replacement restore location is clear"),CatrunRestore::IsPlacementClear(*F.Cat,F.Cat->GetActorTransform()));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunBasketCandidateRegressionTest, "Catrun.Basket.CandidateInputAndCollision",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunBasketCandidateRegressionTest::RunTest(const FString&)
{
	auto* Settings = UCatrunUserSettings::GetCatrunUserSettings();
	if (!TestNotNull(TEXT("Configured settings singleton"), Settings)) return false;
	const FCatrunKeyboardBindings Saved = Settings->GetKeyboardBindings();
	struct FRestoreBindings
	{
		UCatrunUserSettings* Settings;
		FCatrunKeyboardBindings Saved;
		~FRestoreBindings() { FText Error; Settings->SetKeyboardBindings(Saved, Error); }
	} Restore{Settings, Saved};
	FText Error;
	Settings->SetKeyboardBindings(FCatrunKeyboardBindings(), Error);
	FBasketCollisionFixture F;
	// Reproduce the saved first-basket frame without changing any project map.
	F.Basket->OpenDirectionLocal = FVector(0,-1,0);
	F.Basket->TryOccupy(F.Cat);
	F.Actions->EnterBasket(F.Basket, FVector(82,0,26));
	F.Actions->FinishEnter();
	F.Keys({EKeys::W,EKeys::A});
	F.Actions->UpdateExitCandidate(true);
	TestTrue(TEXT("Camera -135 WA selects world -X"), F.Actions->ExitWorldDirection.Equals(FVector(-1,0,0), .001));
	TestTrue(TEXT("Supported clear WA landing is available"), F.Actions->CanExit);
	TestTrue(TEXT("Landing uses floor + real capsule halfheight + 2"), F.Actions->ExitWorldLocation.Equals(FVector(-82,0,26), .01));
	F.Keys({EKeys::A,EKeys::S});
	TestTrue(TEXT("Effective default AS axes are back and left"),
		UCatrunInputBindings::GetMovementInput([&](FKey Key) { return F.PC->IsInputKeyDown(Key); }).Equals(FVector2D(-1,-1)));
	TestFalse(TEXT("At camera -135 the saved -Y front excludes AS world +Y"),
		CatrunBasket::IsDirectionAllowed(FVector(0,1,0), F.Basket->GetOpenDirection(), -135.f));
	F.Actions->UpdateExitCandidate(true);
	TestTrue(TEXT("Excluded AS retains the selected WA rather than changing to +Y"),
		F.Actions->ExitWorldDirection.Equals(FVector(-1,0,0),.001));
	TestTrue(TEXT("Excluded AS keeps a physically safe retained exit available"), F.Actions->CanExit);
	// The historical per-instance front is a candidate asset correction, not a global fan expansion.
	F.Basket->OpenDirectionLocal = FVector(-1,1,0);
	F.Actions->UpdateExitCandidate(true);
	TestTrue(TEXT("The historical A-front lets the same AS input replace WA with world +Y"),
		F.Actions->ExitWorldDirection.Equals(FVector(0,1,0),.001));
	TestTrue(TEXT("The selected AS landing uses the same floor and capsule policy"),
		F.Actions->CanExit && F.Actions->ExitWorldLocation.Equals(FVector(0,82,26),.01));
	F.Keys({EKeys::W,EKeys::A});
	F.Actions->UpdateExitCandidate(true);
	F.Keys({EKeys::D});
	F.Actions->UpdateExitCandidate(false);
	TestTrue(TEXT("Rejected rear input preserves the previous safe exit availability"), F.Actions->CanExit);
	TestTrue(TEXT("Rejected rear input retains the stored valid selection"), F.Actions->ExitWorldDirection.Equals(FVector(-1,0,0), .001));
	F.Actions->UpdatePreview();
	TestTrue(TEXT("Rejected input keeps the retained safe selection visible"), F.Actions->ExitPreview && F.Actions->ExitPreview->IsVisible());
	auto* RetainedPathBlocker = F.Box(FVector(-41,0,26), FVector(2,25,24));
	F.Actions->ExitBasket();
	TestEqual(TEXT("Confirmation rechecks the retained path and refuses a new blocker"), F.Actions->BasketPhase, ECatrunBasketPhase::Hidden);
	TestFalse(TEXT("Blocked retained selection loses its availability"), F.Actions->CanExit);
	TestFalse(TEXT("Blocked retained selection hides its preview"), F.Actions->ExitPreview->IsVisible());
	RetainedPathBlocker->Destroy();
	F.Actions->ExitBasket();
	TestEqual(TEXT("Rejected input can confirm the retained selection once physically clear"), F.Actions->BasketPhase, ECatrunBasketPhase::Exiting);
	TestTrue(TEXT("Retained selection confirmation commits the previously selected landing"), F.Cat->GetActorLocation().Equals(FVector(-82,0,26),.01));
	F.Actions->FinishExit();
	TestEqual(TEXT("Safe retained-selection exit completes"), F.Actions->BasketPhase, ECatrunBasketPhase::Outside);
	F.Keys({});
	F.Basket->TryOccupy(F.Cat);
	F.Actions->EnterBasket(F.Basket, FVector(82,0,26));
	F.Actions->FinishEnter();
	F.Actions->ExitWorldDirection = FVector(-1,0,0);
	F.Actions->UpdateExitCandidate(false);
	TestTrue(TEXT("Release preserves the retained supported selection"), F.Actions->CanExit);
	F.Keys({EKeys::W,EKeys::S,EKeys::A,EKeys::D});
	F.Actions->UpdateExitCandidate(true);
	TestTrue(TEXT("Cancelling opposite axes retains the valid selection"), F.Actions->CanExit);
	auto Remapped = FCatrunKeyboardBindings();
	Remapped.Keys[0]=EKeys::I; Remapped.Keys[1]=EKeys::K; Remapped.Keys[2]=EKeys::J; Remapped.Keys[3]=EKeys::L;
	TestTrue(TEXT("Temporary remap is accepted without saving"), Settings->SetKeyboardBindings(Remapped,Error));
	F.Actions->ExitWorldDirection = F.Basket->GetOpenDirection();
	F.Keys({EKeys::W,EKeys::A});
	F.Actions->UpdateExitCandidate(true);
	TestTrue(TEXT("Old WA cannot change the selection after remap"), F.Actions->ExitWorldDirection.Equals(FVector(-1,1,0).GetSafeNormal2D(),.001));
	F.Keys({EKeys::I,EKeys::J});
	F.Actions->UpdateExitCandidate(true);
	TestTrue(TEXT("Rebound forward+left selects the same world -X"), F.Actions->ExitWorldDirection.Equals(FVector(-1,0,0),.001));
	auto* Blocker = F.Box(FVector(-82,0,26), FVector(10,25,24));
	F.Actions->UpdateExitCandidate(true);
	TestTrue(TEXT("Endpoint probe actually hits the narrow blocker's top"), FMath::IsNearlyEqual(F.Actions->FloorLocation.Z,50.f,.01f));
	TestFalse(TEXT("Blocked endpoint rejects WA"), F.Actions->CanExit);
	Blocker->SetActorLocation(FVector(-41,0,26));
	F.Actions->UpdateExitCandidate(true);
	TestFalse(TEXT("Thin transit obstruction rejects a clear endpoint"), F.Actions->CanExit);
	Blocker->Destroy();
	F.Actions->UpdateExitCandidate(true);
	TestTrue(TEXT("Removing the obstruction restores the supported landing"), F.Actions->CanExit);
	// Destination floor remains present, but the hidden origin no longer has supporting floor.
	Cast<UBoxComponent>(F.Floor->GetRootComponent())->SetBoxExtent(FVector(30,60,10));
	F.Floor->SetActorLocation(FVector(-82,0,-10));
	F.Actions->UpdateExitCandidate(true);
	TestFalse(TEXT("A supported destination cannot enable an exit from an unsupported origin"), F.Actions->CanExit);
	F.Floor->Destroy();
	F.Actions->UpdateExitCandidate(true);
	TestFalse(TEXT("Missing supporting floor rejects WA"), F.Actions->CanExit);
	F.Actions->AbortBasket();
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunBasketRestoreRegressionTest, "Catrun.Basket.ExactLandingAndCancellation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunBasketRestoreRegressionTest::RunTest(const FString&)
{
	FBasketCollisionFixture F;
	auto Enter = [&]
	{
		F.Basket->TryOccupy(F.Cat);
		F.Actions->EnterBasket(F.Basket,FVector(82,0,26));
		F.Actions->FinishEnter();
	};
	Enter();
	TestEqual(TEXT("Fixture captures the explicitly chosen post-possession movement mode"), F.Actions->SavedMovementMode, uint8(MOVE_Flying));
	const FVector Landing(-82,0,26);
	F.Actions->ExitWorldDirection = FVector(-1,0,0);
	F.Keys({});
	// Transit intentionally ignores basket presentation, but restoration must still use the actual capsule profile.
	auto* Body = F.Box(Landing,FVector(10,25,24));
	F.Basket->ExternalBody = Body;
	TestTrue(TEXT("Basket-body transit exemption is characterized"), F.Actions->IsExitPathClear(F.Basket->GetHiddenLocation(),Landing));
	F.Actions->UpdateExitCandidate(true);
	TestFalse(TEXT("Persistent external body blocks candidate before preview or animation"), F.Actions->CanExit);
	F.Actions->ExitBasket();
	TestEqual(TEXT("Persistent external body prevents normal exit confirmation"), F.Actions->BasketPhase, ECatrunBasketPhase::Hidden);
	TestFalse(TEXT("Rejected confirmation does not become busy"), F.Actions->Busy);
	Body->Destroy();
	F.Basket->ExternalBody = nullptr;
	F.Actions->UpdateExitCandidate(true);
	TestTrue(TEXT("Removing external body restores candidate availability"), F.Actions->CanExit);
	F.Actions->ExitBasket();
	TestEqual(TEXT("Normal confirmation starts after blocker removal"), F.Actions->BasketPhase, ECatrunBasketPhase::Exiting);
	// The same obstruction arriving after confirmation must still be rejected at completion.
	Body = F.Box(Landing,FVector(10,25,24));
	F.Basket->ExternalBody = Body;
	F.Actions->FinishExit();
	TestEqual(TEXT("A landing blocked for collision restoration returns hidden without a nearby unpreviewed exit"), F.Actions->BasketPhase, ECatrunBasketPhase::Hidden);
	TestTrue(TEXT("Hidden fallback returns to basket origin"), F.Cat->GetActorLocation().Equals(F.Basket->GetHiddenLocation()));
	TestFalse(TEXT("Hidden fallback keeps collision disabled"), F.Cat->GetActorEnableCollision());
	TestTrue(TEXT("Hidden fallback retains occupancy"), F.Basket->Occupied);
	Body->Destroy();
	F.Basket->ExternalBody = nullptr;
	F.Cat->SetActorLocation(Landing);
	F.Actions->BasketPhase = ECatrunBasketPhase::Exiting;
	F.Actions->Busy = true;
	auto* LateBlocker = F.Box(FVector(-41,0,26), FVector(2,25,24));
	F.Actions->FinishExit();
	TestEqual(TEXT("Late transit blocker preserves hidden fallback"), F.Actions->BasketPhase, ECatrunBasketPhase::Hidden);
	LateBlocker->Destroy();
	F.Cat->SetActorLocation(Landing);
	F.Actions->BasketPhase = ECatrunBasketPhase::Exiting;
	F.Actions->FinishExit();
	TestEqual(TEXT("Clear exit completes"), F.Actions->BasketPhase, ECatrunBasketPhase::Outside);
	TestTrue(TEXT("Accepted exact landing is committed unchanged"), F.Cat->GetActorLocation().Equals(Landing,.001));
	TestTrue(TEXT("Clear exit restores collision"), F.Cat->GetActorEnableCollision());
	TestEqual(TEXT("Clear exit restores saved movement mode"), F.Cat->GetCharacterMovement()->MovementMode, TEnumAsByte<EMovementMode>(MOVE_Flying));
	TestFalse(TEXT("Clear exit releases occupancy"), F.Basket->Occupied);
	const FTransform Entry = F.Cat->GetActorTransform();
	Enter();
	F.Actions->AbortBasket();
	TestTrue(TEXT("Cancellation commits the original clear entry"), F.Cat->GetActorTransform().Equals(Entry,.001));
	TestTrue(TEXT("Cancellation restores collision"), F.Cat->GetActorEnableCollision());
	TestEqual(TEXT("Cancellation clears phase"), F.Actions->BasketPhase, ECatrunBasketPhase::Outside);
	TestFalse(TEXT("Cancellation releases occupancy"), F.Basket->Occupied);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunBasketLateLandingSupportTest, "Catrun.Basket.ExitRechecksExactLandingSupport",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunBasketLateLandingSupportTest::RunTest(const FString&)
{
	FBasketCollisionFixture F;
	const FVector Origin(0,0,26), Landing(-82,0,26);
	const FVector Extent(28,100,10);
	F.Floor->Destroy();
	F.Box(FVector(0,0,-10),Extent);
	auto* LandingFloor = F.Box(FVector(-82,0,-10),Extent);
	F.Basket->OpenDirectionLocal = FVector(-1,0,0);
	F.Keys({});
	F.Basket->TryOccupy(F.Cat);
	F.Actions->EnterBasket(F.Basket,FVector(82,0,26));
	F.Actions->FinishEnter();
	auto StartExit = [&]
	{
		F.Actions->ExitBasket();
		return TestTrue(TEXT("Confirmation commits the original exact landing"),
			F.Actions->BasketPhase==ECatrunBasketPhase::Exiting && F.Cat->GetActorLocation().Equals(Landing,.01));
	};
	if (!StartExit()) return false;
	LandingFloor->Destroy();
	F.Actions->FinishExit();
	if (!TestEqual(TEXT("Removing only the selected landing floor returns the cat to Hidden"),
		F.Actions->BasketPhase,ECatrunBasketPhase::Hidden)) return false;
	TestTrue(TEXT("Unsupported exit keeps the same basket reserved and returns to its origin"),
		F.Basket->Occupied && F.Actions->IsHidden && F.Cat->GetActorLocation().Equals(Origin,.01));
	TestFalse(TEXT("Unsupported exit keeps collision disabled"),F.Cat->GetActorEnableCollision());
	TestFalse(TEXT("Unsupported exit leaves no visible guide"),F.Actions->ExitPreview && F.Actions->ExitPreview->IsVisible());
	LandingFloor = F.Box(FVector(-82,0,-10),Extent);
	if (!StartExit()) return false;
	LandingFloor->SetActorLocation(FVector(-82,0,-14));
	F.Actions->FinishExit();
	if (!TestEqual(TEXT("A different landing height cannot complete the original exit"),
		F.Actions->BasketPhase,ECatrunBasketPhase::Hidden)) return false;
	TestTrue(TEXT("Changed support never moves the cat to an unpreviewed landing"),F.Cat->GetActorLocation().Equals(Origin,.01));
	LandingFloor->SetActorLocation(FVector(-82,0,-10));
	if (!StartExit()) return false;
	F.Actions->FinishExit();
	TestEqual(TEXT("Restored support allows the exact original exit"),F.Actions->BasketPhase,ECatrunBasketPhase::Outside);
	TestTrue(TEXT("Successful exit restores collision and preserves the accepted landing"),
		F.Cat->GetActorEnableCollision() && F.Cat->GetActorLocation().Equals(Landing,.01));
	TestFalse(TEXT("Successful exit releases the basket"),F.Basket->Occupied);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBasketDirectionTest, "Catrun.Basket.CameraInputAndBlockedBack",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBasketDirectionTest::RunTest(const FString&)
{
	const FVector Front(1,0,0);
	const FVector Right = CatrunBasket::SelectDirection(-45,0,1,Front,Front);
	TestTrue(TEXT("D follows the quarter-view camera right axis"), Right.Equals(FVector(1,1,0).GetSafeNormal(),.001));
	const FVector Diagonal = CatrunBasket::SelectDirection(-45,1,1,Front,Front);
	TestTrue(TEXT("W+D combines into a normalized world direction"), Diagonal.Equals(Front,.001));
	TestTrue(TEXT("Key release preserves selection"), CatrunBasket::SelectDirection(-45,0,0,Right,Front).Equals(Right));
	TestTrue(TEXT("Back input cannot replace the last valid selection"), CatrunBasket::SelectDirection(0,-1,0,Right,Front).Equals(Right));
	TestTrue(TEXT("Opposing keys preserve selection"), CatrunBasket::SelectDirection(0,0,0,Right,Front).Equals(Right));
	const FVector RotatedFront(0,-1,0);
	TestTrue(TEXT("A rotated basket rejects world +Y"), CatrunBasket::SelectDirection(0,0,1,RotatedFront,RotatedFront).Equals(RotatedFront));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBasketArcTest, "Catrun.Basket.ArcEndpoints",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBasketArcTest::RunTest(const FString&)
{
	const FVector A(0,0,58), B(82,0,3);
	TestTrue(TEXT("Arc begins above the basket"), CatrunBasket::ArcPoint(A,B,90,0).Equals(A));
	TestTrue(TEXT("Arc ends at landing circle"), CatrunBasket::ArcPoint(A,B,90,1).Equals(B));
	TestTrue(TEXT("Middle rises above both endpoints"), CatrunBasket::ArcPoint(A,B,90,.5).Z>A.Z);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBasketFiveDirectionsTest, "Catrun.Basket.PhysicalRearBlockedAtAnyCameraRotation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBasketFiveDirectionsTest::RunTest(const FString&)
{
	for (float CameraYaw : {-135.f, -45.f, 0.f, 17.f, 90.f})
	{
		for (int32 Yaw = -180; Yaw < 180; ++Yaw)
		{
			const FVector Opening = FRotator(0, Yaw, 0).Vector();
			int32 Allowed = 0;
			for (int32 Sector = 0; Sector < 8; ++Sector)
			{
				const FVector Direction = FRotator(0, CameraYaw + Sector * 45.f, 0).Vector();
				const bool bAllowed=CatrunBasket::IsDirectionAllowed(Direction,Opening,CameraYaw);
				Allowed += bAllowed ? 1 : 0;
				TestFalse(TEXT("Camera quantization cannot admit the physical closed rear"),
					bAllowed && FVector::DotProduct(Direction,Opening)<-.0001f);
			}
			if (Allowed < 4 || Allowed > 5)
			{
				AddError(FString::Printf(TEXT("Camera %.1f, basket %d: expected four or five front-side directions, got %d"), CameraYaw, Yaw, Allowed));
				return false;
			}
			if (FMath::IsNearlyEqual(FMath::Fmod(FMath::Abs(Yaw-CameraYaw),45.f),0.f,.001f))
				TestEqual(TEXT("Aligned front and exact sides retain five keyboard directions"),Allowed,5);
			TestFalse(TEXT("Directly behind the opening is blocked"),
				CatrunBasket::IsDirectionAllowed(-Opening, Opening, CameraYaw));
			for (const float Offset : {-90.1f,-90.f,-89.9f,89.9f,90.f,90.1f})
			{
				const FVector Direction=FRotator(0,Yaw+Offset,0).Vector();
				TestEqual(TEXT("Physical side boundary stays fixed while camera and basket rotate"),
					CatrunBasket::IsDirectionAllowed(Direction,Opening,CameraYaw),FMath::Abs(Offset)<=90.f);
			}
		}
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBasketConfiguredDirectionTest, "Catrun.Basket.ExplicitDirectionOverridesCloth",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBasketConfiguredDirectionTest::RunTest(const FString&)
{
	// 사용자 맵을 건드리지 않는 임시 월드에서 실제 바구니의 출구 계산을 검사한다.
	const UWorld::InitializationValues Settings = UWorld::InitializationValues().AllowAudioPlayback(false)
		.CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false);
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true,
		ERHIFeatureLevel::Num, &Settings);
	ACatrunHideBasket* Basket = World->SpawnActor<ACatrunHideBasket>();
	if (!TestNotNull(TEXT("Basket spawns"), Basket))
	{
		World->DestroyWorld(false);
		return false;
	}
	USceneComponent* Root = NewObject<USceneComponent>(Basket);
	Basket->SetRootComponent(Root);
	Root->RegisterComponent();
	USkeletalMesh* Mesh = LoadObject<USkeletalMesh>(nullptr,
		TEXT("/Game/Environment/Shared/Castle/Props/Hiding/HideBasket/Meshes/SK_HideBasket_Cloth.SK_HideBasket_Cloth"));
	TestNotNull(TEXT("Basket cloth asset loads"), Mesh);
	USkeletalMeshComponent* Cloth = NewObject<USkeletalMeshComponent>(Basket);
	Cloth->SetSkeletalMesh(Mesh);
	Basket->ExternalCloth = Cloth;
	Basket->OpenDirectionLocal = FVector(-1, 1, 0);
	const FVector ExpectedFront = FVector(-1, 1, 0).GetSafeNormal2D();
	for (float ClothYaw : {0.f, 90.f, 180.f, 270.f})
	{
		Cloth->SetWorldRotation(FRotator(0, ClothYaw, 0));
		TestTrue(TEXT("Explicit front does not follow the cloth bones or rotation"),
			Basket->GetOpenDirection().Equals(ExpectedFront, .001));
	}
	// 현재 창고 바구니: 카메라 -135도에서 A가 정면이면 W/WA/A/AS/S를 허용한다.
	const bool Allowed[8] = {true, false, false, false, true, true, true, true};
	for (int32 Sector = 0; Sector < 8; ++Sector)
	{
		const FVector Direction = FRotator(0, -135 + Sector * 45.f, 0).Vector();
		TestEqual(FString::Printf(TEXT("Storage basket input sector %d"), Sector),
			CatrunBasket::IsDirectionAllowed(Direction, Basket->GetOpenDirection(), -135), Allowed[Sector]);
	}
	const FVector South = FRotator(0, 45, 0).Vector();
	TestTrue(TEXT("S replaces A when A is the configured front"),
		CatrunBasket::SelectDirection(-135, -1, 0, ExpectedFront, Basket->GetOpenDirection()).Equals(South, .001));
	Basket->SetActorRotation(FRotator(0, 90, 0));
	Basket->SetActorScale3D(FVector(2, 3, 1));
	TestTrue(TEXT("Rotating the basket rotates its configured front; size does not distort it"),
		Basket->GetOpenDirection().Equals(FVector(-1, -1, 0).GetSafeNormal2D(), .001));
	Basket->OpenDirectionLocal = FVector::ZeroVector;
	TestFalse(TEXT("An unset direction cannot enable an exit"),
		CatrunBasket::IsDirectionAllowed(South, Basket->GetOpenDirection(), -135));
	World->DestroyWorld(false);
	return true;
}
#endif
