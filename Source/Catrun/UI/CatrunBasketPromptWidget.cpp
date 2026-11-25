#include "CatrunBasketPromptWidget.h"
#include "Components/TextBlock.h"
#include "Settings/CatrunInputBindings.h"
#include "Interaction/CatrunBasketInteractionComponent.h"
#include "GameFramework/Pawn.h"

FText UCatrunBasketPromptWidget::GetPromptText() const
{
	const auto* Pawn=GetOwningPlayerPawn();
	const auto* Actions=Pawn ? Pawn->FindComponentByClass<UCatrunBasketInteractionComponent>() : nullptr;
	if (Actions && Actions->BasketPhase==ECatrunBasketPhase::Hidden)
	{
		if (!Actions->ExitWorldDirection.IsNearlyZero() && !Actions->CanExit)
			return NSLOCTEXT("CatrunBasket","SelectedBlocked","선택한 방향이 막혀 있습니다 — 다른 이동 키로 방향 변경");
		return FText::Format(NSLOCTEXT("CatrunBasket","MovementExit","[{0}/{1}/{2}/{3}] 방향 선택   [{4}] 나가기"),
			UCatrunInputBindings::GetEffectiveKeyLabel(ECatrunInputSlot::Forward),
			UCatrunInputBindings::GetEffectiveKeyLabel(ECatrunInputSlot::Left),
			UCatrunInputBindings::GetEffectiveKeyLabel(ECatrunInputSlot::Back),
			UCatrunInputBindings::GetEffectiveKeyLabel(ECatrunInputSlot::Right),
			UCatrunInputBindings::GetEffectiveKeyLabel(ECatrunInputSlot::Interact));
	}
	return FText::Format(NSLOCTEXT("CatrunBasket", "HidePrompt", "[{0}] 숨기"),
		UCatrunInputBindings::GetEffectiveKeyLabel(ECatrunInputSlot::Interact));
}

void UCatrunBasketPromptWidget::NativeConstruct()
{
	Super::NativeConstruct();
	SetIsFocusable(false);
	SetPromptActive(false);
}

void UCatrunBasketPromptWidget::SetPromptActive(bool bActive)
{
	if (bActive && PromptText) PromptText->SetText(GetPromptText());
	SetVisibility(bActive ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
}
