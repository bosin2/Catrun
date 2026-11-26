#include "CatrunRestartSubsystem.h"
#include "Interaction/CatrunPuzzleSuspension.h"
#include "Perception/CatrunSafeRestore.h"
#include "Sound/CatrunNotice.h"

#include "Camera/CameraShakeBase.h"
#include "Camera/PlayerCameraManager.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PawnMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "TimerManager.h"

UCatrunRestartSubsystem* UCatrunRestartSubsystem::Get(const UObject* WorldContextObject)
{
	const UWorld* World = GEngine ? GEngine->GetWorldFromContextObject(WorldContextObject, EGetWorldErrorMode::ReturnNull) : nullptr;
	return World ? World->GetSubsystem<UCatrunRestartSubsystem>() : nullptr;
}

bool UCatrunRestartSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	const UWorld* World = Cast<UWorld>(Outer);
	return World && World->IsGameWorld();
}

bool UCatrunRestartSubsystem::TryBeginCatch(UObject* Owner)
{
	check(IsInGameThread()); // Admission and publication are one synchronous game-thread operation.
	const UWorld* World = GetWorld();
	if (!IsValid(Owner) || !World || World->bIsTearingDown) return false;
	// Detached automation worlds have no travel handler. IsInSeamlessTravel requires one.
	const FWorldContext* Context = GEngine ? GEngine->GetWorldContextFromWorld(World) : nullptr;
	if (Context && (!Context->TravelURL.IsEmpty() || World->IsInSeamlessTravel())) return false;
	if (bRecoveryScheduled || HasBlockedPawnRecovery() || UCatrunPuzzleSuspension::IsSuspended(this)) return false;
	if (const auto* Flow = UCatrunLevelFlowSubsystem::Get(this); Flow && (Flow->IsTransitioning() || Flow->IsStageComplete())) return false;
	if (bCatching)
	{
		return false;
	}
	bCatching = true;
	CatchOwner = Owner;
	OnCatchOwnerChanged.Broadcast(Owner);
	return true;
}

void UCatrunRestartSubsystem::CancelCatch(UObject* Owner)
{
	check(IsInGameThread());
	if (!IsCatchOwner(Owner)) return;
	if (Owner == this && TimeoutController.IsValid()) ReleaseTimeoutPresentation();
	bCatching = false;
	CatchOwner.Reset();
	OnCatchOwnerChanged.Broadcast(nullptr);
}

void UCatrunRestartSubsystem::Deinitialize()
{
	bCatching = false;
	CatchOwner.Reset();
	OnCatchOwnerChanged.Clear();
	ReleaseTimeoutPresentation();
	if (GetWorld()) GetWorld()->GetTimerManager().ClearTimer(RecoveryTimer);
	Super::Deinitialize();
}

void UCatrunRestartSubsystem::CancelCaptureRestart(UObject* Owner)
{
	if (!IsCatchOwner(Owner)) return;
	if (auto* Flow = UCatrunLevelFlowSubsystem::Get(this)) Flow->AbortOwnedTravel(this);
}

bool UCatrunRestartSubsystem::CanRecoverWorld() const
{
	const UWorld* World = GetWorld();
	if (!World || !World->IsGameWorld() || World->bIsTearingDown) return false;
	const FWorldContext* Context = GEngine ? GEngine->GetWorldContextFromWorld(World) : nullptr;
	if (!Context || World->IsInSeamlessTravel()) return false;
	const auto* Flow = World->GetSubsystem<UCatrunLevelFlowSubsystem>();
	if (Flow && (Flow->IsTransitioning() || Flow->IsStageComplete())) return false;
	return Context->TravelURL.IsEmpty();
}

