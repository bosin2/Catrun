#include "SoundGridManager.h"
#include "Interaction/CatrunPuzzleSuspension.h"

#include "Catrun.h"
#include "CatrunBellComponent.h"
#include "Perception/CatrunCatStateComponent.h"
#include "CatrunDoor.h"
#include "Interaction/CatrunStatuePuzzle.h"
#include "CatrunSoundSettings.h"
#include "SoundPropagation.h"
#include "Components/BoxComponent.h"
#include "DrawDebugHelpers.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "Serialization/JsonWriter.h"
#include "Policies/CondensedJsonPrintPolicy.h"

using namespace CatrunGrid;

const FName ASoundGridManager::SoundBlockerTag(TEXT("SoundBlocker"));

FString ASoundGridManager::ExportBakedGridSnapshot() const
{
	FString Output;
	const auto Writer = TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&Output);
	Writer->WriteObjectStart();
	Writer->WriteArrayStart(TEXT("Origin"));
	Writer->WriteValue(Grid.Origin.X); Writer->WriteValue(Grid.Origin.Y); Writer->WriteValue(Grid.Origin.Z);
	Writer->WriteArrayEnd();
	Writer->WriteValue(TEXT("CellSize"), Grid.CellSize);
	Writer->WriteValue(TEXT("Width"), Grid.Width);
	Writer->WriteValue(TEXT("Height"), Grid.Height);
	auto Array = [&Writer](const TCHAR* Name, const auto& Values)
	{
		Writer->WriteArrayStart(Name);
		for (const auto Value : Values) Writer->WriteValue(static_cast<double>(Value));
		Writer->WriteArrayEnd();
	};
	Array(TEXT("Walkable"), Grid.Walkable);
	Array(TEXT("CostMultiplier"), Grid.CostMultiplier);
	Array(TEXT("EdgeMask"), Grid.EdgeMask);
	Array(TEXT("WallDistance"), Grid.WallDistance);
	Writer->WriteValue(TEXT("WallProbeLength"), Grid.WallProbeLength);
	Writer->WriteObjectEnd(); Writer->Close();
	return Output;
}

ASoundGridManager::ASoundGridManager()
{
	PrimaryActorTick.bCanEverTick = true;

	SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
}

ASoundGridManager* ASoundGridManager::Get(const UObject* WorldContextObject)
{
	const UWorld* World = GEngine ? GEngine->GetWorldFromContextObject(WorldContextObject, EGetWorldErrorMode::ReturnNull) : nullptr;
	if (World)
	{
		for (TActorIterator<ASoundGridManager> It(World); It; ++It)
		{
			return *It;
		}
	}
	return nullptr;
}

const FCatrunGridData& ASoundGridManager::GetGrid() const
{
	RefreshPuzzleObstacles();
	return Grid;
}

void ASoundGridManager::RefreshPuzzleObstacles() const
{
	if (!bPuzzleObstaclesDirty || !Grid.IsValid() || !GetWorld()) return;
	bPuzzleObstaclesDirty = false;
	TArray<FBox> Boxes;
	for (TActorIterator<ACatrunStatuePuzzle> It(GetWorld()); It; ++It) It->GetObstacleBounds(Boxes);
	if (Boxes.IsEmpty())
	{
		Grid.PuzzleClearance.Reset();
		return;
	}
	Grid.PuzzleClearance.Init(MAX_flt,Grid.NumCells());
	for (int32 Cell=0; Cell<Grid.NumCells(); ++Cell)
	{
		const FVector Center = Grid.CellCenter(Cell);
		for (const FBox& Box : Boxes)
		{
			// Keep a rising gate closed to routing until the full 2m armor can pass.
			if (!Box.IsValid || Box.Min.Z > Grid.Origin.Z+210 || Box.Max.Z < Grid.Origin.Z+10) continue;
			const double DX = FMath::Max3(Box.Min.X-Center.X,0.,Center.X-Box.Max.X);
			const double DY = FMath::Max3(Box.Min.Y-Center.Y,0.,Center.Y-Box.Max.Y);
			Grid.PuzzleClearance[Cell] = FMath::Min(Grid.PuzzleClearance[Cell],static_cast<float>(FMath::Sqrt(DX*DX+DY*DY)));
		}
	}
}

// ---------------------------------------------------------------------------
// Life cycle
// ---------------------------------------------------------------------------

