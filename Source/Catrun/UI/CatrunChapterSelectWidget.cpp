#include "UI/CatrunChapterSelectWidget.h"

#include "Blueprint/WidgetBlueprintLibrary.h"
#include "Components/Button.h"
#include "Components/ScrollBox.h"
#include "Components/TextBlock.h"
#include "Engine/World.h"
#include "Framework/Application/SlateApplication.h"
#include "GameFramework/PlayerController.h"
#include "Input/Reply.h"
#include "InputCoreTypes.h"

namespace
{
	const FName Stage3Id(TEXT("Stage3"));
	// Latest chapter first: that is where a returning player usually continues.
	const TCHAR* const FocusOrder[] = { TEXT("Stage3"), TEXT("Stage2"), TEXT("Stage1"), TEXT("Tutorial") };
}

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
	Selector->FocusFirstAvailable();
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
	if (auto* Button = Cast<UButton>(GetWidgetFromName(TEXT("Stage3Button"))))
		Button->OnClicked.AddUniqueDynamic(this, &ThisClass::SelectStage3);
	RefreshCards();
}

void UCatrunChapterSelectWidget::SelectStage3() { SelectChapter(Stage3Id); }

void UCatrunChapterSelectWidget::RefreshCards()
{
	RefreshChapterPresentation();
	if (auto* Button = GetWidgetFromName(TEXT("Stage3Button")))
	{
		const FCatrunChapterInfo Chapter = GetChapter(Stage3Id);
		Button->SetIsEnabled(CanSelectChapter(Stage3Id));
		if (auto* Name = Cast<UTextBlock>(GetWidgetFromName(TEXT("Stage3Name"))); Name && !Chapter.DisplayName.IsEmpty())
			Name->SetText(Chapter.DisplayName);
		if (auto* Artwork = GetWidgetFromName(TEXT("Stage3Artwork"))) Artwork->SetRenderOpacity(Chapter.bUnlocked ? 1.f : .46f);
		if (auto* Locked = GetWidgetFromName(TEXT("Stage3Locked")))
			Locked->SetVisibility(Chapter.bUnlocked ? ESlateVisibility::Hidden : ESlateVisibility::HitTestInvisible);
	}
	RefreshUnderlines();
}

void UCatrunChapterSelectWidget::RefreshUnderlines()
{
	const auto Mark = [this](const FString& ButtonName, const FString& UnderlineName)
	{
		const auto* Button = GetWidgetFromName(FName(ButtonName));
		auto* Underline = GetWidgetFromName(FName(UnderlineName));
		if (!Button || !Underline) return;
		const auto Show = Button->GetIsEnabled() && (Button->IsHovered() || Button->HasAnyUserFocus())
			? ESlateVisibility::HitTestInvisible : ESlateVisibility::Hidden;
		if (Underline->GetVisibility() != Show) Underline->SetVisibility(Show);
	};
	for (const TCHAR* Stage : FocusOrder) Mark(FString(Stage) + TEXT("Button"), FString(Stage) + TEXT("Underline"));
	Mark(TEXT("ChapterBack"), TEXT("ChapterBackUnderline"));
}

void UCatrunChapterSelectWidget::FocusFirstAvailable()
{
	auto* PC = GetOwningPlayer();
	if (!PC) return;
	for (const TCHAR* Stage : FocusOrder)
		if (auto* Button = GetWidgetFromName(FName(FString(Stage) + TEXT("Button"))); Button && Button->GetIsEnabled())
		{
			Button->SetUserFocus(PC);
			return;
		}
	if (auto* Back = GetWidgetFromName(TEXT("ChapterBack"))) Back->SetUserFocus(PC);
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
		: NSLOCTEXT("Catrun", "ChapterOpenFailed", "구역을 불러오지 못했습니다. 다시 선택해 주세요.");
	RefreshCards();
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
		RefreshCards();
	}
	RefreshUnderlines();
}

