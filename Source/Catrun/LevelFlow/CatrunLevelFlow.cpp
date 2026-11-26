#include "CatrunLevelFlow.h"
#include "CatrunPlayHUD.h"
#include "CatrunProgressSave.h"
#include "CatrunProgressWriter.h"
#include "CatrunExitTransitionComponent.h"
#include "CatrunElevatorTransition.h"
#include "Interaction/CatrunPuzzleSuspension.h"
#include "Interaction/CatrunBasketInteractionComponent.h"
#include "Settings/CatrunUserSettings.h"
#include "Settings/CatrunSettingsSubsystem.h"
#include "HAL/IConsoleManager.h"

#include "Components/BoxComponent.h"
#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Engine/GameInstance.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PawnMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"
#include "Interaction/CatrunBasketInteractionComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/PackageName.h"
#include "Monster/CatrunRestartSubsystem.h"
#include "Monster/CatrunCapturePresentationComponent.h"
#include "Monster/CatrunMarkSubsystem.h"
#include "LatentActions.h"
#include "Sound/CatrunNotice.h"
#include "Perception/CatrunSafeRestore.h"
#include "SaveGameSystem.h"
#include "UI/CatrunPlayerStatusWidget.h"

DEFINE_LOG_CATEGORY_STATIC(LogCatrunFlow, Log, All);

namespace
{
	const FString ProgressSlot(TEXT("CatrunProgress"));
	constexpr int32 ProgressUser = 0;
	constexpr TCHAR Stage1PortalArrivalOption[] = TEXT("FromStage1Portal");
	constexpr TCHAR Stage2ElevatorArrivalOption[] = TEXT("FromStage2Elevator");

	UCatrunFlowSession* GetFlowSession(UWorld* World)
	{
		UGameInstance* Instance = World ? World->GetGameInstance() : nullptr;
		return Instance ? Instance->GetSubsystem<UCatrunFlowSession>() : nullptr;
	}

	int32 FindStageId(FName StageId)
	{
		const auto& Stages = GetDefault<UCatrunLevelFlowSettings>()->Stages;
		return Stages.IndexOfByPredicate([StageId](const FCatrunStageRoute& Stage) { return Stage.StageId == StageId; });
	}
	const UCatrunProgressSave* DecodeProgress(const TArray<uint8>& Data)
	{
		const auto* Save = UCatrunProgressSave::Decode(Data);
		if (!Save || FindStageId(Save->StageId) == INDEX_NONE) return nullptr;
		if (Save->SchemaVersion >= 3 && !Save->HighestUnlockedStageId.IsNone()
			&& FindStageId(Save->HighestUnlockedStageId) == INDEX_NONE) return nullptr;
		return Save;
	}
	FString SoundTestPackage(const FCatrunStageRoute& Stage)
	{
		return FPackageName::GetLongPackagePath(Stage.Map.ToSoftObjectPath().GetLongPackageName())
			/ (TEXT("SoundTest_") + Stage.StageId.ToString());
	}
	bool IsAvailableStage(int32 Index)
	{
		const auto& Stages = GetDefault<UCatrunLevelFlowSettings>()->Stages;
		return Stages.IsValidIndex(Index) && FPackageName::DoesPackageExist(Stages[Index].Map.ToSoftObjectPath().GetLongPackageName());
	}


	bool IsGameplayCameraOwner(const AActor* Actor, const APawn* Pawn)
	{
		if (!Actor) return false;
		if (Actor == Pawn || Actor->ActorHasTag(TEXT("CatrunGameplayCamera"))) return true;
		for (const UClass* Class = Actor->GetClass(); Class; Class = Class->GetSuperClass())
			if (Class->GetFName() == TEXT("BP_QuarterViewCamera_C")) return true;
		return false;
	}
}

#if WITH_EDITOR
static TAutoConsoleVariable<int32> CVarDebugRestart(TEXT("catrun.DebugRestart"), 0,
	TEXT("Enable R quick restart in PIE only. Disabled by default."), ECVF_Cheat);
#endif

void FCatrunRestartIntent::Request(const FString& Package, float FadeDuration, bool bIsContinue)
{
	bContinue = bIsContinue;
	MapPackage = UWorld::RemovePIEPrefix(Package);
	FadeInDuration = FMath::IsFinite(FadeDuration) ? FMath::Max(0.f, FadeDuration) : 0.f;
}

void FCatrunRestartIntent::Clear()
{
	bContinue = false;
	MapPackage.Reset();
	FadeInDuration = 0.f;
}

bool FCatrunRestartIntent::Consume(const FString& Package, float& OutFadeDuration)
{
	const bool bMatches = !MapPackage.IsEmpty() && MapPackage == UWorld::RemovePIEPrefix(Package);
	OutFadeDuration = bMatches ? FadeInDuration : 0.f;
	Clear();
	return bMatches;
}

uint64 UCatrunFlowSession::AcceptTravel(const FString& Package, bool bBeginProgress, bool bCheckpoint, ECatrunArrivalRestart Restart, int8 OnboardingOnArrival, float FadeInDuration, ECatrunProgressArrival Progress)
{
	TitleIntentMap.Reset();
	ProgressOnArrival = Progress;
	AcceptedOnboarding = OnboardingOnArrival;
	AcceptedTravelMap = UWorld::RemovePIEPrefix(Package);
	bBeginProgressOnArrival = bBeginProgress;
	bCheckpointOnArrival = bCheckpoint;
	ArrivalRestart = Restart;
	ArrivalFadeInDuration = FMath::IsFinite(FadeInDuration) ? FMath::Max(0.f, FadeInDuration) : 0.f;
	AcceptedTravelToken = ++NextTravelToken;
	return AcceptedTravelToken;
}

void UCatrunFlowSession::CancelTravel(uint64 ExpectedToken)
{
	if (ExpectedToken && AcceptedTravelToken != ExpectedToken) return;
	AcceptedTravelToken = 0;
	AcceptedOnboarding = -1;
	AcceptedTravelMap.Reset();
	bBeginProgressOnArrival = false;
	bCheckpointOnArrival = false;
	ArrivalRestart = ECatrunArrivalRestart::Preserve;
	ArrivalFadeInDuration = 0.f;
	ProgressOnArrival = ECatrunProgressArrival::Resume;
}

void UCatrunFlowSession::ResolveArrivalRestart(const FString& Package)
{
	if (AcceptedTravelMap.IsEmpty() || AcceptedTravelMap != UWorld::RemovePIEPrefix(Package)) return;
	if ((ArrivalRestart == ECatrunArrivalRestart::Clear || ArrivalRestart == ECatrunArrivalRestart::Continue)
		&& GetDefault<UCatrunLevelFlowSettings>()->FindStageIndex(AcceptedTravelMap) != INDEX_NONE)
		TitleIntentMap = AcceptedTravelMap;
	if (ArrivalRestart == ECatrunArrivalRestart::SkipIntro || ArrivalRestart == ECatrunArrivalRestart::Continue)
		RestartIntent.Request(AcceptedTravelMap, ArrivalFadeInDuration, ArrivalRestart == ECatrunArrivalRestart::Continue);
	else if (ArrivalRestart == ECatrunArrivalRestart::Clear) RestartIntent.Clear();
	ArrivalRestart = ECatrunArrivalRestart::Preserve;
	ArrivalFadeInDuration = 0.f;
}

bool UCatrunFlowSession::HasRestartArrivalIntent(const FString& CleanPackage) const
{
	if (AcceptedTravelMap == CleanPackage && ArrivalRestart != ECatrunArrivalRestart::Preserve)
		return ArrivalRestart == ECatrunArrivalRestart::SkipIntro || ArrivalRestart == ECatrunArrivalRestart::Continue;
	return RestartIntent.MapPackage == CleanPackage;
}

bool UCatrunFlowSession::Arrive(const FString& Package)
{
	CaptureClock();
	const FString CleanPackage = UWorld::RemovePIEPrefix(Package);
	const bool bAccepted = !AcceptedTravelMap.IsEmpty() && AcceptedTravelMap == CleanPackage;
	if (bAccepted && bBeginProgressOnArrival) EnsureProgressLoaded();
	ResolveArrivalRestart(CleanPackage);
	const auto* Settings = GetDefault<UCatrunLevelFlowSettings>();
	const int32 Index = Settings->FindStageIndex(CleanPackage);
	CurrentStage = Settings->Stages.IsValidIndex(Index) ? Settings->Stages[Index].StageId : NAME_None;
	const bool bRefillStage1 = bAccepted && (ProgressOnArrival == ECatrunProgressArrival::NewRun
		|| (CurrentStage == TEXT("Stage1") && ProgressOnArrival != ECatrunProgressArrival::Resume));
	const bool bCheckpoint = bAccepted && (bCheckpointOnArrival || bRefillStage1);
	if (bAccepted && bBeginProgressOnArrival)
	{
		++ProgressGeneration;
		if (AcceptedOnboarding >= 0) bTutorialOnboardingCompleted = AcceptedOnboarding != 0;
		ActiveProgressMap = CleanPackage;
	}
	else if (bCheckpoint && !ActiveProgressMap.IsEmpty()) ActiveProgressMap = CleanPackage;
	else if (ActiveProgressMap != CleanPackage) ActiveProgressMap.Reset();
	if (bAccepted && IsTrackingWorld(CleanPackage))
	{
		LastTrackedStage = CurrentStage;
		if (Index > FindStageId(HighestUnlockedStageId)) HighestUnlockedStageId = Settings->Stages[Index].StageId;
	}
	if (bRefillStage1) RefillStage1Clock();
	if (CurrentStage == TEXT("Stage2")) Stage2Seconds = -1.;
	if (CurrentStage == TEXT("Stage3")) Stage3Seconds = -1.;
	if (!bAccepted) TitleIntentMap.Reset();
	CancelTravel();
	return bCheckpoint && !ActiveProgressMap.IsEmpty();
}


bool UCatrunFlowSession::IsTrackingWorld(const FString& Package) const
{
	return !ActiveProgressMap.IsEmpty() && ActiveProgressMap == UWorld::RemovePIEPrefix(Package);
}

UCatrunLevelFlowSettings::UCatrunLevelFlowSettings()
{
	for (const auto& Entry : {TPair<FName, float>(TEXT("Tutorial"), 1.f),
		TPair<FName, float>(TEXT("Stage1"), 1.15f), TPair<FName, float>(TEXT("Stage2"), 1.30f)})
	{
		auto& Profile = CameraProfiles.AddDefaulted_GetRef();
		Profile.StageId = Entry.Key;
		Profile.DistanceScale = Entry.Value;
	}
}

