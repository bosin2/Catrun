#include "CatrunLevelFlow.h"
#include "CatrunPlayHUD.h"
#include "CatrunProgressSave.h"
#include "CatrunProgressWriter.h"
#include "CatrunExitTransitionComponent.h"
#include "Interaction/CatrunPuzzleSuspension.h"
#include "Settings/CatrunUserSettings.h"
#include "Settings/CatrunSettingsSubsystem.h"
#include "HAL/IConsoleManager.h"

#include "Components/BoxComponent.h"
#include "Camera/CameraComponent.h"
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
#include "Sound/CatrunNotice.h"
#include "Perception/CatrunSafeRestore.h"
#include "SaveGameSystem.h"

DEFINE_LOG_CATEGORY_STATIC(LogCatrunFlow, Log, All);

namespace
{
	const FString ProgressSlot(TEXT("CatrunProgress"));
	constexpr int32 ProgressUser = 0;

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

void FCatrunRestartIntent::Request(const FString& Package, float FadeDuration, bool bIsContinue, bool bRestoreCheckpoint)
{
	bContinue = bIsContinue;
	bRestoreStage2EntryCheckpoint = bRestoreCheckpoint;
	MapPackage = UWorld::RemovePIEPrefix(Package);
	FadeInDuration = FMath::IsFinite(FadeDuration) ? FMath::Max(0.f, FadeDuration) : 0.f;
}

void FCatrunRestartIntent::Clear()
{
	bContinue = false;
	bRestoreStage2EntryCheckpoint = false;
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

uint64 UCatrunFlowSession::AcceptTravel(const FString& Package, bool bBeginProgress, bool bCheckpoint, ECatrunArrivalRestart Restart, int8 OnboardingOnArrival, float FadeInDuration, bool bRestoreStage2EntryCheckpoint)
{
	TitleIntentMap.Reset();
	bRestoreCheckpointOnArrival = bRestoreStage2EntryCheckpoint;
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
	bRestoreCheckpointOnArrival = false;
}

void UCatrunFlowSession::ResolveArrivalRestart(const FString& Package)
{
	if (AcceptedTravelMap.IsEmpty() || AcceptedTravelMap != UWorld::RemovePIEPrefix(Package)) return;
	if (ArrivalRestart == ECatrunArrivalRestart::Clear || ArrivalRestart == ECatrunArrivalRestart::Continue)
		for (const auto& Stage : GetDefault<UCatrunLevelFlowSettings>()->Stages)
			if (Stage.Map.ToSoftObjectPath().GetLongPackageName() == AcceptedTravelMap) { TitleIntentMap = AcceptedTravelMap; break; }
	if (ArrivalRestart == ECatrunArrivalRestart::SkipIntro || ArrivalRestart == ECatrunArrivalRestart::Continue)
		RestartIntent.Request(AcceptedTravelMap, ArrivalFadeInDuration, ArrivalRestart == ECatrunArrivalRestart::Continue, bRestoreCheckpointOnArrival);
	else if (ArrivalRestart == ECatrunArrivalRestart::Clear) RestartIntent.Clear();
	ArrivalRestart = ECatrunArrivalRestart::Preserve;
	ArrivalFadeInDuration = 0.f;
}

bool UCatrunFlowSession::Arrive(const FString& Package)
{
	EnsureProgressLoaded();
	const FString CleanPackage = UWorld::RemovePIEPrefix(Package);
	const bool bAccepted = !AcceptedTravelMap.IsEmpty() && AcceptedTravelMap == CleanPackage;
	ResolveArrivalRestart(CleanPackage);
	const bool bCheckpoint = bAccepted && bCheckpointOnArrival;
	if (bAccepted && bBeginProgressOnArrival)
	{
		++ProgressGeneration;
		if (AcceptedOnboarding >= 0) bTutorialOnboardingCompleted = AcceptedOnboarding != 0;
		ActiveProgressMap = CleanPackage;
	}
	else if (bCheckpoint && !ActiveProgressMap.IsEmpty()) ActiveProgressMap = CleanPackage;
	else if (ActiveProgressMap != CleanPackage) ActiveProgressMap.Reset();
	if (bAccepted && IsTrackingWorld(CleanPackage))
		for (int32 Index = 0; Index < GetDefault<UCatrunLevelFlowSettings>()->Stages.Num(); ++Index)
		{
			const auto& Stage = GetDefault<UCatrunLevelFlowSettings>()->Stages[Index];
			if (Stage.Map.ToSoftObjectPath().GetLongPackageName() == CleanPackage && Index > GetHighestUnlockedStageIndex())
				HighestUnlockedStageId = Stage.StageId;
		}
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

int32 UCatrunLevelFlowSettings::FindStageIndex(const FString& PackageName) const
{
	const FString CleanName = UWorld::RemovePIEPrefix(PackageName);
	const FName ShortName(*FPackageName::GetShortName(CleanName));
	for (int32 Index = 0; Index < Stages.Num(); ++Index)
	{
		// StageId also recognizes the original art maps opened directly during development.
		if (Stages[Index].Map.ToSoftObjectPath().GetLongPackageName() == CleanName || Stages[Index].StageId == ShortName)
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

void UCatrunLevelFlowSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);
	// Intro queries also resolve lazily, so subsystem initialization order cannot consume the token twice.
	ResolveRestartIntent();
	if (auto* Session = GetFlowSession(&InWorld))
		if (Session->Arrive(InWorld.GetOutermost()->GetName()))
			Session->SaveArrivalCheckpoint(InWorld);
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
			bRestoreStage2EntryCheckpoint = Session->RestartIntent.bRestoreStage2EntryCheckpoint;
			bSkipStageIntro = Session->RestartIntent.Consume(GetWorld()->GetOutermost()->GetName(), RestartFadeInDuration);
			bContinueArrival &= bSkipStageIntro;
			bRestoreStage2EntryCheckpoint &= bSkipStageIntro;
		}
}

bool UCatrunLevelFlowSubsystem::ShouldSkipStageIntro()
{
	ResolveRestartIntent();
	return bSkipStageIntro;
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
	Super::Deinitialize();
}

TStatId UCatrunLevelFlowSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UCatrunLevelFlowSubsystem, STATGROUP_Tickables);
}

