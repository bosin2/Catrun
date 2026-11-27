#include "CatrunSettingsWidget.h"
#include "CatrunSettingsSubsystem.h"
#include "CatrunUserSettings.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/Button.h"
#include "Components/CheckBox.h"
#include "Components/PanelSlot.h"
#include "Components/PanelWidget.h"
#include "Components/VerticalBox.h"
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
namespace
{
 // Copies the authored look of a widget or slot. Hierarchy, slots, navigation objects and event
 // bindings are not copied: the copy gets its own children and its own events.
 void CopyLook(const UObject* Source, UObject* Target)
 {
  for (TFieldIterator<FProperty> It(Source->GetClass()); It; ++It)
  {
   const FProperty* Property = *It;
   if (Property->HasAnyPropertyFlags(CPF_Transient | CPF_InstancedReference | CPF_ContainsInstancedReference)
    || Property->IsA<FMulticastDelegateProperty>() || Property->IsA<FDelegateProperty>()
    || Property->GetFName() == TEXT("Slot") || Property->GetFName() == TEXT("Slots") || Property->GetFName() == TEXT("Content")
    || Property->GetFName() == TEXT("Parent") || Property->GetFName() == TEXT("Navigation")) continue;
   Property->CopyCompleteValue_InContainer(Target, Source);
  }
 }
}
void UCatrunSettingsWidget::NativeOnInitialized()
{
 Super::NativeOnInitialized();
 // Before the Slate widgets are built, so the new rows are in their final place from the start.
 if (IsDesignTime() || !WidgetTree || !UCatrunUserSettings::IsDeveloperModeAvailable()) return;
 ArmorAreaCheckBox = AddDeveloperRow(TEXT("NoArmorCaptureCheckBox"), TEXT("ArmorAreaCheckBox"),
  NSLOCTEXT("Catrun","ArmorAreaDebugLabel","갑옷 이동 영역 보기"));
 if (ArmorAreaCheckBox) ArmorAreaCheckBox->OnCheckStateChanged.AddUniqueDynamic(this, &ThisClass::HandleArmorAreaChanged);
 InfiniteStaminaCheckBox = AddDeveloperRow(TEXT("ArmorAreaCheckBox"), TEXT("InfiniteStaminaCheckBox"),
  NSLOCTEXT("Catrun","InfiniteStaminaLabel","스태미나 무제한"));
 if (InfiniteStaminaCheckBox) InfiniteStaminaCheckBox->OnCheckStateChanged.AddUniqueDynamic(this, &ThisClass::HandleInfiniteStaminaChanged);
}
UWidget* UCatrunSettingsWidget::CloneRowWidget(UWidget* Source, UCheckBox* SourceBox, FName BoxName, const FText& Label, UCheckBox*& OutBox, bool& bLabelSet)
{
 if (!Source || Source->IsA<UUserWidget>()) return nullptr;
 const FName Name = Source == SourceBox ? BoxName : MakeUniqueObjectName(WidgetTree, Source->GetClass(), FName(*(Source->GetName() + TEXT("_") + BoxName.ToString())));
 UWidget* Copy = WidgetTree->ConstructWidget<UWidget>(Source->GetClass(), Name);
 CopyLook(Source, Copy);
 if (Source == SourceBox) OutBox = Cast<UCheckBox>(Copy);
 if (auto* Text = Cast<UTextBlock>(Copy); Text && !bLabelSet)
 {
  Text->SetText(Label);
  bLabelSet = true;
 }
 if (const auto* SourcePanel = Cast<UPanelWidget>(Source))
 {
  auto* Panel = CastChecked<UPanelWidget>(Copy);
  for (int32 I = 0; I < SourcePanel->GetChildrenCount(); ++I)
  {
   UWidget* Child = SourcePanel->GetChildAt(I);
   UWidget* ChildCopy = CloneRowWidget(Child, SourceBox, BoxName, Label, OutBox, bLabelSet);
   if (!ChildCopy) continue;
   if (UPanelSlot* NewSlot = Panel->AddChild(ChildCopy); NewSlot && Child->Slot && NewSlot->GetClass() == Child->Slot->GetClass())
   {
    CopyLook(Child->Slot, NewSlot);
    NewSlot->SynchronizeProperties();
   }
  }
 }
 return Copy;
}
UCheckBox* UCatrunSettingsWidget::AddDeveloperRow(FName AboveBox, FName BoxName, const FText& Label)
{
 // The new row copies the original "갑옷에게 잡히지 않기" row (same look) and goes below AboveBox's row.
 auto* Template = Cast<UCheckBox>(GetWidgetFromName(TEXT("NoArmorCaptureCheckBox")));
 UCheckBox* Above = AboveBox == TEXT("ArmorAreaCheckBox") ? ArmorAreaCheckBox.Get() : Cast<UCheckBox>(GetWidgetFromName(AboveBox));
 if (!Template || !Above) return nullptr;
 const auto RowOf = [](UWidget* Widget)
 {
  // The whole row is the ancestor that sits directly in the vertical list of the developer tab.
  while (Widget->GetParent() && !Widget->GetParent()->IsA<UVerticalBox>()) Widget = Widget->GetParent();
  return Widget;
 };
 UWidget* TemplateRow = RowOf(Template);
 UWidget* AboveRow = RowOf(Above);
 auto* List = Cast<UVerticalBox>(AboveRow->GetParent());
 if (!List || TemplateRow->GetParent() != List) return nullptr;
 UCheckBox* Box = nullptr;
 bool bLabelSet = false;
 UWidget* Copy = CloneRowWidget(TemplateRow, Template, BoxName, Label, Box, bLabelSet);
 if (!Copy || !Box) return nullptr;
 UPanelSlot* NewSlot = List->InsertChildAt(List->GetChildIndex(AboveRow) + 1, Copy);
 if (NewSlot && TemplateRow->Slot && NewSlot->GetClass() == TemplateRow->Slot->GetClass()) { CopyLook(TemplateRow->Slot, NewSlot); NewSlot->SynchronizeProperties(); }
 return Box;
}
void UCatrunSettingsWidget::HandleArmorAreaChanged(bool bIsChecked)
{
 // Immediate, like the row above it: the armor area shows as soon as the box is ticked.
 if (UCatrunUserSettings::IsDeveloperModeAvailable()) UCatrunUserSettings::SetArmorAreaDebugEnabled(bIsChecked);
}
void UCatrunSettingsWidget::HandleInfiniteStaminaChanged(bool bIsChecked)
{
 if (UCatrunUserSettings::IsDeveloperModeAvailable()) UCatrunUserSettings::SetInfiniteStaminaEnabled(bIsChecked);
}
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
 if (ArmorAreaCheckBox) ArmorAreaCheckBox->SetIsChecked(UCatrunUserSettings::IsArmorAreaDebugEnabled());
 if (InfiniteStaminaCheckBox) InfiniteStaminaCheckBox->SetIsChecked(UCatrunUserSettings::IsInfiniteStaminaEnabled());
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
 case 3: Page=Collect({TEXT("NoArmorCaptureCheckBox"),TEXT("ArmorAreaCheckBox"),TEXT("InfiniteStaminaCheckBox")}); break;
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
