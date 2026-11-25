#include "CatrunCapturePresentationComponent.h"
#include "CatrunMarkSubsystem.h"
#include "CatrunArmor.h"
#include "Interaction/CatrunBasketInteractionComponent.h"
#include "Perception/CatrunSafeRestore.h"
#include "CatrunRestartSubsystem.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "Sound/CatrunSoundSettings.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimationAsset.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/PrimitiveComponent.h"
#include "Components/SpotLightComponent.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"

namespace
{
#if !UE_BUILD_SHIPPING
	TAutoConsoleVariable<int32> CVarNoArmorCapture(
		TEXT("catrun.NoArmorCapture"), 0,
		TEXT("Prevent new armor captures for debugging. 0: normal play, 1: prevent capture. Existing captures finish normally."),
		ECVF_Cheat);
#endif
}

void FCatrunCaptureMeshState::Save(USkeletalMeshComponent* Mesh)
{
	if (!Mesh) return;
	Mode = Mesh->GetAnimationMode();
	AnimClass = Mesh->GetAnimClass();
	Animation = Mesh->AnimationData;
	if (auto* Single = Mesh->GetSingleNodeInstance())
	{
		Animation.AnimToPlay = Single->GetCurrentAsset();
		Animation.SavedPosition = Single->GetCurrentTime();
		Animation.SavedPlayRate = Single->GetPlayRate();
		Animation.bSavedLooping = Single->IsLooping();
		Animation.bSavedPlaying = Single->IsPlaying();
	}
}
void FCatrunCaptureMeshState::Restore(USkeletalMeshComponent* Mesh) const
{
	if (!Mesh) return;
	Mesh->SetAnimInstanceClass(AnimClass);
	Mesh->AnimationData = Animation;
	Mesh->SetAnimationMode(Mode, true);
	if (Mode == EAnimationMode::AnimationSingleNode)
	{
		Mesh->PlayAnimation(Animation.AnimToPlay, Animation.bSavedLooping);
		Mesh->SetPosition(Animation.SavedPosition, false);
		Mesh->SetPlayRate(Animation.SavedPlayRate);
		if (!Animation.bSavedPlaying) Mesh->Stop();
	}
}

UCatrunCapturePresentationComponent::UCatrunCapturePresentationComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.bStartWithTickEnabled = false;
}

