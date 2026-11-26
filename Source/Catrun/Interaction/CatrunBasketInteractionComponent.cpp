#include "CatrunBasketInteractionComponent.h"
#include "Settings/CatrunInputBindings.h"
#include "UI/CatrunBasketPromptWidget.h"
#include "CatrunPuzzleSuspension.h"
#include "BasketExitMath.h"
#include "Perception/CatrunSafeRestore.h"
#include "Perception/CatrunGroundSupport.h"
#include "CatrunHideBasket.h"
#include "Sound/CatrunBellComponent.h"
#include "Sound/CatrunNoBellZone.h"
#include "Sound/CatrunNotice.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "Monster/CatrunRestartSubsystem.h"
#include "Animation/AnimSequenceBase.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "TimerManager.h"
#include "UObject/ConstructorHelpers.h"

UCatrunBasketInteractionComponent::UCatrunBasketInteractionComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.bStartWithTickEnabled = true;
	PrimaryComponentTick.bTickEvenWhenPaused = true;
	PrimaryComponentTick.TickInterval = .15f;
	static ConstructorHelpers::FObjectFinder<UAnimSequenceBase> Enter(TEXT("/Game/Characters/BlackCat/Final/Animations/AN_BlackCat_BasketEnter"));
	static ConstructorHelpers::FObjectFinder<UAnimSequenceBase> Exit(TEXT("/Game/Systems/Interaction/Hiding/Animations/AN_Cat_BasketExit"));
	EnterAnimation = Enter.Object;
	ExitAnimation = Exit.Object;
}

void UCatrunBasketInteractionComponent::BeginPlay()
{
	Super::BeginPlay();
	CatOwner = Cast<ACharacter>(GetOwner());
	for (TActorIterator<ACatrunHideBasket> It(GetWorld()); It; ++It) TrackBasket(*It);
	BasketSpawnHandle = GetWorld()->AddOnActorSpawnedHandler(FOnActorSpawned::FDelegate::CreateUObject(this, &UCatrunBasketInteractionComponent::TrackBasket));
	SetComponentTickEnabled(true); // Outside queries are throttled; hidden directional input still updates each frame.
}

void UCatrunBasketInteractionComponent::EndPlay(const EEndPlayReason::Type Reason)
{
	CancelBellAction();
	if (BasketPhase != ECatrunBasketPhase::Outside && IsValid(CatOwner) && !CatOwner->IsActorBeingDestroyed()) AbortBasket();
	if (GetWorld()) GetWorld()->GetTimerManager().ClearTimer(AnimationTimer);
	if (IsValid(ActiveBasket)) ActiveBasket->Release(GetOwner());
	if (ExitPreview) ExitPreview->DestroyComponent();
	if (BasketPromptWidget) BasketPromptWidget->RemoveFromParent();
	if (GetWorld()) GetWorld()->RemoveOnActorSpawnedHandler(BasketSpawnHandle);
	NearbyBaskets.Reset();
	Super::EndPlay(Reason);
}

void UCatrunBasketInteractionComponent::TrackBasket(AActor* Actor)
{
	if (ACatrunHideBasket* Basket = Cast<ACatrunHideBasket>(Actor)) NearbyBaskets.AddUnique(Basket);
}

bool UCatrunBasketInteractionComponent::BeginBellAction(float EmitDelay, float Duration)
{
	if (!IsValid(CatOwner) || !GetWorld() || GetWorld()->bIsTearingDown || Busy || IsHidden || bBellActive
		|| BasketPhase != ECatrunBasketPhase::Outside || !CatOwner->GetCharacterMovement()->IsMovingOnGround()
		|| UCatrunBellComponent::IsBellActionContextBlocked(CatOwner)) return false;
	if (ACatrunNoBellZone::IsBellForbidden(*CatOwner)) { UCatrunNoticeLibrary::ShowBellDenied(this,2.f); return false; }
	auto* Mesh = CatOwner->GetMesh();
	auto* Move = CatOwner->GetCharacterMovement();
	BellSavedMovementMode = Move->MovementMode;
	BellSavedCustomMode = Move->CustomMovementMode;
	BellSavedAnimMode = Mesh->GetAnimationMode();
	BellSavedAnimClass = Mesh->GetAnimClass();
	BellSavedAnimation = Mesh->AnimationData;
	if (auto* Single = Mesh->GetSingleNodeInstance())
	{
		BellSavedAnimation.AnimToPlay = Single->GetCurrentAsset();
		BellSavedAnimation.SavedPosition = Single->GetCurrentTime();
		BellSavedAnimation.SavedPlayRate = Single->GetPlayRate();
		BellSavedAnimation.bSavedLooping = Single->IsLooping();
		BellSavedAnimation.bSavedPlaying = Single->IsPlaying();
	}
	Busy = bBellActive = true;
	HideInteractionPrompt();
	bBellEmitted = false;
	const int32 Session = ++BellSessionId;
	Move->StopMovementImmediately();
	Move->DisableMovement();
	// Weak, session-bound callbacks never read a later action's token. Clear only these handles.
	const float End = FMath::Clamp(Duration,.02f,30.f);
	GetWorld()->GetTimerManager().SetTimer(BellEmitTimer,FTimerDelegate::CreateWeakLambda(this,[this,Session]{EmitBellAction(Session);}),FMath::Clamp(EmitDelay,.001f,End-.001f),false);
	GetWorld()->GetTimerManager().SetTimer(BellFinishTimer,FTimerDelegate::CreateWeakLambda(this,[this,Session]{FinishBellAction(Session);}),End,false);
	return true;
}

