#pragma once

#include "CoreMinimal.h"
#include "Engine/DeveloperSettings.h"
#include "Engine/LatentActionManager.h"
#include "GameFramework/Actor.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Subsystems/WorldSubsystem.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "CatrunLevelFlow.generated.h"

class ACatrunElevatorTransition;
class UBoxComponent;
class UCatrunNoticeWidget;
class UCatrunPlayHUD;
class UUserWidget;
class UCameraComponent;
class USpringArmComponent;
class APlayerController;
class UCatrunExitTransitionComponent;
class FCatrunProgressWriter;
class ISaveGameSystem;
class UCatrunProgressSave;
class UTexture2D;

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
enum class ECatrunProgressArrival : uint8 { Resume, FailureRefill, ResetStage, NewRun };

USTRUCT(BlueprintType)
struct CATRUN_API FCatrunStageClockState
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly) float RemainingSeconds = 0.f;
	UPROPERTY(BlueprintReadOnly) float BudgetSeconds = 0.f;
	UPROPERTY(BlueprintReadOnly) bool bTimed = false;
	UPROPERTY(BlueprintReadOnly) bool bRunning = false;
	UPROPERTY(BlueprintReadOnly) float WarningFraction = .3f;
	UPROPERTY(BlueprintReadOnly) float UrgentFraction = .15f;
};
UENUM(BlueprintType)
enum class ECatrunCheckpointState : uint8 { Idle, Pending, Saved, Failed };
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FCatrunCheckpointStateChanged, ECatrunCheckpointState, State);

/** Travel state belongs to one game session, including isolated PIE instances. */
UCLASS()
class CATRUN_API UCatrunFlowSession : public UGameInstanceSubsystem
{
	GENERATED_BODY()
public:
	virtual void Deinitialize() override;
	FCatrunRestartIntent RestartIntent;
	uint64 AcceptTravel(const FString& Package, bool bBeginProgress, bool bCheckpoint, ECatrunArrivalRestart Restart, int8 OnboardingOnArrival = -1, float FadeInDuration = 0.f, ECatrunProgressArrival Progress = ECatrunProgressArrival::Resume);
	void CancelTravel(uint64 ExpectedToken = 0);
	void ResolveArrivalRestart(const FString& Package);
	bool HasRestartArrivalIntent(const FString& CleanPackage) const;
	bool Arrive(const FString& Package);
	void SaveArrivalCheckpoint(UWorld& World, bool bQuiet = false);
	bool ConsumeArrivalTitle(const FString& Package);
	int32 GetHighestUnlockedStageIndex();
	bool IsProgressReadResolved() const { return bProgressLoaded; }
	void RefreshMenuWithProgressSnapshot(TFunctionRef<void()> Refresh);
	const UCatrunProgressSave* LoadSavedProgress() const;
	UFUNCTION(BlueprintPure, Category="Catrun|Progress")
	ECatrunCheckpointState GetCheckpointState() const { return CheckpointState; }
	UPROPERTY(BlueprintAssignable, Category="Catrun|Progress")
	FCatrunCheckpointStateChanged OnCheckpointStateChanged;
	bool IsTrackingWorld(const FString& Package) const;
	/** Returns zero for an untracked/editor world; callback is not called in that case. */
	uint64 SaveCurrentCheckpoint(const FString& Package, TFunction<void(bool, const FString&)> Completion = {});
	bool HasCompletedOnboarding() const { return bTutorialOnboardingCompleted; }
	void MarkOnboardingCompleted(const FString& Package);
	bool IsSavePending() const;
	float GetRemainingSeconds(FName StageId) const;
	void AdvanceClock(float DeltaSeconds);
	void FlushTrackedProgress();
	FName GetContinueStageId();
#if WITH_DEV_AUTOMATION_TESTS
	void SetSaveBackendForTest(ISaveGameSystem* Backend, FSimpleDelegate DrainCallbacks = {}, bool bUseAtomicIO = false);
#endif
private:
	bool EnsureProgressLoaded();
	void MergeSavedProgress(const UCatrunProgressSave& Save);
	uint64 BeginCheckpoint(const FString& Package, bool bRetryOnce, TFunction<void(bool, const FString&)> Completion, bool bQuiet = false);
	uint64 EnqueueCheckpoint(FName StageId, uint64 Generation, uint64 Request, uint64 Revision, bool bRetryOnce, TFunction<void(bool, const FString&)> Completion);
	void OnCheckpointQueueIdle();
	void OnCheckpointStarted();
	struct FStage1ClockMutation
	{
		uint64 Revision;
		int32 RemainingMs;
	};
	void RefillStage1Clock();
	void CaptureClock();
	void ReadStageValues(const UCatrunProgressSave& Save);
	TArray<FStage1ClockMutation> Mutations;
	uint64 MutationRevision = 0;
	double Stage1Seconds = -1.;
	double LocalStage1Seconds = -1.;
	double Stage2Seconds = -1.;
	double Stage3Seconds = -1.;
	FName CurrentStage, LastTrackedStage;
	bool bClockDirty = false;
	bool bFlushing = false;
	bool bRetriedDuringShutdown = false;
	bool bShowCheckpointNotice = false;
	TSharedPtr<FCatrunProgressWriter> Writer;
	uint64 LatestSaveRequest = 0;
	ECatrunCheckpointState CheckpointState = ECatrunCheckpointState::Idle;
	ECatrunCheckpointState CompletedCheckpointState = ECatrunCheckpointState::Idle;
	bool bProgressLoaded = false;
	bool bDrawingProgressSnapshot = false;
	FName HighestUnlockedStageId;
	FString TitleIntentMap;
	ECatrunProgressArrival ProgressOnArrival = ECatrunProgressArrival::Resume;
#if WITH_DEV_AUTOMATION_TESTS
	ISaveGameSystem* SaveBackendForTest = nullptr;
#endif
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
	float ArrivalFadeInDuration = 0.f;
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
	UPROPERTY(EditAnywhere, BlueprintReadOnly) FText DisplayName;
	UPROPERTY(EditAnywhere, BlueprintReadOnly) TSoftObjectPtr<UTexture2D> Thumbnail;
};

