#include "SoundWaveVisual.h"

#include "Catrun.h"
#include "CatrunSoundSettings.h"
#include "SoundPropagation.h"
#include "Grid/CatrunGridData.h"
#include "Async/ParallelFor.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/Texture2D.h"
#include "Engine/World.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Math/Float16.h"

namespace
{
	// Picture value meaning "the sound never gets here". The material draws nothing there.
	// Must stay below the largest 16-bit float (65504) and above 60000 (see M_SoundWave).
	constexpr float UnreachedPixel = 65000.f;

	// The picture may not be larger than this in either direction (graphics card limit).
	constexpr int32 MaxTextureSize = 8192;

	// Distance (cm) at a floor position, interpolated between the four nearest cell centres.
	// Returns UnreachedPixel when the cell under the position is not reached by the sound.
	float SampleDistance(const FCatrunGridData& Grid, const TArray<float>& Distance, float WorldX, float WorldY)
	{
		const float CellX = (WorldX - Grid.Origin.X) / Grid.CellSize;
		const float CellY = (WorldY - Grid.Origin.Y) / Grid.CellSize;

		// The cell under the position decides whether there is sound here at all.
		const int32 OwnX = FMath::FloorToInt(CellX);
		const int32 OwnY = FMath::FloorToInt(CellY);
		if (!Grid.InBounds(OwnX, OwnY) || Distance[Grid.CellIndex(OwnX, OwnY)] == CatrunSoundPropagation::Unreached)
		{
			return UnreachedPixel;
		}

		// Bilinear blend of the surrounding cell centres that the sound reaches (smooth ring).
		const float BlendX = CellX - 0.5f;
		const float BlendY = CellY - 0.5f;
		const int32 X0 = FMath::FloorToInt(BlendX);
		const int32 Y0 = FMath::FloorToInt(BlendY);
		const float FractionX = BlendX - X0;
		const float FractionY = BlendY - Y0;

		float WeightedSum = 0.f;
		float TotalWeight = 0.f;
		for (int32 OffsetY = 0; OffsetY <= 1; ++OffsetY)
		{
			for (int32 OffsetX = 0; OffsetX <= 1; ++OffsetX)
			{
				const int32 X = X0 + OffsetX;
				const int32 Y = Y0 + OffsetY;
				if (!Grid.InBounds(X, Y) || Distance[Grid.CellIndex(X, Y)] == CatrunSoundPropagation::Unreached)
				{
					continue;
				}
				const float Weight = (OffsetX ? FractionX : 1.f - FractionX) * (OffsetY ? FractionY : 1.f - FractionY);
				WeightedSum += Weight * Distance[Grid.CellIndex(X, Y)];
				TotalWeight += Weight;
			}
		}
		return TotalWeight > KINDA_SMALL_NUMBER ? WeightedSum / TotalWeight : Distance[Grid.CellIndex(OwnX, OwnY)];
	}
}

USoundWaveVisual::USoundWaveVisual()
{
	PrimaryComponentTick.bCanEverTick = true;
}

