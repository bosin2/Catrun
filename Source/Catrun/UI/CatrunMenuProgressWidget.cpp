#include "UI/CatrunMenuProgressWidget.h"
#include "Engine/World.h"
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
