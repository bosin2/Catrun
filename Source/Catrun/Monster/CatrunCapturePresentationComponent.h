#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "CatrunCapturePresentationComponent.generated.h"

class ACatrunArmor;
class ACameraActor;
class USpotLightComponent;
class APlayerController;
class UCatrunSoundSettings;

UENUM(BlueprintType)
enum class ECatrunCapturePhase : uint8 { Inactive, Framing, Pickup, Holding, Fading };
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FCatrunCapturePhaseEvent, ECatrunCapturePhase, Phase, int32, SessionId);

USTRUCT()
struct FCatrunCaptureMeshState
{
	GENERATED_BODY()
	UPROPERTY() TEnumAsByte<EAnimationMode::Type> Mode = EAnimationMode::AnimationBlueprint;
	UPROPERTY() TSubclassOf<UAnimInstance> AnimClass;
	UPROPERTY() FSingleAnimationPlayData Animation;
	void Save(USkeletalMeshComponent* Mesh);
	void Restore(USkeletalMeshComponent* Mesh) const;
};

/** Owns only temporary capture presentation and its reversible state. AI remains on the armor. */
UCLASS(ClassGroup=(Catrun), meta=(BlueprintSpawnableComponent))
class CATRUN_API UCatrunCapturePresentationComponent : public UActorComponent
{
	GENERATED_BODY()
public:
	UCatrunCapturePresentationComponent();
	// Initial phase listeners must defer retries until BeginCapture returns, even after aborting.
	bool BeginCapture(APawn* Cat, const UCatrunSoundSettings* Settings);
	UFUNCTION(BlueprintCallable, Category="Capture") void AbortCapture();
	UFUNCTION(BlueprintCallable, Category="Capture") bool NotifyGrab(int32 InSessionId);
	UFUNCTION(BlueprintCallable, Category="Capture") bool NotifyFinished(int32 InSessionId);
	UFUNCTION(BlueprintPure, Category="Capture") bool IsCapturing() const { return Phase != ECatrunCapturePhase::Inactive; }
	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Capture") ECatrunCapturePhase Phase = ECatrunCapturePhase::Inactive;
	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Capture") int32 SessionId = 0;
	UPROPERTY(BlueprintAssignable, Category="Capture") FCatrunCapturePhaseEvent OnPhaseChanged;
	// BP uses OnPhaseChanged/Pickup to play its montage, then sends matching session notifies.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Capture") bool bUseBlueprintPresentation = false;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Capture") TObjectPtr<UAnimationAsset> CatPickupAnimation;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Capture", meta=(ClampMin="0.1")) float PickupPlayRate = 1.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Capture", meta=(ClampMin="0.1")) float MissingAnimationDuration = 3.5f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Capture", meta=(ClampMin="1")) float CameraProbeRadius = 15.f;
	/** Illuminance of the presentation-only key light on the pair. 0 disables it. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Capture", meta=(ClampMin="0")) float KeyLightLux = 1.6f;
	/** Half of the vertical extent (cm) that must stay visible around the pair. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Capture", meta=(ClampMin="1")) float CameraFitHalfHeight = 160.f;
	/** A settled camera that has to move farther than this in one frame (cm) is marked as a cut so it does not smear. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Capture", meta=(ClampMin="1")) float CameraCutDistance = 20.f;
	/** Entry blend (alpha < 1) moves fast on purpose; only snaps and settled moves beyond the distance are cuts. */
	static bool ShouldCutCameraMove(float StepDistance, bool bSnapped, float BlendAlpha, float CutDistance);
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Capture") FName LeftHandBone = TEXT("hand_l");
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Capture") FName RightHandBone = TEXT("hand_r");
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* Tick) override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;
private:
	bool SetPhase(ECatrunCapturePhase Next);
	bool IsCurrentSession(int32 ExpectedSession, ECatrunCapturePhase ExpectedPhase) const;
	void CreateCamera();
	void UpdateCamera(float DeltaTime);
	void Cleanup(bool bRestoreTransform);
	FVector HandsLocation() const;
	UPROPERTY(Transient) TObjectPtr<const UCatrunSoundSettings> Settings;
	UPROPERTY(Transient) FCatrunCaptureMeshState CatMeshState;
	UPROPERTY(Transient) FCatrunCaptureMeshState ArmorMeshState;
	TWeakObjectPtr<ACatrunArmor> Armor;
	TWeakObjectPtr<APawn> Cat;
	TWeakObjectPtr<APlayerController> Player;
	TWeakObjectPtr<AActor> PreviousView;
	TWeakObjectPtr<ACameraActor> Camera;
	TWeakObjectPtr<USpotLightComponent> KeyLight;
	float CameraYaw = 0.f;
	bool bCameraYawChosen = false, bCameraNeedsCat = true, bCameraOverhead = false, bCameraCut = false;
	FTransform OriginalTransform;
	FVector GrabFrom = FVector::ZeroVector;
	FRotator GrabRotation = FRotator::ZeroRotator;
	FVector CameraFrom = FVector::ZeroVector;
	FRotator CameraFromRotation = FRotator::ZeroRotator;
	float FramingFromYaw = 0.f, FramingTargetYaw = 0.f;
	float Elapsed = 0.f, PickupElapsed = 0.f, GrabElapsed = 0.f, FadeElapsed = 0.f, PickupDuration = 0.f;
	uint8 MovementMode = 0, CustomMode = 0;
	bool bAbortPreparation = false;
	bool bBeginningCapture = false, bCleaningUp = false, bEndingPlay = false;
	bool bCollision = true, bOwnFade = false, bOwnInputLock = false, bOwnCatch = false, bRestartIssued = false, bOwnMarkHide = false;
};