void USoundWaveVisual::Initialize(const FCatrunGridData& Grid, const UCatrunSoundSettings& InSettings)
{
	Settings = &InSettings;
	AActor* Owner = GetOwner();
	UStaticMesh* PlaneMesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Plane.Plane"));
	if (!Owner || !PlaneMesh || !Settings->WaveMaterial || !Grid.IsValid())
	{
		UE_LOG(LogCatrunSound, Warning, TEXT("Sound wave visual disabled: needs a grid, the plane mesh and Settings->WaveMaterial."));
		return;
	}

	// The picture covers the grid area. One pixel = Texel cm of floor (VisualTexelSize, made larger
	// only when the map is so big that the picture would be too large for the graphics card).
	const float LongestSide = FMath::Max(Grid.Width, Grid.Height) * Grid.CellSize;
	Texel = FMath::Max(FMath::Max(Settings->VisualTexelSize, 0.1f), LongestSide / MaxTextureSize);
	TextureWidth = FMath::CeilToInt(Grid.Width * Grid.CellSize / Texel);
	TextureHeight = FMath::CeilToInt(Grid.Height * Grid.CellSize / Texel);
	const float AreaWidth = TextureWidth * Texel;
	const float AreaHeight = TextureHeight * Texel;

	// 16-bit float picture with one channel: precise enough for distances in cm, and small
	// (2 bytes per pixel) even at one pixel per square centimetre.
	DistanceTexture = UTexture2D::CreateTransient(TextureWidth, TextureHeight, PF_R16F);
	DistanceTexture->Filter = TF_Nearest; // values are already smoothed in FillTexture
	DistanceTexture->AddressX = TA_Clamp;
	DistanceTexture->AddressY = TA_Clamp;
	DistanceTexture->SRGB = false;
	DistanceTexture->NeverStream = true;

	// Start with "no sound anywhere".
	{
		FTexture2DMipMap& Mip = DistanceTexture->GetPlatformData()->Mips[0];
		FFloat16* Pixels = static_cast<FFloat16*>(Mip.BulkData.Lock(LOCK_READ_WRITE));
		const FFloat16 Nothing(UnreachedPixel);
		const int32 Width = TextureWidth;
		ParallelFor(TextureHeight, [Pixels, Nothing, Width](int32 Y)
		{
			for (int32 X = 0; X < Width; ++X)
			{
				Pixels[Y * Width + X] = Nothing;
			}
		});
		Mip.BulkData.Unlock();
	}
	DistanceTexture->UpdateResource();

	// One flat plane laid over the whole map.
	Plane = NewObject<UStaticMeshComponent>(Owner, TEXT("WavePlane"));
	Plane->SetStaticMesh(PlaneMesh);
	Plane->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Plane->SetCastShadow(false);
	Plane->SetCanEverAffectNavigation(false);
	Plane->SetupAttachment(Owner->GetRootComponent());
	Plane->RegisterComponent();
	Plane->SetWorldLocation(FVector(Grid.Origin.X + AreaWidth * 0.5f, Grid.Origin.Y + AreaHeight * 0.5f, Grid.Origin.Z + Settings->VisualHeight));
	Plane->SetWorldScale3D(FVector(AreaWidth / 100.f, AreaHeight / 100.f, 1.f)); // the engine plane is 100 x 100 cm

	// Material settings that never change while the game runs.
	Material = UMaterialInstanceDynamic::Create(Settings->WaveMaterial, Owner);
	Material->SetTextureParameterValue(TEXT("DistTex"), DistanceTexture);
	Material->SetVectorParameterValue(TEXT("GridRect"), FLinearColor(Grid.Origin.X, Grid.Origin.Y, AreaWidth, AreaHeight));
	Material->SetVectorParameterValue(TEXT("SoundColor"), FLinearColor(Settings->SoundColor.R, Settings->SoundColor.G, Settings->SoundColor.B, 1.f));
	Material->SetScalarParameterValue(TEXT("RingWidth"), Settings->RingWidth);
	Material->SetScalarParameterValue(TEXT("Feather"), Settings->RingFeather);
	Material->SetScalarParameterValue(TEXT("EdgeFade"), Settings->EdgeFade);
	Material->SetScalarParameterValue(TEXT("RingCount"), static_cast<float>(Settings->WaveCount));
	Material->SetScalarParameterValue(TEXT("RingGap"), Settings->WaveInterval * Settings->SoundSpeed);
	Plane->SetMaterial(0, Material);

	SetPlaneVisible(false);
}

void USoundWaveVisual::SetPlaneVisible(bool bVisible)
{
	if (Plane)
	{
		Plane->SetVisibility(bVisible);
	}
}

// How long the rings need to travel: the last ring starts (Count - 1) gaps after the first.
float USoundWaveVisual::GetTravelDuration() const
{
	const float TailLength = Settings->RingWidth + (Settings->WaveCount - 1) * Settings->WaveInterval * Settings->SoundSpeed;
	return (Budget + TailLength) / Settings->SoundSpeed;
}

void USoundWaveVisual::Show(const FCatrunGridData& Grid, const TArray<float>& Distance, float InBudget, double InStartTime)
{
	if (!Material || !DistanceTexture)
	{
		return;
	}
	// Quiet sounds (footsteps) must not wipe out a louder wave that is still travelling.
	if (bActive && InBudget < Budget && (InStartTime - StartTime) < GetTravelDuration())
	{
		return;
	}
	FillTexture(Grid, Distance);

	Budget = InBudget;
	StartTime = InStartTime;
	bActive = true;
	Material->SetScalarParameterValue(TEXT("Budget"), Budget);
	Material->SetScalarParameterValue(TEXT("Radius"), 0.f);
	Material->SetScalarParameterValue(TEXT("Opacity"), 0.f);
	SetPlaneVisible(true);
}

