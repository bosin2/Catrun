#include "SoundGridManager.h"

#include "../Catrun.h"
#include "CatrunDoor.h"
#include "CatrunSoundSettings.h"
#include "Components/BoxComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "CollisionQueryParams.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Engine/StaticMesh.h"
#include "DrawDebugHelpers.h"
#include "EngineUtils.h"
#include "Engine/World.h"

namespace
{
	// 0:E 1:W 2:S 3:N 4:SE 5:SW 6:NE 7:NW  (X = east, Y = south)
	constexpr int32 DirX[8] = { 1, -1, 0, 0, 1, -1, 1, -1 };
	constexpr int32 DirY[8] = { 0, 0, 1, -1, 1, 1, -1, -1 };
	constexpr int32 Opposite[8] = { 1, 0, 3, 2, 7, 6, 5, 4 };
	constexpr int32 DirE = 0, DirW = 1, DirS = 2, DirN = 3;

	struct FHeapNode
	{
		float Dist;
		int32 Cell;
		bool operator<(const FHeapNode& Other) const { return Dist < Other.Dist; }
	};
}

ASoundGridManager::ASoundGridManager()
{
	PrimaryActorTick.bCanEverTick = true;

	USceneComponent* Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	SetRootComponent(Root);
}

ASoundGridManager* ASoundGridManager::Get(const UObject* WorldContextObject)
{
	const UWorld* World = GEngine ? GEngine->GetWorldFromContextObject(WorldContextObject, EGetWorldErrorMode::ReturnNull) : nullptr;
	if (!World)
	{
		return nullptr;
	}
	for (TActorIterator<ASoundGridManager> It(World); It; ++It)
	{
		return *It;
	}
	return nullptr;
}

float ASoundGridManager::GetCellSize() const
{
	return BakedCellSize;
}

FVector ASoundGridManager::CellToWorld(int32 CellIndex) const
{
	const int32 X = CellIndex % GridWidth;
	const int32 Y = CellIndex / GridWidth;
	return FVector(GridOrigin.X + (X + 0.5f) * BakedCellSize, GridOrigin.Y + (Y + 0.5f) * BakedCellSize, FloorZ);
}

int32 ASoundGridManager::WorldToCell(const FVector& WorldLocation) const
{
	if (!HasGrid())
	{
		return INDEX_NONE;
	}
	const int32 X = FMath::FloorToInt((WorldLocation.X - GridOrigin.X) / BakedCellSize);
	const int32 Y = FMath::FloorToInt((WorldLocation.Y - GridOrigin.Y) / BakedCellSize);
	if (X < 0 || Y < 0 || X >= GridWidth || Y >= GridHeight)
	{
		return INDEX_NONE;
	}
	return Y * GridWidth + X;
}

bool ASoundGridManager::IsCellBlocked(int32 CellIndex) const
{
	return GateClosedCount.IsValidIndex(CellIndex) && GateClosedCount[CellIndex] > 0;
}

bool ASoundGridManager::IsEdgeOpen(int32 CellIndex, int32 Dir) const
{
	return EdgeMask.IsValidIndex(CellIndex) && (EdgeMask[CellIndex] & (1 << Dir)) != 0;
}

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
		UE_LOG(LogCatrunSound, Warning, TEXT("SoundGridManager has no baked grid. Building it now."));
		BuildGrid();
	}
	RefreshDoorGates();
	CreateVisual();
}

void ASoundGridManager::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (bDebugDrawGrid)
	{
		DebugDrawGrid();
	}
	UpdateVisual();
}

