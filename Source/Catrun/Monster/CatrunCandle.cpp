#include "CatrunCandle.h"
#include "Interaction/CatrunPuzzleSuspension.h"
#include "CatrunPerceptionPolicy.h"
#include "Components/CapsuleComponent.h"
#include "Engine/World.h"

#include "Catrun.h"
#include "CatrunMarkSubsystem.h"
#include "Perception/AlertMarkComponent.h"
#include "Perception/CatrunCatQueries.h"
#include "Perception/VisionFanComponent.h"
#include "Sound/CatrunSoundSettings.h"
#include "Sound/SoundGridManager.h"
#include "Animation/AnimationAsset.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/Pawn.h"
#include "EngineUtils.h"
#include "CatrunArmor.h"
#include "Interaction/CatrunStatuePuzzle.h"

ACatrunCandle::ACatrunCandle()
{
	PrimaryActorTick.bCanEverTick = true;

	SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));

	BlockingCapsule = CreateDefaultSubobject<UCapsuleComponent>(TEXT("BlockingCapsule"));
	BlockingCapsule->SetupAttachment(GetRootComponent());
	BlockingCapsule->InitCapsuleSize(22.f, 60.f);
	BlockingCapsule->SetRelativeLocation(FVector(0, 0, 60));
	BlockingCapsule->SetCollisionProfileName(TEXT("Pawn"));
	BlockingCapsule->SetCollisionResponseToChannel(ECC_Pawn, ECR_Block);

	Body = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("Body"));
	Body->SetupAttachment(GetRootComponent());
	Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Body->SetAnimationMode(EAnimationMode::AnimationSingleNode);

	Sight = CreateDefaultSubobject<UCatrunVisionFanComponent>(TEXT("Sight"));

	AlertMark = CreateDefaultSubobject<UCatrunAlertMarkComponent>(TEXT("AlertMark"));
	AlertMark->SetupAttachment(GetRootComponent());
	AlertMark->SetRelativeLocation(FVector(0.f, 0.f, 200.f));
}

const UCatrunSoundSettings* ACatrunCandle::GetSettings()
{
	if (!CachedManager.IsValid())
	{
		CachedManager = ASoundGridManager::Get(this);
	}
	return CachedManager.IsValid() ? CachedManager->GetSettings() : nullptr;
}

// Distance behind the candle where the cone's point sits: there the cone is as wide as the body.
float ACatrunCandle::GetConeBackOffset(const UCatrunSoundSettings& S) const
{
	const float HalfAngleTan = FMath::Tan(FMath::DegreesToRadians(FMath::Clamp(S.CandleConeAngle * 0.5f, 1.f, 89.f)));
	return S.CandleBodyWidth * 0.5f / HalfAngleTan;
}

void ACatrunCandle::BeginPlay()
{
	Super::BeginPlay();
	ResetPatrol();
	PlayAnimation(IdleAnim, true);
	// The sight is set up in Tick, as soon as the level's sound system is ready.
}

void ACatrunCandle::PlayAnimation(UAnimationAsset* Anim, bool bLoop)
{
	if (Anim && Body)
	{
		Body->PlayAnimation(Anim, bLoop);
	}
}

