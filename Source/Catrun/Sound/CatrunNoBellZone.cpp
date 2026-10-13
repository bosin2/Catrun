#include "CatrunNoBellZone.h"

#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"

ACatrunNoBellZone::ACatrunNoBellZone()
{
	PrimaryActorTick.bCanEverTick = false;

	Box = CreateDefaultSubobject<UBoxComponent>(TEXT("Box"));
	SetRootComponent(Box);
	Box->SetBoxExtent(FVector(100.f, 100.f, 100.f));
	Box->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Box->SetCanEverAffectNavigation(false);
	Box->SetHiddenInGame(true);
}

bool ACatrunNoBellZone::Touches(const AActor& Cat) const
{
	// Work in the box's own space, seen from above: the distance from the cat's centre to the box
	// is compared with the cat's radius.
	const FVector Local = Box->GetComponentTransform().InverseTransformPositionNoScale(Cat.GetActorLocation());
	const FVector Extent = Box->GetScaledBoxExtent();
	const FVector2D Closest(FMath::Clamp(Local.X, -Extent.X, Extent.X), FMath::Clamp(Local.Y, -Extent.Y, Extent.Y));
	const float Distance = FVector2D::Distance(FVector2D(Local.X, Local.Y), Closest);

	const ACharacter* Character = Cast<ACharacter>(&Cat);
	const float Radius = Character ? Character->GetCapsuleComponent()->GetScaledCapsuleRadius() : 0.f;
	return Distance <= Radius;
}

bool ACatrunNoBellZone::IsBellForbidden(const AActor& Cat)
{
	for (TActorIterator<ACatrunNoBellZone> It(Cat.GetWorld()); It; ++It)
	{
		if (It->Touches(Cat))
		{
			return true;
		}
	}
	return false;
}
