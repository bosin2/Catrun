#include "CatrunSafeRestore.h"
#include "CatrunGroundSupport.h"
#include "Catrun.h"
#include "Monster/CatrunRestartSubsystem.h"
#include "Components/CapsuleComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Engine/World.h"
#include "Engine/OverlapResult.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/Controller.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerStart.h"
#include "TimerManager.h"

bool CatrunRestore::IsPlacementClear(const APawn& Pawn, const FTransform& Transform)
{
	const auto* Primitive = Cast<UPrimitiveComponent>(Pawn.GetRootComponent());
	if (!Primitive) return true;
	if (!Pawn.GetWorld()) return false;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(CatrunRestorePlacement), false, &Pawn);
	const FCollisionResponseParams Responses(Primitive->GetCollisionResponseToChannels());
	return !Pawn.GetWorld()->OverlapBlockingTestByChannel(Transform.GetLocation(), Transform.GetRotation(),
		Primitive->GetCollisionObjectType(), Primitive->GetCollisionShape(), Params, Responses);
}

bool CatrunRestore::TryPlaceOnSupport(APawn& Pawn, const FTransform& Reference)
{
	const auto* Character = Cast<ACharacter>(&Pawn);
	const auto* Capsule = Character ? Character->GetCapsuleComponent() : nullptr;
	if (!Capsule || !Reference.IsValid()) return false;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(CatrunRestoreSpawn), false, &Pawn);
	FHitResult Floor;
	FVector Center;
	if (!CatrunGround::FindSupport(*Capsule, Reference.GetLocation(), 40.f, 80.f, Params, Floor, Center)) return false;
	FTransform Supported = Reference;
	Supported.SetLocation(Center);
	if (!IsPlacementClear(Pawn, Supported)) return false;
	const FTransform Previous = Pawn.GetActorTransform();
	if (!Pawn.TeleportTo(Center, Supported.Rotator(), false, true)) return false;
	if (IsPlacementClear(Pawn, Pawn.GetActorTransform())) return true;
	Pawn.SetActorTransform(Previous, false, nullptr, ETeleportType::TeleportPhysics);
	return false;
}

namespace
{
bool TryPlaceForCollision(APawn& Pawn, const FTransform& Desired, bool bRestoreCollision)
{
	auto Place = [&](const FTransform& Candidate)
	{
		if (bRestoreCollision && !CatrunRestore::IsPlacementClear(Pawn, Candidate)) return false;
		Pawn.SetActorTransform(Candidate, false, nullptr, ETeleportType::TeleportPhysics);
		// An overlap callback/teleport hook can change geometry or the pawn's transform.
		return !bRestoreCollision || CatrunRestore::IsPlacementClear(Pawn, Pawn.GetActorTransform());
	};
	if (Place(Desired)) return true;
	const auto* Character = Cast<ACharacter>(&Pawn);
	const auto* Capsule = Character ? Character->GetCapsuleComponent() : nullptr;
	if (Capsule && Pawn.GetWorld())
	{
		const float Radius = Capsule->GetScaledCapsuleRadius();
		const float HalfHeight = Capsule->GetScaledCapsuleHalfHeight();
		const auto Shape = Capsule->GetCollisionShape();
		const ECollisionChannel Channel = Capsule->GetCollisionObjectType();
		const FCollisionResponseParams Responses(Capsule->GetCollisionResponseToChannels());
		FCollisionQueryParams Transit(SCENE_QUERY_STAT(CatrunRestoreTransit), false, &Pawn);
		TArray<FOverlapResult> OriginOverlaps;
		Pawn.GetWorld()->OverlapMultiByChannel(OriginOverlaps, Desired.GetLocation(), Desired.GetRotation(), Channel, Shape, Transit, Responses);
		bool bOriginContainsGeometry = false;
		for (const auto& Overlap : OriginOverlaps)
		{
			if (!Overlap.bBlockingHit) continue;
			// Step out of a Pawn that entered the original footprint, never through a wall/gate/furniture.
			if (const auto* OtherPawn = Cast<APawn>(Overlap.GetActor())) Transit.AddIgnoredActor(OtherPawn);
			else bOriginContainsGeometry = true;
		}
		if (!bOriginContainsGeometry)
		{
			FCollisionQueryParams FloorParams(SCENE_QUERY_STAT(CatrunRestoreFloor), false, &Pawn);
			const float Step = FMath::Max(20.f, Radius * 2.f + 4.f);
			FTransform Candidate = Desired;
			for (int32 Ring = 1; Ring <= 3 && Step*Ring <= 150.f; ++Ring)
			{
				for (int32 Direction = 0; Direction < 16; ++Direction)
				{
					const float Angle = Direction * UE_TWO_PI / 16.f;
					FVector Location = Desired.GetLocation() + FVector(FMath::Cos(Angle)*Step*Ring, FMath::Sin(Angle)*Step*Ring, 0);
					FHitResult Floor;
					FVector Supported;
					if (!CatrunGround::FindSupport(*Capsule, Location+FVector(0,0,HalfHeight), 20.f, HalfHeight+22.f, FloorParams, Floor, Supported)
						|| Floor.ImpactPoint.Z > Location.Z+20.f+.01f || Floor.ImpactPoint.Z < Location.Z-HalfHeight-22.f-.01f) continue;
					Location = Supported;
					if (FMath::Abs(Location.Z - Desired.GetLocation().Z) > 20.f) continue;
					Candidate.SetLocation(Location);
					if (!CatrunRestore::IsPlacementClear(Pawn, Candidate)) continue;
					FHitResult Hit;
					if (Pawn.GetWorld()->SweepSingleByChannel(Hit, Desired.GetLocation(), Location, Desired.GetRotation(), Channel, Shape, Transit, Responses)) continue;
					if (Place(Candidate)) return true;
				}
			}
		}
	}
	return false;
}

bool TryPlaceAtPlayerStart(APawn& Pawn)
{
	const auto* Controller = Pawn.GetController();
	const auto* StartSpot = Controller ? Controller->StartSpot.Get() : nullptr;
	if (IsValid(StartSpot) && StartSpot->GetWorld() == Pawn.GetWorld()
		&& CatrunRestore::TryPlaceOnSupport(Pawn, StartSpot->GetActorTransform())) return true;
	for (TActorIterator<APlayerStart> It(Pawn.GetWorld()); It; ++It)
		if (*It != StartSpot && CatrunRestore::TryPlaceOnSupport(Pawn, It->GetActorTransform())) return true;
	return false;
}
}

