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
		// Blocked exits are not options: they are left out of the key list and never described.
		if (!Actions->HasAnyExitOption() && !Actions->CanExit)
			return NSLOCTEXT("CatrunBasket","NoExit","지금은 나갈 곳이 없습니다");
		struct FOption { FVector2D Input; ECatrunInputSlot A; ECatrunInputSlot B; };
		const FOption Cardinals[]={{FVector2D(1.,0.),ECatrunInputSlot::Forward,ECatrunInputSlot::Forward},
			{FVector2D(0.,-1.),ECatrunInputSlot::Left,ECatrunInputSlot::Left},
			{FVector2D(-1.,0.),ECatrunInputSlot::Back,ECatrunInputSlot::Back},
			{FVector2D(0.,1.),ECatrunInputSlot::Right,ECatrunInputSlot::Right}};
		const FOption Diagonals[]={{FVector2D(1.,-1.),ECatrunInputSlot::Forward,ECatrunInputSlot::Left},
			{FVector2D(1.,1.),ECatrunInputSlot::Forward,ECatrunInputSlot::Right},
			{FVector2D(-1.,-1.),ECatrunInputSlot::Back,ECatrunInputSlot::Left},
			{FVector2D(-1.,1.),ECatrunInputSlot::Back,ECatrunInputSlot::Right}};
		TArray<FString> Keys;
		for (const FOption& Option : Cardinals)
			if (Actions->IsExitInputAvailable(Option.Input))
				Keys.Add(UCatrunInputBindings::GetEffectiveKeyLabel(Option.A).ToString());
		// Diagonals are listed only when no single key is open, to keep the line short.
		if (Keys.IsEmpty())
			for (const FOption& Option : Diagonals)
				if (Actions->IsExitInputAvailable(Option.Input))
					Keys.Add(UCatrunInputBindings::GetEffectiveKeyLabel(Option.A).ToString()+TEXT("+")
						+UCatrunInputBindings::GetEffectiveKeyLabel(Option.B).ToString());
		const FText Interact=UCatrunInputBindings::GetEffectiveKeyLabel(ECatrunInputSlot::Interact);
		if (Keys.IsEmpty()) // Only the remembered choice is open (e.g. camera turned since the refresh).
			return FText::Format(NSLOCTEXT("CatrunBasket","ExitOnly","[{0}] 나가기"),Interact);
		const FText KeyList=FText::FromString(FString::Join(Keys,TEXT("/")));
		if (!Actions->CanExit)
			return FText::Format(NSLOCTEXT("CatrunBasket","MovementSelect","[{0}] 방향 선택"),KeyList);
		return FText::Format(NSLOCTEXT("CatrunBasket","MovementExitOpen","[{0}] 방향 선택   [{1}] 나가기"),KeyList,Interact);
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
