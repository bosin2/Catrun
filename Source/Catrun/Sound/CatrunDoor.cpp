#include "CatrunDoor.h"

#include "SoundGridManager.h"
#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"

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

	// Remember how the leaf was placed (hinge on the left) and how wide it is.
	ClosedScale = DoorMesh->GetRelativeScale3D();
	if (const UStaticMesh* Mesh = DoorMesh->GetStaticMesh())
	{
		LeafWidth = Mesh->GetBounds().BoxExtent.X * 2.f * FMath::Abs(ClosedScale.X);
	}

	bIsOpen = bStartOpen;
	SnapToState();
	OnDoorStateChanged(bIsOpen);
	if (ASoundGridManager* Manager = ASoundGridManager::Get(this))
	{
		Manager->NotifyDoorStateChanged(this);
	}
}

void ACatrunDoor::SetHingeOnRight(bool bOnRight)
{
	// Mirror the leaf around the middle of the doorway: same closed look, hinge on the other edge.
	DoorMesh->SetRelativeLocation(FVector(bOnRight ? LeafWidth : 0.f, 0.f, 0.f));
	DoorMesh->SetRelativeScale3D(FVector(bOnRight ? -ClosedScale.X : ClosedScale.X, ClosedScale.Y, ClosedScale.Z));
}

void ACatrunDoor::SnapToState()
{
	DoorMesh->SetRelativeRotation(FRotator(0.f, bIsOpen ? OpenYaw : 0.f, 0.f));
	DoorMesh->SetCollisionEnabled(bIsOpen ? ECollisionEnabled::NoCollision : ECollisionEnabled::QueryAndPhysics);
}

void ACatrunDoor::OpenFrom(const FVector& OpenerLocation)
{
	if (bIsOpen)
	{
		return;
	}
	// The opener stands on one side of the doorway looking at it. The hinge goes to the
	// opener's LEFT hand side; the actor origin is the placed leaf's left edge (class comment).
	const FVector ToOpener = OpenerLocation - GetDoorwayCenter();
	const FVector Normal = GetDoorNormal(); // points out of the leaf, along the actor's +Y
	const float Side = FVector::DotProduct(ToOpener, Normal);

	// Seen from the +Y side the original hinge (x = 0, the actor's left edge) is already on the
	// LEFT of someone facing the door. From the -Y side it is on their right, so the hinge
	// moves to the other edge.
	SetHingeOnRight(Side < 0.f);
	SetOpen(true);
}

FBox ACatrunDoor::GetLeafBounds() const
{
	return DoorMesh->Bounds.GetBox();
}

void ACatrunDoor::BeginHandOpen(const FVector& OpenerLocation)
{
	if (bIsOpen)
	{
		return;
	}
	OpenFrom(OpenerLocation); // places the hinge, unblocks the doorway, starts the timed opening
	SetActorTickEnabled(false); // ...but the hand moves the leaf, not the timer
	bHandDriven = true;
	bHandReferenceSet = false;
	HandProgress = 0.f;
}

void ACatrunDoor::DriveWithPoint(const FVector& PointWorld)
{
	if (!bHandDriven)
	{
		return;
	}
	// Direction (degrees, same sense as yaw) from the hinge to the hand.
	const FVector Hinge = DoorMesh->GetComponentLocation();
	const float Angle = FMath::RadiansToDegrees(FMath::Atan2(PointWorld.Y - Hinge.Y, PointWorld.X - Hinge.X));
	if (!bHandReferenceSet)
	{
		HandReferenceAngle = Angle; // the leaf is still closed at this moment
		bHandReferenceSet = true;
		return;
	}
	// How far the hand has swung around the hinge since it took hold = how far the leaf turned.
	const float Swung = FMath::FindDeltaAngleDegrees(HandReferenceAngle, Angle);
	HandProgress = FMath::Max(HandProgress, FMath::Clamp(Swung / OpenYaw, 0.f, 1.f));
	DoorMesh->SetRelativeRotation(FRotator(0.f, OpenYaw * HandProgress, 0.f));
}

void ACatrunDoor::EndHandOpen()
{
	bHandDriven = false;
	SetActorTickEnabled(true); // the tick turns the leaf the rest of the way
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