void ASoundGridManager::BeginPlay()
{
	Super::BeginPlay();

	if (!Settings)
	{
		Settings = NewObject<UCatrunSoundSettings>(this, TEXT("DefaultSoundSettings"));
		UE_LOG(LogCatrunSound, Warning, TEXT("SoundGridManager has no Settings asset. Using default values."));
	}
	if (!HasGrid())
	{
		UE_LOG(LogCatrunSound, Log, TEXT("No baked grid found. Building it now."));
		BuildGrid();
	}
	RefreshDoorGates();
}

void ASoundGridManager::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	DeliveryBudget = 32;
	if (!UCatrunPuzzleSuspension::IsSuspended(this)) ListenerClock += FMath::Max(0.f, DeltaSeconds);
	DeliverPendingSounds();
	if (bAutoAttachBell && !bBellAttached)
	{
		AttachBellToPlayer();
	}
	if (bDebugDrawGrid)
	{
		DebugDrawGrid();
	}
}

void ASoundGridManager::BuildGrid()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	if (!Settings)
	{
		Settings = NewObject<UCatrunSoundSettings>(this, TEXT("DefaultSoundSettings"));
	}
	if (Grid.Bake(*World, *Settings))
	{
		InvalidatePuzzleObstacles();
		LastDistance.Reset();
		RefreshDoorGates();
		Modify();
	}
}

// The player pawn is not always ready in BeginPlay, so this runs from Tick until it succeeds.
void ASoundGridManager::AttachBellToPlayer()
{
	APawn* Pawn = UGameplayStatics::GetPlayerPawn(this, 0);
	if (!Pawn)
	{
		return;
	}
	bBellAttached = true;
	if (!Pawn->FindComponentByClass<UCatrunBellComponent>())
	{
		UCatrunBellComponent* Bell = NewObject<UCatrunBellComponent>(Pawn, TEXT("BellComponent"));
		Pawn->AddInstanceComponent(Bell);
		Bell->RegisterComponent();
		UE_LOG(LogCatrunSound, Log, TEXT("Bell component added to %s."), *Pawn->GetName());
	}
	// Footsteps and hideout entry (the cat's own blueprints are only read, never changed).
	if (!Pawn->FindComponentByClass<UCatrunCatStateComponent>())
	{
		UCatrunCatStateComponent* State = NewObject<UCatrunCatStateComponent>(Pawn, TEXT("CatStateComponent"));
		Pawn->AddInstanceComponent(State);
		State->RegisterComponent();
		UE_LOG(LogCatrunSound, Log, TEXT("Cat state component added to %s."), *Pawn->GetName());
	}
}

// ---------------------------------------------------------------------------
// Doors
// ---------------------------------------------------------------------------

// Finds, for every door, the cells under its gate box, and counts the closed doors per cell.
// Sound-blocking furniture is added to the same count.
void ASoundGridManager::RefreshDoorGates()
{
	UWorld* World = GetWorld();
	if (!World || !HasGrid())
	{
		return;
	}
	ClosedGateCells.Init(0, Grid.NumCells());
	DoorCells.Reset();

	for (TActorIterator<ACatrunDoor> It(World); It; ++It)
	{
		ACatrunDoor* Door = *It;
		const FBox GateBox = Door->GetGateBox()->Bounds.GetBox();
		TArray<int32>& Cells = DoorCells.Add(Door);

		for (int32 Cell = 0; Cell < Grid.NumCells(); ++Cell)
		{
			if (!Grid.IsWalkable(Cell))
			{
				continue;
			}
			const FVector Center = Grid.CellCenter(Cell);
			if (Center.X >= GateBox.Min.X && Center.X <= GateBox.Max.X && Center.Y >= GateBox.Min.Y && Center.Y <= GateBox.Max.Y)
			{
				Cells.Add(Cell);
				if (!Door->IsOpen())
				{
					ClosedGateCells[Cell]++;
				}
			}
		}
	}

	// Furniture that blocks sound. Cells are tested against the real (rotated) shape, so a turned
	// shelf does not block the floor next to it.
	SoundBlockerCells.Init(0, Grid.NumCells());
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		if (!It->ActorHasTag(SoundBlockerTag))
		{
			continue;
		}
		It->ForEachComponent<UPrimitiveComponent>(false, [this](const UPrimitiveComponent* Shape)
		{
			if (!Shape->IsRegistered() || !Shape->IsCollisionEnabled())
			{
				return;
			}
			const FBox Local = Shape->CalcBounds(FTransform::Identity).GetBox();
			const FTransform& ToWorld = Shape->GetComponentTransform();
			const FBox Covered = Shape->Bounds.GetBox();
			for (int32 Cell = 0; Cell < Grid.NumCells(); ++Cell)
			{
				FVector Center = Grid.CellCenter(Cell);
				if (Center.X < Covered.Min.X || Center.X > Covered.Max.X || Center.Y < Covered.Min.Y || Center.Y > Covered.Max.Y)
				{
					continue;
				}
				Center.Z = Covered.GetCenter().Z;
				if (Local.IsInsideOrOn(ToWorld.InverseTransformPosition(Center)))
				{
					SoundBlockerCells[Cell] = 1;
				}
			}
		});
	}
	for (int32 Cell = 0; Cell < Grid.NumCells(); ++Cell)
	{
		ClosedGateCells[Cell] += SoundBlockerCells[Cell];
	}
}