float UCatrunLevelFlowSettings::GetCameraDistanceScale(FName StageId) const
{
	// The original tutorial framing is a binding contract, including after settings edits.
	if (StageId == TEXT("Tutorial")) return 1.f;
	for (const auto& Profile : CameraProfiles)
		if (Profile.StageId == StageId && FMath::IsFinite(Profile.DistanceScale))
			return FMath::Clamp(Profile.DistanceScale, 1.f, 3.f);
	return 1.f;
}

float UCatrunLevelFlowSettings::GetClockBudget(FName StageId) const
{
	if (StageId == TEXT("Stage1")) return FMath::IsFinite(Stage1BudgetSeconds) ? FMath::Clamp(Stage1BudgetSeconds, 1.f, 86400.f) : 600.f;
	if (StageId == TEXT("Stage2")) return FMath::IsFinite(Stage2BudgetSeconds) ? FMath::Clamp(Stage2BudgetSeconds, 1.f, 86400.f) : 900.f;
	if (StageId == TEXT("Stage3")) return FMath::IsFinite(Stage3BudgetSeconds) ? FMath::Clamp(Stage3BudgetSeconds, 1.f, 86400.f) : 1200.f;
	return 0.f;
}

int32 UCatrunLevelFlowSettings::FindStageIndex(const FString& PackageName) const
{
	const FString CleanName = UWorld::RemovePIEPrefix(PackageName);
	const FName ShortName(*FPackageName::GetShortName(CleanName));
	for (int32 Index = 0; Index < Stages.Num(); ++Index)
	{
		// StageId also recognizes the original art maps opened directly during development.
		if (Stages[Index].Map.ToSoftObjectPath().GetLongPackageName() == CleanName || Stages[Index].StageId == ShortName
			|| (ShortName.ToString().StartsWith(TEXT("SoundTest_")) && CleanName == SoundTestPackage(Stages[Index])))
			return Index;
	}
	return INDEX_NONE;
}

UCatrunLevelFlowSubsystem* UCatrunLevelFlowSubsystem::Get(const UObject* Context)
{
	UWorld* World = GEngine ? GEngine->GetWorldFromContextObject(Context, EGetWorldErrorMode::ReturnNull) : nullptr;
	return World ? World->GetSubsystem<UCatrunLevelFlowSubsystem>() : nullptr;
}

bool UCatrunLevelFlowSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	const UWorld* World = Cast<UWorld>(Outer);
	return World && World->IsGameWorld();
}

void UCatrunLevelFlowSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	IsMainMenuWorld();
	if (GEngine)
		TravelFailureHandle = GEngine->OnTravelFailure().AddWeakLambda(this,
			[this](UWorld* FailedWorld, ETravelFailure::Type, const FString& Error)
			{
				if (FailedWorld != GetWorld() || !bTransitioning || FailedWorld->bIsTearingDown) return;
				UE_LOG(LogCatrunFlow, Error, TEXT("Travel failed; progress retained: %s"), *Error);
                auto* Exit = Cast<UCatrunExitTransitionComponent>(ExitReservation.Get());
                const TWeakObjectPtr<UObject> FailureOwner = TravelFailureOwner;
                auto Failure = MoveTemp(TravelFailureCallback);
                ClearFailedTravel();
                if (Exit) Exit->NotifyTravelFailure(Error);
                if (FailureOwner.IsValid() && Failure) Failure(Error);
			});
}

bool UCatrunLevelFlowSubsystem::IsMainMenuWorld() const
{
    const UWorld* World = GetWorld();
    if (!World) return false;
    const FName WorldPackage = World->GetOutermost()->GetFName();
    const FName MenuPackage = GetDefault<UCatrunLevelFlowSettings>()->MainMenuMap.ToSoftObjectPath().GetLongPackageFName();
    if (!bMenuIdentityCached || WorldPackage != CachedWorldPackageName)
    {
        CachedWorldPackageName = WorldPackage;
        NormalizedWorldPackageName = FName(*UWorld::RemovePIEPrefix(WorldPackage.ToString()));
        bMenuIdentityCached = false;
    }
    if (!bMenuIdentityCached || MenuPackage != CachedMenuPackageName)
    {
        CachedMenuPackageName = MenuPackage;
        bMainMenuWorld = !MenuPackage.IsNone() && NormalizedWorldPackageName == MenuPackage;
        bMenuIdentityCached = true;
    }
    return bMainMenuWorld;
}

void UCatrunLevelFlowSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);
	const auto* Routes = GetDefault<UCatrunLevelFlowSettings>();
	const int32 Index = Routes->FindStageIndex(InWorld.GetOutermost()->GetName());
	if (Routes->Stages.IsValidIndex(Index)) PlayableStage = Routes->Stages[Index].StageId;
	// Intro queries also resolve lazily, so subsystem initialization order cannot consume the token twice.
	ResolveRestartIntent();
	if (auto* Session = GetFlowSession(&InWorld))
		if (Session->Arrive(InWorld.GetOutermost()->GetName()))
			Session->SaveArrivalCheckpoint(InWorld, bContinueArrival);
	if (auto* Settings = UCatrunUserSettings::GetCatrunUserSettings()) Settings->ApplyAudioVolume(&InWorld);
}

void UCatrunLevelFlowSubsystem::ResolveRestartIntent()
{
	if (bRestartIntentResolved) return;
	bRestartIntentResolved = true;
	if (UGameInstance* Instance = GetWorld()->GetGameInstance())
		if (auto* Session = Instance->GetSubsystem<UCatrunFlowSession>())
		{
			Session->ResolveArrivalRestart(GetWorld()->GetOutermost()->GetName());
			bStageTitlePending = Session->ConsumeArrivalTitle(GetWorld()->GetOutermost()->GetName());
			bContinueArrival = Session->RestartIntent.bContinue;
			bSkipStageIntro = Session->RestartIntent.Consume(GetWorld()->GetOutermost()->GetName(), RestartFadeInDuration);
			bContinueArrival &= bSkipStageIntro;
		}
}

bool UCatrunLevelFlowSubsystem::ShouldSkipStageIntro()
{
	ResolveRestartIntent();
	return bSkipStageIntro;
}

bool UCatrunLevelFlowSubsystem::IsStage2PortalArrival() const
{
	UWorld* World = GetWorld();
	if (!World || !World->URL.HasOption(Stage1PortalArrivalOption)) return false;
	const int32 Stage2Index = FindStageId(TEXT("Stage2"));
	if (Stage2Index == INDEX_NONE) return false;
	const FString Package = UWorld::RemovePIEPrefix(World->GetOutermost()->GetName());
	const auto& Stage2 = GetDefault<UCatrunLevelFlowSettings>()->Stages[Stage2Index];
	if (Package != Stage2.Map.ToSoftObjectPath().GetLongPackageName() && Package != SoundTestPackage(Stage2)) return false;
	if (bRestartIntentResolved) return !bSkipStageIntro;
	const auto* Session = GetFlowSession(World);
	return !Session || !Session->HasRestartArrivalIntent(Package);
}

bool UCatrunLevelFlowSubsystem::IsStage3ElevatorArrival() const
{
	const UWorld* World = GetWorld();
	if (!World || !World->URL.HasOption(Stage2ElevatorArrivalOption) || bSkipStageIntro) return false;
	const auto* Settings = GetDefault<UCatrunLevelFlowSettings>();
	const int32 Index = Settings->FindStageIndex(World->GetOutermost()->GetName());
	if (!Settings->Stages.IsValidIndex(Index) || Settings->Stages[Index].StageId != TEXT("Stage3")) return false;
	const auto* Session = GetFlowSession(GetWorld());
	return bRestartIntentResolved || !Session || !Session->HasRestartArrivalIntent(UWorld::RemovePIEPrefix(World->GetOutermost()->GetName()));
}

bool UCatrunLevelFlowSubsystem::ClaimElevatorArrival(ACatrunElevatorTransition& Owner)
{
	if (Owner.GetWorld() != GetWorld() || !IsStage3ElevatorArrival() || bElevatorArrivalReleased) return false;
	if (ElevatorArrivalOwner.IsValid()) return ElevatorArrivalOwner.Get() == &Owner;
	ElevatorArrivalOwner = &Owner;
	return true;
}

void UCatrunLevelFlowSubsystem::ReleaseElevatorArrival(const ACatrunElevatorTransition& Owner)
{
	if (ElevatorArrivalOwner.Get(true) != &Owner || (Owner.ExitTransition && Owner.ExitTransition->HasExitLease())) return;
	ElevatorArrivalOwner.Reset();
	bElevatorArrivalReleased = true;
}

float UCatrunLevelFlowSubsystem::GetRestartFadeInDuration()
{
	ResolveRestartIntent();
	return RestartFadeInDuration;
}

bool UCatrunLevelFlowSubsystem::ApplyStageCameraProfile(UCameraComponent* Camera, USpringArmComponent* SpringArm)
{
	const auto* Settings = GetDefault<UCatrunLevelFlowSettings>();
	const int32 Index = Settings->FindStageIndex(GetWorld()->GetOutermost()->GetName());
	APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0);
	APawn* Pawn = PC ? PC->GetPawn() : nullptr;
	// A temporary camera, or even the pawn camera during a cinematic, cannot define the baseline.
	if (Index == INDEX_NONE || !Camera || !Pawn || Camera->GetWorld() != GetWorld()
		|| !IsGameplayCameraOwner(Camera->GetOwner(), Pawn) || PC->GetViewTarget() != Camera->GetOwner()) return false;
	const float Scale = Settings->GetCameraDistanceScale(Settings->Stages[Index].StageId);
	if (Settings->Stages[Index].StageId == TEXT("Tutorial")) return true;
	if (SpringArm && (SpringArm->GetOwner() != Camera->GetOwner() || !Camera->IsAttachedTo(SpringArm))) return false;
	if (Camera->ProjectionMode == ECameraProjectionMode::Perspective && !SpringArm) return false;
	if (GameplayCamera.Get() != Camera)
	{
		GameplayCamera = Camera;
		AuthoredOrthoWidth = Camera->OrthoWidth;
	}
	if (SpringArm && GameplaySpringArm.Get() != SpringArm)
	{
		GameplaySpringArm = SpringArm;
		AuthoredArmLength = SpringArm->TargetArmLength;
	}
	if (Camera->ProjectionMode == ECameraProjectionMode::Orthographic)
		Camera->SetOrthoWidth(AuthoredOrthoWidth * Scale);
	else
		SpringArm->TargetArmLength = AuthoredArmLength * Scale;
	return true;
}

