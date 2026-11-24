#include "CatrunSettingsSubsystem.h"
#include "CatrunSettingsWidget.h"
#include "CatrunInputBindings.h"
#include "UI/CatrunChapterSelectWidget.h"
#include "Blueprint/UserWidget.h"
#include "Blueprint/WidgetBlueprintLibrary.h"
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
#include "LevelFlow/CatrunPlayHUD.h"
#include "Widgets/SViewport.h"
#include "Widgets/Input/SButton.h"
#include "Slate/SGameLayerManager.h"
namespace
{
 UWidget* FindMenuSourcePanel(APlayerController* PlayerController)
 {
  const auto* FlowSettings=GetDefault<UCatrunLevelFlowSettings>();
  const FString MapPackage=UWorld::RemovePIEPrefix(PlayerController->GetWorld()->GetOutermost()->GetName());
  if (MapPackage!=FlowSettings->MainMenuMap.ToSoftObjectPath().GetLongPackageName()) return nullptr;
  auto* MenuClass=FSoftClassPath(TEXT("/Game/UI/WBP_MainMenu.WBP_MainMenu_C")).ResolveClass();
  TArray<UUserWidget*> MenuWidgets;
  UWidgetBlueprintLibrary::GetAllWidgetsOfClass(PlayerController,MenuWidgets,MenuClass,true);
  for (auto* Menu : MenuWidgets)
   if (Menu->GetOwningPlayer()==PlayerController) return Menu;
  return nullptr;
 }

