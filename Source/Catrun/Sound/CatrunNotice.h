#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "Subsystems/WorldSubsystem.h"
#include "CatrunNotice.generated.h"

class UTextBlock;

/** A line of text at the bottom of the screen. Built in code, so it needs no widget blueprint. */
UCLASS()
class CATRUN_API UCatrunNoticeWidget : public UUserWidget
{
	GENERATED_BODY()

public:
	void SetNoticeText(const FText& Text);

protected:
	virtual TSharedRef<SWidget> RebuildWidget() override;

private:
	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> TextBlock;
};

/** Shows short messages to the player ("you cannot ring the bell here"). */
UCLASS()
class CATRUN_API UCatrunNoticeSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	static UCatrunNoticeSubsystem* Get(const UObject* WorldContextObject);

	// Shows Text for Duration seconds (a new notice replaces the one on screen).
	void ShowNotice(const FText& Text, float Duration);

	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;

private:
	void HideNotice();

	UPROPERTY(Transient)
	TObjectPtr<UCatrunNoticeWidget> Widget;

	FTimerHandle HideTimer;
};