// The body is turned so that the eyes (not some arbitrary side of the mesh) look along the cone.
// We turn the body to yaw 0, see where the eye bones are compared to the body bone, and remember
// the turn that brings that direction onto the cone.
void ACatrunCandle::AlignBodyToEyes()
{
	const FName EyeLeft(TEXT("eye_l"));
	const FName EyeRight(TEXT("eye_r"));
	const FName Core(TEXT("body"));
	if (Body->GetBoneIndex(EyeLeft) == INDEX_NONE || Body->GetBoneIndex(EyeRight) == INDEX_NONE)
	{
		UE_LOG(LogCatrunSound, Warning, TEXT("%s: no eye bones found, body is not aligned automatically."), *GetName());
		return;
	}

	Body->SetWorldRotation(FRotator::ZeroRotator);
	Body->TickAnimation(0.f, false);
	Body->RefreshBoneTransforms();

	const FVector EyeMiddle = (Body->GetBoneLocation(EyeLeft, EBoneSpaces::WorldSpace) + Body->GetBoneLocation(EyeRight, EBoneSpaces::WorldSpace)) * 0.5f;
	const FVector Center = (Body->GetBoneIndex(Core) != INDEX_NONE) ? Body->GetBoneLocation(Core, EBoneSpaces::WorldSpace) : Body->GetComponentLocation();
	FVector Front = EyeMiddle - Center;
	Front.Z = 0.f;
	if (Front.Size() < 1.f)
	{
		UE_LOG(LogCatrunSound, Warning, TEXT("%s: the eyes are in the middle of the body, cannot tell the front. Use BodyYawOffset."), *GetName());
		return;
	}
	AutoBodyYaw = -Front.Rotation().Yaw;
	UE_LOG(LogCatrunSound, Log, TEXT("%s: eyes look toward yaw %.0f with the body unturned, body turn set to %.0f."), *GetName(), Front.Rotation().Yaw, AutoBodyYaw);
}

float ACatrunCandle::GetSweepHalfAngle(const UCatrunSoundSettings& S) const
{
    return SweepHalfAngleOverride >= 0.f ? FMath::Clamp(SweepHalfAngleOverride, 0.f, 180.f)
        : FMath::Max(0.f, (S.CandleTotalAngle - S.CandleConeAngle) * 0.5f);
}

void ACatrunCandle::ForgetCorridorCat()
{
    if (bTracking)
        if (const UCatrunSoundSettings* Settings = GetSettings()) StopTracking(*Settings);
    bCatInView = false;
    if (ReactTimeLeft > 0.f) PlayAnimation(IdleAnim, true);
    ReactTimeLeft = 0.f;
    AlertMark->SetVisibility(false);
    bTracking = false;
}

void ACatrunCandle::UpdateSweep(float DeltaSeconds, const UCatrunSoundSettings& S)
{
	// The cone stays inside the total range, so its middle can move this far from the candle's direction.
	const float MaxOffset = GetSweepHalfAngle(S);

	if (PauseLeft > 0.f)
	{
		PauseLeft -= DeltaSeconds;
		return;
	}
	SweepOffset += SweepDirection * S.CandleSweepSpeed * DeltaSeconds;
	if (FMath::Abs(SweepOffset) >= MaxOffset)
	{
		SweepOffset = FMath::Clamp(SweepOffset, -MaxOffset, MaxOffset);
		SweepDirection = -SweepDirection;
		PauseLeft = S.CandleSweepEndPause; // wait a moment at the end, then turn back
	}
}

void ACatrunCandle::TrackCat(float DeltaSeconds, const APawn& Cat, const UCatrunSoundSettings& S)
{
	const float MaxOffset = GetSweepHalfAngle(S);

	// Direction of the cat as an angle away from the candle's own direction.
	const FVector ToCat = Cat.GetActorLocation() - GetActorLocation();
	const float CatAngle = FMath::RadiansToDegrees(FMath::Atan2(ToCat.Y, ToCat.X));
	const float WantedOffset = FMath::Clamp(FMath::FindDeltaAngleDegrees(GetActorRotation().Yaw, CatAngle), -MaxOffset, MaxOffset);

	const float OldOffset = SweepOffset;
    if (SweepHalfAngleOverride >= 0.f)
        SweepOffset = FMath::FInterpConstantTo(SweepOffset, WantedOffset, DeltaSeconds, S.CandleTrackSpeed);
    else
        SweepOffset = FMath::FixedTurn(SweepOffset, WantedOffset, S.CandleTrackSpeed * DeltaSeconds);
	PauseLeft = 0.f;
	if (!FMath::IsNearlyEqual(OldOffset, SweepOffset))
	{
		LastTurnDirection = FMath::Sign(SweepOffset - OldOffset);
	}
}

