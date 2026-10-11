#include "VisionFanComponent.h"

#include "Catrun.h"
#include "Sound/CatrunDoor.h"
#include "Sound/CatrunSoundSettings.h"
#include "Sound/SoundGridManager.h"
#include "CollisionQueryParams.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/Texture2D.h"
#include "Engine/World.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Math/Float16Color.h"

UCatrunVisionFanComponent::UCatrunVisionFanComponent()
{
	// The owner calls Update every frame, so the component needs no tick of its own.
	PrimaryComponentTick.bCanEverTick = false;
}

void UCatrunVisionFanComponent::Configure(float InRange, int32 InRayCount, const FLinearColor& InColor)
{
	Range = FMath::Max(InRange, 10.f);
	RayCount = FMath::Max(InRayCount, 4);
	Color = InColor;
	RayDistances.Init(Range, RayCount);
}

bool UCatrunVisionFanComponent::EnsureReady()
{
	if (bReady)
	{
		return true;
	}
	const ASoundGridManager* Manager = ASoundGridManager::Get(this);
	if (!Manager || !Manager->HasGrid() || !Manager->GetSettings())
	{
		return false; // the sound system of the level is not up yet; try again next frame
	}
	Settings = Manager->GetSettings();
	FloorZ = Manager->GetGrid().Origin.Z;
	RayDistances.Init(Range, RayCount);

	AActor* Owner = GetOwner();
	UStaticMesh* PlaneMesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Plane.Plane"));
	if (Owner && PlaneMesh && Settings->VisionMaterial)
	{
		// One ray distance per pixel in a one-pixel-high picture. 16-bit float values, filtered
		// smoothly so the display edge does not show the individual rays.
		DistanceTexture = UTexture2D::CreateTransient(RayCount, 1, PF_FloatRGBA);
		DistanceTexture->Filter = TF_Bilinear;
		DistanceTexture->AddressX = TA_Clamp;
		DistanceTexture->AddressY = TA_Clamp;
		DistanceTexture->SRGB = false;
		DistanceTexture->NeverStream = true;
		DistanceTexture->UpdateResource();

		// A flat square, large enough for the whole fan, lying on the floor.
		Plane = NewObject<UStaticMeshComponent>(Owner, FName(*FString::Printf(TEXT("%s_VisionPlane"), *GetName())));
		Plane->SetStaticMesh(PlaneMesh);
		Plane->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Plane->SetCastShadow(false);
		Plane->SetCanEverAffectNavigation(false);
		Plane->SetupAttachment(Owner->GetRootComponent());
		Plane->RegisterComponent();
		Plane->SetUsingAbsoluteLocation(true);
		Plane->SetUsingAbsoluteRotation(true);
		Plane->SetUsingAbsoluteScale(true);
		Plane->SetWorldScale3D(FVector(Range * 2.f / 100.f, Range * 2.f / 100.f, 1.f)); // engine plane is 100 x 100 cm
		Plane->SetVisibility(bDisplayVisible);

		Material = UMaterialInstanceDynamic::Create(Settings->VisionMaterial, Owner);
		Material->SetTextureParameterValue(TEXT("DistTex"), DistanceTexture);
		Material->SetVectorParameterValue(TEXT("Color"), FLinearColor(Color.R, Color.G, Color.B, 1.f));
		Material->SetScalarParameterValue(TEXT("Range"), Range);
		Material->SetScalarParameterValue(TEXT("Feather"), Settings->VisionEdgeSoftness);
		Material->SetScalarParameterValue(TEXT("RangeFade"), Settings->VisionRangeFade);
		Material->SetScalarParameterValue(TEXT("Opacity"), Settings->VisionOpacity);
		Plane->SetMaterial(0, Material);
	}
	else
	{
		UE_LOG(LogCatrunSound, Warning, TEXT("%s: vision display disabled (needs Settings->VisionMaterial). The sight still works."), *GetOwner()->GetName());
	}
	bReady = true;
	return true;
}

float UCatrunVisionFanComponent::TraceRay(const FVector& Start, const FVector& Direction) const
{
	const UWorld* World = GetWorld();
	FCollisionQueryParams Params(SCENE_QUERY_STAT(CatrunVisionRay), /*bTraceComplex*/ true, GetOwner());
	TArray<FHitResult> Hits;
	World->LineTraceMultiByObjectType(Hits, Start, Start + Direction * Range, FCollisionObjectQueryParams(ECC_WorldStatic), Params);

	for (const FHitResult& Hit : Hits)
	{
		const AActor* HitActor = Hit.GetActor();
		if (!HitActor)
		{
			continue;
		}
		// Walls, furniture marked as obstacle, and closed doors (an open door has no collision).
		const bool bBlocks = HitActor->ActorHasTag(Settings->WallTag) || HitActor->ActorHasTag(Settings->ObstacleTag)
			|| HitActor->IsA<ACatrunDoor>();
		if (bBlocks)
		{
			return Hit.Distance;
		}
	}
	return Range;
}

