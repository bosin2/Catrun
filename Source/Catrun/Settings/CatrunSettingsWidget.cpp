#include "CatrunSettingsWidget.h"
#include "CatrunSettingsSubsystem.h"
#include "CatrunUserSettings.h"
#include "Blueprint/WidgetTree.h"
#include "Components/InputKeySelector.h"
#include "EnhancedInputSubsystems.h"
#include "Engine/LocalPlayer.h"
#include "GameFramework/PlayerController.h"
#include "LevelFlow/CatrunLevelFlow.h"
void UCatrunSettingsWidget::NativeConstruct()
{
 const auto* Settings=UCatrunUserSettings::GetCatrunUserSettings();
 DraftBindings=Settings ? Settings->GetKeyboardBindings() : FCatrunKeyboardBindings();
 Super::NativeConstruct();
 SetIsFocusable(true);
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
 if (!UCatrunInputBindings::IsKeyboardKey(Key)) { Error=NSLOCTEXT("Catrun","KeyInvalid","Esc를 제외한 키보드 키 하나를 지정하세요."); return false; }
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
 DismissSettings();
 return UCatrunLevelFlowLibrary::RestartCurrentStage(this);
}
bool UCatrunSettingsWidget::ReturnToMenuFromSettings()
{
 DismissSettings();
 return UCatrunLevelFlowLibrary::ReturnToMainMenu(this);
}
FReply UCatrunSettingsWidget::NativeOnPreviewKeyDown(const FGeometry& Geometry, const FKeyEvent& Event)
{
 if (Event.GetKey()==EKeys::Escape && !IsCapturingBinding())
 {
  if (!Event.IsRepeat()) DismissSettings();
  return FReply::Handled();
 }
 return Super::NativeOnPreviewKeyDown(Geometry,Event);
}
