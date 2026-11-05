#include "CatrunExitTransitionComponent.h"
#include "CatrunLevelFlow.h"
#include "Interaction/CatrunBasketInteractionComponent.h"
#include "Interaction/CatrunPuzzleSuspension.h"
#include "Perception/CatrunGroundSupport.h"
#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/CapsuleComponent.h"
#include "Components/InputComponent.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "TimerManager.h"

DEFINE_LOG_CATEGORY_STATIC(LogCatrunExit, Log, All);

UCatrunExitTransitionComponent::UCatrunExitTransitionComponent()
{
    PrimaryComponentTick.bCanEverTick = false;
    PrimaryComponentTick.bStartWithTickEnabled = false;
}

bool UCatrunExitTransitionComponent::IsCurrentLease(uint64 Serial) const
{
    return Serial == LeaseSerial && bLeaseActive && !bEnding && !bCleaning && IsValid(this)
        && GetOwner() && !GetOwner()->IsActorBeingDestroyed()
        && Cat.IsValid() && !Cat->IsActorBeingDestroyed() && Controller.IsValid() && !Controller->IsActorBeingDestroyed()
        && Controller->GetPawn() == Cat.Get() && Cat->GetController() == Controller.Get();
}

void UCatrunExitTransitionComponent::OnLeasePossessionChanged(APawn* OldPawn, APawn* NewPawn)
{
    if (bLeaseActive && (NewPawn != Cat.Get() || !Cat.IsValid() || Cat->GetController() != Controller.Get()))
        InvalidateSubjectLease(!GetWorld() || GetWorld()->bIsTearingDown);
}

void UCatrunExitTransitionComponent::OnLeaseSubjectEndPlay(AActor* Actor, EEndPlayReason::Type Reason)
{
    const bool bWorldEnding = !GetWorld() || GetWorld()->bIsTearingDown || Reason == EEndPlayReason::LevelTransition
        || Reason == EEndPlayReason::EndPlayInEditor || Reason == EEndPlayReason::Quit;
    InvalidateSubjectLease(bWorldEnding);
}

void UCatrunExitTransitionComponent::InvalidateSubjectLease(bool bWorldEnding)
{
    if (!bLeaseActive || bCleaning || bEnding) return;
    // Prevent a synchronous failure listener from reacquiring while the subject-loss notification unwinds.
    TGuardValue<bool> Acquiring(bAcquiring, true);
    CleanupLease(!bWorldEnding, bWorldEnding);
    if (bWorldEnding) return;
    const uint64 Serial = LeaseSerial;
    const FText Reason = NSLOCTEXT("Catrun", "ExitSubjectLost", "Exit character or controller ownership ended.");
    OnTravelFailed.Broadcast(Reason);
    if (Serial == LeaseSerial && !bEnding && IsValid(GetOwner()) && !GetOwner()->IsActorBeingDestroyed())
        if (auto* Exit = Cast<ACatrunStageExit>(GetOwner())) Exit->ExitTravelFailed(Reason);
}

