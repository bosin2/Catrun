#include "CatrunSprintComponent.h"
#include "HAL/IConsoleManager.h"

#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "Interaction/CatrunBasketInteractionComponent.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "UObject/UnrealType.h"

namespace
{
#if !UE_BUILD_SHIPPING
	TAutoConsoleVariable<int32> CVarInfiniteStamina(TEXT("catrun.InfiniteStamina"), 0,
		TEXT("Developer: the cat's sprint stamina never runs out. 0: normal, 1: unlimited."), ECVF_Cheat);
#endif
bool ReadMovementFlag(const ACharacter* Cat, FName Name)
{
	const auto* Property = Cat ? FindFProperty<FBoolProperty>(Cat->GetClass(), Name) : nullptr;
	return Property && Property->GetPropertyValue_InContainer(Cat);
}

bool IsPlayerMovementAvailable(const ACharacter& Cat)
{
	const auto* PC = Cast<APlayerController>(Cat.GetController());
	if (!PC || !PC->IsLocalController() || PC->GetPawn() != &Cat || UCatrunLevelFlowLibrary::ShouldHideGameplayHUD(&Cat)) return false;
	const auto* Flow = UCatrunLevelFlowSubsystem::Get(&Cat);
	return !Flow || !Flow->IsStageComplete();
}

bool HasPendingExternalForce(const UCharacterMovementComponent& Movement)
{
	// CharacterMovement consumes these protected accumulators before its movement delegate.
	static const auto* Impulse = FindFProperty<FStructProperty>(UCharacterMovementComponent::StaticClass(), TEXT("PendingImpulseToApply"));
	static const auto* Force = FindFProperty<FStructProperty>(UCharacterMovementComponent::StaticClass(), TEXT("PendingForceToApply"));
	return (Impulse && !Impulse->ContainerPtrToValuePtr<FVector>(&Movement)->IsNearlyZero())
		|| (Force && !Force->ContainerPtrToValuePtr<FVector>(&Movement)->IsNearlyZero());
}
}

UCatrunSprintComponent::UCatrunSprintComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.TickGroup = TG_PrePhysics;
}

void UCatrunSprintComponent::BeginPlay()
{
	Super::BeginPlay();
	ResetStamina();
	if (auto* Cat = Cast<ACharacter>(GetOwner()))
	{
		Cat->GetCharacterMovement()->AddTickPrerequisiteComponent(this);
		Cat->OnCharacterMovementUpdated.AddUniqueDynamic(this, &UCatrunSprintComponent::HandleMovementUpdated);
	}
}

void UCatrunSprintComponent::EndPlay(const EEndPlayReason::Type Reason)
{
	if (auto* Cat = Cast<ACharacter>(GetOwner()))
	{
		Cat->OnCharacterMovementUpdated.RemoveDynamic(this, &UCatrunSprintComponent::HandleMovementUpdated);
		Cat->GetCharacterMovement()->RemoveTickPrerequisiteComponent(this);
	}
	Super::EndPlay(Reason);
}

bool UCatrunSprintComponent::ResolveSprintIntent(ACharacter* Cat, bool bSprintHeld)
{
	const auto* Sprint = Cat ? Cat->FindComponentByClass<UCatrunSprintComponent>() : nullptr;
	return bSprintHeld && (!Sprint || !Sprint->IsExhausted());
}

bool UCatrunSprintComponent::IsRunInputHeld() const
{
	const auto* Cat = Cast<ACharacter>(GetOwner());
	static const FName IsRunning(TEXT("IsRunning"));
	static const FName IsSneaking(TEXT("IsSneaking"));
	return ReadMovementFlag(Cat, IsRunning) && !ReadMovementFlag(Cat, IsSneaking);
}

bool UCatrunSprintComponent::IsSprinting() const
{
	return bSprinting && !bExhausted && IsRunInputHeld();
}

void UCatrunSprintComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	auto* Cat = Cast<ACharacter>(GetOwner());
	if (!Cat) return;
	const auto* Movement = Cat->GetCharacterMovement();
	bGroundedAtMovementStart = Movement->IsMovingOnGround();
	bForcedAtMovementStart = Cat->HasAnyRootMotion() || Movement->bJustTeleported || HasPendingExternalForce(*Movement);

	// CharacterMovement does not emit an update while disabled by a bell or basket action.
	if (Movement->MovementMode == MOVE_None || !Movement->IsComponentTickEnabled())
	{
		bSprinting = false;
		if (IsPlayerMovementAvailable(*Cat)) AdvanceStamina(DeltaTime, false);
	}
}

