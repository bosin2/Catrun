#include "CatrunSettingsWidget.h"
#include "CatrunSettingsSubsystem.h"
#include "CatrunUserSettings.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/Button.h"
#include "Components/ComboBoxString.h"
#include "Components/InputKeySelector.h"
#include "Components/ScrollBox.h"
#include "Components/TextBlock.h"
#include "Components/WidgetSwitcher.h"
#include "EnhancedInputSubsystems.h"
#include "Engine/LocalPlayer.h"
#include "GameFramework/PlayerController.h"
#include "Framework/Application/SlateApplication.h"
#include "LevelFlow/CatrunLevelFlow.h"
void UCatrunSettingsWidget::NativeConstruct()
{
 const auto* Settings=UCatrunUserSettings::GetCatrunUserSettings();
 DraftBindings=Settings ? Settings->GetKeyboardBindings() : FCatrunKeyboardBindings();
 Super::NativeConstruct();
 SetIsFocusable(true);
 bStageRestartPending = false;
 if (RestartConfirmPanel) RestartConfirmPanel->SetVisibility(ESlateVisibility::Collapsed);
 if (RestartAccept) RestartAccept->OnClicked.AddUniqueDynamic(this, &ThisClass::ConfirmStageRestart);
 if (RestartCancel) RestartCancel->OnClicked.AddUniqueDynamic(this, &ThisClass::CancelStageRestart);
 if (WidgetTree)
  WidgetTree->ForEachWidget([](UWidget* Widget)
  {
   if (auto* Selector=Cast<UInputKeySelector>(Widget))
   {
    Selector->SetAllowGamepadKeys(false);
    Selector->SetAllowModifierKeys(true); // Raw modifier keys remain valid; combinations are not.
    Selector->SetEscapeKeys({EKeys::Escape});
   }
  });
 OnSettingsDraftInitialized();
}
void UCatrunSettingsWidget::InitializeSettingsDraft()
{
 const auto* Settings=UCatrunUserSettings::GetCatrunUserSettings();
 DraftBindings=Settings ? Settings->GetKeyboardBindings() : FCatrunKeyboardBindings();
 OnSettingsDraftInitialized();
}
void UCatrunSettingsWidget::ResetDraftKeys() { DraftBindings=FCatrunKeyboardBindings(); OnSettingsDraftInitialized(); }
FKey UCatrunSettingsWidget::GetDraftKey(ECatrunInputSlot BindingSlot) const { return DraftBindings.Get(BindingSlot); }
bool UCatrunSettingsWidget::SetDraftKey(ECatrunInputSlot BindingSlot, FKey Key, FText& Error)
{
 const int32 Index=static_cast<int32>(BindingSlot);
 Error=FText::GetEmpty();
 if (!DraftBindings.Keys.IsValidIndex(Index)) { Error=NSLOCTEXT("Catrun","SlotInvalid","올바른 조작을 선택하세요."); return false; }
 if (!UCatrunInputBindings::IsKeyboardKey(Key)) { Error=UCatrunInputBindings::GetInvalidKeyboardKeyMessage(); return false; }
 // Duplicates may exist in a working draft so two controls can be swapped. Apply validates the complete draft atomically.
 DraftBindings.Keys[Index]=Key;
 return true;
}
bool UCatrunSettingsWidget::SetDraftChord(ECatrunInputSlot BindingSlot, FInputChord Chord, FText& Error)
{
 if (Chord.bShift || Chord.bCtrl || Chord.bAlt || Chord.bCmd)
 {
  Error=NSLOCTEXT("Catrun","ChordInvalid","조합 키 대신 키 하나를 지정하세요."); return false;
 }
 return SetDraftKey(BindingSlot,Chord.Key,Error);
}
bool UCatrunSettingsWidget::ValidateDraftKeys(FText& Error) const { return DraftBindings.Validate(Error); }
bool UCatrunSettingsWidget::ApplyDraftKeys(FText& Error)
{
 auto* Settings=UCatrunUserSettings::GetCatrunUserSettings();
 if (!Settings) { Error=NSLOCTEXT("Catrun","SettingsMissing","설정을 불러올 수 없습니다."); return false; }
 if (!Settings->SetKeyboardBindings(DraftBindings,Error)) return false;
 if (auto* PC=GetOwningPlayer())
  if (auto* LP=PC->GetLocalPlayer())
   if (auto* Input=LP->GetSubsystem<UCatrunInputBindingSubsystem>()) Input->RefreshBindings();
 Settings->SaveSettings();
 return true;
}
bool UCatrunSettingsWidget::IsCapturingBinding() const
{
 bool bSelecting=false;
 if (WidgetTree) WidgetTree->ForEachWidget([&](UWidget* Widget)
 {
  if (const auto* Selector=Cast<UInputKeySelector>(Widget)) bSelecting |= Selector->GetIsSelectingKey();
 });
 return bSelecting;
}
void UCatrunSettingsWidget::DismissSettings()
{
 if (auto* Settings=UCatrunSettingsSubsystem::Get(this)) Settings->CloseSettings();
}
bool UCatrunSettingsWidget::RestartFromSettings()
{
 if (!RestartConfirmPanel || !RestartAccept || !RestartCancel) return false;
 if (bStageRestartPending) return true;
 bStageRestartPending = true;
 if (auto* Panel = GetWidgetFromName(TEXT("Panel_Setting")))
 {
  bSettingsWereEnabled = Panel->GetIsEnabled();
  Panel->SetIsEnabled(false);
 }
 RestartConfirmPanel->SetVisibility(ESlateVisibility::Visible);
 RestartCancel->SetKeyboardFocus();
 return true;
}
void UCatrunSettingsWidget::CancelStageRestart()
{
 if (!bStageRestartPending) return;
 bStageRestartPending = false;
 RestartConfirmPanel->SetVisibility(ESlateVisibility::Collapsed);
 if (auto* Panel = GetWidgetFromName(TEXT("Panel_Setting"))) Panel->SetIsEnabled(bSettingsWereEnabled);
 if (auto* Restart = GetWidgetFromName(TEXT("RestartButton"))) Restart->SetKeyboardFocus();
}
void UCatrunSettingsWidget::ConfirmStageRestart()
{
 if (!bStageRestartPending) return;
 CancelStageRestart();
 if (UCatrunLevelFlowLibrary::RestartCurrentStage(this)) return;
 if (auto* Status=Cast<UTextBlock>(GetWidgetFromName(TEXT("SettingsStatus"))))
  Status->SetText(NSLOCTEXT("Catrun","SettingsRestartUnavailable","지금은 다시 시작할 수 없습니다. 잠시 후 다시 시도하세요."));
}
bool UCatrunSettingsWidget::ReturnToMenuFromSettings()
{
 DismissSettings();
 return UCatrunLevelFlowLibrary::ReturnToMainMenu(this);
}
bool UCatrunSettingsWidget::MoveDirectionalFocus(const FKeyEvent& Event)
{
 // The authored ring serves Tab and stops Up/Down, which leaves a gamepad unable to reach most rows.
 auto* PC=GetOwningPlayer();
 if (!PC || !FSlateApplication::IsInitialized()) return false;
 const EUINavigation Direction=FSlateApplication::Get().GetNavigationDirectionFromKey(Event);
 const bool bVertical=Direction==EUINavigation::Up || Direction==EUINavigation::Down;
 const bool bHorizontal=Direction==EUINavigation::Left || Direction==EUINavigation::Right;
 if (!bVertical && !bHorizontal) return false;
 const auto Collect=[this](std::initializer_list<const TCHAR*> Names)
 {
  TArray<UWidget*> Result;
  for (const TCHAR* Name : Names)
  {
   UWidget* Widget=GetWidgetFromName(Name);
   bool bShown=Widget && Widget->GetIsEnabled();
   // The travel buttons stay visible inside a group that is collapsed on the main menu.
   for (const UWidget* Part=Widget; Part && bShown; Part=Part->GetParent()) bShown=Part->IsVisible();
   if (bShown) Result.Add(Widget);
  }
  return Result;
 };
 const auto* Switcher=Cast<UWidgetSwitcher>(GetWidgetFromName(TEXT("CategorySwitcher")));
 const TArray<UWidget*> Categories=Collect({TEXT("ScreenCategoryButton"),TEXT("AudioCategoryButton"),TEXT("ControlsCategoryButton"),TEXT("DeveloperCategoryButton")});
 TArray<UWidget*> Page;
 switch (Switcher ? Switcher->GetActiveWidgetIndex() : INDEX_NONE)
 {
 case 0: Page=Collect({TEXT("WindowModeCombo"),TEXT("QualityCombo"),TEXT("FrameLimitCombo"),TEXT("VSyncCheckBox")}); break;
 case 1: Page=Collect({TEXT("VolumeSlider")}); break;
 case 2: Page=Collect({TEXT("KeyForward"),TEXT("KeyBack"),TEXT("KeyLeft"),TEXT("KeyRight"),TEXT("KeyRun"),TEXT("KeySneak"),TEXT("KeyBell"),TEXT("KeyInteract")}); break;
 case 3: Page=Collect({TEXT("NoArmorCaptureCheckBox")}); break;
 default: break;
 }
 const TArray<UWidget*> Footer=Collect({TEXT("DefaultsButton"),TEXT("RestartButton"),TEXT("MainMenuButton"),TEXT("ApplyButton"),TEXT("CloseButton")});
 const auto Find=[PC](const TArray<UWidget*>& List)
 {
  return List.IndexOfByPredicate([PC](const UWidget* Widget) { return Widget->HasUserFocus(PC) || Widget->HasUserFocusedDescendants(PC); });
 };
 // An open list owns the arrows until it closes.
 for (const UWidget* Widget : Page)
  if (const auto* Combo=Cast<UComboBoxString>(Widget); Combo && Combo->IsOpen()) return false;
 const int32 Step=Direction==EUINavigation::Down || Direction==EUINavigation::Right ? 1 : -1;
 UWidget* Target=nullptr;
 bool bOwned=false;
 if (const int32 Index=Find(Categories); Index!=INDEX_NONE)
 {
  bOwned=bVertical;
  if (bVertical) Target=Categories.IsValidIndex(Index+Step) ? Categories[Index+Step] : Step>0 && Footer.Num() ? Footer[0] : nullptr;
 }
 else if (const int32 Row=Find(Page); Row!=INDEX_NONE)
 {
  bOwned=bVertical;
  if (bVertical) Target=Page.IsValidIndex(Row+Step) ? Page[Row+Step] : Step>0 && Footer.Num() ? Footer[0] : nullptr;
 }
 else if (const int32 Action=Find(Footer); Action!=INDEX_NONE)
 {
  bOwned=true;
  if (bHorizontal) Target=Footer.IsValidIndex(Action+Step) ? Footer[Action+Step] : nullptr;
  else if (Step<0) Target=Page.Num() ? Page.Last() : Categories.Num() ? Categories.Last() : nullptr;
 }
 if (Target)
 {
  Target->SetUserFocus(PC);
  if (auto* Scroll=Cast<UScrollBox>(GetWidgetFromName(TEXT("SettingsBodyScroll"))); Scroll && Page.Contains(Target)) Scroll->ScrollWidgetIntoView(Target,false);
 }
 return bOwned;
}
FReply UCatrunSettingsWidget::NativeOnPreviewKeyDown(const FGeometry& Geometry, const FKeyEvent& Event)
{
 if ((Event.GetKey()==EKeys::Escape || Event.GetKey()==EKeys::Gamepad_FaceButton_Right) && !IsCapturingBinding())
 {
  if (!Event.IsRepeat())
  {
   if (bStageRestartPending) CancelStageRestart();
   else DismissSettings();
  }
  return FReply::Handled();
 }
 if (!IsCapturingBinding() && !bStageRestartPending && MoveDirectionalFocus(Event)) return FReply::Handled();
 return Super::NativeOnPreviewKeyDown(Geometry,Event);
}