void ASoundGridManager::CreateVisual()
{
	if (!HasGrid() || !Settings || !Settings->VisualMaterial)
	{
		UE_LOG(LogCatrunSound, Warning, TEXT("Sound visual disabled: grid or VisualMaterial missing."));
		return;
	}
	UStaticMesh* Plane = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Plane.Plane"));
	if (!Plane)
	{
		return;
	}

	VisualISM = NewObject<UInstancedStaticMeshComponent>(this, TEXT("SoundVisual"));
	VisualISM->SetStaticMesh(Plane);
	VisualISM->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	VisualISM->SetCastShadow(false);
	VisualISM->NumCustomDataFloats = 1;
	VisualISM->SetupAttachment(GetRootComponent());
	VisualISM->RegisterComponent();

	VisualMID = UMaterialInstanceDynamic::Create(Settings->VisualMaterial, this);
	VisualMID->SetVectorParameterValue(TEXT("SoundColor"), Settings->SoundColor);
	VisualISM->SetMaterial(0, VisualMID);

	const float Scale = BakedCellSize / 100.f; // the engine plane is 100cm wide
	const int32 NumCells = GridWidth * GridHeight;
	CellToInstance.Init(INDEX_NONE, NumCells);
	for (int32 Cell = 0; Cell < NumCells; ++Cell)
	{
		if (!CellFlags[Cell])
		{
			continue;
		}
		const FVector Location = CellToWorld(Cell) + FVector(0.f, 0.f, Settings->VisualHeight);
		CellToInstance[Cell] = VisualISM->AddInstance(FTransform(FRotator::ZeroRotator, Location, FVector(Scale, Scale, 1.f)), /*bWorldSpace*/ true);
		VisualISM->SetCustomDataValue(CellToInstance[Cell], 0, 0.f, false);
	}
	VisualISM->MarkRenderStateDirty();
}

