#if WITH_DEV_AUTOMATION_TESTS

#include "UI/CatrunMinimapWidget.h"
#include "UI/CatrunPlayerStatusWidget.h"
#include "Blueprint/WidgetBlueprintLibrary.h"
#include "Components/CanvasPanel.h"
#include "Components/Button.h"
#include "Components/ProgressBar.h"
#include "Engine/GameViewportClient.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "Framework/Application/SlateApplication.h"
#include "Framework/Application/SlateUser.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/Pawn.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformTime.h"
#include "Kismet/GameplayStatics.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "LevelFlow/CatrunPlayHUD.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/Paths.h"
#include "Player/CatrunSprintComponent.h"
#include "Sound/CatrunBellComponent.h"
#include "Settings/CatrunSettingsSubsystem.h"
#include "Settings/CatrunSettingsWidget.h"
#include "Slate/SceneViewport.h"
#include "Tests/AutomationCommon.h"
#include "UnrealClient.h"
#include "Widgets/SViewport.h"

namespace
{
	template<class T>
	T* FindPlayerWidget(APlayerController* Player)
	{
		TArray<UUserWidget*> Found;
		UWidgetBlueprintLibrary::GetAllWidgetsOfClass(Player, Found, T::StaticClass(), true);
		for (UUserWidget* Widget : Found)
			if (Widget->GetOwningPlayer() == Player && Widget->IsInViewport())
				return CastChecked<T>(Widget);
		return nullptr;
	}

	struct FRoutedMinimap
	{
		explicit FRoutedMinimap(FAutomationTestBase& InTest) : Test(InTest) {}

		FAutomationTestBase& Test;
		FString Stage;
		FString CaptureDirectory;
		TWeakObjectPtr<APlayerController> Player;
		TWeakObjectPtr<UCatrunMinimapWidget> Map;
		TWeakObjectPtr<UWidget> Frame;
		TWeakObjectPtr<UWidget> Image;
		TWeakObjectPtr<UCanvasPanel> Markers;
		TWeakObjectPtr<UCatrunPlayHUD> HUD;
		TWeakObjectPtr<UCatrunPlayerStatusWidget> Resources;
		TWeakObjectPtr<UCatrunMinimapWidget> PreviousMap;
		FVector2D CompactCorner;
		FVector2D CompactLandmarkSize;
		FVector2D CompactMarkerSize;
		TArray<FVector2D, TInlineAllocator<4>> FarCaptureUVs;
		bool bReady = false;
		bool bSentDown = false;
		uint32 User = 0;

		UCatrunSettingsSubsystem* Settings() const { return Player->GetWorld()->GetSubsystem<UCatrunSettingsSubsystem>(); }
		UGameViewportClient* Viewport() const { return Player->GetLocalPlayer()->ViewportClient.Get(); }

		bool Bind()
		{
			UWorld* World = AutomationCommon::GetAnyGameWorld();
			if (!World || World->GetPackage()->GetName() != Stage || !World->HasBegunPlay())
				return false;
			APlayerController* PC = World->GetFirstPlayerController();
			if (!PC || !PC->GetLocalPlayer() || !PC->GetLocalPlayer()->GetSlateUser() || !World->GetGameViewport()
				|| !World->GetGameViewport()->GetGameViewport() || !World->GetGameViewport()->GetGameViewportWidget()
				|| !World->GetSubsystem<UCatrunSettingsSubsystem>() || UCatrunLevelFlowLibrary::ShouldHideGameplayHUD(PC))
				return false;
			Player = PC;
			User = PC->GetLocalPlayer()->GetSlateUser()->GetUserIndex();
			Map = FindPlayerWidget<UCatrunMinimapWidget>(PC);
			HUD = FindPlayerWidget<UCatrunPlayHUD>(PC);
			Resources = FindPlayerWidget<UCatrunPlayerStatusWidget>(PC);
			Frame = Map.IsValid() ? Map->GetWidgetFromName(TEXT("MinimapFrame")) : nullptr;
			Image = Map.IsValid() ? Map->GetWidgetFromName(TEXT("MapBackground")) : nullptr;
			Markers = Map.IsValid() ? Cast<UCanvasPanel>(Map->GetWidgetFromName(TEXT("MarkerLayer"))) : nullptr;
			if (!HUD.IsValid() || !Resources.IsValid() || !Frame.IsValid() || !Cast<UCanvasPanelSlot>(Frame->Slot)
				|| !Image.IsValid() || !Markers.IsValid() || Markers->GetChildrenCount() == 0
				|| Map->GetCachedGeometry().GetLocalSize().GetMin() < 324.)
				return false;
			bReady = true;
			Test.TestTrue(TEXT("Previous map detached on travel"), !PreviousMap.IsValid() || !PreviousMap->IsInViewport());
			Test.TestEqual(TEXT("Owning local Slate user is the keyboard user"), int32(User), FSlateApplication::Get().GetUserIndexForKeyboard());
			return true;
		}