bool UCatrunRestartSubsystem::ScheduleRecoveryRestart(float FadeInDuration, TFunction<void()> RestoreAfterFailure)
{
	if (bRecoveryScheduled || !CanRecoverWorld()) return false;
	bRecoveryScheduled = true;
	const bool bWasCapture = IsCatching();
	RecoveryTimer = GetWorld()->GetTimerManager().SetTimerForNextTick(FTimerDelegate::CreateWeakLambda(this,
		[this, FadeInDuration, bWasCapture, RestoreAfterFailure = MoveTemp(RestoreAfterFailure)]()
	{
		bRecoveryScheduled = false;
		// A competing travel still owns its request. A surviving world needs a playable pawn.
		if (!RestartLevel(FadeInDuration, [RestoreAfterFailure](const FString&)
		{
			if (RestoreAfterFailure) RestoreAfterFailure();
		}, bWasCapture) && RestoreAfterFailure) RestoreAfterFailure();
	}));
	return true;
}

bool UCatrunRestartSubsystem::HasBlockedPawnRecovery() const
{
	const auto* Pawn = BlockedRecoveryPawn.Get();
	return Pawn && !Pawn->GetActorEnableCollision();
}

bool UCatrunRestartSubsystem::HasBlockedPawnRecovery(const APawn* Pawn) const
{
	return Pawn && BlockedRecoveryPawn.Get() == Pawn && HasBlockedPawnRecovery();
}

void UCatrunRestartSubsystem::ReportBlockedPawnRecovery(APawn& Pawn)
{
	BlockedRecoveryPawn = &Pawn;
	if (auto* Notice = UCatrunNoticeSubsystem::Get(this))
		Notice->ShowNotice(NSLOCTEXT("Catrun", "BlockedPawnRecovery", "안전한 위치로 돌아갈 수 없습니다. 설정에서 스테이지를 다시 시작하거나 시작 메뉴로 돌아가세요."), 8.f, ECatrunNoticePolicy::BlockedRecovery);
	UE_LOG(LogTemp, Display, TEXT("Pawn recovery has no clear supported placement in %s."), *GetWorld()->GetName());
}

bool UCatrunRestartSubsystem::BeginStageTimeout()
{
	UWorld* World = GetWorld();
	auto* Controller = World ? UGameplayStatics::GetPlayerController(World, 0) : nullptr;
	if (!Controller || !TryBeginCatch(this) || !IsCatchOwner(this)) return false;
	TimeoutController = Controller;
	Controller->SetIgnoreMoveInput(true);
	Controller->SetIgnoreLookInput(true);
	if (APawn* Pawn = Controller->GetPawn())
		if (auto* Movement = Pawn->GetMovementComponent()) Movement->StopMovementImmediately();
	if (auto* Notice = UCatrunNoticeSubsystem::Get(this))
		Notice->ShowNotice(NSLOCTEXT("Catrun", "StageTimeout", "마왕이 깨어났다"), 1.6f, ECatrunNoticePolicy::StageTimeout);
	if (auto* CameraManager = Controller->PlayerCameraManager.Get())
	{
		// Presentation only: the room shudders and darkens red before the unchanged 1.2s + .4s failure fade.
		CameraManager->StartCameraFade(0.f, .45f, .6f, FLinearColor(.02f, 0.f, 0.f), false, true);
		bTimeoutFadeStarted = true;
		const FSoftClassPath Shake(TEXT("/Game/Environment/Stage2/GameplayPolish_20261125/Presentation/CameraShakeCorrection_20261125/CS_GateImpact.CS_GateImpact_C"));
		if (UClass* ShakeClass = Shake.TryLoadClass<UCameraShakeBase>()) CameraManager->StartCameraShake(ShakeClass, 2.5f);
	}
	World->GetTimerManager().SetTimer(TimeoutTimer, this, &UCatrunRestartSubsystem::StartTimeoutFade, 1.2f, false);
	return true;
}

void UCatrunRestartSubsystem::StartTimeoutFade()
{
	if (!IsCatchOwner(this)) return;
	if (const auto* Controller = TimeoutController.Get(); Controller && Controller->PlayerCameraManager)
	{
		Controller->PlayerCameraManager->StartCameraFade(.45f, 1.f, .4f, FLinearColor::Black, false, true);
		bTimeoutFadeStarted = true;
	}
	GetWorld()->GetTimerManager().SetTimer(TimeoutTimer, this, &UCatrunRestartSubsystem::CommitTimeoutRestart, .4f, false);
}