void ASoundGridManager::UpdateVisual()
{
	if (!VisualISM || !Settings || !LastField.IsValid())
	{
		return;
	}
	const double Elapsed = GetWorld()->GetTimeSeconds() - LastField.EmitTime;
	const float Expand = FMath::Max(LastField.Budget / FMath::Max(Settings->ExpandSpeed, 10.f), 0.01f);
	const float Total = Expand + Settings->HoldDuration + Settings->FadeDuration;

	if (Elapsed > Total)
	{
		if (bVisualActive)
		{
			for (const int32 Instance : CellToInstance)
			{
				if (Instance != INDEX_NONE)
				{
					VisualISM->SetCustomDataValue(Instance, 0, 0.f, false);
				}
			}
			VisualISM->MarkRenderStateDirty();
			bVisualActive = false;
		}
		return;
	}

	const float Radius = LastField.Budget * FMath::Clamp(static_cast<float>(Elapsed) / Expand, 0.f, 1.f);
	float Fade = 1.f;
	const float FadeStart = Expand + Settings->HoldDuration;
	if (Elapsed > FadeStart)
	{
		Fade = 1.f - FMath::Clamp(static_cast<float>(Elapsed - FadeStart) / FMath::Max(Settings->FadeDuration, 0.01f), 0.f, 1.f);
	}

	// The ring grows along the real propagation distance, so it bends around corners and
	// continues from doors exactly like the sound does.
	for (int32 Cell = 0; Cell < LastField.Dist.Num(); ++Cell)
	{
		const int32 Instance = CellToInstance.IsValidIndex(Cell) ? CellToInstance[Cell] : INDEX_NONE;
		if (Instance == INDEX_NONE)
		{
			continue;
		}
		const float Dist = LastField.Dist[Cell];
		float Alpha = 0.f;
		if (Dist != MAX_flt && Dist <= Radius)
		{
			const float Strength = FMath::Lerp(1.f, 1.f - Settings->EdgeFade, Dist / FMath::Max(LastField.Budget, 1.f));
			Alpha = Strength * Fade * Settings->SoundColor.A;
		}
		VisualISM->SetCustomDataValue(Instance, 0, Alpha, false);
	}
	VisualISM->MarkRenderStateDirty();
	bVisualActive = true;
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

	// 1) Collect the floors that define where cells exist.
	struct FFloorInfo
	{
		FBox Box;
		float Cost;
	};
	TArray<FFloorInfo> Floors;
	FBox All(ForceInit);
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* Actor = *It;
		if (!Actor->ActorHasTag(Settings->FloorTag))
		{
			continue;
		}
		FFloorInfo Info;
		Info.Box = Actor->GetComponentsBoundingBox(false);
		Info.Cost = Settings->DefaultFloorMultiplier;
		for (const TPair<FName, float>& Pair : Settings->FloorTagMultipliers)
		{
			if (Actor->ActorHasTag(Pair.Key))
			{
				Info.Cost = Pair.Value;
			}
		}
		Floors.Add(Info);
		All += Info.Box;
	}
	if (Floors.IsEmpty())
	{
		UE_LOG(LogCatrunSound, Error, TEXT("BuildGrid: no actor has the floor tag '%s'."), *Settings->FloorTag.ToString());
		return;
	}

	// 2) Allocate the grid.
	BakedCellSize = FMath::Max(Settings->CellSize, 5.f);
	FloorZ = All.Max.Z;
	GridOrigin = FVector(FMath::FloorToFloat(All.Min.X / BakedCellSize) * BakedCellSize,
		FMath::FloorToFloat(All.Min.Y / BakedCellSize) * BakedCellSize, FloorZ);
	GridWidth = FMath::CeilToInt((All.Max.X - GridOrigin.X) / BakedCellSize);
	GridHeight = FMath::CeilToInt((All.Max.Y - GridOrigin.Y) / BakedCellSize);
	const int32 NumCells = GridWidth * GridHeight;
	CellFlags.Init(0, NumCells);
	CellCost.Init(1.f, NumCells);
	EdgeMask.Init(0, NumCells);

	// 3) A cell exists where its centre lies on a floor.
	int32 NumWalkable = 0;
	for (int32 Y = 0; Y < GridHeight; ++Y)
	{
		for (int32 X = 0; X < GridWidth; ++X)
		{
			const FVector Center(GridOrigin.X + (X + 0.5f) * BakedCellSize, GridOrigin.Y + (Y + 0.5f) * BakedCellSize, FloorZ);
			for (const FFloorInfo& Floor : Floors)
			{
				if (Center.X >= Floor.Box.Min.X && Center.X <= Floor.Box.Max.X
					&& Center.Y >= Floor.Box.Min.Y && Center.Y <= Floor.Box.Max.Y)
				{
					const int32 Index = Y * GridWidth + X;
					CellFlags[Index] = 1;
					CellCost[Index] = Floor.Cost;
					++NumWalkable;
					break;
				}
			}
		}
	}

	// 4) Orthogonal edges: open when no wall stands between the two cell centres.
	//    Traces run at cat height so cat-holes (low openings) count as open.
	FCollisionQueryParams Params(SCENE_QUERY_STAT(SoundGridBake), /*bTraceComplex*/ true);
	const FCollisionObjectQueryParams ObjectParams(ECC_WorldStatic);
	const float TraceZ = FloorZ + Settings->TraceHeight;
	int32 NumBlockedEdges = 0;

	auto IsWalkable = [this](int32 X, int32 Y)
	{
		return X >= 0 && Y >= 0 && X < GridWidth && Y < GridHeight && CellFlags[Y * GridWidth + X] != 0;
	};
	auto SetEdge = [this](int32 Cell, int32 Dir, int32 OtherCell)
	{
		EdgeMask[Cell] |= (1 << Dir);
		EdgeMask[OtherCell] |= (1 << Opposite[Dir]);
	};

	for (int32 Y = 0; Y < GridHeight; ++Y)
	{
		for (int32 X = 0; X < GridWidth; ++X)
		{
			if (!IsWalkable(X, Y))
			{
				continue;
			}
			const int32 Cell = Y * GridWidth + X;
			const FVector From(GridOrigin.X + (X + 0.5f) * BakedCellSize, GridOrigin.Y + (Y + 0.5f) * BakedCellSize, TraceZ);

			for (const int32 Dir : { DirE, DirS })
			{
				const int32 NX = X + DirX[Dir];
				const int32 NY = Y + DirY[Dir];
				if (!IsWalkable(NX, NY))
				{
					continue;
				}
				const FVector To(GridOrigin.X + (NX + 0.5f) * BakedCellSize, GridOrigin.Y + (NY + 0.5f) * BakedCellSize, TraceZ);

				TArray<FHitResult> Hits;
				World->LineTraceMultiByObjectType(Hits, From, To, ObjectParams, Params);
				bool bWall = false;
				for (const FHitResult& Hit : Hits)
				{
					if (Hit.GetActor() && Hit.GetActor()->ActorHasTag(Settings->WallTag))
					{
						bWall = true;
						break;
					}
				}
				if (bWall)
				{
					++NumBlockedEdges;
				}
				else
				{
					SetEdge(Cell, Dir, NY * GridWidth + NX);
				}
			}
		}
	}

	// 5) Diagonal edges: open only when all four edges of the 2x2 block are open (no corner cutting).
	for (int32 Y = 0; Y < GridHeight - 1; ++Y)
	{
		for (int32 X = 0; X < GridWidth; ++X)
		{
			const int32 Cell = Y * GridWidth + X;
			if (!CellFlags[Cell])
			{
				continue;
			}
			// SE: (X,Y) -> (X+1,Y+1)
			if (X + 1 < GridWidth && CellFlags[Cell + GridWidth + 1])
			{
				const int32 East = Cell + 1;
				const int32 South = Cell + GridWidth;
				if (IsEdgeOpen(Cell, DirE) && IsEdgeOpen(Cell, DirS) && IsEdgeOpen(East, DirS) && IsEdgeOpen(South, DirE))
				{
					SetEdge(Cell, 4, Cell + GridWidth + 1);
				}
			}
			// SW: (X,Y) -> (X-1,Y+1)
			if (X - 1 >= 0 && CellFlags[Cell + GridWidth - 1])
			{
				const int32 West = Cell - 1;
				const int32 South = Cell + GridWidth;
				if (IsEdgeOpen(Cell, DirW) && IsEdgeOpen(Cell, DirS) && IsEdgeOpen(West, DirS) && IsEdgeOpen(South, DirW))
				{
					SetEdge(Cell, 5, Cell + GridWidth - 1);
				}
			}
		}
	}

	LastField = FSoundField();
	RefreshDoorGates();

	UE_LOG(LogCatrunSound, Log, TEXT("BuildGrid: %dx%d cells (cell %.0fcm), %d walkable, %d wall-blocked edges."),
		GridWidth, GridHeight, BakedCellSize, NumWalkable, NumBlockedEdges);