 class FCatrunSettingsInputProcessor : public IInputProcessor
 {
 public:
  explicit FCatrunSettingsInputProcessor(UCatrunSettingsSubsystem* InOwner) : Owner(InOwner) {}
  TWeakObjectPtr<UCatrunSettingsSubsystem> Owner;
  TSet<FKey> HeldKeys;
  TSet<FKey> SuppressedKeys;
  bool bEscapeHandled=false;
  virtual void Tick(float,FSlateApplication&,TSharedRef<ICursor>) override {}
  virtual bool HandleKeyDownEvent(FSlateApplication& Slate,const FKeyEvent& Event) override
  {
   auto* Settings=Owner.Get();
   if (!Settings || !Settings->OwnsInputFocus()) return false;
   // A fresh press proves the prior hold ended, even if its key-up occurred outside this viewport.
   if (!Event.IsRepeat()) SuppressedKeys.Remove(Event.GetKey());
   HeldKeys.Add(Event.GetKey());
   const auto* Widget=Settings->GetCurrentSettingsWidget();
   if ((Slate.GetNavigationDirectionFromKey(Event)!=EUINavigation::Invalid ||
    Slate.GetNavigationActionFromKey(Event)==EUINavigationAction::Accept) &&
    Settings->OwnsInputFocus(Event.GetUserIndex()) && (!Widget || !Widget->IsCapturingBinding()))
    NavigationUsers.Add(Event.GetUserIndex());
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
  virtual bool HandleMouseMoveEvent(FSlateApplication& Slate,const FPointerEvent& Event) override
  {
   if (!Event.GetCursorDelta().IsNearlyZero()) RecordPointerInput(Slate,Event);
   return false;
  }
  virtual bool HandleMouseButtonDownEvent(FSlateApplication& Slate,const FPointerEvent& Event) override
  {
   RecordPointerInput(Slate,Event);
   return false;
  }
  virtual bool HandleMouseButtonDoubleClickEvent(FSlateApplication& Slate,const FPointerEvent& Event) override
  {
   return HandleMouseButtonDownEvent(Slate,Event);
  }
  bool IsNavigationFocused(const SWidget& Widget,int32 UserIndex) const
  {
   return NavigationUsers.Contains(UserIndex) &&
    (Widget.HasUserFocus(UserIndex).IsSet() || Widget.HasUserFocusedDescendants(UserIndex));
  }
 private:
  TSet<int32> NavigationUsers;
  void RecordPointerInput(FSlateApplication& Slate,const FPointerEvent& Event)
  {
   const int32 UserIndex=Event.GetUserIndex();
   const auto* Settings=Owner.Get();
   if (!Settings || !NavigationUsers.Contains(UserIndex)) return;
   if (Settings->OwnsInputFocus(UserIndex))
   {
    NavigationUsers.Remove(UserIndex);
    return;
   }
   // A pointer can return to this game viewport before Slate transfers user focus to it.
   const auto* World=Settings->GetWorld();
   const auto* Viewport=World && !World->bIsTearingDown ? World->GetGameViewport() : nullptr;
   if (!Viewport) return;
   const FWidgetPath Path=Slate.LocateWindowUnderMouse(Event.GetScreenSpacePosition(),Slate.GetInteractiveTopLevelWindows(),false,UserIndex);
   const auto Layers=Viewport->GetGameLayerManager();
   const auto View=Viewport->GetGameViewportWidget();
   if ((Layers && Path.ContainsWidget(&Layers->AsWidget().Get())) || (View && Path.ContainsWidget(View.Get())))
    NavigationUsers.Remove(UserIndex);
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
bool UCatrunSettingsSubsystem::IsNavigationFocused(UWidget* Widget)
{
 if (!Widget || !FSlateApplication::IsInitialized()) return false;
 const auto* Settings=Get(Widget);
 if (!Settings || !Settings->InputProcessor) return false;
 const auto* LocalPlayer=Widget->GetOwningLocalPlayer();
 const auto User=LocalPlayer ? LocalPlayer->GetSlateUser() : nullptr;
 const auto SlateWidget=Widget->GetCachedWidget();
 return User && SlateWidget && StaticCastSharedPtr<FCatrunSettingsInputProcessor>(Settings->InputProcessor)->
  IsNavigationFocused(*SlateWidget,User->GetUserIndex());
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
  InputProcessor=MakeShared<FCatrunSettingsInputProcessor>(this);
  FSlateApplication::Get().RegisterInputPreProcessor(InputProcessor,0);
 }
}
void UCatrunSettingsSubsystem::Deinitialize()
{
 CloseSettings();
 if (InputProcessor && FSlateApplication::IsInitialized()) FSlateApplication::Get().UnregisterInputPreProcessor(InputProcessor);
 InputProcessor.Reset();
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
bool UCatrunSettingsSubsystem::OwnsInputFocus(int32 SlateUserIndex) const
{
 if (!GetWorld() || GetWorld()->bIsTearingDown) return false;
 auto* Viewport=GetWorld()->GetGameViewport();
 if (!Viewport) return false;
 const auto HasFocus=[SlateUserIndex](const SWidget& Widget)
 {
  if (SlateUserIndex==INDEX_NONE) return Widget.HasAnyUserFocusOrFocusedDescendants();
  return Widget.HasUserFocus(SlateUserIndex).IsSet() || Widget.HasUserFocusedDescendants(SlateUserIndex);
 };
 if (auto Layers=Viewport->GetGameLayerManager())
  if (HasFocus(*Layers->AsWidget())) return true;
 const auto View=Viewport->GetGameViewportWidget();
 return View && HasFocus(*View);
}
bool UCatrunSettingsSubsystem::HandleEscape()
{
 if (!OwnsInputFocus()) return false;
 if (!CurrentSettings && UCatrunChapterSelectWidget::CloseForWorld(GetWorld())) return true;
 if (CurrentSettings)
 {
  if (CurrentSettings->IsCapturingBinding()) return false; // SInputKeySelector consumes Escape key-up and cancels only capture.
  if (CurrentSettings->IsStageRestartPending()) { CurrentSettings->CancelStageRestart(); return true; }
  CloseSettings();
  return true;
 }
 auto* PC=UGameplayStatics::GetPlayerController(this,0);
 if (!PC || !PC->IsLocalController()) return false;
 // The fallback panel can own the gameplay viewport when explicitly opened.
 // Cancel its prompt before the shared Escape preprocessor opens Settings over it.
 TArray<UUserWidget*> HUDs;
 UWidgetBlueprintLibrary::GetAllWidgetsOfClass(this,HUDs,UCatrunPlayHUD::StaticClass(),true);
 for (UUserWidget* Widget : HUDs)
 {
  auto* HUD=CastChecked<UCatrunPlayHUD>(Widget);
  if (HUD->GetOwningPlayer()==PC && HUD->bMenuOpen)
  {
   const bool bReturnToPauseMenu=HUD->bConfirmRestart;
   HUD->SetMenuOpen(bReturnToPauseMenu);
   return true;
  }
 }
 return OpenSettings(PC,FindMenuSourcePanel(PC))!=nullptr;
}
void UCatrunSettingsSubsystem::IgnoreHeldKeysUntilRelease()
{
 if (InputProcessor)
 {
  auto Processor=StaticCastSharedPtr<FCatrunSettingsInputProcessor>(InputProcessor);
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
void UCatrunSettingsSubsystem::SuspendSourcePanel(UWidget* Panel)
{
 if (!Panel) return;
 SettingsSourcePanel=Panel;
 PreviousPanelVisibility=Panel->GetVisibility();
 bPreviousPanelEnabled=Panel->GetIsEnabled();
 Panel->SetVisibility(ESlateVisibility::Hidden);
 Panel->SetIsEnabled(false);
}
void UCatrunSettingsSubsystem::RestoreSourcePanel()
{
 if (!SettingsSourcePanel) return;
 SettingsSourcePanel->SetIsEnabled(bPreviousPanelEnabled);
 SettingsSourcePanel->SetVisibility(PreviousPanelVisibility);
 SettingsSourcePanel=nullptr;
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
 SuspendSourcePanel(SourcePanel);
 const auto* FlowSettings=GetDefault<UCatrunLevelFlowSettings>();
 const bool bGameplay=FlowSettings->FindStageIndex(GetWorld()->GetOutermost()->GetName())!=INDEX_NONE;
 bPauseOwned=bGameplay && !UGameplayStatics::IsGamePaused(this);
 if (bPauseOwned && !UGameplayStatics::SetGamePaused(this,true))
 {
  bPauseOwned=false;
  RestoreSourcePanel();
  SettingsController.Reset();
  SavedViewport.Reset();
  PreviousSlateState=FCatrunSettingsSlateSnapshot();
  return nullptr;
 }
 CurrentSettings=Widget;
 Widget->AddToViewport(2000);
 if (!Widget->IsInViewport())
 {
  CloseSettings();
  return nullptr;
 }
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
 OnSettingsOpened.Broadcast();
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
 RestoreSourcePanel();
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

#if WITH_DEV_AUTOMATION_TESTS
#include "Components/Border.h"
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/SVirtualWindow.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunSettingsNavigationFocusTest,"Catrun.Settings.NavigationFocusPresentation",
 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunSettingsNavigationFocusTest::RunTest(const FString&)
{
 if (!TestTrue(TEXT("Slate application is initialized"),FSlateApplication::IsInitialized())) return false;
 auto& Slate=FSlateApplication::Get();
 const auto User=Slate.FindOrCreateVirtualUser(941);
 const uint32 UserIndex=User->GetUserIndex();
 const auto Button=SNew(SButton);
 const auto Row=SNew(SBox)[Button];
 const auto Layers=SNew(SGameLayerManager)[Row];
 const auto Window=SNew(SVirtualWindow);
 Window->SetContent(Layers);
 Slate.RegisterVirtualWindow(Window);
 ON_SCOPE_EXIT
 {
  Slate.ClearUserFocus(UserIndex,EFocusCause::SetDirectly);
  Slate.UnregisterVirtualWindow(Window);
 };

 const auto Init=UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false);
 auto* World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Init);
 if (!TestNotNull(TEXT("Settings test world"),World)) return false;
 auto& Context=GEngine->CreateNewWorldContext(EWorldType::Game);
 Context.SetCurrentWorld(World);
 auto* Viewport=NewObject<UGameViewportClient>(GEngine);
 Context.GameViewport=Viewport;
 PRAGMA_DISABLE_DEPRECATION_WARNINGS
 Viewport->SetGameLayerManager(Layers);
 PRAGMA_ENABLE_DEPRECATION_WARNINGS
 ON_SCOPE_EXIT
 {
  World->DestroyWorld(false);
  GEngine->DestroyWorldContext(World);
 };
 auto* Settings=World->GetSubsystem<UCatrunSettingsSubsystem>();
 if (!TestNotNull(TEXT("Settings subsystem"),Settings)) return false;
 FCatrunSettingsInputProcessor Processor(Settings);
 const FKeyEvent Tab(EKeys::Tab,FModifierKeysState(),UserIndex,false,0,0);
 const TSet<FKey> Pressed={EKeys::LeftMouseButton};
 const FPointerEvent Click(UserIndex,0,FVector2f(10,10),FVector2f(10,10),Pressed,EKeys::LeftMouseButton,0,FModifierKeysState());
 const TSet<FKey> Released;
 const FPointerEvent Move(UserIndex,0,FVector2f(20,10),FVector2f(10,10),Released,FKey(),0,FModifierKeysState());

 if (!TestTrue(TEXT("Button receives genuine Slate focus"),Slate.SetUserFocus(UserIndex,Button,EFocusCause::Mouse))) return false;
 TestFalse(TEXT("Pointer focus alone does not highlight a row"),Processor.IsNavigationFocused(*Row,UserIndex));
 TestFalse(TEXT("The processor leaves Tab available to Slate"),Processor.HandleKeyDownEvent(Slate,Tab));
 // Reproduce Slate moving navigation focus to the button, then receiving a click on the same path.
 Slate.ClearUserFocus(UserIndex,EFocusCause::SetDirectly);
 if (!TestTrue(TEXT("Navigation focuses the button"),Slate.SetUserFocus(UserIndex,Button,EFocusCause::Navigation))) return false;
 TestTrue(TEXT("Navigation highlights both the focused button and its row"),
  Processor.IsNavigationFocused(*Button,UserIndex) && Processor.IsNavigationFocused(*Row,UserIndex));
 TestFalse(TEXT("The processor leaves the same-target click available to Slate"),Processor.HandleMouseButtonDownEvent(Slate,Click));
 Slate.SetUserFocus(UserIndex,Button,EFocusCause::Mouse);
 TestTrue(TEXT("A same-target click keeps actual Slate focus"),Slate.GetUserFocusedWidget(UserIndex)==Button);
 TestFalse(TEXT("The same-target click clears the navigation underline"),Processor.IsNavigationFocused(*Row,UserIndex));
 Processor.HandleKeyDownEvent(Slate,Tab);
 TestTrue(TEXT("Keyboard navigation can highlight the existing focus again"),Processor.IsNavigationFocused(*Row,UserIndex));
 TestFalse(TEXT("The processor leaves pointer movement available to Slate"),Processor.HandleMouseMoveEvent(Slate,Move));
 TestFalse(TEXT("Pointer movement clears the navigation underline"),Processor.IsNavigationFocused(*Row,UserIndex));

 const FKeyEvent MovementDown(EKeys::W,FModifierKeysState(),UserIndex,false,0,0);
 const FKeyEvent MovementRepeat(EKeys::W,FModifierKeysState(),UserIndex,true,0,0);
 Processor.HeldKeys.Add(EKeys::W);
 Processor.SuppressedKeys.Add(EKeys::W);
 TestTrue(TEXT("A genuinely held movement key still consumes repeats"),Processor.HandleKeyDownEvent(Slate,MovementRepeat));
 // Simulate releasing W while this viewport does not receive the key-up, then pressing it again after focus returns.
 TestFalse(TEXT("A fresh movement press after a missed release reaches gameplay"),Processor.HandleKeyDownEvent(Slate,MovementDown));
 TestFalse(TEXT("The fresh press clears stale movement suppression"),Processor.SuppressedKeys.Contains(EKeys::W));
 TestFalse(TEXT("Repeats for the new movement press reach gameplay"),Processor.HandleKeyDownEvent(Slate,MovementRepeat));
 Processor.SuppressedKeys.Add(EKeys::W);
 TestFalse(TEXT("The processor leaves a normal movement release available to Slate"),Processor.HandleKeyUpEvent(Slate,MovementDown));
 TestFalse(TEXT("A normal movement release clears held and suppressed state"),
  Processor.HeldKeys.Contains(EKeys::W) || Processor.SuppressedKeys.Contains(EKeys::W));
 return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunSettingsSourcePanelRestorationTest,"Catrun.Settings.SourcePanelStateRestoration",
 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunSettingsSourcePanelRestorationTest::RunTest(const FString&)
{
 auto* Settings=NewObject<UCatrunSettingsSubsystem>(GetTransientPackage());
 auto* Panel=NewObject<UBorder>();
 for (const auto Visibility : {ESlateVisibility::Visible,ESlateVisibility::Hidden,ESlateVisibility::Collapsed,
  ESlateVisibility::HitTestInvisible,ESlateVisibility::SelfHitTestInvisible})
  for (const bool bEnabled : {false,true})
  {
   Panel->SetVisibility(Visibility);
   Panel->SetIsEnabled(bEnabled);
   Settings->SuspendSourcePanel(Panel);
   TestTrue(TEXT("An open modal hides the source panel"),Panel->GetVisibility()==ESlateVisibility::Hidden);
   TestFalse(TEXT("An open modal disables the source panel"),Panel->GetIsEnabled());
   Settings->RestoreSourcePanel();
   TestTrue(TEXT("The modal restores the exact original visibility"),Panel->GetVisibility()==Visibility);
   TestEqual(TEXT("The modal restores the exact original enabled state"),Panel->GetIsEnabled(),bEnabled);
  }
 Settings->SuspendSourcePanel(nullptr);
 Settings->RestoreSourcePanel();
 TestTrue(TEXT("A session without a source panel leaves other UI alone"),
  Panel->GetVisibility()==ESlateVisibility::SelfHitTestInvisible && Panel->GetIsEnabled());
 return true;
}
#endif
