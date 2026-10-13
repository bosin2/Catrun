#include "CatrunHideBasket.h"
#include "Animation/AnimationAsset.h"
#include "Components/ArrowComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SkeletalMeshComponent.h"
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
	// BP의 에디터 전용 화살표는 설정값을 보여주기만 한다. 판정 기준은 OpenDirectionLocal 하나다.
	TInlineComponentArray<UArrowComponent*> Arrows(this);
	for (UArrowComponent* Arrow : Arrows)
	{
		if (Arrow->GetFName() == TEXT("ExitDirectionGuide"))
		{
			const FVector Direction = GetOpenDirection();
			Arrow->SetVisibility(!Direction.IsNearlyZero());
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

void ACatrunHideBasket::PlayCloth(UAnimationAsset* Animation, bool bLoop)
{
	USkeletalMeshComponent* Cloth = IsValid(ExternalCloth) ? ExternalCloth.Get() : LocalCloth.Get();
	if (Cloth && Animation)
	{
		Cloth->PlayAnimation(Animation, bLoop);
		Cloth->SetPlayRate(1.f);
	}
}

void ACatrunHideBasket::ClothEnter() { PlayCloth(ClothEnterAnimation, false); }
void ACatrunHideBasket::ClothExit() { PlayCloth(ClothExitAnimation, false); }
void ACatrunHideBasket::ClothIdle() { PlayCloth(ClothIdleAnimation, true); }
