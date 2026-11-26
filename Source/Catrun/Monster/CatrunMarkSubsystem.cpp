#include "CatrunMarkSubsystem.h"
#include "Interaction/CatrunPuzzleSuspension.h"

#include "Catrun.h"
#include "CatrunArmor.h"
#include "CatrunCandle.h"
#include "CatrunRestartSubsystem.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "LevelFlow/CatrunElevatorTransition.h"
#include "Interaction/CatrunBasketInteractionComponent.h"
#include "Perception/CatrunCatQueries.h"
#include "Sound/CatrunSoundSettings.h"
#include "Sound/SoundGridManager.h"
#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "GameFramework/Pawn.h"

UCatrunMarkSubsystem* UCatrunMarkSubsystem::Get(const UObject* WorldContextObject)
{
	const UWorld* World = GEngine ? GEngine->GetWorldFromContextObject(WorldContextObject, EGetWorldErrorMode::ReturnNull) : nullptr;
	return World ? World->GetSubsystem<UCatrunMarkSubsystem>() : nullptr;
}

bool UCatrunMarkSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	const UWorld* World = Cast<UWorld>(Outer);
	return World && World->IsGameWorld();
}

TStatId UCatrunMarkSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UCatrunMarkSubsystem, STATGROUP_Tickables);
}

void UCatrunMarkSubsystem::ObserveCorridor(ACatrunStageExit& Exit, APawn& Cat)
{
    if (!Exit.bProtectStage1Corridor || !Exit.bUseExitTransition || !Exit.ActorHasTag(TEXT("CatrunAuthoredStage1Exit"))) return;
    if (Corridor.IsValid() && Corridor.Get() != &Exit) return;
    if (CorridorCandidate.Get() != &Cat) bCorridorAdmitted = false;
    Corridor = &Exit;
    CorridorCandidate = &Cat;
    RefreshCorridor();
}

void UCatrunMarkSubsystem::LeaveCorridor(const ACatrunStageExit& Exit)
{
    if (Corridor.Get(true) != &Exit) return;
    Corridor.Reset();
    CorridorCandidate.Reset();
    bCorridorAdmitted = false;
}

void UCatrunMarkSubsystem::RefreshCorridor()
{
    RefreshElevatorCorridor();
    ACatrunStageExit* Exit = Corridor.Get();
    APawn* Cat = CorridorCandidate.Get();
    if (!IsValid(Exit) || Exit->IsActorBeingDestroyed() || !IsValid(Cat) || Cat->IsActorBeingDestroyed()
        || GetWorld()->bIsTearingDown || !Cat->IsLocallyControlled() || CatrunCat::Find(this) != Cat
        || !Exit->IsInsideCorridor(*Cat))
    {
        bCorridorAdmitted = false;
        return;
    }
    if (bCorridorAdmitted) return;
    const auto* Restart = UCatrunRestartSubsystem::Get(this);
    const auto* Actions = Cat->FindComponentByClass<UCatrunBasketInteractionComponent>();
    if ((Restart && Restart->IsCatching()) || (Actions && (Actions->Busy || Actions->IsHidden))
        || UCatrunPuzzleSuspension::IsSuspended(this)) return;
    // Set before clearing. Detection and path callbacks may synchronously query admission again.
    bCorridorAdmitted = true;
    ForgetCorridorCat(*Cat, TEXT("Stage1 corridor entry"));
}

void UCatrunMarkSubsystem::ObserveElevatorCorridor(ACatrunElevatorTransition& Elevator)
{
    if (Elevator.GetWorld() != GetWorld() || Elevator.bArrivalSide || ElevatorCorridor.IsValid()) return;
    ElevatorCorridor = &Elevator;
    RefreshElevatorCorridor();
}

void UCatrunMarkSubsystem::LeaveElevatorCorridor(const ACatrunElevatorTransition& Elevator)
{
    if (ElevatorCorridor.Get(true) != &Elevator) return;
    ElevatorCorridor.Reset();
    ElevatorAdmittedCat.Reset();
}

