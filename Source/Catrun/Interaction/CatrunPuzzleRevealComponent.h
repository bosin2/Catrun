#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Camera/CameraTypes.h"
#include "CatrunPuzzleRevealComponent.generated.h"

class ACameraActor;
class APlayerController;
class UInputComponent;
UENUM(BlueprintType)
enum class ECatrunPuzzleRevealPhase : uint8 { Inactive, ToGate, Opening, Returning };
DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FCatrunPuzzleRevealEvent, FName, PuzzleId, ECatrunPuzzleRevealPhase, Phase, int32, SessionId);

/** Bounded native camera owner. BP owns bars/dust and optional legacy magnification. */
UCLASS(ClassGroup=(Catrun), meta=(BlueprintSpawnableComponent))
class CATRUN_API UCatrunPuzzleRevealComponent : public UActorComponent
{
	GENERATED_BODY()
public:
	UCatrunPuzzleRevealComponent();
	bool BeginReveal(FName Id, AActor* Gate, const FBox& GateBounds);
	bool CanOpenGate(FName Id) const;
	void GateOpened(FName Id);
	UFUNCTION(BlueprintCallable, Category="Puzzle|Reveal") void CancelReveal();
	/** Ignore stale callbacks. Native timeout always remains active. */
	UFUNCTION(BlueprintCallable, Category="Puzzle|Reveal") void NotifyCameraAtGate(int32 ExpectedSession);
	UFUNCTION(BlueprintPure, Category="Puzzle|Reveal") ACameraActor* GetRevealCamera() const { return Camera.Get(); }
	/** Presentation must resolve its zoom endpoints through this bridge. */
	UFUNCTION(BlueprintPure, Category="Puzzle|Reveal") float ResolvePresentationOrthoWidth(float AuthoredWidth) const;
	UPROPERTY(BlueprintAssignable, Category="Puzzle|Reveal") FCatrunPuzzleRevealEvent OnPhaseChanged;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Puzzle|Reveal") ECatrunPuzzleRevealPhase Phase = ECatrunPuzzleRevealPhase::Inactive;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Puzzle|Reveal") FName PuzzleId;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Puzzle|Reveal") int32 SessionId = 0;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Puzzle|Reveal") bool bEnabled = true;
	/** Translate the gameplay view to the gate without turning or changing magnification. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Puzzle|Reveal") bool bPreserveGameplayFraming = true;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Puzzle|Reveal", meta=(ClampMin="0")) float CameraTravelTime = .65f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Puzzle|Reveal", meta=(ClampMin="0")) float CameraReturnTime = .6f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Puzzle|Reveal", meta=(ClampMin="1", ClampMax="15")) float MaximumLockTime = 8.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Puzzle|Reveal") FVector GateCameraOffset = FVector(0,-400,160);
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;
private:
	friend class FStatueRevealTest;
	bool SetPhase(ECatrunPuzzleRevealPhase Next);
	bool ShouldAbort() const;
	/** Orthographic view origins are corrected by the renderer after the camera cache. */
	FVector ResolveProjectionOrigin(FMinimalViewInfo View) const;
	FVector ResolveCollisionLocation(const FVector& Location) const;
	FVector ResolveOwnedCameraLocation(const FMinimalViewInfo& SourceView) const;
	void ApplyGameplayFraming();
	void Cleanup();
	TWeakObjectPtr<APlayerController> Player;
	TWeakObjectPtr<AActor> PreviousView;
	TWeakObjectPtr<AActor> TargetGate;
	TWeakObjectPtr<ACameraActor> Camera;
	UPROPERTY(Transient) TObjectPtr<UInputComponent> InputBlocker;
	FVector CameraStart = FVector::ZeroVector;
	FRotator CameraStartRotation = FRotator::ZeroRotator;
	FVector CameraEnd = FVector::ZeroVector;
	FRotator CameraEndRotation = FRotator::ZeroRotator;
	FMinimalViewInfo GameplayView;
	bool bPreserveSessionFraming = false;
	float Elapsed = 0.f;
	float PhaseElapsed = 0.f;
	bool bOwnInput = false;
	bool bStarting = false;
	bool bCleaning = false;
	bool bEnding = false;
};