USTRUCT(BlueprintType)
struct FCatrunChapterInfo
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly) FName StageId;
	UPROPERTY(BlueprintReadOnly) FText DisplayName;
	UPROPERTY(BlueprintReadOnly) TSoftObjectPtr<UTexture2D> Thumbnail;
	UPROPERTY(BlueprintReadOnly) bool bUnlocked = false;
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
	UPROPERTY(Config, EditAnywhere, Category="Stage Clock", meta=(ClampMin="1", ClampMax="86400")) float Stage1BudgetSeconds = 600.f;
	UPROPERTY(Config, EditAnywhere, Category="Stage Clock", meta=(ClampMin="1", ClampMax="86400")) float Stage2BudgetSeconds = 900.f;
	/** Initial Stage3 tuning; each attempt starts with the full budget. */
	UPROPERTY(Config, EditAnywhere, Category="Stage Clock", meta=(ClampMin="1", ClampMax="86400")) float Stage3BudgetSeconds = 1200.f;
	UPROPERTY(Config, EditAnywhere, Category="Stage Clock", meta=(ClampMin="0", ClampMax="1")) float WarningFraction = .3f;
	UPROPERTY(Config, EditAnywhere, Category="Stage Clock", meta=(ClampMin="0", ClampMax="1")) float UrgentFraction = .15f;
	float GetClockBudget(FName StageId) const;

	int32 FindStageIndex(const FString& PackageName) const;
	float GetCameraDistanceScale(FName StageId) const;
	FText GetStageDisplayName(FName StageId) const;
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FCatrunStageCompleted, FName, StageId);
DECLARE_DYNAMIC_DELEGATE(FCatrunTravelFailureCallback);

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
	bool ContinueStage(FName StageId);
	bool CompleteStage();
	bool ReturnToMenu();
	bool RestartStage();
	/** The owner restores its own presentation after a same-world engine failure. Rejection returns false without invoking Failure. */
	bool CompleteStageWithFailure(UObject* Owner, TFunction<void(const FString&)> Failure);
	/** Same-map recovery also supports loaded development maps outside the canonical stage routes. */
	bool RequestSameMapRestart(UObject* Owner, float FadeInDuration, TFunction<void(const FString&)> Failure = {}, bool bFailureRestart = false);
	/** Cancels only this surviving world's pending request belonging to Owner. Never invokes its failure callback. */
	bool AbortOwnedTravel(const UObject* Owner);
	/** A timeout whose restart travel failed may fire again after RetryDelay seconds of advancing gameplay time. */
	void RearmStageTimeout(float RetryDelay);
	bool ReserveExitTransition(UObject* Owner);
	void ReleaseExitTransition(const UObject* Owner);
	bool CompleteStageForExit(UObject* Owner);
	void AbortExitTravel(const UObject* Owner);
	bool ShouldShowTutorialControls();
	void MarkTutorialOnboardingCompleted();
	/** Stable for this world: consuming the travel token never changes subsequent BP query results. */
	UFUNCTION(BlueprintCallable, Category="Level Flow")
	bool ShouldSkipStageIntro();
	bool IsStage2PortalArrival() const;
	bool IsStage3ElevatorArrival() const;
	bool ClaimElevatorArrival(ACatrunElevatorTransition& Owner);
	void ReleaseElevatorArrival(const ACatrunElevatorTransition& Owner);
	bool HasPendingElevatorArrival() const { return ElevatorArrivalOwner.IsValid(); }
	float GetRestartFadeInDuration();
	UFUNCTION(BlueprintPure, Category="Catrun|Stage Clock")
	FCatrunStageClockState GetStageClockState() const;
	UFUNCTION(BlueprintPure, Category="Catrun|Stage Clock")
	bool IsGameplayTimeAdvancing() const;
    bool IsTitleWindowOpen();
    bool ClaimArrivalTitleGate(UCatrunExitTransitionComponent& Owner);
    void ReleaseArrivalTitleGate(const UCatrunExitTransitionComponent& Owner);
    bool ConsumeStageTitle(FText& OutTitle);
	FText GetCurrentStageTitle() const;
	bool ApplyStageCameraProfile(UCameraComponent* Camera, USpringArmComponent* SpringArm);
	UFUNCTION(BlueprintCallable, Category="Level Flow")
	void SetPauseMenu(bool bOpen);
	bool IsTransitioning() const { return bTransitioning || ExitReservation.IsValid(); }
	bool IsStageComplete() const { return bStageComplete; }
	/** Cached world identity only; cinematic/input ownership remains live. Refreshes when package/settings change. */
	bool IsMainMenuWorld() const;

	UPROPERTY(BlueprintAssignable, Category="Level Flow")
	FCatrunStageCompleted OnStageCompleted;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Level Flow")
	bool bStageComplete = false;