void UCatrunLevelFlowSubsystem::Tick(float)
{
	const auto* Settings = GetDefault<UCatrunLevelFlowSettings>();
	const int32 StageIndex = Settings->FindStageIndex(GetWorld()->GetOutermost()->GetName());
	if (IsTransitioning() || StageIndex == INDEX_NONE) return;
	// The tutorial already owns its intro, key hints and cinematic input handling.
	if (Settings->Stages[StageIndex].StageId == TEXT("Tutorial")) return;
	APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0);
	if (!PC) return;
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
    UObject* FailureOwner, TFunction<void(const FString&)> Failure, float FadeInDuration, bool bReloadCurrentWorld, bool bRestoreCheckpoint)
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
	if (auto* SettingsUI=UCatrunSettingsSubsystem::Get(this)) SettingsUI->CloseSettings();
	bTransitioning = true;
	if (APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0))
	{
		if (!ExitOwner) { PC->SetIgnoreMoveInput(true); TravelLockController = PC; }
		if (APawn* Pawn = PC->GetPawn())
			if (UPawnMovementComponent* Movement = Pawn->GetMovementComponent()) Movement->StopMovementImmediately();
	}
	UE_LOG(LogCatrunFlow, Log, TEXT("Travel requested: %s -> %s [%s]"), *GetWorld()->GetOutermost()->GetName(), *Package, *Options);
	// Existing level cinematics own their fades. Travel must not add another one.
	if (auto* Session = GetFlowSession(GetWorld()))
		PendingTravelToken = Session->AcceptTravel(PendingMap, bBeginProgress, bCheckpoint, Restart, Onboarding, FadeInDuration, bRestoreCheckpoint);
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
    return Settings->Stages.Num() > 0 && TravelTo(Settings->Stages[0].Map, FString(), true, true, ECatrunArrivalRestart::Clear, nullptr, 0);
}

bool UCatrunLevelFlowSubsystem::ContinueGame()
{
    auto* Session = GetFlowSession(GetWorld());
    const auto* Save = Session ? Session->LoadSavedProgress() : nullptr;
    return Save && Save->IsSupported() && ContinueStage(Save->StageId);
}

bool UCatrunLevelFlowSubsystem::ContinueStage(FName StageId)
{
    if (!UCatrunLevelFlowLibrary::CanContinueStage(this, StageId)) return false;
    auto* Session = GetFlowSession(GetWorld());
    return TravelTo(GetDefault<UCatrunLevelFlowSettings>()->Stages[FindStageId(StageId)].Map,
        FString(), true, true, ECatrunArrivalRestart::Continue, nullptr, Session->HasCompletedOnboarding() ? 1 : 0);
}

bool UCatrunLevelFlowSubsystem::CompleteStage() { return CompleteStageInternal(nullptr); }