void UCatrunChapterSelectWidget::CheckpointChanged(ECatrunCheckpointState State)
{
	StatusMessage = State == ECatrunCheckpointState::Failed
		? UCatrunLevelFlowLibrary::GetContinueStageLabel(this) : FText::GetEmpty();
	RefreshCards();
}

bool UCatrunChapterSelectWidget::MoveFocus(const FKeyEvent& Event)
{
	// The card list scrolls and keeps directional focus inside itself, so the back button needs an explicit way in and out.
	auto* PC = GetOwningPlayer();
	UWidget* Back = GetWidgetFromName(TEXT("ChapterBack"));
	if (!PC || !Back || !FSlateApplication::IsInitialized()) return false;
	TArray<UWidget*> Ring;
	for (const TCHAR* Stage : { TEXT("Tutorial"), TEXT("Stage1"), TEXT("Stage2"), TEXT("Stage3") })
		if (auto* Button = GetWidgetFromName(FName(FString(Stage) + TEXT("Button"))); Button && Button->GetIsEnabled()) Ring.Add(Button);
	Ring.Add(Back);
	const int32 Index = Ring.IndexOfByPredicate([PC](const UWidget* Widget) { return Widget->HasUserFocus(PC); });
	if (Index == INDEX_NONE)
	{
		// Focus is on the panel itself: only a navigation key re-enters the list. Escape and back keep their own handling.
		if (Event.GetKey() != EKeys::Tab && FSlateApplication::Get().GetNavigationDirectionFromKey(Event) == EUINavigation::Invalid) return false;
		FocusFirstAvailable();
		return true;
	}
	UWidget* Target = nullptr;
	const EUINavigation Direction = FSlateApplication::Get().GetNavigationDirectionFromKey(Event);
	if (Event.GetKey() == EKeys::Tab)
		Target = Ring[(Index + (Event.IsShiftDown() ? Ring.Num() - 1 : 1)) % Ring.Num()];
	else if (Direction == EUINavigation::Up && Ring[Index] == Back)
		Target = Ring.Num() > 1 ? Ring[Ring.Num() - 2] : nullptr;
	else if (Direction == EUINavigation::Down && Ring[Index] != Back)
	{
		// Wrapped rows below the current card keep the normal spatial move.
		const float Bottom = Ring[Index]->GetCachedGeometry().GetAbsolutePositionAtCoordinates(FVector2f(.5f, 1.f)).Y;
		const bool bLowerCard = Ring.ContainsByPredicate([&](const UWidget* Widget)
		{ return Widget != Back && Widget->GetCachedGeometry().GetAbsolutePosition().Y >= Bottom - 1.f; });
		if (!bLowerCard) Target = Back;
	}
	if (!Target) return false;
	Target->SetUserFocus(PC);
	if (auto* Scroll = Cast<UScrollBox>(GetWidgetFromName(TEXT("ChapterCardScroll"))); Scroll && Target != Back)
		Scroll->ScrollWidgetIntoView(Target, false);
	return true;
}

FReply UCatrunChapterSelectWidget::NativeOnPreviewKeyDown(const FGeometry& InGeometry, const FKeyEvent& InKeyEvent)
{
	// A focused button turns navigation keys into a move itself, so they never bubble to NativeOnKeyDown.
	return MoveFocus(InKeyEvent) ? FReply::Handled() : Super::NativeOnPreviewKeyDown(InGeometry, InKeyEvent);
}

FReply UCatrunChapterSelectWidget::NativeOnKeyDown(const FGeometry& InGeometry, const FKeyEvent& InKeyEvent)
{
	if (InKeyEvent.GetKey() == EKeys::Escape || InKeyEvent.GetKey() == EKeys::Gamepad_FaceButton_Right)
	{
		CloseChapterSelection();
		return FReply::Handled();
	}
	return Super::NativeOnKeyDown(InGeometry, InKeyEvent);
}