void UCatrunLevelFlowSubsystem::Deinitialize()
{
	if (GEngine) GEngine->OnTravelFailure().Remove(TravelFailureHandle);
	if (auto* PC = TravelLockController.Get()) PC->SetIgnoreMoveInput(false);
	TravelLockController.Reset();
	ExitReservation.Reset();
	TravelFailureOwner.Reset(); TravelFailureCallback = {};
	if (PlayHUD) PlayHUD->RemoveFromParent();
	if (PlayerStatusHUD) PlayerStatusHUD->RemoveFromParent();
	PlayerStatusHUD = nullptr;
	Super::Deinitialize();
}

TStatId UCatrunLevelFlowSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UCatrunLevelFlowSubsystem, STATGROUP_Tickables);
}

void UCatrunLevelFlowSubsystem::Tick(float DeltaSeconds)
{
	if (PlayableStage.IsNone()) return;
	const bool bAdvancing = IsGameplayTimeAdvancing();
	if (auto* Session = GetFlowSession(GetWorld()); bAdvancing && Session && PlayableStage != TEXT("Tutorial"))
	{
		// Do not charge the delta spanning release of a presentation or arrival.
		if (bGameplayWasAdvancing) Session->AdvanceClock(DeltaSeconds);
		// A failed timeout restart waits out its notice before retrying; paused time does not count.
		if (TimeoutRetryDelay > 0.f) TimeoutRetryDelay = FMath::Max(0.f, TimeoutRetryDelay - DeltaSeconds);
		if (!bTimeoutAttempted && TimeoutRetryDelay <= 0.f && Session->GetRemainingSeconds(PlayableStage) <= 0.f)
			if (auto* Restart = UCatrunRestartSubsystem::Get(this)) bTimeoutAttempted = Restart->BeginStageTimeout();
	}
	bGameplayWasAdvancing = bAdvancing;
	if (IsTransitioning()) return;
	APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0);
	if (!PC) return;
	if (!bStatusClassResolved && PC->GetLocalPlayer() && PC->GetPawn())
	{
		bStatusClassResolved = true;
		UClass* StatusClass = LoadClass<UCatrunPlayerStatusWidget>(nullptr,
			TEXT("/Game/UI/Gameplay/WBP_PlayerStatus.WBP_PlayerStatus_C"));
		if (StatusClass)
		{
			PlayerStatusHUD = CreateWidget<UCatrunPlayerStatusWidget>(PC, StatusClass);
			if (PlayerStatusHUD) PlayerStatusHUD->AddToViewport(105);
		}
	}
	// The tutorial already owns its intro, key hints and cinematic input handling.
	if (PlayableStage == TEXT("Tutorial")) return;
	if (!GameplayCamera.IsValid() && PC->GetPawn() && IsGameplayCameraOwner(PC->GetViewTarget(), PC->GetPawn()) && !PC->IsMoveInputIgnored())
	{
		const ACharacter* Character = Cast<ACharacter>(PC->GetPawn());
		if (!Character || Character->GetCharacterMovement()->MovementMode != MOVE_None)
		{
			if (auto* Camera = PC->GetViewTarget()->FindComponentByClass<UCameraComponent>())
			{
				USpringArmComponent* Arm = nullptr;
				for (USceneComponent* Parent = Camera->GetAttachParent(); Parent; Parent = Parent->GetAttachParent())
					if ((Arm = Cast<USpringArmComponent>(Parent))) break;
				ApplyStageCameraProfile(Camera, Arm);
			}
		}
	}
	if (!PlayHUD)
	{
		PlayHUD = CreateWidget<UCatrunPlayHUD>(PC, UCatrunPlayHUD::StaticClass());
		if (PlayHUD) PlayHUD->AddToViewport(110);
	}

#if WITH_EDITOR
	if (GetWorld()->WorldType == EWorldType::PIE && CVarDebugRestart.GetValueOnGameThread() != 0 && PC->WasInputKeyJustPressed(EKeys::R)) RestartStage();
#endif
}

void UCatrunLevelFlowSubsystem::SetPauseMenu(bool bOpen)
{
 if (IsTransitioning()) return;
 if (auto* Settings=UCatrunSettingsSubsystem::Get(this))
 {
  if (bOpen) Settings->OpenSettings(UGameplayStatics::GetPlayerController(this,0));
  else Settings->CloseSettings();
 }
}

bool UCatrunLevelFlowSubsystem::TravelTo(const TSoftObjectPtr<UWorld>& Map, const FString& Options,
    bool bBeginProgress, bool bCheckpoint, ECatrunArrivalRestart Restart, UObject* ExitOwner, int8 Onboarding,
    UObject* FailureOwner, TFunction<void(const FString&)> Failure, float FadeInDuration, bool bReloadCurrentWorld, ECatrunProgressArrival Progress)
{
    if (bTransitioning || (ExitReservation.IsValid() && ExitReservation.Get() != ExitOwner)) return false;
    if (ExitOwner && ExitReservation.Get() != ExitOwner) return false;
	const FWorldContext* Context = GEngine ? GEngine->GetWorldContextFromWorld(GetWorld()) : nullptr;
	if (!Context || !Context->TravelURL.IsEmpty() || GetWorld()->bIsTearingDown || GetWorld()->IsInSeamlessTravel()) return false;
	if (FailureOwner && (!IsValid(FailureOwner) || FailureOwner->GetWorld() != GetWorld())) return false;
	const FString Package = Map.ToSoftObjectPath().GetLongPackageName();
	const bool bLoadedCurrentWorld = bReloadCurrentWorld && Package == UWorld::RemovePIEPrefix(GetWorld()->GetOutermost()->GetName());
	if (Package.IsEmpty() || (!bLoadedCurrentWorld && !FPackageName::DoesPackageExist(Package)))
	{
		UE_LOG(LogCatrunFlow, Error, TEXT("Cannot travel: missing map '%s'."), *Package);
		if (auto* Notice = UCatrunNoticeSubsystem::Get(this))
			Notice->ShowNotice(NSLOCTEXT("Catrun", "MissingFlowMap", "다음 구역을 불러올 수 없습니다."), 5.f);
		return false;
	}
	PendingMap = Package;
	PendingOptions = Options;
	TravelFailureOwner = FailureOwner;
	TravelFailureCallback = MoveTemp(Failure);
	bTransitioning = true;
	if (auto* SettingsUI=UCatrunSettingsSubsystem::Get(this)) SettingsUI->CloseSettings();
	if (APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0))
	{
		if (!ExitOwner) { PC->SetIgnoreMoveInput(true); TravelLockController = PC; }
		if (APawn* Pawn = PC->GetPawn())
			if (UPawnMovementComponent* Movement = Pawn->GetMovementComponent()) Movement->StopMovementImmediately();
	}
	UE_LOG(LogCatrunFlow, Log, TEXT("Travel requested: %s -> %s [%s]"), *GetWorld()->GetOutermost()->GetName(), *Package, *Options);
	// Existing level cinematics own their fades. Travel must not add another one.
	if (auto* Session = GetFlowSession(GetWorld()))
		PendingTravelToken = Session->AcceptTravel(PendingMap, bBeginProgress, bCheckpoint, Restart, Onboarding, FadeInDuration, Progress);
	FinishTravel();
	return bTransitioning;
}

void UCatrunLevelFlowSubsystem::FinishTravel()
{
	UGameplayStatics::OpenLevel(this, FName(*PendingMap), true, PendingOptions);
}

bool UCatrunLevelFlowSubsystem::StartGame()
{
    const auto* Settings = GetDefault<UCatrunLevelFlowSettings>();
    return Settings->Stages.Num() > 0 && TravelTo(Settings->Stages[0].Map, FString(), true, true,
        ECatrunArrivalRestart::Clear, nullptr, 0, nullptr, {}, 0.f, false, ECatrunProgressArrival::NewRun);
}

bool UCatrunLevelFlowSubsystem::ContinueGame()
{
    auto* Session = GetFlowSession(GetWorld());
    return Session && !Session->IsSavePending() && ContinueStage(Session->GetContinueStageId());
}

bool UCatrunLevelFlowSubsystem::ContinueStage(FName StageId)
{
    if (!UCatrunLevelFlowLibrary::CanContinueStage(this, StageId)) return false;
    auto* Session = GetFlowSession(GetWorld());
    const bool bChapterChanged = Session->GetContinueStageId() != StageId;
    return TravelTo(GetDefault<UCatrunLevelFlowSettings>()->Stages[FindStageId(StageId)].Map,
        FString(), true, bChapterChanged, ECatrunArrivalRestart::Continue, nullptr, Session->HasCompletedOnboarding() ? 1 : 0);
}

bool UCatrunLevelFlowSubsystem::CompleteStage() { return CompleteStageInternal(nullptr); }

bool UCatrunLevelFlowSubsystem::CompleteStageWithFailure(UObject* Owner, TFunction<void(const FString&)> Failure)
{
    if (!IsValid(Owner) || Owner->GetWorld() != GetWorld()) return false;
    return CompleteStageInternal(ExitReservation.Get() == Owner ? Owner : nullptr, Owner, MoveTemp(Failure));
}

bool UCatrunLevelFlowSubsystem::RequestSameMapRestart(UObject* Owner, float FadeInDuration, TFunction<void(const FString&)> Failure, bool bFailureRestart)
{
    if (!IsValid(Owner) || Owner->GetWorld() != GetWorld() || IsTransitioning() || bStageComplete) return false;
    // This low-level recovery path deliberately permits the current capture's catch reservation.
    const FString Package = UWorld::RemovePIEPrefix(GetWorld()->GetOutermost()->GetName());
    return TravelTo(TSoftObjectPtr<UWorld>(FSoftObjectPath(Package)), FString(), false, false,
        ECatrunArrivalRestart::SkipIntro, nullptr, -1, Owner, MoveTemp(Failure), FadeInDuration, true,
        bFailureRestart ? ECatrunProgressArrival::FailureRefill : ECatrunProgressArrival::Resume);
}