void UCatrunMarkSubsystem::RefreshElevatorCorridor()
{
    const auto* Elevator = ElevatorCorridor.Get();
    if (!Elevator) return;
    APawn* Cat = CatrunCat::Find(this);
    if (!IsValid(Cat) || Cat->IsActorBeingDestroyed() || GetWorld()->bIsTearingDown || !Cat->IsLocallyControlled()
        || !Elevator->IsInsideCorridor(*Cat))
    {
        ElevatorAdmittedCat.Reset();
        return;
    }
    if (ElevatorAdmittedCat.Get() == Cat) return;
    const auto* Restart = UCatrunRestartSubsystem::Get(this);
    const auto* Actions = Cat->FindComponentByClass<UCatrunBasketInteractionComponent>();
    if ((Restart && Restart->IsCatching()) || (Actions && (Actions->Busy || Actions->IsHidden))
        || UCatrunPuzzleSuspension::IsSuspended(this)) return;
    ElevatorAdmittedCat = Cat;
    ForgetCorridorCat(*Cat, TEXT("Stage2 elevator corridor entry"));
}

void UCatrunMarkSubsystem::ForgetCorridorCat(APawn& Cat, const TCHAR* Reason)
{
    for (TActorIterator<ACatrunArmor> It(GetWorld()); It; ++It) It->ForgetCorridorCat(Cat);
    for (TActorIterator<ACatrunCandle> It(GetWorld()); It; ++It) It->ForgetCorridorCat();
    ClearMark(Reason);
}

bool UCatrunMarkSubsystem::IsExcludedFromPerception(const AActor* Subject)
{
    if (!Subject) return false;
    auto* Marks = Get(Subject);
    if (!Marks || (!Marks->ElevatorCorridor.IsValid() && Marks->CorridorCandidate.Get() != Subject)) return false;
    // Recheck the current center even if perception runs before the exit actor's tick.
    Marks->RefreshCorridor();
    return Marks->ElevatorAdmittedCat.Get() == Subject || (Marks->CorridorCandidate.Get() == Subject && Marks->bCorridorAdmitted);
}

void UCatrunMarkSubsystem::ApplyMark(APawn& Cat)
{
	if (IsExcludedFromPerception(&Cat) || UCatrunPuzzleSuspension::IsSuspended(this)) return;
	if (bMarked)
	{
		return;
	}
	bMarked = true;
	FollowTimer = 0.f;
	CreateVisual(Cat);
	UE_LOG(LogCatrunSound, Log, TEXT("The cat is marked."));
}

void UCatrunMarkSubsystem::ClearMark(const TCHAR* Reason)
{
	if (!bMarked)
	{
		return;
	}
	bMarked = false;
	FollowTimer = 0.f;
	if (ACatrunArmor* Armor = FollowingArmor.Get())
	{
		Armor->SetFollowingMark(false); // it goes on to where it last saw the cat, looks, and returns
	}
	FollowingArmor.Reset();
	DestroyVisual();
	UE_LOG(LogCatrunSound, Log, TEXT("The mark is gone (%s)."), Reason);
}

void UCatrunMarkSubsystem::Tick(float DeltaTime)
{
	if (UCatrunPuzzleSuspension::IsSuspended(this)) return;
	APawn* Cat = CatrunCat::Find(this);
	if (!Cat || IsExcludedFromPerception(Cat))
	{
		return;
	}
	// Hideout entry counts from the first moment of the get-in animation.
	if (CatrunCat::IsSafeFromCatch(Cat))
	{
		ClearMark(TEXT("the cat is in a hideout"));
		return;
	}
	UpdateVisual();
	ApplyVisualVisibility(); // an owner destroyed without releasing must not hide the orb forever

	FollowTimer -= DeltaTime;
	if (FollowTimer <= 0.f)
	{
		FollowTimer = 0.25f;
		UpdateFollowingArmor(*Cat);
	}
}

