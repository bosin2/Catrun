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
#include "Math/InverseRotationMatrix.h"
#include "SceneView.h"

namespace
{
	FVector2D ProjectMarker(FMinimalViewInfo View, const FVector& Marker)
	{
		// Use the renderer's public projection path, including camera-to-owner
		// correction, to compare what the player sees rather than actor positions.
		FSceneViewProjectionData Projection;
		Projection.ViewOrigin = View.Location;
		Projection.ViewRotationMatrix = FInverseRotationMatrix(View.Rotation) * FMatrix(
			FPlane(0,0,1,0), FPlane(1,0,0,0), FPlane(0,1,0,0), FPlane(0,0,0,1));
		const FIntRect Rect(0,0,1920,1080);
		Projection.SetViewRectangle(Rect);
		FMinimalViewInfo::CalculateProjectionMatrixGivenViewRectangle(View,AspectRatio_MaintainXFOV,Rect,Projection);
		FVector2D Pixel = FVector2D::ZeroVector;
		FSceneView::ProjectWorldToScreen(Marker,Rect,Projection.ComputeViewProjectionMatrix(),Pixel);
		return Pixel;
	}
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
			Original->SetActorLocationAndRotation(View.Location, View.Rotation);
			Original->GetCameraComponent()->ProjectionMode = Projection;
			Original->GetCameraComponent()->OrthoWidth = View.OrthoWidth;
			Original->GetCameraComponent()->FieldOfView = View.FOV;
			Original->GetCameraComponent()->bAutoCalculateOrthoPlanes = View.bAutoCalculateOrthoPlanes;
			Original->GetCameraComponent()->bUpdateOrthoPlanes = View.bUpdateOrthoPlanes;
			Original->GetCameraComponent()->bUseCameraHeightAsViewTarget = View.bUseCameraHeightAsViewTarget;
			Original->GetCameraComponent()->OrthoNearClipPlane = View.OrthoNearClipPlane;
			Original->GetCameraComponent()->OrthoFarClipPlane = View.OrthoFarClipPlane;
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

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCalmPuzzleRevealOrthoAnchorTest,"Catrun.Stage2.CalmRevealProbesRenderedOrthoOrigin",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FCalmPuzzleRevealOrthoAnchorTest::RunTest(const FString&)
{
	FCalmRevealFixture F(ECameraProjectionMode::Orthographic);
	// Reproduce the real Stage2 arrangement: the logical camera anchor is at
	// pawn height, overlapping the statue, while UE renders from behind it.
	F.View.Location = FVector(0,0,26.25);
	F.View.OrthoWidth = 1170;
	F.View.bAutoCalculateOrthoPlanes = true;
	F.View.bUpdateOrthoPlanes = true;
	F.View.bUseCameraHeightAsViewTarget = true;
	F.View.OrthoNearClipPlane = -768;
	F.Original->SetActorLocation(F.View.Location);
	F.PC->PlayerCameraManager->SetCameraCachePOV(F.View);
	auto* Statue = F.World->SpawnActor<AActor>();
	auto* Shape = NewObject<UBoxComponent>(Statue);
	Statue->SetRootComponent(Shape);
	Shape->SetBoxExtent(FVector(60,60,75));
	Shape->SetCollisionProfileName(TEXT("BlockAllDynamic"));
	Shape->RegisterComponent();
	Statue->SetActorLocation(FVector(55,-55,75));
	FCollisionQueryParams Params;
	Params.AddIgnoredActor(F.Cat);
	TestTrue(TEXT("The logical camera origin really overlaps camera-blocking geometry"),
		F.World->OverlapBlockingTestByChannel(F.View.Location,FQuat::Identity,ECC_Camera,FCollisionShape::MakeSphere(10),Params));
	TestTrue(TEXT("Reveal acquires from the obstructed logical anchor"),F.Begin());
	auto* Camera = F.Reveal->GetRevealCamera();
	if (!TestNotNull(TEXT("Owned camera exists"),Camera)) return false;
	TestTrue(TEXT("No physical camera retreat changes the authored view"),Camera->GetActorLocation().Equals(F.View.Location));
	F.Tick(2);
	const FVector Expected = F.Focus-F.View.Rotation.Vector()*100;
	TestTrue(TEXT("Rendered-origin sweep permits the visible pan past the nearby statue"),Camera->GetActorLocation().Equals(Expected,.01));
	TestEqual(TEXT("Projection width remains unchanged"),Camera->GetCameraComponent()->OrthoWidth,1170.f);
	TestTrue(TEXT("Camera rotation remains unchanged"),Camera->GetActorRotation().Equals(F.View.Rotation,.001));
	TestEqual(TEXT("Near clip is still the authored value, not a second plane correction"),Camera->GetCameraComponent()->OrthoNearClipPlane,-768.f);
	TestTrue(TEXT("Engine automatic plane correction remains enabled"),bool(Camera->GetCameraComponent()->bAutoCalculateOrthoPlanes) && bool(Camera->GetCameraComponent()->bUpdateOrthoPlanes));
	TestEqual(TEXT("Gate is allowed to open after the actual pan"),F.Reveal->Phase,ECatrunPuzzleRevealPhase::Opening);
	F.Reveal->CancelReveal();
	// A real wall on the resolved path must still reject it. No statue/floor
	// actor or collision channel is exempted by the orthographic correction.
	Shape->SetBoxExtent(FVector(1000,50,1000));
	Statue->SetActorLocation(FVector(150,-350,500));
	TestTrue(TEXT("Second reveal acquires with a wall blocking the route"),F.Begin());
	Camera = F.Reveal->GetRevealCamera();
	if (!TestNotNull(TEXT("Blocked reveal camera exists"),Camera)) return false;
	F.Tick(2);
	TestTrue(TEXT("Real geometry still blocks the corrected path"),Camera->GetActorLocation().Equals(F.View.Location));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCalmPuzzleRevealLiveReturnTest,"Catrun.Stage2.CalmRevealReturnsToMovingGameplayComponent",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FCalmPuzzleRevealLiveReturnTest::RunTest(const FString&)
{
	FCalmRevealFixture F(ECameraProjectionMode::Orthographic);
	TestTrue(TEXT("Reveal starts"),F.Begin());
	auto* Camera = F.Reveal->GetRevealCamera();
	if (!TestNotNull(TEXT("Owned camera exists"),Camera)) return false;
	F.Tick(2);
	F.Original->AddActorWorldOffset(FVector(120,70,0));
	F.Original->GetCameraComponent()->SetRelativeLocation(FVector(25,0,0));
	F.Reveal->GateOpened(TEXT("Calm"));
	F.Tick(.8f);
	FMinimalViewInfo LiveView;
	F.Original->CalcCamera(0.f,LiveView);
	TestTrue(TEXT("Return midpoint uses the actual camera component, including its offset"),Camera->GetActorLocation().Equals((F.End()+LiveView.Location)*.5,.01));
	// Follow can continue settling after return has already started.
	F.Original->AddActorWorldOffset(FVector(50,20,0));
	F.Original->CalcCamera(0.f,LiveView);
	F.Tick(.799f);
	TestTrue(TEXT("Last visible return frame converges to the updated gameplay view"),Camera->GetActorLocation().Equals(LiveView.Location,.01));
	F.Tick(.002f);
	TestEqual(TEXT("Normal handoff completes"),F.Reveal->Phase,ECatrunPuzzleRevealPhase::Inactive);
	TestTrue(TEXT("Gameplay view owner is restored"),F.PC->GetViewTarget()==F.Original);
	TestFalse(TEXT("Input locks and suspension are released"),F.PC->IsMoveInputIgnored() || F.PC->IsLookInputIgnored() || UCatrunPuzzleSuspension::IsSuspended(F.Cat));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCalmPuzzleRevealProjectedHandoffTest,"Catrun.Stage2.CalmRevealPreservesProjectedOwnerOffsetAtHandoffs",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FCalmPuzzleRevealProjectedHandoffTest::RunTest(const FString&)
{
	FCalmRevealFixture F(ECameraProjectionMode::Orthographic);
	auto* OriginalCamera = F.Original->GetCameraComponent();
	OriginalCamera->OrthoWidth = 1170;
	OriginalCamera->bAutoCalculateOrthoPlanes = true;
	OriginalCamera->bUpdateOrthoPlanes = true;
	OriginalCamera->bUseCameraHeightAsViewTarget = true;
	// Match the measured Stage2 owner-component difference, in world space.
	F.Original->SetActorLocation(FVector(55,55,26.25));
	OriginalCamera->SetWorldLocation(FVector(0,0,26.25));
	F.Original->CalcCamera(0.f,F.View);
	F.PC->PlayerCameraManager->SetCameraCachePOV(F.View);
	TestTrue(TEXT("Offset gameplay camera acquires reveal"),F.Begin());
	auto* Camera = F.Reveal->GetRevealCamera();
	if (!TestNotNull(TEXT("Reveal camera exists"),Camera)) return false;
	const FVector Markers[] = {F.Focus,FVector(100,100,50),FVector(-150,200,0)};
	FMinimalViewInfo OwnedView;
	Camera->CalcCamera(0.f,OwnedView);
	for (const FVector& Marker : Markers)
		TestTrue(TEXT("Acquisition preserves marker pixels despite a different owner offset"),
			ProjectMarker(OwnedView,Marker).Equals(ProjectMarker(F.View,Marker),.01));
	F.Tick(2);
	F.Reveal->GateOpened(TEXT("Calm"));
	F.Original->AddActorWorldOffset(FVector(120,70,0));
	F.Tick(.8f);
	F.Original->AddActorWorldOffset(FVector(30,20,0));
	F.Tick(.799f);
	Camera->CalcCamera(0.f,OwnedView);
	F.Tick(.002f);
	FMinimalViewInfo RestoredView;
	F.PC->GetViewTarget()->CalcCamera(0.f,RestoredView);
	for (const FVector& Marker : Markers)
		TestTrue(TEXT("Last return frame and restored gameplay frame have matching marker pixels"),
			ProjectMarker(OwnedView,Marker).Equals(ProjectMarker(RestoredView,Marker),.01));
	TestEqual(TEXT("Offset-aware handoff completes"),F.Reveal->Phase,ECatrunPuzzleRevealPhase::Inactive);
	TestFalse(TEXT("Handoff releases only its gameplay locks"),F.PC->IsMoveInputIgnored() || F.PC->IsLookInputIgnored() || UCatrunPuzzleSuspension::IsSuspended(F.Cat));
	return true;
}
#endif