#if WITH_EDITOR
	Modify();
#endif
}

void ASoundGridManager::RefreshDoorGates()
{
	UWorld* World = GetWorld();
	if (!World || !HasGrid())
	{
		return;
	}
	GateClosedCount.Init(0, GridWidth * GridHeight);
	DoorCells.Reset();

	for (TActorIterator<ACatrunDoor> It(World); It; ++It)
	{
		ACatrunDoor* Door = *It;
		const FBox Box = Door->GetGateBox()->Bounds.GetBox();
		TArray<int32>& Cells = DoorCells.Add(Door);
		const int32 MinX = FMath::Max(0, FMath::FloorToInt((Box.Min.X - GridOrigin.X) / BakedCellSize));
		const int32 MaxX = FMath::Min(GridWidth - 1, FMath::FloorToInt((Box.Max.X - GridOrigin.X) / BakedCellSize));
		const int32 MinY = FMath::Max(0, FMath::FloorToInt((Box.Min.Y - GridOrigin.Y) / BakedCellSize));
		const int32 MaxY = FMath::Min(GridHeight - 1, FMath::FloorToInt((Box.Max.Y - GridOrigin.Y) / BakedCellSize));
		for (int32 Y = MinY; Y <= MaxY; ++Y)
		{
			for (int32 X = MinX; X <= MaxX; ++X)
			{
				const int32 Index = Y * GridWidth + X;
				const FVector Center = CellToWorld(Index);
				if (CellFlags[Index] && Center.X >= Box.Min.X && Center.X <= Box.Max.X && Center.Y >= Box.Min.Y && Center.Y <= Box.Max.Y)
				{
					Cells.Add(Index);
					if (!Door->IsOpen())
					{
						GateClosedCount[Index]++;
					}
				}
			}
		}
	}
}

