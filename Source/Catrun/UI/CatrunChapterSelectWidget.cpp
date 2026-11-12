#include "UI/CatrunChapterSelectWidget.h"

#include "Blueprint/WidgetBlueprintLibrary.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Input/Reply.h"
#include "InputCoreTypes.h"

UCatrunChapterSelectWidget* UCatrunChapterSelectWidget::OpenChapterSelection(
	APlayerController* PlayerController, UWidget* SourcePanel, UWidget* ReturnFocus)
{
	if (!IsValid(PlayerController) || !PlayerController->IsLocalController()) return nullptr;
	UWorld* World = PlayerController->GetWorld();
	if (!World || World->bIsTearingDown || !IsValid(SourcePanel) || SourcePanel->GetWorld() != World) return nullptr;
	TArray<UUserWidget*> Existing;
	UWidgetBlueprintLibrary::GetAllWidgetsOfClass(World, Existing, StaticClass(), true);
	for (UUserWidget* Widget : Existing)
		if (Widget->GetWorld() == World) return Cast<UCatrunChapterSelectWidget>(Widget);
	UClass* WidgetClass = LoadClass<UCatrunChapterSelectWidget>(nullptr, TEXT("/Game/UI/Continue/WBP_ChapterSelect.WBP_ChapterSelect_C"));
	if (!WidgetClass) return nullptr;
	auto* Selector = CreateWidget<UCatrunChapterSelectWidget>(PlayerController, WidgetClass);
	if (!Selector) return nullptr;
	Selector->PreviousPanel = SourcePanel;
	Selector->PreviousFocus = ReturnFocus;
	Selector->PreviousVisibility = SourcePanel->GetVisibility();
	Selector->bPreviousEnabled = SourcePanel->GetIsEnabled();
	SourcePanel->SetIsEnabled(false);
	SourcePanel->SetVisibility(ESlateVisibility::Hidden);
	Selector->SetIsFocusable(true);
	Selector->AddToViewport(120);
	Selector->SetUserFocus(PlayerController);
	return Selector;
}

bool UCatrunChapterSelectWidget::CloseForWorld(UWorld* World)
{
	if (!World) return false;
	TArray<UUserWidget*> Widgets;
	UWidgetBlueprintLibrary::GetAllWidgetsOfClass(World, Widgets, StaticClass(), true);
	for (UUserWidget* Widget : Widgets)
	{
		auto* Selector = Cast<UCatrunChapterSelectWidget>(Widget);
		if (Selector && Selector->GetWorld() == World)
		{
			Selector->CloseChapterSelection();
			return true;
		}
	}
	return false;
}

void UCatrunChapterSelectWidget::NativeConstruct()
{
	Super::NativeConstruct();
	BoundSession = UCatrunLevelFlowLibrary::GetFlowSession(this);
	if (BoundSession.IsValid()) BoundSession->OnCheckpointStateChanged.AddUniqueDynamic(this, &ThisClass::CheckpointChanged);
	bPreviouslyBusy = IsBusy();
	StatusMessage = FText::GetEmpty();
	RefreshChapterPresentation();
}

void UCatrunChapterSelectWidget::NativeDestruct()
{
	if (BoundSession.IsValid()) BoundSession->OnCheckpointStateChanged.RemoveDynamic(this, &ThisClass::CheckpointChanged);
	RestoreSource();
	Super::NativeDestruct();
}

void UCatrunChapterSelectWidget::RestoreSource()
{
	if (bSourceRestored) return;
	bSourceRestored = true;
	if (PreviousPanel.IsValid())
	{
		PreviousPanel->SetVisibility(PreviousVisibility);
		PreviousPanel->SetIsEnabled(bPreviousEnabled);
	}
	if (GetWorld() && !GetWorld()->bIsTearingDown && PreviousFocus.IsValid() && GetOwningPlayer())
		PreviousFocus->SetUserFocus(GetOwningPlayer());
}

void UCatrunChapterSelectWidget::CloseChapterSelection()
{
	RestoreSource();
	RemoveFromParent();
}

bool UCatrunChapterSelectWidget::IsBusy() const
{
	const auto* Flow = UCatrunLevelFlowSubsystem::Get(this);
	return (Flow && Flow->IsTransitioning()) || (BoundSession.IsValid() && BoundSession->IsSavePending());
}

FCatrunChapterInfo UCatrunChapterSelectWidget::GetChapter(FName StageId) const
{
	for (const FCatrunChapterInfo& Chapter : UCatrunLevelFlowLibrary::GetChapters(this))
		if (Chapter.StageId == StageId) return Chapter;
	return FCatrunChapterInfo();
}

bool UCatrunChapterSelectWidget::CanSelectChapter(FName StageId) const
{
	return !IsBusy() && UCatrunLevelFlowLibrary::CanContinueStage(this, StageId);
}

bool UCatrunChapterSelectWidget::SelectChapter(FName StageId)
{
	if (!CanSelectChapter(StageId)) return false;
	const bool bAccepted = UCatrunLevelFlowLibrary::ContinueStage(this, StageId);
	bObservedTravel = bAccepted;
	bPreviouslyBusy = IsBusy();
	StatusMessage = bAccepted ? NSLOCTEXT("Catrun", "ChapterLoading", "불러오는 중…")
		: NSLOCTEXT("Catrun", "ChapterOpenFailed", "구간을 불러오지 못했습니다. 다시 선택해 주세요.");
	RefreshChapterPresentation();
	return bAccepted;
}

void UCatrunChapterSelectWidget::NativeTick(const FGeometry& MyGeometry, float InDeltaTime)
{
	Super::NativeTick(MyGeometry, InDeltaTime);
	const bool bBusy = IsBusy();
	if (bBusy != bPreviouslyBusy)
	{
		bPreviouslyBusy = bBusy;
		if (!bBusy && bObservedTravel)
		{
			bObservedTravel = false;
			StatusMessage = NSLOCTEXT("Catrun", "ChapterTravelFailed", "이동하지 못했습니다. 다시 선택해 주세요.");
		}
		RefreshChapterPresentation();
	}
}

void UCatrunChapterSelectWidget::CheckpointChanged(ECatrunCheckpointState State)
{
	StatusMessage = State == ECatrunCheckpointState::Failed
		? UCatrunLevelFlowLibrary::GetContinueStageLabel(this) : FText::GetEmpty();
	RefreshChapterPresentation();
}

FReply UCatrunChapterSelectWidget::NativeOnKeyDown(const FGeometry& InGeometry, const FKeyEvent& InKeyEvent)
{
	if (InKeyEvent.GetKey() == EKeys::Escape)
	{
		CloseChapterSelection();
		return FReply::Handled();
	}
	return Super::NativeOnKeyDown(InGeometry, InKeyEvent);
}
