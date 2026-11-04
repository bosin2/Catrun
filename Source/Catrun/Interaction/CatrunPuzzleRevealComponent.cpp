#include "CatrunPuzzleRevealComponent.h"
#include "CatrunPuzzleSuspension.h"
#include "CatrunBasketInteractionComponent.h"
#include "Components/InputComponent.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "Monster/CatrunRestartSubsystem.h"
#include "Engine/World.h"

UCatrunPuzzleRevealComponent::UCatrunPuzzleRevealComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.bStartWithTickEnabled = false;
}
bool UCatrunPuzzleRevealComponent::ShouldAbort() const
{
	const UWorld* World = GetWorld();
	if (!World || World->bIsTearingDown || World->IsInSeamlessTravel()) return true;
	if (GEngine) if (const auto* Context = GEngine->GetWorldContextFromWorld(World); Context && !Context->TravelURL.IsEmpty()) return true;
	if (const auto* Flow = UCatrunLevelFlowSubsystem::Get(this); Flow && (Flow->IsTransitioning() || Flow->IsStageComplete())) return true;
	const auto* Restart = UCatrunRestartSubsystem::Get(this);
	return Restart && Restart->IsCatching();
}
bool UCatrunPuzzleRevealComponent::BeginReveal(FName Id, AActor* Gate, const FBox& Bounds)
{
	if (!bEnabled || bStarting || bCleaning || bEnding || Phase != ECatrunPuzzleRevealPhase::Inactive || !IsValid(Gate) || ShouldAbort()) return false;
	auto* PC = UGameplayStatics::GetPlayerController(this, 0);
	auto* Guard = UCatrunPuzzleSuspension::Get(this);
	if (PC && PC->GetPawn()) if (const auto* Actions = PC->GetPawn()->FindComponentByClass<UCatrunBasketInteractionComponent>(); Actions && (Actions->Busy || Actions->IsHidden)) return false;
	if (!PC || !PC->GetPawn() || !Guard || !Guard->Acquire(this)) return false;
	TGuardValue<bool> Starting(bStarting, true);
	Player = PC;
	PreviousView = PC->GetViewTarget();
	TargetGate = Gate;
	PuzzleId = Id;
	++SessionId;
	Elapsed = PhaseElapsed = 0;
	PC->SetIgnoreMoveInput(true);
	PC->SetIgnoreLookInput(true);
	bOwnInput = true;
	// IgnoreMove/Look alone do not consume Enhanced Input bell/basket actions.
	InputBlocker = NewObject<UInputComponent>(PC);
	InputBlocker->Priority = MAX_int32;
	InputBlocker->bBlockInput = true;
	InputBlocker->RegisterComponent();
	PC->PushInputComponent(InputBlocker);
	if (auto* Cat = Cast<ACharacter>(PC->GetPawn()))
	{
		Cat->ConsumeMovementInputVector();
		Cat->GetCharacterMovement()->StopMovementImmediately();
	}
	if (PC->PlayerCameraManager)
	{
		CameraStart = PC->PlayerCameraManager->GetCameraLocation();
		CameraStartRotation = PC->PlayerCameraManager->GetCameraRotation();
		CameraEnd = CameraStart;
		CameraEndRotation = CameraStartRotation;
		const FVector Focus = Bounds.GetCenter();
		FCollisionQueryParams Params(SCENE_QUERY_STAT(PuzzleReveal), false, Gate);
		Params.AddIgnoredActor(PC->GetPawn());
		const auto Probe = FCollisionShape::MakeSphere(10.f);
		for (float Sign : {1.f, -1.f})
		{
			const FVector Candidate = Focus + FVector(GateCameraOffset.X, GateCameraOffset.Y * Sign, GateCameraOffset.Z);
			FHitResult Hit;
			if (!GetWorld()->OverlapBlockingTestByChannel(Candidate, FQuat::Identity, ECC_Camera, Probe, Params)
				&& !GetWorld()->SweepSingleByChannel(Hit, CameraStart, Candidate, FQuat::Identity, ECC_Camera, Probe, Params)
				&& !GetWorld()->LineTraceTestByChannel(Candidate, Focus, ECC_Visibility, Params))
			{
				CameraEnd = Candidate; CameraEndRotation = (Focus-Candidate).Rotation(); break;
			}
		}
		FActorSpawnParameters Spawn;
		Spawn.Owner = GetOwner();
		Spawn.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		Camera = GetWorld()->SpawnActor<ACameraActor>(CameraStart, CameraStartRotation, Spawn);
		if (Camera.IsValid()) { Camera->GetCameraComponent()->bConstrainAspectRatio = false; PC->SetViewTarget(Camera.Get()); }
	}
	SetComponentTickEnabled(true);
	return SetPhase(ECatrunPuzzleRevealPhase::ToGate);
}
bool UCatrunPuzzleRevealComponent::SetPhase(ECatrunPuzzleRevealPhase Next)
{
	const int32 ExpectedSession = SessionId;
	Phase = Next;
	PhaseElapsed = 0;
	OnPhaseChanged.Broadcast(PuzzleId, Next, ExpectedSession);
	return !bCleaning && !bEnding && SessionId == ExpectedSession && Phase == Next;
}
bool UCatrunPuzzleRevealComponent::CanOpenGate(FName Id) const
{
	return PuzzleId != Id || Phase != ECatrunPuzzleRevealPhase::ToGate;
}
void UCatrunPuzzleRevealComponent::NotifyCameraAtGate(int32 ExpectedSession)
{
	if (!bCleaning && ExpectedSession == SessionId && Phase == ECatrunPuzzleRevealPhase::ToGate) SetPhase(ECatrunPuzzleRevealPhase::Opening);
}
void UCatrunPuzzleRevealComponent::GateOpened(FName Id)
{
	if (PuzzleId == Id && Phase == ECatrunPuzzleRevealPhase::Opening) SetPhase(ECatrunPuzzleRevealPhase::Returning);
}
void UCatrunPuzzleRevealComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* Function)
{
	Super::TickComponent(DeltaTime, TickType, Function);
	if (Phase == ECatrunPuzzleRevealPhase::Inactive) return;
	Elapsed += FMath::Max(0.f, DeltaTime);
	PhaseElapsed += FMath::Max(0.f, DeltaTime);
	if (ShouldAbort() || !TargetGate.IsValid() || !Player.IsValid() || !Player->GetPawn()
		|| Elapsed >= FMath::Clamp(MaximumLockTime, 1.f, 15.f)
		|| (Camera.IsValid() && Player->GetViewTarget() != Camera.Get())) { Cleanup(); return; }
	const int32 ExpectedSession = SessionId;
	if (Phase == ECatrunPuzzleRevealPhase::ToGate || Phase == ECatrunPuzzleRevealPhase::Returning)
	{
		const bool bReturn = Phase == ECatrunPuzzleRevealPhase::Returning;
		const float Duration = bReturn ? CameraReturnTime : CameraTravelTime;
		const float Alpha = Duration > 0 ? FMath::Clamp(PhaseElapsed / Duration, 0.f, 1.f) : 1.f;
		if (Camera.IsValid())
		{
			const FVector Wanted = FMath::Lerp(bReturn ? CameraEnd : CameraStart, bReturn ? CameraStart : CameraEnd, FMath::SmoothStep(0.f,1.f,Alpha));
			FCollisionQueryParams Params(SCENE_QUERY_STAT(PuzzleCameraMove), false, TargetGate.Get());
			Params.AddIgnoredActor(Player->GetPawn());
			FHitResult Hit;
			if (!GetWorld()->SweepSingleByChannel(Hit, Camera->GetActorLocation(), Wanted, FQuat::Identity, ECC_Camera, FCollisionShape::MakeSphere(10.f), Params))
				Camera->SetActorLocation(Wanted);
			Camera->SetActorRotation(FMath::Lerp(bReturn ? CameraEndRotation : CameraStartRotation, bReturn ? CameraStartRotation : CameraEndRotation, Alpha));
		}
		if (Alpha >= 1.f)
		{
			if (bReturn) Cleanup();
			else NotifyCameraAtGate(ExpectedSession);
		}
	}
}
void UCatrunPuzzleRevealComponent::CancelReveal() { Cleanup(); }
void UCatrunPuzzleRevealComponent::Cleanup()
{
	if (bCleaning || Phase == ECatrunPuzzleRevealPhase::Inactive) return;
	TGuardValue<bool> Cleaning(bCleaning, true);
	if (auto* PC = Player.Get())
	{
		if (Camera.IsValid() && PC->GetViewTarget() == Camera.Get())
			PC->SetViewTarget(PreviousView.IsValid() ? PreviousView.Get() : PC->GetPawn());
		if (bOwnInput) { PC->SetIgnoreMoveInput(false); PC->SetIgnoreLookInput(false); }
		if (InputBlocker) PC->PopInputComponent(InputBlocker);
	}
	if (InputBlocker) InputBlocker->DestroyComponent();
	InputBlocker = nullptr;
	bOwnInput = false;
	if (auto* Guard = UCatrunPuzzleSuspension::Get(this)) Guard->Release(this);
	if (Camera.IsValid()) Camera->Destroy();
	Camera.Reset(); Player.Reset(); PreviousView.Reset(); TargetGate.Reset();
	SetComponentTickEnabled(false);
	SetPhase(ECatrunPuzzleRevealPhase::Inactive);
}
void UCatrunPuzzleRevealComponent::EndPlay(const EEndPlayReason::Type Reason)
{
	bEnding = true;
	Cleanup();
	Super::EndPlay(Reason);
}