void ASoundGridManager::NotifyDoorStateChanged(ACatrunDoor* Door)
{
	if (!Door || !HasGrid())
	{
		return;
	}
	const TArray<int32>* Cells = DoorCells.Find(Door);
	if (!Cells)
	{
		RefreshDoorGates();
		return;
	}
	// Recount so repeated notifications never drift.
	RefreshDoorGates();
}

int32 ASoundGridManager::FindNearestWalkableCell(const FVector& WorldLocation, int32 MaxRing) const
{
	if (!HasGrid())
	{
		return INDEX_NONE;
	}
	const int32 CX = FMath::FloorToInt((WorldLocation.X - GridOrigin.X) / BakedCellSize);
	const int32 CY = FMath::FloorToInt((WorldLocation.Y - GridOrigin.Y) / BakedCellSize);
	int32 Best = INDEX_NONE;
	float BestDistSq = TNumericLimits<float>::Max();
	for (int32 Ring = 0; Ring <= MaxRing; ++Ring)
	{
		for (int32 DY = -Ring; DY <= Ring; ++DY)
		{
			for (int32 DX = -Ring; DX <= Ring; ++DX)
			{
				if (FMath::Max(FMath::Abs(DX), FMath::Abs(DY)) != Ring)
				{
					continue;
				}
				const int32 X = CX + DX;
				const int32 Y = CY + DY;
				if (X < 0 || Y < 0 || X >= GridWidth || Y >= GridHeight)
				{
					continue;
				}
				const int32 Index = Y * GridWidth + X;
				if (!CellFlags[Index])
				{
					continue;
				}
				const float DistSq = FVector::DistSquared2D(CellToWorld(Index), WorldLocation);
				if (DistSq < BestDistSq)
				{
					BestDistSq = DistSq;
					Best = Index;
				}
			}
		}
		if (Best != INDEX_NONE)
		{
			break;
		}
	}
	return Best;
}

void ASoundGridManager::RunDijkstra(int32 SourceCell, float Budget, TArray<float>& OutDist) const
{
	const int32 NumCells = GridWidth * GridHeight;
	OutDist.Init(MAX_flt, NumCells);

	TArray<FHeapNode> Heap;
	OutDist[SourceCell] = 0.f;
	Heap.HeapPush(FHeapNode{ 0.f, SourceCell }, TLess<FHeapNode>());

	while (!Heap.IsEmpty())
	{
		FHeapNode Node;
		Heap.HeapPop(Node, TLess<FHeapNode>(), EAllowShrinking::No);
		if (Node.Dist > OutDist[Node.Cell])
		{
			continue; // stale entry
		}
		const int32 X = Node.Cell % GridWidth;
		const int32 Y = Node.Cell / GridWidth;

		for (int32 Dir = 0; Dir < NumDirs; ++Dir)
		{
			if (!IsEdgeOpen(Node.Cell, Dir))
			{
				continue;
			}
			const int32 Next = (Y + DirY[Dir]) * GridWidth + (X + DirX[Dir]);
			if (IsCellBlocked(Next))
			{
				continue;
			}
			const float StepLength = (DirX[Dir] != 0 && DirY[Dir] != 0) ? BakedCellSize * UE_SQRT_2 : BakedCellSize;
			const float StepCost = StepLength * 0.5f * (CellCost[Node.Cell] + CellCost[Next]);
			const float NewDist = Node.Dist + StepCost;
			if (NewDist <= Budget && NewDist < OutDist[Next])
			{
				OutDist[Next] = NewDist;
				Heap.HeapPush(FHeapNode{ NewDist, Next }, TLess<FHeapNode>());
			}
		}
	}
}

