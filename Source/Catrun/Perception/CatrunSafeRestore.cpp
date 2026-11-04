#include "CatrunSafeRestore.h"
#include "Catrun.h"
#include "Monster/CatrunRestartSubsystem.h"
#include "Components/CapsuleComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Engine/World.h"
#include "Engine/OverlapResult.h"
#include "GameFramework/Character.h"
#include "GameFramework/Pawn.h"

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

bool CatrunRestore::PlaceForCollision(APawn& Pawn, const FTransform& Desired, bool bRestoreCollision)
{
	Pawn.SetActorEnableCollision(false);
	auto Place = [&](const FTransform& Candidate)
	{
		if (bRestoreCollision && !IsPlacementClear(Pawn, Candidate)) return false;
		Pawn.SetActorTransform(Candidate, false, nullptr, ETeleportType::TeleportPhysics);
		// An overlap callback/teleport hook can change geometry or the pawn's transform.
		return !bRestoreCollision || IsPlacementClear(Pawn, Pawn.GetActorTransform());
	};
	if (Place(Desired)) return true;
	const auto* Character = Cast<ACharacter>(&Pawn);
	const auto* Capsule = Character ? Character->GetCapsuleComponent() : nullptr;
	if (Capsule && Pawn.GetWorld())
	{
		const float Radius = Capsule->GetScaledCapsuleRadius();
		const float HalfHeight = Capsule->GetScaledCapsuleHalfHeight();
		const auto Shape = Capsule->GetCollisionShape();
		const FCollisionResponseParams Responses(Capsule->GetCollisionResponseToChannels());
		FCollisionQueryParams Transit(SCENE_QUERY_STAT(CatrunRestoreTransit), false, &Pawn);
		TArray<FOverlapResult> OriginOverlaps;
		Pawn.GetWorld()->OverlapMultiByChannel(OriginOverlaps, Desired.GetLocation(), Desired.GetRotation(), ECC_Pawn, Shape, Transit, Responses);
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
					if (!Pawn.GetWorld()->LineTraceSingleByChannel(Floor, Location + FVector(0,0,20), Location-FVector(0,0,HalfHeight+22), ECC_Pawn, FloorParams, Responses)
						|| Floor.ImpactNormal.Z < .65f || Cast<APawn>(Floor.GetActor())) continue;
					Location.Z = Floor.ImpactPoint.Z + HalfHeight + 2.f;
					if (FMath::Abs(Location.Z - Desired.GetLocation().Z) > 20.f) continue;
					Candidate.SetLocation(Location);
					if (!IsPlacementClear(Pawn, Candidate)) continue;
					FHitResult Hit;
					if (Pawn.GetWorld()->SweepSingleByChannel(Hit, Desired.GetLocation(), Location, Desired.GetRotation(), ECC_Pawn, Shape, Transit, Responses)) continue;
					if (Place(Candidate)) return true;
				}
			}
		}
	}
	if (auto* Restart = UCatrunRestartSubsystem::Get(&Pawn)) Restart->ScheduleRecoveryRestart();
	UE_LOG(LogCatrunSound, Display, TEXT("%s has no clear capsule restoration position; requested clean stage recovery unless travel/teardown owns the world."), *Pawn.GetName());
	return false;
}
