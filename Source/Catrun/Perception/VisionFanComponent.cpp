#include "VisionFanComponent.h"
#include "Monster/CatrunPerceptionPolicy.h"

#include "Catrun.h"
#include "Sound/CatrunDoor.h"
#include "Sound/CatrunSoundSettings.h"
#include "Sound/SoundGridManager.h"
#include "Camera/CameraComponent.h"
#include "CollisionQueryParams.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/Texture2D.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Math/Float16Color.h"

UCatrunVisionFanComponent::UCatrunVisionFanComponent()
{
	// The owner calls Update every frame. This tick only hides the floor display while a cinematic
	// camera owns the screen, also for owners that stop updating (capture, frozen AI).
	PrimaryComponentTick.bCanEverTick = true;
}

bool UCatrunVisionFanComponent::IsCinematicView(const UWorld* World)
{
	// The gameplay and puzzle-reveal cameras are orthographic. The warehouse view is perspective but played.
	const APlayerController* PC = World ? World->GetFirstPlayerController() : nullptr;
	const AActor* View = PC ? PC->GetViewTarget() : nullptr;
	if (!View || View->ActorHasTag(TEXT("CatrunGameplayCamera")) || View->ActorHasTag(TEXT("CatrunElevatorWarehouseCamera"))) return false;
	const UCameraComponent* Camera = View->FindComponentByClass<UCameraComponent>();
	return Camera && Camera->ProjectionMode == ECameraProjectionMode::Perspective;
}

void UCatrunVisionFanComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	ApplyDisplayVisibility();
}

void UCatrunVisionFanComponent::ApplyDisplayVisibility()
{
	const bool bShow = bDisplayVisible && !IsCinematicView(GetWorld());
	if (Plane && Plane->GetVisibleFlag() != bShow) Plane->SetVisibility(bShow);
}

void UCatrunVisionFanComponent::Configure(float InRange, int32 InRayCount, const FLinearColor& InColor)
{
	Range = FMath::Max(InRange, 10.f);
	RayCount = FMath::Max(InRayCount, 4);
	Color = InColor;
	RayDistances.Init(Range, RayCount);
	DisplayRayDistances.Init(GetDisplayRange(), RayCount);
}

void UCatrunVisionFanComponent::SetDisplayMaterialOverride(UMaterialInterface* InMaterial)
{
	DisplayMaterialOverride = InMaterial;
}

void UCatrunVisionFanComponent::SetDisplayStyle(float InOpacity, float InRadiusPadding)
{
	DisplayOpacity = FMath::Clamp(InOpacity, 0.f, 1.f);
	DisplayRadiusPadding = FMath::Max(0.f, InRadiusPadding);
	if (Plane) Plane->SetWorldScale3D(FVector(GetDisplayRange() * .02f, GetDisplayRange() * .02f, 1.f));
	if (Material)
	{
		Material->SetScalarParameterValue(TEXT("Range"), GetDisplayRange());
		Material->SetScalarParameterValue(TEXT("Opacity"), DisplayOpacity);
	}
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
	DisplayRayDistances.Init(GetDisplayRange(), RayCount);

	AActor* Owner = GetOwner();
	UStaticMesh* PlaneMesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Plane.Plane"));
	UMaterialInterface* DisplayMaterial = DisplayMaterialOverride ? DisplayMaterialOverride.Get() : Settings->VisionMaterial.Get();
	if (Owner && PlaneMesh && DisplayMaterial)
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
		Plane->SetWorldScale3D(FVector(GetDisplayRange() * 2.f / 100.f, GetDisplayRange() * 2.f / 100.f, 1.f)); // engine plane is 100 x 100 cm
		Plane->SetVisibility(bDisplayVisible && !IsCinematicView(GetWorld()));

		Material = UMaterialInstanceDynamic::Create(DisplayMaterial, Owner);
		Material->SetTextureParameterValue(TEXT("DistTex"), DistanceTexture);
		Material->SetVectorParameterValue(TEXT("Color"), FLinearColor(Color.R, Color.G, Color.B, 1.f));
		Material->SetScalarParameterValue(TEXT("Range"), GetDisplayRange());
		Material->SetScalarParameterValue(TEXT("Feather"), Settings->VisionEdgeSoftness);
		Material->SetScalarParameterValue(TEXT("RangeFade"), Settings->VisionRangeFade);
		Material->SetScalarParameterValue(TEXT("Opacity"), DisplayOpacity >= 0.f ? DisplayOpacity : Settings->VisionOpacity);
		Plane->SetMaterial(0, Material);
	}
	else
	{
		UE_LOG(LogCatrunSound, Warning, TEXT("%s: vision display could not be created. Sight remains active."), *GetNameSafe(Owner));
	}
	bReady = true;
	return true;
}

float UCatrunVisionFanComponent::GetFreeDistance(const FVector& From, const FVector& Direction, float MaxDistance) const
{
	if (!bReady || !Settings)
	{
		return MaxDistance;
	}
	const FVector Start(From.X, From.Y, FloorZ + Settings->VisionTraceHeight);
	return TraceRay(Start, Direction, MaxDistance);
}

float UCatrunVisionFanComponent::TraceRay(const FVector& Start, const FVector& Direction, float MaxDistance) const
{
	return GetWorld() ? CatrunPerception::SightDistance(*GetWorld(), Start, Start+Direction*MaxDistance, GetOwner()) : MaxDistance;
}