bool CatrunRestore::PlaceForCollision(APawn& Pawn, const FTransform& Desired, bool bRestoreCollision,
	EMovementMode RestoreMode, uint8 RestoreCustomMode)
{
	Pawn.SetActorEnableCollision(false);
	if (TryPlaceForCollision(Pawn, Desired, bRestoreCollision)) return true;
	UWorld* World = Pawn.GetWorld();
	if (!World || World->bIsTearingDown) return false;
	const auto* Character = Cast<ACharacter>(&Pawn);
	const auto* Movement = Character ? Character->GetCharacterMovement() : nullptr;
	if (RestoreMode == MOVE_MAX && Movement && Movement->MovementMode != MOVE_None)
	{
		RestoreMode = Movement->MovementMode;
		RestoreCustomMode = Movement->CustomMovementMode;
	}
	const TWeakObjectPtr<APawn> WeakPawn(&Pawn);
	const TWeakObjectPtr<AController> Controller(Pawn.GetController());
	auto RestoreAfterFailure = [WeakPawn, Controller, Desired, RestoreMode, RestoreCustomMode]()
	{
		auto* Cat = WeakPawn.Get();
		if (!Cat || !Cat->GetWorld() || Cat->GetWorld()->bIsTearingDown || Cat->GetActorEnableCollision()
			|| Cat->GetController() != Controller.Get()) return;
		if (!TryPlaceForCollision(*Cat, Desired, true) && !TryPlaceAtPlayerStart(*Cat))
		{
			if (auto* Restart = UCatrunRestartSubsystem::Get(Cat)) Restart->ReportBlockedPawnRecovery(*Cat);
			return;
		}
		Cat->SetActorEnableCollision(true);
		if (auto* CatCharacter = Cast<ACharacter>(Cat))
		{
			auto* CatMovement = CatCharacter->GetCharacterMovement();
			CatMovement->StopMovementImmediately();
			if (RestoreMode == MOVE_MAX) CatMovement->SetDefaultMovementMode();
			else CatMovement->SetMovementMode(RestoreMode, RestoreCustomMode);
		}
	};
	auto* Restart = UCatrunRestartSubsystem::Get(&Pawn);
	if (!Restart || !Restart->ScheduleRecoveryRestart(.5f, RestoreAfterFailure))
		World->GetTimerManager().SetTimerForNextTick(FTimerDelegate::CreateWeakLambda(&Pawn, MoveTemp(RestoreAfterFailure)));
	UE_LOG(LogCatrunSound, Display, TEXT("%s has no clear local restoration position; queued stage recovery."), *Pawn.GetName());
	return false;
}