private:
	bool TravelTo(const TSoftObjectPtr<UWorld>& Map, const FString& Options = FString(), bool bBeginProgress = false,
		bool bCheckpoint = false, ECatrunArrivalRestart Restart = ECatrunArrivalRestart::Clear, UObject* ExitOwner = nullptr, int8 Onboarding = -1,
		UObject* FailureOwner = nullptr, TFunction<void(const FString&)> Failure = {}, float FadeInDuration = 0.f, bool bReloadCurrentWorld = false, ECatrunProgressArrival Progress = ECatrunProgressArrival::Resume);
	bool CompleteStageInternal(UObject* ExitOwner, UObject* FailureOwner = nullptr, TFunction<void(const FString&)> Failure = {},
		const TCHAR* ArrivalOption = TEXT(""));
	void ClearFailedTravel();
	void FinishTravel();
	void ResolveRestartIntent();
	mutable FName CachedWorldPackageName, CachedMenuPackageName, NormalizedWorldPackageName;
	mutable bool bMenuIdentityCached = false, bMainMenuWorld = false;
	bool bRestartIntentResolved = false;
	bool bSkipStageIntro = false;
	bool bContinueArrival = false;
	FName PlayableStage;
	bool bGameplayWasAdvancing = false;
	bool bTimeoutAttempted = false;
	float TimeoutRetryDelay = 0.f;
	bool bStatusClassResolved = false;
    bool bStageTitlePending = false;
    bool bArrivalTitleReleased = false;
    TWeakObjectPtr<UCatrunExitTransitionComponent> ArrivalTitleOwner;
	TWeakObjectPtr<ACatrunElevatorTransition> ElevatorArrivalOwner;
	bool bElevatorArrivalReleased = false;
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
	TWeakObjectPtr<UObject> TravelFailureOwner;
	TFunction<void(const FString&)> TravelFailureCallback;
	FDelegateHandle TravelFailureHandle;
	UPROPERTY(Transient)
	TObjectPtr<UCatrunPlayHUD> PlayHUD;
	UPROPERTY(Transient) TObjectPtr<UUserWidget> PlayerStatusHUD;
};

