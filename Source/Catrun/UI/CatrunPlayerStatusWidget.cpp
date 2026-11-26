#include "UI/CatrunPlayerStatusWidget.h"
#include "UI/CatrunHUDStyle.h"
#include "Blueprint/WidgetBlueprintLibrary.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Components/BoxComponent.h"
#include "Components/ProgressBar.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Engine/TriggerBox.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Pawn.h"
#include "LevelFlow/CatrunElevatorTransition.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "Player/CatrunSprintComponent.h"
#include "Rendering/DrawElements.h"
#include "Settings/CatrunInputBindings.h"
#include "Settings/CatrunSettingsSubsystem.h"
#include "Sound/CatrunBellComponent.h"
#include "Sound/CatrunNotice.h"

namespace
{
 // The stage title arrives shortly after control returns. Waiting avoids flashing the clock underneath it.
 constexpr float ClockEntryDelay = .9f;
 constexpr float ClockFadeSeconds = .3f;
 constexpr float ClockDockSeconds = .35f;
 constexpr float OverlayScanInterval = .1f;
 constexpr float TimeLimitNoticeRadius = 420.f;
 const FName StageTitleClass(TEXT("WBP_StageTitle_C"));
 const FName TutorialHintClass(TEXT("WBP_Tutorial_KeyHint_C"));

 bool ContainsPawn(const ATriggerBox* Volume, const APawn& Pawn)
 {
  const auto* Box = Volume ? Cast<UBoxComponent>(Volume->GetCollisionComponent()) : nullptr;
  if (!Box) return false;
  const FVector Local = Box->GetComponentTransform().InverseTransformPosition(Pawn.GetActorLocation()).GetAbs();
  const FVector Extent = Box->GetUnscaledBoxExtent();
  return Local.X <= Extent.X && Local.Y <= Extent.Y && Local.Z <= Extent.Z;
 }

 // The tutorial card is authored with the default keys. Keep that artwork and replace only rebound captions.
 void LabelKeyHint(UUserWidget& Hint)
 {
  struct FLabel { const TCHAR* Name; ECatrunInputSlot Slot; };
  static const FLabel Labels[] = {
   {TEXT("Move_W"), ECatrunInputSlot::Forward}, {TEXT("Move_S"), ECatrunInputSlot::Back},
   {TEXT("Move_A"), ECatrunInputSlot::Left}, {TEXT("Move_D"), ECatrunInputSlot::Right},
   {TEXT("Run_W"), ECatrunInputSlot::Forward}, {TEXT("Run_S"), ECatrunInputSlot::Back},
   {TEXT("Run_A"), ECatrunInputSlot::Left}, {TEXT("Run_D"), ECatrunInputSlot::Right},
   {TEXT("Sneak_W"), ECatrunInputSlot::Forward}, {TEXT("Sneak_S"), ECatrunInputSlot::Back},
   {TEXT("Sneak_A"), ECatrunInputSlot::Left}, {TEXT("Sneak_D"), ECatrunInputSlot::Right},
   {TEXT("Run_Modifier"), ECatrunInputSlot::Run}, {TEXT("Sneak_Modifier"), ECatrunInputSlot::Sneak},
   {TEXT("Bell"), ECatrunInputSlot::Bell}, {TEXT("Hide"), ECatrunInputSlot::Interact}
  };
  const FCatrunKeyboardBindings Defaults;
  for (const FLabel& Item : Labels)
  {
   const FKey Key = UCatrunInputBindings::GetEffectiveKey(Item.Slot);
   if (Key == Defaults.Get(Item.Slot)) continue;
   auto* Caption = Cast<UTextBlock>(Hint.GetWidgetFromName(FName(FString(TEXT("KeyLabel_")) + Item.Name)));
   if (!Caption) continue;
   const FText Name = Key.GetDisplayName(false);
   Caption->SetText(Name);
   // Single-letter caps keep the authored square; longer names widen their own cap.
   if (Name.ToString().Len() > 2)
    if (auto* Cap = Cast<USizeBox>(Hint.GetWidgetFromName(FName(FString(TEXT("KeySize_")) + Item.Name))))
    {
     Cap->ClearWidthOverride();
     Cap->SetMinDesiredWidth(78.f);
    }
  }
 }
}

