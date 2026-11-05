#include "CatrunBellIndicatorWidget.h"

#include "Rendering/DrawElementTypes.h"

int32 UCatrunBellIndicatorWidget::NativePaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry,
	const FSlateRect& MyCullingRect, FSlateWindowElementList& OutDrawElements,
	int32 LayerId, const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const
{
	const int32 IconLayer = Super::NativePaint(Args, AllottedGeometry, MyCullingRect,
		OutDrawElements, LayerId, InWidgetStyle, bParentEnabled) + 1;
	const FVector2D Size = AllottedGeometry.GetLocalSize();
	const float Scale = FMath::Min(Size.X, Size.Y) / 56.f;
	if (Scale <= 0.f) return IconLayer;

	// Fixed paths allocate once, then scale through the paint geometry (no per-frame point arrays).
	static const TArray<FVector2D> Paths[] = {
		{ {26,14}, {22,16}, {19,20}, {18,28}, {17,33}, {14,36}, {14,38},
		  {42,38}, {42,36}, {39,33}, {38,28}, {37,20}, {34,16}, {30,14}, {26,14} },
		{ {26,14}, {26,11}, {28,9}, {30,11}, {30,14} },
		{ {24,42}, {25,45}, {28,46}, {31,45}, {32,42} },
		{ {12,19}, {9,24}, {9,30}, {12,34} },
		{ {6,15}, {3,23}, {3,31}, {6,38} },
		{ {44,19}, {47,24}, {47,30}, {44,34} },
		{ {50,15}, {53,23}, {53,31}, {50,38} }
	};
	const FPaintGeometry Geometry = AllottedGeometry.ToPaintGeometry(FVector2D(56.f, 56.f),
		FSlateLayoutTransform(Scale, (Size - FVector2D(56.f * Scale)) * .5f));
	// SObjectWidget passes the parent style to NativePaint; include this UserWidget's tint too.
	const FLinearColor Tint = InWidgetStyle.GetColorAndOpacityTint() * GetColorAndOpacity();
	for (const TArray<FVector2D>& Path : Paths)
	{
		FSlateDrawElement::MakeLines(OutDrawElements, IconLayer, Geometry, Path,
			ESlateDrawEffect::None, Tint, true, 2.2f);
	}
	return IconLayer;
}
