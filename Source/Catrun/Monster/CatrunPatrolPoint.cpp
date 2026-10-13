#include "CatrunPatrolPoint.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "UObject/ConstructorHelpers.h"

ACatrunPatrolPoint::ACatrunPatrolPoint()
{
	PrimaryActorTick.bCanEverTick = false;

	SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));

	Marker = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Marker"));
	Marker->SetupAttachment(GetRootComponent());
	Marker->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Marker->SetCanEverAffectNavigation(false);
	Marker->SetCastShadow(false);
	Marker->SetHiddenInGame(true);
	Marker->SetRelativeScale3D(FVector(0.4f));
	Marker->SetRelativeLocation(FVector(0.f, 0.f, 20.f));

	static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	if (Sphere.Succeeded())
	{
		Marker->SetStaticMesh(Sphere.Object);
	}
}