void UCatrunBasketInteractionComponent::EmitBellAction(int32 ExpectedSession)
{
	if (!bBellActive || bBellEmitted || ExpectedSession != BellSessionId) return;
	bBellEmitted = true;
	// The sound component rechecks no-bell zones at the actual emission position.
	if (!UCatrunPuzzleSuspension::IsSuspended(this)) BellEmissionReady();
}

void UCatrunBasketInteractionComponent::FinishBellAction(int32 ExpectedSession)
{
	if (bBellActive && ExpectedSession == BellSessionId) CancelBellAction();
}

void UCatrunBasketInteractionComponent::CancelBellAction()
{
	if (!bBellActive) return;
	bBellActive = false;
	++BellSessionId; // invalidate before restoring animation, which can invoke callbacks
	if (GetWorld())
	{
		GetWorld()->GetTimerManager().ClearTimer(BellEmitTimer);
		GetWorld()->GetTimerManager().ClearTimer(BellFinishTimer);
	}
	if (IsValid(CatOwner) && !CatOwner->IsActorBeingDestroyed())
	{
		auto* Mesh = CatOwner->GetMesh();
		Mesh->SetAnimInstanceClass(BellSavedAnimClass);
		Mesh->AnimationData = BellSavedAnimation;
		Mesh->SetAnimationMode(BellSavedAnimMode,true);
		if (BellSavedAnimMode == EAnimationMode::AnimationSingleNode)
		{
			Mesh->PlayAnimation(BellSavedAnimation.AnimToPlay,BellSavedAnimation.bSavedLooping);
			Mesh->SetPosition(BellSavedAnimation.SavedPosition,false);
			Mesh->SetPlayRate(BellSavedAnimation.SavedPlayRate);
			if (!BellSavedAnimation.bSavedPlaying) Mesh->Stop();
		}
		CatOwner->GetCharacterMovement()->SetMovementMode(static_cast<EMovementMode>(BellSavedMovementMode),BellSavedCustomMode);
	}
	Busy = false;
}

void UCatrunBasketInteractionComponent::TryInteract()
{
	if (!IsInteractionAvailable()) return;
	if (BasketPhase == ECatrunBasketPhase::Hidden)
		ExitBasket();
	else if (BasketPhase == ECatrunBasketPhase::Outside && CatOwner->GetCharacterMovement()->IsMovingOnGround())
	{
		FindAndEnterBasket();
	}
}

void UCatrunBasketInteractionComponent::FindAndEnterBasket()
{
	ACatrunHideBasket* Best = nullptr;
	FVector BestLocation;
	if (FindEntryCandidate(Best,BestLocation) && Best->TryOccupy(GetOwner())) EnterBasket(Best,BestLocation);
}

bool UCatrunBasketInteractionComponent::IsInteractionAvailable() const
{
	if (!IsValid(CatOwner) || !GetWorld() || GetWorld()->bIsTearingDown || GetWorld()->IsPaused()
		|| Busy || UCatrunPuzzleSuspension::IsSuspended(this)) return false;
	if (const auto* PC=Cast<APlayerController>(CatOwner->GetController()); PC && (PC->IsMoveInputIgnored() || PC->IsLookInputIgnored())) return false;
	if (const auto* Restart=UCatrunRestartSubsystem::Get(this); Restart && Restart->IsCatching()) return false;
	if (const auto* Flow=UCatrunLevelFlowSubsystem::Get(this); Flow && (Flow->IsTransitioning() || Flow->IsStageComplete())) return false;
	return true;
}

