#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "CatrunChapterSelectWidget.generated.h"

/** Owns chapter selection admission and modal lifetime. Designer/BP owns all visuals. */
UCLASS(Abstract, Blueprintable)
class CATRUN_API UCatrunChapterSelectWidget : public UUserWidget
{

	GENERATED_BODY()
public:
	UFUNCTION(BlueprintCallable, Category="Catrun|Chapters")
	static UCatrunChapterSelectWidget* OpenChapterSelection(APlayerController* PlayerController, UWidget* SourcePanel, UWidget* ReturnFocus);
	/** Called by the shared Escape preprocessor before it opens settings. */
	static bool CloseForWorld(UWorld* World);
	UFUNCTION(BlueprintCallable, Category="Catrun|Chapters")
	void CloseChapterSelection();
	UFUNCTION(BlueprintCallable, Category="Catrun|Chapters")
	bool SelectChapter(FName StageId);
	UFUNCTION(BlueprintPure, Category="Catrun|Chapters")
	FCatrunChapterInfo GetChapter(FName StageId) const;
	UFUNCTION(BlueprintPure, Category="Catrun|Chapters")
	bool CanSelectChapter(FName StageId) const;
	UPROPERTY(BlueprintReadOnly, Category="Catrun|Chapters")
	FText StatusMessage;
	UFUNCTION(BlueprintImplementableEvent, Category="Catrun|Chapters")
	void RefreshChapterPresentation();
protected:
	virtual void NativeConstruct() override;
	virtual void NativeDestruct() override;
	virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;
	virtual FReply NativeOnKeyDown(const FGeometry& InGeometry, const FKeyEvent& InKeyEvent) override;
private:
	UFUNCTION() void CheckpointChanged(ECatrunCheckpointState State);
	void RestoreSource();
	bool IsBusy() const;
	TWeakObjectPtr<UWidget> PreviousPanel;
	TWeakObjectPtr<UWidget> PreviousFocus;
	TWeakObjectPtr<UCatrunFlowSession> BoundSession;
	ESlateVisibility PreviousVisibility = ESlateVisibility::Visible;
	bool bPreviousEnabled = true;
	bool bSourceRestored = false;
	bool bObservedTravel = false;
	bool bPreviouslyBusy = false;
};