bool UCatrunCapturePresentationComponent::BeginCapture(APawn* InCat, const UCatrunSoundSettings* InSettings)
{
#if !UE_BUILD_SHIPPING
	if (CVarNoArmorCapture.GetValueOnGameThread() != 0) return false;
#endif
	auto* OwnerArmor = Cast<ACatrunArmor>(GetOwner());
	auto* Restart = UCatrunRestartSubsystem::Get(this);
	if (bBeginningCapture || bCleaningUp || bEndingPlay || IsCapturing() || !IsValid(InCat) || !IsValid(OwnerArmor) || !IsValid(InSettings) || !Restart) return false;
    if (UCatrunMarkSubsystem::IsExcludedFromPerception(InCat)) return false;
    // Cleanup may run inside Framing listeners; keep this guard until the outer setup unwinds.
	TGuardValue<bool> BeginningGuard(bBeginningCapture, true);
	bAbortPreparation = false;
	if (!Restart->TryBeginCatch(this)) return false;
	if (bAbortPreparation || bEndingPlay || !IsValid(OwnerArmor) || !IsValid(InCat) || !Restart->IsCatchOwner(this))
	{
		Restart->CancelCatch(this);
		return false;
	}
	bOwnCatch = true;
	bRestartIssued = false;
	bOwnFade = false;
	Armor = OwnerArmor;
	Cat = InCat;
	Settings = InSettings;
	++SessionId;
	Elapsed = PickupElapsed = GrabElapsed = FadeElapsed = 0.f;
	OriginalTransform = InCat->GetActorTransform();
	bCollision = InCat->GetActorEnableCollision();
	// Acquisition is already reserved; only now end door/turn presentation and snapshot stable idle.
	OwnerArmor->PrepareForCapture();
	if (bAbortPreparation || bEndingPlay || !IsValid(this) || !IsValid(OwnerArmor) || !IsValid(InCat) || !IsValid(InSettings))
	{
		Restart->CancelCatch(this); bOwnCatch = false; Cat.Reset(); Armor.Reset(); Settings = nullptr;
		return false;
	}
	ArmorMeshState.Save(OwnerArmor->GetMesh());
	FramingFromYaw = OwnerArmor->GetActorRotation().Yaw;
	const FVector ToCat = (InCat->GetActorLocation()-OwnerArmor->GetActorLocation()).GetSafeNormal2D();
	FramingTargetYaw = ToCat.IsNearlyZero() ? FramingFromYaw : FMath::GridSnap(ToCat.Rotation().Yaw, 90.f);
	if (auto* Character = Cast<ACharacter>(InCat))
	{
		// End the prior temporary action before snapshotting the stable playable state.
		if (auto* Actions = Character->FindComponentByClass<UCatrunBasketInteractionComponent>()) Actions->CancelBellAction();
		auto* Move = Character->GetCharacterMovement();
		MovementMode = Move->MovementMode;
		CustomMode = Move->CustomMovementMode;
		Move->StopMovementImmediately();
		Move->DisableMovement();
		CatMeshState.Save(Character->GetMesh());
	}
	Player = Cast<APlayerController>(InCat->GetController());
	if (auto* PC = Player.Get())
	{
		PreviousView = PC->GetViewTarget();
		PC->SetIgnoreMoveInput(true);
		PC->SetIgnoreLookInput(true);
		bOwnInputLock = true;
	}
	PickupDuration = FMath::Max(.1f, OwnerArmor->PickupAnim ? OwnerArmor->PickupAnim->GetPlayLength() / FMath::Max(.1f, PickupPlayRate) : MissingAnimationDuration);
	const int32 StartedSession = SessionId;
	if (!SetPhase(ECatrunCapturePhase::Framing)) return false;
	CreateCamera();
	if (!IsCurrentSession(StartedSession, ECatrunCapturePhase::Framing)) return false;
	SetComponentTickEnabled(true);
	return true;
}

bool UCatrunCapturePresentationComponent::IsCurrentSession(int32 ExpectedSession, ECatrunCapturePhase ExpectedPhase) const
{
	const auto* Restart = UCatrunRestartSubsystem::Get(this);
	return IsValid(this) && !bCleaningUp && !bEndingPlay && SessionId == ExpectedSession && Phase == ExpectedPhase
		&& Cat.IsValid() && Armor.IsValid() && IsValid(Settings.Get()) && Restart && Restart->IsCatchOwner(this);
}

bool UCatrunCapturePresentationComponent::SetPhase(ECatrunCapturePhase Next)
{
	const int32 BroadcastSession = SessionId;
	Phase = Next;
	OnPhaseChanged.Broadcast(Next, BroadcastSession);
	if (SessionId == BroadcastSession && IsCapturing() && !bCleaningUp && !bEndingPlay
		&& (!Cat.IsValid() || !Armor.IsValid() || !IsValid(Settings.Get()))) AbortCapture();
	// BP may synchronously abort, destroy participants or begin an entirely new session.
	return IsCurrentSession(BroadcastSession, Next);
}

