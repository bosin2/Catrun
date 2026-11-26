#include "CatrunSightBlockerSubsystem.h"

#include "Components/PrimitiveComponent.h"
#include "Engine/World.h"

UCatrunSightBlockerSubsystem* UCatrunSightBlockerSubsystem::Get(const UWorld* World)
{
	return World ? World->GetSubsystem<UCatrunSightBlockerSubsystem>() : nullptr;
}

void UCatrunSightBlockerSubsystem::Prune()
{
	Blockers.RemoveAll([](const TWeakObjectPtr<UPrimitiveComponent>& Blocker) { return !Blocker.IsValid(); });
}

void UCatrunSightBlockerSubsystem::Register(UPrimitiveComponent& Component)
{
	Prune();
	Blockers.AddUnique(&Component);
}

bool UCatrunSightBlockerSubsystem::IsRegistered(const UPrimitiveComponent* Component) const
{
	if (!IsValid(Component)) return false;
	return Blockers.ContainsByPredicate([Component](const TWeakObjectPtr<UPrimitiveComponent>& Blocker) { return Blocker.Get() == Component; });
}

int32 UCatrunSightBlockerSubsystem::Num()
{
	Prune();
	return Blockers.Num();
}

const TArray<TWeakObjectPtr<UPrimitiveComponent>>& UCatrunSightBlockerSubsystem::GetBlockers()
{
	Prune();
	return Blockers;
}
