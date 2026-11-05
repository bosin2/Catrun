#include "CatrunSettingsSubsystem.h"
#include "CatrunSettingsWidget.h"
#include "CatrunInputBindings.h"
#include "Blueprint/UserWidget.h"
#include "Components/Widget.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "Framework/Application/IInputProcessor.h"
#include "Framework/Application/SlateApplication.h"
#include "Framework/Application/SlateUser.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "Widgets/SViewport.h"
#include "Widgets/Input/SButton.h"
#include "Slate/SGameLayerManager.h"
namespace
{
 class FCatrunSettingsInputProcessor : public IInputProcessor
 {
 public:
  explicit FCatrunSettingsInputProcessor(UCatrunSettingsSubsystem* InOwner) : Owner(InOwner) {}
  TWeakObjectPtr<UCatrunSettingsSubsystem> Owner;
  TSet<FKey> HeldKeys;
  TSet<FKey> SuppressedKeys;
  bool bEscapeHandled=false;
  virtual void Tick(float,FSlateApplication&,TSharedRef<ICursor>) override {}
  virtual bool HandleKeyDownEvent(FSlateApplication&,const FKeyEvent& Event) override
  {
   auto* Settings=Owner.Get();
   if (!Settings || !Settings->OwnsInputFocus()) return false;
   HeldKeys.Add(Event.GetKey());
   if (Event.GetKey()==EKeys::Escape)
    {
    if (Event.IsRepeat()) return bEscapeHandled;
    bEscapeHandled=Settings->HandleEscape();
    return bEscapeHandled;
   }
   return !Settings->GetCurrentSettingsWidget() && SuppressedKeys.Contains(Event.GetKey());
  }
  virtual bool HandleKeyUpEvent(FSlateApplication&,const FKeyEvent& Event) override
  {
   if (Event.GetKey()==EKeys::Escape) bEscapeHandled=false;
   HeldKeys.Remove(Event.GetKey());
   SuppressedKeys.Remove(Event.GetKey());
   return false;
  }
 };
}
void FCatrunSettingsSlateSnapshot::Capture(FSlateApplication& Slate,uint32 InFocusUserIndex)
{
 Focus.Reset();
 CursorCaptor.Reset();
 FocusUserIndex=InFocusUserIndex;
 if (const auto User=Slate.GetUser(InFocusUserIndex)) Focus=User->GetFocusedWidget();
 if (const auto CursorUser=Slate.GetCursorUser())
 {
  CursorUserIndex=CursorUser->GetUserIndex();
  CaptureCursor(CursorUser->GetCursorCaptor(),Slate.IsUsingHighPrecisionMouseMovment());
 }
 else bHighPrecision=false;
}
void FCatrunSettingsSlateSnapshot::CaptureCursor(const TSharedPtr<SWidget>& InCursorCaptor,bool bInHighPrecision)
{
 CursorCaptor=InCursorCaptor;
 bHighPrecision=bInHighPrecision;
 // SButton::OnMouseButtonUp calls Release before OnClicked, and only releases Slate capture in its
 // returned reply. Settings opened inside OnClicked must not later resurrect that completed click.
 if (!bHighPrecision && InCursorCaptor && InCursorCaptor->GetType()==FName(TEXT("SButton")) &&
  !StaticCastSharedPtr<SButton>(InCursorCaptor)->IsPressed()) CursorCaptor.Reset();
}
void FCatrunSettingsSlateSnapshot::RestoreWithCallbacks(TFunctionRef<void()> SuppressViewportAcquisition,
 TFunctionRef<void()> RestoreFocus,TFunctionRef<void(const FReply&)> ProcessCursorReply,
 TFunctionRef<void()> RestoreViewportPolicy) const
{
 SuppressViewportAcquisition();
 RestoreFocus();
 // Ordinary CaptureMouse never disables raw input; release synchronously before restoring any captor.
 ProcessCursorReply(FReply::Handled().ReleaseMouseCapture());
 if (const auto SavedCaptor=CursorCaptor.Pin())
 {
  FReply CaptureReply=FReply::Handled();
  if (bHighPrecision) CaptureReply.UseHighPrecisionMouseMovement(SavedCaptor.ToSharedRef());
  else CaptureReply.CaptureMouse(SavedCaptor.ToSharedRef());
  ProcessCursorReply(CaptureReply);
 }
 RestoreViewportPolicy();
}
void FCatrunSettingsSlateSnapshot::Restore(FSlateApplication& Slate,UGameViewportClient* Viewport,
 bool bRestoreIgnoreInput,EMouseCaptureMode RestoreCaptureMode,const TSharedPtr<SWidget>& FallbackWidget) const
{
 const auto SavedFocus=Focus.Pin();
 RestoreWithCallbacks(
  [&]
  {
   // FSceneViewport::OnFocusReceived must not infer a new capture/raw-input/lock state.
   if (Viewport)
   {
    Viewport->SetIgnoreInput(true);
    Viewport->SetMouseCaptureMode(EMouseCaptureMode::NoCapture);
   }
  },
  [&]
  {
   if (SavedFocus) Slate.SetUserFocus(FocusUserIndex,SavedFocus,EFocusCause::SetDirectly);
   else Slate.ClearUserFocus(FocusUserIndex,EFocusCause::SetDirectly);
  },
  [&](const FReply& Reply)
  {
   FWidgetPath EventPath;
   if (const auto Captor=Reply.GetMouseCaptor()) Slate.GeneratePathToWidgetUnchecked(Captor.ToSharedRef(),EventPath);
   if (!EventPath.IsValid() && SavedFocus) Slate.GeneratePathToWidgetUnchecked(SavedFocus.ToSharedRef(),EventPath);
   if (!EventPath.IsValid() && FallbackWidget) Slate.GeneratePathToWidgetUnchecked(FallbackWidget.ToSharedRef(),EventPath);
   if (EventPath.IsValid()) Slate.ProcessReply(EventPath,Reply,nullptr,nullptr,CursorUserIndex);
  },
  [&]
  {
   // No lock/unlock reply is issued: retain the actual Slate locking-widget path, not merely its policy enum.
   // Restore policy after focus and capture callbacks have completed.
   if (Viewport)
   {
    Viewport->SetIgnoreInput(bRestoreIgnoreInput);
    Viewport->SetMouseCaptureMode(RestoreCaptureMode);
   }
  });
}
UCatrunSettingsSubsystem* UCatrunSettingsSubsystem::Get(const UObject* Context)
{
 auto* World=GEngine ? GEngine->GetWorldFromContextObject(Context,EGetWorldErrorMode::ReturnNull) : nullptr;
 return World ? World->GetSubsystem<UCatrunSettingsSubsystem>() : nullptr;
}
bool UCatrunSettingsSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
 const auto* World=Cast<UWorld>(Outer);
 return World && World->IsGameWorld();
}
void UCatrunSettingsSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
 Super::OnWorldBeginPlay(InWorld);
 if (FSlateApplication::IsInitialized())
 {
  EscapeProcessor=MakeShared<FCatrunSettingsInputProcessor>(this);
  FSlateApplication::Get().RegisterInputPreProcessor(EscapeProcessor,0);
 }
}
void UCatrunSettingsSubsystem::Deinitialize()
{
 CloseSettings();
 if (EscapeProcessor && FSlateApplication::IsInitialized()) FSlateApplication::Get().UnregisterInputPreProcessor(EscapeProcessor);
 EscapeProcessor.Reset();
 Super::Deinitialize();
}
TStatId UCatrunSettingsSubsystem::GetStatId() const
{
 RETURN_QUICK_DECLARE_CYCLE_STAT(UCatrunSettingsSubsystem, STATGROUP_Tickables);
}
void UCatrunSettingsSubsystem::Tick(float)
{
 if (CurrentSettings && (!CurrentSettings->IsInViewport() || !SettingsController.IsValid() || GetWorld()->bIsTearingDown)) CloseSettings();
}
bool UCatrunSettingsSubsystem::OwnsInputFocus() const
{
 if (!GetWorld() || GetWorld()->bIsTearingDown) return false;
 auto* Viewport=GetWorld()->GetGameViewport();
 if (!Viewport) return false;
 if (auto Layers=Viewport->GetGameLayerManager())
  if (Layers->AsWidget()->HasAnyUserFocusOrFocusedDescendants()) return true;
 const auto View=Viewport->GetGameViewportWidget();
 return View && View->HasAnyUserFocusOrFocusedDescendants();
}
bool UCatrunSettingsSubsystem::HandleEscape()
{
 if (!OwnsInputFocus()) return false;
 if (CurrentSettings)
 {
  if (CurrentSettings->IsCapturingBinding()) return false; // SInputKeySelector consumes Escape key-up and cancels only capture.
  CloseSettings();
  return true;
 }
 auto* PC=UGameplayStatics::GetPlayerController(this,0);
 if (!PC || !PC->IsLocalController()) return false;
 return OpenSettings(PC)!=nullptr;
}
void UCatrunSettingsSubsystem::IgnoreHeldKeysUntilRelease()
{
 if (EscapeProcessor)
 {
  auto Processor=StaticCastSharedPtr<FCatrunSettingsInputProcessor>(EscapeProcessor);
  Processor->SuppressedKeys.Append(Processor->HeldKeys);
  if (auto* PC=UGameplayStatics::GetPlayerController(this,0))
   {
    const FCatrunKeyboardBindings Defaults;
    for (const FKey& Key : Defaults.Keys)
     if (PC->IsInputKeyDown(Key)) Processor->SuppressedKeys.Add(Key);
    for (uint8 Index=0;Index<8;++Index)
    {
     const FKey Key=UCatrunInputBindings::GetEffectiveKey(static_cast<ECatrunInputSlot>(Index));
     if (PC->IsInputKeyDown(Key)) Processor->SuppressedKeys.Add(Key);
    }
   }
  Processor->SuppressedKeys.Remove(EKeys::Escape);
 }
}
UCatrunSettingsWidget* UCatrunSettingsSubsystem::OpenSettings(APlayerController* PlayerController,UWidget* SourcePanel)
{
 if (CurrentSettings) return CurrentSettings;
 if (!PlayerController || PlayerController->GetWorld()!=GetWorld() || !PlayerController->IsLocalController() || GetWorld()->bIsTearingDown) return nullptr;
 auto* LP=PlayerController->GetLocalPlayer();
 auto* Viewport=GetWorld()->GetGameViewport();
 if (!LP || !Viewport) return nullptr;
 const auto* Flow=UCatrunLevelFlowSubsystem::Get(this);
 if (Flow && Flow->IsTransitioning()) return nullptr;
 UClass* WidgetClass=LoadClass<UCatrunSettingsWidget>(nullptr,TEXT("/Game/UI/Settings/WBP_Setting.WBP_Setting_C"));
 if (!WidgetClass) return nullptr; // Designer must reparent the existing asset before this runtime is usable.
 auto* Widget=CreateWidget<UCatrunSettingsWidget>(PlayerController,WidgetClass);
 if (!Widget) return nullptr;
 SettingsController=PlayerController;
 SavedViewport=Viewport;
 bPreviousCursor=PlayerController->bShowMouseCursor;
 bPreviousIgnoreInput=Viewport->IgnoreInput();
 bPreviousHideCursor=Viewport->HideCursorDuringCapture();
 PreviousCaptureMode=Viewport->GetMouseCaptureMode();
 PreviousLockMode=Viewport->GetMouseLockMode();
 if (FSlateApplication::IsInitialized())
 {
  if (const auto User=LP->GetSlateUser()) PreviousSlateState.Capture(FSlateApplication::Get(),User->GetUserIndex());
 }
 SettingsSourcePanel=SourcePanel;
 if (SourcePanel)
 {
  bPreviousPanelEnabled=SourcePanel->GetIsEnabled();
  SourcePanel->SetIsEnabled(false);
 }
 const auto* FlowSettings=GetDefault<UCatrunLevelFlowSettings>();
 const bool bGameplay=FlowSettings->FindStageIndex(GetWorld()->GetOutermost()->GetName())!=INDEX_NONE;
 bPauseOwned=bGameplay && !UGameplayStatics::IsGamePaused(this);
 if (bPauseOwned && !UGameplayStatics::SetGamePaused(this,true))
 {
  bPauseOwned=false;
  if (SourcePanel) SourcePanel->SetIsEnabled(bPreviousPanelEnabled);
  SettingsSourcePanel=nullptr;
  SettingsController.Reset();
  return nullptr;
 }
 CurrentSettings=Widget;
 Widget->AddToViewport(2000);
 PlayerController->bShowMouseCursor=true;
 // Preserve the underlying mode rather than guessing it. These are the only input-mode effects changed here.
 Viewport->SetIgnoreInput(true);
 Viewport->SetMouseCaptureMode(EMouseCaptureMode::NoCapture);
 Widget->SetUserFocus(PlayerController);
 if (FSlateApplication::IsInitialized())
 {
  auto& Slate=FSlateApplication::Get();
  FWidgetPath Path;
  if (Slate.GeneratePathToWidgetUnchecked(Widget->TakeWidget(),Path))
   Slate.ProcessReply(Path,FReply::Handled().ReleaseMouseCapture(),nullptr,nullptr,PreviousSlateState.CursorUserIndex);
 }
 IgnoreHeldKeysUntilRelease();
 PlayerController->FlushPressedKeys();
 return Widget;
}
void UCatrunSettingsSubsystem::CloseSettings()
{
 if (!CurrentSettings || bClosing) return;
 TGuardValue<bool> Guard(bClosing,true);
 IgnoreHeldKeysUntilRelease();
 auto* PC=SettingsController.Get();
 auto* Widget=CurrentSettings.Get();
 CurrentSettings=nullptr;
 Widget->RemoveFromParent();
 if (SettingsSourcePanel) SettingsSourcePanel->SetIsEnabled(bPreviousPanelEnabled);
 SettingsSourcePanel=nullptr;
 if (PC)
 {
  PC->bShowMouseCursor=bPreviousCursor;
  PC->FlushPressedKeys();
 }
 if (auto* Viewport=SavedViewport.Get())
 {
  if (FSlateApplication::IsInitialized())
   PreviousSlateState.Restore(FSlateApplication::Get(),Viewport,bPreviousIgnoreInput,PreviousCaptureMode,Viewport->GetGameViewportWidget());
  else
  {
   Viewport->SetIgnoreInput(bPreviousIgnoreInput);
   Viewport->SetMouseCaptureMode(PreviousCaptureMode);
  }
  Viewport->SetMouseLockMode(PreviousLockMode);
  Viewport->SetHideCursorDuringCapture(bPreviousHideCursor);
 }
 if (bPauseOwned && GetWorld() && !GetWorld()->bIsTearingDown) UGameplayStatics::SetGamePaused(this,false);
 bPauseOwned=false;
 SettingsController.Reset();
 SavedViewport.Reset();
 PreviousSlateState=FCatrunSettingsSlateSnapshot();
}
