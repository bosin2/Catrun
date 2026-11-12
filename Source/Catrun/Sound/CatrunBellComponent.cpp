#include "CatrunBellComponent.h"
#include "Settings/CatrunInputBindings.h"
#include "Settings/CatrunUserSettings.h"
#include "EnhancedPlayerInput.h"
#include "Interaction/CatrunPuzzleSuspension.h"
#include "LevelFlow/CatrunLevelFlow.h"

#include "Catrun.h"
#include "CatrunBellIndicatorWidget.h"
#include "CatrunNoBellZone.h"
#include "CatrunNotice.h"
#include "CatrunSoundSettings.h"
#include "SoundGridManager.h"
#include "Components/WidgetComponent.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "InputAction.h"
#include "InputMappingContext.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Monster/CatrunRestartSubsystem.h"
#include "Perception/CatrunCatQueries.h"
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
	BindingsChangedHandle=UCatrunUserSettings::OnKeyboardBindingsChanged.AddUObject(this,&UCatrunBellComponent::UpdateBellBlock);
	// The tick watches the no-bell zones, and in key mode it also polls the key.
	SetComponentTickEnabled(true);

	UE_LOG(LogCatrunSound, Log, TEXT("Bell component on %s: %s."), *GetOwner()->GetName(),
		bListeningToCatActions ? TEXT("listening to the cat's OnBellRung") : TEXT("using the fallback key"));
}

void UCatrunBellComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	UCatrunUserSettings::OnKeyboardBindingsChanged.Remove(BindingsChangedHandle);
	if (auto* Input=BlockInputSubsystem.Get()) if (BlockContext) Input->RemoveMappingContext(BlockContext);
	if (auto* Enhanced=BlockInputComponent.Get()) if (BlockBindingHandle) Enhanced->RemoveBindingByHandle(BlockBindingHandle);
	if (IsValid(BellIndicator)) BellIndicator->DestroyComponent();
	BellIndicator = nullptr;
	BellIndicatorRemaining = 0.f;
	Super::EndPlay(EndPlayReason);
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
	UpdateBellIndicator(DeltaTime);
	if (bListeningToCatActions)
	{
		return;
	}

	// Key mode: used only when there is no BP_CatActions to listen to.
	const APawn* Pawn = Cast<APawn>(GetOwner());
	const APlayerController* Controller = Pawn ? Cast<APlayerController>(Pawn->GetController()) : nullptr;
	if (Controller && Controller->WasInputKeyJustPressed(UCatrunInputBindings::GetEffectiveKey(ECatrunInputSlot::Bell)))
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
	if (UCatrunPuzzleSuspension::IsSuspended(this)) return false;
	if (!GetOwner())
	{
		return false;
	}

	// Forbidden places (the cat hole): no bell sound for the monsters, and the player is told why.
	if (ACatrunNoBellZone::IsBellForbidden(*GetOwner()))
	{
		HandleBlockedBellPressed();
		UE_LOG(LogCatrunSound, Log, TEXT("The bell is forbidden here, no sound for the monsters."));
		return false;
	}
	ASoundGridManager* Manager = ASoundGridManager::Get(this);
	if (!Manager) return false;

	FCatrunSoundEvent Event;
	Event.Source = ECatrunSoundSource::Cat;
	Event.Kind = ECatrunSoundKind::Bell;
	Event.Size = ECatrunSoundSize::Large;
	Event.Target = ECatrunSoundTarget::Minion;
	Event.Location = GetOwner()->GetActorLocation(); // snapshot, not a live reference
	Event.Instigator = GetOwner();
	if (!Manager->EmitSound(Event)) return false;
	if (const UCatrunSoundSettings* Settings = Manager->GetSettings()) ShowBellIndicator(*Settings);
	return true;
}

bool UCatrunBellComponent::ShouldSuppressBellIndicator() const
{
	const APawn* Pawn = Cast<APawn>(GetOwner());
	const APlayerController* Controller = Pawn ? Cast<APlayerController>(Pawn->GetController()) : nullptr;
	const UCatrunRestartSubsystem* Restart = UCatrunRestartSubsystem::Get(this);
	return !IsValid(Pawn) || Pawn->IsActorBeingDestroyed() || !Controller
		|| !Controller->IsLocalController() || !Controller->GetLocalPlayer()
		|| Pawn->IsHidden() || UCatrunLevelFlowLibrary::ShouldHideGameplayHUD(this) || UCatrunPuzzleSuspension::IsSuspended(this)
		|| (Restart && Restart->IsCatching()) || CatrunCat::IsHiding(Pawn) || IsCatHiding();
}