UCLASS()
class CATRUN_API UCatrunLevelFlowLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()
public:
	UFUNCTION(BlueprintPure, Category="Catrun|Level Flow", meta=(WorldContext="WorldContextObject"))
	static UCatrunFlowSession* GetFlowSession(const UObject* WorldContextObject);
	/** Presentation-only query. Reads existing leases/view/input; never changes user HUD preferences or saving. */
	UFUNCTION(BlueprintPure, Category="Catrun|Presentation", meta=(WorldContext="WorldContextObject"))
	static bool ShouldHideGameplayHUD(const UObject* WorldContextObject);
	// Native-only policy for recovery instructions; all presentation owners still suppress it.
	static bool ShouldHideRecoveryNotice(const UObject* WorldContextObject);
	UFUNCTION(BlueprintPure, Category="Catrun|Level Flow", meta=(WorldContext="WorldContextObject"))
	static TArray<FCatrunChapterInfo> GetChapters(const UObject* WorldContextObject);
	UFUNCTION(BlueprintPure, Category="Catrun|Level Flow", meta=(WorldContext="WorldContextObject"))
	static TArray<FName> GetUnlockedStages(const UObject* WorldContextObject);
	UFUNCTION(BlueprintPure, Category="Catrun|Level Flow", meta=(WorldContext="WorldContextObject"))
	static bool CanContinueStage(const UObject* WorldContextObject, FName StageId);
	UFUNCTION(BlueprintCallable, Category="Catrun|Level Flow", meta=(WorldContext="WorldContextObject"))
	static bool ContinueStage(const UObject* WorldContextObject, FName StageId);
	UFUNCTION(BlueprintPure, Category="Catrun|Progress", meta=(WorldContext="WorldContextObject"))
	static ECatrunCheckpointState GetCheckpointState(const UObject* WorldContextObject);
	UFUNCTION(BlueprintPure, Category="Catrun|Level Flow", meta=(WorldContext="WorldContextObject"))
	static FText GetCurrentStageTitle(const UObject* WorldContextObject);
	UFUNCTION(BlueprintCallable, Category="Catrun|Level Flow", meta=(WorldContext="WorldContextObject"))
    static bool ConsumeStageTitle(const UObject* WorldContextObject, FText& OutTitle);
    UFUNCTION(BlueprintCallable, Category="Catrun|Level Flow", meta=(WorldContext="WorldContextObject", Latent, LatentInfo="LatentInfo"))
    static void WaitForStageTitleWindow(const UObject* WorldContextObject, FLatentActionInfo LatentInfo);
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
	/** Both immediate rejection and a later same-world failure invoke this owner's BP cleanup once. */
	UFUNCTION(BlueprintCallable, Category="Catrun|Level Flow", meta=(WorldContext="WorldContextObject"))
	static bool CompleteCurrentStageWithFailure(const UObject* WorldContextObject, UObject* Owner, FCatrunTravelFailureCallback Failure);
	UFUNCTION(BlueprintCallable, Category="Catrun|Level Flow")
	static bool ReserveStagePresentation(UObject* Owner);
	UFUNCTION(BlueprintCallable, Category="Catrun|Level Flow")
	static void ReleaseStagePresentation(UObject* Owner);
	/** Restore the pre-cinematic pawn pose through the existing collision-safe recovery policy. BP owns its sequence, camera and input locks. */
	UFUNCTION(BlueprintCallable, Category="Catrun|Level Flow")
	static bool RestoreFailedStagePawn(APawn* Pawn, const FTransform& OriginalTransform, bool bOriginalCollision = true);
	UFUNCTION(BlueprintCallable, Category="Catrun|Level Flow", meta=(WorldContext="WorldContextObject"))
	static bool ReturnToMainMenu(const UObject* WorldContextObject);
	UFUNCTION(BlueprintCallable, Category="Catrun|Level Flow", meta=(WorldContext="WorldContextObject"))
	static bool RestartCurrentStage(const UObject* WorldContextObject);
	UFUNCTION(BlueprintCallable, Category="Catrun|Level Flow", meta=(WorldContext="WorldContextObject"))
	static bool ShouldSkipStageIntro(const UObject* WorldContextObject);
	/** Reads the current arrival route without consuming its travel or restart intent. */
	UFUNCTION(BlueprintPure, Category="Catrun|Level Flow", meta=(WorldContext="WorldContextObject"))
	static bool IsStage2PortalArrival(const UObject* WorldContextObject);
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
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;
	virtual void Tick(float DeltaSeconds) override;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Exit")
	TObjectPtr<UBoxComponent> Trigger;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Exit")
	TObjectPtr<UCatrunExitTransitionComponent> ExitTransition;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Exit") bool bRequireCenterInside = false;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Exit") bool bUseExitTransition = false;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Exit") FVector InteriorDirectionLocal = FVector::ZeroVector;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Exit") float MinimumInteriorDepth = 0.f;
	UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Exit") bool bProtectStage1Corridor = false;
    UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Exit") float CorridorEntryDepth = 0.f;
    bool IsInsideCorridor(const APawn& Pawn) const;
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
    void ObserveLocalController(APlayerController* Player);
    UFUNCTION() void OnCorridorControllerAssigned(APawn* Pawn, AController* Controller);
    UFUNCTION() void OnCorridorPossessionChanged(APawn* Previous, APawn* Current);
    TWeakObjectPtr<APlayerController> CorridorController;
    bool IsCenterBeyondDepth(const FVector& WorldLocation, float Depth) const;
    bool bArmed = true;
	TWeakObjectPtr<APawn> OverlappingPawn;
	UFUNCTION()
	void HandleOverlap(AActor* OverlappedActor, AActor* OtherActor);
	UFUNCTION()
	void HandleEndOverlap(AActor* OverlappedActor, AActor* OtherActor);
};