void UCatrunCapturePresentationComponent::CreateCamera()
{
	auto* PC = Player.Get();
	if (!PC || !PC->PlayerCameraManager) return;
	CameraFrom = PC->PlayerCameraManager->GetCameraLocation();
	CameraFromRotation = PC->PlayerCameraManager->GetCameraRotation();
	FActorSpawnParameters Params;
	Params.Owner = GetOwner();
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	Camera = GetWorld()->SpawnActor<ACameraActor>(CameraFrom, CameraFromRotation, Params);
	if (auto* View = Camera.Get())
	{
		View->GetCameraComponent()->bConstrainAspectRatio = false;
		View->GetCameraComponent()->SetFieldOfView(60.f);
		// Presentation-only key light: dark rooms otherwise show a black cat against black armor.
		auto* Light = NewObject<USpotLightComponent>(View, TEXT("CaptureKeyLight"));
		Light->SetMobility(EComponentMobility::Movable);
		Light->SetupAttachment(View->GetRootComponent());
		Light->SetRelativeLocation(FVector(-20.f, 130.f, 90.f));
		Light->SetIntensityUnits(ELightUnits::Candelas);
		Light->SetIntensity(0.f);
		Light->SetLightColor(FLinearColor(1.f, .86f, .7f));
		Light->SetOuterConeAngle(28.f);
		Light->SetInnerConeAngle(9.f);
		Light->SetSourceRadius(20.f);
		Light->SetAttenuationRadius(1200.f);
		Light->SetCastShadows(false);
		Light->RegisterComponent();
		KeyLight = Light;
		PC->SetViewTarget(View);
		// Gameplay is orthographic; without a cut the first perspective frame smears into motion blur.
		PC->PlayerCameraManager->SetGameCameraCutThisFrame();
	}
	bCameraYawChosen = false;
}

