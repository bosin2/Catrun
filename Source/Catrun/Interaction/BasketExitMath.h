#pragma once
#include "CoreMinimal.h"

namespace CatrunBasket
{
	// BP_Cat normal walking flattens the camera forward/right vectors separately.
	inline FVector MovementDirection(const FVector2D& Input, const FRotator& CameraRotation)
	{
		const FRotationMatrix Basis(CameraRotation);
		return (Basis.GetUnitAxis(EAxis::X).GetSafeNormal2D()*Input.X
			+ Basis.GetUnitAxis(EAxis::Y).GetSafeNormal2D()*Input.Y).GetSafeNormal2D();
	}

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

	// Digital movement keys give exactly eight camera-relative exit options.
	// Slot order: F, FR, R, BR, B, BL, L, FL in movement-input space (X forward, Y right).
	constexpr int32 ExitOptionCount = 8;
	inline FVector2D ExitOptionInput(int32 Slot)
	{
		static const FVector2D Inputs[ExitOptionCount] = {
			FVector2D(1.,0.), FVector2D(1.,1.), FVector2D(0.,1.), FVector2D(-1.,1.),
			FVector2D(-1.,0.), FVector2D(-1.,-1.), FVector2D(0.,-1.), FVector2D(1.,-1.)};
		return Inputs[FMath::Clamp(Slot,0,ExitOptionCount-1)];
	}

	inline int32 ExitOptionSlot(const FVector2D& Input)
	{
		const double X = Input.X > .1 ? 1. : (Input.X < -.1 ? -1. : 0.);
		const double Y = Input.Y > .1 ? 1. : (Input.Y < -.1 ? -1. : 0.);
		for (int32 Slot=0; Slot<ExitOptionCount; ++Slot)
			if (ExitOptionInput(Slot).Equals(FVector2D(X,Y))) return Slot;
		return INDEX_NONE;
	}

	inline FVector SnapDirection(const FVector& Direction, const FVector& ReferenceForward)
	{
		if (Direction.GetSafeNormal2D().IsNearlyZero()) return FVector::ZeroVector;
		const float Yaw = ReferenceForward.GetSafeNormal2D().Rotation().Yaw;
		return FRotator(0, Yaw + DirectionSector(Direction, Yaw)*45.f, 0).Vector();
	}

	inline FVector ArcPoint(const FVector& Start, const FVector& End, float Height, float T)
	{
		const FVector Control = (Start + End) * .5 + FVector(0, 0, Height);
		return FMath::Lerp(FMath::Lerp(Start, Control, T), FMath::Lerp(Control, End, T), T);
	}
}