bool UCatrunLevelFlowSubsystem::CompleteStageInternal(UObject* ExitOwner, UObject* FailureOwner,
	TFunction<void(const FString&)> Failure, const TCHAR* ArrivalOption)
{
	if (bTransitioning || bStageComplete || (ExitReservation.IsValid() && ExitReservation.Get() != ExitOwner)) return false;
	if (const auto* Restart = UCatrunRestartSubsystem::Get(this); Restart && Restart->IsCatching()) return false;
	const auto* Settings = GetDefault<UCatrunLevelFlowSettings>();
	const int32 Index = Settings->FindStageIndex(GetWorld()->GetOutermost()->GetName());
	if (Index == INDEX_NONE) return false;
	if (Settings->Stages.IsValidIndex(Index + 1))
	{
		// Preserve the existing tutorial stair arrival Blueprint's URL option.
		const FString Options = Settings->Stages[Index].StageId == TEXT("Tutorial") ? TEXT("FromTutorial") : ArrivalOption;
        auto* Session = GetFlowSession(GetWorld());
        const auto& Next = Settings->Stages[Index + 1];
        TSoftObjectPtr<UWorld> Destination = Next.Map;
        if (UWorld::RemovePIEPrefix(GetWorld()->GetOutermost()->GetName()) == SoundTestPackage(Settings->Stages[Index]))
        {
            const FString Mirror = SoundTestPackage(Next);
            if (FPackageName::DoesPackageExist(Mirror)) Destination = TSoftObjectPtr<UWorld>(FSoftObjectPath(Mirror));
        }
        return TravelTo(Destination, Options, false,
            Session && Session->IsTrackingWorld(GetWorld()->GetOutermost()->GetName()), ECatrunArrivalRestart::Clear, ExitOwner,
            -1, FailureOwner, MoveTemp(Failure));
	}

	bStageComplete = true;
	const FName StageId = Settings->Stages[Index].StageId;
	UE_LOG(LogCatrunFlow, Log, TEXT("Stage complete, remaining in map: %s"), *StageId.ToString());
	// The play HUD shows a persistent completion card without interrupting movement.
	OnStageCompleted.Broadcast(StageId);
	return true;
}

bool UCatrunLevelFlowSubsystem::ReturnToMenu()
{
    if (!TravelTo(GetDefault<UCatrunLevelFlowSettings>()->MainMenuMap)) return false;
    if (auto* Session = GetFlowSession(GetWorld())) Session->FlushTrackedProgress();
    return true;
}

bool UCatrunLevelFlowSubsystem::RestartStage()
{
    if (IsTransitioning()) return false;
    const auto* Settings = GetDefault<UCatrunLevelFlowSettings>();
    if (Settings->FindStageIndex(GetWorld()->GetOutermost()->GetName()) == INDEX_NONE) return false;
    auto* Restart = UCatrunRestartSubsystem::Get(this);
    TWeakObjectPtr<UCatrunCapturePresentationComponent> Capture;
    if (Restart && Restart->IsCatching())
    {
        Capture = Cast<UCatrunCapturePresentationComponent>(Restart->GetCatchOwner());
        if (!Capture.IsValid() || !Capture->IsCapturing()) return false;
    }
    const FString Package = UWorld::RemovePIEPrefix(GetWorld()->GetOutermost()->GetName());
    if (!TravelTo(TSoftObjectPtr<UWorld>(FSoftObjectPath(Package)), FString(), false, false,
        ECatrunArrivalRestart::SkipIntro, nullptr, -1, this, [this](const FString&)
        {
            if (auto* Notice = UCatrunNoticeSubsystem::Get(this))
                Notice->ShowNotice(NSLOCTEXT("Catrun", "ManualRestartTravelFailed", "스테이지를 다시 시작하지 못했습니다. 설정에서 다시 시도하세요."),
                    5.f, ECatrunNoticePolicy::DeferredGameplay);
        }, 0.f, true, ECatrunProgressArrival::ResetStage)) return false;
    // Travel now owns the world. Abort callbacks cannot reacquire a catch or replace this request.
    if (Capture.IsValid() && Restart->IsCatchOwner(Capture.Get())) Capture->AbortCapture();
    return true;
}

bool UCatrunLevelFlowLibrary::StartNewGame(const UObject* Context)
{
	auto* Flow = UCatrunLevelFlowSubsystem::Get(Context);
	return Flow && Flow->StartGame();
}
namespace
{
bool ShouldHideGameplayPresentation(const UObject* Context, bool bAllowBlockedRecovery)
{
    const UWorld* World = GEngine ? GEngine->GetWorldFromContextObject(Context, EGetWorldErrorMode::ReturnNull) : nullptr;
    if (!World || World->bIsTearingDown || !World->IsGameWorld() || World->IsPaused()) return true;
    const auto* Flow = UCatrunLevelFlowSubsystem::Get(Context);
    if (Flow && Flow->IsMainMenuWorld()) return true;
    const auto* Restart = UCatrunRestartSubsystem::Get(Context);
    if ((Flow && (Flow->IsTransitioning() || Flow->HasPendingElevatorArrival())) || (Restart && Restart->IsCatching())
        || UCatrunPuzzleSuspension::IsSuspended(Context)) return true;
    const auto* PC = UGameplayStatics::GetPlayerController(World, 0);
    if (!IsValid(PC) || PC->bCinematicMode || PC->IsMoveInputIgnored() || PC->IsLookInputIgnored()) return true;
    // Arrival fades can outlive the old world's camera/input lease. A stopped fade
    // may retain a nonzero amount, so only an enabled, visible fade owns the overlays.
    if (PC->PlayerCameraManager && PC->PlayerCameraManager->bEnableFading
        && PC->PlayerCameraManager->FadeAmount > KINDA_SMALL_NUMBER) return true;
    const APawn* Pawn = PC->GetPawn();
    if (!IsValid(Pawn) || Pawn->IsActorBeingDestroyed() || !IsGameplayCameraOwner(PC->GetViewTarget(), Pawn)) return true;
    if (const auto* Character = Cast<ACharacter>(Pawn); Character && Character->GetCharacterMovement()->MovementMode == MOVE_None)
    {
        // Failed restoration deliberately keeps the pawn immobile. Its recovery instruction
        // may remain visible only after actual camera/input/transition owners have released it.
        if (bAllowBlockedRecovery && Restart && Restart->HasBlockedPawnRecovery(Pawn)) return false;
        // Basket and bell actions are ordinary gameplay. Opening/stair BPs also use MOVE_None,
        // but their temporary camera/input ownership must hide the gameplay overlays.
        const auto* Basket = Character->FindComponentByClass<UCatrunBasketInteractionComponent>();
        return !Basket || (!Basket->Busy && !Basket->IsHidden);
    }
    return false;
}
}

bool UCatrunLevelFlowSubsystem::IsGameplayTimeAdvancing() const
{
    const UWorld* World = GetWorld();
    if (!World || PlayableStage.IsNone() || bStageComplete || ShouldHideGameplayPresentation(this, false)) return false;
    const auto* Controller = UGameplayStatics::GetPlayerController(this, 0);
    if (!Controller || !Controller->IsLocalController() || !Controller->PlayerCameraManager) return false;
    if (const AActor* Target = Controller->PlayerCameraManager->PendingViewTarget.Target)
    {
        // Both ends of the elevator's warehouse blend give the player ordinary control.
        const AActor* Current = Controller->PlayerCameraManager->ViewTarget.Target;
        const APawn* Pawn = Controller->GetPawn();
        if (!IsGameplayCameraOwner(Current, Pawn) || !IsGameplayCameraOwner(Target, Pawn)
            || (!Current->ActorHasTag(TEXT("CatrunElevatorWarehouseCamera"))
                && !Target->ActorHasTag(TEXT("CatrunElevatorWarehouseCamera")))) return false;
    }
    const auto* Context = GEngine ? GEngine->GetWorldContextFromWorld(World) : nullptr;
    if (Context && (!Context->TravelURL.IsEmpty() || World->IsInSeamlessTravel())) return false;
    if (IsStage2PortalArrival() && !bArrivalTitleReleased
        && (ArrivalTitleOwner.IsValid() || World->GetTimeSeconds() <= 2.f)) return false;
    if (const auto* Settings = World->GetSubsystem<UCatrunSettingsSubsystem>(); Settings && Settings->GetCurrentSettingsWidget()) return false;
    const auto* Restart = World->GetSubsystem<UCatrunRestartSubsystem>();
    return !Restart || (!Restart->HasRecoveryRestartPending() && !Restart->HasBlockedPawnRecovery());
}

FCatrunStageClockState UCatrunLevelFlowSubsystem::GetStageClockState() const
{
    const auto* Settings = GetDefault<UCatrunLevelFlowSettings>();
    FCatrunStageClockState State;
    State.BudgetSeconds = Settings->GetClockBudget(PlayableStage);
    State.bTimed = State.BudgetSeconds > 0.f;
    State.WarningFraction = FMath::Clamp(FMath::IsFinite(Settings->WarningFraction) ? Settings->WarningFraction : .3f, 0.f, 1.f);
    State.UrgentFraction = FMath::Clamp(FMath::IsFinite(Settings->UrgentFraction) ? Settings->UrgentFraction : .15f, 0.f, State.WarningFraction);
    const auto* Session = GetFlowSession(GetWorld());
    State.RemainingSeconds = Session ? Session->GetRemainingSeconds(PlayableStage) : State.BudgetSeconds;
    State.bRunning = State.bTimed && State.RemainingSeconds > 0.f && IsGameplayTimeAdvancing();
    return State;
}

bool UCatrunLevelFlowLibrary::ShouldHideGameplayHUD(const UObject* Context)
{
    return ShouldHideGameplayPresentation(Context, false);
}
bool UCatrunLevelFlowLibrary::ShouldHideRecoveryNotice(const UObject* Context)
{
    return ShouldHideGameplayPresentation(Context, true);
}
bool UCatrunLevelFlowLibrary::HasContinueGame(const UObject* Context)
{
    for (const FName Stage : GetUnlockedStages(Context)) if (CanContinueStage(Context, Stage)) return true;
    return false;
}
bool UCatrunLevelFlowLibrary::ContinueGame(const UObject* Context)
{
    auto* Flow = UCatrunLevelFlowSubsystem::Get(Context);
    return Flow && Flow->ContinueGame();
}
FText UCatrunLevelFlowLibrary::GetContinueStageLabel(const UObject* Context)
{
    if (auto* Session = GetFlowSession(Context))
    {
        if (Session->IsSavePending()) return NSLOCTEXT("Catrun", "CheckpointSavePending", "진행을 저장하고 있습니다.");
        if (Session->GetCheckpointState() == ECatrunCheckpointState::Failed)
            return NSLOCTEXT("Catrun", "CheckpointSaveFailed", "진행을 저장하지 못했습니다.");
    }
    if (HasContinueGame(Context)) return NSLOCTEXT("Catrun", "SelectContinueChapter", "시작할 구역을 선택하세요.");
    if (const auto* Session = GetFlowSession(Context); Session && !Session->IsProgressReadResolved())
        return NSLOCTEXT("Catrun", "ProgressReadFailed", "저장된 진행을 읽을 수 없습니다. 다시 확인하고 있습니다.");
    return NSLOCTEXT("Catrun", "NoContinueProgress", "저장된 진행이 없습니다.");
}

