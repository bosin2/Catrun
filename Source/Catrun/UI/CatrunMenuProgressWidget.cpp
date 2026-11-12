#include "UI/CatrunMenuProgressWidget.h"

void UCatrunMenuProgressWidget::NativeConstruct()
{
	Super::NativeConstruct();
	BoundSession = UCatrunLevelFlowLibrary::GetFlowSession(this);
	if (UCatrunFlowSession* Session = BoundSession.Get())
	{
		Session->OnCheckpointStateChanged.AddUniqueDynamic(this, &ThisClass::CheckpointChanged);
	}
	RefreshContinue();
}

void UCatrunMenuProgressWidget::NativeDestruct()
{
	if (UCatrunFlowSession* Session = BoundSession.Get())
	{
		Session->OnCheckpointStateChanged.RemoveDynamic(this, &ThisClass::CheckpointChanged);
	}
	BoundSession.Reset();
	Super::NativeDestruct();
}

void UCatrunMenuProgressWidget::CheckpointChanged(ECatrunCheckpointState)
{
	RefreshContinue();
}