void ACatrunCandle::StartTracking(APawn& Cat, const UCatrunSoundSettings& S)
{
	if (UCatrunPuzzleSuspension::IsSuspended(this) || UCatrunMarkSubsystem::IsExcludedFromPerception(&Cat)) return;
	bTracking = true;
	LoseSightTimer = 0.f;
	LastTurnDirection = 0.f;
	UE_LOG(LogCatrunSound, Log, TEXT("%s spotted the cat."), *GetName());

	Sight->SetColor(S.CandleAlertSightColor); // orange -> red
	AlertMark->Show(S.AlertDuration);
	if (SpotReactAnim)
	{
		PlayAnimation(SpotReactAnim, false);
		ReactTimeLeft = SpotReactAnim->GetPlayLength();
	}
	OnCatSpotted.Broadcast(this, &Cat);
}

void ACatrunCandle::StopTracking(const UCatrunSoundSettings& S)
{
	bTracking = false;
	LoseSightTimer = 0.f;
	UE_LOG(LogCatrunSound, Log, TEXT("%s lost the cat and goes back to patrol."), *GetName());
	Sight->SetColor(S.CandleSightColor); // red -> orange

	// The search starts from where the cone last saw the cat (SweepOffset is kept as it is), and
	// goes on the way the cat was last heading.
	if (LastTurnDirection != 0.f)
	{
		SweepDirection = LastTurnDirection;
		PauseLeft = 0.f;
	}
}

void ACatrunCandle::CheckForCat(float DeltaSeconds, APawn* Cat, const UCatrunSoundSettings& S)
{
	if (UCatrunPuzzleSuspension::IsSuspended(this)) return;
	// Touching the candle counts like being seen: it reacts, looks toward the cat as far as it can,
	// and marks it, but proximity never bypasses a wall.
	const bool bCatVisible = Cat && !CatrunCat::IsSafeFromCatch(Cat);
	const bool bTouching = bCatVisible && FVector::Dist2D(Cat->GetActorLocation(), GetActorLocation()) <= S.CandleTouchRadius;
	const bool bSees = bCatVisible && (bTouching || Sight->CanSee(Cat->GetActorLocation(), S.CatSightRadius))
		&& CatrunPerception::HasDirectSight(*this, *Cat, S.VisionTraceHeight);
	bCatInView = bSees;

	if (bSees)
	{
		LoseSightTimer = 0.f;
		// Tracking has a grace period; a cleared mark must not grant immunity when
		// the cat reappears before that period expires. ApplyMark is idempotent.
		if (bPenaltiesEnabled)
		{
			if (UCatrunMarkSubsystem* Marks = UCatrunMarkSubsystem::Get(this))
				Marks->ApplyMark(*Cat);
		}
		if (!bTracking)
		{
			StartTracking(*Cat, S); // seeing the cat is enough: spotted at once
		}
	}
	else if (bTracking)
	{
		// Out of the cone: give up after a short delay (so the edge of the cone does not flicker).
		LoseSightTimer += DeltaSeconds;
		if (LoseSightTimer >= S.CandleLoseSightDelay)
		{
			StopTracking(S);
		}
	}
}

