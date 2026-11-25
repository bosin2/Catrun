#include "UI/CatrunMenuProgressWidget.h"
#include "Engine/GameViewportClient.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "Framework/Application/SlateApplication.h"
#include "Framework/Application/SlateUser.h"
#include "GameFramework/PlayerController.h"
#include "Widgets/SViewport.h"
#include "TimerManager.h"

void UCatrunMenuProgressWidget::NativeConstruct()
{
	Super::NativeConstruct();
	BoundSession = UCatrunLevelFlowLibrary::GetFlowSession(this);
	if (UCatrunFlowSession* Session = BoundSession.Get())
	{
		Session->OnCheckpointStateChanged.AddUniqueDynamic(this, &ThisClass::CheckpointChanged);
	}
	RefreshMenu();
	if (const auto* Session = BoundSession.Get(); Session && !Session->IsProgressReadResolved())
		GetWorld()->GetTimerManager().SetTimer(ProgressReadTimer, this, &ThisClass::RetryProgressRead, 1.f, true);
}

void UCatrunMenuProgressWidget::NativeTick(const FGeometry& MyGeometry, float InDeltaTime)
{
	Super::NativeTick(MyGeometry, InDeltaTime);
	RestoreMenuFocus();
}

void UCatrunMenuProgressWidget::RestoreMenuFocus()
{
	// Settings and chapter selection hide and disable this menu while they own input.
	if (!IsVisible() || !GetIsEnabled() || !FSlateApplication::IsInitialized() || !FSlateApplication::Get().IsActive()) return;
	auto* PC = GetOwningPlayer();
	const auto* LocalPlayer = PC ? PC->GetLocalPlayer() : nullptr;
	const auto User = LocalPlayer ? LocalPlayer->GetSlateUser() : nullptr;
	if (!User) return;
	UWidget* First = nullptr;
	for (const TCHAR* Name : {TEXT("ContinueButton"), TEXT("StartButton"), TEXT("OptionButton"), TEXT("EndButton")})
	{
		UWidget* Button = GetWidgetFromName(Name);
		if (!Button || !Button->GetIsEnabled() || !Button->IsVisible()) continue;
		if (Button->HasUserFocus(PC)) { LastFocusedButton = Button; return; }
		if (!First) First = Button;
	}
	// Only reclaim focus that fell back to the viewport or this panel; the console and popups keep theirs.
	const auto Focused = User->GetFocusedWidget();
	const auto* Viewport = GetWorld() ? GetWorld()->GetGameViewport() : nullptr;
	if (Focused && Focused != GetCachedWidget() && (!Viewport || Focused != Viewport->GetGameViewportWidget())) return;
	UWidget* Target = LastFocusedButton.IsValid() && LastFocusedButton->GetIsEnabled() ? LastFocusedButton.Get() : First;
	if (Target) Target->SetUserFocus(PC);
}

void UCatrunMenuProgressWidget::NativeDestruct()
{
	if (UWorld* World = GetWorld()) World->GetTimerManager().ClearTimer(ProgressReadTimer);
	if (UCatrunFlowSession* Session = BoundSession.Get())
	{
		Session->OnCheckpointStateChanged.RemoveDynamic(this, &ThisClass::CheckpointChanged);
	}
	BoundSession.Reset();
	Super::NativeDestruct();
}

void UCatrunMenuProgressWidget::CheckpointChanged(ECatrunCheckpointState)
{
	RefreshMenu();
}

void UCatrunMenuProgressWidget::RetryProgressRead()
{
	auto* Session = BoundSession.Get();
	if (Session)
	{
		RefreshMenu();
		if (!Session->IsProgressReadResolved()) return;
	}
	GetWorld()->GetTimerManager().ClearTimer(ProgressReadTimer);
}

void UCatrunMenuProgressWidget::RefreshMenu()
{
	if (auto* Session = BoundSession.Get()) Session->RefreshMenuWithProgressSnapshot([this]() { RefreshContinue(); });
	else RefreshContinue();
}