bool UCatrunBasketInteractionComponent::CanEnterNearbyBasket() const
{
	ACatrunHideBasket* Basket = nullptr;
	FVector Entry;
	return FindEntryCandidate(Basket,Entry);
}

bool UCatrunBasketInteractionComponent::FindEntryCandidate(ACatrunHideBasket*& OutBasket, FVector& OutLocation) const
{
	OutBasket=nullptr;
	if (!IsInteractionAvailable() || IsHidden || BasketPhase!=ECatrunBasketPhase::Outside
		|| !CatOwner->GetCharacterMovement()->IsMovingOnGround()) return false;
	double NearestSquared = FMath::Square(InteractionRange);
	for (const auto& WeakBasket : NearbyBaskets)
	{
		ACatrunHideBasket* Basket = WeakBasket.Get();
		if (!IsValid(Basket) || Basket->Occupied || !Basket->HasHiddenPoint()) continue;
		const double DistanceSquared = FVector::DistSquared(CatOwner->GetActorLocation(), Basket->GetHiddenLocation());
		if (DistanceSquared < NearestSquared)
		{
			OutBasket = Basket;
			NearestSquared = DistanceSquared;
		}
	}
	// Broad phase is cached actor positions only; one physical candidate per query.
	return OutBasket && TestEntry(OutBasket, OutLocation);
}

void UCatrunBasketInteractionComponent::HideInteractionPrompt()
{
	if (BasketPromptWidget) BasketPromptWidget->SetPromptActive(false);
}

void UCatrunBasketInteractionComponent::UpdateInteractionPrompt()
{
	if (!IsInteractionAvailable() || IsHidden || BasketPhase!=ECatrunBasketPhase::Outside
		|| !CatOwner->GetCharacterMovement()->IsMovingOnGround()) { HideInteractionPrompt(); return; }
	auto* PC=Cast<APlayerController>(CatOwner->GetController());
	if (!PC || !PC->IsLocalController() || !BasketPromptWidgetClass) { HideInteractionPrompt(); return; }
	const bool bShow=CanEnterNearbyBasket();
	if (bShow && !BasketPromptWidget)
	{
		BasketPromptWidget=CreateWidget<UCatrunBasketPromptWidget>(PC,BasketPromptWidgetClass);
		if (BasketPromptWidget) BasketPromptWidget->AddToPlayerScreen(20);
	}
	if (BasketPromptWidget) BasketPromptWidget->SetPromptActive(bShow);
}

bool UCatrunBasketInteractionComponent::TestEntry(ACatrunHideBasket* Basket, FVector& OutLocation) const
{
	const FVector Center = Basket->GetHiddenLocation();
	const FVector From = CatOwner->GetActorLocation();
	const FVector Direction = (From-Center).GetSafeNormal2D();
	if (Direction.IsNearlyZero()) return false;
	OutLocation = Center + Direction*Basket->GetTraversalDistance(Direction, EntryDistance);
	const UCapsuleComponent* Capsule = CatOwner->GetCapsuleComponent();
	FCollisionQueryParams Params(SCENE_QUERY_STAT(BasketEntry), false, CatOwner);
	FHitResult Hit;
	FVector Supported;
	// Ground this exact approach point before testing the complete path to it.
	const FVector SurfaceReference = OutLocation;
	if (!CatrunGround::FindSupport(*Capsule, SurfaceReference+FVector(0,0,Capsule->GetScaledCapsuleHalfHeight()),
		0.f, 50.f, Params, Hit, Supported)
		|| Hit.ImpactPoint.Z > SurfaceReference.Z+.01f || Hit.ImpactPoint.Z < SurfaceReference.Z-50.f-.01f) return false;
	OutLocation = Supported;
	// Preserve approach direction without requiring the cat to face the basket.
	const FCollisionResponseParams Responses(Capsule->GetCollisionResponseToChannels());
	if (GetWorld()->SweepSingleByChannel(Hit, From, OutLocation, Capsule->GetComponentQuat(),
		Capsule->GetCollisionObjectType(), Capsule->GetCollisionShape(), Params, Responses))
		return false;
	if (GetWorld()->OverlapBlockingTestByChannel(OutLocation,Capsule->GetComponentQuat(),
		Capsule->GetCollisionObjectType(),Capsule->GetCollisionShape(),Params,Responses)) return false;
	// Only the deliberate jump may pass this basket's shell. The
	// approach and staging capsule above still collide with it normally.
	Params.AddIgnoredActor(Basket);
	if (IsValid(Basket->ExternalBody)) Params.AddIgnoredActor(Basket->ExternalBody);
	const FVector InnerCenter(Center.X,Center.Y,OutLocation.Z);
	if (GetWorld()->SweepSingleByChannel(Hit,OutLocation,InnerCenter,Capsule->GetComponentQuat(),
		Capsule->GetCollisionObjectType(),Capsule->GetCollisionShape(),Params,Responses)) return false;
	if (GetWorld()->LineTraceSingleByChannel(Hit, OutLocation, Center, ObstacleChannel, Params))
		return false;
	return true;
}