		void Key(bool bDown, bool bRepeat = false, bool bShift = false)
		{
			auto& Slate = FSlateApplication::Get();
			const FModifierKeysState Modifiers(bShift, false, false, false, false, false, false, false, false);
			const FKeyEvent Event(EKeys::Tab, Modifiers, Slate.GetInputDeviceIdForKeyboard(), bRepeat, 9, 9, Slate.GetUserIndexForKeyboard());
			if (bDown) Slate.ProcessKeyDownEvent(Event);
			else Slate.ProcessKeyUpEvent(Event);
			bSentDown = bDown;
		}

		void Check(const TCHAR* Step, double Expected, bool bVisible = true)
		{
			const FSceneViewport* Scene = Viewport()->GetGameViewport();
			const auto& Slate = FSlateApplication::Get();
			const auto Focus = Slate.GetUserFocusedWidget(User);
			const auto Layout = CastChecked<UCanvasPanelSlot>(Frame->Slot)->GetLayout();
			const FVector2D PaintedSize = Frame->GetPaintSpaceGeometry().GetLocalSize();
			const FString Label = Stage + TEXT(" ") + Step;
			Test.AddInfo(FString::Printf(TEXT("%s | focused=%s user=%u active=%d direct=%d gameFocus=%d ignore=%d viewportTab=%d playerTab=%d tick=%d slot=%.1fx%.1f painted=%s opacity=%.2f"),
				*Label, Focus ? *Focus->ToString() : TEXT("none"), User, Slate.IsActive(), Scene->HasFocus(), Settings()->OwnsInputFocus(User),
				Viewport()->IgnoreInput(), Scene->KeyState(EKeys::Tab), Player->IsInputKeyDown(EKeys::Tab),
				Map->GetCachedWidget()->GetCanTick(), Layout.Offsets.Right, Layout.Offsets.Bottom, *PaintedSize.ToString(), Map->GetRenderOpacity()));
			Test.TestEqual(Label + TEXT(" slot width"), double(Layout.Offsets.Right), Expected);
			Test.TestEqual(Label + TEXT(" slot height"), double(Layout.Offsets.Bottom), Expected);
			Test.TestTrue(Label + TEXT(" stays in upper right"), Layout.Anchors.Minimum == FVector2D(1., 0.)
				&& Layout.Anchors.Maximum == FVector2D(1., 0.) && Layout.Alignment == FVector2D(1., 0.));
			Test.TestEqual(Label + TEXT(" opacity"), Map->GetRenderOpacity(), bVisible ? 1.f : 0.f);
			const bool bResourcesVisible = Resources.IsValid() && Resources->IsVisible() && Resources->GetRenderOpacity() > 0.f;
			Test.TestEqual(Label + TEXT(" resource readout visibility"), bResourcesVisible, bVisible);
			if (bVisible)
				Test.TestTrue(Label + TEXT(" painted frame dimensions"), PaintedSize.Equals(FVector2D(Expected), .5));
		}

