#include "CatrunRestartSubsystem.h"
#include "Interaction/CatrunPuzzleSuspension.h"
#include "Interaction/CatrunStatuePuzzle.h"
#include "Perception/CatrunSafeRestore.h"
#include "Sound/CatrunNotice.h"

#include "Camera/PlayerCameraManager.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PawnMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "TimerManager.h"

namespace
{
bool IsStage2World(const UWorld& World)
{
	const FString Package = UWorld::RemovePIEPrefix(World.GetOutermost()->GetName());
	const auto* Settings = GetDefault<UCatrunLevelFlowSettings>();
	const int32 Index = Settings->FindStageIndex(Package);
	return Settings->Stages.IsValidIndex(Index) && Settings->Stages[Index].StageId == TEXT("Stage2");
}
}

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
	bCatching = false;
	CatchOwner.Reset();
	OnCatchOwnerChanged.Broadcast(nullptr);
}

void UCatrunRestartSubsystem::Deinitialize()
{
	bCatching = false;
	CatchOwner.Reset();
	OnCatchOwnerChanged.Clear();
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
		Notice->ShowNotice(NSLOCTEXT("Catrun", "BlockedPawnRecovery", "안전한 위치로 돌아갈 수 없습니다. 설정에서 스테이지를 다시 시작하거나 타이틀로 돌아가세요."), 8.f, ECatrunNoticePolicy::BlockedRecovery);
	UE_LOG(LogTemp, Display, TEXT("Pawn recovery has no clear supported placement in %s."), *GetWorld()->GetName());
}

void UCatrunRestartSubsystem::MarkStage2EntryCheckpointReached()
{
	if (const UWorld* World = GetWorld(); World && IsStage2World(*World)) bStage2EntryCheckpointReached = true;
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
	return Flow && Flow->RequestSameMapRestart(this, FadeInDuration, MoveTemp(Failure), bIsCaptureRestart && bStage2EntryCheckpointReached);
}

void UCatrunRestartSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);
	auto* Flow = InWorld.GetSubsystem<UCatrunLevelFlowSubsystem>();
	if (Flow && Flow->ShouldRestoreStage2EntryCheckpoint())
		InWorld.OnWorldBeginPlay.AddUObject(this, &UCatrunRestartSubsystem::RestoreStage2EntryCheckpoint);
	if (!Flow || !Flow->ShouldSkipStageIntro() || Flow->GetRestartFadeInDuration() <= 0.f)
	{
		return;
	}

	// Fade in on the newly loaded level.
	APlayerController* Controller = UGameplayStatics::GetPlayerController(&InWorld, 0);
	if (Controller && Controller->PlayerCameraManager)
	{
		Controller->PlayerCameraManager->StartCameraFade(1.f, 0.f, Flow->GetRestartFadeInDuration(), FLinearColor::Black, false, false);
	}
}

void UCatrunRestartSubsystem::RestoreStage2EntryCheckpoint()
{
	UWorld* World = GetWorld();
	if (!World || !IsStage2World(*World)) return;
	APawn* Pawn = UGameplayStatics::GetPlayerPawn(World, 0);
	for (TActorIterator<ACatrunStatuePuzzle> It(World); It; ++It)
	{
		FVector GateLocation;
		if (!It->RestoreStage2EntryCheckpoint(GateLocation)) continue;
		bStage2EntryCheckpointReached = true;
		if (Pawn)
		{
			// Gate11 spans X. The main Stage2 route continues toward -Y from the practice area.
			FTransform Spawn = Pawn->GetActorTransform();
			for (const double Distance : {110., 80., 140.})
			{
				Spawn.SetLocation(FVector(GateLocation.X, GateLocation.Y - Distance, Spawn.GetLocation().Z));
				if (!CatrunRestore::TryPlaceOnSupport(*Pawn, Spawn)) continue;
				if (auto* Movement = Pawn->GetMovementComponent()) Movement->StopMovementImmediately();
				return;
			}
		}
		UE_LOG(LogTemp, Display, TEXT("Stage2 checkpoint restored Gate11; no clear supported checkpoint spawn, retaining the normal start."));
		return;
	}
	UE_LOG(LogTemp, Display, TEXT("Stage2 checkpoint has no valid practice puzzle link."));
}