void UCatrunVisionFanComponent::Update(float CenterAngleDegrees, float HalfAngleDegrees, bool bWriteDisplay)
{
	if (!EnsureReady())
	{
		return;
	}
	CenterAngle = CenterAngleDegrees;
	HalfAngle = FMath::Clamp(HalfAngleDegrees, 1.f, 180.f);

	const FVector Origin = GetOrigin();
	const FVector Start(Origin.X, Origin.Y, FloorZ + Settings->VisionTraceHeight);
	LastOrigin = Origin;
	LastStart = Start;
	bHasFan = true;

	// Ray i points to the middle of the i-th slice of the fan.
	const float Slice = (2.f * HalfAngle) / RayCount;
	for (int32 i = 0; i < RayCount; ++i)
	{
		const float AngleRad = FMath::DegreesToRadians(CenterAngle - HalfAngle + (i + 0.5f) * Slice);
		// The first NearClip cm of every ray are skipped (not traced, not drawn).
		const FVector Direction(FMath::Cos(AngleRad), FMath::Sin(AngleRad), 0.f);
		RayDistances[i] = NearClip + TraceRay(Start + Direction * NearClip, Direction, FMath::Max(Range - NearClip, 1.f));
	}

	if (bWriteDisplay)
	{
		WriteDisplay();
	}
}

void UCatrunVisionFanComponent::WriteDisplay()
{
	// The display is presentation only: hidden by the owner, it is neither traced nor uploaded.
	if (!bReady || !bHasFan || !bDisplayVisible || !Plane || !Material || !Settings)
	{
		return;
	}
	const int32 Num = FMath::Min(RayCount, FMath::Min(RayDistances.Num(), DisplayRayDistances.Num()));
	const float Slice = (2.f * HalfAngle) / RayCount;
	for (int32 i = 0; i < Num; ++i)
	{
		if (DisplayRadiusPadding > 0.f)
		{
			const float AngleRad = FMath::DegreesToRadians(CenterAngle - HalfAngle + (i + 0.5f) * Slice);
			const FVector Direction(FMath::Cos(AngleRad), FMath::Sin(AngleRad), 0.f);
			DisplayRayDistances[i] = NearClip + TraceRay(LastStart + Direction * NearClip, Direction, FMath::Max(GetDisplayRange() - NearClip, 1.f));
		}
		else
		{
			DisplayRayDistances[i] = RayDistances[i];
		}
	}

	WriteTexture();
	Plane->SetWorldLocation(FVector(LastOrigin.X, LastOrigin.Y, FloorZ + Settings->VisualHeight));
	Material->SetVectorParameterValue(TEXT("Center"), FLinearColor(LastOrigin.X, LastOrigin.Y, NearClip, 0.f)); // z = near clip, see M_VisionFan
	Material->SetScalarParameterValue(TEXT("CenterAngle"), CenterAngle);
	Material->SetScalarParameterValue(TEXT("HalfAngle"), HalfAngle);
}

void UCatrunVisionFanComponent::WriteTexture()
{
	if (!DistanceTexture || !DistanceTexture->GetPlatformData() || DistanceTexture->GetPlatformData()->Mips.IsEmpty())
	{
		return;
	}
	// The texture is created once with the RayCount of that moment; never write past it.
	const int32 Width = DistanceTexture->GetSizeX();
	ensureMsgf(Width == RayCount, TEXT("%s: vision texture has %d pixels but the fan has %d rays (Configure after first Update)."),
		*GetNameSafe(GetOwner()), Width, RayCount);
	const int32 Num = FMath::Min(FMath::Min(RayCount, Width), DisplayRayDistances.Num());
	// An unchanged fan (a still monster) keeps the uploaded texture.
	if (WrittenRayDistances.Num() == Num && FMemory::Memcmp(WrittenRayDistances.GetData(), DisplayRayDistances.GetData(), Num * sizeof(float)) == 0)
	{
		return;
	}
	FTexture2DMipMap& Mip = DistanceTexture->GetPlatformData()->Mips[0];
	FFloat16Color* Pixels = static_cast<FFloat16Color*>(Mip.BulkData.Lock(LOCK_READ_WRITE));
	for (int32 i = 0; i < Num; ++i)
	{
		Pixels[i] = FFloat16Color();
		Pixels[i].R = DisplayRayDistances[i];
	}
	Mip.BulkData.Unlock();
	DistanceTexture->UpdateResource();
	WrittenRayDistances.SetNum(Num);
	FMemory::Memcpy(WrittenRayDistances.GetData(), DisplayRayDistances.GetData(), Num * sizeof(float));
}

bool UCatrunVisionFanComponent::CanSee(const FVector& WorldPoint, float PointRadius) const
{
	if (!bReady || RayDistances.IsEmpty())
	{
		return false;
	}
	const FVector Origin = GetOrigin();
	const FVector2D ToPoint(WorldPoint.X - Origin.X, WorldPoint.Y - Origin.Y);
	const float Distance = ToPoint.Size();
	const float NearEdge = Distance - PointRadius; // distance to the closest part of the body
	if (NearEdge > Range || Distance < NearClip)
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

FVector UCatrunVisionFanComponent::GetOrigin() const
{
	return bOriginOverridden ? OriginOverride : GetOwner()->GetActorLocation();
}

void UCatrunVisionFanComponent::SetOriginOverride(const FVector& WorldPoint)
{
	bOriginOverridden = true;
	OriginOverride = WorldPoint;
}

void UCatrunVisionFanComponent::ClearOriginOverride()
{
	bOriginOverridden = false;
}

void UCatrunVisionFanComponent::SetDisplayVisible(bool bVisible)
{
	const bool bWasVisible = bDisplayVisible;
	bDisplayVisible = bVisible;
	// While hidden the display was not updated: redraw the last fan before it shows again.
	if (bVisible && !bWasVisible)
	{
		WriteDisplay();
	}
	ApplyDisplayVisibility();
}