void UCatrunRestartSubsystem::CommitTimeoutRestart()
{
	if (!IsCatchOwner(this)) return;
	auto Failed = [this](const FString&)
	{
		CancelCatch();
		if (auto* Notice = UCatrunNoticeSubsystem::Get(this))
			Notice->ShowNotice(NSLOCTEXT("Catrun", "TimeoutTravelFailed", "스테이지를 다시 시작하지 못했습니다. 설정에서 다시 시도하세요."), 5.f, ECatrunNoticePolicy::DeferredGameplay);
		// The clock stays at zero in this surviving world, so the timeout must be able to retry.
		if (auto* Flow = UCatrunLevelFlowSubsystem::Get(this)) Flow->RearmStageTimeout(5.f);
	};
	if (!RestartLevel(.5f, Failed, true)) Failed(FString());
}
void UCatrunRestartSubsystem::ReleaseTimeoutPresentation()
{
	if (GetWorld()) GetWorld()->GetTimerManager().ClearTimer(TimeoutTimer);
	if (auto* Controller = TimeoutController.Get())
	{
		Controller->SetIgnoreMoveInput(false);
		Controller->SetIgnoreLookInput(false);
		if (bTimeoutFadeStarted && Controller->PlayerCameraManager) Controller->PlayerCameraManager->StopCameraFade();
		if (auto* Notice = UCatrunNoticeSubsystem::Get(this)) Notice->ClearStageTimeoutNotice();
	}
	TimeoutController.Reset();
	bTimeoutFadeStarted = false;
}

void UCatrunRestartSubsystem::FadeOut(APawn* Cat, float Duration)
{
	APlayerController* Controller = Cat ? Cast<APlayerController>(Cat->GetController()) : UGameplayStatics::GetPlayerController(this, 0);
	if (Controller && Controller->PlayerCameraManager)
	{
		Controller->PlayerCameraManager->StartCameraFade(0.f, 1.f, Duration, FLinearColor::Black, false, true);
	}
}

bool UCatrunRestartSubsystem::RestartLevel(float FadeInDuration, TFunction<void(const FString&)> Failure, bool bIsCaptureRestart)
{
	if (!CanRecoverWorld()) return false;
	auto* Flow = UCatrunLevelFlowSubsystem::Get(this);
	return Flow && Flow->RequestSameMapRestart(this, FadeInDuration, MoveTemp(Failure), bIsCaptureRestart);
}

void UCatrunRestartSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);
	auto* Flow = InWorld.GetSubsystem<UCatrunLevelFlowSubsystem>();
	if (!Flow || Flow->IsMainMenuWorld()) return;
	const auto* Routes = GetDefault<UCatrunLevelFlowSettings>();
	const bool bRestartFade = Flow->ShouldSkipStageIntro() && Flow->GetRestartFadeInDuration() > 0.f;
	// The first stage's intro continues the menu shot without black; every other stage starts behind black.
	if (!bRestartFade && (!InWorld.GetGameViewport() || Routes->FindStageIndex(InWorld.GetOutermost()->GetName()) <= 0)) return;

	// Fade in on the newly loaded level.
	APlayerController* Controller = UGameplayStatics::GetPlayerController(&InWorld, 0);
	if (Controller && Controller->PlayerCameraManager)
	{
		// StartCameraFade only takes effect on the next camera update; the first drawn frame must already be black.
		Controller->PlayerCameraManager->SetManualCameraFade(1.f, FLinearColor::Black, false);
		// Arrival Blueprints and sequences that begin play later replace this short default fade.
		Controller->PlayerCameraManager->StartCameraFade(1.f, 0.f, bRestartFade ? Flow->GetRestartFadeInDuration() : .1f, FLinearColor::Black, false, false);
	}
}