bool ASoundGridManager::IsSoundCell(int32 Cell) const
{
	return Grid.IsWalkable(Cell) && !(SoundBlockerCells.IsValidIndex(Cell) && SoundBlockerCells[Cell] != 0);
}

void ASoundGridManager::NotifyDoorStateChanged(ACatrunDoor* Door)
{
	// Doors are few, so simply count everything again. This never drifts out of sync.
	RefreshDoorGates();
}

void ASoundGridManager::GetClosedDoors(TArray<ACatrunDoor*>& OutDoors) const
{
	for (const TPair<TWeakObjectPtr<ACatrunDoor>, TArray<int32>>& Pair : DoorCells)
	{
		ACatrunDoor* Door = Pair.Key.Get();
		if (Door && !Door->IsOpen())
		{
			OutDoors.Add(Door);
		}
	}
}

// ---------------------------------------------------------------------------
// Making and hearing sounds
// ---------------------------------------------------------------------------

bool ASoundGridManager::EmitSound(const FCatrunSoundEvent& Event)
{
	UWorld* World = GetWorld();
	if (!World || !HasGrid() || !Settings)
	{
		return false;
	}
	RefreshPuzzleObstacles();

	// 1) Where does the sound start? Use the closest floor cell to the given location.
	const int32 SourceCell = Grid.FindNearestCell(Event.Location, 3, [this](int32 Cell) { return IsSoundCell(Cell); });
	if (SourceCell == INDEX_NONE)
	{
		UE_LOG(LogCatrunSound, Warning, TEXT("EmitSound: no floor cell near %s."), *Event.Location.ToString());
		return false;
	}

	// 2) Spread the sound over the grid.
	const bool bPlayerBell = Event.Source == ECatrunSoundSource::Cat && Event.Kind == ECatrunSoundKind::Bell;
	LastBudget = bPlayerBell && FMath::IsFinite(PlayerBellBudgetOverride) && PlayerBellBudgetOverride > 0.f
		? PlayerBellBudgetOverride : Settings->GetBudget(Event.Size);
	const int32 NumReached = CatrunSoundPropagation::Run(Grid, ClosedGateCells, SourceCell, LastBudget, LastDistance);
	UE_LOG(LogCatrunSound, Log, TEXT("EmitSound: size=%d budget=%.0f reached %d cells."), static_cast<int32>(Event.Size), LastBudget, NumReached);

	// 3) The wave is drawn by the ripple blueprints. They copy this picture of the spread in
	// OnSoundEmitted. It needs distances a little beyond the budget, so the end of the wave fades
	// out smoothly instead of being cut along the 25 cm cells.
	const float PictureBudget = LastBudget + Grid.CellSize * 2.f;
	CatrunSoundPropagation::Run(Grid, ClosedGateCells, SourceCell, PictureBudget, PictureDistance);
	const double Now = ListenerClock;

	// 4) Schedule the moment each listener hears it: when the wave reaches them.
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* Actor = *It;
		if (!Actor->Implements<UCatrunSoundListener>() || ICatrunSoundListener::Execute_GetListenerGroup(Actor) != Event.Target)
		{
			continue;
		}
		const float Remaining = GetRemainingBudgetAt(Actor->GetActorLocation());
		if (Remaining <= 0.f)
		{
			continue; // the sound does not reach this listener
		}
		FPendingSound Pending;
		Pending.Listener = Actor;
		Pending.Event = Event;
		Pending.RemainingBudget = Remaining;
		Pending.ArrivalTime = Now + (LastBudget - Remaining) / FMath::Max(1.f, Settings->SoundSpeed); // travelled distance / speed
		PendingSounds.Add(Pending);
	}
	DeliverPendingSounds(); // listeners standing at the source hear it right away

	OnSoundEmitted.Broadcast(Event, LastBudget);
	return true;
}

