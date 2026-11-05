#pragma once

#include "CoreMinimal.h"
#include "Engine/DeveloperSettings.h"
#include "GameFramework/Actor.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Subsystems/WorldSubsystem.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "CatrunLevelFlow.generated.h"

class UBoxComponent;
class UCatrunNoticeWidget;
class UCatrunPlayHUD;
class UCameraComponent;
class USpringArmComponent;
class APlayerController;
class UCatrunExitTransitionComponent;
class FCatrunProgressWriter;
class ISaveGameSystem;

/** A single-use travel token. A different destination discards it rather than leaking into a later run. */
struct CATRUN_API FCatrunRestartIntent
{
	FString MapPackage;
	float FadeInDuration = 0.f;
	bool bContinue = false;
	void Request(const FString& Package, float FadeDuration, bool bIsContinue = false);
	void Clear();
	bool Consume(const FString& Package, float& OutFadeDuration);
};

enum class ECatrunArrivalRestart : uint8 { Preserve, Clear, SkipIntro, Continue };

/** Travel state belongs to one game session, including isolated PIE instances. */
UCLASS()
class CATRUN_API UCatrunFlowSession : public UGameInstanceSubsystem
{
	GENERATED_BODY()
public:
	FCatrunRestartIntent RestartIntent;
	uint64 AcceptTravel(const FString& Package, bool bBeginProgress, bool bCheckpoint, ECatrunArrivalRestart Restart, int8 OnboardingOnArrival = -1);
	void CancelTravel(uint64 ExpectedToken = 0);
	void ResolveArrivalRestart(const FString& Package);
	bool Arrive(const FString& Package);
	bool IsTrackingWorld(const FString& Package) const;
	/** Returns zero for an untracked/editor world; callback is not called in that case. */
	uint64 SaveCurrentCheckpoint(const FString& Package, TFunction<void(bool, const FString&)> Completion = {});
	bool HasCompletedOnboarding() const { return bTutorialOnboardingCompleted; }
	void MarkOnboardingCompleted(const FString& Package);
	bool IsSavePending() const;
#if WITH_DEV_AUTOMATION_TESTS
	void SetSaveBackendForTest(ISaveGameSystem* Backend);
#endif
private:
	TSharedPtr<FCatrunProgressWriter> Writer;
	uint64 ProgressGeneration = 0;
	uint64 NextTravelToken = 0;
	uint64 AcceptedTravelToken = 0;
	bool bTutorialOnboardingCompleted = false;
	int8 AcceptedOnboarding = -1;
	FString ActiveProgressMap;
	FString AcceptedTravelMap;
	bool bBeginProgressOnArrival = false;
	bool bCheckpointOnArrival = false;
	ECatrunArrivalRestart ArrivalRestart = ECatrunArrivalRestart::Preserve;
};

USTRUCT(BlueprintType)
struct FCatrunStageCameraProfile
{
	GENERATED_BODY()
	UPROPERTY(EditAnywhere, BlueprintReadOnly) FName StageId;
	/** Orthographic width or perspective spring-arm length multiplier, relative to authored values. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, meta=(ClampMin="1.0", ClampMax="3.0")) float DistanceScale = 1.f;
};

USTRUCT(BlueprintType)
struct FCatrunStageRoute
{
	GENERATED_BODY()
	UPROPERTY(EditAnywhere, BlueprintReadOnly)
	FName StageId;
	UPROPERTY(EditAnywhere, BlueprintReadOnly)
	TSoftObjectPtr<UWorld> Map;
};

/** Ordered playable maps. Add Stage3 only when its map is ready. */
UCLASS(Config=Game, DefaultConfig, meta=(DisplayName="Catrun Level Flow"))
class CATRUN_API UCatrunLevelFlowSettings : public UDeveloperSettings
{
	GENERATED_BODY()
public:
	UCatrunLevelFlowSettings();
	UPROPERTY(Config, EditAnywhere, Category="Maps")
	TSoftObjectPtr<UWorld> MainMenuMap;
	UPROPERTY(Config, EditAnywhere, Category="Maps")
	TArray<FCatrunStageRoute> Stages;
	UPROPERTY(Config, EditAnywhere, Category="Camera")
	TArray<FCatrunStageCameraProfile> CameraProfiles;

