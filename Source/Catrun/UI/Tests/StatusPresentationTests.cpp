#if WITH_DEV_AUTOMATION_TESTS
#include "UI/CatrunPlayerStatusWidget.h"
#include "Components/TextBlock.h"
#include "Engine/World.h"
#include "Engine/TextureRenderTarget2D.h"
#include "HAL/FileManager.h"
#include "ImageUtils.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/Paths.h"
#include "Misc/ScopeExit.h"
#include "Slate/WidgetRenderer.h"
#include "Blueprint/WidgetBlueprintLibrary.h"
#include "Components/ProgressBar.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/Pawn.h"
#include "HAL/PlatformTime.h"
#include "Player/CatrunSprintComponent.h"
#include "Sound/CatrunBellComponent.h"
#include "Tests/AutomationCommon.h"
#include "UnrealClient.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunStatusPresentationTest, "Catrun.UI.Status.MinimalPresentation",
 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCatrunStatusPresentationTest::RunTest(const FString&)
{
 UClass* Class = LoadClass<UCatrunPlayerStatusWidget>(nullptr,
  TEXT("/Game/UI/Gameplay/WBP_PlayerStatus.WBP_PlayerStatus_C"));
 if (!TestNotNull(TEXT("Production status Blueprint"), Class)) return false;
 const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(false)
  .CreateNavigation(false).CreateAISystem(false);
 UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
 ON_SCOPE_EXIT { World->DestroyWorld(false); };
 auto* Widget = CreateWidget<UCatrunPlayerStatusWidget>(World, Class);
 if (!TestNotNull(TEXT("Production status instance"), Widget)) return false;
 const auto Slate = Widget->TakeWidget();
 Slate->SetCanTick(false);
 TestFalse(TEXT("HUD cannot take gameplay focus"), Widget->IsFocusable());
 for (const TCHAR* Name : {TEXT("StaminaText"), TEXT("BellRemainingText"), TEXT("BellReasonText"), TEXT("ClockText")})
 {
  const auto* Label = Cast<UTextBlock>(Widget->GetWidgetFromName(Name));
  if (TestNotNull(Name, Label))
  {
   TestTrue(FString(Name) + TEXT(" has no numeric or status copy"), Label->GetText().IsEmpty());
   TestEqual(FString(Name) + TEXT(" is collapsed"), Label->GetVisibility(), ESlateVisibility::Collapsed);
  }
 }
 const auto* Card = Widget->GetWidgetFromName(TEXT("StatusContent"));
 if (TestNotNull(TEXT("Legacy card"), Card))
  TestEqual(TEXT("Legacy card and titles are not drawn"), Card->GetVisibility(), ESlateVisibility::Collapsed);
 if (!FParse::Param(FCommandLine::Get(), TEXT("CatrunHUDRender"))) return true;

 const FString Directory = FPaths::ProjectSavedDir() / TEXT("HUDDesign20261125");
 IFileManager::Get().MakeDirectory(*Directory, true);
 FWidgetRenderer Renderer(true, true);
 Widget->SetRenderOpacity(1.f);
 Widget->bShowStatus = true;
 Widget->bTimed = true;
 struct FPhase { const TCHAR* Name; float Stamina; float Bell; float Time; bool Blocked; bool Timed; FVector2D Size; };
 const FPhase Phases[] = {
  {TEXT("ready"), 1.f, 1.f, .72f, false, true, {1920,1080}},
  {TEXT("cooldown"), .55f, .38f, .72f, false, true, {1920,1080}},
  {TEXT("urgent-blocked"), 0.f, 1.f, .08f, true, true, {1920,1080}},
  {TEXT("tutorial"), 1.f, 1.f, 1.f, false, false, {1920,1080}},
  {TEXT("small"), .55f, .38f, .72f, false, true, {960,540}},
  {TEXT("ultrawide"), .55f, .38f, .72f, false, true, {2560,1080}}
 };
 FImage Ready;
 for (const FPhase& Phase : Phases)
 {
  Widget->StaminaFraction = Phase.Stamina;
  Widget->BellFraction = Phase.Bell;
  Widget->TimeFraction = Phase.Time;
  Widget->bBellBlocked = Phase.Blocked;
  Widget->bExhausted = Phase.Stamina == 0.f;
  Widget->bTimed = Phase.Timed;
  FImage Pixels;
  auto* Target = Renderer.DrawWidget(Slate, Phase.Size);
  if (!TestTrue(TEXT("Read actual Slate pixels"), FImageUtils::GetRenderTargetImage(Target, Pixels))) return false;
  TestTrue(TEXT("Write actual widget render"), FImageUtils::SaveImageByExtension(*(Directory / FString(Phase.Name) + TEXT(".png")), Pixels));
  if (FString(Phase.Name) == TEXT("ready")) Ready = MoveTemp(Pixels);
  if (FString(Phase.Name) == TEXT("cooldown"))
  {
   TestTrue(TEXT("Resource state changes actual rendered pixels"), Ready.RawData != Pixels.RawData);
   // Clock and central gameplay must remain identical while only stamina and bell change.
   const auto A = Ready.AsBGRA8();
   const auto B = Pixels.AsBGRA8();
   int32 OutsideChanges = 0, ResourceChanges = 0;
   for (int32 Y = 0; Y < 1080; ++Y)
    for (int32 X = 0; X < 1920; ++X)
     if (A[Y * 1920 + X] != B[Y * 1920 + X])
      (X < 180 && Y > 800 ? ResourceChanges : OutsideChanges)++;
   TestTrue(TEXT("Resource changes are visible in the lower-left"), ResourceChanges > 100);
   TestEqual(TEXT("Resource animation does not disturb the clock or gameplay area"), OutsideChanges, 0);
  }
 }
 Widget->bShowStatus = false;
 FImage Hidden;
 auto* Target = Renderer.DrawWidget(Slate, FVector2D(1920,1080));
 if (TestTrue(TEXT("Read hidden HUD"), FImageUtils::GetRenderTargetImage(Target, Hidden)))
 {
  int32 Visible = 0;
  for (const FColor Pixel : Hidden.AsBGRA8()) Visible += Pixel.A != 0;
  TestEqual(TEXT("Presentation suppression leaves no status pixels"), Visible, 0);
 }
 return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunStatusLiveTest, "Catrun.UI.Status.LiveStage",
 EAutomationTestFlags::ClientContext | EAutomationTestFlags::NonNullRHI | EAutomationTestFlags::EngineFilter)

