#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Sound/CatrunDoor.h"
#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunDoorHingeSeatingTest,
	"Catrun.Doors.AuthoredSeatSurvivesBothHinges", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunDoorHingeSeatingTest::RunTest(const FString&)
{
	UStaticMesh* Asset = LoadObject<UStaticMesh>(nullptr,
		TEXT("/Game/Environment/Shared/Castle/Architecture/Doors/BedroomDoor/Meshes/SM_BedroomDoorLeaf_A.SM_BedroomDoorLeaf_A"));
	if (!TestNotNull(TEXT("Real tutorial leaf"), Asset)) return false;
	TestTrue(TEXT("Fixture retains the nonzero pivot overhang"), Asset->GetBounds().GetBox().Min.X < -1.f);
	const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false);
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
	GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
	World->InitializeActorsForPlay(FURL());
	for (int32 Case = 0; Case < 3; ++Case)
	{
		FActorSpawnParameters Spawn; Spawn.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		auto* Door = World->SpawnActor<ACatrunDoor>(FVector(Case * 500.f, 0.f, 0.f), FRotator(0.f, Case * 35.f, 0.f), Spawn);
		auto* Leaf = Door->FindComponentByClass<UStaticMeshComponent>();
		Leaf->SetStaticMesh(Asset);
		const FVector Seat = Case == 0 ? FVector::ZeroVector : FVector(7.f, -3.f, 2.f);
		const FQuat SeatRotation = FRotator(0.f, Case == 0 ? 0.f : 12.f, 0.f).Quaternion();
		Leaf->SetRelativeLocation(Seat);
		Leaf->SetRelativeRotation(SeatRotation);
		Leaf->SetRelativeScale3D(Case == 0 ? FVector::OneVector : FVector(Case == 2 ? -0.85f : 0.85f, .9f, 1.05f));
		const FTransform Authored = Leaf->GetRelativeTransform();
		const FTransform Gate = Door->GetGateBox()->GetComponentTransform();
		Door->DispatchBeginPlay();
		TestTrue(TEXT("BeginPlay preserves closed seating"), Leaf->GetRelativeTransform().Equals(Authored, .001f));
		const FBox ClosedBounds = Door->GetLeafBounds();
		for (const float Side : {-1.f, 1.f, -1.f})
		{
			Door->OpenFrom(Door->GetDoorwayCenter() + Door->GetDoorNormal() * Side * 200.f);
			const FBox Mirrored = Door->GetLeafBounds();
			TestTrue(TEXT("Hinge switch never translates closed bounds"), Mirrored.Min.Equals(ClosedBounds.Min, .01f) && Mirrored.Max.Equals(ClosedBounds.Max, .01f));
			TestTrue(TEXT("Opening releases physical blockage"), Door->IsOpen() && Leaf->GetCollisionEnabled() == ECollisionEnabled::NoCollision);
			static_cast<AActor*>(Door)->Tick(3.f);
			const FQuat Open = SeatRotation * FQuat(FVector::UpVector, FMath::DegreesToRadians(Door->OpenYaw));
			TestTrue(TEXT("Swing is relative to authored seating rotation"), Leaf->GetRelativeRotation().Quaternion().Equals(Open, .001f));
			Door->SetOpen(false);
			static_cast<AActor*>(Door)->Tick(3.f);
			TestTrue(TEXT("Closing restores the exact seating silhouette"), Door->GetLeafBounds().Min.Equals(ClosedBounds.Min, .01f) && Door->GetLeafBounds().Max.Equals(ClosedBounds.Max, .01f));
			TestTrue(TEXT("Closed leaf blocks again"), !Door->IsOpen() && Leaf->GetCollisionEnabled() == ECollisionEnabled::QueryAndPhysics);
			TestTrue(TEXT("Sound and armor gate anchor stays fixed"), Door->GetGateBox()->GetComponentTransform().Equals(Gate, .001f));
		}
		Door->Destroy();
	}
	GEngine->DestroyWorldContext(World);
	World->DestroyWorld(false);
	return true;
}
#endif
