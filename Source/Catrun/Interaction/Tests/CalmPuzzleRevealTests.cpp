#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Interaction/CatrunPuzzleRevealComponent.h"
#include "Interaction/CatrunPuzzleSuspension.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/BoxComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/PlayerController.h"

namespace
{
	struct FCalmRevealFixture
	{
		UWorld* World;
		ACharacter* Cat;
		APlayerController* PC;
		ACameraActor* Original;
		AActor* Gate;
		UCatrunPuzzleRevealComponent* Reveal;
		FMinimalViewInfo View;
		const FVector Focus = FVector(300,-700,150);
		FCalmRevealFixture(ECameraProjectionMode::Type Projection)
		{
			const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false)
				.CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false);
			World = UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Init);
			GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
			World->InitializeActorsForPlay(FURL());
			Cat = World->SpawnActor<ACharacter>();
			PC = World->SpawnActor<APlayerController>();
			PC->Possess(Cat);
			Original = World->SpawnActor<ACameraActor>();
			PC->SetViewTarget(Original);
			if (!PC->PlayerCameraManager) PC->PlayerCameraManager = World->SpawnActor<APlayerCameraManager>();
			View.Rotation = FRotator(-55,-135,0);
			View.Location = Cat->GetActorLocation() - View.Rotation.Vector() * 1200;
			View.ProjectionMode = Projection;
			View.OrthoWidth = 1375;
			View.FOV = 73;
			View.AspectRatio = 16.f/9.f;
			View.bConstrainAspectRatio = true;
			View.bAutoCalculateOrthoPlanes = false;
			View.OrthoNearClipPlane = -800;
			View.OrthoFarClipPlane = 9000;
			PC->PlayerCameraManager->SetCameraCachePOV(View);
			Gate = World->SpawnActor<AActor>();
			Reveal = NewObject<UCatrunPuzzleRevealComponent>(Cat);
			Reveal->RegisterComponent();
			Reveal->CameraTravelTime = 2;
			Reveal->CameraReturnTime = 1.6f;
			Reveal->MaximumLockTime = 8;
			// This old authored offset must have no influence on the calm mode.
			Reveal->GateCameraOffset = FVector(350,350,1200);
		}
		~FCalmRevealFixture()
		{
			Reveal->CancelReveal();
			GEngine->DestroyWorldContext(World);
			World->DestroyWorld(false);
		}
		bool Begin() { return Reveal->BeginReveal(TEXT("Calm"),Gate,FBox(Focus-FVector(50),Focus+FVector(50))); }
		void Tick(float Seconds) { Reveal->TickComponent(Seconds,LEVELTICK_All,nullptr); }
		FVector End() const { return Focus-View.Rotation.Vector()*1200; }
	};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCalmPuzzleRevealFramingTest,"Catrun.Stage2.CalmRevealPreservesLiveFramingAndReturns",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FCalmPuzzleRevealFramingTest::RunTest(const FString&)
{
	for (const auto Projection : {ECameraProjectionMode::Orthographic,ECameraProjectionMode::Perspective})
	{
		FCalmRevealFixture F(Projection);
		TestTrue(TEXT("Reveal captures the live gameplay camera"),F.Begin());
		auto* Camera = F.Reveal->GetRevealCamera();
		if (!TestNotNull(TEXT("Owned reveal camera exists"),Camera)) return false;
		auto CheckFraming = [&]()
		{
			auto* C = Camera->GetCameraComponent();
			TestTrue(TEXT("No yaw/pitch/roll change"),Camera->GetActorRotation().Equals(F.View.Rotation,.001));
			TestEqual(TEXT("Projection mode survives"),C->ProjectionMode,F.View.ProjectionMode);
			TestEqual(TEXT("No orthographic zoom"),C->OrthoWidth,F.View.OrthoWidth);
			TestEqual(TEXT("No perspective zoom"),C->FieldOfView,F.View.FOV);
			TestEqual(TEXT("Aspect ratio survives"),C->AspectRatio,F.View.AspectRatio);
			TestTrue(TEXT("Aspect constraint survives"),bool(C->bConstrainAspectRatio));
			TestEqual(TEXT("BP zoom bridge resolves captured width"),F.Reveal->ResolvePresentationOrthoWidth(650),1375.f);
		};
		CheckFraming();
		F.Tick(1);
		TestTrue(TEXT("Smooth outbound pan reaches midpoint at one second"),Camera->GetActorLocation().Equals((F.View.Location+F.End())*.5,.01));
		CheckFraming();
		F.Tick(1);
		TestTrue(TEXT("Gate is centred along original view ray"),Camera->GetActorLocation().Equals(F.End(),.01));
		TestEqual(TEXT("Gate opens after two second travel"),F.Reveal->Phase,ECatrunPuzzleRevealPhase::Opening);
		CheckFraming();
		// Presentation cannot change native framing even during the opening hold.
		Camera->GetCameraComponent()->SetOrthoWidth(650);
		F.Tick(.1f);
		CheckFraming();
		F.Reveal->GateOpened(TEXT("Calm"));
		F.Tick(.8f);
		TestTrue(TEXT("Smooth return reaches midpoint"),Camera->GetActorLocation().Equals((F.View.Location+F.End())*.5,.01));
		CheckFraming();
		F.Tick(.81f);
		TestEqual(TEXT("Return releases reveal"),F.Reveal->Phase,ECatrunPuzzleRevealPhase::Inactive);
		TestTrue(TEXT("Original view owner restored"),F.PC->GetViewTarget()==F.Original);
		TestFalse(TEXT("Return releases movement/look locks"),F.PC->IsMoveInputIgnored() || F.PC->IsLookInputIgnored());
		TestFalse(TEXT("Return releases hostile suspension"),UCatrunPuzzleSuspension::IsSuspended(F.Cat));
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCalmPuzzleRevealBlockedTest,"Catrun.Stage2.CalmRevealBlockedPathAndEightSecondGuard",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FCalmPuzzleRevealBlockedTest::RunTest(const FString&)
{
	FCalmRevealFixture F(ECameraProjectionMode::Orthographic);
	auto* Blocker = F.World->SpawnActor<AActor>();
	auto* Shape = NewObject<UBoxComponent>(Blocker);
	Blocker->SetRootComponent(Shape);
	Shape->SetBoxExtent(FVector(60));
	Shape->SetCollisionProfileName(TEXT("BlockAllDynamic"));
	Shape->RegisterComponent();
	Blocker->SetActorLocation((F.View.Location+F.End())*.5);
	F.PC->SetIgnoreMoveInput(true); // An unrelated owner's lock must survive timeout.
	TestTrue(TEXT("Blocked pan retains bounded gate-opening fallback"),F.Begin());
	auto* Camera = F.Reveal->GetRevealCamera();
	if (!TestNotNull(TEXT("Blocked reveal still has camera"),Camera)) return false;
	F.Tick(2);
	TestTrue(TEXT("Blocked path cannot cut through geometry or choose another angle"),Camera->GetActorLocation().Equals(F.View.Location));
	TestTrue(TEXT("Blocked pan retains original angle"),Camera->GetActorRotation().Equals(F.View.Rotation));
	TestEqual(TEXT("Blocked camera still allows gate opening"),F.Reveal->Phase,ECatrunPuzzleRevealPhase::Opening);
	F.Tick(5.9f);
	TestEqual(TEXT("Guard has not expired prematurely"),F.Reveal->Phase,ECatrunPuzzleRevealPhase::Opening);
	F.Tick(.11f);
	TestEqual(TEXT("Missing gate completion cannot lock beyond eight seconds"),F.Reveal->Phase,ECatrunPuzzleRevealPhase::Inactive);
	TestTrue(TEXT("Timeout restores original view"),F.PC->GetViewTarget()==F.Original);
	TestTrue(TEXT("Unrelated movement lock survives"),F.PC->IsMoveInputIgnored());
	F.PC->SetIgnoreMoveInput(false);
	TestFalse(TEXT("Only reveal's movement lock was released"),F.PC->IsMoveInputIgnored());
	TestFalse(TEXT("Timeout releases look lock and suspension"),F.PC->IsLookInputIgnored() || UCatrunPuzzleSuspension::IsSuspended(F.Cat));
	TestNull(TEXT("Timeout destroys native reveal camera"),F.Reveal->GetRevealCamera());
	return true;
}
#endif