void UCatrunBellComponent::ShowBellIndicator(const UCatrunSoundSettings& Settings)
{
	const float Duration = FMath::IsFinite(Settings.BellIndicatorDuration)
		? FMath::Clamp(Settings.BellIndicatorDuration, 0.f, 10.f) : 0.f;
	if (Duration <= 0.f || ShouldSuppressBellIndicator() || !GetOwner()->GetRootComponent())
	{
		HideBellIndicator();
		return;
	}
	const float Size = FMath::IsFinite(Settings.BellIndicatorSize)
		? FMath::Clamp(Settings.BellIndicatorSize, 16.f, 256.f) : 56.f;
	APlayerController* Controller = Cast<APlayerController>(Cast<APawn>(GetOwner())->GetController());
	if (!IsValid(BellIndicator))
	{
		UClass* WidgetClass = Settings.BellIndicatorWidgetClass.Get();
		if (!WidgetClass || WidgetClass->HasAnyClassFlags(CLASS_Abstract))
		{
			WidgetClass = UCatrunBellIndicatorWidget::StaticClass();
		}
		UUserWidget* Widget = CreateWidget<UUserWidget>(Controller, WidgetClass);
		if (!Widget) return;
		Widget->SetIsFocusable(false);
		Widget->SetVisibility(ESlateVisibility::HitTestInvisible);
		BellIndicator = NewObject<UWidgetComponent>(GetOwner());
		BellIndicator->SetupAttachment(GetOwner()->GetRootComponent());
		BellIndicator->SetWidgetSpace(EWidgetSpace::Screen);
		BellIndicator->SetOwnerPlayer(Controller->GetLocalPlayer());
		BellIndicator->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		BellIndicator->SetGenerateOverlapEvents(false);
		BellIndicator->SetWindowFocusable(false);
		BellIndicator->SetVisibility(false);
		BellIndicator->SetDrawSize(FVector2D(Size, Size));
		BellIndicator->RegisterComponent();
		BellIndicator->SetWidget(Widget);
	}
	BellIndicator->SetRelativeLocation(Settings.BellIndicatorOffset);
	BellIndicator->SetDrawSize(FVector2D(Size, Size));
	BellIndicator->SetOwnerPlayer(Controller->GetLocalPlayer());
	if (UUserWidget* Widget = BellIndicator->GetUserWidgetObject())
	{
		Widget->SetColorAndOpacity(Settings.BellIndicatorColor);
		Widget->SetRenderOpacity(1.f);
		Widget->SetVisibility(ESlateVisibility::HitTestInvisible);
	}
	BellIndicatorRemaining = Duration;
	BellIndicatorFadeDuration = FMath::Min(.25f, Duration);
	BellIndicator->SetVisibility(true);
}

void UCatrunBellComponent::UpdateBellIndicator(float DeltaTime)
{
	if (BellIndicatorRemaining <= 0.f) return;
	BellIndicatorRemaining = FMath::Max(0.f, BellIndicatorRemaining - DeltaTime);
	if (!IsValid(BellIndicator) || BellIndicatorRemaining <= 0.f || ShouldSuppressBellIndicator())
	{
		HideBellIndicator();
		return;
	}
	if (UUserWidget* Widget = BellIndicator->GetUserWidgetObject())
	{
		Widget->SetRenderOpacity(FMath::Clamp(BellIndicatorRemaining / BellIndicatorFadeDuration, 0.f, 1.f));
	}
}

void UCatrunBellComponent::HideBellIndicator()
{
	BellIndicatorRemaining = 0.f;
	if (IsValid(BellIndicator))
	{
		if (UUserWidget* Widget = BellIndicator->GetUserWidgetObject()) Widget->SetVisibility(ESlateVisibility::Collapsed);
		BellIndicator->SetVisibility(false);
	}
}

