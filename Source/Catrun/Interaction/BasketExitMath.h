#pragma once
#include "CoreMinimal.h"

namespace CatrunBasket
{
	inline int32 DirectionSector(const FVector& Direction, float CameraYaw)
	{
		const float Angle = FMath::FindDeltaAngleDegrees(CameraYaw, Direction.Rotation().Yaw);
		return (FMath::FloorToInt((Angle + 22.5f) / 45.f) % 8 + 8) % 8;
	}

	// Entry and exit share the physical open half: exact sides are allowed, the
	// hinge rear is never opened by camera-sector rounding. Aligned input retains
	// five directions; off-grid rotations may expose four physically valid keys.
	inline bool IsDirectionAllowed(const FVector& Direction, const FVector& BasketForward, float CameraYaw)
	{
		const FVector FlatDirection=Direction.GetSafeNormal2D();
		const FVector FlatForward=BasketForward.GetSafeNormal2D();
		if (FlatDirection.IsNearlyZero() || FlatForward.IsNearlyZero()
			|| FVector::DotProduct(FlatDirection,FlatForward)<-.0001f) return false;
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