	int32 FindStageIndex(const FString& PackageName) const;
	float GetCameraDistanceScale(FName StageId) const;
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FCatrunStageCompleted, FName, StageId);

/** Rules and travel are native; existing Blueprint cinematics call the library when finished. */
UCLASS()
class CATRUN_API UCatrunLevelFlowSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()
public:
	static UCatrunLevelFlowSubsystem* Get(const UObject* WorldContextObject);
	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;
	virtual void Deinitialize() override;
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;

	bool StartGame();
	bool ContinueGame();
	bool CompleteStage();
	bool ReturnToMenu();
	bool RestartStage();
	bool ReserveExitTransition(UObject* Owner);
	void ReleaseExitTransition(const UObject* Owner);
	bool CompleteStageForExit(UObject* Owner);
	void AbortExitTravel(const UObject* Owner);
	bool ShouldShowTutorialControls();
	void MarkTutorialOnboardingCompleted();
	/** Stable for this world: consuming the travel token never changes subsequent BP query results. */
	UFUNCTION(BlueprintCallable, Category="Level Flow")
	bool ShouldSkipStageIntro();
	float GetRestartFadeInDuration();
	bool ApplyStageCameraProfile(UCameraComponent* Camera, USpringArmComponent* SpringArm);
	UFUNCTION(BlueprintCallable, Category="Level Flow")
	void SetPauseMenu(bool bOpen);
	bool IsTransitioning() const { return bTransitioning || ExitReservation.IsValid(); }
	bool IsStageComplete() const { return bStageComplete; }

	UPROPERTY(BlueprintAssignable, Category="Level Flow")
	FCatrunStageCompleted OnStageCompleted;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Level Flow")
	bool bStageComplete = false;

private:
	bool TravelTo(const TSoftObjectPtr<UWorld>& Map, const FString& Options = FString(), bool bBeginProgress = false,
		bool bCheckpoint = false, ECatrunArrivalRestart Restart = ECatrunArrivalRestart::Clear, UObject* ExitOwner = nullptr, int8 Onboarding = -1);
	bool CompleteStageInternal(UObject* ExitOwner);
	void ClearFailedTravel();
	void FinishTravel();
	void ResolveRestartIntent();
	bool bRestartIntentResolved = false;
	bool bSkipStageIntro = false;
	bool bContinueArrival = false;
	bool bControlsOffered = false;
	float RestartFadeInDuration = 0.f;
	TWeakObjectPtr<UCameraComponent> GameplayCamera;
	TWeakObjectPtr<USpringArmComponent> GameplaySpringArm;
	float AuthoredOrthoWidth = 0.f;
	float AuthoredArmLength = 0.f;
	bool bTransitioning = false;
	TWeakObjectPtr<UObject> ExitReservation;
	TWeakObjectPtr<APlayerController> TravelLockController;
	FString PendingMap;
	uint64 PendingTravelToken = 0;
	FString PendingOptions;
	FDelegateHandle TravelFailureHandle;
	UPROPERTY(Transient)
	TObjectPtr<UCatrunPlayHUD> PlayHUD;
};

