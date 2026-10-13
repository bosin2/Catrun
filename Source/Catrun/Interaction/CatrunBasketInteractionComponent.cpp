#include "CatrunBasketInteractionComponent.h"
#include "BasketExitMath.h"
#include "CatrunHideBasket.h"
#include "Animation/AnimInstance.h"
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
	PrimaryComponentTick.bStartWithTickEnabled = false;
	static ConstructorHelpers::FObjectFinder<UAnimSequenceBase> Enter(TEXT("/Game/Characters/BlackCat/Final/Animations/AN_BlackCat_BasketEnter"));
	static ConstructorHelpers::FObjectFinder<UAnimSequenceBase> Exit(TEXT("/Game/Systems/Interaction/Hiding/Animations/AN_Cat_BasketExit"));
	EnterAnimation = Enter.Object;
	ExitAnimation = Exit.Object;
}

void UCatrunBasketInteractionComponent::BeginPlay()
{
	Super::BeginPlay();
	CatOwner = Cast<ACharacter>(GetOwner());
	SetComponentTickEnabled(false); // 바깥에서는 틱을 끄고 F 입력 시에만 바구니를 탐색한다.
}

void UCatrunBasketInteractionComponent::EndPlay(const EEndPlayReason::Type Reason)
{
	if (GetWorld()) GetWorld()->GetTimerManager().ClearTimer(AnimationTimer);
	if (IsValid(ActiveBasket)) ActiveBasket->Release(GetOwner());
	if (ExitPreview) ExitPreview->DestroyComponent();
	Super::EndPlay(Reason);
}

void UCatrunBasketInteractionComponent::TryInteract()
{
	if (!IsValid(CatOwner) || Busy) return;
	if (BasketPhase == ECatrunBasketPhase::Hidden)
		ExitBasket();
	else if (BasketPhase == ECatrunBasketPhase::Outside && CatOwner->GetCharacterMovement()->IsMovingOnGround())
		FindAndEnterBasket();
}

void UCatrunBasketInteractionComponent::FindAndEnterBasket()
{
	ACatrunHideBasket* Best = nullptr;
	FVector BestLocation;
	double Nearest = InteractionRange;
	for (TActorIterator<ACatrunHideBasket> It(GetWorld()); It; ++It)
	{
		ACatrunHideBasket* Basket = *It;
		if (Basket->Occupied || !Basket->HasHiddenPoint()) continue;
		const double Distance = FVector::Distance(CatOwner->GetActorLocation(), Basket->GetHiddenLocation());
		if (Distance <= 50. || Distance >= Nearest) continue;
		FVector Location;
		if (TestEntry(Basket, Location))
		{
			Best = Basket;
			BestLocation = Location;
			Nearest = Distance;
		}
	}
	if (Best && Best->TryOccupy(GetOwner())) EnterBasket(Best, BestLocation);
}

bool UCatrunBasketInteractionComponent::TestEntry(ACatrunHideBasket* Basket, FVector& OutLocation) const
{
	const FVector Center = Basket->GetHiddenLocation();
	const FVector From = CatOwner->GetActorLocation();
	const FVector Direction = (From-Center).GetSafeNormal2D();
	if (Direction.IsNearlyZero()) return false;
	OutLocation = Center + Direction*EntryDistance;
	const UCapsuleComponent* Capsule = CatOwner->GetCapsuleComponent();
	FCollisionQueryParams Params(SCENE_QUERY_STAT(BasketEntry), false, CatOwner);
	FHitResult Hit;
	// 기존처럼 고양이가 접근한 방향에서 진입하며, 진입 위치까지 캡슐이 지나갈 공간을 확인한다.
	if (GetWorld()->SweepSingleByChannel(Hit, From, OutLocation, FQuat::Identity, ObstacleChannel,
		FCollisionShape::MakeCapsule(Capsule->GetScaledCapsuleRadius(), Capsule->GetScaledCapsuleHalfHeight()), Params))
		return false;
	if (GetWorld()->LineTraceSingleByChannel(Hit, OutLocation, Center, ObstacleChannel, Params)
		&& Hit.GetActor()!=Basket && Hit.GetActor()!=Basket->ExternalBody)
		return false;
	return GetWorld()->LineTraceSingleByChannel(Hit, OutLocation, OutLocation-FVector(0,0,50), ObstacleChannel, Params)
		&& Hit.ImpactNormal.Z >= .65;
}