// Tells listeners about sounds whose wave has arrived.
void ASoundGridManager::DeliverPendingSounds()
{
	if (bDeliveringSounds || UCatrunPuzzleSuspension::IsSuspended(this)) return;
	TGuardValue<bool> Guard(bDeliveringSounds, true);
	// Callback may append events or acquire suspension. Remove only the selected snapshot before calling it.
	while (DeliveryBudget > 0 && !UCatrunPuzzleSuspension::IsSuspended(this))
	{
		PendingSounds.RemoveAll([](const FPendingSound& Entry) { return !Entry.Listener.IsValid(); });
		int32 Next = INDEX_NONE;
		for (int32 Index=0; Index<PendingSounds.Num(); ++Index)
			if (PendingSounds[Index].ArrivalTime <= ListenerClock && (Next == INDEX_NONE || PendingSounds[Index].ArrivalTime < PendingSounds[Next].ArrivalTime)) Next = Index;
		if (Next == INDEX_NONE) break;
		const FPendingSound Pending = PendingSounds[Next];
		PendingSounds.RemoveAt(Next); // stable insertion ordering for equal arrival times
		--DeliveryBudget;
		if (AActor* Listener = Pending.Listener.Get())
			ICatrunSoundListener::Execute_OnSoundHeard(Listener, Pending.Event, Pending.RemainingBudget);
	}
}

float ASoundGridManager::GetRemainingBudgetAt(const FVector& WorldLocation) const
{
	if (LastDistance.IsEmpty())
	{
		return -1.f;
	}
	const int32 Cell = Grid.FindNearestCell(WorldLocation, 1, [this](int32 C) { return IsSoundCell(C); });
	if (Cell == INDEX_NONE || LastDistance[Cell] == CatrunSoundPropagation::Unreached)
	{
		return -1.f;
	}
	return LastBudget - LastDistance[Cell];
}

// ---------------------------------------------------------------------------
// Debug
// ---------------------------------------------------------------------------

void ASoundGridManager::DebugDrawGrid() const
{
#if ENABLE_DRAW_DEBUG
	UWorld* World = GetWorld();
	if (!World || !HasGrid())
	{
		return;
	}
	const float Z = Grid.Origin.Z + 2.f;
	const float Half = Grid.CellSize * 0.5f;
	for (int32 Cell = 0; Cell < Grid.NumCells(); ++Cell)
	{
		if (!Grid.IsWalkable(Cell))
		{
			continue;
		}
		const FVector Center = Grid.CellCenter(Cell) + FVector(0.f, 0.f, 2.f);
		const bool bClosedDoor = ClosedGateCells.IsValidIndex(Cell) && ClosedGateCells[Cell] > 0;
		DrawDebugPoint(World, Center, 3.f, bClosedDoor ? FColor::Red : FColor(60, 200, 60), false, -1.f);

		// A wall edge = both cells are floor, but the edge between them is closed.
		const int32 East = Grid.Neighbor(Cell, DirE);
		if (East != INDEX_NONE && Grid.IsWalkable(East) && !Grid.IsEdgeOpen(Cell, DirE))
		{
			DrawDebugLine(World, FVector(Center.X + Half, Center.Y - Half, Z), FVector(Center.X + Half, Center.Y + Half, Z), FColor::Red, false, -1.f, 0, 2.f);
		}
		const int32 South = Grid.Neighbor(Cell, DirS);
		if (South != INDEX_NONE && Grid.IsWalkable(South) && !Grid.IsEdgeOpen(Cell, DirS))
		{
			DrawDebugLine(World, FVector(Center.X - Half, Center.Y + Half, Z), FVector(Center.X + Half, Center.Y + Half, Z), FColor::Red, false, -1.f, 0, 2.f);
		}
	}
#endif
}
