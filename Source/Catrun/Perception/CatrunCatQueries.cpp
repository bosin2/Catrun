#include "CatrunCatQueries.h"

#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"

APawn* CatrunCat::Find(const UObject* WorldContextObject)
{
	return UGameplayStatics::GetPlayerPawn(WorldContextObject, 0);
}

bool CatrunCat::IsHiding(const APawn* Cat)
{
	if (!Cat)
	{
		return false;
	}
	// The interaction blueprint class is not known to C++, so find its component by class name.
	for (const UActorComponent* Component : Cat->GetComponents())
	{
		if (!Component || !Component->GetClass()->GetName().Contains(TEXT("CatActions")))
		{
			continue;
		}
		const FBoolProperty* Hidden = FindFProperty<FBoolProperty>(Component->GetClass(), TEXT("IsHidden"));
		if (Hidden)
		{
			return Hidden->GetPropertyValue_InContainer(Component);
		}
	}
	return false;
}