void UCatrunCapturePresentationComponent::UpdateCamera(float DeltaTime)
{
	if (!Camera.IsValid() || !Armor.IsValid() || !Cat.IsValid()) return;
	// The focus includes both participants; re-evaluate every frame as the cat rises.
	const FVector ArmorFocus = Armor->GetActorLocation() + FVector(0,0,Settings->CatchLookAtHeight - Settings->CatchCameraLowering);
	const FVector Focus = (ArmorFocus + Cat->GetActorLocation()) * .5f;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(CatrunCaptureCamera), false, Armor.Get());
	Params.AddIgnoredActor(Cat.Get());
	Params.AddIgnoredActor(Camera.Get());
	const auto Probe = FCollisionShape::MakeSphere(FMath::Max(1.f, CameraProbeRadius));
	const float Distance = FMath::Max(Settings->CatchCameraDistance, FVector::Distance(ArmorFocus, Cat->GetActorLocation()) * 1.4f);
	auto Blocked = [&](const FVector& Point) { return GetWorld()->OverlapBlockingTestByChannel(Point, FQuat::Identity, ECC_Camera, Probe, Params); };
	// Furniture beside the cat can swallow the focus point; start the probe from a clear point of the pair.
	FVector SweepStart = Focus;
	for (const FVector& Start : {Focus, ArmorFocus, FVector(Focus + FVector(0,0,80)), FVector(ArmorFocus + FVector(0,0,60))})
		if (!Blocked(Start)) { SweepStart = Start; break; }
	// The armor ends on FramingTargetYaw. Composing for that heading keeps the shot stable while it turns.
	const FRotationMatrix Heading(FRotator(0.f, FramingTargetYaw, 0.f));
	auto Evaluate = [&](float Yaw, bool bNeedCat, FVector& Out)
	{
		FVector Offset = Heading.GetUnitAxis(EAxis::X) * Distance + Heading.GetUnitAxis(EAxis::Y) * Settings->CatchCameraSideOffset;
		Offset = Offset.RotateAngleAxis(Yaw, FVector::UpVector);
		Offset.Z = Settings->CatchCameraHeight;
		FVector Candidate = Focus + Offset;
		FHitResult Hit;
		if (GetWorld()->SweepSingleByChannel(Hit, SweepStart, Candidate, FQuat::Identity, ECC_Camera, Probe, Params))
		{
			if (Hit.bStartPenetrating) return false;
			Candidate = Hit.Location + Hit.Normal * 2.f;
		}
		if (Blocked(Candidate) || GetWorld()->LineTraceTestByChannel(Candidate, ArmorFocus, ECC_Visibility, Params)
			|| (bNeedCat && GetWorld()->LineTraceTestByChannel(Candidate, Cat->GetActorLocation(), ECC_Visibility, Params))) return false;
		Out = Candidate;
		return true;
	};
	FVector Best = Camera->GetActorLocation();
	const bool bFirst = !bCameraYawChosen;
	if (bFirst)
	{
		// One choice per session: re-scoring every frame made the shot jump. Show the caught cat, so
		// front and side views win and behind the armor is a last resort.
		float BestScore = -1.f;
		for (const bool bNeedCat : {true, false})
		{
			if (BestScore >= 0.f) break;
			for (float Yaw : {0.f, 45.f, -45.f, 90.f, -90.f, 135.f, -135.f, 180.f})
			{
				FVector Candidate;
				if (!Evaluate(Yaw, bNeedCat, Candidate)) continue;
				const float AbsYaw = FMath::Abs(Yaw);
				const float Score = FMath::Clamp((FVector::Distance(Candidate, Focus) - 120.f) / 180.f, .02f, 1.f)
					* (AbsYaw < 1.f ? 1.f : AbsYaw < 46.f ? .9f : AbsYaw < 91.f ? .6f : AbsYaw < 136.f ? .2f : .1f);
				if (Score > BestScore) { BestScore = Score; CameraYaw = Yaw; bCameraNeedsCat = bNeedCat; }
			}
		}
		bCameraOverhead = BestScore < 0.f;
		bCameraYawChosen = true;
	}
	// The rooms have no ceiling, so an overhead view always shows the pair when no eye-level shot fits.
	FVector Candidate;
	if (bCameraOverhead) Best = Focus + Heading.GetUnitAxis(EAxis::X) * 150.f + Heading.GetUnitAxis(EAxis::Y) * 60.f + FVector(0.f, 0.f, 430.f);
	else if (Evaluate(CameraYaw, bCameraNeedsCat, Candidate)) Best = Candidate;
	FHitResult Hit;
	auto PathBlocked = [&](const FVector& From, const FVector& To)
	{
		return GetWorld()->SweepSingleByChannel(Hit, From, To, FQuat::Identity, ECC_Camera, Probe, Params)
			|| GetWorld()->LineTraceTestByChannel(To, Focus, ECC_Visibility, Params);
	};
	// A blend that would cross a wall becomes one clean cut on the first frame instead of a jump half way.
	if (bFirst) bCameraCut = bCameraOverhead || PathBlocked(CameraFrom, (CameraFrom + Best) * .5f) || PathBlocked((CameraFrom + Best) * .5f, Best);
	const float Alpha = Settings->CatchCameraBlendTime > 0.f ? FMath::Clamp(Elapsed / Settings->CatchCameraBlendTime, 0.f, 1.f) : 1.f;
	FVector Blended;
	if (bCameraCut) Blended = bFirst ? Best : FMath::VInterpTo(Camera->GetActorLocation(), Best, DeltaTime, 5.f);
	else Blended = Alpha < 1.f ? FMath::Lerp(CameraFrom, Best, FMath::SmoothStep(0.f, 1.f, Alpha))
		: FMath::VInterpTo(Camera->GetActorLocation(), Best, DeltaTime, 5.f);
	if (!bCameraOverhead && !bFirst && PathBlocked(Camera->GetActorLocation(), Blended)) Blended = Best;
	if (bFirst && bCameraCut && Player.IsValid() && Player->PlayerCameraManager) Player->PlayerCameraManager->SetGameCameraCutThisFrame();
	Camera->SetActorLocationAndRotation(Blended, (Focus-Blended).Rotation());
	// A wall can push the camera close; widen so the armor's head and the cat stay in frame.
	const float FocusDistance = FMath::Max(1.f, FVector::Distance(Blended, Focus));
	int32 Width = 0, Height = 0;
	if (const auto* PC = Player.Get()) PC->GetViewportSize(Width, Height);
	const float Aspect = Height > 0 ? FMath::Clamp(float(Width) / Height, 1.f, 2.4f) : 16.f / 9.f;
	const float Fov = FMath::RadiansToDegrees(2.f * FMath::Atan(CameraFitHalfHeight / FocusDistance * Aspect));
	Camera->GetCameraComponent()->SetFieldOfView(FMath::Clamp(Fov, 60.f, 90.f));
	if (auto* Light = KeyLight.Get())
	{
		Light->SetWorldRotation((Focus - Light->GetComponentLocation()).Rotation());
		Light->SetIntensity(KeyLightLux * FMath::Square(FVector::Distance(Light->GetComponentLocation(), Focus) / 100.f) * FMath::SmoothStep(0.f, 1.f, Alpha));
	}
}