void UCatrunVisionFanComponent::Update(float CenterAngleDegrees, float HalfAngleDegrees)
{
	if (!EnsureReady())
	{
		return;
	}
	CenterAngle = CenterAngleDegrees;
	HalfAngle = FMath::Clamp(HalfAngleDegrees, 1.f, 180.f);

	const FVector Origin = GetOwner()->GetActorLocation();
	const FVector Start(Origin.X, Origin.Y, FloorZ + Settings->VisionTraceHeight);

	// Ray i points to the middle of the i-th slice of the fan.
	const float Slice = (2.f * HalfAngle) / RayCount;
	for (int32 i = 0; i < RayCount; ++i)
	{
		const float AngleRad = FMath::DegreesToRadians(CenterAngle - HalfAngle + (i + 0.5f) * Slice);
		RayDistances[i] = TraceRay(Start, FVector(FMath::Cos(AngleRad), FMath::Sin(AngleRad), 0.f));
	}

	if (Plane && Material)
	{
		WriteTexture();
		Plane->SetWorldLocation(FVector(Origin.X, Origin.Y, FloorZ + Settings->VisualHeight));
		Material->SetVectorParameterValue(TEXT("Center"), FLinearColor(Origin.X, Origin.Y, 0.f, 0.f));
		Material->SetScalarParameterValue(TEXT("CenterAngle"), CenterAngle);
		Material->SetScalarParameterValue(TEXT("HalfAngle"), HalfAngle);
	}
}

void UCatrunVisionFanComponent::WriteTexture()
{
	FTexture2DMipMap& Mip = DistanceTexture->GetPlatformData()->Mips[0];
	FFloat16Color* Pixels = static_cast<FFloat16Color*>(Mip.BulkData.Lock(LOCK_READ_WRITE));
	for (int32 i = 0; i < RayCount; ++i)
	{
		Pixels[i] = FFloat16Color();
		Pixels[i].R = RayDistances[i];
	}
	Mip.BulkData.Unlock();
	DistanceTexture->UpdateResource();
}

bool UCatrunVisionFanComponent::CanSee(const FVector& WorldPoint, float PointRadius) const
{
	if (!bReady || RayDistances.IsEmpty())
	{
		return false;
	}
	const FVector Origin = GetOwner()->GetActorLocation();
	const FVector2D ToPoint(WorldPoint.X - Origin.X, WorldPoint.Y - Origin.Y);
	const float Distance = ToPoint.Size();
	const float NearEdge = Distance - PointRadius; // distance to the closest part of the body
	if (NearEdge > Range)
	{
		return false;
	}

	// Which part of the fan is the point in? (A point on top of the monster is always seen.)
	if (Distance < KINDA_SMALL_NUMBER)
	{
		return true;
	}
	const float Angle = FMath::RadiansToDegrees(FMath::Atan2(ToPoint.Y, ToPoint.X));
	const float Delta = FMath::FindDeltaAngleDegrees(CenterAngle, Angle);
	const float BodyHalfWidth = FMath::RadiansToDegrees(FMath::Asin(FMath::Clamp(PointRadius / Distance, 0.f, 1.f)));
	if (FMath::Abs(Delta) > HalfAngle + BodyHalfWidth)
	{
		return false;
	}

	// Compare with the ray that points at it (blend of the two nearest rays).
	const float Position = FMath::Clamp((Delta + HalfAngle) / (2.f * HalfAngle) * RayCount - 0.5f, 0.f, RayCount - 1.f);
	const int32 Low = FMath::FloorToInt(Position);
	const int32 High = FMath::Min(Low + 1, RayCount - 1);
	const float RayDistance = FMath::Lerp(RayDistances[Low], RayDistances[High], Position - Low);
	return NearEdge <= RayDistance;
}

void UCatrunVisionFanComponent::SetColor(const FLinearColor& NewColor)
{
	Color = NewColor;
	if (Material)
	{
		Material->SetVectorParameterValue(TEXT("Color"), FLinearColor(Color.R, Color.G, Color.B, 1.f));
	}
}

void UCatrunVisionFanComponent::SetDisplayVisible(bool bVisible)
{
	bDisplayVisible = bVisible;
	if (Plane)
	{
		Plane->SetVisibility(bVisible);
	}
}
