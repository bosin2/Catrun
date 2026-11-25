#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "CatrunMinimapMarkerWidget.generated.h"

enum class ECatrunMinimapGlyph : uint8 { Cat, Armor, Candle };

/** Flat translucent silhouettes. Map position and visibility stay with the presenter. */
UCLASS(Abstract, meta=(DisableNativeTick))
class CATRUN_API UCatrunMinimapMarkerWidget : public UUserWidget
{
 GENERATED_BODY()
public:
 ECatrunMinimapGlyph GetGlyph() const { return Glyph; }
protected:
 virtual TSharedRef<SWidget> RebuildWidget() override;
 virtual int32 NativePaint(const FPaintArgs& Args, const FGeometry& Geometry,
  const FSlateRect& CullingRect, FSlateWindowElementList& Elements, int32 LayerId,
  const FWidgetStyle& Style, bool bParentEnabled) const override;
 ECatrunMinimapGlyph Glyph = ECatrunMinimapGlyph::Cat;
 float Side = 22.f;
};

UCLASS(meta=(DisableNativeTick))
class CATRUN_API UCatrunMinimapCatMarker : public UCatrunMinimapMarkerWidget
{
 GENERATED_BODY()
};

UCLASS(meta=(DisableNativeTick))
class CATRUN_API UCatrunMinimapArmorMarker : public UCatrunMinimapMarkerWidget
{
 GENERATED_BODY()
public:
 UCatrunMinimapArmorMarker() { Glyph = ECatrunMinimapGlyph::Armor; Side = 20.f; }
};

UCLASS(meta=(DisableNativeTick))
class CATRUN_API UCatrunMinimapCandleMarker : public UCatrunMinimapMarkerWidget
{
 GENERATED_BODY()
public:
 UCatrunMinimapCandleMarker() { Glyph = ECatrunMinimapGlyph::Candle; Side = 18.f; }
};
