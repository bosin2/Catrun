#include "CatrunLevelFlow.h"
#include "CatrunPlayHUD.h"
#include "HAL/IConsoleManager.h"

#include "Components/BoxComponent.h"
#include "Camera/CameraComponent.h"
#include "Engine/GameInstance.h"
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

DEFINE_LOG_CATEGORY_STATIC(LogCatrunFlow, Log, All);

namespace
{
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

void FCatrunRestartIntent::Request(const FString& Package, float FadeDuration)
{
	MapPackage = UWorld::RemovePIEPrefix(Package);
	FadeInDuration = FMath::IsFinite(FadeDuration) ? FMath::Max(0.f, FadeDuration) : 0.f;
}

void FCatrunRestartIntent::Clear()
{
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

void UCatrunLevelFlowSubsystem::ResolveRestartIntent()
{
	if (bRestartIntentResolved) return;
	bRestartIntentResolved = true;
	if (UGameInstance* Instance = GetWorld()->GetGameInstance())
		if (auto* Session = Instance->GetSubsystem<UCatrunFlowSession>())
			bSkipStageIntro = Session->RestartIntent.Consume(GetWorld()->GetOutermost()->GetName(), RestartFadeInDuration);
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
	if (bTransitioning || StageIndex == INDEX_NONE) return;
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
	if (PC->WasInputKeyJustPressed(EKeys::Escape) || PC->WasInputKeyJustPressed(EKeys::P)) SetPauseMenu(true);
#if WITH_EDITOR
	else if (GetWorld()->WorldType == EWorldType::PIE && CVarDebugRestart.GetValueOnGameThread() != 0 && PC->WasInputKeyJustPressed(EKeys::R)) RestartStage();
#endif
}

void UCatrunLevelFlowSubsystem::SetPauseMenu(bool bOpen)
{
	if (!PlayHUD || bTransitioning) return;
	APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0);
	if (!PC) return;
	UGameplayStatics::SetGamePaused(this, bOpen);
	PlayHUD->SetMenuOpen(bOpen);
	PC->bShowMouseCursor = bOpen;
	if (bOpen)
	{
		FInputModeUIOnly Mode;
		Mode.SetWidgetToFocus(PlayHUD->TakeWidget());
		PC->SetInputMode(Mode);
	}
	else
	{
		PC->SetInputMode(FInputModeGameOnly());
		PC->FlushPressedKeys(); // Do not reopen the menu or resume a held movement key on the same frame.
	}
}

bool UCatrunLevelFlowSubsystem::TravelTo(const TSoftObjectPtr<UWorld>& Map, const FString& Options)
{
	if (bTransitioning) return false;
	const FString Package = Map.ToSoftObjectPath().GetLongPackageName();
	if (Package.IsEmpty() || !FPackageName::DoesPackageExist(Package))
	{
		UE_LOG(LogCatrunFlow, Error, TEXT("Cannot travel: missing map '%s'."), *Package);
		if (auto* Notice = UCatrunNoticeSubsystem::Get(this))
			Notice->ShowNotice(NSLOCTEXT("Catrun", "MissingFlowMap", "다음 구역을 불러올 수 없습니다."), 5.f);
		return false;
	}
	PendingMap = Package;
	PendingOptions = Options;
	if (PlayHUD && PlayHUD->bMenuOpen) SetPauseMenu(false);
	bTransitioning = true;
	if (APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0))
	{
		PC->SetIgnoreMoveInput(true);
		if (APawn* Pawn = PC->GetPawn())
			if (UPawnMovementComponent* Movement = Pawn->GetMovementComponent()) Movement->StopMovementImmediately();
	}
	UE_LOG(LogCatrunFlow, Log, TEXT("Travel requested: %s -> %s [%s]"), *GetWorld()->GetOutermost()->GetName(), *Package, *Options);
	// Existing level cinematics own their fades. Travel must not add another one.
	FinishTravel();
	return true;
}

void UCatrunLevelFlowSubsystem::FinishTravel()
{
	UGameplayStatics::OpenLevel(this, FName(*PendingMap), true, PendingOptions);
}

