#include "CatrunBasketPromptWidget.h"
#include "Components/TextBlock.h"
#include "Settings/CatrunInputBindings.h"

FText UCatrunBasketPromptWidget::GetPromptText() const
{
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