bool UCatrunExitTransitionComponent::AcquireExitLease(APawn* Pawn, FText& Failure)
{
    Failure = FText::GetEmpty();
    auto Reject = [&Failure](const TCHAR* Detail) { Failure = FText::FromString(Detail); return false; };
    if (bAcquiring || bCleaning || bEnding || bLeaseActive) return Reject(TEXT("Exit lease is already active or ending."));
    TGuardValue<bool> Acquiring(bAcquiring, true);
    auto* Character = Cast<ACharacter>(Pawn);
    auto* PC = Character ? Cast<APlayerController>(Character->GetController()) : nullptr;
    auto* LevelFlow = UCatrunLevelFlowSubsystem::Get(this);
    auto* Guard = UCatrunPuzzleSuspension::Get(this);
    if (!Character || !PC || !PC->IsLocalController() || Pawn != UGameplayStatics::GetPlayerPawn(this, 0)
        || !LevelFlow || !Guard || GetWorld()->IsPaused() || PC->IsMoveInputIgnored() || PC->IsLookInputIgnored()
        || !PC->PlayerCameraManager || !PC->GetViewTarget() || !PC->GetViewTarget()->FindComponentByClass<UCameraComponent>()
        || PC->PlayerCameraManager->bEnableFading) return Reject(TEXT("Gameplay input/camera is owned by another action."));
    auto* Move = Character->GetCharacterMovement();
    if (!Move || Move->MovementMode != MOVE_Walking || !Move->IsComponentTickEnabled()
        || !Character->GetCapsuleComponent()->IsQueryCollisionEnabled() || Character->GetRootComponent() != Character->GetCapsuleComponent()
        || !Character->GetCapsuleComponent()->GetUpVector().Equals(FVector::UpVector, .001))
        return Reject(TEXT("Exit lease requires a grounded upright collision-enabled character."));
    if (const auto* Actions = Pawn->FindComponentByClass<UCatrunBasketInteractionComponent>(); Actions && (Actions->Busy || Actions->IsHidden))
        return Reject(TEXT("The character is performing another interaction."));
    if (!FMath::IsFinite(MaximumPathStep) || MaximumPathStep < 1 || MaximumPathStep > 10
        || !FMath::IsFinite(GroundTolerance) || GroundTolerance < .1f || GroundTolerance > 5)
        return Reject(TEXT("Invalid collision query tolerances."));
    Cat = Character;
    FVector Ground;
    if (!FindGround(Character->GetActorLocation(), Ground) || !CapsuleFits(Character->GetActorLocation())
        || FMath::Abs(Ground.Z - Character->GetActorLocation().Z) > GroundTolerance)
    { Cat.Reset(); return Reject(TEXT("Character start is obstructed or unsupported.")); }
    if (!LevelFlow->ReserveExitTransition(this)) { Cat.Reset(); return Reject(TEXT("Another flow owns travel or gameplay.")); }
    Flow = LevelFlow; bOwnReservation = true;
    if (!Guard->Acquire(this)) { CleanupLease(false, false); return Reject(TEXT("Hostile suspension is already owned.")); }
    Suspension = Guard; bOwnSuspension = true;
    Controller = PC; PreviousView = PC->GetViewTarget(); CapturedTransform = Character->GetActorTransform();
    SavedMovementMode = Move->MovementMode; SavedCustomMode = Move->CustomMovementMode;
    bSavedMovementTick = Move->IsComponentTickEnabled(); bSavedControllerYaw = Character->bUseControllerRotationYaw;
    const uint64 Serial = ++LeaseSerial;
    bLeaseActive = true; bCheckpointReady = bSavePending = bTravelCommitted = false;
    PC->OnPossessedPawnChanged.AddDynamic(this, &UCatrunExitTransitionComponent::OnLeasePossessionChanged);
    PC->OnEndPlay.AddDynamic(this, &UCatrunExitTransitionComponent::OnLeaseSubjectEndPlay);
    Character->OnEndPlay.AddDynamic(this, &UCatrunExitTransitionComponent::OnLeaseSubjectEndPlay);
    PC->SetIgnoreMoveInput(true); PC->SetIgnoreLookInput(true); bOwnInput = true;
    InputBlocker = NewObject<UInputComponent>(PC);
    InputBlocker->Priority = MAX_int32; InputBlocker->bBlockInput = true;
    InputBlocker->RegisterComponent(); PC->PushInputComponent(InputBlocker);
    bOwnMovement = true;
    Move->SetComponentTickEnabled(false); Character->bUseControllerRotationYaw = false;
    Character->ConsumeMovementInputVector(); Move->StopMovementImmediately();
    Move->SetMovementMode(MOVE_None);
    // Movement-mode notifications can synchronously destroy/cancel the owning Blueprint.
    if (IsCurrentLease(Serial)) if (auto* Exit=Cast<ACatrunStageExit>(GetOwner())) Exit->RefreshExitTick();
    return IsCurrentLease(Serial);
}

void UCatrunExitTransitionComponent::RememberOwnedViewTarget(AActor* ViewTarget)
{
    if (bLeaseActive && IsValid(ViewTarget) && ViewTarget->GetWorld() == GetWorld()) OwnedViews.AddUnique(ViewTarget);
}

