#include "CatrunNotice.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "UI/CatrunHUDStyle.h"

#include "Blueprint/WidgetTree.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/TextBlock.h"
#include "Engine/Font.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "Styling/CoreStyle.h"
#include "TimerManager.h"

namespace
{
	// Above the basket prompt (83%), below the cat. Long copy wraps instead of leaving a narrow viewport.
	constexpr float NoticeAnchorY = .73f;
	constexpr float NoticeWrapWidth = 960.f;

	FSlateFontInfo NoticeFont(float Size)
	{
		if (const auto* Font = LoadObject<UFont>(nullptr, TEXT("/Game/Environment/Font/HSBombaram3_0_Regular_Font.HSBombaram3_0_Regular_Font")))
			return FSlateFontInfo(Font, Size, TEXT("Default"));
		return FCoreStyle::GetDefaultFontStyle("Bold", Size);
	}
}

TSharedRef<SWidget> UCatrunNoticeWidget::RebuildWidget()
{
	if (WidgetTree && !WidgetTree->RootWidget)
	{
		UCanvasPanel* Root = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), TEXT("Root"));
		WidgetTree->RootWidget = Root;

		TextBlock = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("Text"));
		TextBlock->SetFont(NoticeFont(28.f));
		TextBlock->SetColorAndOpacity(FSlateColor(CatrunHUDStyle::Text));
		TextBlock->SetShadowOffset(FVector2D(1.f, 1.5f));
		TextBlock->SetShadowColorAndOpacity(FLinearColor(0.f, 0.f, 0.f, 0.8f));
		TextBlock->SetJustification(ETextJustify::Center);
		TextBlock->SetWrapTextAt(NoticeWrapWidth);
		TextBlock->SetText(PendingText);

		// The same ink plate as the minimap keeps the line readable over candlelight and pale floors.
		Plate = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), TEXT("Plate"));
		FSlateRoundedBoxBrush PlateBrush(CatrunHUDStyle::Ink.CopyWithNewOpacity(.62f), 4.f);
		Plate->SetBrush(PlateBrush);
		// This face keeps about twenty units of empty descent under each line; the padding centers the visible glyphs.
		Plate->SetPadding(FMargin(26.f, 19.f, 26.f, 0.f));
		Plate->SetContent(TextBlock);
		if (UCanvasPanelSlot* PlateSlot = Root->AddChildToCanvas(Plate))
		{
			PlateSlot->SetAnchors(FAnchors(0.5f, NoticeAnchorY));
			PlateSlot->SetAlignment(FVector2D(0.5f, 0.5f));
			PlateSlot->SetAutoSize(true);
		}
	}
	return Super::RebuildWidget();
}

void UCatrunNoticeWidget::SetNoticeText(const FText& Text)
{
	PendingText = Text;
	if (TextBlock)
	{
		TextBlock->SetText(Text);
	}
}

void UCatrunNoticeWidget::NativeTick(const FGeometry& Geometry, float DeltaSeconds)
{
	Super::NativeTick(Geometry, DeltaSeconds);
	const bool bReadable = RefreshPresentation() && IsVisible();
	// A frame that restores presentation can still carry elapsed time from a hidden frame.
	if (bReadable && bWasReadable && RemainingReadableSeconds > 0.f)
	{
		RemainingReadableSeconds -= DeltaSeconds;
		if (RemainingReadableSeconds <= 0.f) SetVisibility(ESlateVisibility::Collapsed);
	}
	bWasReadable = bReadable;
}

void UCatrunNoticeWidget::SetNoticePolicy(ECatrunNoticePolicy Policy, float Duration)
{
	NoticePolicy = Policy;
	RemainingReadableSeconds = Policy == ECatrunNoticePolicy::DeferredGameplay ? Duration : 0.f;
	bWasReadable = false;
	RefreshPresentation();
}

bool UCatrunNoticeWidget::RefreshPresentation()
{
	const bool bHide = NoticePolicy != ECatrunNoticePolicy::StageTimeout
		&& (NoticePolicy == ECatrunNoticePolicy::BlockedRecovery
			? UCatrunLevelFlowLibrary::ShouldHideRecoveryNotice(this)
			: UCatrunLevelFlowLibrary::ShouldHideGameplayHUD(this));
	SetRenderOpacity(bHide ? 0.f : 1.f);
	return !bHide;
}

void UCatrunNoticeWidget::SetScreenAnchor(FVector2D Anchor)
{
	if (Plate)
		if (auto* PlateSlot = Cast<UCanvasPanelSlot>(Plate->Slot)) PlateSlot->SetAnchors(FAnchors(Anchor.X, Anchor.Y));
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

void UCatrunNoticeSubsystem::Deinitialize()
{
	if (GetWorld()) GetWorld()->GetTimerManager().ClearTimer(HideTimer);
	if (Widget) Widget->RemoveFromParent();
	Widget = nullptr;
	Super::Deinitialize();
}

FText UCatrunNoticeSubsystem::BellDeniedText()
{
	return NSLOCTEXT("Catrun", "BellDeniedExact", "방울을 울릴 수 없습니다");
}

void UCatrunNoticeLibrary::ShowBottomNotice(const UObject* Context, const FText& Text, float Duration)
{
	if (auto* Notice = UCatrunNoticeSubsystem::Get(Context)) Notice->ShowNotice(Text, Duration);
}

void UCatrunNoticeLibrary::ShowBellDenied(const UObject* Context, float Duration)
{
	ShowBottomNotice(Context, UCatrunNoticeSubsystem::BellDeniedText(), Duration);
}

void UCatrunNoticeSubsystem::ShowNotice(const FText& Text, float Duration, ECatrunNoticePolicy Policy)
{
	UWorld* World = GetWorld();
	if (!World || (bStageTimeoutNotice && Policy != ECatrunNoticePolicy::StageTimeout))
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
	const float NoticeDuration = FMath::Max(Duration, 0.1f);
	bStageTimeoutNotice = Policy == ECatrunNoticePolicy::StageTimeout;
	Widget->SetNoticeText(Text);
	Widget->SetNoticePolicy(Policy, NoticeDuration);
	Widget->SetVisibility(ESlateVisibility::HitTestInvisible);

	if (Policy == ECatrunNoticePolicy::DeferredGameplay)
	{
		World->GetTimerManager().ClearTimer(HideTimer);
	}
	else
	{
		World->GetTimerManager().SetTimer(HideTimer, this, &UCatrunNoticeSubsystem::HideNotice, NoticeDuration, false);
	}
}

void UCatrunNoticeSubsystem::ClearStageTimeoutNotice()
{
	if (!bStageTimeoutNotice) return;
	if (UWorld* World = GetWorld()) World->GetTimerManager().ClearTimer(HideTimer);
	HideNotice();
}

void UCatrunNoticeSubsystem::HideNotice()
{
	bStageTimeoutNotice = false;
	if (Widget)
	{
		Widget->SetVisibility(ESlateVisibility::Collapsed);
	}
}
