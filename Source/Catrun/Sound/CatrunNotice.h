#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Subsystems/WorldSubsystem.h"
#include "CatrunNotice.generated.h"

class UBorder;
class UTextBlock;

enum class ECatrunNoticePolicy : uint8
{
	Gameplay,
	DeferredGameplay,
	BlockedRecovery,
	StageTimeout
};

/** A line of text at the bottom of the screen. Built in code, so it needs no widget blueprint. */
UCLASS()
class CATRUN_API UCatrunNoticeWidget : public UUserWidget
{
	GENERATED_BODY()

public:
	void SetNoticeText(const FText& Text);
	void SetScreenAnchor(FVector2D Anchor);
	void SetNoticePolicy(ECatrunNoticePolicy Policy, float Duration);

protected:
	virtual TSharedRef<SWidget> RebuildWidget() override;
	virtual void NativeTick(const FGeometry& Geometry, float DeltaSeconds) override;

private:
	friend class FCatrunNoticeLayoutTest;
	ECatrunNoticePolicy NoticePolicy = ECatrunNoticePolicy::Gameplay;
	bool RefreshPresentation();
	float RemainingReadableSeconds = 0.f;
	bool bWasReadable = false;
	FText PendingText;
	UPROPERTY(Transient)
	TObjectPtr<UTextBlock> TextBlock;
	UPROPERTY(Transient)
	TObjectPtr<UBorder> Plate;
};

/** Shows short messages to the player ("you cannot ring the bell here"). */
UCLASS()
class CATRUN_API UCatrunNoticeSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	static UCatrunNoticeSubsystem* Get(const UObject* WorldContextObject);

	// A new notice replaces the one on screen. DeferredGameplay counts only readable time.
	void ShowNotice(const FText& Text, float Duration, ECatrunNoticePolicy Policy = ECatrunNoticePolicy::Gameplay);
	void ClearStageTimeoutNotice();
	static FText BellDeniedText();

	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void Deinitialize() override;

private:
	friend class FCatrunRecoveryNoticeTest;
	friend class FCatrunDeferredNoticeTest;
	void HideNotice();

	UPROPERTY(Transient)
	TObjectPtr<UCatrunNoticeWidget> Widget;

	FTimerHandle HideTimer;
	bool bStageTimeoutNotice = false;
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