bool ASoundGridManager::EmitSound(const FCatrunSoundEvent& Event)
{
	UWorld* World = GetWorld();
	if (!World || !HasGrid() || !Settings)
	{
		return false;
	}
	const int32 SourceCell = FindNearestWalkableCell(Event.Location, 3);
	if (SourceCell == INDEX_NONE)
	{
		UE_LOG(LogCatrunSound, Warning, TEXT("EmitSound: no walkable cell near %s."), *Event.Location.ToString());
		return false;
	}

	const float Budget = Settings->GetBudget(Event.Size);
	RunDijkstra(SourceCell, Budget, LastField.Dist);
	LastField.Event = Event;
	LastField.Budget = Budget;
	LastField.SourceCell = SourceCell;
	LastField.EmitTime = World->GetTimeSeconds();

	int32 NumReached = 0;
	for (const float D : LastField.Dist)
	{
		NumReached += (D != MAX_flt) ? 1 : 0;
	}
	UE_LOG(LogCatrunSound, Log, TEXT("EmitSound: size=%d budget=%.0f reached %d cells."), static_cast<int32>(Event.Size), Budget, NumReached);

	// Tell every listener that this sound reaches.
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* Actor = *It;
		if (!Actor->Implements<UCatrunSoundListener>())
		{
			continue;
		}
		if (ICatrunSoundListener::Execute_GetListenerGroup(Actor) != Event.Target)
		{
			continue;
		}
		const float Remaining = GetRemainingBudgetAt(Actor->GetActorLocation());
		if (Remaining > 0.f)
		{
			ICatrunSoundListener::Execute_OnSoundHeard(Actor, Event, Remaining);
		}
	}

	OnSoundEmitted.Broadcast(Event, Budget);
	return true;
}

float ASoundGridManager::GetRemainingBudgetAt(const FVector& WorldLocation) const
{
	if (!LastField.IsValid())
	{
		return -1.f;
	}
	const int32 Cell = FindNearestWalkableCell(WorldLocation, 1);
	if (Cell == INDEX_NONE || !LastField.Dist.IsValidIndex(Cell) || LastField.Dist[Cell] == MAX_flt)
	{
		return -1.f;
	}
	return LastField.Budget - LastField.Dist[Cell];
}

void ASoundGridManager::DebugDrawGrid() const
{
#if ENABLE_DRAW_DEBUG
	UWorld* World = GetWorld();
	if (!World || !HasGrid())
	{
		return;
	}
	const float Z = FloorZ + 2.f;
	const float Half = BakedCellSize * 0.5f;
	for (int32 Index = 0; Index < GridWidth * GridHeight; ++Index)
	{
		if (!CellFlags[Index])
		{
			continue;
		}
		const FVector C = CellToWorld(Index) + FVector(0, 0, 2.f);
		DrawDebugPoint(World, C, 3.f, IsCellBlocked(Index) ? FColor::Red : FColor(60, 200, 60), false, -1.f);

		const int32 X = Index % GridWidth;
		const int32 Y = Index / GridWidth;
		// A wall edge = both cells exist but the edge between them is closed.
		if (X + 1 < GridWidth && CellFlags[Index + 1] && !IsEdgeOpen(Index, DirE))
		{
			DrawDebugLine(World, FVector(C.X + Half, C.Y - Half, Z), FVector(C.X + Half, C.Y + Half, Z), FColor::Red, false, -1.f, 0, 2.f);
		}
		if (Y + 1 < GridHeight && CellFlags[Index + GridWidth] && !IsEdgeOpen(Index, DirS))
		{
			DrawDebugLine(World, FVector(C.X - Half, C.Y + Half, Z), FVector(C.X + Half, C.Y + Half, Z), FColor::Red, false, -1.f, 0, 2.f);
		}
	}
#endif
}
