#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "CoreGlobals.h"
#include "CatrunExitTestTypes.h"
#include "CatrunCheckpointTestBackend.h"
#include "Interaction/CatrunPuzzleSuspension.h"
#include "Monster/CatrunRestartSubsystem.h"
#include "Camera/CameraActor.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/WorldSettings.h"
#include "Kismet/GameplayStatics.h"
#include "Perception/CatrunGroundSupport.h"
#include "TimerManager.h"

namespace
{
    struct FExitLeaseFixture
    {
        UWorld* World;
        ACharacter* Cat;
        APlayerController* PC;
        ACameraActor* Gameplay;
        AActor* Floor;
        ACatrunExitTestActor* Exit;
        UGameInstance* Instance = nullptr;
        TArray<FCatrunStageRoute> PreviousRoutes;
        AActor* Box(FVector Location,FVector Extent)
        {
            auto* Actor=World->SpawnActor<AActor>(); auto* Shape=NewObject<UBoxComponent>(Actor);
            Actor->SetRootComponent(Shape); Shape->SetBoxExtent(Extent); Shape->SetCollisionProfileName(TEXT("BlockAllDynamic"));
            Shape->RegisterComponent(); Actor->SetActorLocation(Location); return Actor;
        }
        FExitLeaseFixture()
        {
            const auto Init=UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false);
            World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Init);
            GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
            World->InitializeActorsForPlay(FURL());
            auto* Routes=GetMutableDefault<UCatrunLevelFlowSettings>(); PreviousRoutes=Routes->Stages; Routes->Stages.Reset();
            auto& First=Routes->Stages.AddDefaulted_GetRef(); First.StageId=TEXT("Stage1"); First.Map=TSoftObjectPtr<UWorld>(FSoftObjectPath(World->GetOutermost()->GetName()));
            auto& Next=Routes->Stages.AddDefaulted_GetRef(); Next.StageId=TEXT("Stage2"); Next.Map=TSoftObjectPtr<UWorld>(FSoftObjectPath(TEXT("/Game/Maps/Stage2.Stage2")));
            Floor=Box(FVector(0,0,-10),FVector(1000,1000,10));
            Cat=World->SpawnActor<ACharacter>(); Cat->GetCapsuleComponent()->SetCapsuleSize(20,24);
            Cat->SetActorLocation(FVector(0,0,26)); Cat->GetCharacterMovement()->SetMovementMode(MOVE_Walking); Cat->GetCharacterMovement()->SetComponentTickEnabled(true);
            PC=World->SpawnActor<APlayerController>();
            // A bare controller is not local in a headless test world. Bind the same
            // ULocalPlayer ownership used by gameplay before exercising local-only admission.
            PC->SetPlayer(NewObject<ULocalPlayer>(GEngine)); PC->Possess(Cat);
            Gameplay=World->SpawnActor<ACameraActor>(); PC->SetViewTarget(Gameplay);
            Exit=World->SpawnActorDeferred<ACatrunExitTestActor>(ACatrunExitTestActor::StaticClass(),FTransform::Identity);
            Exit->Trigger->SetGenerateOverlapEvents(false); Exit->FinishSpawning(FTransform::Identity);
            Exit->Trigger->SetBoxExtent(FVector(70,35,80)); Exit->bRequireCenterInside=Exit->bUseExitTransition=true;
            // Overlap delegates require the WORLD to have begun play. Dispatching only
            // the exit actor populates overlap lists without delivering those delegates.
            World->GetWorldSettings()->NotifyBeginPlay();
        }
        UCatrunFlowSession* Track(FCheckpointBackend& Backend)
        {
            Instance=NewObject<UGameInstance>(); World->SetGameInstance(Instance); Instance->Init();
            auto* Session=Instance->GetSubsystem<UCatrunFlowSession>(); Session->SetSaveBackendForTest(&Backend);
            const FString Package=World->GetOutermost()->GetName();
            Session->AcceptTravel(Package,true,true,ECatrunArrivalRestart::Clear,0); Session->Arrive(Package);
            return Session;
        }
        ~FExitLeaseFixture()
        {
            if (IsValid(Exit) && IsValid(Exit->ExitTransition)) Exit->ExitTransition->ReleaseExitLease();
            World->EndPlay(EEndPlayReason::Quit);
            if (Instance) { Instance->Shutdown(); World->SetGameInstance(nullptr); }
            GetMutableDefault<UCatrunLevelFlowSettings>()->Stages=PreviousRoutes;
            GEngine->DestroyWorldContext(World); World->DestroyWorld(false);
        }
    };

    bool AcquireForTest(FAutomationTestBase& Test, FExitLeaseFixture& F, FText& Failure, const TCHAR* Label)
    {
        const bool bAcquired=F.Exit->ExitTransition->AcquireExitLease(F.Cat,Failure);
        if (!bAcquired)
        {
            const auto* Capsule=F.Cat->GetCapsuleComponent();
            const auto* Move=F.Cat->GetCharacterMovement();
            FCollisionQueryParams Params(SCENE_QUERY_STAT(ExitLeaseFixtureSupport),false,F.Cat);
            Params.AddIgnoredActor(F.Exit);
            FHitResult Hit; FVector Center;
            const bool bSupport=CatrunGround::FindSupport(*Capsule,F.Cat->GetActorLocation(),Move->MaxStepHeight,
                Move->MaxStepHeight+F.Exit->ExitTransition->GroundTolerance,Params,Hit,Center);
            Test.AddInfo(FString::Printf(TEXT("Lease refusal: %s; worldBegun=%d player0=%d local=%d center=%s radius=%.3f halfheight=%.3f mode=%d tick=%d collision=%d camera=%s support=%d supportCenter=%s hit=%s penetrating=%d normal=%s impact=%s"),
                *Failure.ToString(),F.World->HasBegunPlay(),UGameplayStatics::GetPlayerPawn(F.World,0)==F.Cat,
                F.PC->IsLocalController(),*F.Cat->GetActorLocation().ToString(),Capsule->GetScaledCapsuleRadius(),Capsule->GetScaledCapsuleHalfHeight(),
                int32(Move->MovementMode),Move->IsComponentTickEnabled(),Capsule->IsQueryCollisionEnabled(),*GetNameSafe(F.PC->PlayerCameraManager),
                bSupport,*Center.ToString(),*GetNameSafe(Hit.GetActor()),Hit.bStartPenetrating,*Hit.ImpactNormal.ToString(),*Hit.ImpactPoint.ToString()));
        }
        return Test.TestTrue(FString::Printf(TEXT("%s (%s)"),Label,*Failure.ToString()),bAcquired);
    }
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunExitQualificationTest,"Catrun.LevelFlow.ExitQualificationNotifiesBlueprintOnly",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FCatrunExitQualificationTest::RunTest(const FString&)
{
    FExitLeaseFixture F;
    TestTrue(TEXT("Fixture world actually delivers gameplay overlap delegates"),F.World->HasBegunPlay());
    TestTrue(TEXT("Fixture cat is the actual local player zero"),F.Cat->IsLocallyControlled() && UGameplayStatics::GetPlayerPawn(F.World,0)==F.Cat);
    TestFalse(TEXT("Idle exit does not tick"),F.Exit->IsActorTickEnabled());
    F.Cat->SetActorLocation(FVector(-80,0,26)); F.Exit->Trigger->SetGenerateOverlapEvents(true);
    F.Cat->GetCapsuleComponent()->UpdateOverlaps(); F.Exit->Trigger->UpdateOverlaps();
    TestTrue(TEXT("Capsule edge enters broadphase"),F.Exit->Trigger->IsOverlappingActor(F.Cat));
    F.Exit->Tick(0); TestEqual(TEXT("Edge entry does not invoke BP presentation"),F.Exit->Qualified,0);
    F.Cat->SetActorLocation(FVector(-65,0,26)); F.Exit->Tick(0);
    TestEqual(TEXT("Later center entry sends one real inherited BP event"),F.Exit->Qualified,1);
    TestFalse(TEXT("Qualification itself does not acquire gameplay ownership"),F.Exit->ExitTransition->HasExitLease());
    TestFalse(TEXT("Qualification itself never locks or starts presentation"),F.PC->IsMoveInputIgnored());
    F.Exit->Tick(0); TestEqual(TEXT("Repeated interior ticks remain disarmed"),F.Exit->Qualified,1);
    F.Cat->SetActorLocation(FVector(-120,0,26)); F.Cat->GetCapsuleComponent()->UpdateOverlaps();
    F.Cat->SetActorLocation(FVector(-60,0,26)); F.Cat->GetCapsuleComponent()->UpdateOverlaps(); F.Exit->Tick(0);
    TestEqual(TEXT("Leave/reenter permits another BP attempt"),F.Exit->Qualified,2);
    F.Exit->SetActorTransform(FTransform(FRotator(0,70,0),FVector(500,300,0),FVector(2,.5,1)));
    F.Exit->InteriorDirectionLocal=FVector(1,0,0); F.Exit->MinimumInteriorDepth=10;
    TestFalse(TEXT("Rotated/scaled shallow depth rejects"),F.Exit->IsCenterQualified(F.Exit->GetActorTransform().TransformPosition(FVector(5,0,26))));
    TestTrue(TEXT("Rotated/scaled interior depth accepts"),F.Exit->IsCenterQualified(F.Exit->GetActorTransform().TransformPosition(FVector(20,0,26))));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunExitQueryTest,"Catrun.LevelFlow.ExitCollisionQueriesNeverMovePawn",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FCatrunExitQueryTest::RunTest(const FString&)
{
    FExitLeaseFixture F; auto* Lease=F.Exit->ExitTransition.Get(); FText Failure;
    if (!AcquireForTest(*this,F,Failure,TEXT("Grounded character acquires service lease"))) return false;
    const FTransform Start=F.Cat->GetActorTransform();
    TestTrue(TEXT("Supported clear grounded route validates"),Lease->ValidateExitPath({FVector(100,0,26),FVector(200,0,26)},true,Failure));
    TestTrue(TEXT("Airborne route can be queried without forced landing/timing"),Lease->ValidateExitMotion(FVector(200,0,26),FVector(250,0,65),false,Failure));
    F.Box(FVector(150,0,60),FVector(5,100,60));
    TestFalse(TEXT("Full capsule transit detects mid-path blocker"),Lease->ValidateExitMotion(FVector(100,0,26),FVector(200,0,26),true,Failure));
    TestFalse(TEXT("Grounded validation rejects unsupported height"),Lease->ValidateExitMotion(FVector(0,0,100),FVector(50,0,100),true,Failure));
    TestTrue(TEXT("All successful/failed query calls leave exact actor transform unchanged"),F.Cat->GetActorTransform().Equals(Start));
    F.Floor->Destroy();
    F.Box(FVector(-493.5,0,-10),FVector(506.5,1000,10)); // floor ends at X=13
    F.Box(FVector(507.5,0,-10),FVector(492.5,1000,10)); // resumes at X=15
    TestTrue(TEXT("Actual capsule support accepts a narrow seam under an off-center footprint ray"),
        Lease->ValidateExitMotion(FVector(0,0,26),FVector(0,0,26),true,Failure));
    TestFalse(TEXT("Adapter never owns a tick clock"),Lease->PrimaryComponentTick.bCanEverTick);
    TestTrue(TEXT("Explicit lease release succeeds"),Lease->ReleaseExitLease());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunExitLeaseLifetimeTest,"Catrun.LevelFlow.ExitOwnerDestructionRestoresLivePlayer",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FCatrunExitLeaseLifetimeTest::RunTest(const FString&)
{
    for (bool bDestroyComponent : {false,true})
    {
        FExitLeaseFixture F; auto* Lease=F.Exit->ExitTransition.Get(); FText Failure;
        F.PC->SetIgnoreMoveInput(true);
        TestFalse(TEXT("Existing intro owner refuses lease"),Lease->AcquireExitLease(F.Cat,Failure));
        TestTrue(TEXT("Refusal preserves prior lock"),F.PC->IsMoveInputIgnored()); F.PC->SetIgnoreMoveInput(false);
        if (!AcquireForTest(*this,F,Failure,TEXT("Valid lease starts"))) return false;
        TestTrue(TEXT("Hostiles suspend while BP owns lease"),UCatrunPuzzleSuspension::IsSuspended(F.Exit));
        TestFalse(TEXT("Capture cannot steal active flow lease"),F.World->GetSubsystem<UCatrunRestartSubsystem>()->TryBeginCatch());
        TestFalse(TEXT("Generic flow cannot bypass owned BP presentation"),F.World->GetSubsystem<UCatrunLevelFlowSubsystem>()->CompleteStage());
        ACameraActor* Shot=F.World->SpawnActor<ACameraActor>(); Lease->RememberOwnedViewTarget(Shot); F.PC->SetViewTarget(Shot);
        F.Cat->SetActorLocation(FVector(180,0,70)); // simulated actor transform supplied externally by Sequence
        F.PC->SetIgnoreMoveInput(true); F.PC->SetIgnoreLookInput(true);
        if (bDestroyComponent) Lease->DestroyComponent(); else F.Exit->Destroy();
        TestTrue(TEXT("Owner lifetime ends without destroying the player"),IsValid(F.Cat));
        TestTrue(TEXT("Owner destruction restores supported captured transform"),F.Cat->GetActorLocation().Equals(FVector(0,0,26),.1));
        TestEqual(TEXT("Surviving player never remains MOVE_None"),F.Cat->GetCharacterMovement()->MovementMode,TEnumAsByte<EMovementMode>(MOVE_Walking));
        TestTrue(TEXT("Movement tick restored"),F.Cat->GetCharacterMovement()->IsComponentTickEnabled());
        TestEqual(TEXT("Registered presentation view returns to prior camera"),F.PC->GetViewTarget(),static_cast<AActor*>(F.Gameplay));
        TestTrue(TEXT("Later owner input increment remains"),F.PC->IsMoveInputIgnored());
        F.PC->SetIgnoreMoveInput(false); F.PC->SetIgnoreLookInput(false);
        TestFalse(TEXT("Exactly one owned move lock released"),F.PC->IsMoveInputIgnored());
        TestFalse(TEXT("Exactly one owned look lock released"),F.PC->IsLookInputIgnored());
        TestFalse(TEXT("Suspension ends immediately"),UCatrunPuzzleSuspension::IsSuspended(F.Cat));
        TestFalse(TEXT("No lingering source flow reservation"),F.World->GetSubsystem<UCatrunLevelFlowSubsystem>()->IsTransitioning());
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunExitSaveCallbackTest,"Catrun.LevelFlow.ExitSaveCallbackCancellationAndActualPending",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FCatrunExitSaveCallbackTest::RunTest(const FString&)
{
    FExitLeaseFixture F; auto* Lease=F.Exit->ExitTransition.Get(); FText Failure;
    auto AdvanceTimerFrame=[&F]()
    {
        // TimerManager rejects a second Tick in the same engine frame. These
        // synchronous test steps represent separate gameplay frames.
        ++GFrameCounter;
        F.World->GetTimerManager().Tick(.01f);
    };
    auto* Observer=NewObject<UCatrunExitTestObserver>(); Observer->Lease=Lease;
    Lease->OnCheckpointSaveFinished.AddDynamic(Observer,&UCatrunExitTestObserver::Saved);
    if (!AcquireForTest(*this,F,Failure,TEXT("Lease starts without cinematic native machinery"))) return false;
    TestTrue(TEXT("Untracked request uses the asynchronous event contract"),Lease->RequestExitCheckpointSave());
    TestFalse(TEXT("Untracked request never labels a fake save pending"),Lease->IsCheckpointSavePending());
    Lease->ReleaseExitLease(); AdvanceTimerFrame();
    TestEqual(TEXT("Canceled run cannot receive stale next-tick result"),Observer->Results,0);
    FCheckpointBackend Backend; Backend.bExists=false; F.Track(Backend);
    AcquireForTest(*this,F,Failure,TEXT("New lease can reacquire after cancellation"));
    TestFalse(TEXT("Travel rejected before checkpoint service success"),Lease->CommitExitTravel());
    TestTrue(TEXT("Tracked request accepted"),Lease->RequestExitCheckpointSave());
    TestTrue(TEXT("Pending flag covers real backend I/O"),Lease->IsCheckpointSavePending());
    Lease->ReleaseExitLease(); Backend.Drain(); AdvanceTimerFrame();
    TestEqual(TEXT("Late actual I/O callback cannot resume canceled BP run"),Observer->Results,0);
    AcquireForTest(*this,F,Failure,TEXT("Third lease starts"));
    Observer->bReleaseOnResult=true;
    TestTrue(TEXT("Third tracked request is accepted"),Lease->RequestExitCheckpointSave());
    TestTrue(TEXT("Third request has actual backend I/O pending"),Lease->IsCheckpointSavePending());
    Backend.Drain();
    TestFalse(TEXT("Completed I/O clears pending before event delivery"),Lease->IsCheckpointSavePending());
    TestEqual(TEXT("Actual success remains deferred until its next gameplay frame"),Observer->Results,0);
    TestTrue(TEXT("Lease remains active until its result listener cancels"),Lease->HasExitLease());
    AdvanceTimerFrame();
    TestEqual(TEXT("Exactly one actual result callback"),Observer->Results,1);
    TestTrue(TEXT("Actual tracked success is reported"),Observer->bLastSuccess && Observer->bLastTracked);
    TestFalse(TEXT("Synchronous result-listener cancel stays canceled"),Lease->HasExitLease());
    TestFalse(TEXT("Callback cancellation cannot reactivate a component tick"),Lease->IsComponentTickEnabled());
    TestFalse(TEXT("Service callback never creates a fade"),F.PC->PlayerCameraManager->bEnableFading);
    TestEqual(TEXT("Canceled callback does not forward into abandoned BP owner"),F.Exit->Saved,0);
    TestTrue(TEXT("No old callback issues travel"),GEngine->GetWorldContextFromWorld(F.World)->TravelURL.IsEmpty());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunExitTeardownTokenTest,"Catrun.LevelFlow.ExitTeardownPreservesOnlyAcceptedArrival",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FCatrunExitTeardownTokenTest::RunTest(const FString&)
{
    for (bool bWorldTeardown : {false,true})
    {
        FExitLeaseFixture F; FCheckpointBackend Backend; Backend.bExists=false; auto* Session=F.Track(Backend);
        auto* Lease=F.Exit->ExitTransition.Get(); FText Failure;
        if (!AcquireForTest(*this,F,Failure,TEXT("Lease starts"))) return false;
        Lease->RequestExitCheckpointSave(); Backend.Drain(); F.World->GetTimerManager().Tick(.01f);
        if (!TestTrue(TEXT("Explicit BP travel call accepts existing destination after save"),Lease->CommitExitTravel())) return false;
        const FString Destination=TEXT("/Game/Maps/Stage2");
        TestEqual(TEXT("Only the accepted portal commit queues the Stage2 arrival option"),
            GEngine->GetWorldContextFromWorld(F.World)->TravelURL, Destination + TEXT("?FromStage1Portal"));
        if (bWorldTeardown)
        {
            F.World->bIsTearingDown=true; F.PC->UnPossess(); Lease->EndPlay(EEndPlayReason::LevelTransition); F.World->bIsTearingDown=false;
            TestEqual(TEXT("Travel subject teardown does not notify a live-world BP abort"),F.Exit->TravelFailures,0);
            TestTrue(TEXT("Real travel teardown preserves accepted-arrival checkpoint token"),Session->Arrive(Destination));
        }
        else
        {
            F.Exit->Destroy();
            TestTrue(TEXT("Destroying owner in live world cancels its queued URL"),GEngine->GetWorldContextFromWorld(F.World)->TravelURL.IsEmpty());
            TestFalse(TEXT("Destroyed owner cannot later advance destination checkpoint"),Session->Arrive(Destination));
        }
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunPlainStage1CompletionTest, "Catrun.LevelFlow.PlainStage1CompletionOmitsPortalArrival", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunPlainStage1CompletionTest::RunTest(const FString&)
{
    FExitLeaseFixture F;
    auto* Flow = F.World->GetSubsystem<UCatrunLevelFlowSubsystem>();
    auto* Context = GEngine->GetWorldContextFromWorld(F.World);
    TestFalse(TEXT("An exit component without a lease cannot issue portal travel"), Flow->CompleteStageForExit(F.Exit->ExitTransition));
    TestTrue(TEXT("A rejected exit leaves the engine travel URL empty"), Context->TravelURL.IsEmpty());
    TestTrue(TEXT("The ordinary Stage1 route still accepts completion"), Flow->CompleteStage());
    TestEqual(TEXT("Plain completion queues Stage2 with no arrival option"), Context->TravelURL, FString(TEXT("/Game/Maps/Stage2")));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunExitSubjectLifetimeTest,"Catrun.LevelFlow.ExitSubjectLossRejectsLateSave",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FCatrunExitSubjectLifetimeTest::RunTest(const FString&)
{
    // Exercise real possession notifications and actor EndPlay, not a synthetic lease state mutation.
    for (int32 Loss=0;Loss<4;++Loss)
    {
        FExitLeaseFixture F; FCheckpointBackend Backend; Backend.bExists=false; F.Track(Backend);
        auto* Lease=F.Exit->ExitTransition.Get(); FText Failure;
        auto* Replacement=F.World->SpawnActor<ACharacter>(); Replacement->SetActorLocation(FVector(500,0,100));
        auto* Observer=NewObject<UCatrunExitTestObserver>(); Observer->Lease=Lease;
        Lease->OnCheckpointSaveFinished.AddDynamic(Observer,&UCatrunExitTestObserver::Saved);
        if (!AcquireForTest(*this,F,Failure,TEXT("Lease acquires before subject loss"))) return false;
        TestTrue(TEXT("Actual tracked checkpoint queued"),Lease->RequestExitCheckpointSave());
        TestTrue(TEXT("Backend pending before ownership change"),Lease->IsCheckpointSavePending());
        if (Loss==0) F.PC->UnPossess();
        else if (Loss==1) F.PC->Possess(Replacement);
        else if (Loss==2) F.Cat->Destroy();
        else F.PC->Destroy();
        TestFalse(TEXT("Subject loss immediately releases lease without tick"),Lease->HasExitLease());
        TestFalse(TEXT("Subject loss releases source flow reservation"),F.World->GetSubsystem<UCatrunLevelFlowSubsystem>()->IsTransitioning());
        TestFalse(TEXT("Subject loss releases hostile suspension"),UCatrunPuzzleSuspension::IsSuspended(F.Exit));
        TestEqual(TEXT("BP receives exactly one failure to stop its own presentation"),F.Exit->TravelFailures,1);
        if (Loss!=3)
        {
            TestFalse(TEXT("Captured controller has no stale move lock"),F.PC->IsMoveInputIgnored());
            TestFalse(TEXT("Captured controller has no stale look lock"),F.PC->IsLookInputIgnored());
        }
        if (Loss!=2)
        {
            TestTrue(TEXT("Surviving old pawn movement tick restored"),F.Cat->GetCharacterMovement()->IsComponentTickEnabled());
            TestTrue(TEXT("Surviving old pawn leaves MOVE_None"),F.Cat->GetCharacterMovement()->MovementMode!=MOVE_None);
        }
        Backend.Drain(); F.World->GetTimerManager().Tick(.01f);
        TestEqual(TEXT("Late backend result cannot reach abandoned lease multicast"),Observer->Results,0);
        TestEqual(TEXT("Late backend result cannot resume BP save completion"),F.Exit->Saved,0);
        TestFalse(TEXT("Lost subject cannot commit travel"),Lease->CommitExitTravel());
        TestTrue(TEXT("Lost subject never queues a destination"),GEngine->GetWorldContextFromWorld(F.World)->TravelURL.IsEmpty());
        TestEqual(TEXT("Late callback cannot duplicate abort"),F.Exit->TravelFailures,1);
    }
    return true;
}
#endif