void ACatrunCandle::Tick(float DeltaSeconds)
{
	if (UCatrunPuzzleSuspension::IsSuspended(this)) return;
	Super::Tick(DeltaSeconds);

	const UCatrunSoundSettings* S = GetSettings();
	if (!S)
	{
		UpdatePatrol(DeltaSeconds);
		return;
	}
	if (!bSightConfigured)
	{
		// The sight numbers come from the settings asset of the level (read once).
		// The cone's point sits behind the body, so the range is extended to keep CandleRange in front of it.
		Sight->Configure(S->CandleRange + GetConeBackOffset(*S), S->CandleRayCount, S->CandleSightColor);
		Sight->SetDisplayVisible(bShowSightDisplay);
		bSightConfigured = true;
	}
	if (!bEyesAligned)
	{
		if (bAutoAlignEyes)
		{
			AlignBodyToEyes();
		}
		bEyesAligned = true;
	}

	// Move the cone: follow the cat only while the cone really sees it. When the cat has left the
	// view the cone stays where it last saw the cat (the candle does not know where it went) until
	// the candle gives up; then the sweep starts again from that place.
	APawn* Cat = CatrunCat::Find(this);
	if (UCatrunMarkSubsystem::IsExcludedFromPerception(Cat)) Cat = nullptr;
	if (bTracking)
	{
		if (Cat && bCatInView)
		{
			TrackCat(DeltaSeconds, *Cat, *S);
		}
	}
	else if (HasPatrolRoute())
	{
		// Walking a route: look straight ahead, no back-and-forth sweep. After tracking, the cone
		// comes back to the middle.
		SweepOffset = FMath::FInterpConstantTo(SweepOffset, 0.f, DeltaSeconds, FMath::Max(1.f, S->CandleTrackSpeed));
		PauseLeft = 0.f;
	}
	else
	{
		UpdateSweep(DeltaSeconds, *S);
	}

	// The cone and the body (eyes) turn together.
	float ConeCenter = GetActorRotation().Yaw + SweepOffset;
	// The cone's point sits behind the body and the part of the cone behind the body is cut off, so
	// the view starts at the body (and a wall behind the candle does not matter).
	const float ConeCenterRad = FMath::DegreesToRadians(ConeCenter);
	FVector Forward(FMath::Cos(ConeCenterRad), FMath::Sin(ConeCenterRad), 0.f);
	const float BackOffset = GetConeBackOffset(*S);
	Sight->SetNearClip(BackOffset);
	Sight->SetOriginOverride(GetActorLocation() - Forward * BackOffset);
	// Sight only: the floor display is drawn once, after the patrol step below.
	Sight->Update(ConeCenter, S->CandleConeAngle * 0.5f, false);
	Body->SetWorldRotation(FRotator(0.f, ConeCenter + AutoBodyYaw + BodyYawOffset, 0.f));

	CheckForCat(DeltaSeconds, Cat, *S);
	// Check visibility before moving: a newly spotted cat freezes this very step.
	const FVector BeforePatrol = GetActorLocation();
	const float YawBeforePatrol = GetActorRotation().Yaw;
	UpdatePatrol(DeltaSeconds);
	const bool bTurned = !FMath::IsNearlyEqual(YawBeforePatrol, GetActorRotation().Yaw);
	if (bTurned)
	{
		ConeCenter = GetActorRotation().Yaw + SweepOffset;
		Forward = FVector(FMath::Cos(FMath::DegreesToRadians(ConeCenter)), FMath::Sin(FMath::DegreesToRadians(ConeCenter)), 0.f);
		Body->SetWorldRotation(FRotator(0.f, ConeCenter + AutoBodyYaw + BodyYawOffset, 0.f));
	}
	if (bTurned || !BeforePatrol.Equals(GetActorLocation()))
	{
		Sight->SetOriginOverride(GetActorLocation() - Forward * BackOffset);
		Sight->Update(ConeCenter, S->CandleConeAngle * 0.5f);
	}
	else
	{
		Sight->WriteDisplay();
	}

	// While the candle is tracking the cat the "!" stays on. (Show keeps it visible for a short
	// time, so renewing it every frame holds it until tracking stops.)
	if (bTracking)
	{
		AlertMark->Show(0.2f);
	}

	// Go back to the idle animation when the reaction has finished.
	if (ReactTimeLeft > 0.f)
	{
		ReactTimeLeft -= DeltaSeconds;
		if (ReactTimeLeft <= 0.f)
		{
			PlayAnimation(IdleAnim, true);
		}
	}
}