// Only the closest armor follows. To keep the choice from flipping back and forth, another armor
// takes over only when it is clearly closer (MarkSwitchRatio).
void UCatrunMarkSubsystem::UpdateFollowingArmor(const APawn& Cat)
{
	if (UCatrunPuzzleSuspension::IsSuspended(this)) return;
	const ASoundGridManager* Manager = ASoundGridManager::Get(this);
	const UCatrunSoundSettings* S = Manager ? Manager->GetSettings() : nullptr;
	if (!S)
	{
		return;
	}
	// A level may explicitly disable mark pursuit for a separate demonstration.
	if (!Manager->bMarkAttractsArmors)
	{
		return;
	}

	ACatrunArmor* Closest = nullptr;
	float ClosestDistance = TNumericLimits<float>::Max();
	for (TActorIterator<ACatrunArmor> It(GetWorld()); It; ++It)
	{
		const float Distance = FVector::Dist2D(It->GetActorLocation(), Cat.GetActorLocation());
		if (Distance <= S->MarkCallRadius && Distance < ClosestDistance)
		{
			Closest = *It;
			ClosestDistance = Distance;
		}
	}

	ACatrunArmor* Current = FollowingArmor.Get();
	if (Current)
	{
		const float CurrentDistance = FVector::Dist2D(Current->GetActorLocation(), Cat.GetActorLocation());
		if (CurrentDistance <= S->MarkCallRadius &&
			(Closest == Current || (Closest && ClosestDistance >= CurrentDistance * S->MarkSwitchRatio)))
		{
			return; // keep the one that is following
		}
		Current->SetFollowingMark(false);
	}
	FollowingArmor = Closest;
	if (Closest)
	{
		Closest->SetFollowingMark(true);
	}
}

void UCatrunMarkSubsystem::CreateVisual(APawn& Cat)
{
	const ASoundGridManager* Manager = ASoundGridManager::Get(this);
	const UCatrunSoundSettings* S = Manager ? Manager->GetSettings() : nullptr;
	if (!S || !Cat.GetRootComponent())
	{
		return;
	}
	OrbHeight = S->MarkHeight;

	Orb = NewObject<UStaticMeshComponent>(&Cat, TEXT("CatrunMarkOrb"));
	Orb->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Sphere.Sphere")));
	if (S->MarkMaterial)
	{
		Orb->SetMaterial(0, S->MarkMaterial);
	}
	Orb->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Orb->SetCastShadow(false);
	Orb->SetupAttachment(Cat.GetRootComponent());
	Orb->RegisterComponent();
	Orb->SetWorldScale3D(FVector(S->MarkOrbScale));
	Orb->SetRelativeLocation(FVector(0.f, 0.f, OrbHeight));

	Light = NewObject<UPointLightComponent>(&Cat, TEXT("CatrunMarkLight"));
	Light->SetLightColor(S->MarkLightColor);
	Light->SetIntensity(S->MarkLightIntensity);
	Light->SetAttenuationRadius(S->MarkLightRadius);
	Light->SetCastShadows(false);
	Light->SetupAttachment(Orb);
	Light->RegisterComponent();
	ApplyVisualVisibility();
}

void UCatrunMarkSubsystem::SetVisualSuppressed(const UObject* Owner, bool bSuppressed)
{
	if (!Owner) return;
	if (bSuppressed) VisualSuppressors.AddUnique(Owner);
	else VisualSuppressors.Remove(Owner);
	ApplyVisualVisibility();
}

bool UCatrunMarkSubsystem::IsVisualSuppressed() const
{
	return VisualSuppressors.ContainsByPredicate([](const TWeakObjectPtr<const UObject>& Owner) { return Owner.IsValid(); });
}

bool UCatrunMarkSubsystem::IsVisualShown() const
{
	return Orb && Orb->IsVisible() && Light && Light->IsVisible();
}

void UCatrunMarkSubsystem::ApplyVisualVisibility()
{
	VisualSuppressors.RemoveAll([](const TWeakObjectPtr<const UObject>& Owner) { return !Owner.IsValid(); });
	if (Orb) Orb->SetVisibility(VisualSuppressors.IsEmpty(), true); // propagates to the attached light
}

void UCatrunMarkSubsystem::DestroyVisual()
{
	// Free the fixed names so a mark re-applied before GC never reconstructs over a pending-kill component.
	constexpr ERenameFlags RenameFlags = REN_DontCreateRedirectors | REN_DoNotDirty | REN_NonTransactional;
	if (IsValid(Light))
	{
		Light->DestroyComponent();
		Light->Rename(nullptr, nullptr, RenameFlags);
	}
	Light = nullptr;
	if (IsValid(Orb))
	{
		Orb->DestroyComponent();
		Orb->Rename(nullptr, nullptr, RenameFlags);
	}
	Orb = nullptr;
}

// The orb floats up and down a little and turns, so it reads as magic.
void UCatrunMarkSubsystem::UpdateVisual()
{
	if (!Orb)
	{
		return;
	}
	const float Time = GetWorld()->GetTimeSeconds();
	Orb->SetRelativeLocation(FVector(0.f, 0.f, OrbHeight + FMath::Sin(Time * 3.f) * 4.f));
}
