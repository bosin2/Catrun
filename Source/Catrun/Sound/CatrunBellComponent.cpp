#include "CatrunBellComponent.h"

#include "Catrun.h"
#include "CatrunNoBellZone.h"
#include "CatrunNotice.h"
#include "CatrunSoundSettings.h"
#include "SoundGridManager.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "InputAction.h"
#include "InputMappingContext.h"
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
	// The tick watches the no-bell zones, and in key mode it also polls the key.
	SetComponentTickEnabled(true);

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

	UpdateBellBlock();
	if (bListeningToCatActions)
	{
		return;
	}

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

	// Forbidden places (the cat hole): no bell sound for the monsters, and the player is told why.
	if (ACatrunNoBellZone::IsBellForbidden(*GetOwner()))
	{
		if (UCatrunNoticeSubsystem* Notice = UCatrunNoticeSubsystem::Get(this))
		{
			if (const UCatrunSoundSettings* Settings = Manager->GetSettings())
			{
				Notice->ShowNotice(Settings->BellBlockedNotice, Settings->NoticeDuration);
			}
		}
		UE_LOG(LogCatrunSound, Log, TEXT("The bell is forbidden here, no sound for the monsters."));
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

void UCatrunBellComponent::BuildBlockContext()
{
	bBlockContextBuilt = true;

	// The bell keys are read from the cat's mapping contexts (every mapping of an action called "...Bell...").
	BlockAction = NewObject<UInputAction>(this, TEXT("BellBlockAction"));
	BlockContext = NewObject<UInputMappingContext>(this, TEXT("BellBlockContext"));
	int32 KeyCount = 0;
	const TCHAR* ContextPaths[] = {
		TEXT("/Game/Input/Contexts/IMC_Default.IMC_Default"),
		TEXT("/Game/Input/Contexts/IMC_CatInteraction.IMC_CatInteraction"),
	};
	for (const TCHAR* Path : ContextPaths)
	{
		const UInputMappingContext* CatContext = LoadObject<UInputMappingContext>(nullptr, Path);
		if (!CatContext)
		{
			UE_LOG(LogCatrunSound, Warning, TEXT("%s not found: the bell input cannot be blocked from it."), Path);
			continue;
		}
		for (const FEnhancedActionKeyMapping& Mapping : CatContext->GetMappings())
		{
			if (Mapping.Action && Mapping.Action->GetName().Contains(TEXT("Bell")))
			{
				BlockContext->MapKey(BlockAction, Mapping.Key);
				++KeyCount;
				UE_LOG(LogCatrunSound, Log, TEXT("Bell key %s (%s) will be taken over in no-bell zones."), *Mapping.Key.ToString(), *Mapping.Action->GetName());
			}
		}
	}
	if (KeyCount == 0)
	{
		UE_LOG(LogCatrunSound, Warning, TEXT("No bell key found in the cat's input contexts: the bell input cannot be blocked."));
	}
}

void UCatrunBellComponent::UpdateBellBlock()
{
	const APawn* Pawn = Cast<APawn>(GetOwner());
	APlayerController* Controller = Pawn ? Cast<APlayerController>(Pawn->GetController()) : nullptr;
	ULocalPlayer* LocalPlayer = Controller ? Controller->GetLocalPlayer() : nullptr;
	UEnhancedInputLocalPlayerSubsystem* Input = LocalPlayer ? LocalPlayer->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>() : nullptr;
	if (!Input)
	{
		return;
	}

	const bool bForbidden = ACatrunNoBellZone::IsBellForbidden(*Pawn);
	if (bForbidden == bBlockActive)
	{
		return;
	}
	if (!bBlockContextBuilt)
	{
		BuildBlockContext();
	}
	if (!BlockContext)
	{
		return;
	}

	if (bForbidden)
	{
		Input->AddMappingContext(BlockContext, 10000);
		if (!bBlockBound)
		{
			if (UEnhancedInputComponent* Enhanced = Cast<UEnhancedInputComponent>(Controller->InputComponent))
			{
				Enhanced->BindAction(BlockAction, ETriggerEvent::Started, this, &UCatrunBellComponent::HandleBlockedBellPressed);
				bBlockBound = true;
			}
		}
	}
	else
	{
		Input->RemoveMappingContext(BlockContext);
	}
	bBlockActive = bForbidden;
	UE_LOG(LogCatrunSound, Log, TEXT("No-bell zone %s: bell input %s."), bForbidden ? TEXT("entered") : TEXT("left"), bForbidden ? TEXT("blocked") : TEXT("free"));
}

void UCatrunBellComponent::HandleBlockedBellPressed()
{
	const ASoundGridManager* Manager = ASoundGridManager::Get(this);
	const UCatrunSoundSettings* Settings = Manager ? Manager->GetSettings() : nullptr;
	if (UCatrunNoticeSubsystem* Notice = UCatrunNoticeSubsystem::Get(this))
	{
		if (Settings)
		{
			Notice->ShowNotice(Settings->BellBlockedNotice, Settings->NoticeDuration);
		}
	}
}
