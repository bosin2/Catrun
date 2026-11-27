#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Components/SkeletalMeshComponent.h"
#include "CatrunStatuePuzzle.h"
#include "CatrunStage3Objectives.generated.h"

class ACatrunStatuePuzzle;
class APawn;
class ACharacter;
class APlayerController;
class UAnimSequence;
class UCatrunPuzzleRevealComponent;
class UCameraShakeBase;

USTRUCT(BlueprintType)
struct FCatrunReleaseDevice
{
	GENERATED_BODY()
	UPROPERTY(EditAnywhere, BlueprintReadWrite) TObjectPtr<AActor> Housing;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) TObjectPtr<AActor> Ring;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) TObjectPtr<AActor> Pin;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) TObjectPtr<AActor> LockBolt;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) TArray<TObjectPtr<AActor>> ChainLinks;
	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly) bool bReleased = false;
};

/** Stage-local objective wiring. Reuses the existing statue, perception and travel systems. */
UCLASS()
class CATRUN_API ACatrunStage3Objectives : public AActor
{
	GENERATED_BODY()
public:
	ACatrunStage3Objectives();
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;
	UPROPERTY(EditInstanceOnly, BlueprintReadWrite) TArray<FCatrunReleaseDevice> Devices;
	UPROPERTY(EditInstanceOnly, BlueprintReadWrite) TObjectPtr<ACatrunStatuePuzzle> Puzzle;
	UPROPERTY(EditInstanceOnly, BlueprintReadWrite) FName LockedPuzzleId = TEXT("S3_P2");
	UPROPERTY(EditInstanceOnly, BlueprintReadWrite) TObjectPtr<AActor> FinalLeafLeft;
	UPROPERTY(EditInstanceOnly, BlueprintReadWrite) TObjectPtr<AActor> FinalLeafRight;
	UPROPERTY(EditAnywhere, BlueprintReadWrite) float InteractionRange = 95.f;
	/** Sound made when a ring is pulled, as travel distance in cm along open paths (the armors that hear it come).
	 *  0 = use LargeBudget of the level's sound settings (DA_SoundSettings), shared with every other large sound. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Sound", meta=(ClampMin="0", Units="Centimeters")) float ReleaseSoundBudget = 0.f;
	/** BP_S3Polish_Presenter starts this endless shake when a gate starts moving. It is stopped (blended out)
	 *  here when the final gate, or a D1/D2 statue gate, has finished opening. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Presentation") TSoftClassPtr<UCameraShakeBase> GateMotionShake;
	UPROPERTY(EditInstanceOnly, BlueprintReadWrite) TObjectPtr<UAnimSequence> ReleaseAnimation;
	/** Authored muzzle track in character-local centimetres, sampled at 30Hz. */
	UPROPERTY(EditInstanceOnly, BlueprintReadWrite) TArray<FVector> MouthOffsets;
	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly) int32 ActiveDevice = INDEX_NONE;
	/** Rises when the leaves start moving (after the reveal camera arrives). BP_S3Polish_Presenter keys on this edge. */
	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly) bool bFinalGateOpen = false;
	/** The final gate is triggered and waits for the reveal camera to reach it. */
	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly) bool bFinalRevealPending = false;
	/** Same native camera owner as the D1/D2 statue gates (input lock, hostile suspension, bounded timeout). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Puzzle") TObjectPtr<UCatrunPuzzleRevealComponent> FinalReveal;
	UFUNCTION(BlueprintCallable) bool TryRelease(int32 Index, APawn* Cat);
	UFUNCTION(BlueprintPure) bool AllReleased() const;
	UFUNCTION(BlueprintPure) bool CanRelease(int32 Index, APawn* Cat) const;
	/** Final gate timing. BP_S3Polish_Presenter fires its impact 3.45 s after bFinalGateOpen rises. */
	static constexpr float FinalGateTravel = 310.f;
	static constexpr float FinalGateDuration = 3.45f;
	static constexpr float FinalGateHold = .35f;
	/** Per-leaf outward offset (cm) at the given time since the final gate started; never negative. */
	static float FinalGateOffsetAt(float Seconds);
	/** Final gate reveal: eased pan to the gate, open on arrival, hold on the open gate, eased return to the cat. */
	static constexpr float FinalRevealTravel = 2.f;
	static constexpr float FinalRevealHoldAfterOpen = 1.f;
	static constexpr float FinalRevealReturn = 1.6f;
	static FName FinalRevealId() { return FName(TEXT("S3_FinalGate")); }
	/** Starts the final gate: camera reveal first when available, otherwise opens immediately. */
	void BeginFinalGate();
private:
	bool GameplayAvailable(APawn* Cat) const;
	void StopGateMotionShake() const;
	UFUNCTION() void HandlePuzzleEvent(FName PuzzleId, ECatrunStatueEvent Event, int32 Revision);
	void AdvanceFinalGate(float DeltaSeconds);
	void UpdateInteraction(float DeltaSeconds);
	void FinishInteraction(bool bInterrupted);
	void CommitRelease(int32 Index);
	void UpdateChain(FCatrunReleaseDevice& Device);
	TWeakObjectPtr<ACharacter> InteractingCat;
	TWeakObjectPtr<APlayerController> InteractingController;
	UPROPERTY(Transient) TSubclassOf<UAnimInstance> SavedAnimClass;
	UPROPERTY(Transient) FSingleAnimationPlayData SavedAnimation;
	EAnimationMode::Type SavedAnimMode = EAnimationMode::AnimationBlueprint;
	uint8 SavedMovementMode = 0, SavedCustomMode = 0;
	FVector AlignmentStart, AlignmentTarget, RingStart, PinStart;
	FRotator AlignmentRotation;
	float AlignmentElapsed = 0.f;
	bool bClipStarted = false;
	FVector LeftStart, RightStart;
	float FinalOffset = 0.f;
	float FinalGateTime = 0.f;
	float FinalHoldTime = 0.f;
	void OpenFinalGate(float DeltaSeconds);
	bool IsFinalRevealOpening() const;
	int32 PromptIndex = INDEX_NONE;
	float PromptTime = 0.f;
};
