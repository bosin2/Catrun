#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimationAsset.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/Actor.h"
#include "InputCoreTypes.h"
#include "CatrunElevatorTransition.generated.h"

class ACharacter;
class APawn;
class APlayerController;
class ATriggerBox;
class SWidget;
class UAnimInstance;
class UAnimSequence;
class UCatrunExitTransitionComponent;
class UCatrunElevatorWeightComponent;
class UGameViewportClient;
class UPrimitiveComponent;
class USceneComponent;
class USoundBase;
class UUserWidget;
enum class ESlateVisibility : uint8;

UENUM(BlueprintType)
enum class ECatrunElevatorState : uint8
{
    Waiting,
    Aligning,
    Departure,
    Blackout,
    Travelling,
    Arrival,
    Finished,
    ArrivalWalk,
    ArrivalLook,
    ArrivalBlend
};

/** Place an instance on each side of the Stage2 -> Stage3 route. Marks specify grounded capsule centers. */
UCLASS()
class CATRUN_API ACatrunElevatorTransition : public AActor
{
    GENERATED_BODY()

public:
    ACatrunElevatorTransition();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Elevator")
    TObjectPtr<UCatrunExitTransitionComponent> ExitTransition;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Elevator|Weight")
    TObjectPtr<UCatrunElevatorWeightComponent> CabinWeight;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator")
    bool bArrivalSide = false;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Zones")
    TObjectPtr<ATriggerBox> CorridorVolume;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Zones")
    TObjectPtr<ATriggerBox> EntryVolume;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Zones")
    TObjectPtr<ATriggerBox> CabinVolume;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Zones")
    TObjectPtr<ATriggerBox> WarehouseVolume;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Zones")
    TArray<TObjectPtr<AActor>> CorridorOccluders;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Zones")
    TArray<TObjectPtr<AActor>> CabinOccluders;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Zones")
    TArray<TObjectPtr<AActor>> HideDuringAscent;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Lighting")
    bool bUseLocalElevatorLighting = false;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Marks")
    TObjectPtr<AActor> CatMark;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Marks")
    TObjectPtr<AActor> ArrivalReleaseMark;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Cabin")
    TObjectPtr<AActor> CabinPivot;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Cabin")
    TArray<TObjectPtr<AActor>> CabinActors;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Cabin")
    TObjectPtr<AActor> ChainActor;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Cabin")
    TArray<TObjectPtr<AActor>> ControlPullActors;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Cabin")
    TObjectPtr<AActor> LanternActor;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Cabin")
    TArray<TObjectPtr<AActor>> LanternActors;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Cabin", meta=(ClampMin="0"))
    float DepartureRiseDistance = 420.f;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Cabin", meta=(ClampMin="0"))
    float ArrivalApproachDistance = 120.f;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Camera")
    TObjectPtr<AActor> FrontCamera;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Camera")
    TObjectPtr<AActor> PeekCamera;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Camera")
    TObjectPtr<AActor> CabinCamera;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Camera")
    TObjectPtr<AActor> WarehouseCamera;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Camera")
    TObjectPtr<AActor> ArrivalExitCamera;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Camera", meta=(ClampMin="0.1", ClampMax="3"))
    float ArrivalCameraBlendSeconds = .75f;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Animation")
    TArray<TObjectPtr<UAnimSequence>> DepartureClips;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Animation")
    TArray<TObjectPtr<UAnimSequence>> ArrivalClips;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Animation")
    TObjectPtr<UAnimSequence> ArrivalExitWalkClip;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Animation")
    TObjectPtr<UAnimSequence> ArrivalLookAroundClip;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Animation", meta=(ClampMin="5", ClampMax="200"))
    float ArrivalWalkSpeed = 90.f;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Animation", meta=(ClampMin="0.1", ClampMax="8"))
    float ArrivalWalkClipPlayRate = 1.f;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Animation", meta=(ClampMin="0"))
    float ArrivalLookClipStartSeconds = 0.f;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Sound")
    TObjectPtr<USoundBase> PullSound;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Sound")
    TObjectPtr<USoundBase> StartSound;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Sound")
    TObjectPtr<USoundBase> DockLatchSound;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Elevator|Input")
    FKey SkipKey;

    UFUNCTION(BlueprintCallable, Category="Elevator")
    bool TryBegin(APawn* Pawn);
    UFUNCTION(BlueprintCallable, Category="Elevator")
    bool SkipTransition();
    UFUNCTION(BlueprintCallable, Category="Elevator")
    void CancelTransition();
    UFUNCTION(BlueprintPure, Category="Elevator")
    ECatrunElevatorState GetTransitionState() const { return State; }
    UFUNCTION(BlueprintPure, Category="Elevator")
    float GetTimelineSeconds() const { return TimelineSeconds; }
    UFUNCTION(BlueprintPure, Category="Elevator")
    int32 GetActiveClipIndex() const { return ActiveClipIndex; }

