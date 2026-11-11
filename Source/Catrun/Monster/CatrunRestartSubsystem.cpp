#include "CatrunRestartSubsystem.h"
#include "Interaction/CatrunPuzzleSuspension.h"

#include "Camera/PlayerCameraManager.h"
#include "Engine/GameInstance.h"
#include "Engine/Engine.h"
#include "TimerManager.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "LevelFlow/CatrunLevelFlow.h"

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

bool UCatrunRestartSubsystem::TryBeginCatch()
{
	if (UCatrunPuzzleSuspension::IsSuspended(this)) return false;
	if (const auto* Flow = UCatrunLevelFlowSubsystem::Get(this); Flow && (Flow->IsTransitioning() || Flow->IsStageComplete())) return false;
	if (bCatching)
	{
		return false;
	}
	bCatching = true;
	return true;
}

bool UCatrunRestartSubsystem::CanRecoverWorld() const
{
	const UWorld* World = GetWorld();
	if (!World || !World->IsGameWorld() || World->bIsTearingDown || World->IsInSeamlessTravel()) return false;
	const auto* Flow = World->GetSubsystem<UCatrunLevelFlowSubsystem>();
	if (Flow && (Flow->IsTransitioning() || Flow->IsStageComplete())) return false;
	const FWorldContext* Context = GEngine ? GEngine->GetWorldContextFromWorld(World) : nullptr;
	return Context && Context->TravelURL.IsEmpty();
}

bool UCatrunRestartSubsystem::ScheduleRecoveryRestart(float FadeInDuration)
{
	if (bRecoveryScheduled || !CanRecoverWorld()) return false;
	bRecoveryScheduled = true;
	RecoveryTimer = GetWorld()->GetTimerManager().SetTimerForNextTick(FTimerDelegate::CreateWeakLambda(this, [this, FadeInDuration]()
	{
		bRecoveryScheduled = false;
		// Travel/teardown may have begun since the failed placement. They take precedence.
		if (CanRecoverWorld()) RestartLevel(FadeInDuration);
	}));
	return true;
}

void UCatrunRestartSubsystem::FadeOut(APawn* Cat, float Duration)
{
	APlayerController* Controller = Cat ? Cast<APlayerController>(Cat->GetController()) : UGameplayStatics::GetPlayerController(this, 0);
	if (Controller && Controller->PlayerCameraManager)
	{
		Controller->PlayerCameraManager->StartCameraFade(0.f, 1.f, Duration, FLinearColor::Black, false, true);
	}
}

bool UCatrunRestartSubsystem::RestartLevel(float FadeInDuration, TFunction<void(const FString&)> Failure)
{
	if (!CanRecoverWorld()) return false;
	auto* Flow = UCatrunLevelFlowSubsystem::Get(this);
	return Flow && Flow->RequestSameMapRestart(this, FadeInDuration, MoveTemp(Failure));
}

void UCatrunRestartSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);
	auto* Flow = InWorld.GetSubsystem<UCatrunLevelFlowSubsystem>();
	if (!Flow || !Flow->ShouldSkipStageIntro() || Flow->GetRestartFadeInDuration() <= 0.f)
	{
		return;
	}

	// The new level starts black and fades in; the cat is at its start place again.
	APlayerController* Controller = UGameplayStatics::GetPlayerController(&InWorld, 0);
	if (Controller && Controller->PlayerCameraManager)
	{
		Controller->PlayerCameraManager->StartCameraFade(1.f, 0.f, Flow->GetRestartFadeInDuration(), FLinearColor::Black, false, false);
	}
}