void UCatrunBasketInteractionComponent::EnterBasket(ACatrunHideBasket* Basket, const FVector& Location)
{
	ActiveBasket = Basket;
	Busy = true;
	HideInteractionPrompt();
	BasketPhase = ECatrunBasketPhase::Entering;
	SetComponentTickInterval(0.f);
	SetComponentTickEnabled(true);
	USkeletalMeshComponent* Mesh = CatOwner->GetMesh();
	UCharacterMovementComponent* Movement = CatOwner->GetCharacterMovement();
	SavedEntryTransform = CatOwner->GetActorTransform();
	SavedAnimClass = Mesh->GetAnimClass();
	SavedAnimMode = Mesh->GetAnimationMode();
	SavedAnimation = Mesh->AnimationData;
	if (auto* Single = Mesh->GetSingleNodeInstance())
	{
		SavedAnimation.AnimToPlay = Single->GetCurrentAsset();
		SavedAnimation.SavedPosition = Single->GetCurrentTime();
		SavedAnimation.SavedPlayRate = Single->GetPlayRate();
		SavedAnimation.bSavedLooping = Single->IsLooping();
		SavedAnimation.bSavedPlaying = Single->IsPlaying();
	}
	SavedMovementMode = Movement->MovementMode;
	SavedCustomMovementMode = Movement->CustomMovementMode;
	bSavedCollision = CatOwner->GetActorEnableCollision();
	bSavedMeshVisible = Mesh->IsVisible();
	bSavedControllerYaw = CatOwner->bUseControllerRotationYaw;
	bSavedOrientToMovement = Movement->bOrientRotationToMovement;
	bSavedControllerDesiredRotation = Movement->bUseControllerDesiredRotation;
	CatOwner->bUseControllerRotationYaw = false;
	Movement->bOrientRotationToMovement = false;
	Movement->bUseControllerDesiredRotation = false;
	Movement->StopMovementImmediately();
	Movement->DisableMovement();
	CatOwner->SetActorEnableCollision(false);
	// Hidden anchors and supported entries may have different heights. Keep the
	// gameplay capsule upright; vertical animation belongs to the mesh pose.
	const FVector EntryHeading=(Basket->GetHiddenLocation()-Location).GetSafeNormal2D();
	const FRotator EntryRotation(0.f,EntryHeading.IsNearlyZero() ? CatOwner->GetActorRotation().Yaw : EntryHeading.Rotation().Yaw,0.f);
	CatOwner->SetActorLocationAndRotation(Location, EntryRotation,
		false, nullptr, ETeleportType::TeleportPhysics);
	Basket->PlayDirectionalCloth(true, Location-Basket->GetHiddenLocation(), AnimationPlayRate);
	const float Duration = PlayCharacterAnimation(EnterAnimation);
	GetWorld()->GetTimerManager().SetTimer(AnimationTimer, this,
		&UCatrunBasketInteractionComponent::FinishEnter, Duration, false);
}

float UCatrunBasketInteractionComponent::PlayCharacterAnimation(UAnimSequenceBase* Animation)
{
	const float Rate = FMath::Max(AnimationPlayRate, .01f);
	if (Animation)
	{
		CatOwner->GetMesh()->PlayAnimation(Animation, false);
		CatOwner->GetMesh()->SetPlayRate(Rate);
		return FMath::Max(Animation->GetPlayLength()/Rate, .01f);
	}
	return .01f;
}