bool UCatrunLevelFlowSubsystem::StartGame()
{
	const auto* Settings = GetDefault<UCatrunLevelFlowSettings>();
	if (Settings->Stages.Num() == 0 || !TravelTo(Settings->Stages[0].Map)) return false;
	if (UGameInstance* Instance = GetWorld()->GetGameInstance())
		if (auto* Session = Instance->GetSubsystem<UCatrunFlowSession>()) Session->RestartIntent.Clear();
	return true;
}

bool UCatrunLevelFlowSubsystem::CompleteStage()
{
	if (bTransitioning || bStageComplete) return false;
	if (const auto* Restart = UCatrunRestartSubsystem::Get(this); Restart && Restart->IsCatching()) return false;
	const auto* Settings = GetDefault<UCatrunLevelFlowSettings>();
	const int32 Index = Settings->FindStageIndex(GetWorld()->GetOutermost()->GetName());
	if (Index == INDEX_NONE) return false;
	if (Settings->Stages.IsValidIndex(Index + 1))
	{
		// Preserve the existing tutorial stair arrival Blueprint's URL option.
		const FString Options = Settings->Stages[Index].StageId == TEXT("Tutorial") ? TEXT("FromTutorial") : FString();
		return TravelTo(Settings->Stages[Index + 1].Map, Options);
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
	if (UGameInstance* Instance = GetWorld()->GetGameInstance())
		if (auto* Session = Instance->GetSubsystem<UCatrunFlowSession>()) Session->RestartIntent.Clear();
	return true;
}

bool UCatrunLevelFlowSubsystem::RestartStage()
{
	if (bTransitioning) return false;
	const auto* Settings = GetDefault<UCatrunLevelFlowSettings>();
	if (Settings->FindStageIndex(GetWorld()->GetOutermost()->GetName()) == INDEX_NONE) return false;
	if (const auto* Restart = UCatrunRestartSubsystem::Get(this); Restart && Restart->IsCatching()) return false;
	const FString Package = UWorld::RemovePIEPrefix(GetWorld()->GetOutermost()->GetName());
	if (!TravelTo(TSoftObjectPtr<UWorld>(FSoftObjectPath(Package)))) return false;
	if (UGameInstance* Instance = GetWorld()->GetGameInstance())
		if (auto* Session = Instance->GetSubsystem<UCatrunFlowSession>()) Session->RestartIntent.Request(Package, 0.f);
	return true;
}

bool UCatrunLevelFlowLibrary::StartNewGame(const UObject* Context)
{
	auto* Flow = UCatrunLevelFlowSubsystem::Get(Context);
	return Flow && Flow->StartGame();
}
bool UCatrunLevelFlowLibrary::CompleteCurrentStage(const UObject* Context)
{
	auto* Flow = UCatrunLevelFlowSubsystem::Get(Context);
	return Flow && Flow->CompleteStage();
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
	Trigger = CreateDefaultSubobject<UBoxComponent>(TEXT("Trigger"));
	SetRootComponent(Trigger);
	Trigger->SetBoxExtent(FVector(70, 35, 80));
	Trigger->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	Trigger->SetCollisionResponseToAllChannels(ECR_Ignore);
	Trigger->SetCollisionResponseToChannel(ECC_Pawn, ECR_Overlap);
	Trigger->SetGenerateOverlapEvents(true);
	OnActorBeginOverlap.AddDynamic(this, &ACatrunStageExit::HandleOverlap);
}

void ACatrunStageExit::HandleOverlap(AActor*, AActor* OtherActor)
{
	TryCompleteFor(Cast<APawn>(OtherActor));
}

bool ACatrunStageExit::TryCompleteFor(APawn* Pawn)
{
	if (!Pawn || Pawn != UGameplayStatics::GetPlayerPawn(this, 0) || !Trigger->IsOverlappingActor(Pawn)) return false;
	if (const auto* Actions = Pawn->FindComponentByClass<UCatrunBasketInteractionComponent>(); Actions && (Actions->Busy || Actions->IsHidden)) return false;
	return UCatrunLevelFlowLibrary::CompleteCurrentStage(this);
}
