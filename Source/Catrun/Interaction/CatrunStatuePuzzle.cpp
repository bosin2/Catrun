#include "CatrunStatuePuzzle.h"
#include "Settings/CatrunInputBindings.h"
#include "CatrunPuzzleRevealComponent.h"
#include "CatrunPuzzleSuspension.h"
#include "CatrunBasketInteractionComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Engine/World.h"
#include "Engine/OverlapResult.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "Monster/CatrunRestartSubsystem.h"
#include "Sound/SoundGridManager.h"

ACatrunStatuePuzzle::ACatrunStatuePuzzle()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PostPhysics;
	SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
	Reveal = CreateDefaultSubobject<UCatrunPuzzleRevealComponent>(TEXT("Reveal"));
}
void ACatrunStatuePuzzle::BeginPlay()
{
	Super::BeginPlay();
	InitializePuzzle();
}
void ACatrunStatuePuzzle::InitializePuzzle()
{
	if (bInitialized) return;
	if (!Settings) Settings = NewObject<UCatrunStatuePuzzleSettings>(this);
	for (auto& Link : Links)
	{
		if (!IsValid(Link.Statue) || !IsValid(Link.Plate) || !IsValid(Link.Gate))
		{
			UE_LOG(LogTemp, Error, TEXT("Statue puzzle %s has a missing actor link."), *Link.PuzzleId.ToString());
			continue;
		}
		for (AActor* Actor : {Link.Statue.Get(), Link.Plate.Get(), Link.Gate.Get()})
			if (USceneComponent* Root = Actor->GetRootComponent()) Root->SetMobility(EComponentMobility::Movable);
		Link.InitialStatue = Link.Statue->GetActorTransform();
		Link.InitialPlate = Link.Plate->GetActorLocation();
		Link.InitialGate = Link.Gate->GetActorLocation();
		const FBox Bounds = Link.Statue->GetComponentsBoundingBox(true);
		Link.StatueExtent = Bounds.GetExtent();
		Link.StatueCenterOffset = Bounds.GetCenter() - Link.Statue->GetActorLocation();
		Link.InitialPlateBounds = Link.Plate->GetComponentsBoundingBox(true);
		Link.InitialGateBounds = Link.Gate->GetComponentsBoundingBox(true);
		Link.SeatLocation = FVector(Link.InitialPlateBounds.GetCenter().X-Link.StatueCenterOffset.X,
			Link.InitialPlateBounds.GetCenter().Y-Link.StatueCenterOffset.Y, Link.InitialStatue.GetLocation().Z);
		const FVector Axis = Link.SocketAxis.IsNearlyZero() ? Link.SeatLocation-Link.InitialStatue.GetLocation() : Link.SocketAxis;
		Link.SeatingAxis = FMath::Abs(Axis.X) >= FMath::Abs(Axis.Y) ? FVector::ForwardVector : FVector::RightVector;
		Link.RequiredGateTravel = FMath::Max(Settings->GateTravel,
			float(Link.InitialGateBounds.GetSize().Z-Link.GateFloorOffset)+FMath::Max(.1f,Settings->GateFloorClearance));
		Link.bPressed = Link.bCompleted = Link.bGateOpening = Link.bSeating = Link.bRevealPending = false;
		Link.GateOffset = 0;
		Link.PushVelocity = FVector::ZeroVector;
	}
	bInitialized = true;
	NotifyObstaclesChanged();
}
bool ACatrunStatuePuzzle::IsGameplayAvailable() const
{
	if (!GetWorld() || GetWorld()->bIsTearingDown || GetWorld()->IsInSeamlessTravel()) return false;
	if (GEngine) if (const auto* Context = GEngine->GetWorldContextFromWorld(GetWorld()); Context && !Context->TravelURL.IsEmpty()) return false;
	if (const auto* Flow = UCatrunLevelFlowSubsystem::Get(this); Flow && (Flow->IsTransitioning() || Flow->IsStageComplete())) return false;
	const auto* Restart = UCatrunRestartSubsystem::Get(this);
	return !Restart || !Restart->IsCatching();
}
void ACatrunStatuePuzzle::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	for (auto& Link : Links) Link.bDrivenThisFrame = false;
	ACharacter* Cat = Cast<ACharacter>(UGameplayStatics::GetPlayerPawn(this, 0));
	APlayerController* PC = Cat ? Cast<APlayerController>(Cat->GetController()) : nullptr;
	if (IsGameplayAvailable() && !UCatrunPuzzleSuspension::IsSuspended(this) && Cat && PC && !PC->IsMoveInputIgnored()
		&& Settings && (!Settings->bRequireInteractKey || PC->IsInputKeyDown(UCatrunInputBindings::GetEffectiveKey(ECatrunInputSlot::Interact))))
		for (int32 Index=0; Index<Links.Num(); ++Index)
			if (TryPushStatue(Index,Cat,Cat->GetLastMovementInputVector(),DeltaSeconds)) break;
	// Friction continues on release, with real collision and no free sliding through the cat.
	for (auto& Link : Links)
	{
		if (!IsGameplayAvailable() || UCatrunPuzzleSuspension::IsSuspended(this)) { Link.PushVelocity = FVector::ZeroVector; continue; }
		if (Link.bDrivenThisFrame || Link.bPressed || Link.PushVelocity.IsNearlyZero() || !Settings) continue;
		float Speed = Link.PushVelocity.Size();
		const FVector Direction = Link.PushVelocity.GetSafeNormal();
		const float Distance = IntegratePushSpeed(Speed,0,Settings->PushDeceleration,DeltaSeconds);
		Link.PushVelocity = Direction*Speed;
		MoveStatue(Link,Direction*Distance,nullptr);
	}
	UpdatePlatesAndGates(DeltaSeconds);
}
float ACatrunStatuePuzzle::IntegratePushSpeed(float& Speed, float Target, float Acceleration, float DeltaSeconds)
{
	const float Time = FMath::Max(0.f,DeltaSeconds);
	const float Rate = FMath::Max(1.f,Acceleration);
	const float Reach = FMath::Min(Time,FMath::Abs(Target-Speed)/Rate);
	const float Next = FMath::FInterpConstantTo(Speed,Target,Reach,Rate);
	const float Distance = (Speed+Next)*.5f*Reach + Target*(Time-Reach);
	Speed = Next;
	return Distance;
}
bool ACatrunStatuePuzzle::CanMoveStatue(const FCatrunStatuePuzzleLink& Link, const FVector& Delta, const AActor* Cat) const
{
	if (!IsValid(Link.Statue)) return false;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(StatuePush), false, Link.Statue);
	if (Cat) Params.AddIgnoredActor(Cat);
	// Only the low plate/rim is traversable. The swept body starts 20cm above its base.
	FVector Extent = Link.StatueExtent;
	Extent.Z = FMath::Max(1.,Extent.Z-10.);
	const FVector Start = Link.Statue->GetActorLocation()+Link.StatueCenterOffset+FVector(0,0,10);
	FCollisionObjectQueryParams Objects;
	Objects.AddObjectTypesToQuery(ECC_WorldStatic);
	Objects.AddObjectTypesToQuery(ECC_WorldDynamic);
	Objects.AddObjectTypesToQuery(ECC_Pawn);
	TArray<FHitResult> Hits;
	GetWorld()->SweepMultiByObjectType(Hits,Start,Start+Delta,FQuat::Identity,Objects,FCollisionShape::MakeBox(Extent),Params);
	for (const auto& Hit : Hits)
		if (Hit.GetComponent() && Hit.GetComponent()->GetCollisionResponseToChannel(ECC_Pawn)==ECR_Block) return false;
	TArray<FOverlapResult> EndHits;
	GetWorld()->OverlapMultiByObjectType(EndHits,Start+Delta,FQuat::Identity,Objects,FCollisionShape::MakeBox(Extent),Params);
	for (const auto& Hit : EndHits)
		if (Hit.GetComponent() && Hit.GetComponent()->GetCollisionResponseToChannel(ECC_Pawn)==ECR_Block) return false;
	// Floor support includes the actual body offset, not an assumed floor-pivot asset.
	const FVector Base = Start+Delta-FVector(0,0,Extent.Z);
	for (double X : {-Extent.X+3,Extent.X-3}) for (double Y : {-Extent.Y+3,Extent.Y-3})
	{
		FHitResult Floor;
		const FVector Point = Base+FVector(X,Y,5);
		if (!GetWorld()->LineTraceSingleByChannel(Floor,Point,Point-FVector(0,0,40),ECC_Visibility,Params) || Floor.ImpactNormal.Z<.7f) return false;
	}
	return true;
}
bool ACatrunStatuePuzzle::MoveStatue(FCatrunStatuePuzzleLink& Link,const FVector& Delta,const AActor* Cat)
{
	if (Delta.IsNearlyZero()) return false;
	if (!CanMoveStatue(Link,Delta,Cat)) { Link.PushVelocity=FVector::ZeroVector; return false; }
	Link.Statue->SetActorLocation(Link.Statue->GetActorLocation()+Delta,false);
	NotifyObstaclesChanged();
	return true;
}
bool ACatrunStatuePuzzle::TryPushStatue(int32 Index,ACharacter* Cat,FVector Input,float DeltaSeconds)
{
	if (!bInitialized || bResetting || bUpdating || !Links.IsValidIndex(Index) || !IsValid(Cat) || !Settings || DeltaSeconds<=0 || !IsGameplayAvailable()
		|| UCatrunPuzzleSuspension::IsSuspended(this)) return false;
	auto& Link = Links[Index];
	if (Link.bPressed || Link.bSeating || !IsValid(Link.Statue) || !Cat->GetCharacterMovement()->IsMovingOnGround()) return false;
	if (const auto* PC=Cast<APlayerController>(Cat->GetController()); PC && PC->IsMoveInputIgnored()) return false;
	const auto* Actions=Cat->FindComponentByClass<UCatrunBasketInteractionComponent>();
	if (Actions && (Actions->Busy || Actions->IsHidden)) return false;
	Input.Z=0;
	if (!Input.Normalize()) return false;
	const FVector Direction=FMath::Abs(Input.X)>=FMath::Abs(Input.Y) ? FVector(FMath::Sign(Input.X),0,0) : FVector(0,FMath::Sign(Input.Y),0);
	const FVector FromStatue=Cat->GetActorLocation()-(Link.Statue->GetActorLocation()+Link.StatueCenterOffset);
	const float Radius=Cat->GetCapsuleComponent()->GetScaledCapsuleRadius();
	const double Half=Direction.X!=0 ? Link.StatueExtent.X : Link.StatueExtent.Y;
	const double SideHalf=Direction.X!=0 ? Link.StatueExtent.Y : Link.StatueExtent.X;
	const double Gap=-FVector::DotProduct(FromStatue,Direction)-Half-Radius;
	const double Side=FMath::Abs(Direction.X!=0 ? FromStatue.Y : FromStatue.X);
	if (Gap < -5 || Gap > Settings->ContactDistance || Side > SideHalf-Radius*.25 || FMath::Abs(FromStatue.Z)>Link.StatueExtent.Z+50) return false;
	float Speed=FMath::Max(0.f,float(FVector::DotProduct(Link.PushVelocity,Direction)));
	const float Distance=IntegratePushSpeed(Speed,FMath::Min(Settings->PushSpeed,Cat->GetCharacterMovement()->GetMaxSpeed()),Settings->PushAcceleration,DeltaSeconds);
	Link.PushVelocity=Direction*Speed;
	Link.bDrivenThisFrame=true;
	return MoveStatue(Link,Direction*Distance,Cat);
}
float ACatrunStatuePuzzle::GetSeatingOverlap(int32 Index) const
{
	if (!Links.IsValidIndex(Index) || !IsValid(Links[Index].Statue)) return 0;
	const auto& Link=Links[Index];
	const FVector Center=Link.Statue->GetActorLocation()+Link.StatueCenterOffset;
	const FVector Extent=Link.StatueExtent;
	const FVector2D Half(Link.ContactHalfExtent.X>0 ? Link.ContactHalfExtent.X : Extent.X,Link.ContactHalfExtent.Y>0 ? Link.ContactHalfExtent.Y : Extent.Y);
	const FBox& Plate=Link.InitialPlateBounds;
	const double Width=FMath::Max(0.,FMath::Min(Center.X+Half.X,Plate.Max.X)-FMath::Max(Center.X-Half.X,Plate.Min.X));
	const double Height=FMath::Max(0.,FMath::Min(Center.Y+Half.Y,Plate.Max.Y)-FMath::Max(Center.Y-Half.Y,Plate.Min.Y));
	const double Area=FMath::Min(4.*Half.X*Half.Y,Plate.GetSize().X*Plate.GetSize().Y);
	return Area>0 ? Width*Height/Area : 0;
}
bool ACatrunStatuePuzzle::Broadcast(int32 Index,ECatrunStatueEvent Event,int32 Expected)
{
	OnPuzzleEvent.Broadcast(Links[Index].PuzzleId,Event,Expected);
	return IsValid(this) && Links.IsValidIndex(Index) && Links[Index].Revision==Expected && !bResetting
		&& IsValid(Links[Index].Statue) && IsValid(Links[Index].Plate) && IsValid(Links[Index].Gate);
}
bool ACatrunStatuePuzzle::TrySeat(int32 Index)
{
	auto& Link=Links[Index];
	if (Link.bPressed || Link.bSeating || !IsGameplayAvailable() || UCatrunPuzzleSuspension::IsSuspended(this)) return false;
	const FVector Delta=Link.SeatLocation-Link.Statue->GetActorLocation();
	const FVector Side=FVector::CrossProduct(Link.SeatingAxis,FVector::UpVector);
	if (GetSeatingOverlap(Index)+1.e-6f < FMath::Clamp(Settings->SeatingOverlap,.5f,1.f)
		|| FMath::Abs(FVector::DotProduct(Delta,Side))>Settings->SocketAxisTolerance
		|| FMath::Abs(Delta.Z)>Settings->SocketHeightTolerance
		|| FMath::Abs(Link.InitialPlateBounds.Min.Z-(Link.Statue->GetActorLocation().Z+Link.StatueCenterOffset.Z-Link.StatueExtent.Z))>Settings->SocketHeightTolerance
		|| !Link.Statue->GetActorQuat().Equals(Link.InitialStatue.GetRotation(),.01)
		|| !CanMoveStatue(Link,Delta,nullptr)) return false;
	const int32 Revision=Link.Revision;
	Link.bSeating=true;
	if (!Broadcast(Index,ECatrunStatueEvent::SnapStarted,Revision)) return false;
	// A callback may introduce a blocker or start travel. Revalidate before the atomic seat.
	if (!IsGameplayAvailable() || !CanMoveStatue(Link,Link.SeatLocation-Link.Statue->GetActorLocation(),nullptr)) { Link.bSeating=false; return false; }
	Link.Statue->SetActorLocation(Link.SeatLocation,false);
	Link.PushVelocity=FVector::ZeroVector;
	Link.bPressed=true;
	Link.bRevealPending=true;
	Link.bSeating=false;
	Link.Plate->SetActorLocation(Link.InitialPlate-FVector(0,0,Settings->PlateTravel),false);
	NotifyObstaclesChanged();
	OnPlateChanged(Link.PuzzleId,true);
	if (!IsValid(this) || !IsValid(Link.Statue) || !IsValid(Link.Plate) || !IsValid(Link.Gate) || Link.Revision!=Revision || !Link.bPressed) return false;
	if (!Broadcast(Index,ECatrunStatueEvent::Seated,Revision) || !Link.bPressed) return false;
	return Link.Revision==Revision && Link.bPressed;
}
bool ACatrunStatuePuzzle::IsGateClear(const FCatrunStatuePuzzleLink& Link,float NewOffset) const
{
	FCollisionQueryParams Params(SCENE_QUERY_STAT(PuzzleGate),false,Link.Gate);
	FCollisionObjectQueryParams Objects(ECC_Pawn);
	Objects.AddObjectTypesToQuery(ECC_WorldDynamic);
	// Conservative continuous swept occupancy, clipped below the authored base plane.
	// WorldStatic is the designed recess; dynamic floor geometry ending at that plane is excluded too.
	FBox Swept=Link.InitialGateBounds.ShiftBy(FVector(0,0,NewOffset));
	Swept+=Link.InitialGateBounds.ShiftBy(FVector(0,0,Link.GateOffset));
	Swept.Min.Z=FMath::Max(Swept.Min.Z,Link.InitialGateBounds.Min.Z+Link.GateFloorOffset+.5);
	if (Swept.Max.Z<=Swept.Min.Z) return true;
	TArray<FOverlapResult> Hits;
	GetWorld()->OverlapMultiByObjectType(Hits,Swept.GetCenter(),FQuat::Identity,Objects,FCollisionShape::MakeBox(Swept.GetExtent()+FVector(2,2,0)),Params);
	for (const auto& Hit : Hits)
		if (Hit.GetComponent() && Hit.GetComponent()->GetCollisionResponseToChannel(ECC_Pawn)==ECR_Block) return false;
	return true;
}
void ACatrunStatuePuzzle::UpdatePlatesAndGates(float DeltaSeconds)
{
	if (!bInitialized || !Settings || bUpdating || bResetting) return;
	TGuardValue<bool> Updating(bUpdating,true);
	if (!IsGameplayAvailable()) { Reveal->CancelReveal(); return; }
	bool Changed=false;
	for (int32 Index=0; Index<Links.Num(); ++Index)
	{
		auto& Link=Links[Index];
		if (!IsValid(Link.Statue) || !IsValid(Link.Plate) || !IsValid(Link.Gate)) continue;
		TrySeat(Index);
		if (!IsValid(this) || !IsGameplayAvailable()) { Reveal->CancelReveal(); break; }
		const int32 Revision=Link.Revision;
		if (Link.bPressed && Link.bRevealPending)
		{
			const auto* Cat = UGameplayStatics::GetPlayerPawn(this,0);
			const auto* Actions = Cat ? Cat->FindComponentByClass<UCatrunBasketInteractionComponent>() : nullptr;
			// Keep the solve and gate closed until the existing action finishes naturally.
			if ((Actions && (Actions->Busy || Actions->IsHidden)) || UCatrunPuzzleSuspension::IsSuspended(this)
				|| Reveal->Phase != ECatrunPuzzleRevealPhase::Inactive) continue;
			// One acquisition attempt once contention ends. Missing/disabled presentation falls
			// back immediately; acquired presentation retains its existing bounded timeout.
			Link.bRevealPending=false;
			Reveal->BeginReveal(Link.PuzzleId,Link.Gate,Link.InitialGateBounds);
			if (!IsValid(this) || Link.Revision!=Revision || !Link.bPressed || !IsGameplayAvailable()) continue;
		}
		if (Link.bPressed && !Reveal->CanOpenGate(Link.PuzzleId)) continue;
		if (Link.bPressed && !Link.bGateOpening)
		{
			Link.bGateOpening=true;
			if (!Broadcast(Index,ECatrunStatueEvent::GateOpening,Revision) || !Link.bPressed || !IsGameplayAvailable()) continue;
		}
		const float Offset=FMath::FInterpConstantTo(Link.GateOffset,Link.bPressed ? -Link.RequiredGateTravel : 0.f,FMath::Max(0.f,DeltaSeconds),FMath::Max(1.f,Settings->GateSpeed));
		if (!FMath::IsNearlyEqual(Offset,Link.GateOffset) && IsGateClear(Link,Offset))
		{
			Link.GateOffset=Offset;
			Link.Gate->SetActorLocation(Link.InitialGate+FVector(0,0,Offset),false);
			Changed=true;
		}
		if (Link.bPressed && !Link.bCompleted && FMath::IsNearlyEqual(Link.GateOffset,-Link.RequiredGateTravel))
		{
			Link.bCompleted=true;
			if (Broadcast(Index,ECatrunStatueEvent::Completed,Revision) && Link.bCompleted) Reveal->GateOpened(Link.PuzzleId);
		}
	}
	if (Changed) NotifyObstaclesChanged();
}
bool ACatrunStatuePuzzle::ResetPuzzle()
{
	TArray<int32> Indices;
	for (int32 Index=0;Index<Links.Num();++Index) Indices.Add(Index);
	return ResetStatues(Indices);
}
bool ACatrunStatuePuzzle::ResetStatue(FName PuzzleId)
{
	const int32 Index=Links.IndexOfByPredicate([PuzzleId](const auto& Link){return Link.PuzzleId==PuzzleId;});
	return Index!=INDEX_NONE && ResetStatues({Index});
}
bool ACatrunStatuePuzzle::ResetStatues(const TArray<int32>& Indices)
{
	if (!bInitialized || bResetting) return false;
	for (int32 Index : Indices)
	{
		if (!Links.IsValidIndex(Index) || !IsValid(Links[Index].Statue)) return false;
		const auto& Link=Links[Index];
		FCollisionQueryParams Params(SCENE_QUERY_STAT(PuzzleReset),false,Link.Statue);
		for (int32 Other : Indices) if (Links.IsValidIndex(Other) && Links[Other].Statue) Params.AddIgnoredActor(Links[Other].Statue);
		FCollisionObjectQueryParams Objects(ECC_Pawn);
		Objects.AddObjectTypesToQuery(ECC_WorldDynamic);
		Objects.AddObjectTypesToQuery(ECC_WorldStatic);
		TArray<FOverlapResult> Hits;
		GetWorld()->OverlapMultiByObjectType(Hits,Link.InitialStatue.GetLocation()+Link.StatueCenterOffset+FVector(0,0,10),FQuat::Identity,Objects,
			FCollisionShape::MakeBox(FVector(Link.StatueExtent.X,Link.StatueExtent.Y,FMath::Max(1.,Link.StatueExtent.Z-10))),Params);
		for (const auto& Hit : Hits)
			if (Hit.GetComponent() && Hit.GetComponent()->GetCollisionResponseToChannel(ECC_Pawn)==ECR_Block) return false;
	}
	TGuardValue<bool> Resetting(bResetting,true);
	bool Changed=false;
	// Invalidate old callbacks before cancellation can invoke BP.
	for (int32 Index : Indices) ++Links[Index].Revision;
	if (Indices.ContainsByPredicate([this](int32 Index){return Links[Index].PuzzleId==Reveal->PuzzleId;})) Reveal->CancelReveal();
	for (int32 Index : Indices)
	{
		auto& Link=Links[Index];
		Changed |= !Link.Statue->GetActorTransform().Equals(Link.InitialStatue) || Link.bPressed;
		Link.Statue->SetActorTransform(Link.InitialStatue,false,nullptr,ETeleportType::TeleportPhysics);
		Link.PushVelocity=FVector::ZeroVector;
		Link.bPressed=Link.bCompleted=Link.bSeating=Link.bGateOpening=Link.bRevealPending=false;
		if (IsValid(Link.Plate)) Link.Plate->SetActorLocation(Link.InitialPlate,false);
		OnPlateChanged(Link.PuzzleId,false);
		OnPuzzleEvent.Broadcast(Link.PuzzleId,ECatrunStatueEvent::Reset,Link.Revision);
		// Gate closes on subsequent checked updates, never teleports around an occupant.
	}
	if (Changed) NotifyObstaclesChanged();
	return true;
}
void ACatrunStatuePuzzle::GetObstacleBounds(TArray<FBox>& OutBounds) const
{
	for (const auto& Link : Links)
	{
		if (IsValid(Link.Statue)) OutBounds.Add(Link.Statue->GetComponentsBoundingBox(true));
		if (IsValid(Link.Gate) && Link.InitialGateBounds.Max.Z+Link.GateOffset>Link.InitialGateBounds.Min.Z+Link.GateFloorOffset)
			OutBounds.Add(Link.Gate->GetComponentsBoundingBox(true));
	}
}
void ACatrunStatuePuzzle::NotifyObstaclesChanged()
{
	if (auto* Manager=ASoundGridManager::Get(this)) Manager->InvalidatePuzzleObstacles();
}