void ACatrunCandle::ResetPatrol()
{
	PatrolOrigin = GetActorTransform();
	PatrolIndex = 0;
	PatrolStep = 1;
	PatrolWaitLeft = 0.f;
}

bool ACatrunCandle::FindPatrolFloor(const FVector& Center, float& OutFloor) const
{
	if (!GetWorld() || !BlockingCapsule) return false;
	// Authored candles are upright. A tilted capsule has a different support footprint: stop safely.
	if (FMath::Abs(BlockingCapsule->GetUpVector().Z) < .99f) return false;
	const float Radius = BlockingCapsule->GetScaledCapsuleRadius() * .9f;
	const float Bottom = Center.Z - BlockingCapsule->GetScaledCapsuleHalfHeight();
	FCollisionQueryParams Params(SCENE_QUERY_STAT(CandlePatrolFloor), false, this);
	FCollisionObjectQueryParams Objects(FCollisionObjectQueryParams::AllObjects);
	Objects.RemoveObjectTypesToQuery(ECC_Pawn); // bodies never provide floor support
	float Low = MAX_flt, High = -MAX_flt;
	for (const FVector Offset : {FVector::ZeroVector, FVector(Radius,0,0), FVector(-Radius,0,0), FVector(0,Radius,0), FVector(0,-Radius,0), FVector(Radius*.7071f,Radius*.7071f,0), FVector(-Radius*.7071f,Radius*.7071f,0), FVector(Radius*.7071f,-Radius*.7071f,0), FVector(-Radius*.7071f,-Radius*.7071f,0)})
	{
		const FVector Start(Center.X+Offset.X, Center.Y+Offset.Y, Bottom+PatrolMaxFloorHeightChange+2.f);
		TArray<FHitResult> Hits;
		GetWorld()->LineTraceMultiByObjectType(Hits, Start, Start-FVector(0,0,PatrolFloorProbeDistance+PatrolMaxFloorHeightChange+2.f), Objects, Params);
		// Object traces include overlap/ignore-only volumes. Filter those before selecting support,
		// otherwise a trigger above a solid floor hides that floor from a single-hit object query.
		const FHitResult* FloorHit = nullptr;
		for (const FHitResult& Hit : Hits)
		{
			if (Hit.GetComponent() && Hit.GetComponent()->GetCollisionResponseToChannel(BlockingCapsule->GetCollisionObjectType()) == ECR_Block
				&& (!FloorHit || Hit.Distance < FloorHit->Distance)) FloorHit = &Hit;
		}
		if (!FloorHit || FloorHit->ImpactNormal.Z < .7f) return false;
		Low = FMath::Min(Low, float(FloorHit->ImpactPoint.Z));
		High = FMath::Max(High, float(FloorHit->ImpactPoint.Z));
	}
	if (High-Low > PatrolMaxFloorHeightChange) return false;
	OutFloor = High;
	return true;
}

bool ACatrunCandle::TryPatrolStep(const FVector& Delta, AActor** OutBlocker)
{
	if (OutBlocker) *OutBlocker = nullptr;
	if (!BlockingCapsule || !GetWorld() || !BlockingCapsule->IsQueryCollisionEnabled()) return false;
	const FVector Start = BlockingCapsule->GetComponentLocation(), End = Start+Delta;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(CandlePatrolMove), false, this);
	FCollisionResponseParams Responses;
	BlockingCapsule->InitSweepCollisionParams(Params, Responses);
	Params.AddIgnoredActor(this);
	const auto Shape = BlockingCapsule->GetCollisionShape();
	const auto Rotation = BlockingCapsule->GetComponentQuat();
	FHitResult Hit;
	if (GetWorld()->SweepSingleByChannel(Hit, Start, End, Rotation, BlockingCapsule->GetCollisionObjectType(), Shape, Params, Responses))
	{
		if (OutBlocker) *OutBlocker = Hit.GetActor();
		return false;
	}
	if (GetWorld()->OverlapBlockingTestByChannel(End, Rotation, BlockingCapsule->GetCollisionObjectType(), Shape, Params, Responses)) return false;
	float FromFloor, ToFloor;
	if (!FindPatrolFloor(Start, FromFloor) || !FindPatrolFloor(End, ToFloor)
		|| FMath::Abs(ToFloor-FromFloor) > PatrolMaxFloorHeightChange
		|| FMath::Abs((End.Z-ToFloor)-(Start.Z-FromFloor)) > PatrolMaxFloorHeightChange) return false;
	// Root is deliberately a SceneComponent; the attached, scaled, offset capsule was queried above.
	return SetActorLocation(GetActorLocation()+Delta, false, nullptr, ETeleportType::None);
}

