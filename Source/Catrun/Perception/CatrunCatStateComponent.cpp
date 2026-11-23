#include "CatrunCatStateComponent.h"
#include "Components/CapsuleComponent.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"

#include "Catrun.h"
#include "Sound/CatrunSoundSettings.h"
#include "Sound/SoundGridManager.h"
#include "GameFramework/Pawn.h"
#include "UObject/UnrealType.h"

UCatrunCatStateComponent::UCatrunCatStateComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
}

void UCatrunCatStateComponent::BeginPlay()
{
	Super::BeginPlay();
	if (auto* Cat = Cast<ACharacter>(GetOwner()))
	{
		Cat->GetCapsuleComponent()->SetCollisionObjectType(ECC_Pawn);
		Cat->GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Pawn, ECR_Block);
	}
}

UActorComponent* UCatrunCatStateComponent::FindCatActions() const
{
	if (UActorComponent* Known = CatActions.Get())
	{
		return Known;
	}
	// The interaction blueprint class is not known to C++, so find its component by class name.
	for (UActorComponent* Component : GetOwner()->GetComponents())
	{
		if (Component && Component->GetClass()->GetName().Contains(TEXT("CatActions")))
		{
			const_cast<UCatrunCatStateComponent*>(this)->CatActions = Component;
			return Component;
		}
	}
	return nullptr;
}

bool UCatrunCatStateComponent::ReadCatBool(const TCHAR* VariableName) const
{
	const UObject* Cat = GetOwner();
	const FBoolProperty* Property = Cat ? FindFProperty<FBoolProperty>(Cat->GetClass(), VariableName) : nullptr;
	return Property && Property->GetPropertyValue_InContainer(Cat);
}

float UCatrunCatStateComponent::GetStatuePushSpeedLimit(const ACharacter& Cat)
{
	const auto* Movement = Cat.GetCharacterMovement();
	const float Speed = Movement->GetMaxSpeed();
	if (Movement->IsCrouching()) return Speed;

	const auto* OffsetProperty = FindFProperty<FNumericProperty>(Cat.GetClass(), TEXT("StatuePushLocomotionOffset"));
	if (!OffsetProperty || !OffsetProperty->IsFloatingPoint()) return Speed;

	const double Offset = OffsetProperty->GetFloatingPointPropertyValue(OffsetProperty->ContainerPtrToValuePtr<void>(&Cat));
	return FMath::IsFinite(Offset) && Offset > 0.0 ? static_cast<float>(FMath::Max(0.0, Speed - Offset)) : Speed;
}

bool UCatrunCatStateComponent::ReadActionsBool(const TCHAR* VariableName) const
{
	const UActorComponent* Actions = FindCatActions();
	const FBoolProperty* Property = Actions ? FindFProperty<FBoolProperty>(Actions->GetClass(), VariableName) : nullptr;
	return Property && Property->GetPropertyValue_InContainer(Actions);
}

bool UCatrunCatStateComponent::HasBasket() const
{
	const UActorComponent* Actions = FindCatActions();
	const FObjectPropertyBase* Property = Actions ? FindFProperty<FObjectPropertyBase>(Actions->GetClass(), TEXT("ActiveBasket")) : nullptr;
	return Property && Property->GetObjectPropertyValue_InContainer(Actions) != nullptr;
}

void UCatrunCatStateComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	UpdateHideEntry();
	UpdateFootsteps(DeltaTime);
}

// ---------------------------------------------------------------------------
// Hideout entry
// ---------------------------------------------------------------------------

// The cat's interaction blueprint says it is "busy" while an animation plays and has a basket
// (the hideout) while it goes in or out. An entry is: busy, a hideout chosen, not hidden yet,
// and not on the way out (hidden -> leaving stays "leaving" until the cat is free again).
void UCatrunCatStateComponent::UpdateHideEntry()
{
	const bool bHidden = ReadActionsBool(TEXT("IsHidden"));
	const bool bBusy = ReadActionsBool(TEXT("Busy"));

	if (bHidden)
	{
		bLeavingHideout = true;
	}
	else if (!bBusy)
	{
		bLeavingHideout = false;
	}

	const bool bEntering = bBusy && !bHidden && !bLeavingHideout && HasBasket();
	if (bEntering != bEnteringHideout)
	{
		bEnteringHideout = bEntering;
		UE_LOG(LogCatrunSound, Log, TEXT("Cat %s the hideout (busy %d, hidden %d, basket %d)."),
			bEntering ? TEXT("is getting into") : TEXT("finished getting into"), bBusy, bHidden, HasBasket());
	}
	bWasBusy = bBusy;
}

// ---------------------------------------------------------------------------
// Footsteps
// ---------------------------------------------------------------------------

void UCatrunCatStateComponent::UpdateFootsteps(float DeltaTime)
{
	const ASoundGridManager* Manager = ASoundGridManager::Get(this);
	const UCatrunSoundSettings* S = Manager ? Manager->GetSettings() : nullptr;
	const APawn* Cat = Cast<APawn>(GetOwner());
	if (!S || !Cat)
	{
		return;
	}

	const bool bMoving = Cat->GetVelocity().Size2D() >= S->FootstepMinSpeed;
	const bool bHidden = ReadActionsBool(TEXT("IsHidden")) || bEnteringHideout;
	if (!bMoving || bHidden)
	{
		StepTimer = 0.f; // the first step after standing still is heard at once
		LastMoveMode = -1;
		return;
	}

	const bool bSneaking = ReadCatBool(TEXT("IsSneaking"));
	const bool bRunning = !bSneaking && ReadCatBool(TEXT("IsRunning"));
	const int32 MoveMode = bSneaking ? 0 : (bRunning ? 2 : 1);
	if (MoveMode != LastMoveMode)
	{
		UE_LOG(LogCatrunSound, Log, TEXT("Cat moves: %s."), MoveMode == 0 ? TEXT("sneaking (silent)") : (MoveMode == 2 ? TEXT("running") : TEXT("walking")));
		LastMoveMode = MoveMode;
		// The step timer is kept: changing how the cat moves must not make an extra step every time
		// (tapping the sneak or run key would otherwise make a footstep on every tap).
	}
	if (bSneaking)
	{
		return;
	}

	const float Interval = bRunning ? S->RunStepInterval : S->WalkStepInterval;
	StepTimer = FMath::Min(StepTimer, Interval); // a shorter interval (starting to run) takes effect at once
	if (StepTimer <= 0.f)
	{
		EmitFootstep(bRunning);
		StepTimer = Interval;
	}
	StepTimer -= DeltaTime;
}

void UCatrunCatStateComponent::EmitFootstep(bool bRunning)
{
	ASoundGridManager* Manager = ASoundGridManager::Get(this);
	if (!Manager || !GetOwner())
	{
		return;
	}
	FCatrunSoundEvent Event;
	Event.Source = ECatrunSoundSource::Cat;
	Event.Kind = ECatrunSoundKind::Footstep;
	Event.Size = bRunning ? ECatrunSoundSize::Medium : ECatrunSoundSize::Small;
	Event.Target = ECatrunSoundTarget::Minion;
	Event.Location = GetOwner()->GetActorLocation(); // snapshot, not a live reference
	Event.Instigator = GetOwner();
	Manager->EmitSound(Event);
}