		void CheckReveal(const TCHAR* Step, bool bHeld, bool bRecordCompact = false)
		{
			const FString Label = Stage + TEXT(" ") + Step;
			const FGeometry& FrameGeometry = Frame->GetPaintSpaceGeometry();
			const FGeometry& ImageGeometry = Image->GetPaintSpaceGeometry();
			const FGeometry& Surface = Markers->GetPaintSpaceGeometry();
			const FGeometry& Cat = Markers->GetChildAt(0)->GetPaintSpaceGeometry();
			const FVector2D ImageSize = ImageGeometry.GetLocalSize();
			const FVector2D SurfaceSize = Surface.GetLocalSize();
			const auto PaintedSize = [](const FGeometry& Geometry, const FVector2D& LocalSize)
			{
				const FVector2D Origin = Geometry.LocalToAbsolute(FVector2D::ZeroVector);
				return FVector2D((FVector2D(Geometry.LocalToAbsolute(FVector2D(LocalSize.X, 0.))) - Origin).Size(),
					(FVector2D(Geometry.LocalToAbsolute(FVector2D(0., LocalSize.Y))) - Origin).Size());
			};
			const FVector2D Corner = FrameGeometry.LocalToAbsolute(FVector2D(FrameGeometry.GetLocalSize().X, 0.));
			// The same .1-wide image span represents the same world distance before and after pressing Tab.
			const FVector2D LandmarkSize = PaintedSize(ImageGeometry, ImageSize * .1);
			const FVector2D MarkerSize = PaintedSize(Cat, Cat.GetLocalSize());
			Test.TestTrue(Label + TEXT(" paints the landmark and cat marker"), LandmarkSize.GetMin() > 0. && MarkerSize.GetMin() > 0.);
			Test.TestTrue(Label + TEXT(" cat stays centered"), FVector2D(Cat.LocalToAbsolute(Cat.GetLocalSize() * .5)).Equals(
				FVector2D(Surface.LocalToAbsolute(SurfaceSize * .5)), .5));
			if (bRecordCompact)
			{
				CompactCorner = Corner;
				CompactLandmarkSize = LandmarkSize;
				CompactMarkerSize = MarkerSize;
				FarCaptureUVs.Reset();
				// Pick actual capture texels just beyond each compact clip edge. Edges outside the source image are skipped.
				for (const FVector2D& Outside : { FVector2D(-.1, .5), FVector2D(1.1, .5), FVector2D(.5, -.1), FVector2D(.5, 1.1) })
				{
					const FVector2D UV = FVector2D(ImageGeometry.AbsoluteToLocal(Surface.LocalToAbsolute(Outside * SurfaceSize))) / ImageSize;
					if (UV.GetMin() >= 0. && UV.GetMax() <= 1.)
						FarCaptureUVs.Add(UV);
				}
				Test.TestTrue(Label + TEXT(" contains a fixture texel beyond the compact crop"), !FarCaptureUVs.IsEmpty());
				return;
			}

			bool bShowsFarTexel = false;
			for (const FVector2D& UV : FarCaptureUVs)
			{
				const FVector2D OnSurface = Surface.AbsoluteToLocal(ImageGeometry.LocalToAbsolute(UV * ImageSize));
				bShowsFarTexel |= OnSurface.GetMin() >= 0. && OnSurface.X <= SurfaceSize.X && OnSurface.Y <= SurfaceSize.Y;
			}
			Test.TestTrue(Label + TEXT(" fixes the painted outer right corner"), Corner.Equals(CompactCorner, .5));
			Test.TestEqual(Label + TEXT(" distant capture texel is visible only while held"), bShowsFarTexel, bHeld);
			if (bHeld)
			{
			// A 280/220 inner side and 1.45 times the coverage yield about .88 times the compact texture scale.
			Test.TestTrue(Label + TEXT(" world distance draws smaller"), LandmarkSize.Equals(CompactLandmarkSize * (280. / 220. / 1.45), .5));
				Test.TestTrue(Label + TEXT(" cat marker draws smaller"), MarkerSize.Equals(CompactMarkerSize * .85, .5));
			}
			else
			{
				Test.TestTrue(Label + TEXT(" restores the compact world scale"), LandmarkSize.Equals(CompactLandmarkSize, .5));
				Test.TestTrue(Label + TEXT(" restores the compact marker size"), MarkerSize.Equals(CompactMarkerSize, .5));
			}
		}