void UCatrunBasketInteractionComponent::FinishEnter()
{
	if (BasketPhase != ECatrunBasketPhase::Entering) return;
	if (!IsValid(CatOwner) || !IsValid(ActiveBasket)) { AbortBasket(); return; }
	CatOwner->GetMesh()->SetVisibility(false, true);
	CatOwner->SetActorLocation(ActiveBasket->GetHiddenLocation(), false, nullptr, ETeleportType::TeleportPhysics);
	IsHidden = true;
	Busy = false;
	BasketPhase = ECatrunBasketPhase::Hidden;
	ActiveBasket->ClothIdle();
	ExitWorldDirection = FVector::ZeroVector; // No automatic exit selection.
	BasketHiddenStateChanged();
	UpdateExitCandidate(true);
	UpdatePreview();
}

void UCatrunBasketInteractionComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* Tick)
{
	Super::TickComponent(DeltaTime, TickType, Tick);
	if (BasketPhase==ECatrunBasketPhase::Outside) UpdateInteractionPrompt();
	if (UCatrunPuzzleSuspension::IsSuspended(this) || GetWorld()->IsPaused() || BasketPhase==ECatrunBasketPhase::Outside) return;
	if (!IsValid(CatOwner) || !IsValid(ActiveBasket)) { AbortBasket(); return; }
	if (BasketPhase == ECatrunBasketPhase::Hidden)
	{
		if (UpdateExitCandidate(false)) UpdatePreview();
	}
}

bool UCatrunBasketInteractionComponent::GetExitCameraRotation(FRotator& OutRotation) const
{
	const auto* PC=IsValid(CatOwner) ? Cast<APlayerController>(CatOwner->GetController()) : nullptr;
	if (!PC || !PC->PlayerCameraManager) return false;
	OutRotation=PC->PlayerCameraManager->GetCameraRotation();
	return true;
}

bool UCatrunBasketInteractionComponent::IsExitInputAvailable(const FVector2D& Input) const
{
	const int32 Slot=CatrunBasket::ExitOptionSlot(Input);
	return Slot!=INDEX_NONE && (AvailableExitMask & (1u<<Slot))!=0;
}

bool UCatrunBasketInteractionComponent::ReadExitDirectionInput()
{
	const auto* PC=Cast<APlayerController>(CatOwner->GetController());
	if (!PC || !PC->PlayerCameraManager) return false;
	const FVector2D Input=UCatrunInputBindings::GetMovementInput([PC](FKey Key)
	{
		return PC->IsInputKeyDown(Key) || PC->WasInputKeyJustPressed(Key);
	});
	if (Input.IsNearlyZero()) return false; // Release keeps the last deliberate direction.
	// A blocked option is not selectable: the key does nothing until that option opens.
	if (!IsExitInputAvailable(Input)) return false;
	const FVector Direction=CatrunBasket::MovementDirection(Input,PC->PlayerCameraManager->GetCameraRotation());
	if (Direction.IsNearlyZero() || Direction.Equals(ExitWorldDirection,.001)) return false;
	ExitWorldDirection=Direction;
	return true;
}

bool UCatrunBasketInteractionComponent::EvaluateExitFrom(const FVector& SupportedOrigin, const FVector& Direction, FVector& OutLanding) const
{
	OutLanding=FVector::ZeroVector;
	if (!IsValid(CatOwner) || !IsValid(ActiveBasket) || Direction.GetSafeNormal2D().IsNearlyZero()) return false;
	const FVector Candidate=ActiveBasket->GetHiddenLocation()+Direction*ActiveBasket->GetTraversalDistance(Direction, ExitDistance);
	if (!FindExitSupport(Candidate, OutLanding)) return false;
	FTransform LandingTransform=CatOwner->GetActorTransform();
	LandingTransform.SetLocation(OutLanding);
	LandingTransform.SetRotation(Direction.Rotation().Quaternion());
	// Same three checks FinishExit repeats at landing time.
	return IsExitPathClear(SupportedOrigin, OutLanding)
		&& (!bSavedCollision || CatrunRestore::IsPlacementClear(*CatOwner, LandingTransform));
}

bool UCatrunBasketInteractionComponent::EvaluateExitDirection(const FVector& Direction, FVector& OutLanding) const
{
	OutLanding=FVector::ZeroVector;
	FVector SupportedOrigin;
	// Equivalent to IsBasketExitPathClear: ground the hidden origin, then test the transit.
	return IsValid(CatOwner) && IsValid(ActiveBasket)
		&& FindExitSupport(ActiveBasket->GetHiddenLocation(), SupportedOrigin)
		&& EvaluateExitFrom(SupportedOrigin, Direction, OutLanding);
}

