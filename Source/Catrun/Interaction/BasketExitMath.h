#pragma once
#include "CoreMinimal.h"

namespace CatrunBasket
{
	inline int32 DirectionSector(const FVector& Direction, float CameraYaw)
	{
		const float Angle = FMath::FindDeltaAngleDegrees(CameraYaw, Direction.Rotation().Yaw);
		return (FMath::FloorToInt((Angle + 22.5f) / 45.f) % 8 + 8) % 8;
	}

	// 실제 열린 면에 가까운 키보드 방향 5개를 허용하고 반대편 3개를 막는다.
	// 단순 내적 판정은 바구니가 비스듬하면 옆 방향까지 잘려 4개만 허용될 수 있다.
	inline bool IsDirectionAllowed(const FVector& Direction, const FVector& BasketForward, float CameraYaw)
	{
		if (Direction.IsNearlyZero() || BasketForward.IsNearlyZero()) return false;
		const int32 Difference = FMath::Abs(DirectionSector(Direction, CameraYaw)
			- DirectionSector(BasketForward, CameraYaw));
		return FMath::Min(Difference, 8 - Difference) <= 2;
	}

	// 카메라 기준 WASD. 키를 놓거나 뒤쪽 방향을 누르면 마지막 선택을 유지한다.
	inline FVector SelectDirection(float CameraYaw, float ForwardAxis, float RightAxis,
		const FVector& Previous, const FVector& BasketForward)
	{
		const FRotationMatrix Camera(FRotator(0, CameraYaw, 0));
		const FVector Desired = (Camera.GetUnitAxis(EAxis::X) * ForwardAxis
			+ Camera.GetUnitAxis(EAxis::Y) * RightAxis).GetSafeNormal2D();
		return IsDirectionAllowed(Desired, BasketForward, CameraYaw)
			? Desired : Previous;
	}

	inline FVector ArcPoint(const FVector& Start, const FVector& End, float Height, float T)
	{
		const FVector Control = (Start + End) * .5 + FVector(0, 0, Height);
		return FMath::Lerp(FMath::Lerp(Start, Control, T), FMath::Lerp(Control, End, T), T);
	}
}
