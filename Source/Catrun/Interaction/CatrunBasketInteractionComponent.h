#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "CatrunBasketExitPreview.h"
#include "CatrunBasketInteractionComponent.generated.h"

class ACharacter;
class ACatrunHideBasket;
class UAnimInstance;
class UAnimSequenceBase;

UENUM(BlueprintType)
enum class ECatrunBasketPhase : uint8 { Outside, Entering, Hidden, Exiting };

/**
 * BP_CatActions의 C++ 부모. 바구니 탐색부터 진입·숨기·탈출·복원까지 담당한다.
 * 방울 연출은 BP에 유지하고 Busy/IsHidden/ActiveBasket으로 기존 AI·소리 연동을 보존한다.
 */
UCLASS(ClassGroup=(Catrun), meta=(BlueprintSpawnableComponent))
class CATRUN_API UCatrunBasketInteractionComponent : public UActorComponent
{
	GENERATED_BODY()
public:
	UCatrunBasketInteractionComponent();
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

	/** F 입력: 접근 가능한 가장 가까운 바구니에 들어가거나, 선택한 방향으로 탈출한다. */
	UFUNCTION(BlueprintCallable, Category="Basket")
	void TryInteract();

	// 기존 몬스터·소리 컴포넌트가 리플렉션으로 읽는 이름이므로 변경하지 않는다.
	UPROPERTY(VisibleInstanceOnly, BlueprintReadWrite, Category="Cat Interaction")
	bool Busy = false;
	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Cat Interaction")
	bool IsHidden = false;
	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Cat Interaction")
	TObjectPtr<ACatrunHideBasket> ActiveBasket;
	UPROPERTY(VisibleInstanceOnly, BlueprintReadWrite, Category="Cat Interaction")
	TObjectPtr<ACharacter> CatOwner;

	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category="Basket|Interaction", meta=(ClampMin="1"))
	float InteractionRange = 110.f;
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Basket|Interaction", meta=(ClampMin="1"))
	float EntryDistance = 82.f;
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Basket|Interaction", meta=(ClampMin="1"))
	float ExitDistance = 82.f;
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Basket|Interaction")
	TEnumAsByte<ECollisionChannel> ObstacleChannel = ECC_Visibility;

	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Basket|Animation")
	TObjectPtr<UAnimSequenceBase> EnterAnimation;
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Basket|Animation")
	TObjectPtr<UAnimSequenceBase> ExitAnimation;
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Basket|Animation", meta=(ClampMin=".01"))
	float AnimationPlayRate = 1.f;
	UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category="Basket|Preview")
	FCatrunBasketPreviewStyle PreviewStyle;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Basket|State")
	ECatrunBasketPhase BasketPhase = ECatrunBasketPhase::Outside;
	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Basket|State")
	bool CanExit = false;
	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Basket|State")
	FVector ExitWorldDirection = FVector::ForwardVector;
	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Basket|State")
	FVector ExitWorldLocation = FVector::ZeroVector;

protected:
	/** BP의 짧은 연결을 통해 기존 OnHiddenChanged 디스패처로 상태 변경을 전달한다. */
	UFUNCTION(BlueprintImplementableEvent, Category="Basket", meta=(DisplayName="Basket Hidden State Changed"))
	void BasketHiddenStateChanged();

private:
	void FindAndEnterBasket();
	bool TestEntry(ACatrunHideBasket* Basket, FVector& OutLocation) const;
	void EnterBasket(ACatrunHideBasket* Basket, const FVector& Location);
	void FinishEnter();
	void ExitBasket();
	void FinishExit();
	void UpdateExitCandidate(bool bForce);
	void UpdatePreview();
	void RestoreCharacter();
	void AbortBasket();
	float PlayCharacterAnimation(UAnimSequenceBase* Animation);

	UPROPERTY(Transient)
	TObjectPtr<UCatrunBasketExitPreview> ExitPreview;
	UPROPERTY(Transient)
	TSubclassOf<UAnimInstance> SavedAnimClass;

	FTimerHandle AnimationTimer;
	FTransform SavedEntryTransform;
	FVector FloorLocation = FVector::ZeroVector;
	FVector LastBasketOrigin = FVector::ZeroVector;
	FVector LastBasketForward = FVector::ZeroVector;
	double NextObstacleCheck = 0;
	uint8 SavedMovementMode = 1;
	uint8 SavedCustomMovementMode = 0;
	bool bSavedCollision = true;
	bool bSavedMeshVisible = true;
	bool bSavedControllerYaw = false;
	bool bSavedOrientToMovement = false;
	bool bSavedControllerDesiredRotation = false;
};