bool UCatrunExitTransitionComponent::FindGround(const FVector& Position, FVector& GroundCenter) const
{
    const auto* Character = Cat.Get();
    if (!Character || Position.ContainsNaN()) return false;
    const auto* Capsule = Character->GetCapsuleComponent();
    const auto* Move = Character->GetCharacterMovement();
    const float Step = FMath::Max(0.f, Move->MaxStepHeight);
    FCollisionQueryParams Params(SCENE_QUERY_STAT(CatrunExitFloor), false, Character);
    Params.AddIgnoredActor(GetOwner());
    FHitResult Hit;
    return CatrunGround::FindSupport(*Capsule, Position, Step, Step + GroundTolerance, Params, Hit, GroundCenter)
        && Hit.ImpactNormal.Z >= Move->GetWalkableFloorZ();
}

bool UCatrunExitTransitionComponent::CapsuleFits(const FVector& Position) const
{
    const auto* Character = Cat.Get();
    if (!Character || Position.ContainsNaN()) return false;
    const auto* Capsule = Character->GetCapsuleComponent();
    FCollisionQueryParams Params(SCENE_QUERY_STAT(CatrunExitFit), false, Character); Params.AddIgnoredActor(GetOwner());
    return !GetWorld()->OverlapBlockingTestByChannel(Position, FQuat::Identity, Capsule->GetCollisionObjectType(),
        FCollisionShape::MakeCapsule(Capsule->GetScaledCapsuleRadius(),Capsule->GetScaledCapsuleHalfHeight()), Params,
        FCollisionResponseParams(Capsule->GetCollisionResponseToChannels()));
}

bool UCatrunExitTransitionComponent::ValidateExitMotion(FVector From, FVector To, bool bGrounded, FText& Failure) const
{
    Failure = FText::GetEmpty();
    auto Reject = [&Failure](const TCHAR* Detail) { Failure = FText::FromString(Detail); return false; };
    const auto* Character = Cat.Get();
    if (!IsCurrentLease(LeaseSerial) || From.ContainsNaN() || To.ContainsNaN()) return Reject(TEXT("No live lease or invalid path coordinates."));
    const double Distance = FVector::Dist(From, To);
    if (!FMath::IsFinite(Distance) || Distance > MaximumPathStep * 4096.0) return Reject(TEXT("Path query exceeds its bounded sampling budget."));
    const auto* Capsule = Character->GetCapsuleComponent();
    FCollisionQueryParams Params(SCENE_QUERY_STAT(CatrunExitSweep), false, Character); Params.AddIgnoredActor(GetOwner());
    const FCollisionShape Shape = FCollisionShape::MakeCapsule(Capsule->GetScaledCapsuleRadius(),Capsule->GetScaledCapsuleHalfHeight());
    const FCollisionResponseParams Responses(Capsule->GetCollisionResponseToChannels());
    const int32 Steps = FMath::Max(1,FMath::CeilToInt(Distance / MaximumPathStep));
    FVector Last = From;
    if (!CapsuleFits(From)) return Reject(TEXT("Path begins in blocking geometry."));
    for (int32 Step = 0; Step <= Steps; ++Step)
    {
        const FVector Next = FMath::Lerp(From,To,double(Step)/Steps);
        FHitResult Hit;
        if (GetWorld()->SweepSingleByChannel(Hit,Last,Next,FQuat::Identity,Capsule->GetCollisionObjectType(),Shape,Params,Responses)
            || !CapsuleFits(Next)) return Reject(TEXT("Capsule path is blocked."));
        if (bGrounded)
        {
            FVector Ground;
            if (!FindGround(Next,Ground) || FMath::Abs(Ground.Z-Next.Z)>GroundTolerance)
                return Reject(TEXT("Grounded path is unsupported or does not follow floor height."));
        }
        Last=Next;
    }
    return true;
}

bool UCatrunExitTransitionComponent::ValidateExitPath(const TArray<FVector>& WorldPoints, bool bGrounded, FText& Failure) const
{
    if (WorldPoints.IsEmpty() || WorldPoints.Num()>256 || !Cat.IsValid())
    { Failure=FText::FromString(TEXT("Path requires 1..256 points and a live character lease.")); return false; }
    FVector Previous=Cat->GetActorLocation();
    for (const FVector& Point : WorldPoints)
    {
        if (!ValidateExitMotion(Previous,Point,bGrounded,Failure)) return false;
        Previous=Point;
    }
    return true;
}