void UCatrunSprintComponent::HandleMovementUpdated(float DeltaSeconds, FVector OldLocation, FVector /*OldVelocity*/)
{
	const auto* Cat = Cast<ACharacter>(GetOwner());
	bSprinting = false;
	if (!Cat || !IsPlayerMovementAvailable(*Cat)) return;

	const auto* Movement = Cat->GetCharacterMovement();
	const auto* Actions = Cat->FindComponentByClass<UCatrunBasketInteractionComponent>();
	const bool bBusy = Actions && (Actions->Busy || Actions->IsHidden || Actions->BasketPhase != ECatrunBasketPhase::Outside);
	const FVector Travel = Cat->GetActorLocation() - OldLocation;
	const bool bForced = bForcedAtMovementStart || Movement->bJustTeleported || Cat->HasAnyRootMotion()
		|| Travel.Size2D() > DeltaSeconds * Movement->GetMaxSpeed() + 1.;
	bSprinting = !bExhausted && !bBusy && !Movement->IsCrouching() && IsRunInputHeld()
		&& !Movement->GetCurrentAcceleration().IsNearlyZero()
		&& IsVoluntaryHorizontalTravel(Movement->GetLastInputVector(), Travel,
			bGroundedAtMovementStart && Movement->IsMovingOnGround(), bForced);
	AdvanceStamina(DeltaSeconds, bSprinting);
}

bool UCatrunSprintComponent::IsVoluntaryHorizontalTravel(const FVector& Input, const FVector& Travel, bool bGrounded, bool bForced)
{
	return bGrounded && !bForced && FVector::DotProduct(Input.GetSafeNormal2D(), Travel) > UE_KINDA_SMALL_NUMBER;
}

void UCatrunSprintComponent::ResetStamina()
{
	Stamina = GetMaxStamina();
	SecondsWithoutDrain = 0.;
	bSprinting = false;
	ApplyExhaustion(false);
}

void UCatrunSprintComponent::AdvanceStamina(double DeltaSeconds, bool bDraining)
{
	if (DeltaSeconds <= 0. || !FMath::IsFinite(DeltaSeconds)) return;
#if !UE_BUILD_SHIPPING
	if (CVarInfiniteStamina.GetValueOnGameThread() != 0)
	{
		// Developer: always full, never exhausted; sprinting itself still works normally.
		Stamina = GetMaxStamina();
		SecondsWithoutDrain = 0.;
		ApplyExhaustion(false);
		return;
	}
#endif
	const double Maximum = GetMaxStamina();
	const double Drain = FMath::Max(0.f, DrainPerSecond);
	if (bDraining && !bExhausted && Drain > 0.)
	{
		SecondsWithoutDrain = 0.;
		Stamina = FMath::Clamp(Stamina - Drain * DeltaSeconds, 0., Maximum);
		if (Stamina <= UE_DOUBLE_SMALL_NUMBER)
		{
			Stamina = 0.;
			ApplyExhaustion(true);
		}
		return;
	}

	const double Delay = FMath::Max(0.f, RecoveryDelaySeconds);
	const double TimeUntilRecovery = FMath::Max(0., Delay - SecondsWithoutDrain);
	SecondsWithoutDrain = FMath::Min(Delay, SecondsWithoutDrain + DeltaSeconds);
	const double RecoveryTime = FMath::Max(0., DeltaSeconds - TimeUntilRecovery);
	Stamina = FMath::Clamp(Stamina + RecoveryTime * FMath::Max(0.f, RecoveryPerSecond), 0., Maximum);
	if (Stamina + UE_DOUBLE_SMALL_NUMBER >= FMath::Clamp(static_cast<double>(RearmStamina), 1., Maximum)) ApplyExhaustion(false);
}

void UCatrunSprintComponent::ApplyExhaustion(bool bNewExhausted)
{
	if (bExhausted == bNewExhausted) return;
	bExhausted = bNewExhausted;
	if (!IsRunInputHeld()) return;
	AActor* Cat = GetOwner();
	if (auto* UpdateSpeed = Cat->FindFunction(TEXT("UpdateMovementSpeed"))) Cat->ProcessEvent(UpdateSpeed, nullptr);
}