		void FocusViewport()
		{
			auto& Slate = FSlateApplication::Get();
			Slate.SetUserFocus(User, Viewport()->GetGameViewportWidget());
			Test.TestTrue(TEXT("Direct viewport focus fixture"), Slate.GetUserFocusedWidget(User) == Viewport()->GetGameViewportWidget());
		}

		void Capture(const TCHAR* Phase) const
		{
			if (!CaptureDirectory.IsEmpty())
				FScreenshotRequest::RequestScreenshot(CaptureDirectory / (FPaths::GetCleanFilename(Stage) + TEXT("-") + Phase + TEXT(".png")), true, false);
		}
	};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunMinimapRoutedInput, "Catrun.UI.Minimap.RoutedHoldAcrossStages",
	EAutomationTestFlags::ClientContext | EAutomationTestFlags::NonNullRHI | EAutomationTestFlags::EngineFilter)

bool FCatrunMinimapRoutedInput::RunTest(const FString&)
{
	if (!TestTrue(TEXT("A rendered game and Slate are running"), FSlateApplication::IsInitialized() && AutomationCommon::GetAnyGameWorld()))
		return false;
	const auto State = MakeShared<FRoutedMinimap>(*this);
	if (FParse::Value(FCommandLine::Get(), TEXT("CatrunMinimapCapture="), State->CaptureDirectory)
		&& !TestTrue(TEXT("Screenshot folder is writable"), IFileManager::Get().MakeDirectory(*State->CaptureDirectory, true)))
		return false;
	auto Step = [this, State](TFunction<void(FRoutedMinimap&)> Action, double WaitSeconds = .25)
	{
		// Allow the .18-second animation and subsequent Slate layout and paint to finish.
		AddCommand(new FFunctionLatentCommand([State, Action = MoveTemp(Action), WaitSeconds, First = uint64(0), Started = 0.]() mutable
		{
			if (!State->bReady) return true;
			if (!First)
			{
				First = GFrameCounter;
				Started = FPlatformTime::Seconds();
			}
			if (GFrameCounter - First < 3 || FPlatformTime::Seconds() - Started < WaitSeconds) return false;
			if (!State->Player.IsValid() || !State->Map.IsValid() || !State->Frame.IsValid() || !State->Image.IsValid()
				|| !State->Markers.IsValid() || !State->HUD.IsValid())
			{
				State->Test.AddError(TEXT("Live player or stage widgets unexpectedly disappeared"));
				State->bReady = false;
				return true;
			}
			Action(*State);
			return true;
		}));
	};
	for (const FString Package : { FString(TEXT("/Game/Maps/Stage1")), FString(TEXT("/Game/Maps/Stage2")) })
	{
		AddCommand(new FFunctionLatentCommand([State, Package]
		{
			State->PreviousMap = State->Map;
			State->bReady = false;
			State->Stage = Package;
			UGameplayStatics::OpenLevel(AutomationCommon::GetAnyGameWorld(), FName(*Package));
			return true;
		}));
		AddCommand(new FUntilCommand([State] { return State->Bind(); }, [State]
		{
			State->Test.AddError(State->Stage + TEXT(" timed out waiting for gameplay, a painted minimap and a local viewport of at least 324 logical units"));
			return true;
		}, 90.f));
		Step([](auto& S) { S.Check(TEXT("natural focus at entry"), 240.); S.CheckReveal(TEXT("compact"), false, true); S.Capture(TEXT("compact")); S.FocusViewport(); });
		Step([](auto& S)
		{
			S.HUD->SetMenuOpen(true);
			S.HUD->RequestRestart();
			const FKeyEvent Escape(EKeys::Escape, FModifierKeysState(), S.User, false, 0, 0);
			FSlateApplication::Get().ProcessKeyDownEvent(Escape);
			FSlateApplication::Get().ProcessKeyUpEvent(Escape);
			S.Test.TestTrue(TEXT("Escape returns fallback prompt to its pause menu"), S.HUD->bMenuOpen && !S.HUD->bConfirmRestart);
			S.Test.TestNull(TEXT("Cancelling fallback does not open an overlapping options screen"), S.Settings()->GetCurrentSettingsWidget());
			S.HUD->SetMenuOpen(false);
			S.FocusViewport();
		});
		Step([](auto& S)
		{
			const auto* Stamina = Cast<UProgressBar>(S.Resources->GetWidgetFromName(TEXT("StaminaBar")));
			const auto* BellBar = Cast<UProgressBar>(S.Resources->GetWidgetFromName(TEXT("BellProgress")));
			const auto* Sprint = S.Player->GetPawn()->template FindComponentByClass<UCatrunSprintComponent>();
			const auto* Bell = S.Player->GetPawn()->template FindComponentByClass<UCatrunBellComponent>();
			S.Test.TestFalse(TEXT("Passive readout cannot take focus"), S.Resources->IsFocusable());
			if (S.Test.TestTrue(TEXT("Both authored UMG bars and their gameplay owners exist"), Stamina && BellBar && Sprint && Bell))
			{
				S.Test.TestEqual(TEXT("Stamina readout samples its controller's pawn"), Stamina->GetPercent(), Sprint->GetStaminaNormalized());
				const auto Live = Bell->GetBellStatus();
				const float Expected = Live.CooldownSeconds > 0.f ? 1.f - Live.RemainingSeconds / Live.CooldownSeconds : 1.f;
				S.Test.TestTrue(TEXT("Bell readout follows the accepted action timestamp"), FMath::IsNearlyEqual(BellBar->GetPercent(), Expected, .03f));
			}
		});
		if (Package.EndsWith(TEXT("Stage2")))
		{
			Step([](auto& S) { S.Key(true, true); });
			Step([](auto& S) { S.Check(TEXT("old stage key repeat"), 240.); S.Key(false); });
		}
		Step([](auto& S) { S.Key(true); });
		Step([](auto& S) { S.Check(TEXT("viewport press"), 300.); S.CheckReveal(TEXT("held"), true); S.Capture(TEXT("held")); S.Key(true, true); });
		Step([](auto& S)
		{
			S.Check(TEXT("viewport held without release"), 300.);
			S.CheckReveal(TEXT("sustained hold"), true);
			S.Key(true, true);
		}, Package.EndsWith(TEXT("Stage1")) ? 5. : .25);
		Step([](auto& S) { S.Check(TEXT("viewport held after repeat"), 300.); S.Key(false); });
		Step([](auto& S)
		{
			S.Check(TEXT("viewport release"), 240.);
			S.CheckReveal(TEXT("released"), false);
			S.Capture(TEXT("released"));
			auto& Slate = FSlateApplication::Get();
			Slate.SetUserFocus(S.User, S.HUD->TakeWidget());
			S.Test.TestTrue(TEXT("Focusable gameplay HUD owns keyboard focus"), Slate.GetUserFocusedWidget(S.User) == S.HUD->TakeWidget());
		});
		Step([](auto& S) { S.Key(true); });
		Step([](auto& S) { S.Check(TEXT("focused gameplay HUD press"), 300.); FSlateApplication::Get().ClearUserFocus(S.User); });
		Step([](auto& S) { S.Check(TEXT("focus loss during hold"), 240.); S.FocusViewport(); S.Key(true, true); });
		Step([](auto& S) { S.Check(TEXT("refocused repeat"), 240.); S.Key(false); S.Key(true); });
		Step([](auto& S)
		{
			S.Check(TEXT("fresh press after focus loss"), 300.);
			S.Test.TestNotNull(TEXT("Opened settings while held"), S.Settings()->OpenSettings(S.Player.Get()));
		});
		Step([](auto& S)
		{
			S.Check(TEXT("settings interrupts hold"), 240., false);
			S.Key(false);
			auto* Panel = S.Settings()->GetCurrentSettingsWidget();
			auto* Start = Panel ? Panel->GetWidgetFromName(TEXT("RestartButton")) : nullptr;
			if (S.Test.TestNotNull(TEXT("Gameplay settings restart navigation button"), Start))
				Start->SetUserFocus(S.Player.Get());
			S.Key(true);
		});
		Step([](auto& S)
		{
			auto* Panel = S.Settings()->GetCurrentSettingsWidget();
			auto* Next = Panel ? Panel->GetWidgetFromName(TEXT("MainMenuButton")) : nullptr;
			S.Test.TestTrue(TEXT("Settings navigates forward with Tab"), Next && Next->HasUserFocus(S.Player.Get()));
			S.Check(TEXT("settings tab remains in menu"), 240., false);
			S.Key(false);
			S.Key(true, false, true);
		});
		Step([](auto& S)
		{
			auto* Panel = S.Settings()->GetCurrentSettingsWidget();
			auto* Prev = Panel ? Panel->GetWidgetFromName(TEXT("RestartButton")) : nullptr;
			S.Test.TestTrue(TEXT("Settings navigates backward with Shift+Tab"), Prev && Prev->HasUserFocus(S.Player.Get()));
			if (Panel)
			{
				auto* Restart = Cast<UButton>(Prev);
				auto* Cancel = Cast<UButton>(Panel->GetWidgetFromName(TEXT("RestartCancel")));
				auto* Flow = UCatrunLevelFlowSubsystem::Get(Panel);
				if (S.Test.TestTrue(TEXT("Actual restart and cancel buttons are bound"), Restart && Cancel && Flow))
				{
					const float TimeBefore = Flow->GetStageClockState().RemainingSeconds;
					Restart->OnClicked.Broadcast();
					S.Test.TestTrue(TEXT("One press opens a single confirmation without travel"), Panel->IsStageRestartPending() && !Flow->IsTransitioning());
					Cancel->OnClicked.Broadcast();
					S.Test.TestTrue(TEXT("Cancel keeps options open"), S.Settings()->GetCurrentSettingsWidget() == Panel && !Panel->IsStageRestartPending());
					Restart->OnClicked.Broadcast();
					const FKeyEvent Escape(EKeys::Escape, FModifierKeysState(), S.User, false, 0, 0);
					FSlateApplication::Get().ProcessKeyDownEvent(Escape);
					FSlateApplication::Get().ProcessKeyUpEvent(Escape);
					S.Test.TestTrue(TEXT("One Escape cancels only confirmation"), S.Settings()->GetCurrentSettingsWidget() == Panel && !Panel->IsStageRestartPending());
					S.Test.TestEqual(TEXT("Prompt, cancellation and Escape retain stage time"), Flow->GetStageClockState().RemainingSeconds, TimeBefore);
					S.Test.TestFalse(TEXT("No restart before affirmation"), Flow->IsTransitioning());
				}
			}
			S.Settings()->CloseSettings();
			S.FocusViewport();
			S.Key(true, true);
		});
		Step([](auto& S) { S.Check(TEXT("repeat after settings closes"), 240.); S.Key(false); S.Key(true); });
		Step([](auto& S)
		{
			S.Check(TEXT("fresh press after settings closes"), 300.);
			S.Player->SetCinematicMode(true, false, false, false, false);
		});
		Step([](auto& S) { S.Check(TEXT("cinematic interrupts hold"), 240., false); S.Player->SetCinematicMode(false, false, false, false, false); S.Key(true, true); });
		Step([](auto& S) { S.Check(TEXT("repeat after cinematic ends"), 240.); S.Key(false); S.Key(true); });
		Step([](auto& S) { S.Check(TEXT("fresh press after cinematic ends"), 300.); });
	}
	Step([](auto& S) { S.Key(false); });
	Step([](auto& S) { S.Check(TEXT("final release"), 240.); });
	// Balance the synthetic key even when a travel/setup assertion made further stage steps inapplicable.
	AddCommand(new FFunctionLatentCommand([State] { if (State->bSentDown) State->Key(false); return true; }));
	return true;
}

#endif