UCatrunFlowSession* UCatrunLevelFlowLibrary::GetFlowSession(const UObject* Context)
{
    auto* Flow = UCatrunLevelFlowSubsystem::Get(Context);
    return Flow ? ::GetFlowSession(Flow->GetWorld()) : nullptr;
}
TArray<FCatrunChapterInfo> UCatrunLevelFlowLibrary::GetChapters(const UObject* Context)
{
    TArray<FCatrunChapterInfo> Result;
    auto* Session = GetFlowSession(Context);
    const int32 Highest = Session ? Session->GetHighestUnlockedStageIndex() : INDEX_NONE;
    const auto* Settings = GetDefault<UCatrunLevelFlowSettings>();
    for (int32 Index = 0; Index < Settings->Stages.Num(); ++Index)
    {
        const auto& Stage = Settings->Stages[Index];
        auto& Chapter = Result.AddDefaulted_GetRef();
        Chapter.StageId = Stage.StageId; Chapter.DisplayName = Settings->GetStageDisplayName(Stage.StageId);
        Chapter.Thumbnail = Stage.Thumbnail; Chapter.bUnlocked = Index <= Highest;
    }
    return Result;
}
TArray<FName> UCatrunLevelFlowLibrary::GetUnlockedStages(const UObject* Context)
{
    TArray<FName> Result;
    for (const auto& Chapter : GetChapters(Context)) if (Chapter.bUnlocked) Result.Add(Chapter.StageId);
    return Result;
}
bool UCatrunLevelFlowLibrary::CanContinueStage(const UObject* Context, FName StageId)
{
    auto* Flow = UCatrunLevelFlowSubsystem::Get(Context);
    auto* Session = GetFlowSession(Context);
    const int32 Index = FindStageId(StageId);
    return Flow && !Flow->IsTransitioning() && Session && !Session->IsSavePending()
        && Index != INDEX_NONE && Index <= Session->GetHighestUnlockedStageIndex() && IsAvailableStage(Index);
}
bool UCatrunLevelFlowLibrary::ContinueStage(const UObject* Context, FName StageId)
{
    auto* Flow = UCatrunLevelFlowSubsystem::Get(Context);
    return Flow && Flow->ContinueStage(StageId);
}
ECatrunCheckpointState UCatrunLevelFlowLibrary::GetCheckpointState(const UObject* Context)
{
    auto* Session = GetFlowSession(Context);
    return Session ? Session->GetCheckpointState() : ECatrunCheckpointState::Idle;
}
FText UCatrunLevelFlowLibrary::GetCurrentStageTitle(const UObject* Context)
{
    auto* Flow = UCatrunLevelFlowSubsystem::Get(Context);
    return Flow ? Flow->GetCurrentStageTitle() : FText::GetEmpty();
}
bool UCatrunLevelFlowLibrary::ConsumeStageTitle(const UObject* Context, FText& OutTitle)
{
    OutTitle = FText::GetEmpty();
    auto* Flow = UCatrunLevelFlowSubsystem::Get(Context);
    return Flow && Flow->ConsumeStageTitle(OutTitle);
}

bool UCatrunLevelFlowLibrary::CompleteCurrentStage(const UObject* Context)
{
	auto* Flow = UCatrunLevelFlowSubsystem::Get(Context);
	return Flow && Flow->CompleteStage();
}
bool UCatrunLevelFlowLibrary::CompleteCurrentStageWithFailure(const UObject* Context, UObject* Owner, FCatrunTravelFailureCallback Failure)
{
    auto* Flow = UCatrunLevelFlowSubsystem::Get(Context);
    const bool bAccepted = Flow && Flow->CompleteStageWithFailure(Owner,
        [Failure](const FString&) { Failure.ExecuteIfBound(); });
    if (!bAccepted) Failure.ExecuteIfBound();
    return bAccepted;
}

bool UCatrunLevelFlowLibrary::ReserveStagePresentation(UObject* Owner)
{
    auto* Flow = UCatrunLevelFlowSubsystem::Get(Owner);
    return Flow && Flow->ReserveExitTransition(Owner);
}

void UCatrunLevelFlowLibrary::ReleaseStagePresentation(UObject* Owner)
{
    if (auto* Flow = UCatrunLevelFlowSubsystem::Get(Owner)) Flow->ReleaseExitTransition(Owner);
}

bool UCatrunLevelFlowLibrary::RestoreFailedStagePawn(APawn* Pawn, const FTransform& OriginalTransform, bool bOriginalCollision)
{
    if (!IsValid(Pawn) || !Pawn->GetWorld() || Pawn->GetWorld()->bIsTearingDown || !OriginalTransform.IsValid()) return false;
    const bool bPlaced = CatrunRestore::PlaceForCollision(*Pawn, OriginalTransform, bOriginalCollision);
    Pawn->SetActorEnableCollision(bOriginalCollision && bPlaced);
    if (auto* Movement = Pawn->GetMovementComponent()) Movement->StopMovementImmediately();
    if (!bPlaced) if (auto* Character = Cast<ACharacter>(Pawn)) Character->GetCharacterMovement()->DisableMovement();
    return bPlaced;
}
bool UCatrunLevelFlowLibrary::ReturnToMainMenu(const UObject* Context)
{
	auto* Flow = UCatrunLevelFlowSubsystem::Get(Context);
	return Flow && Flow->ReturnToMenu();
}
bool UCatrunLevelFlowLibrary::RestartCurrentStage(const UObject* Context)
{
	auto* Flow = UCatrunLevelFlowSubsystem::Get(Context);
	return Flow && Flow->RestartStage();
}

bool UCatrunLevelFlowLibrary::ShouldSkipStageIntro(const UObject* Context)
{
	auto* Flow = UCatrunLevelFlowSubsystem::Get(Context);
	return Flow && Flow->ShouldSkipStageIntro();
}

bool UCatrunLevelFlowLibrary::IsStage2PortalArrival(const UObject* Context)
{
	const auto* Flow = UCatrunLevelFlowSubsystem::Get(Context);
	return Flow && Flow->IsStage2PortalArrival();
}

bool UCatrunLevelFlowLibrary::RestorePlayableStart(const UObject* Context, APawn* Pawn, const FTransform& PlayableTransform, AActor* GameplayViewTarget)
{
	auto* Flow = UCatrunLevelFlowSubsystem::Get(Context);
	APlayerController* PC = Pawn ? Cast<APlayerController>(Pawn->GetController()) : nullptr;
	if (!Flow || !Flow->ShouldSkipStageIntro() || Flow->IsTransitioning() || !PC || Pawn->GetWorld() != Flow->GetWorld()) return false;
	if (const auto* Restart = UCatrunRestartSubsystem::Get(Context); Restart && Restart->IsCatching()) return false;
	if (GameplayViewTarget && (GameplayViewTarget->GetWorld() != Pawn->GetWorld() || !IsGameplayCameraOwner(GameplayViewTarget, Pawn))) return false;
	if (!GameplayViewTarget)
	{
		// The original game uses a separate quarter-view actor, not a camera on the cat.
		for (TActorIterator<AActor> It(Pawn->GetWorld()); It; ++It)
			if (*It != Pawn && IsGameplayCameraOwner(*It, Pawn)) { GameplayViewTarget = *It; break; }
	}
	// TeleportTo checks encroachment; a bad authored restart marker must not place the cat in a wall.
	if (!Pawn->TeleportTo(PlayableTransform.GetLocation(), PlayableTransform.Rotator())) return false;
	if (auto* Movement = Pawn->GetMovementComponent()) Movement->StopMovementImmediately();
	if (auto* Character = Cast<ACharacter>(Pawn)) Character->GetCharacterMovement()->SetMovementMode(MOVE_Walking);
	if (GameplayViewTarget && GameplayViewTarget != Pawn) GameplayViewTarget->SetActorTickEnabled(true);
	PC->SetViewTarget(GameplayViewTarget ? GameplayViewTarget : Pawn);
	PC->SetInputMode(FInputModeGameOnly());
	PC->bShowMouseCursor = false;
	PC->FlushPressedKeys();
	// This hook runs before the intro acquires input locks; do not reset locks owned by other systems.
	return true;
}

bool UCatrunLevelFlowLibrary::ApplyStageCameraProfile(const UObject* Context, UCameraComponent* Camera, USpringArmComponent* SpringArm)
{
	auto* Flow = UCatrunLevelFlowSubsystem::Get(Context);
	return Flow && Flow->ApplyStageCameraProfile(Camera, SpringArm);
}

ACatrunStageExit::ACatrunStageExit()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = false;
	ExitTransition = CreateDefaultSubobject<UCatrunExitTransitionComponent>(TEXT("ExitTransition"));
	Trigger = CreateDefaultSubobject<UBoxComponent>(TEXT("Trigger"));
	SetRootComponent(Trigger);
	Trigger->SetBoxExtent(FVector(70, 35, 80));
	Trigger->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	Trigger->SetCollisionResponseToAllChannels(ECR_Ignore);
	Trigger->SetCollisionResponseToChannel(ECC_Pawn, ECR_Overlap);
	Trigger->SetGenerateOverlapEvents(true);
	OnActorBeginOverlap.AddDynamic(this, &ACatrunStageExit::HandleOverlap);
	OnActorEndOverlap.AddDynamic(this, &ACatrunStageExit::HandleEndOverlap);
}

void ACatrunStageExit::BeginPlay()
{
    Super::BeginPlay();
    if (!bProtectStage1Corridor) return;
    if (auto* Instance = GetGameInstance())
        Instance->GetOnPawnControllerChanged().AddDynamic(this, &ACatrunStageExit::OnCorridorControllerAssigned);
    ObserveLocalController(UGameplayStatics::GetPlayerController(this, 0));
    OnCorridorPossessionChanged(nullptr, UGameplayStatics::GetPlayerPawn(this, 0));
}

void ACatrunStageExit::EndPlay(const EEndPlayReason::Type Reason)
{
    if (auto* Instance = GetGameInstance())
        Instance->GetOnPawnControllerChanged().RemoveDynamic(this, &ACatrunStageExit::OnCorridorControllerAssigned);
    ObserveLocalController(nullptr);
    if (bProtectStage1Corridor)
        if (auto* Marks = UCatrunMarkSubsystem::Get(this)) Marks->LeaveCorridor(*this);
    Super::EndPlay(Reason);
}