void UCatrunBasketInteractionComponent::EnterBasket(ACatrunHideBasket* Basket, const FVector& Location)
{
	ActiveBasket = Basket;
	Busy = true;
	BasketPhase = ECatrunBasketPhase::Entering;
	SetComponentTickEnabled(true);
	USkeletalMeshComponent* Mesh = CatOwner->GetMesh();
	UCharacterMovementComponent* Movement = CatOwner->GetCharacterMovement();
	SavedEntryTransform = CatOwner->GetActorTransform();
	SavedAnimClass = Mesh->GetAnimClass();
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
	CatOwner->SetActorLocationAndRotation(Location, (Basket->GetHiddenLocation()-Location).Rotation(),
		false, nullptr, ETeleportType::TeleportPhysics);
	Basket->ClothEnter();
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
	ExitWorldDirection = ActiveBasket->GetOpenDirection();
	BasketHiddenStateChanged();
	UpdateExitCandidate(true);
	UpdatePreview(); // 추가 키 입력 없이 열린 정면을 기본 방향으로 바로 표시한다.
}

void UCatrunBasketInteractionComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* Tick)
{
	Super::TickComponent(DeltaTime, TickType, Tick);
	if (!IsValid(CatOwner) || !IsValid(ActiveBasket)) { AbortBasket(); return; }
	if (BasketPhase == ECatrunBasketPhase::Hidden)
	{
		UpdateExitCandidate(false);
		UpdatePreview();
	}
}

void UCatrunBasketInteractionComponent::UpdateExitCandidate(bool bForce)
{
	APlayerController* PC = Cast<APlayerController>(CatOwner->GetController());
	const FVector Origin = ActiveBasket->GetHiddenLocation();
	const FVector Forward = ActiveBasket->GetOpenDirection();
	const FVector Previous = ExitWorldDirection;
	const float CameraYaw = PC && PC->PlayerCameraManager
		? PC->PlayerCameraManager->GetCameraRotation().Yaw : Forward.Rotation().Yaw;
	if (PC && PC->PlayerCameraManager)
	{
		auto Down = [PC](const FKey& Key) { return PC->IsInputKeyDown(Key) || PC->WasInputKeyJustPressed(Key); };
		ExitWorldDirection = CatrunBasket::SelectDirection(CameraYaw,
			float(Down(EKeys::W))-float(Down(EKeys::S)), float(Down(EKeys::D))-float(Down(EKeys::A)),
			ExitWorldDirection, Forward);
	}
	if (!CatrunBasket::IsDirectionAllowed(ExitWorldDirection, Forward, CameraYaw)) ExitWorldDirection = Forward;
	const double Now = GetWorld()->GetTimeSeconds();
	// 입력이 없어도 움직이는 장애물을 0.1초마다 확인한다. 방향 변경과 F 확정은 즉시 검사한다.
	if (!bForce && Previous.Equals(ExitWorldDirection,.001) && LastBasketOrigin.Equals(Origin,.1)
		&& LastBasketForward.Equals(Forward,.001) && Now<NextObstacleCheck) return;
	LastBasketOrigin = Origin;
	LastBasketForward = Forward;
	NextObstacleCheck = Now+.1;
	CanExit = false;
	const FVector Candidate = Origin + ExitWorldDirection*ExitDistance;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(BasketExit), false, CatOwner);
	Params.AddIgnoredActor(ActiveBasket);
	if (IsValid(ActiveBasket->ExternalBody)) Params.AddIgnoredActor(ActiveBasket->ExternalBody);
	FHitResult Floor;
	if (!GetWorld()->LineTraceSingleByChannel(Floor, Candidate+FVector(0,0,50), Candidate-FVector(0,0,100),
		ObstacleChannel, Params) || Floor.ImpactNormal.Z<.65) return;
	FloorLocation = Floor.ImpactPoint;
	const UCapsuleComponent* Capsule = CatOwner->GetCapsuleComponent();
	ExitWorldLocation = FloorLocation+FVector(0,0,Capsule->GetScaledCapsuleHalfHeight()+2.);
	CanExit = !GetWorld()->OverlapBlockingTestByChannel(ExitWorldLocation, FQuat::Identity, ObstacleChannel,
		FCollisionShape::MakeCapsule(Capsule->GetScaledCapsuleRadius(), Capsule->GetScaledCapsuleHalfHeight()), Params);
}

