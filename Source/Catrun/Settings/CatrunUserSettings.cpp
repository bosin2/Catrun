#include "CatrunUserSettings.h"

#include "AudioDevice.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"

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
	FText Error;
	if (!KeyboardBindings.Validate(Error)) KeyboardBindings = FCatrunKeyboardBindings();
}

void UCatrunUserSettings::LoadSettings(bool bForceReload)
{
	Super::LoadSettings(bForceReload);
	SetMasterVolume(MasterVolume);
	FText Error;
	if (!KeyboardBindings.Validate(Error)) KeyboardBindings = FCatrunKeyboardBindings();
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

FCatrunKeyboardBindings UCatrunUserSettings::GetKeyboardBindings() const
{
 FText Error;
 return KeyboardBindings.Validate(Error) ? KeyboardBindings : FCatrunKeyboardBindings();
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