bool FCatrunStatusLiveTest::RunTest(const FString&)
{
 const double Started = FPlatformTime::Seconds();
 AddCommand(new FFunctionLatentCommand([this, Started, ReadyAt = 0.]() mutable
 {
  auto* World = AutomationCommon::GetAnyGameWorld();
  auto* PC = World ? World->GetFirstPlayerController() : nullptr;
  TArray<UUserWidget*> Widgets;
  if (PC) UWidgetBlueprintLibrary::GetAllWidgetsOfClass(PC, Widgets, UCatrunPlayerStatusWidget::StaticClass(), true);
  UCatrunPlayerStatusWidget* HUD = Widgets.Num() == 1 ? Cast<UCatrunPlayerStatusWidget>(Widgets[0]) : nullptr;
  if (!HUD || HUD->GetRenderOpacity() < .99f || HUD->GetCachedGeometry().GetLocalSize().X < 900.)
  {
   if (FPlatformTime::Seconds() - Started < 120.) return false;
   AddError(TEXT("Stage did not present its live status HUD before timeout"));
   return true;
  }
  if (ReadyAt == 0.) ReadyAt = FPlatformTime::Seconds();
  if (FPlatformTime::Seconds() - ReadyAt < 3.) return false;
  TestEqual(TEXT("Exactly one live status HUD"), Widgets.Num(), 1);
  APawn* Pawn = PC->GetPawn();
  const auto* Sprint = Pawn ? Pawn->FindComponentByClass<UCatrunSprintComponent>() : nullptr;
  const auto* Bell = Pawn ? Pawn->FindComponentByClass<UCatrunBellComponent>() : nullptr;
  const auto* StaminaBar = Cast<UProgressBar>(HUD->GetWidgetFromName(TEXT("StaminaBar")));
  const auto* BellBar = Cast<UProgressBar>(HUD->GetWidgetFromName(TEXT("BellProgress")));
  if (TestTrue(TEXT("Live gameplay resource owners exist"), Sprint && Bell && StaminaBar && BellBar))
  {
   TestTrue(TEXT("HUD samples live stamina"), FMath::IsNearlyEqual(StaminaBar->GetPercent(), Sprint->GetStaminaNormalized(), .01f));
   const auto Status = Bell->GetBellStatus();
   const float Expected = Status.CooldownSeconds > 0.f ? 1.f - Status.RemainingSeconds / Status.CooldownSeconds : 1.f;
   TestTrue(TEXT("HUD samples live bell cooldown"), FMath::IsNearlyEqual(BellBar->GetPercent(), Expected, .03f));
  }
  for (const TCHAR* Name : {TEXT("StaminaText"), TEXT("BellRemainingText"), TEXT("ClockText"), TEXT("BellReasonText")})
  {
   const auto* Text = Cast<UTextBlock>(HUD->GetWidgetFromName(Name));
   TestTrue(FString(Name) + TEXT(" remains empty and hidden during gameplay"), Text && Text->GetText().IsEmpty() && !Text->IsVisible());
  }
  const FString Directory = FPaths::ProjectSavedDir() / TEXT("HUDDesign20261125");
  IFileManager::Get().MakeDirectory(*Directory, true);
  FScreenshotRequest::RequestScreenshot(Directory / TEXT("Stage1-live.png"), true, false);
  return true;
 }));
 AddCommand(new FWaitLatentCommand(2.f));
 return true;
}
#endif
