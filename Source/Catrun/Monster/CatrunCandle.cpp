#include "CatrunCandle.h"

#include "Catrun.h"
#include "Perception/AlertMarkComponent.h"
#include "Perception/CatrunCatQueries.h"
#include "Perception/VisionFanComponent.h"
#include "Sound/CatrunSoundSettings.h"
#include "Sound/SoundGridManager.h"
#include "Animation/AnimationAsset.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/Pawn.h"

ACatrunCandle::ACatrunCandle()
{
	PrimaryActorTick.bCanEverTick = true;

	SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));

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

void ACatrunCandle::BeginPlay()
{
	Super::BeginPlay();
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

void ACatrunCandle::UpdateSweep(float DeltaSeconds, const UCatrunSoundSettings& S)
{
	// The cone stays inside the total range, so its middle can move this far from the candle's direction.
	const float MaxOffset = FMath::Max(0.f, (S.CandleTotalAngle - S.CandleConeAngle) * 0.5f);

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
	const float MaxOffset = FMath::Max(0.f, (S.CandleTotalAngle - S.CandleConeAngle) * 0.5f);

	// Direction of the cat as an angle away from the candle's own direction.
	const FVector ToCat = Cat.GetActorLocation() - GetActorLocation();
	const float CatAngle = FMath::RadiansToDegrees(FMath::Atan2(ToCat.Y, ToCat.X));
	const float WantedOffset = FMath::Clamp(FMath::FindDeltaAngleDegrees(GetActorRotation().Yaw, CatAngle), -MaxOffset, MaxOffset);

	SweepOffset = FMath::FixedTurn(SweepOffset, WantedOffset, S.CandleTrackSpeed * DeltaSeconds);
	PauseLeft = 0.f;
}

void ACatrunCandle::StartTracking(APawn& Cat, const UCatrunSoundSettings& S)
{
	bTracking = true;
	LoseSightTimer = 0.f;
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
	Sight->SetColor(S.CandleSightColor); // red -> orange; the sweep goes on from where the cone is
}

void ACatrunCandle::CheckForCat(float DeltaSeconds, APawn* Cat, const UCatrunSoundSettings& S)
{
	const bool bSees = Cat && !CatrunCat::IsHiding(Cat) && Sight->CanSee(Cat->GetActorLocation(), S.CatSightRadius);

	if (bSees)
	{
		LoseSightTimer = 0.f;
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
	Super::Tick(DeltaSeconds);

	const UCatrunSoundSettings* S = GetSettings();
	if (!S)
	{
		return;
	}
	if (!bSightConfigured)
	{
		// The sight numbers come from the settings asset of the level (read once).
		Sight->Configure(S->CandleRange, S->CandleRayCount, S->CandleSightColor);
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

	// Move the cone: follow the cat while tracking, otherwise sweep.
	APawn* Cat = CatrunCat::Find(this);
	if (bTracking && Cat)
	{
		TrackCat(DeltaSeconds, *Cat, *S);
	}
	else
	{
		UpdateSweep(DeltaSeconds, *S);
	}

	// The cone and the body (eyes) turn together.
	const float ConeCenter = GetActorRotation().Yaw + SweepOffset;
	Sight->Update(ConeCenter, S->CandleConeAngle * 0.5f);
	Body->SetWorldRotation(FRotator(0.f, ConeCenter + AutoBodyYaw + BodyYawOffset, 0.f));

	CheckForCat(DeltaSeconds, Cat, *S);

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
