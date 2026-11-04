#include "CatrunPuzzleSuspension.h"
#include "Monster/CatrunArmor.h"
#include "Monster/CatrunCandle.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"

UCatrunPuzzleSuspension* UCatrunPuzzleSuspension::Get(const UObject* Context)
{
	UWorld* World = Context ? Context->GetWorld() : nullptr;
	return World ? World->GetSubsystem<UCatrunPuzzleSuspension>() : nullptr;
}
bool UCatrunPuzzleSuspension::IsSuspended(const UObject* Context)
{
	const auto* Guard = Get(Context);
	return Guard && Guard->bAcquired && Guard->RevealOwner.IsValid();
}
bool UCatrunPuzzleSuspension::ShouldCreateSubsystem(UObject* Outer) const
{
	const UWorld* World = Cast<UWorld>(Outer);
	return World && World->IsGameWorld();
}
bool UCatrunPuzzleSuspension::Acquire(UObject* Owner)
{
	if (!IsValid(Owner) || bAcquired) return false;
	RevealOwner = Owner;
	bAcquired = true;
	FreezeActors();
	return true;
}
void UCatrunPuzzleSuspension::FreezeActors()
{
	auto PauseMesh = [this](USkeletalMeshComponent* Mesh)
	{
		if (Mesh && !Mesh->bPauseAnims) { Mesh->bPauseAnims = true; Meshes.AddUnique(Mesh); }
	};
	for (TActorIterator<ACatrunArmor> It(GetWorld()); It; ++It)
	{
		auto* Move = It->GetCharacterMovement();
		if (Move && Move->IsComponentTickEnabled())
		{
			Move->SetComponentTickEnabled(false);
			Movements.AddUnique(Move);
		}
		PauseMesh(It->GetMesh());
	}
	for (TActorIterator<ACatrunCandle> It(GetWorld()); It; ++It) PauseMesh(It->Body);
}
void UCatrunPuzzleSuspension::Release(const UObject* Owner)
{
	if (bAcquired && RevealOwner.Get() == Owner) Restore();
}
void UCatrunPuzzleSuspension::Restore()
{
	bAcquired = false;
	RevealOwner.Reset();
	for (auto& Move : Movements) if (Move.IsValid()) Move->SetComponentTickEnabled(true);
	for (auto& Mesh : Meshes) if (Mesh.IsValid()) Mesh->bPauseAnims = false;
	Movements.Reset();
	Meshes.Reset();
}
void UCatrunPuzzleSuspension::Tick(float)
{
	if (!bAcquired) return;
	if (!RevealOwner.IsValid()) Restore();
	else FreezeActors(); // Includes enemies spawned during the reveal.
}
TStatId UCatrunPuzzleSuspension::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UCatrunPuzzleSuspension, STATGROUP_Tickables);
}
void UCatrunPuzzleSuspension::Deinitialize()
{
	Restore();
	Super::Deinitialize();
}