UCLASS()
class CATRUN_API UCatrunLevelFlowLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()
public:
	UFUNCTION(BlueprintCallable, Category="Catrun|Level Flow", meta=(WorldContext="WorldContextObject"))
	static bool StartNewGame(const UObject* WorldContextObject);
	UFUNCTION(BlueprintPure, Category="Catrun|Level Flow", meta=(WorldContext="WorldContextObject"))
	static bool HasContinueGame(const UObject* WorldContextObject);
	UFUNCTION(BlueprintCallable, Category="Catrun|Level Flow", meta=(WorldContext="WorldContextObject"))
	static bool ContinueGame(const UObject* WorldContextObject);
	UFUNCTION(BlueprintPure, Category="Catrun|Level Flow", meta=(WorldContext="WorldContextObject"))
	static FText GetContinueStageLabel(const UObject* WorldContextObject);
	UFUNCTION(BlueprintCallable, Category="Catrun|Level Flow", meta=(WorldContext="WorldContextObject"))
	static bool CompleteCurrentStage(const UObject* WorldContextObject);
	UFUNCTION(BlueprintCallable, Category="Catrun|Level Flow", meta=(WorldContext="WorldContextObject"))
	static bool ReturnToMainMenu(const UObject* WorldContextObject);
	UFUNCTION(BlueprintCallable, Category="Catrun|Level Flow", meta=(WorldContext="WorldContextObject"))
	static bool RestartCurrentStage(const UObject* WorldContextObject);
	UFUNCTION(BlueprintCallable, Category="Catrun|Level Flow", meta=(WorldContext="WorldContextObject"))
	static bool ShouldSkipStageIntro(const UObject* WorldContextObject);
	UFUNCTION(BlueprintCallable, Category="Catrun|Level Flow", meta=(WorldContext="WorldContextObject"))
	static bool ShouldShowTutorialControls(const UObject* WorldContextObject);
	UFUNCTION(BlueprintCallable, Category="Catrun|Level Flow", meta=(WorldContext="WorldContextObject"))
	static void MarkTutorialOnboardingCompleted(const UObject* WorldContextObject);
	/** Call only on the restart branch, using the original intro's final playable transform. */
	UFUNCTION(BlueprintCallable, Category="Catrun|Level Flow", meta=(WorldContext="WorldContextObject"))
	static bool RestorePlayableStart(const UObject* WorldContextObject, APawn* Pawn, const FTransform& PlayableTransform, AActor* GameplayViewTarget = nullptr);
	/** Pass the pawn camera or original BP_QuarterViewCamera/tagged CatrunGameplayCamera, never a cinematic camera. */
	UFUNCTION(BlueprintCallable, Category="Catrun|Camera", meta=(WorldContext="WorldContextObject"))
	static bool ApplyStageCameraProfile(const UObject* WorldContextObject, UCameraComponent* Camera, USpringArmComponent* SpringArm);
};

/** Place at an existing doorway. Only the locally controlled cat can complete the stage. */
UCLASS()
class CATRUN_API ACatrunStageExit : public AActor
{
	GENERATED_BODY()
public:
	ACatrunStageExit();
	virtual void Tick(float DeltaSeconds) override;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Exit")
	TObjectPtr<UBoxComponent> Trigger;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Exit")
	TObjectPtr<UCatrunExitTransitionComponent> ExitTransition;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Exit") bool bRequireCenterInside = false;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Exit") bool bUseExitTransition = false;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Exit") FVector InteriorDirectionLocal = FVector::ZeroVector;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Exit") float MinimumInteriorDepth = 0.f;
	bool IsCenterQualified(const FVector& WorldLocation) const;
	UFUNCTION(BlueprintCallable, Category="Exit")
	bool TryCompleteFor(APawn* Pawn);
	/** Presentation, sequence ownership and completion order are authored in the exit Blueprint. */
	UFUNCTION(BlueprintImplementableEvent, Category="Exit")
	void BeginPortalPresentation(APawn* Pawn);
	UFUNCTION(BlueprintImplementableEvent, Category="Exit")
	void ExitCheckpointSaveFinished(bool bSuccess, bool bTracked, const FText& Status);
	UFUNCTION(BlueprintImplementableEvent, Category="Exit")
	void ExitTravelFailed(const FText& Reason);
	void RefreshExitTick();
private:
	bool bArmed = true;
	TWeakObjectPtr<APawn> OverlappingPawn;
	UFUNCTION()
	void HandleOverlap(AActor* OverlappedActor, AActor* OtherActor);
	UFUNCTION()
	void HandleEndOverlap(AActor* OverlappedActor, AActor* OtherActor);
};