void UCatrunPlayerStatusWidget::NativePreConstruct()
{
 Super::NativePreConstruct();
 SetIsFocusable(false);
 SetVisibility(ESlateVisibility::HitTestInvisible);
 SetRenderOpacity(IsDesignTime() ? 1.f : 0.f);
 // Preserve authored BP bindings, but retire the entire numeric card.
 if (UWidget* Card = GetWidgetFromName(TEXT("StatusContent")))
  Card->SetVisibility(ESlateVisibility::Collapsed);
 for (UTextBlock* Label : {StaminaText.Get(), BellRemainingText.Get(), BellReasonText.Get(), ClockText.Get()})
  if (Label) { Label->SetText(FText::GetEmpty()); Label->SetVisibility(ESlateVisibility::Collapsed); }
}

void UCatrunPlayerStatusWidget::NativeConstruct()
{
 Super::NativeConstruct();
 bShowStatus = false;
 SetRenderOpacity(0.f);
 ClockHoldSeconds = ClockEntryDelay;
 ClockOpacity = 0.f;
 ClockDock = 0.f;
 OverlayScanSeconds = 0.f;
 Elevators.Reset();
 if (UWorld* World = GetWorld())
  for (TActorIterator<ACatrunElevatorTransition> It(World); It; ++It)
   if (!It->bArrivalSide) Elevators.Add(*It);
 TutorialExit.Reset();
 bTimeLimitAnnounced = false;
 if (UWorld* World = GetWorld(); World && UWorld::RemovePIEPrefix(World->GetOutermost()->GetName()).EndsWith(TEXT("/Tutorial")))
  for (TActorIterator<AActor> It(World); It; ++It)
   if (It->ActorHasTag(TEXT("CatrunMapExit")) || It->GetClass()->GetFName() == TEXT("BP_LevelExit_C"))
   {
    TutorialExit = *It;
    break;
   }
}

void UCatrunPlayerStatusWidget::AnnounceTimeLimit(const APawn& Pawn)
{
 // The untimed tutorial never mentions that the next area counts down. One line, once, on the way out.
 const AActor* Exit = TutorialExit.Get();
 if (bTimeLimitAnnounced || !Exit || FVector::Dist2D(Pawn.GetActorLocation(), Exit->GetActorLocation()) > TimeLimitNoticeRadius) return;
 if (auto* Notice = UCatrunNoticeSubsystem::Get(this))
 {
  bTimeLimitAnnounced = true;
  Notice->ShowNotice(NSLOCTEXT("Catrun", "NextAreaTimed", "다음 구역부터 제한 시간이 있습니다."), 4.f, ECatrunNoticePolicy::DeferredGameplay);
 }
}

void UCatrunPlayerStatusWidget::ScanOverlays()
{
 bClockSpaceTaken = false;
 TArray<UUserWidget*> Widgets;
 UWidgetBlueprintLibrary::GetAllWidgetsOfClass(this, Widgets, UUserWidget::StaticClass(), true);
 for (UUserWidget* Widget : Widgets)
 {
  const FName Class = Widget->GetClass()->GetFName();
  if ((Class != StageTitleClass && Class != TutorialHintClass) || Widget->GetOwningPlayer() != GetOwningPlayer()) continue;
  bClockSpaceTaken = true;
  if (Class == TutorialHintClass && LabelledKeyHint != Widget)
  {
   LabelledKeyHint = Widget;
   LabelKeyHint(*Widget);
  }
 }
}

