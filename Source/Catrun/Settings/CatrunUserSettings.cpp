#include "CatrunUserSettings.h"

#include "AudioDevice.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"

namespace
{
	FCatrunKeyboardBindings ReadKeyboardBindings(const FCatrunKeyboardBindings& Stored)
	{
		FText Error;
		if (Stored.Validate(Error))
			return Stored;

		const FCatrunKeyboardBindings Defaults;
		const int32 TabSlot = Stored.Keys.Find(EKeys::Tab);
		if (Stored.Keys.Num() != Defaults.Keys.Num() || TabSlot == INDEX_NONE || TabSlot != Stored.Keys.FindLast(EKeys::Tab))
			return Defaults;

		// A legacy Tab binding reserves exactly one slot. Keep the other choices when they still validate.
		auto IsAvailable = [&Stored](const FKey& Key)
		{
			return UCatrunInputBindings::IsKeyboardKey(Key) && !Stored.Keys.Contains(Key);
		};
		const FKey& Preferred = Defaults.Keys[TabSlot];
		const FKey* Replacement = IsAvailable(Preferred) ? &Preferred : Defaults.Keys.FindByPredicate(IsAvailable);
		if (!Replacement)
			return Defaults;

		FCatrunKeyboardBindings Repaired = Stored;
		Repaired.Keys[TabSlot] = *Replacement;
		return Repaired.Validate(Error) ? Repaired : Defaults;
	}
}

FSimpleMulticastDelegate UCatrunUserSettings::OnKeyboardBindingsChanged;

UCatrunUserSettings* UCatrunUserSettings::GetCatrunUserSettings()
{
	return GEngine ? Cast<UCatrunUserSettings>(GEngine->GetGameUserSettings()) : nullptr;
}

void UCatrunUserSettings::SetToDefaults()
{
	Super::SetToDefaults();
	MasterVolume = 1.f;
	KeyboardBindings = FCatrunKeyboardBindings();
}

void UCatrunUserSettings::ValidateSettings()
{
	Super::ValidateSettings();
	SetMasterVolume(MasterVolume);
	KeyboardBindings = ReadKeyboardBindings(KeyboardBindings);
}

void UCatrunUserSettings::LoadSettings(bool bForceReload)
{
	Super::LoadSettings(bForceReload);
	SetMasterVolume(MasterVolume);
	KeyboardBindings = ReadKeyboardBindings(KeyboardBindings);
}

void UCatrunUserSettings::SetMasterVolume(float Volume)
{
	MasterVolume = FMath::IsFinite(Volume) ? FMath::Clamp(Volume, 0.f, 1.f) : 1.f;
}

float UCatrunUserSettings::GetMasterVolume() const
{
	return FMath::IsFinite(MasterVolume) ? FMath::Clamp(MasterVolume, 0.f, 1.f) : 1.f;
}

void UCatrunUserSettings::ApplyAudioVolume(const UObject* WorldContextObject)
{
	UWorld* World = GEngine ? GEngine->GetWorldFromContextObject(WorldContextObject, EGetWorldErrorMode::ReturnNull) : nullptr;
	if (!World || !World->IsGameWorld()) return;
	if (FAudioDeviceHandle Device = World->GetAudioDevice())
	{
		// The mixer marshals this to the audio/render threads. Keep camera audio fades independent.
		Device->SetSubmixOutputVolume(&Device->GetMainSubmixObject(), GetMasterVolume());
	}
}

bool UCatrunUserSettings::IsDeveloperModeAvailable()
{
#if UE_BUILD_SHIPPING
	return false;
#else
	return IConsoleManager::Get().FindConsoleVariable(TEXT("catrun.NoArmorCapture")) != nullptr;
#endif
}

bool UCatrunUserSettings::IsNoArmorCaptureEnabled()
{
#if !UE_BUILD_SHIPPING
	if (const IConsoleVariable* Variable = IConsoleManager::Get().FindConsoleVariable(TEXT("catrun.NoArmorCapture")))
		return Variable->GetInt() != 0;
#endif
	return false;
}

void UCatrunUserSettings::SetNoArmorCaptureEnabled(bool bEnabled)
{
#if !UE_BUILD_SHIPPING
	if (IConsoleVariable* Variable = IConsoleManager::Get().FindConsoleVariable(TEXT("catrun.NoArmorCapture")))
		Variable->Set(bEnabled ? 1 : 0, ECVF_SetByConsole);
#endif
}

bool UCatrunUserSettings::IsArmorAreaDebugEnabled()
{
#if !UE_BUILD_SHIPPING
	if (const IConsoleVariable* Variable = IConsoleManager::Get().FindConsoleVariable(TEXT("catrun.DebugArmorArea")))
		return Variable->GetInt() != 0;
#endif
	return false;
}

void UCatrunUserSettings::SetArmorAreaDebugEnabled(bool bEnabled)
{
#if !UE_BUILD_SHIPPING
	if (IConsoleVariable* Variable = IConsoleManager::Get().FindConsoleVariable(TEXT("catrun.DebugArmorArea")))
		Variable->Set(bEnabled ? 1 : 0, ECVF_SetByConsole);
#endif
}

bool UCatrunUserSettings::IsInfiniteStaminaEnabled()
{
#if !UE_BUILD_SHIPPING
	if (const IConsoleVariable* Variable = IConsoleManager::Get().FindConsoleVariable(TEXT("catrun.InfiniteStamina")))
		return Variable->GetInt() != 0;
#endif
	return false;
}

void UCatrunUserSettings::SetInfiniteStaminaEnabled(bool bEnabled)
{
#if !UE_BUILD_SHIPPING
	if (IConsoleVariable* Variable = IConsoleManager::Get().FindConsoleVariable(TEXT("catrun.InfiniteStamina")))
		Variable->Set(bEnabled ? 1 : 0, ECVF_SetByConsole);
#endif
}

FCatrunKeyboardBindings UCatrunUserSettings::GetKeyboardBindings() const
{
 return ReadKeyboardBindings(KeyboardBindings);
}
bool UCatrunUserSettings::SetKeyboardBindings(const FCatrunKeyboardBindings& Bindings, FText& Error)
{
 if (!Bindings.Validate(Error)) return false;
 if (KeyboardBindings != Bindings)
 {
  KeyboardBindings = Bindings;
  OnKeyboardBindingsChanged.Broadcast();
 }
 return true;
}
