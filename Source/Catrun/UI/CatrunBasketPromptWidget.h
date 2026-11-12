#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "CatrunBasketPromptWidget.generated.h"

class UTextBlock;

/** Presentation is authored in WBP_BasketInteractPrompt; native code owns only availability and key text. */
UCLASS()
class CATRUN_API UCatrunBasketPromptWidget : public UUserWidget
{
	GENERATED_BODY()
public:
	UFUNCTION(BlueprintPure, Category="Basket|Prompt")
	FText GetPromptText() const;
	UFUNCTION(BlueprintCallable, Category="Basket|Prompt")
	void SetPromptActive(bool bActive);
protected:
	virtual void NativeConstruct() override;
	/** Optional convenience binding; a custom layout can bind GetPromptText instead. */
	UPROPERTY(BlueprintReadOnly, meta=(BindWidgetOptional))
	TObjectPtr<UTextBlock> PromptText;
};
