#include "CatrunHideBasket.h"
#include "Animation/AnimationAsset.h"
#include "BasketExitMath.h"
#include "Components/ArrowComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "TimerManager.h"
#include "UObject/ConstructorHelpers.h"

ACatrunHideBasket::ACatrunHideBasket()
{
	PrimaryActorTick.bCanEverTick = false;
	static ConstructorHelpers::FObjectFinder<UAnimationAsset> Enter(TEXT("/Game/Environment/Shared/Castle/Props/Hiding/HideBasket/Animations/AN_HideBasket_Cloth_Enter"));
	static ConstructorHelpers::FObjectFinder<UAnimationAsset> Exit(TEXT("/Game/Environment/Shared/Castle/Props/Hiding/HideBasket/Animations/AN_HideBasket_Cloth_Exit"));
	static ConstructorHelpers::FObjectFinder<UAnimationAsset> Idle(TEXT("/Game/Environment/Shared/Castle/Props/Hiding/HideBasket/Animations/AN_HideBasket_Cloth_Idle"));
	ClothEnterAnimation = Enter.Object;
	ClothExitAnimation = Exit.Object;
	ClothIdleAnimation = Idle.Object;
}

void ACatrunHideBasket::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
#if WITH_EDITOR
	RefreshDirectionGuide();
#endif
}

void ACatrunHideBasket::PostRegisterAllComponents()
{
	Super::PostRegisterAllComponents();
#if WITH_EDITOR
	// 맵을 다시 열어 저장된 컴포넌트를 불러올 때도 안내 방향을 갱신한다.
	RefreshDirectionGuide();
#endif
}

#if WITH_EDITOR
void ACatrunHideBasket::RefreshDirectionGuide()
{
	// Legacy hinge guide is only meaningful for the old single-opening presentation.
	TInlineComponentArray<UArrowComponent*> Arrows(this);
	for (UArrowComponent* Arrow : Arrows)
	{
		if (Arrow->GetFName() == TEXT("ExitDirectionGuide"))
		{
			const FVector Direction = GetOpenDirection();
			Arrow->SetVisibility(ClothEnterDirections.Num()!=8 && !Direction.IsNearlyZero());
			Arrow->SetWorldRotation(Direction.Rotation());
		}
	}
}
#endif

void ACatrunHideBasket::PostInitializeComponents()
{
	Super::PostInitializeComponents();
	// BP의 메시와 위치 편집은 유지하고, 컴포넌트 검색은 초기화할 때 한 번만 한다.
	for (UActorComponent* Component : GetComponents())
	{
		if (Component->GetFName() == TEXT("HiddenPoint"))
			HiddenAnchor = Cast<USceneComponent>(Component);
		if (Component->GetFName() == TEXT("BasketCloth"))
			LocalCloth = Cast<USkeletalMeshComponent>(Component);
	}
	InitializeCloth();
}

void ACatrunHideBasket::BeginPlay()
{
	Super::BeginPlay();
	// External actors can finish their own component initialization later in the
	// level's startup pass. Finalize once after that pass, never on a permanent tick.
	GetWorldTimerManager().SetTimerForNextTick(FTimerDelegate::CreateWeakLambda(this,[this]
	{
		if (!Occupied) InitializeCloth();
	}));
}

void ACatrunHideBasket::InitializeCloth()
{
	USkeletalMeshComponent* Cloth = IsValid(ExternalCloth) ? ExternalCloth.Get() : LocalCloth.Get();
	if (Cloth && Cloth->GetSkeletalMeshAsset())
	{
		const FReferenceSkeleton& Ref = Cloth->GetSkeletalMeshAsset()->GetRefSkeleton();
		auto RefDirection = [&Ref](FName Name)
		{
			int32 Bone = Ref.FindBoneIndex(Name);
			if (Bone == INDEX_NONE) return FVector::ZeroVector;
			FTransform Pose = Ref.GetRefBonePose()[Bone];
			while ((Bone = Ref.GetParentIndex(Bone)) != INDEX_NONE) Pose *= Ref.GetRefBonePose()[Bone];
			return Pose.GetLocation().GetSafeNormal2D();
		};
		const FVector Front = RefDirection(TEXT("Edge_F")), Right = RefDirection(TEXT("Edge_R"));
		if (!Front.IsNearlyZero()) ClothReferenceForward = Front;
		// FBX converts Blender's handedness. Read the imported reference frame once,
		// so R/L clips stay correct without rotating the actual camera-relative exit.
		ClothSectorSign = FVector::CrossProduct(Front,Right).Z < 0 ? -1.f : 1.f;
	}
	if (LocalCloth.IsValid() && LocalCloth.Get()!=Cloth)
	{
		LocalCloth->PrimaryComponentTick.bStartWithTickEnabled=false;
		LocalCloth->SetComponentTickEnabled(false);
	}
	ClothIdle();
}