void UCatrunPlayerStatusWidget::UpdateClockPlacement(const APawn* Pawn, float DeltaSeconds)
{
 OverlayScanSeconds -= DeltaSeconds;
 if (OverlayScanSeconds <= 0.f)
 {
  OverlayScanSeconds = OverlayScanInterval;
  ScanOverlays();
 }
 bool bDock = false;
 for (const auto& Entry : Elevators)
  if (const auto* Elevator = Entry.Get(); Elevator && Pawn)
   bDock |= ContainsPawn(Elevator->WarehouseVolume, *Pawn) || ContainsPawn(Elevator->CabinVolume, *Pawn);
 if (!bShowStatus)
 {
  // A cinematic returns to the correct place without replaying the move.
  ClockDock = bDock ? 1.f : 0.f;
  return;
 }
 ClockHoldSeconds = FMath::Max(0.f, ClockHoldSeconds - DeltaSeconds);
 const float Target = bClockSpaceTaken || ClockHoldSeconds > 0.f ? 0.f : 1.f;
 ClockOpacity = FMath::FInterpConstantTo(ClockOpacity, Target, DeltaSeconds, 1.f / ClockFadeSeconds);
 ClockDock = FMath::FInterpConstantTo(ClockDock, bDock ? 1.f : 0.f, DeltaSeconds, 1.f / ClockDockSeconds);
}

void UCatrunPlayerStatusWidget::NativeTick(const FGeometry& Geometry, float DeltaSeconds)
{
 Super::NativeTick(Geometry, DeltaSeconds);
 const APawn* Pawn = GetOwningPlayerPawn();
 const auto* Flow = UCatrunLevelFlowSubsystem::Get(this);
 const auto* Options = GetWorld() ? GetWorld()->GetSubsystem<UCatrunSettingsSubsystem>() : nullptr;
 bShowStatus = Pawn && Flow && !(Options && Options->GetCurrentSettingsWidget())
  && !UCatrunLevelFlowLibrary::ShouldHideGameplayHUD(this);
 // A collapsed viewport wrapper cannot tick to restore itself after a cinematic.
 SetRenderOpacity(bShowStatus ? 1.f : 0.f);
 UpdateClockPlacement(Pawn, DeltaSeconds);
 if (!bShowStatus) return;
 AnnounceTimeLimit(*Pawn);
 const auto* Sprint = Pawn->FindComponentByClass<UCatrunSprintComponent>();
 StaminaFraction = Sprint ? FMath::Clamp(Sprint->GetStaminaNormalized(), 0.f, 1.f) : 0.f;
 bExhausted = Sprint && Sprint->IsExhausted();
 if (StaminaBar) StaminaBar->SetPercent(StaminaFraction);
 const auto* Bell = Pawn->FindComponentByClass<UCatrunBellComponent>();
 bBellBlocked = !Bell;
 BellFraction = 0.f;
 if (Bell)
 {
  const auto State = Bell->GetBellStatus();
  bBellBlocked = !State.bCanRing && State.Reason != ECatrunBellBlockReason::Cooldown;
  BellFraction = State.CooldownSeconds > 0.f ?
   FMath::Clamp(1.f - State.RemainingSeconds / State.CooldownSeconds, 0.f, 1.f) : 1.f;
 }
 if (BellProgress) BellProgress->SetPercent(BellFraction);
 const auto Clock = Flow->GetStageClockState();
 bTimed = Clock.bTimed;
 TimeFraction = Clock.BudgetSeconds > 0.f ? FMath::Clamp(Clock.RemainingSeconds / Clock.BudgetSeconds, 0.f, 1.f) : 1.f;
 ClockWarningFraction = Clock.WarningFraction;
 ClockUrgentFraction = Clock.UrgentFraction;
}

