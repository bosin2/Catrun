#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "CatrunBellIndicatorWidget.generated.h"

/** Asset-free bell icon. Timing, visibility and designer overrides belong to the bell component. */
UCLASS(meta = (DisableNativeTick))
class CATRUN_API UCatrunBellIndicatorWidget : public UUserWidget
{
	GENERATED_BODY()

protected:
	virtual int32 NativePaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry,
		const FSlateRect& MyCullingRect, FSlateWindowElementList& OutDrawElements,
		int32 LayerId, const FWidgetStyle& InWidgetStyle, bool bParentEnabled) const override;
};
