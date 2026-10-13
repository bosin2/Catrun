#include "CatrunNotice.h"

#include "Blueprint/WidgetTree.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/TextBlock.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "Styling/CoreStyle.h"
#include "TimerManager.h"

TSharedRef<SWidget> UCatrunNoticeWidget::RebuildWidget()
{
	if (WidgetTree && !WidgetTree->RootWidget)
	{
		UCanvasPanel* Root = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), TEXT("Root"));
		WidgetTree->RootWidget = Root;

		TextBlock = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("Text"));
		TextBlock->SetFont(FCoreStyle::GetDefaultFontStyle("Bold", 28));
		TextBlock->SetColorAndOpacity(FSlateColor(FLinearColor::White));
		TextBlock->SetShadowOffset(FVector2D(2.f, 2.f));
		TextBlock->SetShadowColorAndOpacity(FLinearColor(0.f, 0.f, 0.f, 0.8f));
		TextBlock->SetJustification(ETextJustify::Center);

		if (UCanvasPanelSlot* TextSlot = Root->AddChildToCanvas(TextBlock))
		{
			TextSlot->SetAnchors(FAnchors(0.5f, 0.82f)); // bottom middle of the screen
			TextSlot->SetAlignment(FVector2D(0.5f, 0.5f));
			TextSlot->SetAutoSize(true);
		}
	}
	return Super::RebuildWidget();
}

void UCatrunNoticeWidget::SetNoticeText(const FText& Text)
{
	if (TextBlock)
	{
		TextBlock->SetText(Text);
	}
}

UCatrunNoticeSubsystem* UCatrunNoticeSubsystem::Get(const UObject* WorldContextObject)
{
	const UWorld* World = GEngine ? GEngine->GetWorldFromContextObject(WorldContextObject, EGetWorldErrorMode::ReturnNull) : nullptr;
	return World ? World->GetSubsystem<UCatrunNoticeSubsystem>() : nullptr;
}

bool UCatrunNoticeSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	const UWorld* World = Cast<UWorld>(Outer);
	return World && World->IsGameWorld();
}

void UCatrunNoticeSubsystem::ShowNotice(const FText& Text, float Duration)
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	if (!Widget)
	{
		APlayerController* Controller = UGameplayStatics::GetPlayerController(World, 0);
		if (!Controller)
		{
			return;
		}
		Widget = CreateWidget<UCatrunNoticeWidget>(Controller, UCatrunNoticeWidget::StaticClass());
		if (!Widget)
		{
			return;
		}
		Widget->AddToViewport(100);
	}
	Widget->SetNoticeText(Text);
	Widget->SetVisibility(ESlateVisibility::HitTestInvisible);

	World->GetTimerManager().SetTimer(HideTimer, this, &UCatrunNoticeSubsystem::HideNotice, FMath::Max(Duration, 0.1f), false);
}

void UCatrunNoticeSubsystem::HideNotice()
{
	if (Widget)
	{
		Widget->SetVisibility(ESlateVisibility::Collapsed);
	}
}
