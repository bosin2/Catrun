#include "CatrunBellComponent.h"

#include "Catrun.h"
#include "CatrunSoundSettings.h"
#include "SoundGridManager.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "UObject/UnrealType.h"

namespace
{
	// Names used by the cat's blueprint (read only, we never edit that blueprint).
	const TCHAR* CatActionsClassHint = TEXT("CatActions");
	const FName BellRungDispatcher = TEXT("OnBellRung");
	const FName IsHiddenVariable = TEXT("IsHidden");
}

UCatrunBellComponent::UCatrunBellComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
}

void UCatrunBellComponent::BeginPlay()
{
	Super::BeginPlay();

	bListeningToCatActions = BindToCatActions();
	// In key mode the tick polls the key. When listening to the cat we do not need it.
	SetComponentTickEnabled(!bListeningToCatActions);

	UE_LOG(LogCatrunSound, Log, TEXT("Bell component on %s: %s."), *GetOwner()->GetName(),
		bListeningToCatActions ? TEXT("listening to the cat's OnBellRung") : TEXT("using the fallback key"));
}

bool UCatrunBellComponent::BindToCatActions()
{
	AActor* Owner = GetOwner();
	if (!Owner)
	{
		return false;
	}

	// The blueprint class is not known to C++, so find the component by its class name.
	for (UActorComponent* Component : Owner->GetComponents())
	{
		if (!Component || !Component->GetClass()->GetName().Contains(CatActionsClassHint))
		{
			continue;
		}
		// The event dispatcher is a multicast delegate property of the blueprint class.
		FMulticastDelegateProperty* Dispatcher = FindFProperty<FMulticastDelegateProperty>(Component->GetClass(), BellRungDispatcher);
		if (!Dispatcher)
		{
			continue;
		}
		FScriptDelegate Callback;
		Callback.BindUFunction(this, GET_FUNCTION_NAME_CHECKED(UCatrunBellComponent, HandleBellRung));
		Dispatcher->AddDelegate(Callback, Component);
		CatActions = Component;
		return true;
	}
	return false;
}

bool UCatrunBellComponent::IsCatHiding() const
{
	const UActorComponent* Component = CatActions.Get();
	const FBoolProperty* Hidden = Component ? FindFProperty<FBoolProperty>(Component->GetClass(), IsHiddenVariable) : nullptr;
	return Hidden && Hidden->GetPropertyValue_InContainer(Component);
}

void UCatrunBellComponent::HandleBellRung()
{
	// The cat's own rules (cooldown, busy) already let this ring through. Hiding is checked
	// again here because no bell may be heard from a hideout (design doc 5).
	if (!IsCatHiding())
	{
		EmitBellSound();
	}
}

void UCatrunBellComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	// Key mode: used only when there is no BP_CatActions to listen to.
	const APawn* Pawn = Cast<APawn>(GetOwner());
	const APlayerController* Controller = Pawn ? Cast<APlayerController>(Pawn->GetController()) : nullptr;
	if (Controller && Controller->WasInputKeyJustPressed(FallbackBellKey))
	{
		TryRing();
	}
}

float UCatrunBellComponent::GetCooldownRemaining() const
{
	const ASoundGridManager* Manager = ASoundGridManager::Get(this);
	const UCatrunSoundSettings* Settings = Manager ? Manager->GetSettings() : nullptr;
	if (!Settings || !GetWorld())
	{
		return 0.f;
	}
	return FMath::Max(0.f, static_cast<float>(Settings->BellCooldown - (GetWorld()->GetTimeSeconds() - LastRingTime)));
}

bool UCatrunBellComponent::TryRing()
{
	if (!bCanRing || GetCooldownRemaining() > 0.f)
	{
		return false;
	}
	if (EmitBellSound())
	{
		LastRingTime = GetWorld()->GetTimeSeconds();
		return true;
	}
	return false;
}

bool UCatrunBellComponent::EmitBellSound()
{
	ASoundGridManager* Manager = ASoundGridManager::Get(this);
	if (!Manager || !GetOwner())
	{
		return false;
	}

	FCatrunSoundEvent Event;
	Event.Source = ECatrunSoundSource::Cat;
	Event.Kind = ECatrunSoundKind::Bell;
	Event.Size = ECatrunSoundSize::Large;
	Event.Target = ECatrunSoundTarget::Minion;
	Event.Location = GetOwner()->GetActorLocation(); // snapshot, not a live reference
	Event.Instigator = GetOwner();
	return Manager->EmitSound(Event);
}
