#pragma once
#include "CoreMinimal.h"
#include "Components/SlateWrapperTypes.h"
#include "Subsystems/WorldSubsystem.h"
#include "Engine/EngineBaseTypes.h"
#include "CatrunSettingsSubsystem.generated.h"
class APlayerController;
class UCatrunSettingsWidget;
class UWidget;
class UGameViewportClient;
class IInputProcessor;
class SWidget;
class FSlateApplication;
class FReply;
/** Slate lock ownership is retained in place: none of these operations requests a lock/unlock.
 * Focus is restored with viewport acquisition suppressed, then capture/raw input is restored synchronously.
 */
struct CATRUN_API FCatrunSettingsSlateSnapshot
{
 TWeakPtr<SWidget> Focus;
 TWeakPtr<SWidget> CursorCaptor;
 uint32 FocusUserIndex=0;
 uint32 CursorUserIndex=0;
 bool bHighPrecision=false;
 void Capture(FSlateApplication& Slate,uint32 InFocusUserIndex);
 // Shared ordered transition; synthetic tests can model focus callbacks without native input changes.
 void RestoreWithCallbacks(TFunctionRef<void()> SuppressViewportAcquisition,TFunctionRef<void()> RestoreFocus,
  TFunctionRef<void(const FReply&)> ProcessCursorReply,TFunctionRef<void()> RestoreViewportPolicy) const;
 void Restore(FSlateApplication& Slate,UGameViewportClient* Viewport,bool bRestoreIgnoreInput,
  EMouseCaptureMode RestoreCaptureMode,const TSharedPtr<SWidget>& FallbackWidget) const;
private:
 void CaptureCursor(const TSharedPtr<SWidget>& InCursorCaptor,bool bInHighPrecision);
 friend class FCatrunSettingsInputRestorationTest;
};
UCLASS()
class CATRUN_API UCatrunSettingsSubsystem : public UTickableWorldSubsystem
{
 GENERATED_BODY()
public:
 FSimpleMulticastDelegate OnSettingsOpened;
 UFUNCTION(BlueprintPure, Category="Catrun|Settings", meta=(WorldContext="Context")) static UCatrunSettingsSubsystem* Get(const UObject* Context);
 UFUNCTION(BlueprintCallable, Category="Catrun|Settings") UCatrunSettingsWidget* OpenSettings(APlayerController* PlayerController, UWidget* SourcePanel=nullptr);
 UFUNCTION(BlueprintCallable, Category="Catrun|Settings") void CloseSettings();
 UFUNCTION(BlueprintPure, Category="Catrun|Settings") UCatrunSettingsWidget* GetCurrentSettingsWidget() const { return CurrentSettings; }
 UFUNCTION(BlueprintPure, Category="Catrun|Settings") static bool IsNavigationFocused(UWidget* Widget);
 virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
 virtual void OnWorldBeginPlay(UWorld& InWorld) override;
 virtual void Deinitialize() override;
 virtual void Tick(float DeltaTime) override;
 virtual TStatId GetStatId() const override;
 virtual bool IsTickableWhenPaused() const override { return true; }
 bool HandleEscape();
 bool OwnsInputFocus(int32 SlateUserIndex=INDEX_NONE) const;
 // Input repeats of held keyboard keys must not become new gameplay actions on Apply/close.
 void IgnoreHeldKeysUntilRelease();
private:
 void SuspendSourcePanel(UWidget* Panel);
 void RestoreSourcePanel();
 friend class FCatrunSettingsSourcePanelRestorationTest;
 UPROPERTY(Transient) TObjectPtr<UCatrunSettingsWidget> CurrentSettings;
 UPROPERTY(Transient) TObjectPtr<UWidget> SettingsSourcePanel;
 TWeakObjectPtr<APlayerController> SettingsController;
 TWeakObjectPtr<UGameViewportClient> SavedViewport;
 FCatrunSettingsSlateSnapshot PreviousSlateState;
 TSharedPtr<IInputProcessor> InputProcessor;
 bool bClosing=false;
 bool bPauseOwned=false;
 bool bPreviousCursor=false;
 bool bPreviousIgnoreInput=false;
 bool bPreviousHideCursor=false;
 EMouseCaptureMode PreviousCaptureMode=EMouseCaptureMode::NoCapture;
 EMouseLockMode PreviousLockMode=EMouseLockMode::DoNotLock;
 ESlateVisibility PreviousPanelVisibility=ESlateVisibility::Visible;
 bool bPreviousPanelEnabled=true;
};