bool UCatrunExitTransitionComponent::RequestExitCheckpointSave()
{
    if (!IsCurrentLease(LeaseSerial) || bSavePending || bTravelCommitted) return false;
    auto* Instance=GetWorld()->GetGameInstance();
    auto* Session=Instance ? Instance->GetSubsystem<UCatrunFlowSession>() : nullptr;
    const FString Package=GetWorld()->GetOutermost()->GetName();
    const uint64 Lease=LeaseSerial, Request=++SaveRequestSerial;
    bCheckpointReady=false;
    if (!Session || !Session->IsTrackingWorld(Package))
    {
        DeliverSaveResult(Lease,Request,true,false,FText::GetEmpty());
        return true;
    }
    bSavePending=true;
    const uint64 Operation=Session->SaveCurrentCheckpoint(Package,
        [Weak=TWeakObjectPtr<UCatrunExitTransitionComponent>(this),Lease,Request](bool bOK,const FString& Error)
        {
            if (auto* Self=Weak.Get(); Self && Self->IsCurrentLease(Lease) && Self->SaveRequestSerial==Request)
                Self->DeliverSaveResult(Lease,Request,bOK,true,bOK ? NSLOCTEXT("Catrun","ExitSaved","저장 완료") : FText::FromString(Error));
        });
    if (!Operation) DeliverSaveResult(Lease,Request,false,true,FText::FromString(TEXT("Tracked world is not an exact configured checkpoint route.")));
    return true;
}

void UCatrunExitTransitionComponent::DeliverSaveResult(uint64 Lease,uint64 Request,bool bSuccess,bool bTracked,const FText& Status)
{
    if (!IsCurrentLease(Lease) || SaveRequestSerial!=Request) return;
    bSavePending=false; bCheckpointReady=bSuccess;
    GetWorld()->GetTimerManager().SetTimerForNextTick(FTimerDelegate::CreateWeakLambda(this,[this,Lease,Request,bSuccess,bTracked,Status]
    {
        if (!IsCurrentLease(Lease) || SaveRequestSerial!=Request) return;
        OnCheckpointSaveFinished.Broadcast(bSuccess,bTracked,Status);
        if (!IsCurrentLease(Lease) || SaveRequestSerial!=Request) return;
        if (auto* Exit=Cast<ACatrunStageExit>(GetOwner())) Exit->ExitCheckpointSaveFinished(bSuccess,bTracked,Status);
    }));
}

bool UCatrunExitTransitionComponent::CanCommitExitTravel() const
{
    return IsCurrentLease(LeaseSerial) && bCheckpointReady && !bSavePending && !bTravelCommitted;
}

bool UCatrunExitTransitionComponent::CommitExitTravel()
{
    if (!CanCommitExitTravel() || !Flow.IsValid()) return false;
    const uint64 Serial=LeaseSerial;
    const bool bAccepted=Flow->CompleteStageForExit(this);
    if (IsCurrentLease(Serial)) bTravelCommitted=bAccepted;
    return bAccepted;
}

void UCatrunExitTransitionComponent::NotifyTravelFailure(const FString& Reason)
{
    if (!IsCurrentLease(LeaseSerial)) return;
    const uint64 Serial=LeaseSerial;
    bTravelCommitted=false;
    const FText Text=FText::FromString(Reason);
    OnTravelFailed.Broadcast(Text);
    if (IsCurrentLease(Serial)) if (auto* Exit=Cast<ACatrunStageExit>(GetOwner())) Exit->ExitTravelFailed(Text);
}

bool UCatrunExitTransitionComponent::RestoreStartSafely()
{
    auto* Character=Cat.Get();
    if (!Character || Character->IsActorBeingDestroyed()) return false;
    FVector Ground;
    const FVector Start=CapturedTransform.GetLocation();
    // This is explicit abort rollback, never normal cinematic movement. Check the full capsule and support first.
    if (FindGround(Start,Ground) && FMath::Abs(Ground.Z-Start.Z)<=GroundTolerance && CapsuleFits(Start)
        && Character->TeleportTo(Start,CapturedTransform.Rotator(),false,false)) return true;
    // A newly occupied original position gets a small bounded safe recovery search, never a collision bypass.
    const float Radius=Character->GetCapsuleComponent()->GetScaledCapsuleRadius();
    for (int32 Ring=1;Ring<=2;++Ring)
        for (int32 Direction=0;Direction<8;++Direction)
        {
            const float Angle=Direction*UE_PI/4;
            FVector Candidate=Start+FVector(FMath::Cos(Angle),FMath::Sin(Angle),0)*(Radius*2+2)*Ring;
            if (FindGround(Candidate,Ground) && CapsuleFits(Ground)
                && Character->TeleportTo(Ground,CapturedTransform.Rotator(),false,false)) return true;
        }
    UE_LOG(LogCatrunExit,Warning,TEXT("Exit lease released, but start recovery is obstructed; Blueprint must handle false recovery result."));
    return false;
}