int32 UCatrunPlayerStatusWidget::NativePaint(const FPaintArgs& Args, const FGeometry& Geometry,
 const FSlateRect& CullingRect, FSlateWindowElementList& Elements, int32 LayerId,
 const FWidgetStyle& Style, bool bParentEnabled) const
{
 int32 Layer = Super::NativePaint(Args, Geometry, CullingRect, Elements, LayerId, Style, bParentEnabled);
 if (!bShowStatus && !IsDesignTime()) return Layer;
 using namespace CatrunHUDStyle;
 const FVector2D Size = Geometry.GetLocalSize();
 const float Scale = FMath::Min(1.f, FMath::Min(Size.X / 960.f, Size.Y / 540.f));
 if (Scale <= 0.f) return Layer;
 const FVector2D Space = Size / Scale;
 const FPaintGeometry Paint = Geometry.ToPaintGeometry(Space, FSlateLayoutTransform(Scale));
 const FLinearColor BaseTint = Style.GetColorAndOpacityTint() * GetColorAndOpacity();
 FLinearColor Tint = BaseTint;
 auto Path = [&](const TArray<FVector2D>& Points, FLinearColor Color, float Width = 1.5f)
 {
  FSlateDrawElement::MakeLines(Elements, ++Layer, Paint, Points, ESlateDrawEffect::None, Color * Tint, true, Width);
 };
 auto Box = [&](FVector2D Position, FVector2D Extent, float Radius, FLinearColor Fill)
 {
  const FSlateRoundedBoxBrush Brush(FLinearColor::White, Radius);
  FSlateDrawElement::MakeBox(Elements, ++Layer,
   Geometry.ToPaintGeometry(Extent, FSlateLayoutTransform(Scale, Position * Scale)), &Brush,
   ESlateDrawEffect::None, Fill * Tint);
 };
 auto Disc = [&](FVector2D Center, float Radius, FLinearColor Fill)
 { Box(Center - FVector2D(Radius), FVector2D(Radius * 2.f), Radius, Fill); };
 auto Radial = [](FVector2D Center, float Radius, float Turns)
 {
  const float Angle = Turns * 2.f * PI - PI / 2.f;
  return Center + FVector2D(FMath::Cos(Angle), FMath::Sin(Angle)) * Radius;
 };
 auto Arc = [&](FVector2D Center, float Radius, float Fraction, FLinearColor Color, float Width)
 {
  if (Fraction <= 0.f) return;
  TArray<FVector2D> Points;
  const int32 Count = FMath::Max(2, FMath::CeilToInt(96.f * Fraction));
  Points.Reserve(Count + 1);
  for (int32 I = 0; I <= Count; ++I) Points.Add(Radial(Center, Radius, Fraction * I / Count));
  Path(Points, Color, Width);
 };

 // One pointed finial, a double bezel and a lance-shaped hand, without scrollwork.
 // The warehouse camera frames the lift at the top center, where the map corner is already empty.
 const float Dock = FMath::SmoothStep(0.f, 1.f, ClockDock);
 const FVector2D Clock(FMath::Lerp(Space.X * .5f, Space.X - 118.f, Dock), 100.f);
 Tint.A *= ClockOpacity;
 if (ClockOpacity > 0.f)
 {
 Path({Clock + FVector2D(-9,-72), Clock + FVector2D(0,-84), Clock + FVector2D(9,-72)}, Brass, 2.f);
 Disc(Clock + FVector2D(0,3), 69.f, FLinearColor(0,0,0,.35f));
 Disc(Clock, 68.f, Rim);
 Disc(Clock, 65.f, Ink);
 const FLinearColor TimeColor = !bTimed ? Brass : TimeFraction <= ClockUrgentFraction ? Urgent
  : TimeFraction <= ClockWarningFraction ? Warning : Brass;
 const bool bTimeLow = bTimed && TimeFraction <= ClockWarningFraction;
 const bool bTimeUrgent = bTimed && TimeFraction <= ClockUrgentFraction;
 // A short arc alone is easy to miss, so the whole inner bezel takes the warning color. No motion, no new threshold.
 Disc(Clock, 60.f, TimeColor);
 Disc(Clock, 57.f, Parchment);
 for (int32 I = 0; I < 12; ++I)
  Path({Radial(Clock, I % 3 == 0 ? 43.f : 46.f, I / 12.f), Radial(Clock, 50.f, I / 12.f)}, Rim, I % 3 == 0 ? 2.4f : 1.5f);
 if (bTimed)
 {
  if (bTimeLow) Arc(Clock, 65.f, 1.f, TimeColor.CopyWithNewOpacity(.4f), 3.f);
  Arc(Clock, 65.f, TimeFraction, TimeColor, bTimeUrgent ? 6.f : bTimeLow ? 4.5f : 2.5f);
  // One revolution over the stage budget. The rim depletes as the hand approaches midnight.
  const float Turn = 1.f - TimeFraction;
  const FVector2D Tip = Radial(Clock, 39.f, Turn);
  const FVector2D Side = Radial(FVector2D::ZeroVector, 3.f, Turn + .25f);
  const FVector2D Base = Radial(Clock, 26.f, Turn);
  if (bTimeUrgent)
  {
   // The remaining sweep is also filled in, so the state does not rely on hue alone.
   TArray<FVector2D> Sweep;
   for (int32 I = 0; I <= 24; ++I) Sweep.Add(Radial(Clock, 53.f, Turn + TimeFraction * I / 24.f));
   Path(Sweep, Urgent, 6.f);
  }
  Path({Radial(Clock, -9.f, Turn), Tip}, Ink, 2.6f);
  Path({Base + Side, Tip, Base - Side}, Ink, 1.5f);
  Path({Clock, Radial(Clock, 25.f, Turn / 12.f + .66f)}, Rim, 3.f);
  Disc(Clock, 4.5f, Ink);
  Disc(Clock, 1.8f, Brass);
 }
 else
 {
  // Untimed tutorial: stationary crescent, no false countdown.
  Disc(Clock, 16.f, Rim);
  Disc(Clock + FVector2D(7,-5), 14.f, Parchment);
 }
 }
 Tint = BaseTint;

 const float Bottom = Space.Y - 40.f;
 const FVector2D Gauge(40.f, Bottom - 192.f);
 Box(Gauge + FVector2D(-2,-2), FVector2D(28,196), 7.f, FLinearColor(0,0,0,.3f));
 Box(Gauge, FVector2D(24,192), 5.f, Brass);
 Box(Gauge + FVector2D(2), FVector2D(20,188), 3.f, Ink);
 const float FillHeight = 180.f * StaminaFraction;
 if (FillHeight > .1f)
  Box(Gauge + FVector2D(6,186.f - FillHeight), FVector2D(12,FillHeight), FMath::Min(2.f, FillHeight * .5f), bExhausted ? Urgent : Sage);
 Path({Gauge + FVector2D(-4,-18), Gauge + FVector2D(12,-27), Gauge + FVector2D(28,-18)}, Brass, 2.f);
 if (bExhausted)
  Path({Gauge + FVector2D(7,183), Gauge + FVector2D(17,183)}, Urgent, 2.f);

 const FVector2D Bell(116.f, Bottom - 39.f);
 Disc(Bell, 40.f, FLinearColor(0,0,0,.24f));
 Disc(Bell, 36.f, Ink);
 Arc(Bell, 38.f, 1.f, Rim, 2.f);
 const FLinearColor BellInk = bBellBlocked ? Rim : Brass;
 Arc(Bell, 38.f, BellFraction, BellInk, 3.5f);
 // Round collar bell: loop, equator and keyhole slit.
 Arc(Bell + FVector2D(0,-19), 6.f, 1.f, BellInk, 2.f);
 Disc(Bell + FVector2D(0,3), 17.f, BellInk);
 Path({Bell + FVector2D(-14,0), Bell + FVector2D(-7,-3), Bell + FVector2D(0,-4),
  Bell + FVector2D(7,-3), Bell + FVector2D(14,0)}, Ink, 2.f);
 Disc(Bell + FVector2D(0,7), 2.6f, Ink);
 Path({Bell + FVector2D(0,8), Bell + FVector2D(0,17)}, Ink, 2.f);
 if (bBellBlocked)
  Path({Bell + FVector2D(-19,21), Bell + FVector2D(19,-21)}, Parchment, 2.f);
 return Layer;
}
