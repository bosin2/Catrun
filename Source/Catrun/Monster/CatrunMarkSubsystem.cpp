#include "CatrunMarkSubsystem.h"

#include "Catrun.h"
#include "CatrunArmor.h"
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

void UCatrunMarkSubsystem::ApplyMark(APawn& Cat)
{
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
	APawn* Cat = CatrunCat::Find(this);
	if (!Cat)
	{
		return;
	}
	// The only way to lose the mark: hide.
	if (CatrunCat::IsHiding(Cat))
	{
		ClearMark(TEXT("the cat is in a hideout"));
		return;
	}
	UpdateVisual();

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
	const ASoundGridManager* Manager = ASoundGridManager::Get(this);
	const UCatrunSoundSettings* S = Manager ? Manager->GetSettings() : nullptr;
	if (!S)
	{
		return;
	}

	ACatrunArmor* Closest = nullptr;
	float ClosestDistance = TNumericLimits<float>::Max();
	for (TActorIterator<ACatrunArmor> It(GetWorld()); It; ++It)
	{
		const float Distance = FVector::Dist2D(It->GetActorLocation(), Cat.GetActorLocation());
		if (Distance < ClosestDistance)
		{
			Closest = *It;
			ClosestDistance = Distance;
		}
	}

	ACatrunArmor* Current = FollowingArmor.Get();
	if (Current)
	{
		const float CurrentDistance = FVector::Dist2D(Current->GetActorLocation(), Cat.GetActorLocation());
		if (Closest == Current || ClosestDistance >= CurrentDistance * S->MarkSwitchRatio)
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
}

void UCatrunMarkSubsystem::DestroyVisual()
{
	if (Light)
	{
		Light->DestroyComponent();
		Light = nullptr;
	}
	if (Orb)
	{
		Orb->DestroyComponent();
		Orb = nullptr;
	}
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