bool UCatrunLevelFlowSubsystem::CompleteStageWithFailure(UObject* Owner, TFunction<void(const FString&)> Failure)
{
    if (!IsValid(Owner) || Owner->GetWorld() != GetWorld()) return false;
    return CompleteStageInternal(ExitReservation.Get() == Owner ? Owner : nullptr, Owner, MoveTemp(Failure));
}

bool UCatrunLevelFlowSubsystem::RequestSameMapRestart(UObject* Owner, float FadeInDuration, TFunction<void(const FString&)> Failure, bool bRestoreCheckpoint)
{
    if (!IsValid(Owner) || Owner->GetWorld() != GetWorld() || IsTransitioning() || bStageComplete) return false;
    // This low-level recovery path deliberately permits the current capture's catch reservation.
    // Menu restart admission keeps its separate IsCatching guard in RestartStage.
    const FString Package = UWorld::RemovePIEPrefix(GetWorld()->GetOutermost()->GetName());
    return TravelTo(TSoftObjectPtr<UWorld>(FSoftObjectPath(Package)), FString(), false, false,
        ECatrunArrivalRestart::SkipIntro, nullptr, -1, Owner, MoveTemp(Failure), FadeInDuration, true, bRestoreCheckpoint);
}

bool UCatrunLevelFlowSubsystem::CompleteStageInternal(UObject* ExitOwner, UObject* FailureOwner, TFunction<void(const FString&)> Failure)
{
	if (bTransitioning || bStageComplete || (ExitReservation.IsValid() && ExitReservation.Get() != ExitOwner)) return false;
	if (const auto* Restart = UCatrunRestartSubsystem::Get(this); Restart && Restart->IsCatching()) return false;
	const auto* Settings = GetDefault<UCatrunLevelFlowSettings>();
	const int32 Index = Settings->FindStageIndex(GetWorld()->GetOutermost()->GetName());
	if (Index == INDEX_NONE) return false;
	if (Settings->Stages.IsValidIndex(Index + 1))
	{
		// Preserve the existing tutorial stair arrival Blueprint's URL option.
		const FString Options = Settings->Stages[Index].StageId == TEXT("Tutorial") ? TEXT("FromTutorial") : FString();
        auto* Session = GetFlowSession(GetWorld());
        return TravelTo(Settings->Stages[Index + 1].Map, Options, false,
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
    return TravelTo(GetDefault<UCatrunLevelFlowSettings>()->MainMenuMap);
}

bool UCatrunLevelFlowSubsystem::RestartStage()
{
    if (IsTransitioning()) return false;
    const auto* Settings = GetDefault<UCatrunLevelFlowSettings>();
    if (Settings->FindStageIndex(GetWorld()->GetOutermost()->GetName()) == INDEX_NONE) return false;
    if (const auto* Restart = UCatrunRestartSubsystem::Get(this); Restart && Restart->IsCatching()) return false;
    const FString Package = UWorld::RemovePIEPrefix(GetWorld()->GetOutermost()->GetName());
    return TravelTo(TSoftObjectPtr<UWorld>(FSoftObjectPath(Package)), FString(), false, false, ECatrunArrivalRestart::SkipIntro);
}

bool UCatrunLevelFlowLibrary::StartNewGame(const UObject* Context)
{
	auto* Flow = UCatrunLevelFlowSubsystem::Get(Context);
	return Flow && Flow->StartGame();
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
    return HasContinueGame(Context) ? NSLOCTEXT("Catrun", "SelectContinueChapter", "시작할 구역을 선택하세요.")
        : NSLOCTEXT("Catrun", "NoContinueProgress", "저장된 진행이 없습니다.");
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

void ACatrunStageExit::HandleOverlap(AActor*, AActor* OtherActor)
{
	APawn* Pawn = Cast<APawn>(OtherActor);
	if (!Pawn || !Pawn->IsLocallyControlled() || Pawn != UGameplayStatics::GetPlayerPawn(this, 0)) return;
	OverlappingPawn = Pawn;
	RefreshExitTick();
	TryCompleteFor(Pawn);
}

void ACatrunStageExit::HandleEndOverlap(AActor*, AActor* OtherActor)
{
	if (OverlappingPawn.Get() != OtherActor) return;
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
    bArmed = false;
    if (bUseExitTransition) { BeginPortalPresentation(Pawn); return true; }
    return UCatrunLevelFlowLibrary::CompleteCurrentStage(this);
}

void UCatrunFlowSession::EnsureProgressLoaded()
{
    if (bProgressLoaded) return;
    bProgressLoaded = true;
    const auto* Save = LoadSavedProgress();
    if (!Save || !Save->IsSupported()) return;
    const int32 Reached = FindStageId(Save->StageId);
    const int32 Highest = Save->SchemaVersion >= 3 ? FindStageId(Save->HighestUnlockedStageId) : INDEX_NONE;
    const int32 Index = FMath::Max(Reached, Highest);
    if (Index != INDEX_NONE) HighestUnlockedStageId = GetDefault<UCatrunLevelFlowSettings>()->Stages[Index].StageId;
    bTutorialOnboardingCompleted = Save->HasCompletedOnboarding();
}
int32 UCatrunFlowSession::GetHighestUnlockedStageIndex()
{
    EnsureProgressLoaded();
    return FindStageId(HighestUnlockedStageId);
}
bool UCatrunFlowSession::ConsumeArrivalTitle(const FString& Package)
{
    const bool bMatches = !TitleIntentMap.IsEmpty() && TitleIntentMap == UWorld::RemovePIEPrefix(Package);
    TitleIntentMap.Reset();
    return bMatches;
}
const UCatrunProgressSave* UCatrunFlowSession::LoadSavedProgress() const
{
#if WITH_DEV_AUTOMATION_TESTS
    if (SaveBackendForTest)
    {
        TArray<uint8> Data;
        return SaveBackendForTest->LoadGame(false, *ProgressSlot, ProgressUser, Data)
            ? Cast<UCatrunProgressSave>(UGameplayStatics::LoadGameFromMemory(Data)) : nullptr;
    }
#endif
    return Cast<UCatrunProgressSave>(UGameplayStatics::LoadGameFromSlot(ProgressSlot, ProgressUser));
}
uint64 UCatrunFlowSession::SaveCurrentCheckpoint(const FString& Package, TFunction<void(bool, const FString&)> Completion)
{
    return BeginCheckpoint(Package, false, MoveTemp(Completion));
}
void UCatrunFlowSession::SaveArrivalCheckpoint(UWorld& World)
{
    BeginCheckpoint(World.GetOutermost()->GetName(), true, {});
}
uint64 UCatrunFlowSession::BeginCheckpoint(const FString& Package, bool bRetryOnce, TFunction<void(bool, const FString&)> Completion)
{
    const FString CleanPackage = UWorld::RemovePIEPrefix(Package);
    if (!IsTrackingWorld(CleanPackage)) return 0;
    FName StageId;
    for (const auto& Route : GetDefault<UCatrunLevelFlowSettings>()->Stages)
        if (Route.Map.ToSoftObjectPath().GetLongPackageName() == CleanPackage) { StageId = Route.StageId; break; }
    if (StageId.IsNone()) return 0;
    if (!Writer)
    {
        Writer = MakeShared<FCatrunProgressWriter>();
        Writer->OnIdle.BindUObject(this, &UCatrunFlowSession::OnCheckpointQueueIdle);
    }
    CompletedCheckpointState = ECatrunCheckpointState::Idle;
    return EnqueueCheckpoint(StageId, ProgressGeneration, ++LatestSaveRequest, bRetryOnce, MoveTemp(Completion));
}
uint64 UCatrunFlowSession::EnqueueCheckpoint(FName StageId, uint64 Generation, uint64 Request, bool bRetryOnce, TFunction<void(bool, const FString&)> Completion)
{
    const auto KeepAlive = Writer.ToSharedRef();
    const TWeakObjectPtr<UCatrunFlowSession> Weak(this);
    return KeepAlive->Enqueue([Weak, Generation, StageId](TArray<uint8>& Data)
    {
        auto* Session = Weak.Get();
        if (!Session || Session->ProgressGeneration != Generation) return false;
        if (Session->CheckpointState != ECatrunCheckpointState::Pending)
        {
            Session->CheckpointState = ECatrunCheckpointState::Pending;
            Session->OnCheckpointStateChanged.Broadcast(ECatrunCheckpointState::Pending);
            if (auto* Instance = Session->GetGameInstance()) if (auto* Notice = UCatrunNoticeSubsystem::Get(Instance->GetWorld()))
                Notice->ShowNotice(NSLOCTEXT("Catrun", "CheckpointSavePending", "진행을 저장하고 있습니다."), 2.f);
            if (Session->ProgressGeneration != Generation) return false;
        }
        auto* Save = NewObject<UCatrunProgressSave>();
        Save->StageId = StageId;
        Save->HighestUnlockedStageId = Session->HighestUnlockedStageId;
        Save->SavedAtUtc = FDateTime::UtcNow();
        Save->bTutorialOnboardingCompleted = Session->bTutorialOnboardingCompleted;
        return UGameplayStatics::SaveGameToMemory(Save, Data);
    }, [Weak, StageId, Generation, Request, bRetryOnce, Completion = MoveTemp(Completion)](bool bOK, const FString& Error) mutable
    {
        if (auto* Session = Weak.Get(); Session && Session->ProgressGeneration == Generation && Session->LatestSaveRequest == Request)
        {
            if (!bOK && bRetryOnce)
            {
                Session->EnqueueCheckpoint(StageId, Generation, Request, false, MoveTemp(Completion));
                return;
            }
            Session->CompletedCheckpointState = bOK ? ECatrunCheckpointState::Saved : ECatrunCheckpointState::Failed;
            if (!bOK) UE_LOG(LogCatrunFlow, Error, TEXT("%s"), *Error);
        }
        if (Completion) Completion(bOK, Error);
    });
}
void UCatrunFlowSession::OnCheckpointQueueIdle()
{
    CheckpointState = CompletedCheckpointState;
    OnCheckpointStateChanged.Broadcast(CheckpointState);
    // Subscribers may begin another write. Do not overwrite its pending status or show a stale notice.
    if (IsSavePending()) return;
    if (auto* Instance = GetGameInstance()) if (auto* Notice = UCatrunNoticeSubsystem::Get(Instance->GetWorld()))
    {
        if (CheckpointState == ECatrunCheckpointState::Failed)
            Notice->ShowNotice(NSLOCTEXT("Catrun", "CheckpointSaveFailed", "진행을 저장하지 못했습니다."), 5.f);
        else if (CheckpointState == ECatrunCheckpointState::Saved)
            Notice->ShowNotice(NSLOCTEXT("Catrun", "CheckpointSaved", "진행을 저장했습니다."), 2.f);
    }
}
void UCatrunFlowSession::Deinitialize()
{
    ++ProgressGeneration;
    if (Writer) Writer->OnIdle.Unbind();
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
void UCatrunFlowSession::SetSaveBackendForTest(ISaveGameSystem* Backend)
{
    check(!IsSavePending());
    SaveBackendForTest = Backend;
    bProgressLoaded = false;
    HighestUnlockedStageId = NAME_None;
    Writer = MakeShared<FCatrunProgressWriter>(Backend);
    Writer->OnIdle.BindUObject(this, &UCatrunFlowSession::OnCheckpointQueueIdle);
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
bool UCatrunLevelFlowSubsystem::ConsumeStageTitle(FText& OutTitle)
{
    ResolveRestartIntent();
    OutTitle = FText::GetEmpty();
    if (!bStageTitlePending) return false;
    bStageTitlePending = false;
    OutTitle = GetCurrentStageTitle();
    return !OutTitle.IsEmpty();
}
bool UCatrunLevelFlowSubsystem::ShouldRestoreStage2EntryCheckpoint()
{
    ResolveRestartIntent();
    return bRestoreStage2EntryCheckpoint && bSkipStageIntro;
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
    if (Index < 0 || !Settings->Stages.IsValidIndex(Index + 1) || Settings->Stages[Index].StageId != TEXT("Stage1")
        || Settings->Stages[Index + 1].StageId != TEXT("Stage2")) return false;
    return CompleteStageInternal(Owner);
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

bool ACatrunStageExit::IsCenterQualified(const FVector& WorldLocation) const
{
    if (!Trigger || WorldLocation.ContainsNaN() || InteriorDirectionLocal.ContainsNaN() || !FMath::IsFinite(MinimumInteriorDepth)) return false;
    const FTransform Transform = Trigger->GetComponentTransform();
    const FVector Scale = Transform.GetScale3D().GetAbs();
    if (!Transform.IsValid() || Scale.GetMin() < UE_SMALL_NUMBER) return false;
    const FVector Local = Transform.InverseTransformPosition(WorldLocation);
    const FVector Extent = Trigger->GetUnscaledBoxExtent();
    return FMath::Abs(Local.X) <= Extent.X && FMath::Abs(Local.Y) <= Extent.Y && FMath::Abs(Local.Z) <= Extent.Z
        && (InteriorDirectionLocal.IsNearlyZero() || FVector::DotProduct(Local, InteriorDirectionLocal.GetSafeNormal()) >= MinimumInteriorDepth);
}

void ACatrunStageExit::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    APawn* Pawn = OverlappingPawn.Get();
    const bool bQualified = Pawn && Trigger->IsOverlappingActor(Pawn)
        && (!(bRequireCenterInside || bUseExitTransition) || IsCenterQualified(Pawn->GetActorLocation()));
    if (!bQualified) bArmed = true;
    else if (bArmed) TryCompleteFor(Pawn);
}