void ACatrunStageExit::ObserveLocalController(APlayerController* Player)
{
    if (CorridorController.Get() == Player) return;
    if (auto* Old = CorridorController.Get(true))
        Old->OnPossessedPawnChanged.RemoveDynamic(this, &ACatrunStageExit::OnCorridorPossessionChanged);
    CorridorController = Player;
    if (Player) Player->OnPossessedPawnChanged.AddUniqueDynamic(this, &ACatrunStageExit::OnCorridorPossessionChanged);
}

void ACatrunStageExit::OnCorridorControllerAssigned(APawn* Pawn, AController* Controller)
{
    // PossessedBy fires before the controller commits GetPawn(). Its subsequent possession
    // notification is the first point where both sides identify the same local player.
    auto* Player = Cast<APlayerController>(Controller);
    if (Pawn && Pawn->GetWorld() == GetWorld() && Player && Player->IsLocalController()
        && Player == UGameplayStatics::GetPlayerController(this, 0))
        ObserveLocalController(Player);
}

void ACatrunStageExit::OnCorridorPossessionChanged(APawn* Previous, APawn* Current)
{
    if (!GetWorld() || GetWorld()->bIsTearingDown || IsActorBeingDestroyed()) return;
    if (auto* Old = OverlappingPawn.Get(); Old && Old != Current)
        HandleEndOverlap(this, Old);
    if (Current && Trigger->IsOverlappingActor(Current)) HandleOverlap(this, Current);
}

void ACatrunStageExit::HandleOverlap(AActor*, AActor* OtherActor)
{
	APawn* Pawn = Cast<APawn>(OtherActor);
    if (Pawn && bProtectStage1Corridor)
        ObserveLocalController(UGameplayStatics::GetPlayerController(this, 0));
	if (!Pawn || !Pawn->IsLocallyControlled() || Pawn != UGameplayStatics::GetPlayerPawn(this, 0)) return;
    OverlappingPawn = Pawn;
    if (bProtectStage1Corridor)
        if (auto* Marks = UCatrunMarkSubsystem::Get(this)) Marks->ObserveCorridor(*this, *Pawn);
    RefreshExitTick();
    TryCompleteFor(Pawn);
}

void ACatrunStageExit::HandleEndOverlap(AActor*, AActor* OtherActor)
{
	if (OverlappingPawn.Get() != OtherActor) return;
    if (bProtectStage1Corridor)
        if (auto* Marks = UCatrunMarkSubsystem::Get(this)) Marks->LeaveCorridor(*this);
    OverlappingPawn.Reset();
    RefreshExitTick();
}

void ACatrunStageExit::RefreshExitTick()
{
	const bool bActiveLease = ExitTransition && ExitTransition->HasExitLease();
	if (!OverlappingPawn.IsValid() && !bActiveLease) bArmed = true;
	SetActorTickEnabled(OverlappingPawn.IsValid() || bActiveLease);
}

bool ACatrunStageExit::TryCompleteFor(APawn* Pawn)
{
    if (!bArmed || !Pawn || !Pawn->IsLocallyControlled() || Pawn != UGameplayStatics::GetPlayerPawn(this, 0) || !Trigger->IsOverlappingActor(Pawn)) return false;
    if ((bRequireCenterInside || bUseExitTransition) && !IsCenterQualified(Pawn->GetActorLocation())) return false;
	if (const auto* Actions = Pawn->FindComponentByClass<UCatrunBasketInteractionComponent>(); Actions && (Actions->Busy || Actions->IsHidden)) return false;
    // Rollback occupies the trigger synchronously, while hostile admission is still suspended.
    if (ExitTransition && ExitTransition->BlocksExitQualification())
    {
        bArmed = false;
        return false;
    }
    if (bProtectStage1Corridor && !UCatrunMarkSubsystem::IsExcludedFromPerception(Pawn)) return false;
    bArmed = false;
    if (bUseExitTransition) { BeginPortalPresentation(Pawn); return true; }
    return UCatrunLevelFlowLibrary::CompleteCurrentStage(this);
}

bool UCatrunFlowSession::EnsureProgressLoaded()
{
    if (bProgressLoaded || bDrawingProgressSnapshot) return bProgressLoaded;
    ISaveGameSystem* Backend = FCatrunProgressWriter::GetPlatformBackend();
#if WITH_DEV_AUTOMATION_TESTS
    if (SaveBackendForTest) Backend = SaveBackendForTest;
#endif
    if (!Backend) return false;
    const auto Exists = Backend->DoesSaveGameExistWithResult(*ProgressSlot, ProgressUser);
    if (Exists == ISaveGameSystem::ESaveExistsResult::OK)
    {
        const auto* Save = LoadSavedProgress();
        if (!Save) return false;
        MergeSavedProgress(*Save);
        ReadStageValues(*Save);
    }
    else if (Exists != ISaveGameSystem::ESaveExistsResult::DoesNotExist) return false;
    bProgressLoaded = true;
    return true;
}
void UCatrunFlowSession::RefreshMenuWithProgressSnapshot(TFunctionRef<void()> Refresh)
{
    EnsureProgressLoaded();
    // The saved BP reads button availability and status separately in one redraw.
    TGuardValue<bool> DrawGuard(bDrawingProgressSnapshot, true);
    Refresh();
}
void UCatrunFlowSession::MergeSavedProgress(const UCatrunProgressSave& Save)
{
    const int32 Reached = FindStageId(Save.StageId);
    const int32 Highest = Save.SchemaVersion >= 3 ? FindStageId(Save.HighestUnlockedStageId) : INDEX_NONE;
    const int32 Index = FMath::Max(Reached, Highest);
    if (Index > FindStageId(HighestUnlockedStageId)) HighestUnlockedStageId = GetDefault<UCatrunLevelFlowSettings>()->Stages[Index].StageId;
    // After a new run starts, its own onboarding choice wins over late disk recovery.
    if (!ProgressGeneration) bTutorialOnboardingCompleted = Save.HasCompletedOnboarding();
}

void UCatrunFlowSession::ReadStageValues(const UCatrunProgressSave& Save)
{
    if (LastTrackedStage.IsNone()) LastTrackedStage = Save.StageId;
    if (bClockDirty) return;
    // Stage2 uses chapter-start checkpoints. Old v4 fields are accepted by the reader
    // for compatibility and never applied to the current attempt.
    const int32 RemainingMs = Mutations.IsEmpty() ? Save.Stage1RemainingMs : Mutations.Last().RemainingMs;
    Stage1Seconds = RemainingMs < 0 ? -1. : RemainingMs / 1000.;
}

FName UCatrunFlowSession::GetContinueStageId()
{
    return EnsureProgressLoaded() ? LastTrackedStage : NAME_None;
}

void UCatrunFlowSession::RefillStage1Clock()
{
    const bool bTracked = !ActiveProgressMap.IsEmpty();
    const float Budget = GetDefault<UCatrunLevelFlowSettings>()->GetClockBudget(TEXT("Stage1"));
    const int32 RemainingMs = FMath::RoundToInt32(double(Budget) * 1000.);
    (bTracked ? Stage1Seconds : LocalStage1Seconds) = RemainingMs / 1000.;
    if (bTracked) Mutations.Add({++MutationRevision, RemainingMs});
}

float UCatrunFlowSession::GetRemainingSeconds(FName StageId) const
{
    double Seconds = -1.;
    if (StageId == TEXT("Stage1")) Seconds = ActiveProgressMap.IsEmpty() ? LocalStage1Seconds : Stage1Seconds;
    else if (StageId == TEXT("Stage2")) Seconds = Stage2Seconds;
    else if (StageId == TEXT("Stage3")) Seconds = Stage3Seconds;
    return Seconds >= 0. ? float(Seconds) : GetDefault<UCatrunLevelFlowSettings>()->GetClockBudget(StageId);
}

void UCatrunFlowSession::AdvanceClock(float DeltaSeconds)
{
    if (DeltaSeconds <= 0.f || !FMath::IsFinite(DeltaSeconds)) return;
    const bool bTracked = !ActiveProgressMap.IsEmpty();
    const bool bStage1 = CurrentStage == TEXT("Stage1");
    if (!bStage1 && CurrentStage != TEXT("Stage2") && CurrentStage != TEXT("Stage3")) return;
    double& Seconds = bStage1 ? (bTracked ? Stage1Seconds : LocalStage1Seconds) : (CurrentStage == TEXT("Stage3") ? Stage3Seconds : Stage2Seconds);
    if (Seconds == 0.) return;
    if (Seconds < 0.) Seconds = GetDefault<UCatrunLevelFlowSettings>()->GetClockBudget(CurrentStage);
    Seconds = FMath::Max(0., Seconds - DeltaSeconds);
    bClockDirty |= bTracked && bStage1;
}

void UCatrunFlowSession::CaptureClock()
{
    if (!bClockDirty || ActiveProgressMap.IsEmpty()) return;
    bClockDirty = false;
    Mutations.Add({++MutationRevision, FMath::RoundToInt32(Stage1Seconds * 1000.)});
}

void UCatrunFlowSession::FlushTrackedProgress()
{
    if (bClockDirty || (!IsSavePending() && !Mutations.IsEmpty()))
        BeginCheckpoint(ActiveProgressMap, true, {}, true);
}

