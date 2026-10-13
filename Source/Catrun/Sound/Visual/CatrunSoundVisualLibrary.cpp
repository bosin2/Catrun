#include "Sound/Visual/CatrunSoundVisualLibrary.h"

#include "Engine/Texture2D.h"
#include "Grid/CatrunGridData.h"
#include "Sound/SoundGridManager.h"
#include "Sound/SoundPropagation.h"

bool UCatrunSoundVisualLibrary::CaptureLatestSoundVisual(
	ASoundGridManager* SoundManager,
	float Budget,
	FCatrunSoundVisualSnapshot& Snapshot)
{
	// 실패했을 때 이전 결과가 남지 않도록 초기화한다.
	Snapshot = FCatrunSoundVisualSnapshot();

	// 게임 스레드에서 유효한 매니저와 범위로 호출됐는지 확인한다.
	if (!IsInGameThread() ||
		!IsValid(SoundManager) ||
		!SoundManager->HasGrid() ||
		!FMath::IsFinite(Budget) ||
		Budget <= 0.f)
	{
		return false;
	}

	// 기존 소리 전파 격자를 읽는다. 격자 자체는 수정하지 않는다.
	const FCatrunGridData& Grid = SoundManager->GetGrid();

	if (!Grid.IsValid() ||
		!FMath::IsFinite(Grid.CellSize) ||
		Grid.CellSize <= 0.f)
	{
		return false;
	}

	const int64 CellCount64 =
		static_cast<int64>(Grid.Width) * Grid.Height;

	if (CellCount64 <= 0 || CellCount64 > MAX_int32)
	{
		return false;
	}

	const int32 CellCount = static_cast<int32>(CellCount64);

	// 격자 크기와 내부 데이터 개수가 일치하는지 확인한다.
	if (Grid.Walkable.Num() != CellCount ||
		Grid.EdgeMask.Num() != CellCount ||
		Grid.CostMultiplier.Num() != CellCount)
	{
		return false;
	}

	// 각 칸까지의 전파 거리를 저장한다.
	// 기존 시스템이 계산해 둔 그림용 거리를 읽는다.
// 실제 소리 범위 밖의 여유 데이터도 가져와 끝부분 잘림을 방지한다.
	float CapturedBudget = 0.f;
	const TArray<float>& VisualDistances =
		SoundManager->GetLatestVisualDistances(CapturedBudget);

	// 같은 소리 이벤트의 결과인지 기본적인 유효성을 확인한다.
	// 반드시 OnSoundEmitted 직후에 호출해야 한다.
	if (VisualDistances.Num() != CellCount ||
		!FMath::IsNearlyEqual(CapturedBudget, Budget, 0.1f))
	{
		return false;
	}

	// 이 파동이 사용할 거리 데이터를 복사한다.
	TArray<float> Distances;
	Distances.Init(-1.f, CellCount);

	int32 MinX = Grid.Width;
	int32 MinY = Grid.Height;
	int32 MaxX = -1;
	int32 MaxY = -1;

	for (int32 Cell = 0; Cell < CellCount; ++Cell)
	{
		if (!Grid.IsWalkable(Cell))
		{
			continue;
		}

		const float Distance = VisualDistances[Cell];

		// 벽 등에 막혀 계산되지 않은 칸은 제외한다.
		if (!FMath::IsFinite(Distance) ||
			Distance < 0.f ||
			Distance == CatrunSoundPropagation::Unreached)
		{
			continue;
		}

		// Budget보다 큰 값도 보간에 필요하므로 보관한다.
		// 실제 파동의 최대 반지름은 기존 블루프린트가 제한한다.
		Distances[Cell] = Distance;

		const int32 X = Grid.CellX(Cell);
		const int32 Y = Grid.CellY(Cell);

		MinX = FMath::Min(MinX, X);
		MinY = FMath::Min(MinY, Y);
		MaxX = FMath::Max(MaxX, X);
		MaxY = FMath::Max(MaxY, Y);
	}

	if (MaxX < 0)
	{
		return false;
	}

	// 맵 전체가 아닌 소리가 닿은 영역만 텍스처로 만든다.
	// 바깥쪽에는 빈 칸 한 줄을 여유로 추가한다.
	const int32 StartX = MinX - 1;
	const int32 StartY = MinY - 1;
	const int32 Width = MaxX - MinX + 3;
	const int32 Height = MaxY - MinY + 3;

	// 소리 한 번에 지나치게 큰 텍스처가 만들어지는 것을 제한한다.
	if (Width > 2048 || Height > 2048)
	{
		UE_LOG(LogTemp, Warning,
			TEXT("Sound visual snapshot is too large: %d x %d"),
			Width, Height);
		return false;
	}

	// 픽셀 하나가 격자 한 칸에 해당한다.
	// R: 전파 거리
	// G: 도달 여부. 도달하면 1, 도달하지 않으면 0.
	// B: 도달한 주변 칸으로 이동할 수 있는 방향을 비트로 저장.
	// A: 해당 바닥의 소리 전파 비용 배율.
	TArray<FLinearColor> Pixels;
	Pixels.Init(
		FLinearColor(-1.f, 0.f, 0.f, 1.f),
		Width * Height);

	for (int32 Y = MinY; Y <= MaxY; ++Y)
	{
		for (int32 X = MinX; X <= MaxX; ++X)
		{
			const int32 Cell = Grid.CellIndex(X, Y);

			if (Distances[Cell] < 0.f)
			{
				continue;
			}

			uint8 OpenDirections = 0;

			// 벽에 막히지 않았고 소리가 도달한 이웃 방향을 기록한다.
			for (int32 Dir = 0;
				Dir < CatrunGrid::NumDirs;
				++Dir)
			{
				if (!Grid.IsEdgeOpen(Cell, Dir))
				{
					continue;
				}

				const int32 Neighbor = Grid.Neighbor(Cell, Dir);

				if (Distances.IsValidIndex(Neighbor) &&
					Distances[Neighbor] >= 0.f)
				{
					OpenDirections |=
						static_cast<uint8>(1u << Dir);
				}
			}

			// 맵의 격자 좌표를 잘라낸 텍스처 내부 좌표로 바꾼다.
			const int32 PixelIndex =
				(Y - StartY) * Width + (X - StartX);

			Pixels[PixelIndex] = FLinearColor(
				Distances[Cell],
				1.f,
				static_cast<float>(OpenDirections),
				Grid.CostMultiplier[Cell]);
		}
	}

	const int64 ByteCount =
		static_cast<int64>(Pixels.Num()) *
		sizeof(FLinearColor);

	const TConstArrayView64<uint8> ImageData(
		reinterpret_cast<const uint8*>(Pixels.GetData()),
		ByteCount);

	// 이 소리만 사용하는 런타임 텍스처를 새로 만든다.
	// 다음 소리가 발생해도 이 텍스처의 내용은 덮어쓰지 않는다.
	UTexture2D* Texture = UTexture2D::CreateTransient(
		Width,
		Height,
		PF_A32B32G32R32F,
		NAME_None,
		ImageData);

	if (!Texture)
	{
		return false;
	}

	// 일반 색상 그림이 아닌 숫자 데이터이므로 색상 보정을 끈다.
	// 인접 칸을 무조건 섞지 않도록 최근접 필터를 사용한다.
	// 부드러운 보간은 이후 머티리얼에서 연결 방향을 고려해 처리한다.
	Texture->SRGB = false;
	Texture->Filter = TF_Nearest;
	Texture->AddressX = TA_Clamp;
	Texture->AddressY = TA_Clamp;
	Texture->NeverStream = true;
	Texture->UpdateResource();

	// 블루프린트로 전달할 결과를 완성한다.
	Snapshot.DistanceTexture = Texture;
	Snapshot.CellSizeCm = Grid.CellSize;
	Snapshot.GridRect = FLinearColor(
		static_cast<float>(
			Grid.Origin.X + StartX * Grid.CellSize),
		static_cast<float>(
			Grid.Origin.Y + StartY * Grid.CellSize),
		Width * Grid.CellSize,
		Height * Grid.CellSize);

	return true;
}