#include "UI/CatrunMinimapMarkerWidget.h"
#include "UI/CatrunHUDStyle.h"
#include "Framework/Application/SlateApplication.h"
#include "Rendering/DrawElements.h"
#include "Rendering/SlateRenderer.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SSpacer.h"

TSharedRef<SWidget> UCatrunMinimapMarkerWidget::RebuildWidget()
{
 SetIsFocusable(false);
 return SNew(SBox).WidthOverride(Side).HeightOverride(Side)[SNew(SSpacer)];
}

int32 UCatrunMinimapMarkerWidget::NativePaint(const FPaintArgs& Args, const FGeometry& Geometry,
 const FSlateRect& CullingRect, FSlateWindowElementList& Elements, int32 LayerId,
 const FWidgetStyle& Style, bool bParentEnabled) const
{
 int32 Layer = Super::NativePaint(Args, Geometry, CullingRect, Elements, LayerId, Style, bParentEnabled);
 using namespace CatrunHUDStyle;
 const float Scale = Geometry.GetLocalSize().GetMin() / 32.f;
 if (Scale <= 0.f) return Layer;
 FLinearColor Tint = Style.GetColorAndOpacityTint() * GetColorAndOpacity();
 Tint.A *= .78f;
 const auto Resource = FSlateApplication::Get().GetRenderer()->GetResourceHandle(*FCoreStyle::Get().GetBrush("WhiteBrush"));
 // Flat, non-overlapping silhouettes keep the same translucency across the whole glyph.
 auto Fill = [&](const TArray<FVector2f>& Edge, FVector2f Center, FLinearColor Color)
 {
  TArray<FSlateVertex> Vertices;
  TArray<SlateIndex> Indices;
  Vertices.Reserve(Edge.Num() + 1);
  Indices.Reserve(Edge.Num() * 3);
  const FColor VertexColor = (Color * Tint).ToFColor(true);
  auto Vertex = [&](FVector2f Point)
  {
   return FSlateVertex::Make<ESlateVertexRounding::Disabled>(Geometry.GetAccumulatedRenderTransform(),
    Point * Scale, FVector2f(.5f,.5f), VertexColor);
  };
  Vertices.Add(Vertex(Center));
  for (const auto& Point : Edge) Vertices.Add(Vertex(Point));
  for (int32 I = 0; I < Edge.Num(); ++I)
  {
   Indices.Add(0); Indices.Add(I + 1); Indices.Add((I + 1) % Edge.Num() + 1);
  }
  FSlateDrawElement::MakeCustomVerts(Elements, ++Layer, Resource, Vertices, Indices, nullptr, 0, 0);
 };
 if (Glyph == ECatrunMinimapGlyph::Cat)
 {
  static const TArray<FVector2f> Head = {{4,5},{12,11},{20,11},{28,5},{28,22},{23,28},{9,28},{4,22}};
  Fill(Head, {16,19}, CatYellow);
 }
 else if (Glyph == ECatrunMinimapGlyph::Armor)
 {
  static const TArray<FVector2f> Crown = {{11,5},{21,5},{27,11},{27,14},{5,14},{5,11}};
  static const TArray<FVector2f> Guard = {{5,17},{27,17},{27,24},{22,28},{10,28},{5,24}};
  static const TArray<FVector2f> Bridge = {{15,14},{17,14},{17,17},{15,17}};
  Fill(Crown, {16,10}, ArmorRed);
  Fill(Guard, {16,22}, ArmorRed);
  Fill(Bridge, {16,15.5f}, ArmorRed);
 }
 else
 {
  static const TArray<FVector2f> Flame = {{17,3},{23,13},{25,20},{22,26},{16,29},{10,26},{7,20},{10,12}};
  Fill(Flame, {16,19}, CandleFlame);
 }
 return Layer;
}