bool ACatrunCandle::HasPatrolRoute() const
{
	return bPatrolEnabled && BlockingCapsule && (!PatrolPoints.IsEmpty() || !PatrolRelativePoints.IsEmpty());
}

bool ACatrunCandle::GetPatrolTarget(FVector& OutTarget) const
{
	const bool bActors = !PatrolPoints.IsEmpty();
	const int32 Count = bActors ? PatrolPoints.Num() : PatrolRelativePoints.Num();
	if (!Count) return false;
	const int32 Index = FMath::Clamp(PatrolIndex, 0, Count-1);
	if (bActors && !IsValid(PatrolPoints[Index])) return false; // keep intent, never jump to a different route
	OutTarget = bActors ? PatrolPoints[Index]->GetActorLocation() : PatrolOrigin.TransformPosition(PatrolRelativePoints[Index]);
	return true;
}

bool ACatrunCandle::IsPatrolEncounter(const AActor* Actor) const
{
	for (; Actor; Actor = Actor->GetAttachParentActor())
	{
		if (Actor->IsA<ACatrunArmor>()) return true;
		for (TActorIterator<ACatrunStatuePuzzle> It(GetWorld()); It; ++It)
			for (const FCatrunStatuePuzzleLink& Link : It->Links)
				if (Link.Statue.Get() == Actor) return true;
	}
	return false;
}

AActor* ACatrunCandle::FindPatrolEncounter(const FVector& Direction) const
{
	if (!GetWorld() || !BlockingCapsule || PatrolEncounterDistance <= 0.f || Direction.IsNearlyZero()) return nullptr;
	const FVector Ahead = Direction.GetSafeNormal2D();
	const FVector Start = BlockingCapsule->GetComponentLocation();
	const FVector End = Start + Ahead * PatrolEncounterDistance;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(CandlePatrolEncounter), false, this);
	FCollisionResponseParams Responses;
	BlockingCapsule->InitSweepCollisionParams(Params, Responses);
	Params.AddIgnoredActor(this);
	TArray<FHitResult> Hits;
	GetWorld()->SweepMultiByChannel(Hits, Start, End, BlockingCapsule->GetComponentQuat(), BlockingCapsule->GetCollisionObjectType(),
		BlockingCapsule->GetCollisionShape(), Params, Responses);
	for (const FHitResult& Hit : Hits)
	{
		AActor* Actor = Hit.GetActor();
		// Only things in front: an armor coming from behind does not turn the candle around.
		if (!Actor || FVector::DotProduct((Actor->GetActorLocation()-Start).GetSafeNormal2D(), Ahead) <= 0.f) continue;
		if (IsPatrolEncounter(Actor)) return Actor;
	}
	return nullptr;
}

void ACatrunCandle::ReversePatrol()
{
	const int32 Count = !PatrolPoints.IsEmpty() ? PatrolPoints.Num() : PatrolRelativePoints.Num();
	if (Count < 2) return;
	// Head for the point the candle came from. On the very first leg there is none: take the other way.
	int32 Previous = PatrolIndex - PatrolStep;
	if (bPatrolLoop) Previous = (Previous + Count) % Count;
	else if (Previous < 0 || Previous >= Count) Previous = PatrolIndex + PatrolStep;
	PatrolStep = -PatrolStep;
	PatrolIndex = FMath::Clamp(Previous, 0, Count-1);
	PatrolWaitLeft = FMath::Max(PatrolWaitLeft, PatrolEncounterPause);
	UE_LOG(LogCatrunSound, Log, TEXT("%s met a statue/armor and turns back to patrol point %d."), *GetName(), PatrolIndex);
}