int32 UCatrunFlowSession::GetHighestUnlockedStageIndex()
{
    return EnsureProgressLoaded() ? FindStageId(HighestUnlockedStageId) : INDEX_NONE;
}
bool UCatrunFlowSession::ConsumeArrivalTitle(const FString& Package)
{
    const bool bMatches = !TitleIntentMap.IsEmpty() && TitleIntentMap == UWorld::RemovePIEPrefix(Package);
    TitleIntentMap.Reset();
    return bMatches;
}
const UCatrunProgressSave* UCatrunFlowSession::LoadSavedProgress() const
{
    TArray<uint8> Data;
#if WITH_DEV_AUTOMATION_TESTS
    if (SaveBackendForTest)
        return SaveBackendForTest->LoadGame(false, *ProgressSlot, ProgressUser, Data) ? DecodeProgress(Data) : nullptr;
#endif
    return UGameplayStatics::LoadDataFromSlot(Data, ProgressSlot, ProgressUser) ? DecodeProgress(Data) : nullptr;
}
uint64 UCatrunFlowSession::SaveCurrentCheckpoint(const FString& Package, TFunction<void(bool, const FString&)> Completion)
{
    return BeginCheckpoint(Package, false, MoveTemp(Completion));
}
void UCatrunFlowSession::SaveArrivalCheckpoint(UWorld& World, bool bQuiet)
{
    BeginCheckpoint(World.GetOutermost()->GetName(), true, {}, bQuiet);
}
uint64 UCatrunFlowSession::BeginCheckpoint(const FString& Package, bool bRetryOnce, TFunction<void(bool, const FString&)> Completion, bool bQuiet)
{
    const FString CleanPackage = UWorld::RemovePIEPrefix(Package);
    if (!IsTrackingWorld(CleanPackage)) return 0;
    const auto* Settings = GetDefault<UCatrunLevelFlowSettings>();
    const int32 StageIndex = Settings->FindStageIndex(CleanPackage);
    if (StageIndex == INDEX_NONE) return 0;
    const FName StageId = Settings->Stages[StageIndex].StageId;
    CaptureClock();
    if (!Writer)
    {
        Writer = MakeShared<FCatrunProgressWriter>();
        Writer->OnIdle.BindUObject(this, &UCatrunFlowSession::OnCheckpointQueueIdle);
        Writer->OnStarted.BindUObject(this, &UCatrunFlowSession::OnCheckpointStarted);
    }
    bShowCheckpointNotice |= !bQuiet;
    CompletedCheckpointState = ECatrunCheckpointState::Idle;
    return EnqueueCheckpoint(StageId, ProgressGeneration, ++LatestSaveRequest, MutationRevision, bRetryOnce, MoveTemp(Completion));
}
uint64 UCatrunFlowSession::EnqueueCheckpoint(FName StageId, uint64 Generation, uint64 Request, uint64 Revision, bool bRetryOnce, TFunction<void(bool, const FString&)> Completion)
{
    const auto KeepAlive = Writer.ToSharedRef();
    const TWeakObjectPtr<UCatrunFlowSession> Weak(this);
    const bool bOnboarding = bTutorialOnboardingCompleted;
    return KeepAlive->Enqueue([Weak, StageId, Revision, bOnboarding](const TArray<uint8>* Previous, TArray<uint8>& Data)
    {
        auto* Session = Weak.Get();
        if (!Session) return false;
        auto* Save = NewObject<UCatrunProgressSave>();
        if (Previous)
        {
            const auto* Existing = DecodeProgress(*Previous);
            if (!Existing) return false;
            Session->MergeSavedProgress(*Existing);
            if (!Session->bProgressLoaded) Session->ReadStageValues(*Existing);
            Save->Stage1RemainingMs = Existing->Stage1RemainingMs;
        }
        Session->bProgressLoaded = true;
        Save->SchemaVersion = UCatrunProgressSave::CurrentSchemaVersion;
        Save->StageId = StageId;
        Save->HighestUnlockedStageId = Session->HighestUnlockedStageId;
        Save->SavedAtUtc = FDateTime::UtcNow();
        Save->bTutorialOnboardingCompleted = bOnboarding;
        for (const auto& Mutation : Session->Mutations)
            if (Mutation.Revision <= Revision) Save->Stage1RemainingMs = Mutation.RemainingMs;
        return UGameplayStatics::SaveGameToMemory(Save, Data);
    }, [Weak, StageId, Generation, Request, Revision, bRetryOnce, Completion = MoveTemp(Completion)](bool bOK, const FString& Error) mutable
    {
        if (auto* Session = Weak.Get())
        {
            if (bOK) Session->Mutations.RemoveAll([Revision](const FStage1ClockMutation& Mutation) { return Mutation.Revision <= Revision; });
            if (Session->ProgressGeneration == Generation && Session->LatestSaveRequest == Request)
            {
                const bool bCanRetry = Session->bFlushing ? !Session->bRetriedDuringShutdown : bRetryOnce;
                if (!bOK && bCanRetry)
                {
                    Session->bRetriedDuringShutdown = Session->bFlushing;
                    Session->EnqueueCheckpoint(StageId, Generation, Request, Revision, false, MoveTemp(Completion));
                    return;
                }
                Session->CompletedCheckpointState = bOK ? ECatrunCheckpointState::Saved : ECatrunCheckpointState::Failed;
                if (!bOK) UE_LOG(LogCatrunFlow, Error, TEXT("%s"), *Error);
            }
        }
        if (Completion) Completion(bOK, Error);
    });
}
void UCatrunFlowSession::OnCheckpointStarted()
{
    if (CheckpointState == ECatrunCheckpointState::Pending) return;
    CheckpointState = ECatrunCheckpointState::Pending;
    if (bFlushing) return;
    OnCheckpointStateChanged.Broadcast(CheckpointState);
    if (!bShowCheckpointNotice) return;
    if (auto* Instance = GetGameInstance()) if (auto* Notice = UCatrunNoticeSubsystem::Get(Instance->GetWorld()))
        Notice->ShowNotice(NSLOCTEXT("Catrun", "CheckpointSavePending", "진행을 저장하고 있습니다."), 2.f);
}
void UCatrunFlowSession::OnCheckpointQueueIdle()
{
    CheckpointState = CompletedCheckpointState;
    const bool bShowNotice = bShowCheckpointNotice;
    bShowCheckpointNotice = false;
    if (bFlushing) return;
    OnCheckpointStateChanged.Broadcast(CheckpointState);
    // Subscribers may begin another write. Do not overwrite its pending status or show a stale notice.
    if (IsSavePending() || !bShowNotice) return;
    if (auto* Instance = GetGameInstance()) if (auto* Notice = UCatrunNoticeSubsystem::Get(Instance->GetWorld()))
    {
        if (CheckpointState == ECatrunCheckpointState::Failed)
            Notice->ShowNotice(NSLOCTEXT("Catrun", "CheckpointSaveFailed", "진행을 저장하지 못했습니다."), 5.f, ECatrunNoticePolicy::DeferredGameplay);
        else if (CheckpointState == ECatrunCheckpointState::Saved)
            Notice->ShowNotice(NSLOCTEXT("Catrun", "CheckpointSaved", "진행을 저장했습니다."), 2.f);
    }
}
void UCatrunFlowSession::Deinitialize()
{
    bFlushing = true;
    FlushTrackedProgress();
    if (Writer && !Writer->Flush()) UE_LOG(LogCatrunFlow, Error, TEXT("The checkpoint queue could not be drained during shutdown."));
    ++ProgressGeneration;
    if (Writer) { Writer->OnIdle.Unbind(); Writer->OnStarted.Unbind(); }
    Writer.Reset();
    OnCheckpointStateChanged.Clear();
    Super::Deinitialize();
}
bool UCatrunFlowSession::IsSavePending() const { return Writer && Writer->IsBusy(); }
void UCatrunFlowSession::MarkOnboardingCompleted(const FString& Package)
{
    EnsureProgressLoaded();
    if (bTutorialOnboardingCompleted) return;
    bTutorialOnboardingCompleted = true;
    SaveCurrentCheckpoint(Package);
}
#if WITH_DEV_AUTOMATION_TESTS
void UCatrunFlowSession::SetSaveBackendForTest(ISaveGameSystem* Backend, FSimpleDelegate DrainCallbacks, bool bUseAtomicIO)
{
    check(!IsSavePending());
    SaveBackendForTest = Backend;
    bProgressLoaded = false;
    HighestUnlockedStageId = NAME_None;
    LastTrackedStage = NAME_None;
    Stage1Seconds = -1.;
    Writer = MakeShared<FCatrunProgressWriter>(Backend, MoveTemp(DrainCallbacks), bUseAtomicIO);
    Writer->OnIdle.BindUObject(this, &UCatrunFlowSession::OnCheckpointQueueIdle);
    Writer->OnStarted.BindUObject(this, &UCatrunFlowSession::OnCheckpointStarted);
}
#endif

FText UCatrunLevelFlowSettings::GetStageDisplayName(FName StageId) const
{
    for (const auto& Stage : Stages) if (Stage.StageId == StageId && !Stage.DisplayName.IsEmpty()) return Stage.DisplayName;
    if (StageId == TEXT("Tutorial")) return NSLOCTEXT("Catrun", "TutorialChapterName", "마왕의 침실");
    if (StageId == TEXT("Stage1")) return NSLOCTEXT("Catrun", "Stage1ChapterName", "연회장");
    if (StageId == TEXT("Stage2")) return NSLOCTEXT("Catrun", "Stage2ChapterName", "마법회랑");
    return FText::FromName(StageId);
}
FText UCatrunLevelFlowSubsystem::GetCurrentStageTitle() const
{
    const auto* Settings = GetDefault<UCatrunLevelFlowSettings>();
    const int32 Index = Settings->FindStageIndex(GetWorld()->GetOutermost()->GetName());
    return Index == INDEX_NONE ? FText::GetEmpty() : FText::Format(NSLOCTEXT("Catrun", "StageTitleFormat", "~ {0} ~"), Settings->GetStageDisplayName(Settings->Stages[Index].StageId));
}
bool UCatrunLevelFlowSubsystem::ClaimArrivalTitleGate(UCatrunExitTransitionComponent& Owner)
{
    if (GetWorld() != Owner.GetWorld() || !IsStage2PortalArrival() || bArrivalTitleReleased) return false;
    if (ArrivalTitleOwner.IsValid()) return ArrivalTitleOwner.Get() == &Owner;
    ArrivalTitleOwner = &Owner;
    return true;
}

void UCatrunLevelFlowSubsystem::ReleaseArrivalTitleGate(const UCatrunExitTransitionComponent& Owner)
{
    if (ArrivalTitleOwner.Get(true) != &Owner || Owner.HasExitLease()) return;
    ArrivalTitleOwner.Reset();
    bArrivalTitleReleased = true;
}

bool UCatrunLevelFlowSubsystem::IsTitleWindowOpen()
{
    ResolveRestartIntent();
    if (!bStageTitlePending) return true;
    if (!GetWorld() || GetWorld()->bIsTearingDown) return false;
    if (IsStage2PortalArrival() && !bArrivalTitleReleased)
    {
        // Qualified directors claim synchronously in BeginPlay, before retrying the pawn/camera.
        // A missing director must not strand the title past its two-second readiness window.
        if (ArrivalTitleOwner.IsValid() || GetWorld()->GetTimeSeconds() <= 2.f) return false;
        bArrivalTitleReleased = true;
    }
    if (IsStage3ElevatorArrival() && !bElevatorArrivalReleased)
    {
        // Give the dock director time to acquire its arrival lease. A missing actor falls back to normal play.
        if (ElevatorArrivalOwner.IsValid() || GetWorld()->GetTimeSeconds() <= 3.f) return false;
        bElevatorArrivalReleased = true;
    }
    const auto* PC = UGameplayStatics::GetPlayerController(this, 0);
    return !UCatrunLevelFlowLibrary::ShouldHideGameplayHUD(this) && PC && PC->PlayerCameraManager
        && !PC->PlayerCameraManager->PendingViewTarget.Target;
}

