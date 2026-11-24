#include "UI/CatrunPlayerStatusWidget.h"

#include "Components/ProgressBar.h"
#include "Components/TextBlock.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "Player/CatrunSprintComponent.h"
#include "Settings/CatrunSettingsSubsystem.h"
#include "Sound/CatrunBellComponent.h"

namespace
{
	FText BellReason(ECatrunBellBlockReason Reason)
	{
		switch (Reason)
		{
		case ECatrunBellBlockReason::Hidden: return NSLOCTEXT("PlayerStatus", "Hidden", "은신 중");
		case ECatrunBellBlockReason::Busy: return NSLOCTEXT("PlayerStatus", "Busy", "행동 중");
		case ECatrunBellBlockReason::Airborne: return NSLOCTEXT("PlayerStatus", "Airborne", "공중");
		case ECatrunBellBlockReason::CatHole: return NSLOCTEXT("PlayerStatus", "CatHole", "캣홀 안");
		case ECatrunBellBlockReason::Cinematic: return NSLOCTEXT("PlayerStatus", "Cinematic", "연출 중");
		case ECatrunBellBlockReason::Cooldown: return NSLOCTEXT("PlayerStatus", "Cooldown", "충전 중");
		default: return FText::GetEmpty();
		}
	}

	void SetLabel(UTextBlock* Block, const FText& Text)
	{
		if (Block && !Block->GetText().EqualTo(Text))
			Block->SetText(Text);
	}
}

void UCatrunPlayerStatusWidget::NativeConstruct()
{
	Super::NativeConstruct();
	SetIsFocusable(false);
	SetVisibility(ESlateVisibility::HitTestInvisible);
	SetRenderOpacity(0.f);
	RefreshDelay = 0.f;
}

void UCatrunPlayerStatusWidget::NativeTick(const FGeometry& Geometry, float DeltaSeconds)
{
	Super::NativeTick(Geometry, DeltaSeconds);
	const APawn* Pawn = GetOwningPlayerPawn();
	const auto* Flow = UCatrunLevelFlowSubsystem::Get(this);
	const auto* Options = GetWorld() ? GetWorld()->GetSubsystem<UCatrunSettingsSubsystem>() : nullptr;
	const bool bVisible = Pawn && Flow && !(Options && Options->GetCurrentSettingsWidget())
		&& !UCatrunLevelFlowLibrary::ShouldHideGameplayHUD(this);
	// A collapsed UserWidget stops ticking; keep the passive viewport wrapper awake while its content is hidden.
	if (GetRenderOpacity() != (bVisible ? 1.f : 0.f))
		SetRenderOpacity(bVisible ? 1.f : 0.f);
	if (!bVisible)
	{
		RefreshDelay = 0.f;
		return;
	}
	RefreshDelay -= DeltaSeconds;
	if (RefreshDelay > 0.f) return;
	RefreshDelay = .08f;

	const auto* Sprint = Pawn->FindComponentByClass<UCatrunSprintComponent>();
	if (StaminaBar)
	{
		StaminaBar->SetPercent(Sprint ? Sprint->GetStaminaNormalized() : 0.f);
		StaminaBar->SetFillColorAndOpacity(Sprint && Sprint->IsExhausted() ? UrgentColor : StaminaColor);
	}
	SetLabel(StaminaText, Sprint ? FText::AsNumber(FMath::CeilToInt(Sprint->GetStamina())) : FText::FromString(TEXT("—")));
	const auto* Bell = Pawn->FindComponentByClass<UCatrunBellComponent>();
	if (Bell)
	{
		const auto State = Bell->GetBellStatus();
		const bool bBlocked = !State.bCanRing && State.Reason != ECatrunBellBlockReason::Cooldown;
		if (BellProgress)
		{
			BellProgress->SetPercent(State.CooldownSeconds > 0.f ?
				FMath::Clamp(1.f - State.RemainingSeconds / State.CooldownSeconds, 0.f, 1.f) : 1.f);
			BellProgress->SetFillColorAndOpacity(bBlocked ? BlockedColor : BellColor);
		}
		SetLabel(BellReasonText, BellReason(State.Reason));
		SetLabel(BellRemainingText, State.RemainingSeconds > 0.f ?
			FText::FromString(FString::Printf(TEXT("%.1f초"), FMath::CeilToFloat(State.RemainingSeconds * 10.f) / 10.f)) :
			(State.bCanRing ? NSLOCTEXT("PlayerStatus", "Ready", "준비") : FText::GetEmpty()));
	}
	else
	{
		if (BellProgress) BellProgress->SetPercent(0.f);
		SetLabel(BellReasonText, FText::GetEmpty());
		SetLabel(BellRemainingText, FText::FromString(TEXT("—")));
	}
	if (ClockText)
	{
		const auto Clock = Flow->GetStageClockState();
		const int32 Seconds = FMath::Max(0, FMath::CeilToInt(Clock.RemainingSeconds));
		const float Fraction = Clock.BudgetSeconds > 0.f ? Clock.RemainingSeconds / Clock.BudgetSeconds : 1.f;
		const FLinearColor Color = !Clock.bTimed ? ClockColor : Fraction <= Clock.UrgentFraction ? UrgentColor :
			Fraction <= Clock.WarningFraction ? WarningColor : ClockColor;
		ClockText->SetColorAndOpacity(Color);
		SetLabel(ClockText, Clock.bTimed ?
			FText::FromString(FString::Printf(TEXT("남은 시간   %02d:%02d"), Seconds / 60, Seconds % 60)) :
			NSLOCTEXT("PlayerStatus", "PracticeClock", "튜토리얼 · 시간 제한 없음\n다음 구역부터 제한 시간이 흘러요."));
	}
}