void UCatrunBasketInteractionComponent::RefreshExitOptions()
{
	AvailableExitMask=0;
	FRotator Camera;
	if (!IsValid(CatOwner) || !IsValid(ActiveBasket) || !GetExitCameraRotation(Camera)) return;
	LastExitCameraRotation=Camera;
	FVector SupportedOrigin;
	if (!FindExitSupport(ActiveBasket->GetHiddenLocation(), SupportedOrigin)) return;
	for (int32 Slot=0; Slot<CatrunBasket::ExitOptionCount; ++Slot)
	{
		FVector Landing;
		const FVector Direction=CatrunBasket::MovementDirection(CatrunBasket::ExitOptionInput(Slot),Camera);
		if (EvaluateExitFrom(SupportedOrigin, Direction, Landing)) AvailableExitMask=static_cast<uint8>(AvailableExitMask | (1u<<Slot));
	}
}

bool UCatrunBasketInteractionComponent::UpdateExitCandidate(bool bForce, bool bReadDirectionInput)
{
	const FVector Origin = ActiveBasket->GetHiddenLocation();
	const FVector Forward = ActiveBasket->GetTraversalForward();
	const double Now = GetWorld()->GetTimeSeconds();
	FRotator Camera;
	const bool bCameraMoved = GetExitCameraRotation(Camera)
		&& FMath::Abs(FRotator::NormalizeAxis(Camera.Yaw-LastExitCameraRotation.Yaw)) > .1;
	// Only the occupied basket is checked. Its eight options are refreshed on demand
	// (enter/F/camera/basket move) and at 5Hz for dynamic blockers such as patrolling armor.
	const bool bRefresh = bForce || bCameraMoved || !LastBasketOrigin.Equals(Origin,.1)
		|| !LastBasketForward.Equals(Forward,.001) || Now>=NextObstacleCheck;
	const uint8 PreviousMask = AvailableExitMask;
	if (bRefresh)
	{
		LastBasketOrigin = Origin;
		LastBasketForward = Forward;
		NextObstacleCheck = Now+.2;
		RefreshExitOptions();
	}
	// Input is read after the refresh so a key can never select an option that was just closed.
	const bool bSelectionChanged = bReadDirectionInput && ReadExitDirectionInput();
	if (!bRefresh && !bSelectionChanged) return false;
	const bool bPreviousCanExit = CanExit;
	const FVector PreviousLanding = ExitWorldLocation;
	CanExit = false;
	bHasExitSupport = false;
	if (!ExitWorldDirection.IsNearlyZero())
	{
		// The remembered choice is re-tested with the exact confirmation test. When blocked it is
		// hidden (never drawn red) and stays remembered so it reappears once the blocker leaves.
		FVector Landing;
		CanExit = EvaluateExitDirection(ExitWorldDirection, Landing);
		if (CanExit)
		{
			ExitWorldLocation = Landing;
			bHasExitSupport = true;
			// Keep the guide centered on the selected landing, not the off-center capsule contact.
			const UCapsuleComponent* Capsule = CatOwner->GetCapsuleComponent();
			FloorLocation = ExitWorldLocation - FVector(0,0,Capsule->GetScaledCapsuleHalfHeight()+2.f);
		}
	}
	// Report a change only when something the player sees can differ.
	return bForce || bSelectionChanged || PreviousMask!=AvailableExitMask || bPreviousCanExit!=CanExit
		|| (CanExit && !PreviousLanding.Equals(ExitWorldLocation,.1));
}

bool UCatrunBasketInteractionComponent::FindExitSupport(const FVector& Reference, FVector& OutCenter) const
{
	constexpr float ProbeUp = 50.f, ProbeDown = 100.f;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(BasketExitSupport), false, CatOwner);
	Params.AddIgnoredActor(ActiveBasket);
	if (IsValid(ActiveBasket->ExternalBody)) Params.AddIgnoredActor(ActiveBasket->ExternalBody);
	FHitResult Floor;
	const auto* Capsule = CatOwner->GetCapsuleComponent();
	return CatrunGround::FindSupport(*Capsule, Reference+FVector(0,0,Capsule->GetScaledCapsuleHalfHeight()),
		ProbeUp, ProbeDown, Params, Floor, OutCenter)
		&& Floor.ImpactPoint.Z <= Reference.Z+ProbeUp+.01f && Floor.ImpactPoint.Z >= Reference.Z-ProbeDown-.01f;
}