FVector UCatrunCapturePresentationComponent::HandsLocation() const
{
	const auto* Mesh = Armor->GetMesh();
	if (Mesh && Mesh->GetBoneIndex(LeftHandBone) != INDEX_NONE && Mesh->GetBoneIndex(RightHandBone) != INDEX_NONE)
		return (Mesh->GetBoneLocation(LeftHandBone) + Mesh->GetBoneLocation(RightHandBone)) * .5f;
	return Armor->GetActorLocation() + Armor->GetActorForwardVector()*35.f + FVector(0,0,40.f);
}

bool UCatrunCapturePresentationComponent::NotifyGrab(int32 InSessionId)
{
	if (!IsCurrentSession(InSessionId, ECatrunCapturePhase::Pickup)) return false;
	GrabFrom = Cat->GetActorLocation();
	GrabRotation = Cat->GetActorRotation();
	GrabElapsed = 0.f;
	Cat->SetActorEnableCollision(false);
	if (!IsCurrentSession(InSessionId, ECatrunCapturePhase::Pickup)) return false;
	return SetPhase(ECatrunCapturePhase::Holding);
}

bool UCatrunCapturePresentationComponent::NotifyFinished(int32 InSessionId)
{
	if (!IsCurrentSession(InSessionId, ECatrunCapturePhase::Pickup) && !IsCurrentSession(InSessionId, ECatrunCapturePhase::Holding)) return false;
	if (Phase == ECatrunCapturePhase::Pickup && !NotifyGrab(InSessionId)) return false;
	if (!IsCurrentSession(InSessionId, ECatrunCapturePhase::Holding)) return false;
	FadeElapsed = 0.f;
	if (!SetPhase(ECatrunCapturePhase::Fading)) return false;
	if (auto* Restart = UCatrunRestartSubsystem::Get(this))
	{
		Restart->FadeOut(Cat.Get(), Settings->CatchFadeOutTime);
		bOwnFade = true;
	}
	return true;
}

void UCatrunCapturePresentationComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* Tick)
{
	Super::TickComponent(DeltaTime, TickType, Tick);
	if (!IsCapturing() || bRestartIssued) return;
	if (const auto* Restart = UCatrunRestartSubsystem::Get(this); !Restart || !Restart->IsCatchOwner(this)) { AbortCapture(); return; }
	const auto* Flow = UCatrunLevelFlowSubsystem::Get(this);
	if (!Cat.IsValid() || !Armor.IsValid() || !Settings || (Flow && (Flow->IsTransitioning() || Flow->IsStageComplete()))) { AbortCapture(); return; }
	const int32 TickingSession = SessionId;
	Elapsed += DeltaTime;
	if (Phase == ECatrunCapturePhase::Framing)
	{
		const float Alpha = Settings->CatchCameraBlendTime > 0.f ? FMath::Clamp(Elapsed/Settings->CatchCameraBlendTime,0.f,1.f) : 1.f;
		const float Yaw = FramingFromYaw + FMath::FindDeltaAngleDegrees(FramingFromYaw,FramingTargetYaw)*FMath::SmoothStep(0.f,1.f,Alpha);
		Armor->SetActorRotation(FRotator(0.f, FRotator::NormalizeAxis(Yaw),0.f));
		if (!IsCurrentSession(TickingSession, ECatrunCapturePhase::Framing)) return;
	}
	const ECatrunCapturePhase CameraPhase = Phase;
	UpdateCamera(DeltaTime);
	if (!IsCurrentSession(TickingSession, CameraPhase)) return;
	if (Phase == ECatrunCapturePhase::Framing && Elapsed >= Settings->CatchCameraBlendTime)
	{
		if (!bUseBlueprintPresentation)
		{
			if (Armor->PickupAnim)
			{
				Armor->GetMesh()->PlayAnimation(Armor->PickupAnim, false);
				if (!IsCurrentSession(TickingSession, ECatrunCapturePhase::Framing)) return;
				Armor->GetMesh()->SetPlayRate(FMath::Max(.1f, PickupPlayRate));
			}
			if (auto* Character = Cast<ACharacter>(Cat.Get()); Character && CatPickupAnimation)
			{
				Character->GetMesh()->PlayAnimation(CatPickupAnimation, false);
				if (!IsCurrentSession(TickingSession, ECatrunCapturePhase::Framing)) return;
				Character->GetMesh()->SetPlayRate(FMath::Max(.1f, PickupPlayRate));
			}
		}
		if (!SetPhase(ECatrunCapturePhase::Pickup)) return;
	}
	if (Phase == ECatrunCapturePhase::Pickup || Phase == ECatrunCapturePhase::Holding)
	{
		PickupElapsed += DeltaTime;
		// BP notifies are authoritative when present; bounded fallback prevents missing notifies softlocking.
		const float GrabDeadline = FMath::Min(Settings->CatchGrabLatestTime / FMath::Max(.1f, PickupPlayRate), PickupDuration * .8f);
		if (Phase == ECatrunCapturePhase::Pickup && (PickupElapsed >= GrabDeadline || (!bUseBlueprintPresentation && FVector::Dist(HandsLocation(), Cat->GetActorLocation()) <= Settings->CatchGrabDistance)))
		{
			if (!NotifyGrab(TickingSession)) return;
		}
		if (PickupElapsed >= PickupDuration && !NotifyFinished(TickingSession)) return;
	}
	if (Phase == ECatrunCapturePhase::Holding || Phase == ECatrunCapturePhase::Fading)
	{
		GrabElapsed += DeltaTime;
		const float Alpha = Settings->CatchGrabBlendTime > 0.f ? FMath::Clamp(GrabElapsed / Settings->CatchGrabBlendTime, 0.f, 1.f) : 1.f;
		const FVector Hold = HandsLocation() + Armor->GetActorTransform().TransformVectorNoScale(Settings->CatchHoldOffset);
		const float Blend = FMath::SmoothStep(0.f, 1.f, Alpha);
		// Carry turns from this grab's actual heading along the shortest arc. Keep the
		// existing upright policy and the same position/rotation completion time.
		const float Yaw = FRotator::NormalizeAxis(GrabRotation.Yaw
			+ FMath::FindDeltaAngleDegrees(GrabRotation.Yaw, Armor->GetActorRotation().Yaw) * Blend);
		FVector CarryLocation = FMath::Lerp(GrabFrom, Hold, Blend);
		const FRotator CarryRotation(0.f, Yaw, 0.f);
		if (const auto* Root = Cast<UPrimitiveComponent>(Cat->GetRootComponent()))
		{
			// Carry intentionally disables collision. Query the real root shape/profile
			// explicitly; an actor sweep would otherwise allow movement through scenery.
			FCollisionQueryParams Params(SCENE_QUERY_STAT(CatrunCaptureCarry), false, Cat.Get());
			Params.AddIgnoredActor(Armor.Get());
			const FCollisionResponseParams Responses(Root->GetCollisionResponseToChannels());
			const auto Shape = Root->GetCollisionShape();
			const ECollisionChannel Channel = Root->GetCollisionObjectType();
			const FVector Previous = Cat->GetActorLocation();
			FHitResult Hit;
			if (GetWorld()->SweepSingleByChannel(Hit, Previous, CarryLocation, CarryRotation.Quaternion(),
				Channel, Shape, Params, Responses)
				|| GetWorld()->OverlapBlockingTestByChannel(CarryLocation, CarryRotation.Quaternion(),
					Channel, Shape, Params, Responses))
			{
				// Preserve the authored heading and deadlines while the hand path is blocked.
				CarryLocation = Previous;
			}
		}
		Cat->SetActorLocationAndRotation(CarryLocation, CarryRotation);
	}
	if (SessionId != TickingSession || !IsCurrentSession(TickingSession, Phase)) return;
	if (Phase == ECatrunCapturePhase::Fading)
	{
		FadeElapsed += DeltaTime;
		if (FadeElapsed >= Settings->CatchFadeOutTime + Settings->CatchBlackHoldTime)
		{
			bRestartIssued = true;
			// A queued URL is not arrival. Keep the successful teardown behavior, but
			// let only this session release its temporary state if the old world survives.
			const TWeakObjectPtr<UCatrunCapturePresentationComponent> WeakThis(this);
			auto RestoreRejectedRestart = [WeakThis, TickingSession](const FString&)
			{
				auto* Capture = WeakThis.Get();
				if (!Capture || !Capture->bRestartIssued
					|| Capture->SessionId != TickingSession || Capture->Phase != ECatrunCapturePhase::Fading
					|| Capture->bCleaningUp || Capture->bEndingPlay) return;
				Capture->bRestartIssued = false;
				Capture->AbortCapture();
			};
			auto* Restart = UCatrunRestartSubsystem::Get(this);
			if (!Restart || !Restart->RestartLevel(Settings->RestartFadeInTime, RestoreRejectedRestart, true))
				RestoreRejectedRestart(TEXT("Capture restart was not accepted."));
		}
	}
}