FVector ACatrunHideBasket::GetTraversalForward() const
{
	const USkeletalMeshComponent* Cloth = IsValid(ExternalCloth) ? ExternalCloth.Get() : LocalCloth.Get();
	return Cloth && ClothEnterDirections.Num()==8
		? Cloth->GetComponentTransform().TransformVectorNoScale(ClothReferenceForward).GetSafeNormal2D()
		: GetOpenDirection();
}

FVector ACatrunHideBasket::SnapTraversalDirection(const FVector& Direction) const
{
	return CatrunBasket::SnapDirection(Direction, GetTraversalForward());
}

float ACatrunHideBasket::GetTraversalDistance(const FVector& Direction, float CardinalDistance) const
{
	const FVector Local = FRotator(0,GetTraversalForward().Rotation().Yaw,0).UnrotateVector(Direction.GetSafeNormal2D());
	return CardinalDistance + (ClothEnterDirections.Num()==8 ? 24.f*FMath::Abs(Local.X*Local.Y) : 0.f);
}

FVector ACatrunHideBasket::GetHiddenLocation() const
{
	return HiddenAnchor.IsValid() ? HiddenAnchor->GetComponentLocation() : GetActorLocation();
}

FVector ACatrunHideBasket::GetOpenDirection() const
{
	// 명시한 정면을 바구니 회전에 따라 변환한다. Z와 메시 크기는 평면 출구 방향에 영향을 주지 않는다.
	return GetActorTransform().TransformVectorNoScale(OpenDirectionLocal.GetSafeNormal2D()).GetSafeNormal2D();
}

bool ACatrunHideBasket::TryOccupy(AActor* User)
{
	if (!IsValid(User) || Occupied) return false;
	Occupied = true;
	Occupant = User;
	return true;
}

void ACatrunHideBasket::Release(AActor* User)
{
	if (Occupant.Get() == User || !Occupant.IsValid())
	{
		Occupied = false;
		Occupant.Reset();
		ClothIdle();
	}
}

void ACatrunHideBasket::PlayCloth(UAnimationAsset* Animation, bool bFreeze, float PlayRate)
{
	USkeletalMeshComponent* Cloth = IsValid(ExternalCloth) ? ExternalCloth.Get() : LocalCloth.Get();
	if (Cloth && Animation)
	{
		Cloth->SetComponentTickEnabled(true);
		Cloth->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
		Cloth->PlayAnimation(Animation, false);
		Cloth->SetPlayRate(FMath::Max(PlayRate,.01f));
		if (bFreeze)
		{
			// An external SkeletalMeshActor may register its ticks after this basket.
			Cloth->PrimaryComponentTick.bStartWithTickEnabled=false;
			Cloth->SetPosition(0.f, false);
			Cloth->TickAnimation(0.f, false);
			Cloth->RefreshBoneTransforms();
			Cloth->SetComponentTickEnabled(false);
		}
	}
}

void ACatrunHideBasket::ClothEnter() { PlayCloth(ClothEnterAnimation, false); }
void ACatrunHideBasket::ClothExit() { PlayCloth(ClothExitAnimation, false); }
void ACatrunHideBasket::ClothIdle() { PlayCloth(Occupied && ClothHiddenAnimation ? ClothHiddenAnimation.Get() : ClothIdleAnimation.Get(), true); }

void ACatrunHideBasket::PlayDirectionalCloth(bool bEntering, const FVector& OutwardDirection, float PlayRate)
{
	const auto& Clips = bEntering ? ClothEnterDirections : ClothExitDirections;
	int32 Index = CatrunBasket::DirectionSector(OutwardDirection, GetTraversalForward().Rotation().Yaw);
	if (ClothSectorSign<0) Index=(8-Index)%8;
	UAnimationAsset* Animation = Clips.IsValidIndex(Index) ? Clips[Index].Get() : nullptr;
	if (!Animation) Animation = bEntering ? ClothEnterAnimation.Get() : ClothExitAnimation.Get();
	PlayCloth(Animation, false, PlayRate);
}
