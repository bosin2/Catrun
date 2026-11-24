#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Components/SkeletalMeshComponent.h"
#include "CatrunStage3Objectives.generated.h"

class ACatrunStatuePuzzle;
class APawn;
class ACharacter;
class APlayerController;
class UAnimSequence;

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
	UPROPERTY(EditInstanceOnly, BlueprintReadWrite) TObjectPtr<UAnimSequence> ReleaseAnimation;
	/** Authored muzzle track in character-local centimetres, sampled at 30Hz. */
	UPROPERTY(EditInstanceOnly, BlueprintReadWrite) TArray<FVector> MouthOffsets;
	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly) int32 ActiveDevice = INDEX_NONE;
	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly) bool bFinalGateOpen = false;
	UFUNCTION(BlueprintCallable) bool TryRelease(int32 Index, APawn* Cat);
	UFUNCTION(BlueprintPure) bool AllReleased() const;
	UFUNCTION(BlueprintPure) bool CanRelease(int32 Index, APawn* Cat) const;
private:
	bool GameplayAvailable(APawn* Cat) const;
	void UpdateInteraction(float DeltaSeconds);
	void FinishInteraction(bool bInterrupted);
	void CommitRelease(int32 Index);
	void UpdateChain(FCatrunReleaseDevice& Device);
	TWeakObjectPtr<ACharacter> InteractingCat;
	TWeakObjectPtr<APlayerController> InteractingController;
	TSubclassOf<UAnimInstance> SavedAnimClass;
	FSingleAnimationPlayData SavedAnimation;
	EAnimationMode::Type SavedAnimMode = EAnimationMode::AnimationBlueprint;
	uint8 SavedMovementMode = 0, SavedCustomMode = 0;
	FVector AlignmentStart, AlignmentTarget, RingStart, PinStart;
	FRotator AlignmentRotation;
	float AlignmentElapsed = 0.f;
	bool bClipStarted = false;
	FVector LeftStart, RightStart;
	float FinalOffset = 0.f;
	int32 PromptIndex = INDEX_NONE;
	float PromptTime = 0.f;
};