bool UCatrunBasketInteractionComponent::IsBasketExitPathClear(const FVector& Destination) const
{
	if (!IsValid(CatOwner) || !IsValid(ActiveBasket) || !GetWorld()) return false;
	FVector SupportedOrigin;
	if (!FindExitSupport(ActiveBasket->GetHiddenLocation(), SupportedOrigin)) return false;
	// HiddenPoint may be authored on the floor. Ground the actual start instead of lifting the
	// entire transit to a raised destination (which could pass above an intervening blocker's side).
	return IsExitPathClear(SupportedOrigin, Destination);
}

bool UCatrunBasketInteractionComponent::IsExitPathClear(const FVector& Origin, const FVector& Destination) const
{
	if (!IsValid(CatOwner) || !GetWorld()) return false;
	const auto* Capsule = CatOwner->GetCapsuleComponent();
	FCollisionQueryParams Params(SCENE_QUERY_STAT(BasketExitTransit), false, CatOwner);
	if (IsValid(ActiveBasket))
	{
		Params.AddIgnoredActor(ActiveBasket);
		if (IsValid(ActiveBasket->ExternalBody)) Params.AddIgnoredActor(ActiveBasket->ExternalBody);
	}
	const auto Shape = Capsule->GetCollisionShape();
	const FQuat Rotation = Capsule->GetComponentQuat();
	const ECollisionChannel Channel = Capsule->GetCollisionObjectType();
	const FCollisionResponseParams Responses(Capsule->GetCollisionResponseToChannels());
	FHitResult Hit;
	return !GetWorld()->OverlapBlockingTestByChannel(Destination, Rotation, Channel, Shape, Params, Responses)
		&& !GetWorld()->SweepSingleByChannel(Hit, Origin, Destination, Rotation, Channel, Shape, Params, Responses);
}

void UCatrunBasketInteractionComponent::UpdatePreview()
{
	if (!BasketPromptWidget && BasketPromptWidgetClass)
	{
		if (auto* PC=Cast<APlayerController>(CatOwner->GetController());PC && PC->IsLocalController())
		{
			BasketPromptWidget=CreateWidget<UCatrunBasketPromptWidget>(PC,BasketPromptWidgetClass);
			if (BasketPromptWidget) BasketPromptWidget->AddToPlayerScreen(20);
		}
	}
	if (BasketPromptWidget) BasketPromptWidget->SetPromptActive(BasketPhase==ECatrunBasketPhase::Hidden);
	// Only an exit that passes the confirmation test is drawn. Blocked choices get no guide at all.
	if (BasketPhase!=ECatrunBasketPhase::Hidden || !CanExit || !bHasExitSupport || ExitWorldDirection.IsNearlyZero())
	{
		if (ExitPreview) ExitPreview->HidePath();
		return;
	}
	if (!ExitPreview)
	{
		ExitPreview = NewObject<UCatrunBasketExitPreview>(CatOwner, NAME_None, RF_Transient);
		ExitPreview->RegisterComponent(); // 숨겨진 고양이 메시와 독립된 월드 좌표로 안내를 그린다.
	}
	ExitPreview->ShowPath(ActiveBasket->GetHiddenLocation()+ExitWorldDirection*8.+FVector(0,0,32),FloorLocation+FVector(0,0,3),PreviewStyle);
}

void UCatrunBasketInteractionComponent::ExitBasket()
{
	// Input may arrive after the basket was removed, before this component's tick.
	if (!IsValid(CatOwner) || !IsValid(ActiveBasket)) { AbortBasket(); return; }
	UpdateExitCandidate(true);
	if (!CanExit) { UpdatePreview(); return; }
	Busy = true;
	HideInteractionPrompt();
	BasketPhase = ECatrunBasketPhase::Exiting;
	if (ExitPreview) ExitPreview->HidePath();
	CatOwner->SetActorLocationAndRotation(ExitWorldLocation, ExitWorldDirection.Rotation(),
		false, nullptr, ETeleportType::TeleportPhysics);
	CatOwner->GetMesh()->SetVisibility(true, true);
	ActiveBasket->PlayDirectionalCloth(false, ExitWorldDirection, AnimationPlayRate);
	const float Duration = PlayCharacterAnimation(ExitAnimation);
	GetWorld()->GetTimerManager().SetTimer(AnimationTimer, this,
		&UCatrunBasketInteractionComponent::FinishExit, Duration, false);
}