void UCatrunBellComponent::BuildBlockContext()
{
 bBlockContextBuilt = true;
 if (!BlockAction) BlockAction=NewObject<UInputAction>(this,TEXT("BellBlockAction"));
 if (!BlockContext) BlockContext=NewObject<UInputMappingContext>(this,TEXT("BellBlockContext"));
 BlockContext->UnmapAll();
 CachedBlockBellKey=UCatrunInputBindings::GetEffectiveKey(ECatrunInputSlot::Bell);
 BlockContext->MapKey(BlockAction,CachedBlockBellKey);
 // Keyboard is the selected semantic key. Retain authored controller bindings independently.
 const TCHAR* Paths[]={TEXT("/Game/Input/Contexts/IMC_Default.IMC_Default"),TEXT("/Game/Input/Contexts/IMC_CatInteraction.IMC_CatInteraction")};
 for (const TCHAR* Path : Paths)
  if (const auto* Context=LoadObject<UInputMappingContext>(nullptr,Path))
   for (const auto& Mapping : Context->GetMappings())
    if (Mapping.Action && Mapping.Action->GetName()==TEXT("IA_Bell") && Mapping.Key.IsGamepadKey())
     BlockContext->MapKey(BlockAction,Mapping.Key);
}

void UCatrunBellComponent::UpdateBellBlock()
{
 const APawn* Pawn=Cast<APawn>(GetOwner());
 APlayerController* Controller=Pawn ? Cast<APlayerController>(Pawn->GetController()) : nullptr;
 ULocalPlayer* LocalPlayer=Controller ? Controller->GetLocalPlayer() : nullptr;
 auto* Input=LocalPlayer ? LocalPlayer->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>() : nullptr;
 if (!Input || !Input->GetPlayerInput()) return;
 if (BlockInputSubsystem.Get()!=Input)
 {
  if (auto* Old=BlockInputSubsystem.Get()) if (BlockContext) Old->RemoveMappingContext(BlockContext);
  BlockInputSubsystem=Input;
  bBlockActive=false;
 }
 if (bBlockActive && (!BlockContext || !Input->HasMappingContext(BlockContext))) bBlockActive=false;
 const bool bForbidden=ACatrunNoBellZone::IsBellForbidden(*Pawn) || UCatrunPuzzleSuspension::IsSuspended(this);
 const bool bKeyChanged=!bBlockContextBuilt || CachedBlockBellKey!=UCatrunInputBindings::GetEffectiveKey(ECatrunInputSlot::Bell);
 if (bKeyChanged)
 {
  if (bBlockActive && BlockContext) Input->RemoveMappingContext(BlockContext);
  BuildBlockContext();
  bBlockActive=false;
 }
 if (bForbidden && BlockInputComponent.Get()!=Controller->InputComponent)
 {
  if (auto* Old=BlockInputComponent.Get()) if (BlockBindingHandle) Old->RemoveBindingByHandle(BlockBindingHandle);
  BlockBindingHandle=0;
  BlockInputComponent=Cast<UEnhancedInputComponent>(Controller->InputComponent);
  if (auto* Enhanced=BlockInputComponent.Get())
   BlockBindingHandle=Enhanced->BindAction(BlockAction,ETriggerEvent::Started,this,&UCatrunBellComponent::HandleBlockedBellPressed).GetHandle();
 }
 if (bForbidden==bBlockActive) return;
 FModifyContextOptions Options;
 Options.bIgnoreAllPressedKeysUntilRelease=true;
 Options.bForceImmediately=true;
 if (bForbidden) Input->AddMappingContext(BlockContext,10000,Options);
 else Input->RemoveMappingContext(BlockContext,Options);
 bBlockActive=bForbidden;
}

void UCatrunBellComponent::HandleBlockedBellPressed()
{
	if (UCatrunPuzzleSuspension::IsSuspended(this)) return;
	const ASoundGridManager* Manager = ASoundGridManager::Get(this);
	const UCatrunSoundSettings* Settings = Manager ? Manager->GetSettings() : nullptr;
	UCatrunNoticeLibrary::ShowBellDenied(this, Settings ? Settings->NoticeDuration : 2.f);
}
