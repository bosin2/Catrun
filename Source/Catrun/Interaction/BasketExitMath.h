#pragma once
#include "CoreMinimal.h"

namespace CatrunBasket
{
	inline int32 DirectionSector(const FVector& Direction, float CameraYaw)
	{
		const float Angle = FMath::FindDeltaAngleDegrees(CameraYaw, Direction.Rotation().Yaw);
		return (FMath::FloorToInt((Angle + 22.5f) / 45.f) % 8 + 8) % 8;
	}

	// The loose cover has no closed rear. Geometry, not a hinge sector, blocks travel.
	inline bool IsDirectionAllowed(const FVector& Direction, const FVector& BasketForward, float CameraYaw)
	{
		return !Direction.ContainsNaN() && !Direction.GetSafeNormal2D().IsNearlyZero();
	}

	inline FVector SnapDirection(const FVector& Direction, const FVector& ReferenceForward)
	{
		if (Direction.GetSafeNormal2D().IsNearlyZero()) return FVector::ZeroVector;
		const float Yaw = ReferenceForward.GetSafeNormal2D().Rotation().Yaw;
		return FRotator(0, Yaw + DirectionSector(Direction, Yaw)*45.f, 0).Vector();
	}

	// One key per camera direction. Chords retain a held selection or prefer the
	// forward/back axis; they never create a fifth diagonal input requirement.
	inline FVector SelectDirection(float CameraYaw, float ForwardAxis, float RightAxis,
		const FVector& Previous, const FVector& BasketForward)
	{
		const FRotationMatrix Camera(FRotator(0, CameraYaw, 0));
		if (FMath::IsNearlyZero(ForwardAxis) && FMath::IsNearlyZero(RightAxis)) return Previous;
		// The actual exit follows the screen/camera axes exactly, never the basket axes.
		const FVector F = Camera.GetUnitAxis(EAxis::X)*FMath::Sign(ForwardAxis);
		const FVector R = Camera.GetUnitAxis(EAxis::Y)*FMath::Sign(RightAxis);
		if (!FMath::IsNearlyZero(ForwardAxis) && !FMath::IsNearlyZero(RightAxis))
		{
			if (Previous.Equals(F,.001) || Previous.Equals(R,.001)) return Previous;
			return FMath::Abs(RightAxis)>FMath::Abs(ForwardAxis) ? R : F;
		}
		return FMath::IsNearlyZero(ForwardAxis) ? R : F;
	}

	inline FVector ArcPoint(const FVector& Start, const FVector& End, float Height, float T)
	{
		const FVector Control = (Start + End) * .5 + FVector(0, 0, Height);
		return FMath::Lerp(FMath::Lerp(Start, Control, T), FMath::Lerp(Control, End, T), T);
	}
}
