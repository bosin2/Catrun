#pragma once
#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "CatrunInputBindings.h"
#include "Framework/Commands/InputChord.h"
#include "CatrunSettingsWidget.generated.h"
class UBorder;
class UButton;
class UCheckBox;
/** Designer-owned WBP_Setting base. Existing BP ParentMenuWidget/ReturnFocusWidget/CloseSettings names are intentionally untouched. */
UCLASS(Abstract, Blueprintable)
class CATRUN_API UCatrunSettingsWidget : public UUserWidget
{
 GENERATED_BODY()
public:
 UFUNCTION(BlueprintCallable, Category="Catrun|Settings") void InitializeSettingsDraft();
 UFUNCTION(BlueprintCallable, Category="Catrun|Settings") void ResetDraftKeys();
 UFUNCTION(BlueprintPure, Category="Catrun|Settings") FKey GetDraftKey(ECatrunInputSlot BindingSlot) const;
 UFUNCTION(BlueprintCallable, Category="Catrun|Settings") bool SetDraftKey(ECatrunInputSlot BindingSlot, FKey Key, FText& Error);
 UFUNCTION(BlueprintCallable, Category="Catrun|Settings") bool SetDraftChord(ECatrunInputSlot BindingSlot, FInputChord Chord, FText& Error);
 UFUNCTION(BlueprintPure, Category="Catrun|Settings") bool ValidateDraftKeys(FText& Error) const;
 UFUNCTION(BlueprintCallable, Category="Catrun|Settings") bool ApplyDraftKeys(FText& Error);
 UFUNCTION(BlueprintCallable, Category="Catrun|Settings") void DismissSettings();
 UFUNCTION(BlueprintCallable, Category="Catrun|Settings") bool RestartFromSettings();
 UFUNCTION(BlueprintCallable, Category="Catrun|Settings") void ConfirmStageRestart();
 UFUNCTION(BlueprintCallable, Category="Catrun|Settings") void CancelStageRestart();
 bool IsStageRestartPending() const { return bStageRestartPending; }
 UFUNCTION(BlueprintCallable, Category="Catrun|Settings") bool ReturnToMenuFromSettings();
 UFUNCTION(BlueprintPure, Category="Catrun|Settings") bool IsCapturingBinding() const;
 UFUNCTION(BlueprintImplementableEvent, Category="Catrun|Settings") void OnSettingsDraftInitialized();
protected:
 virtual void NativeOnInitialized() override;
 virtual void NativeConstruct() override;
 virtual FReply NativeOnPreviewKeyDown(const FGeometry& Geometry, const FKeyEvent& Event) override;
private:
 UPROPERTY(meta=(BindWidgetOptional)) TObjectPtr<UBorder> RestartConfirmPanel;
 UPROPERTY(meta=(BindWidgetOptional)) TObjectPtr<UButton> RestartAccept;
 UPROPERTY(meta=(BindWidgetOptional)) TObjectPtr<UButton> RestartCancel;
 bool MoveDirectionalFocus(const FKeyEvent& Event);
 /** Developer tab: copies of the "갑옷에게 잡히지 않기" row (same look), each placed below AboveBox's row. */
 UCheckBox* AddDeveloperRow(FName AboveBox, FName BoxName, const FText& Label);
 UWidget* CloneRowWidget(UWidget* Source, UCheckBox* SourceBox, FName BoxName, const FText& Label, UCheckBox*& OutBox, bool& bLabelSet);
 UFUNCTION() void HandleArmorAreaChanged(bool bIsChecked);
 UFUNCTION() void HandleInfiniteStaminaChanged(bool bIsChecked);
 UPROPERTY(Transient) TObjectPtr<UCheckBox> ArmorAreaCheckBox;
 UPROPERTY(Transient) TObjectPtr<UCheckBox> InfiniteStaminaCheckBox;
 bool bStageRestartPending = false;
 bool bSettingsWereEnabled = true;
 UPROPERTY(Transient) FCatrunKeyboardBindings DraftBindings;
};
