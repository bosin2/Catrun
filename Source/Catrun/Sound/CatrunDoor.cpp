#include "CatrunDoor.h"

#include "SoundGridManager.h"
#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"

ACatrunDoor::ACatrunDoor()
{
	PrimaryActorTick.bCanEverTick = false;

	USceneComponent* Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	SetRootComponent(Root);

	DoorMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("DoorMesh"));
	DoorMesh->SetupAttachment(Root);

	GateBox = CreateDefaultSubobject<UBoxComponent>(TEXT("GateBox"));
	GateBox->SetupAttachment(Root);
	GateBox->SetBoxExtent(FVector(75.f, 15.f, 100.f));
	GateBox->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	GateBox->SetHiddenInGame(true);
}

void ACatrunDoor::BeginPlay()
{
	Super::BeginPlay();
	bIsOpen = bStartOpen;
	OnDoorStateChanged(bIsOpen);
	if (ASoundGridManager* Manager = ASoundGridManager::Get(this))
	{
		Manager->NotifyDoorStateChanged(this);
	}
}

void ACatrunDoor::SetOpen(bool bNewOpen)
{
	if (bIsOpen == bNewOpen)
	{
		return;
	}
	bIsOpen = bNewOpen;
	OnDoorStateChanged(bIsOpen);
	if (ASoundGridManager* Manager = ASoundGridManager::Get(this))
	{
		Manager->NotifyDoorStateChanged(this);
	}
}
