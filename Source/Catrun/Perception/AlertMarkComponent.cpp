#include "AlertMarkComponent.h"

#include "Camera/PlayerCameraManager.h"
#include "Kismet/GameplayStatics.h"

UCatrunAlertMarkComponent::UCatrunAlertMarkComponent()
{
	PrimaryComponentTick.bCanEverTick = true;

	SetText(FText::FromString(TEXT("!")));
	SetHorizontalAlignment(EHTA_Center);
	SetWorldSize(80.f);
	SetTextRenderColor(FColor(255, 60, 40));
	SetCastShadow(false);
	SetVisibility(false);
}

void UCatrunAlertMarkComponent::Show(float Duration)
{
	TimeLeft = Duration;
	SetVisibility(true);
}

void UCatrunAlertMarkComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	if (TimeLeft <= 0.f)
	{
		return;
	}
	TimeLeft -= DeltaTime;
	if (TimeLeft <= 0.f)
	{
		SetVisibility(false);
		return;
	}
	// Always face the camera so the "!" can be read from the fixed view.
	if (const APlayerCameraManager* Camera = UGameplayStatics::GetPlayerCameraManager(this, 0))
	{
		SetWorldRotation((-Camera->GetCameraRotation().Vector()).Rotation());
	}
}
