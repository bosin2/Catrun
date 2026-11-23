#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "CatrunExitTransitionComponent.generated.h"

class APawn;
class ACharacter;
class APlayerController;
class UInputComponent;
class UCatrunLevelFlowSubsystem;
class UCatrunPuzzleSuspension;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FCatrunExitCheckpointSaved, bool, bSuccess, bool, bTracked, FText, Status);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FCatrunExitTravelFailed, FText, Reason);

/** Low-level, non-ticking lease/collision/save adapter. Blueprint and LevelSequence own presentation. */
UCLASS(ClassGroup=(Catrun), meta=(BlueprintSpawnableComponent))
class CATRUN_API UCatrunExitTransitionComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UCatrunExitTransitionComponent();
    /** Captures the actual pawn/view and suspends gameplay; does not play/move/fade anything. */
    UFUNCTION(BlueprintCallable, Category="Exit|Lease")
    bool AcquireExitLease(APawn* Pawn, FText& Failure);
    /** Called by the Stage1 portal director immediately before playing the departure sequence. */
    UFUNCTION(BlueprintCallable, Category="Exit|Lease")
    void ClearAcceptedStage1PortalMark();
    UFUNCTION(BlueprintCallable, Category="Exit|Arrival")
    bool ClaimArrivalTitleGate();
    UFUNCTION(BlueprintCallable, Category="Exit|Arrival")
    void ReleaseArrivalTitleGate();
    /** The lease's original gameplay camera has taken over, including the final blend update. */
    UFUNCTION(BlueprintPure, Category="Exit|Arrival")
    bool IsArrivalViewSettled(AActor* ExpectedView) const;
    /** Abort recovery; returns false only when no collision-safe start recovery was found. Idempotent. */
    UFUNCTION(BlueprintCallable, Category="Exit|Lease")
    bool ReleaseExitLease(bool bRestoreStart = true);
    UFUNCTION(BlueprintPure, Category="Exit|Lease")
    bool HasExitLease() const { return bLeaseActive; }
    /** Acquisition and rollback can synchronously move the pawn or dispatch overlap callbacks. */
    bool BlocksExitQualification() const { return bAcquiring || bLeaseActive || bCleaning || bEnding; }
    /** BP registers cameras it owns. Release never overrides an unregistered newer view owner. */
    UFUNCTION(BlueprintCallable, Category="Exit|Lease")
    void RememberOwnedViewTarget(AActor* ViewTarget);
    /** Query only. The array and all positions are world-space capsule centers; no actor is moved. */
    UFUNCTION(BlueprintCallable, Category="Exit|Collision")
    bool ValidateExitPath(const TArray<FVector>& WorldPoints, bool bGrounded, FText& Failure) const;
    UFUNCTION(BlueprintCallable, Category="Exit|Collision")
    bool ValidateExitMotion(FVector From, FVector To, bool bGrounded, FText& Failure) const;
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Exit|Collision", meta=(ClampMin="1", ClampMax="10"))
    float MaximumPathStep = 5.f;
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Exit|Collision", meta=(ClampMin="0.1", ClampMax="5"))
    float GroundTolerance = 3.f;
    /** Result is delivered on a later game-thread tick. Untracked editor worlds report success without I/O. */
    UFUNCTION(BlueprintCallable, Category="Exit|Save")
    bool RequestExitCheckpointSave();
    UFUNCTION(BlueprintPure, Category="Exit|Save")
    bool IsCheckpointSavePending() const { return bSavePending; }
    UPROPERTY(BlueprintAssignable, Category="Exit|Save") FCatrunExitCheckpointSaved OnCheckpointSaveFinished;
    /** BP calls only after its own sequence/fade/save completion gates. Native checks service ownership. */
    UFUNCTION(BlueprintCallable, Category="Exit|Travel")
    bool CommitExitTravel();
    UPROPERTY(BlueprintAssignable, Category="Exit|Travel") FCatrunExitTravelFailed OnTravelFailed;

    bool CanCommitExitTravel() const;
    void NotifyTravelFailure(const FString& Reason);
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
private:
    bool IsCurrentLease(uint64 Serial) const;
    UFUNCTION() void OnLeasePossessionChanged(APawn* OldPawn, APawn* NewPawn);
    UFUNCTION() void OnLeaseSubjectEndPlay(AActor* Actor, EEndPlayReason::Type Reason);
    void InvalidateSubjectLease(bool bWorldEnding);
    bool CleanupLease(bool bRestoreStart, bool bWorldEnding);
    bool FindGround(const FVector& Position, FVector& GroundCenter) const;
    bool CapsuleFits(const FVector& Position) const;
    bool RestoreStartSafely();
    void DeliverSaveResult(uint64 Lease, uint64 Request, bool bSuccess, bool bTracked, const FText& Status);
    TWeakObjectPtr<ACharacter> Cat;
    TWeakObjectPtr<APlayerController> Controller;
    TWeakObjectPtr<AActor> PreviousView;
    TWeakObjectPtr<UCatrunLevelFlowSubsystem> Flow;
    TWeakObjectPtr<UCatrunPuzzleSuspension> Suspension;
    TArray<TWeakObjectPtr<AActor>> OwnedViews;
    UPROPERTY(Transient) TObjectPtr<UInputComponent> InputBlocker;
    FTransform CapturedTransform;
    uint64 LeaseSerial = 0;
    uint64 SaveRequestSerial = 0;
    bool bLeaseActive = false, bSavePending = false, bCheckpointReady = false, bTravelCommitted = false;
    bool bOwnInput = false, bOwnMovement = false, bOwnSuspension = false, bOwnReservation = false;
    bool bAcquiring = false, bCleaning = false, bEnding = false;
    bool bSavedMovementTick = false, bSavedControllerYaw = false;
    uint8 SavedMovementMode = 0, SavedCustomMode = 0;
};