bool ACatrunCandle::TurnPatrolFacing(float Yaw, float DeltaSeconds)
{
	const float Current = GetActorRotation().Yaw;
	const float Delta = FMath::FindDeltaAngleDegrees(Current, Yaw);
	if (FMath::Abs(Delta) <= 1.f)
	{
		if (!FMath::IsNearlyZero(Delta)) SetActorRotation(FRotator(0.f, Yaw, 0.f));
		return true;
	}
	const float MaxStep = FMath::Max(1.f, PatrolTurnSpeed) * DeltaSeconds;
	const float Step = FMath::Clamp(Delta, -MaxStep, MaxStep);
	SetActorRotation(FRotator(0.f, Current + Step, 0.f));
	return FMath::Abs(Delta - Step) <= 1.f;
}

void ACatrunCandle::UpdatePatrol(float DeltaSeconds)
{
	if (!bPatrolEnabled || bTracking || UCatrunPuzzleSuspension::IsSuspended(this) || DeltaSeconds <= 0.f) return;
	const bool bActors = !PatrolPoints.IsEmpty();
	const int32 Count = bActors ? PatrolPoints.Num() : PatrolRelativePoints.Num();
	if (!Count || !BlockingCapsule) return;
	PatrolIndex = FMath::Clamp(PatrolIndex, 0, Count-1);
	FVector Target;
	if (!GetPatrolTarget(Target)) return;
	const FVector Remaining = Target-GetActorLocation();
	// Face the next point, also while pausing (the candle turns around during the pause).
	bool bFacing = true;
	if (bPatrolFaceTravelDirection && Remaining.Size2D() > 1.f)
		bFacing = TurnPatrolFacing(Remaining.Rotation().Yaw, DeltaSeconds);
	if (PatrolWaitLeft > 0.f) { PatrolWaitLeft = FMath::Max(0.f, PatrolWaitLeft-DeltaSeconds); return; }
	if (Remaining.Size() <= 1.f)
	{
		PatrolWaitLeft = FMath::Max(0.f, PatrolPauseSeconds);
		if (bPatrolLoop) PatrolIndex = (PatrolIndex+PatrolStep+Count)%Count;
		else if (Count > 1)
		{
			if (PatrolIndex+PatrolStep < 0 || PatrolIndex+PatrolStep >= Count) PatrolStep = -PatrolStep;
			PatrolIndex += PatrolStep;
		}
		return;
	}
	if (!bFacing) return; // finish turning in place first
	const FVector Direction = Remaining.GetSafeNormal();
	// A statue or an armor ahead: turn back to the point the candle came from.
	if (FindPatrolEncounter(Direction)) { ReversePatrol(); return; }
	// Bounded work AND distance per substep. Large frame stalls cannot bridge an unsupported gap.
	float Travel = FMath::Min(Remaining.Size(), FMath::Max(0.f, PatrolSpeed)*DeltaSeconds);
	const float StepSize = FMath::Max(1.f, BlockingCapsule->GetScaledCapsuleRadius()*.25f);
	for (int32 Step=0; Step<64 && Travel>UE_KINDA_SMALL_NUMBER; ++Step)
	{
		const float Distance = FMath::Min(Travel, StepSize);
		AActor* Blocker = nullptr;
		if (!TryPatrolStep(Direction*Distance, &Blocker))
		{
			if (IsPatrolEncounter(Blocker)) ReversePatrol();
			break;
		}
		Travel -= Distance;
	}
}
