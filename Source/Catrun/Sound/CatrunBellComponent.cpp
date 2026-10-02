#include "CatrunBellComponent.h"

#include "../Catrun.h"
#include "CatrunSoundSettings.h"
#include "SoundGridManager.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"

UCatrunBellComponent::UCatrunBellComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
}

void UCatrunBellComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	const APawn* Pawn = Cast<APawn>(GetOwner());
	const APlayerController* Controller = Pawn ? Cast<APlayerController>(Pawn->GetController()) : nullptr;
	if (Controller && Controller->WasInputKeyJustPressed(BellKey))
	{
		TryRing();
	}
}

float UCatrunBellComponent::GetCooldownRemaining() const
{
	const ASoundGridManager* Manager = ASoundGridManager::Get(this);
	const UCatrunSoundSettings* Settings = Manager ? Manager->GetSettings() : nullptr;
	if (!Settings || !GetWorld())
	{
		return 0.f;
	}
	return FMath::Max(0.f, static_cast<float>(Settings->BellCooldown - (GetWorld()->GetTimeSeconds() - LastRingTime)));
}

bool UCatrunBellComponent::TryRing()
{
	ASoundGridManager* Manager = ASoundGridManager::Get(this);
	if (!bCanRing || !Manager || !GetOwner() || GetCooldownRemaining() > 0.f)
	{
		return false;
	}

	FCatrunSoundEvent Event;
	Event.Source = ECatrunSoundSource::Cat;
	Event.Kind = ECatrunSoundKind::Bell;
	Event.Size = ECatrunSoundSize::Large;
	Event.Target = ECatrunSoundTarget::Minion;
	Event.Location = GetOwner()->GetActorLocation(); // snapshot, not a live reference
	Event.Instigator = GetOwner();

	if (Manager->EmitSound(Event))
	{
		LastRingTime = GetWorld()->GetTimeSeconds();
		return true;
	}
	return false;
}