void UCatrunBasketInteractionComponent::UpdatePreview()
{
	if (!CanExit)
	{
		if (ExitPreview) ExitPreview->HidePath();
		return;
	}
	if (!ExitPreview)
	{
		ExitPreview = NewObject<UCatrunBasketExitPreview>(CatOwner, NAME_None, RF_Transient);
		ExitPreview->RegisterComponent(); // 숨겨진 고양이 메시와 독립된 월드 좌표로 안내를 그린다.
	}
	ExitPreview->ShowPath(ActiveBasket->GetHiddenLocation()+ExitWorldDirection*8.+FVector(0,0,32),
		FloorLocation+FVector(0,0,3), PreviewStyle);
}

void UCatrunBasketInteractionComponent::ExitBasket()
{
	UpdateExitCandidate(true);
	if (!CanExit) { UpdatePreview(); return; }
	Busy = true;
	BasketPhase = ECatrunBasketPhase::Exiting;
	if (ExitPreview) ExitPreview->HidePath();
	CatOwner->SetActorLocationAndRotation(ExitWorldLocation, ExitWorldDirection.Rotation(),
		false, nullptr, ETeleportType::TeleportPhysics);
	CatOwner->GetMesh()->SetVisibility(true, true);
	ActiveBasket->ClothExit();
	const float Duration = PlayCharacterAnimation(ExitAnimation);
	GetWorld()->GetTimerManager().SetTimer(AnimationTimer, this,
		&UCatrunBasketInteractionComponent::FinishExit, Duration, false);
}

void UCatrunBasketInteractionComponent::RestoreCharacter()
{
	if (!IsValid(CatOwner)) return;
	if (SavedAnimClass) CatOwner->GetMesh()->SetAnimInstanceClass(SavedAnimClass);
	CatOwner->GetMesh()->SetVisibility(bSavedMeshVisible, true);
	CatOwner->SetActorEnableCollision(bSavedCollision);
	CatOwner->bUseControllerRotationYaw = bSavedControllerYaw;
	UCharacterMovementComponent* Movement = CatOwner->GetCharacterMovement();
	Movement->bOrientRotationToMovement = bSavedOrientToMovement;
	Movement->bUseControllerDesiredRotation = bSavedControllerDesiredRotation;
	Movement->SetMovementMode(EMovementMode(SavedMovementMode), SavedCustomMovementMode);
}

void UCatrunBasketInteractionComponent::FinishExit()
{
	if (BasketPhase != ECatrunBasketPhase::Exiting) return;
	RestoreCharacter();
	if (IsValid(ActiveBasket)) ActiveBasket->Release(GetOwner());
	ActiveBasket = nullptr;
	IsHidden = false;
	Busy = false;
	CanExit = false;
	BasketPhase = ECatrunBasketPhase::Outside;
	SetComponentTickEnabled(false);
	BasketHiddenStateChanged();
}

void UCatrunBasketInteractionComponent::AbortBasket()
{
	GetWorld()->GetTimerManager().ClearTimer(AnimationTimer);
	if (BasketPhase != ECatrunBasketPhase::Outside && IsValid(CatOwner))
	{
		CatOwner->SetActorTransform(SavedEntryTransform, false, nullptr, ETeleportType::TeleportPhysics);
		RestoreCharacter();
	}
	if (IsValid(ActiveBasket)) ActiveBasket->Release(GetOwner());
	if (ExitPreview) ExitPreview->HidePath();
	ActiveBasket = nullptr;
	IsHidden = false;
	Busy = false;
	CanExit = false;
	BasketPhase = ECatrunBasketPhase::Outside;
	SetComponentTickEnabled(false);
	BasketHiddenStateChanged();
}
