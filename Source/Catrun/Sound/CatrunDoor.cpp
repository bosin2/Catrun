#include "CatrunDoor.h"

#include "SoundGridManager.h"
#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"

ACatrunDoor::ACatrunDoor()
{
	// The tick only runs while the leaf is turning.
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = false;

	USceneComponent* Root = CreateDefaultSubobject<USceneComponent>(TEXT("Hinge"));
	SetRootComponent(Root);

	DoorMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("DoorMesh"));
	DoorMesh->SetupAttachment(Root);
	DoorMesh->SetCollisionProfileName(TEXT("BlockAll"));

	GateBox = CreateDefaultSubobject<UBoxComponent>(TEXT("GateBox"));
	GateBox->SetupAttachment(Root);
	GateBox->SetBoxExtent(FVector(75.f, 15.f, 100.f));
	GateBox->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	GateBox->SetHiddenInGame(true);
}

FVector ACatrunDoor::GetDoorwayCenter() const
{
	return GateBox->GetComponentLocation();
}

FVector ACatrunDoor::GetDoorNormal() const
{
	// The gate box is wide along its X axis and thin along its Y axis, so Y is the leaf's normal.
	return GateBox->GetRightVector().GetSafeNormal2D();
}

void ACatrunDoor::BeginPlay()
{
	Super::BeginPlay();
	bIsOpen = bStartOpen;
	SnapToState();
	OnDoorStateChanged(bIsOpen);
	if (ASoundGridManager* Manager = ASoundGridManager::Get(this))
	{
		Manager->NotifyDoorStateChanged(this);
	}
}

void ACatrunDoor::SnapToState()
{
	DoorMesh->SetRelativeRotation(FRotator(0.f, bIsOpen ? OpenYaw : 0.f, 0.f));
	DoorMesh->SetCollisionEnabled(bIsOpen ? ECollisionEnabled::NoCollision : ECollisionEnabled::QueryAndPhysics);
}

void ACatrunDoor::SetOpen(bool bNewOpen)
{
	if (bIsOpen == bNewOpen)
	{
		return;
	}
	bIsOpen = bNewOpen;

	// An open leaf must not block anyone while it swings; a closing leaf blocks again at once.
	DoorMesh->SetCollisionEnabled(bIsOpen ? ECollisionEnabled::NoCollision : ECollisionEnabled::QueryAndPhysics);
	SetActorTickEnabled(true);

	OnDoorStateChanged(bIsOpen);
	if (ASoundGridManager* Manager = ASoundGridManager::Get(this))
	{
		Manager->NotifyDoorStateChanged(this);
	}
}

void ACatrunDoor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// Turn the leaf toward the target angle at a constant speed.
	const float TargetYaw = bIsOpen ? OpenYaw : 0.f;
	const float Speed = FMath::Abs(OpenYaw) / OpenDuration;
	const float NewYaw = FMath::FInterpConstantTo(DoorMesh->GetRelativeRotation().Yaw, TargetYaw, DeltaSeconds, Speed);
	DoorMesh->SetRelativeRotation(FRotator(0.f, NewYaw, 0.f));

	if (FMath::IsNearlyEqual(NewYaw, TargetYaw))
	{
		SetActorTickEnabled(false);
	}
}
