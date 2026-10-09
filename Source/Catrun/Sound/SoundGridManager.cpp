#include "SoundGridManager.h"

#include "Catrun.h"
#include "CatrunBellComponent.h"
#include "Perception/CatrunCatStateComponent.h"
#include "CatrunDoor.h"
#include "CatrunSoundSettings.h"
#include "SoundPropagation.h"
#include "SoundWaveVisual.h"
#include "Components/BoxComponent.h"
#include "DrawDebugHelpers.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"

using namespace CatrunGrid;

ASoundGridManager::ASoundGridManager()
{
	PrimaryActorTick.bCanEverTick = true;

	SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
	WaveVisual = CreateDefaultSubobject<USoundWaveVisual>(TEXT("WaveVisual"));
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
	WaveVisual->Initialize(Grid, *Settings);
}

void ASoundGridManager::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

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

	// 1) Where does the sound start? Use the closest floor cell to the given location.
	const int32 SourceCell = Grid.FindNearestCell(Event.Location, 3, [this](int32 Cell) { return Grid.IsWalkable(Cell); });
	if (SourceCell == INDEX_NONE)
	{
		UE_LOG(LogCatrunSound, Warning, TEXT("EmitSound: no floor cell near %s."), *Event.Location.ToString());
		return false;
	}

	// 2) Spread the sound over the grid.
	LastBudget = Settings->GetBudget(Event.Size);
	const int32 NumReached = CatrunSoundPropagation::Run(Grid, ClosedGateCells, SourceCell, LastBudget, LastDistance);
	UE_LOG(LogCatrunSound, Log, TEXT("EmitSound: size=%d budget=%.0f reached %d cells."), static_cast<int32>(Event.Size), LastBudget, NumReached);

	// 3) Draw the wave. The picture needs distances a little beyond the budget, so the end of the
	// wave fades out smoothly instead of being cut along the 25 cm cells.
	const float PictureBudget = LastBudget + Grid.CellSize * 2.f;
	CatrunSoundPropagation::Run(Grid, ClosedGateCells, SourceCell, PictureBudget, PictureDistance);
	const double Now = World->GetTimeSeconds();
	WaveVisual->Show(Grid, PictureDistance, LastBudget, Now);

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
		Pending.ArrivalTime = Now + (LastBudget - Remaining) / Settings->SoundSpeed; // travelled distance / speed
		PendingSounds.Add(Pending);
	}
	DeliverPendingSounds(); // listeners standing at the source hear it right away

	OnSoundEmitted.Broadcast(Event, LastBudget);
	return true;
}

// Tells listeners about sounds whose wave has arrived.
void ASoundGridManager::DeliverPendingSounds()
{
	if (PendingSounds.IsEmpty())
	{
		return;
	}
	const double Now = GetWorld()->GetTimeSeconds();
	for (int32 i = PendingSounds.Num() - 1; i >= 0; --i)
	{
		if (PendingSounds[i].ArrivalTime > Now)
		{
			continue;
		}
		const FPendingSound Pending = PendingSounds[i];
		PendingSounds.RemoveAtSwap(i);
		if (AActor* Listener = Pending.Listener.Get())
		{
			ICatrunSoundListener::Execute_OnSoundHeard(Listener, Pending.Event, Pending.RemainingBudget);
		}
	}
}

float ASoundGridManager::GetRemainingBudgetAt(const FVector& WorldLocation) const
{
	if (LastDistance.IsEmpty())
	{
		return -1.f;
	}
	const int32 Cell = Grid.FindNearestCell(WorldLocation, 1, [this](int32 C) { return Grid.IsWalkable(C); });
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