namespace
{
class FWaitForStageTitle final : public FPendingLatentAction
{
public:
    FWaitForStageTitle(UCatrunLevelFlowSubsystem& InFlow, const FLatentActionInfo& Info)
        : Flow(&InFlow), Target(Info.CallbackTarget.Get()), Function(Info.ExecutionFunction), Link(Info.Linkage) {}
    virtual void UpdateOperation(FLatentResponse& Response) override
    {
        const UObject* Listener = Target.Get();
        if (!Flow.IsValid() || !IsValid(Listener) || Listener->GetWorld() != Flow->GetWorld()
            || !Flow->GetWorld() || Flow->GetWorld()->bIsTearingDown)
        {
            Response.DoneIf(true);
            return;
        }
        Response.FinishAndTriggerIf(Flow->IsTitleWindowOpen(), Function, Link, Target);
    }
private:
    TWeakObjectPtr<UCatrunLevelFlowSubsystem> Flow;
    FWeakObjectPtr Target;
    FName Function;
    int32 Link;
};
}

void UCatrunLevelFlowLibrary::WaitForStageTitleWindow(const UObject* Context, FLatentActionInfo LatentInfo)
{
    auto* Flow = UCatrunLevelFlowSubsystem::Get(Context);
    if (!Flow || !IsValid(LatentInfo.CallbackTarget)) return;
    auto& Manager = Flow->GetWorld()->GetLatentActionManager();
    if (!Manager.FindExistingAction<FWaitForStageTitle>(LatentInfo.CallbackTarget, LatentInfo.UUID))
        Manager.AddNewAction(LatentInfo.CallbackTarget, LatentInfo.UUID, new FWaitForStageTitle(*Flow, LatentInfo));
}

bool UCatrunLevelFlowSubsystem::ConsumeStageTitle(FText& OutTitle)
{
    ResolveRestartIntent();
    OutTitle = FText::GetEmpty();
    if (!bStageTitlePending || !IsTitleWindowOpen()) return false;
    bStageTitlePending = false;
    OutTitle = GetCurrentStageTitle();
    return !OutTitle.IsEmpty();
}
bool UCatrunLevelFlowSubsystem::ReserveExitTransition(UObject* Owner)
{
    if (!IsValid(Owner) || Owner->GetWorld() != GetWorld() || IsTransitioning() || bStageComplete || GetWorld()->IsPaused()) return false;
    const FWorldContext* Context = GEngine ? GEngine->GetWorldContextFromWorld(GetWorld()) : nullptr;
    if (!Context || !Context->TravelURL.IsEmpty() || GetWorld()->bIsTearingDown) return false;
    if (const auto* Restart = UCatrunRestartSubsystem::Get(this); Restart && Restart->IsCatching()) return false;
    if (const auto* Settings = UCatrunSettingsSubsystem::Get(this); Settings && Settings->GetCurrentSettingsWidget()) return false;
    if (UCatrunPuzzleSuspension::IsSuspended(this)) return false;
    ExitReservation = Owner;
    return true;
}

void UCatrunLevelFlowSubsystem::ReleaseExitTransition(const UObject* Owner)
{
    if (ExitReservation.Get(true) == Owner && !bTransitioning) ExitReservation.Reset();
}

bool UCatrunLevelFlowSubsystem::CompleteStageForExit(UObject* Owner)
{
    auto* Transition = Cast<UCatrunExitTransitionComponent>(Owner);
    if (ExitReservation.Get() != Owner || !Transition || !Transition->CanCommitExitTravel()) return false;
    const auto* Settings = GetDefault<UCatrunLevelFlowSettings>();
    const int32 Index = Settings->FindStageIndex(GetWorld()->GetOutermost()->GetName());
    if (Index < 0 || !Settings->Stages.IsValidIndex(Index + 1)) return false;
    if (const auto* Elevator = Cast<ACatrunElevatorTransition>(Transition->GetOwner()))
    {
        if (Elevator->bArrivalSide || Settings->Stages[Index].StageId != TEXT("Stage2")
            || Settings->Stages[Index + 1].StageId != TEXT("Stage3")) return false;
        return CompleteStageInternal(Owner, nullptr, {}, Stage2ElevatorArrivalOption);
    }
    if (Settings->Stages[Index].StageId != TEXT("Stage1") || Settings->Stages[Index + 1].StageId != TEXT("Stage2")) return false;
    return CompleteStageInternal(Owner, nullptr, {}, Stage1PortalArrivalOption);
}

void UCatrunLevelFlowSubsystem::ClearFailedTravel()
{
    if (PendingTravelToken) if (auto* Session = GetFlowSession(GetWorld())) Session->CancelTravel(PendingTravelToken);
    PendingTravelToken = 0;
    bTransitioning = false;
    PendingMap.Reset(); PendingOptions.Reset();
    TravelFailureOwner.Reset(); TravelFailureCallback = {};
    if (auto* PC = TravelLockController.Get()) PC->SetIgnoreMoveInput(false);
    TravelLockController.Reset();
}

void UCatrunLevelFlowSubsystem::RearmStageTimeout(float RetryDelay)
{
    bTimeoutAttempted = false;
    TimeoutRetryDelay = FMath::Max(0.f, RetryDelay);
}

bool UCatrunLevelFlowSubsystem::AbortOwnedTravel(const UObject* Owner)
{
    if (!Owner || Owner->GetWorld() != GetWorld() || TravelFailureOwner.Get(true) != Owner
        || !bTransitioning || !GetWorld() || GetWorld()->bIsTearingDown) return false;
    FWorldContext* Context = GEngine ? GEngine->GetWorldContextFromWorld(GetWorld()) : nullptr;
    if (!Context || GetWorld()->IsInSeamlessTravel()) return false;
    const FString OwnedURL = PendingMap + (PendingOptions.IsEmpty() ? FString() : TEXT("?") + PendingOptions);
    if (Context->TravelURL == OwnedURL) Context->TravelURL.Reset();
    // A subsequent foreign URL survives; only our token and our input-lock layer are retired.
    ClearFailedTravel();
    return true;
}

void UCatrunLevelFlowSubsystem::AbortExitTravel(const UObject* Owner)
{
    if (ExitReservation.Get(true) != Owner) return;
    if (bTransitioning)
    {
        // Only cancel the URL this flow issued. Never erase a subsequent unrelated travel.
        if (FWorldContext* Context = GEngine ? GEngine->GetWorldContextFromWorld(GetWorld()) : nullptr)
            if (Context->TravelURL == PendingMap || Context->TravelURL.StartsWith(PendingMap + TEXT("?"))) Context->TravelURL.Reset();
        ClearFailedTravel();
    }
    ExitReservation.Reset();
}

bool UCatrunLevelFlowSubsystem::ShouldShowTutorialControls()
{
    ResolveRestartIntent();
    const auto* Settings = GetDefault<UCatrunLevelFlowSettings>();
    const int32 Index = Settings->FindStageIndex(GetWorld()->GetOutermost()->GetName());
    const auto* Session = GetFlowSession(GetWorld());
    if (bControlsOffered || Index == INDEX_NONE || Settings->Stages[Index].StageId != TEXT("Tutorial")
        || (bSkipStageIntro && !bContinueArrival) || (Session && Session->HasCompletedOnboarding())) return false;
    bControlsOffered = true;
    return true;
}

void UCatrunLevelFlowSubsystem::MarkTutorialOnboardingCompleted()
{
    const auto* Settings = GetDefault<UCatrunLevelFlowSettings>();
    const int32 Index = Settings->FindStageIndex(GetWorld()->GetOutermost()->GetName());
    if (Index == INDEX_NONE || Settings->Stages[Index].StageId != TEXT("Tutorial")) return;
    bControlsOffered = true;
    if (auto* Session = GetFlowSession(GetWorld())) Session->MarkOnboardingCompleted(GetWorld()->GetOutermost()->GetName());
}

bool UCatrunLevelFlowLibrary::ShouldShowTutorialControls(const UObject* Context)
{
    auto* Flow = UCatrunLevelFlowSubsystem::Get(Context);
    return Flow && Flow->ShouldShowTutorialControls();
}

void UCatrunLevelFlowLibrary::MarkTutorialOnboardingCompleted(const UObject* Context)
{
    if (auto* Flow = UCatrunLevelFlowSubsystem::Get(Context)) Flow->MarkTutorialOnboardingCompleted();
}

bool ACatrunStageExit::IsInsideCorridor(const APawn& Pawn) const
{
    return bProtectStage1Corridor && bUseExitTransition && OverlappingPawn.Get() == &Pawn
        && !InteriorDirectionLocal.IsNearlyZero() && CorridorEntryDepth <= MinimumInteriorDepth
        && IsCenterBeyondDepth(Pawn.GetActorLocation(), CorridorEntryDepth);
}

bool ACatrunStageExit::IsCenterQualified(const FVector& WorldLocation) const
{
    return IsCenterBeyondDepth(WorldLocation, MinimumInteriorDepth);
}

bool ACatrunStageExit::IsCenterBeyondDepth(const FVector& WorldLocation, float Depth) const
{
    if (!Trigger || WorldLocation.ContainsNaN() || InteriorDirectionLocal.ContainsNaN() || !FMath::IsFinite(Depth)) return false;
    const FTransform Transform = Trigger->GetComponentTransform();
    const FVector Scale = Transform.GetScale3D().GetAbs();
    if (!Transform.IsValid() || Scale.GetMin() < UE_SMALL_NUMBER) return false;
    const FVector Local = Transform.InverseTransformPosition(WorldLocation);
    const FVector Extent = Trigger->GetUnscaledBoxExtent();
    return FMath::Abs(Local.X) <= Extent.X && FMath::Abs(Local.Y) <= Extent.Y && FMath::Abs(Local.Z) <= Extent.Z
        && (InteriorDirectionLocal.IsNearlyZero() || FVector::DotProduct(Local, InteriorDirectionLocal.GetSafeNormal()) >= Depth);
}

void ACatrunStageExit::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (bProtectStage1Corridor)
        if (auto* Marks = UCatrunMarkSubsystem::Get(this)) Marks->RefreshCorridor();
    // Sequenced motion can leave the trigger. Only gameplay motion should rearm a spent entry.
    if (ExitTransition && ExitTransition->BlocksExitQualification()) return;
    APawn* Pawn = OverlappingPawn.Get();
    const bool bQualified = Pawn && Trigger->IsOverlappingActor(Pawn)
        && (!(bRequireCenterInside || bUseExitTransition) || IsCenterQualified(Pawn->GetActorLocation()));
    if (!bQualified) bArmed = true;
    else if (bArmed) TryCompleteFor(Pawn);
}
