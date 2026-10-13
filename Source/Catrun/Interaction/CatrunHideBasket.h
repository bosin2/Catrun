#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CatrunHideBasket.generated.h"

class UAnimationAsset;
class USkeletalMeshComponent;
class USceneComponent;

/** BP_HideBasket의 메시와 배치는 유지하고, 점유 상태와 천 재생은 C++에서 관리한다. */
UCLASS()
class CATRUN_API ACatrunHideBasket : public AActor
{
	GENERATED_BODY()
public:
	ACatrunHideBasket();
	virtual void OnConstruction(const FTransform& Transform) override;
	virtual void PostRegisterAllComponents() override;
	virtual void PostInitializeComponents() override;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Basket|State")
	bool Occupied = false;

	// 배치된 바구니의 외부 메시 연결을 보존하기 위해 기존 프로퍼티 이름을 유지한다.
	UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Basket|Meshes")
	TObjectPtr<USkeletalMeshComponent> ExternalCloth;

	UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category="Basket|Meshes")
	TObjectPtr<AActor> ExternalBody;

	// 바구니마다 지정하는 출구 정면. 천의 본이나 외부 메시 회전으로 덮어쓰지 않는다.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Basket|Direction",
		meta=(ToolTip="바구니 로컬 좌표의 출구 정면입니다. X/Y로 지정하며 길이와 Z는 사용하지 않습니다. 에디터의 청록색 화살표로 확인하세요."))
	FVector OpenDirectionLocal = FVector(0, -1, 0);

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Basket|Animation")
	TObjectPtr<UAnimationAsset> ClothEnterAnimation;
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Basket|Animation")
	TObjectPtr<UAnimationAsset> ClothExitAnimation;
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Basket|Animation")
	TObjectPtr<UAnimationAsset> ClothIdleAnimation;

	UFUNCTION(BlueprintCallable, Category="Basket")
	void ClothEnter();
	UFUNCTION(BlueprintCallable, Category="Basket")
	void ClothExit();
	UFUNCTION(BlueprintCallable, Category="Basket")
	void ClothIdle();

	UFUNCTION(BlueprintPure, Category="Basket")
	FVector GetHiddenLocation() const;
	FVector GetOpenDirection() const;
	bool HasHiddenPoint() const { return HiddenAnchor.IsValid(); }
	bool TryOccupy(AActor* User);
	void Release(AActor* User);

private:
	TWeakObjectPtr<USceneComponent> HiddenAnchor;
	TWeakObjectPtr<USkeletalMeshComponent> LocalCloth;
	TWeakObjectPtr<AActor> Occupant;
	void PlayCloth(UAnimationAsset* Animation, bool bLoop);
#if WITH_EDITOR
	void RefreshDirectionGuide();
#endif
};