void UCatrunBasketInteractionComponent::RestoreCharacter(bool bPlacedSafely)
{
	if (!IsValid(CatOwner)) return;
	auto* Mesh = CatOwner->GetMesh();
	Mesh->SetAnimInstanceClass(SavedAnimClass);
	Mesh->AnimationData = SavedAnimation;
	Mesh->SetAnimationMode(SavedAnimMode, true);
	if (SavedAnimMode == EAnimationMode::AnimationSingleNode)
	{
		Mesh->PlayAnimation(SavedAnimation.AnimToPlay, SavedAnimation.bSavedLooping);
		Mesh->SetPosition(SavedAnimation.SavedPosition, false);
		Mesh->SetPlayRate(SavedAnimation.SavedPlayRate);
		if (!SavedAnimation.bSavedPlaying) Mesh->Stop();
	}
	CatOwner->GetMesh()->SetVisibility(bSavedMeshVisible, true);
	CatOwner->SetActorEnableCollision(bSavedCollision && bPlacedSafely);
	CatOwner->bUseControllerRotationYaw = bSavedControllerYaw;
	UCharacterMovementComponent* Movement = CatOwner->GetCharacterMovement();
	Movement->bOrientRotationToMovement = bSavedOrientToMovement;
	Movement->bUseControllerDesiredRotation = bSavedControllerDesiredRotation;
	Movement->SetMovementMode(bPlacedSafely ? EMovementMode(SavedMovementMode) : MOVE_None, SavedCustomMovementMode);
}

void UCatrunBasketInteractionComponent::FinishExit()
{
	if (BasketPhase != ECatrunBasketPhase::Exiting) return;
	if (!IsValid(CatOwner) || !IsValid(ActiveBasket)) { AbortBasket(); return; }
	// Confirmation freezes the landing and the basket height used to bound its support query.
	const FVector Landing = ExitWorldLocation;
	const FVector Reference(Landing.X, Landing.Y, LastBasketOrigin.Z);
	FVector SupportedLanding;
	if (!CatOwner->GetActorLocation().Equals(Landing,.01)
		|| !FindExitSupport(Reference, SupportedLanding) || !SupportedLanding.Equals(Landing,.01)
		|| !IsBasketExitPathClear(Landing)
		|| (bSavedCollision && !CatrunRestore::IsPlacementClear(*CatOwner, CatOwner->GetActorTransform())))
	{
		// A late support or collision change keeps us hidden at the same basket.
		CatOwner->SetActorLocation(ActiveBasket->GetHiddenLocation(), false, nullptr, ETeleportType::TeleportPhysics);
		CatOwner->GetMesh()->SetVisibility(false, true);
		BasketPhase = ECatrunBasketPhase::Hidden;
		Busy = false;
		IsHidden = true;
		ActiveBasket->ClothIdle();
		UpdateExitCandidate(true, false);
		UpdatePreview();
		BasketHiddenStateChanged();
		return;
	}
	RestoreCharacter(true);
	if (IsValid(ActiveBasket)) ActiveBasket->Release(GetOwner());
	ActiveBasket = nullptr;
	IsHidden = false;
	Busy = false;
	CanExit = false;
	bHasExitSupport = false;
	AvailableExitMask = 0;
	BasketPhase = ECatrunBasketPhase::Outside;
	SetComponentTickInterval(.15f);
	SetComponentTickEnabled(true);
	BasketHiddenStateChanged();
}

void UCatrunBasketInteractionComponent::AbortBasket()
{
	GetWorld()->GetTimerManager().ClearTimer(AnimationTimer);
	if (BasketPhase != ECatrunBasketPhase::Outside && IsValid(CatOwner))
	{
		const bool bPlacedSafely = CatrunRestore::PlaceForCollision(*CatOwner, SavedEntryTransform, bSavedCollision,
			EMovementMode(SavedMovementMode), SavedCustomMovementMode);
		RestoreCharacter(bPlacedSafely);
	}
	if (IsValid(ActiveBasket)) ActiveBasket->Release(GetOwner());
	if (ExitPreview) ExitPreview->HidePath();
	ActiveBasket = nullptr;
	IsHidden = false;
	Busy = false;
	CanExit = false;
	bHasExitSupport = false;
	AvailableExitMask = 0;
	BasketPhase = ECatrunBasketPhase::Outside;
	SetComponentTickInterval(.15f);
	SetComponentTickEnabled(true);
	BasketHiddenStateChanged();
}