    bool IsInsideCorridor(const APawn& Pawn) const;

private:
    void UpdateFreeWalk(ACharacter* Pawn, APlayerController* PC, float DeltaSeconds);
    void UpdateAlignment(float DeltaSeconds);
    void UpdateDeparture(float DeltaSeconds);
    void UpdateArrival(float DeltaSeconds);
    void BeginArrivalWalk();
    void UpdateArrivalWalk(float DeltaSeconds);
    void BeginArrivalLook();
    void UpdateArrivalLook(float DeltaSeconds);
    void BeginArrivalBlend();
    void UpdateArrivalBlend(float DeltaSeconds);
    void FinishArrival();
    void FinishDeparture();
    void StartClip(int32 Index);
    void StartClipAsset(UAnimSequence& Clip, int32 Index);
    void SampleClip(float Position);
    void CutTo(AActor* Camera);
    void SetFade(float Alpha);
    void AddLetterbox();
    void RemoveLetterbox();
    void HideMinimap(APlayerController* PC, float DeltaSeconds = 0.f);
    void RestoreMinimap();
    void PositionArrivalTitle(APlayerController* PC, float DeltaSeconds);
    void UpdateJumpCamera(float Position);
    void ApplyCabinMotion(float Height, float Sway, float LanternSwing, float ChainPull, bool bMoveCat);
    void RestorePresentation();
    void StartCabinWeight(ACharacter* ScriptedRider = nullptr);
    void UpdateOccluders(bool bCorridor, bool bCabin, bool bAscent = false);
    void UpdateWarehouseView(ACharacter* Pawn, APlayerController* PC, bool bWarehouse);
    void SetLocalLighting(USkeletalMeshComponent* Mesh);
    bool SetCatOnMark(AActor& Mark);
    void SavePresentation(ACharacter& Pawn, APlayerController& PC);
    bool ValidateClips(const ACharacter& Pawn) const;
    UFUNCTION() void HandleTravelFailure(FText Reason);

    TWeakObjectPtr<ACharacter> Cat;
    TWeakObjectPtr<APlayerController> Controller;
    TWeakObjectPtr<AActor> ActiveCamera;
    TWeakObjectPtr<AActor> GameplayCamera;
    TWeakObjectPtr<AActor> TrackedArrivalExitCamera;
    TWeakObjectPtr<AActor> PreviousWarehouseView;
    TWeakObjectPtr<APlayerController> WarehouseController;
    TWeakObjectPtr<APawn> WarehousePawn;
    TWeakObjectPtr<USkeletalMeshComponent> LitMesh;
    FString LastArrivalRejection;
    TWeakObjectPtr<UGameViewportClient> LetterboxViewport;
    TSharedPtr<SWidget> Letterbox;
    TMap<TWeakObjectPtr<UUserWidget>, ESlateVisibility> MinimapVisibility;
    FLightingChannels PreviousLighting;
    TArray<TWeakObjectPtr<AActor>> HiddenOccluders;
    TMap<TWeakObjectPtr<AActor>, FTransform> RestTransforms;
    FTransform OriginalMeshRelative;
    FTransform SceneMeshWorld;
    FTransform WalkStart;
    FTransform WalkDestination;
    FTransform ArrivalExitCameraStart;
    FQuat LookBaseRotation = FQuat::Identity;
    FVector AlignStart = FVector::ZeroVector;
    FQuat AlignStartRotation = FQuat::Identity;
    FVector MotionPivot = FVector::ZeroVector;
    FVector LanternPivot = FVector::ZeroVector;
    EAnimationMode::Type SavedAnimMode = EAnimationMode::AnimationBlueprint;
    UPROPERTY(Transient) TSubclassOf<UAnimInstance> SavedAnimClass;
    UPROPERTY(Transient) FSingleAnimationPlayData SavedAnimation;
    UPROPERTY(Transient) TObjectPtr<UAnimSequence> ActiveClip;
    ECatrunElevatorState State = ECatrunElevatorState::Waiting;
    float TimelineSeconds = 0.f;
    float PhaseSeconds = 0.f;
    float ClipSeconds = 0.f;
    float PromptCooldown = 0.f;
    float ArrivalWaitSeconds = 0.f;
    float LetterboxFraction = 0.f;
    float MinimapRetrySeconds = 0.f;
    float TitlePlacementTimeLeft = 5.f;
    float TitlePlacementRetrySeconds = 0.f;
    float WalkDuration = 0.f;
    float LookClipStart = 0.f;
    int32 ActiveClipIndex = INDEX_NONE;
    bool bArrivalExpected = false;
    bool bOwnPlayback = false;
    bool bOwnFade = false;
    bool bPlayedStart = false;
    bool bPlayedPull = false;
    bool bPlayedLatch = false;

    // Zone presentation is owned before the cinematic acquires Controller/Cat.
    TWeakObjectPtr<APlayerController> MinimapController;
    TWeakObjectPtr<APlayerController> IsolationController;
    TWeakObjectPtr<ACharacter> IsolationCat;
    TArray<TWeakObjectPtr<UPrimitiveComponent>> IsolatedPrimitives;
    TArray<TWeakObjectPtr<USceneComponent>> IsolatedSceneComponents;
    FDelegateHandle IsolationSpawnedHandle;

    void UpdateZonePresentation(ACharacter* Pawn, APlayerController* PC, float DeltaSeconds);
    void UpdateCabinIsolation(ACharacter* Pawn, APlayerController* PC, bool bIsolate);
    bool IsIsolationVisibleActor(const AActor* Actor) const;
    void IsolateActor(AActor* Actor);
    void RestoreCabinIsolation();
    void UpdatePeekCamera(float DeltaSeconds);
};
