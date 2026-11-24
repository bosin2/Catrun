#include "CatrunDoor.h"
#include "Interaction/CatrunPuzzleSuspension.h"
#include "Pathfinding/ArmorPathfinder.h"

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

bool ACatrunDoor::GetArmorPassageLane(float CapsuleRadius, float GridCellSize, CatrunArmorPath::FDoorLane& OutLane) const
{
	if (!FMath::IsFinite(ArmorPassageHalfWidth) || ArmorPassageHalfWidth <= 0.f) return false;
	const FVector2D Normal(GetDoorNormal());
	if (Normal.IsNearlyZero()) return false;

	const FVector Extent = GateBox->GetScaledBoxExtent();
	OutLane.Center = FVector2D(GetDoorwayCenter());
	OutLane.Normal = Normal;
	OutLane.PassageHalfWidth = FMath::Min<double>(ArmorPassageHalfWidth, Extent.X);
	OutLane.FrameHalfWidth = Extent.X + CapsuleRadius;
	// Start aligning a cell before the expanded gate. Frames can project past
	// the leaf, and CharacterMovement turns shortly before a path corner.
	OutLane.ApproachHalfDepth = Extent.Y + CapsuleRadius + GridCellSize;
	return true;
}

void ACatrunDoor::BeginPlay()
{
	Super::BeginPlay();

	// Preserve the authored seating pose, including a mesh pivot outside its bounds.
	ClosedScale = DoorMesh->GetRelativeScale3D();
	ClosedLocation = DoorMesh->GetRelativeLocation();
	ClosedRotation = DoorMesh->GetRelativeRotation().Quaternion();
	if (const UStaticMesh* Mesh = DoorMesh->GetStaticMesh())
	{
		// Reflect around the bounds' center, not their width: min X need not be zero.
		// Width alone shifted the tutorial's -1.7 cm pivot overhang by 3.4 cm.
		OppositeHingeOffset = ClosedRotation.RotateVector(FVector(2.f * Mesh->GetBounds().Origin.X * ClosedScale.X, 0.f, 0.f));
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
	DoorMesh->SetRelativeLocation(ClosedLocation + (bOnRight ? OppositeHingeOffset : FVector::ZeroVector));
	DoorMesh->SetRelativeScale3D(FVector(bOnRight ? -ClosedScale.X : ClosedScale.X, ClosedScale.Y, ClosedScale.Z));
}

void ACatrunDoor::ApplyLeafAngle(float Angle)
{
	CurrentLeafAngle = Angle;
	DoorMesh->SetRelativeRotation(ClosedRotation * FQuat(FVector::UpVector, FMath::DegreesToRadians(Angle)));
}

void ACatrunDoor::SnapToState()
{
	ApplyLeafAngle(bIsOpen ? OpenYaw : 0.f);
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
	if (UCatrunPuzzleSuspension::IsSuspended(this)) return;
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
	ApplyLeafAngle(OpenYaw * HandProgress);
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
	if (UCatrunPuzzleSuspension::IsSuspended(this)) return;
	Super::Tick(DeltaSeconds);

	// Turn the leaf toward the target angle at a constant speed.
	const float TargetYaw = bIsOpen ? OpenYaw : 0.f;
	const float Speed = FMath::Abs(OpenYaw) / FMath::Max(OpenDuration, .01f);
	const float NewYaw = FMath::FInterpConstantTo(CurrentLeafAngle, TargetYaw, DeltaSeconds, Speed);
	ApplyLeafAngle(NewYaw);

	if (FMath::IsNearlyEqual(NewYaw, TargetYaw))
	{
		SetActorTickEnabled(false);
	}
}