// Writes the distances into the picture. Only the part around the sound is written (plus the part
// the previous sound wrote, which has to be cleared), so the picture can be as fine as one pixel
// per square centimetre. The rows are filled on several threads.
void USoundWaveVisual::FillTexture(const FCatrunGridData& Grid, const TArray<float>& Distance)
{
	// The cells the sound reaches.
	int32 MinCellX = MAX_int32, MinCellY = MAX_int32, MaxCellX = -1, MaxCellY = -1;
	for (int32 CellY = 0; CellY < Grid.Height; ++CellY)
	{
		for (int32 CellX = 0; CellX < Grid.Width; ++CellX)
		{
			if (Distance[Grid.CellIndex(CellX, CellY)] != CatrunSoundPropagation::Unreached)
			{
				MinCellX = FMath::Min(MinCellX, CellX);
				MaxCellX = FMath::Max(MaxCellX, CellX);
				MinCellY = FMath::Min(MinCellY, CellY);
				MaxCellY = FMath::Max(MaxCellY, CellY);
			}
		}
	}
	if (MaxCellX < 0)
	{
		return;
	}

	// The same area in pixels, one cell wider on every side.
	const FIntRect NewRect(
		FMath::Max(0, FMath::FloorToInt((MinCellX - 1) * Grid.CellSize / Texel)),
		FMath::Max(0, FMath::FloorToInt((MinCellY - 1) * Grid.CellSize / Texel)),
		FMath::Min(TextureWidth, FMath::CeilToInt((MaxCellX + 2) * Grid.CellSize / Texel)),
		FMath::Min(TextureHeight, FMath::CeilToInt((MaxCellY + 2) * Grid.CellSize / Texel)));
	FIntRect Rect = NewRect;
	if (bHasWrittenRect)
	{
		Rect.Min.X = FMath::Min(Rect.Min.X, WrittenRect.Min.X);
		Rect.Min.Y = FMath::Min(Rect.Min.Y, WrittenRect.Min.Y);
		Rect.Max.X = FMath::Max(Rect.Max.X, WrittenRect.Max.X);
		Rect.Max.Y = FMath::Max(Rect.Max.Y, WrittenRect.Max.Y);
	}

	FTexture2DMipMap& Mip = DistanceTexture->GetPlatformData()->Mips[0];
	FFloat16* Pixels = static_cast<FFloat16*>(Mip.BulkData.Lock(LOCK_READ_WRITE));
	const int32 Width = TextureWidth;
	const float PixelSize = Texel;
	ParallelFor(Rect.Height(), [&](int32 Row)
	{
		const int32 Y = Rect.Min.Y + Row;
		for (int32 X = Rect.Min.X; X < Rect.Max.X; ++X)
		{
			// World position of the middle of this pixel.
			const float WorldX = Grid.Origin.X + (X + 0.5f) * PixelSize;
			const float WorldY = Grid.Origin.Y + (Y + 0.5f) * PixelSize;
			Pixels[Y * Width + X] = FFloat16(SampleDistance(Grid, Distance, WorldX, WorldY));
		}
	});
	Mip.BulkData.Unlock();
	DistanceTexture->UpdateResource();

	WrittenRect = NewRect;
	bHasWrittenRect = true;
}

void USoundWaveVisual::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	if (!bActive || !Material)
	{
		return;
	}

	const float Elapsed = static_cast<float>(GetWorld()->GetTimeSeconds() - StartTime);

	// The first ring front moves at sound speed; the others follow it at a fixed gap. It is done
	// when the back of the last ring passed the budget.
	const float Radius = Elapsed * Settings->SoundSpeed;
	const float TravelDuration = GetTravelDuration();

	// After the rings have finished, hold for a moment and fade out.
	const float TimeAfterTravel = Elapsed - TravelDuration - Settings->HoldDuration;
	const float Fade = TimeAfterTravel <= 0.f ? 1.f : 1.f - FMath::Clamp(TimeAfterTravel / FMath::Max(Settings->FadeDuration, 0.01f), 0.f, 1.f);

	if (Fade <= 0.f)
	{
		bActive = false;
		SetPlaneVisible(false);
		return;
	}
	Material->SetScalarParameterValue(TEXT("Radius"), Radius);
	Material->SetScalarParameterValue(TEXT("Opacity"), Settings->SoundColor.A * Fade);
}