void UCatrunCapturePresentationComponent::Cleanup(bool bRestoreTransform)
{
	if (bCleaningUp) return;
	bCleaningUp = true;
	if (auto* Pawn = Cat.Get())
	{
		const FTransform Desired = bRestoreTransform ? OriginalTransform : Pawn->GetActorTransform();
		const bool bPlacedSafely = CatrunRestore::PlaceForCollision(*Pawn, Desired, bCollision, EMovementMode(MovementMode), CustomMode);
		Pawn->SetActorEnableCollision(bCollision && bPlacedSafely);
		if (auto* Character = Cast<ACharacter>(Pawn))
		{
			Character->GetCharacterMovement()->SetMovementMode(bPlacedSafely ? EMovementMode(MovementMode) : MOVE_None, CustomMode);
			CatMeshState.Restore(Character->GetMesh());
		}
	}
	if (Armor.IsValid()) ArmorMeshState.Restore(Armor->GetMesh());
	if (auto* PC = Player.Get())
	{
		if (bOwnInputLock) { PC->SetIgnoreMoveInput(false); PC->SetIgnoreLookInput(false); }
		if (Camera.IsValid() && PC->GetViewTarget() == Camera.Get()) PC->SetViewTarget(PreviousView.IsValid() ? PreviousView.Get() : Cat.Get());
		if (!bRestartIssued && bOwnFade && PC->PlayerCameraManager) PC->PlayerCameraManager->StopCameraFade();
	}
	if (Camera.IsValid()) Camera->Destroy();
	Camera.Reset();
	bOwnInputLock = false;
	bOwnFade = false;
	if (bOwnCatch) if (auto* Restart = UCatrunRestartSubsystem::Get(this)) Restart->CancelCatch(this);
	bOwnCatch = false;
	Cat.Reset();
	Settings = nullptr;
	SetComponentTickEnabled(false);
	bCleaningUp = false;
	SetPhase(ECatrunCapturePhase::Inactive);
}

void UCatrunCapturePresentationComponent::AbortCapture()
{
	// AnimationRequested during owner preparation can cancel before snapshots/phase callbacks exist.
	if (bBeginningCapture && !IsCapturing()) { bAbortPreparation = true; return; }
	if (IsCapturing() && !bCleaningUp)
	{
		if (bRestartIssued)
		{
			if (auto* Restart = UCatrunRestartSubsystem::Get(this)) Restart->CancelCaptureRestart(this);
			bRestartIssued = false;
		}
		Cleanup(true);
	}
}
void UCatrunCapturePresentationComponent::EndPlay(const EEndPlayReason::Type Reason)
{
	bEndingPlay = true;
	if (IsCapturing())
	{
		if (Reason == EEndPlayReason::Destroyed || Reason == EEndPlayReason::RemovedFromWorld) AbortCapture();
		else Cleanup(!bRestartIssued); // successful travel keeps its single-use arrival intent
	}
	Super::EndPlay(Reason);
}
