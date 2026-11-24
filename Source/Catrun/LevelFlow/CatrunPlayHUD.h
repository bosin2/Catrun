#pragma once
#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "GameFramework/Actor.h"
#include "CatrunPlayHUD.generated.h"

class UBoxComponent;
class UBorder;
class UTextBlock;
class UButton;
class UVerticalBox;

/** Level-authored prompts; designers can move/resize zones and edit copy without recompiling. */
UCLASS()
class CATRUN_API ACatrunGuidanceZone : public AActor
{
	GENERATED_BODY()
public:
	ACatrunGuidanceZone();
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly) TObjectPtr<UBoxComponent> Area;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Guidance") FText Title;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Guidance", meta=(MultiLine=true)) FText Message;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Guidance") int32 Priority = 0;
	bool Contains(const FVector& Point) const;
};

/** Compact play instructions + a real pause menu. No new abilities or progression gates. */
UCLASS()
class CATRUN_API UCatrunPlayHUD : public UUserWidget
{
	GENERATED_BODY()
public:
	virtual TSharedRef<SWidget> RebuildWidget() override;
	virtual void NativeTick(const FGeometry& Geometry, float DeltaSeconds) override;
	virtual FReply NativeOnKeyDown(const FGeometry& Geometry, const FKeyEvent& Event) override;
	void SetMenuOpen(bool bOpen);
	UFUNCTION(BlueprintCallable) void ResumePlay();
	UFUNCTION(BlueprintCallable) void RequestRestart();
	UFUNCTION(BlueprintCallable) void ReturnToMenu();
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly) bool bMenuOpen = false;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly) bool bConfirmRestart = false;
private:
	void Refresh();
	UTextBlock* AddText(UVerticalBox* Parent, FName Name, const FString& Text, int32 Size, FLinearColor Color);
	UButton* AddButton(UVerticalBox* Parent, FName Name, const FString& Text, UTextBlock*& Label);
	UPROPERTY(Transient) TObjectPtr<UTextBlock> ObjectiveTitle;
	UPROPERTY(Transient) TObjectPtr<UTextBlock> ObjectiveBody;
	UPROPERTY(Transient) TObjectPtr<UTextBlock> Status;
	UPROPERTY(Transient) TObjectPtr<UTextBlock> Context;
	UPROPERTY(Transient) TObjectPtr<UTextBlock> MenuTitle;
	UPROPERTY(Transient) TObjectPtr<UTextBlock> MenuBody;
	UPROPERTY(Transient) TObjectPtr<UTextBlock> RestartLabel;
	UPROPERTY(Transient) TObjectPtr<UTextBlock> ResumeLabel;
	UPROPERTY(Transient) TObjectPtr<UButton> MainMenuButton;
	UPROPERTY(Transient) TObjectPtr<UBorder> PausePanel;
	UPROPERTY(Transient) TObjectPtr<UBorder> GuidePanel;
	UPROPERTY(Transient) TObjectPtr<UBorder> StatePanel;
	UPROPERTY(Transient) TObjectPtr<UBorder> ControlsPanel;
	float RefreshDelay = 0;
};