bool UCatrunExitTransitionComponent::ReleaseExitLease(bool bRestoreStart)
{
    return CleanupLease(bRestoreStart,false);
}

bool UCatrunExitTransitionComponent::CleanupLease(bool bRestoreStart,bool bWorldEnding)
{
    if (bCleaning) return true;
    TGuardValue<bool> Cleaning(bCleaning,true);
    ++LeaseSerial; ++SaveRequestSerial;
    const bool bHadLease=bLeaseActive;
    bLeaseActive=false; bSavePending=false; bCheckpointReady=false;
    auto* PC=Controller.Get();
    if (auto* BoundController=Controller.Get(true))
    {
        BoundController->OnPossessedPawnChanged.RemoveDynamic(this, &UCatrunExitTransitionComponent::OnLeasePossessionChanged);
        BoundController->OnEndPlay.RemoveDynamic(this, &UCatrunExitTransitionComponent::OnLeaseSubjectEndPlay);
    }
    if (auto* BoundCat=Cat.Get(true)) BoundCat->OnEndPlay.RemoveDynamic(this, &UCatrunExitTransitionComponent::OnLeaseSubjectEndPlay);
    bool bRestored=true;
    if (bHadLease && bRestoreStart && !bWorldEnding) bRestored=RestoreStartSafely();
    if (!bWorldEnding && PC && PreviousView.IsValid()
        && OwnedViews.ContainsByPredicate([PC](const auto& View){return View.Get()==PC->GetViewTarget();})) PC->SetViewTarget(PreviousView.Get());
    if (InputBlocker)
    {
        if (PC) PC->PopInputComponent(InputBlocker);
        InputBlocker->DestroyComponent(); InputBlocker=nullptr;
    }
    if (bOwnInput && PC) { PC->SetIgnoreMoveInput(false); PC->SetIgnoreLookInput(false); }
    bOwnInput=false;
    if (bOwnMovement && Cat.IsValid() && !Cat->IsActorBeingDestroyed())
    {
        auto* Move=Cat->GetCharacterMovement(); Cat->bUseControllerRotationYaw=bSavedControllerYaw;
        if (!bWorldEnding)
        {
            FVector Ground;
            const bool bSupported=FindGround(Cat->GetActorLocation(),Ground) && FMath::Abs(Ground.Z-Cat->GetActorLocation().Z)<=GroundTolerance;
            Move->SetMovementMode(bSupported ? static_cast<EMovementMode>(SavedMovementMode) : MOVE_Falling,bSupported ? SavedCustomMode : 0);
            Move->StopMovementImmediately(); Cat->ConsumeMovementInputVector();
        }
        Move->SetComponentTickEnabled(bSavedMovementTick);
    }
    bOwnMovement=false;
    if (bOwnSuspension && Suspension.IsValid()) Suspension->Release(this);
    bOwnSuspension=false;
    if (bOwnReservation && Flow.IsValid())
    {
        if (bWorldEnding) Flow->ReleaseExitTransition(this); // Do not cancel a surviving accepted-arrival token.
        else Flow->AbortExitTravel(this);
    }
    bOwnReservation=false; bTravelCommitted=false;
    OwnedViews.Reset(); PreviousView.Reset(); Cat.Reset(); Controller.Reset(); Flow.Reset(); Suspension.Reset();
    if (!bWorldEnding) if (auto* Exit=Cast<ACatrunStageExit>(GetOwner()); Exit && !Exit->IsActorBeingDestroyed()) Exit->RefreshExitTick();
    return bRestored;
}

void UCatrunExitTransitionComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    bEnding=true;
    const UWorld* World=GetWorld();
    const bool bWorldEnding=!World || World->bIsTearingDown || Reason==EEndPlayReason::LevelTransition
        || Reason==EEndPlayReason::EndPlayInEditor || Reason==EEndPlayReason::Quit;
    CleanupLease(!bWorldEnding,bWorldEnding);
    Super::EndPlay(Reason);
}
