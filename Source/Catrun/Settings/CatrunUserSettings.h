#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameUserSettings.h"
#include "CatrunInputBindings.h"
#include "CatrunUserSettings.generated.h"

/** Video settings use the engine's existing controls and ApplySettings(false). */
UCLASS(Config=GameUserSettings, BlueprintType)
class CATRUN_API UCatrunUserSettings : public UGameUserSettings
{
	GENERATED_BODY()
public:
 static FSimpleMulticastDelegate OnKeyboardBindingsChanged;
	virtual void SetToDefaults() override;
	virtual void ValidateSettings() override;
	virtual void LoadSettings(bool bForceReload = false) override;

	UFUNCTION(BlueprintPure, Category="Catrun|Settings")
	static UCatrunUserSettings* GetCatrunUserSettings();
	UFUNCTION(BlueprintCallable, Category="Catrun|Settings")
	void SetMasterVolume(float Volume);
	UFUNCTION(BlueprintPure, Category="Catrun|Settings")
	float GetMasterVolume() const;
	UFUNCTION(BlueprintCallable, Category="Catrun|Settings", meta=(WorldContext="WorldContextObject"))
	void ApplyAudioVolume(const UObject* WorldContextObject);
	UFUNCTION(BlueprintPure, Category="Catrun|Settings")
	static bool IsDeveloperModeAvailable();
	UFUNCTION(BlueprintPure, Category="Catrun|Settings")
	static bool IsNoArmorCaptureEnabled();
	UFUNCTION(BlueprintCallable, Category="Catrun|Settings")
	static void SetNoArmorCaptureEnabled(bool bEnabled);
 UFUNCTION(BlueprintPure, Category="Catrun|Settings")
 FCatrunKeyboardBindings GetKeyboardBindings() const;
 // Rejection leaves the whole stored draft unchanged. Persistence belongs to Apply.
 bool SetKeyboardBindings(const FCatrunKeyboardBindings& Bindings, FText& Error);
private:
 UPROPERTY(Config) FCatrunKeyboardBindings KeyboardBindings;
	UPROPERTY(Config) float MasterVolume = 1.f;
};
