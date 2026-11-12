#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Subsystems/WorldSubsystem.h"
#include "CatrunNotice.generated.h"

class UTextBlock;

enum class ECatrunNoticePolicy : uint8
{
	Gameplay,
	BlockedRecovery
};

/** A line of text at the bottom of the screen. Built in code, so it needs no widget blueprint. */
UCLASS()
class CATRUN_API UCatrunNoticeWidget : public UUserWidget
{
	GENERATED_BODY()

public:
	void SetNoticeText(const FText& Text);
	void SetScreenAnchor(FVector2D Anchor);
	void SetNoticePolicy(ECatrunNoticePolicy Policy);

protected:
	virtual TSharedRef<SWidget> RebuildWidget() override;
	virtual void NativeTick(const FGeometry& Geometry, float DeltaSeconds) override;

private:
	friend class FCatrunRecoveryNoticeTest;
	ECatrunNoticePolicy NoticePolicy = ECatrunNoticePolicy::Gameplay;
	void RefreshPresentation();
	FText PendingText;
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
	void ShowNotice(const FText& Text, float Duration, ECatrunNoticePolicy Policy = ECatrunNoticePolicy::Gameplay);
	static FText BellDeniedText();

	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void Deinitialize() override;

private:
	friend class FCatrunRecoveryNoticeTest;
	void HideNotice();

	UPROPERTY(Transient)
	TObjectPtr<UCatrunNoticeWidget> Widget;

	FTimerHandle HideTimer;
};

/** Available in the original tutorial without installing the replacement play HUD. */
UCLASS()
class CATRUN_API UCatrunNoticeLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()
public:
	UFUNCTION(BlueprintCallable, Category="Catrun|Feedback", meta=(WorldContext="WorldContextObject"))
	static void ShowBottomNotice(const UObject* WorldContextObject, const FText& Text, float Duration = 2.f);
	UFUNCTION(BlueprintCallable, Category="Catrun|Feedback", meta=(WorldContext="WorldContextObject"))
	static void ShowBellDenied(const UObject* WorldContextObject, float Duration = 2.f);
};
