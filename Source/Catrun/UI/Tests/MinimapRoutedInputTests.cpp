#if WITH_DEV_AUTOMATION_TESTS

#include "UI/CatrunMinimapWidget.h"
#include "Blueprint/WidgetBlueprintLibrary.h"
#include "Engine/GameViewportClient.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "Framework/Application/SlateApplication.h"
#include "Framework/Application/SlateUser.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "Kismet/GameplayStatics.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "LevelFlow/CatrunPlayHUD.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/Paths.h"
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
		TWeakObjectPtr<UCatrunPlayHUD> HUD;
		TWeakObjectPtr<UCatrunMinimapWidget> PreviousMap;
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
			Frame = Map.IsValid() ? Map->GetWidgetFromName(TEXT("MinimapFrame")) : nullptr;
			if (!HUD.IsValid() || !Frame.IsValid() || !Cast<UCanvasPanelSlot>(Frame->Slot)
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
			if (bVisible)
				Test.TestTrue(Label + TEXT(" painted frame dimensions"), PaintedSize.Equals(FVector2D(Expected), .5));
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
	auto Step = [this, State](TFunction<void(FRoutedMinimap&)> Action)
	{
		// Allow several world/Slate frames for event dispatch, widget tick, layout and paint.
		AddCommand(new FFunctionLatentCommand([State, Action = MoveTemp(Action), First = uint64(0)]() mutable
		{
			if (!State->bReady) return true;
			if (!First) First = GFrameCounter;
			if (GFrameCounter - First < 3) return false;
			if (!State->Player.IsValid() || !State->Map.IsValid() || !State->Frame.IsValid() || !State->HUD.IsValid())
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
		Step([](auto& S) { S.Check(TEXT("natural focus at entry"), 240.); S.Capture(TEXT("compact")); S.FocusViewport(); });
		if (Package.EndsWith(TEXT("Stage2")))
		{
			Step([](auto& S) { S.Key(true, true); });
			Step([](auto& S) { S.Check(TEXT("old stage key repeat"), 240.); S.Key(false); });
		}
		Step([](auto& S) { S.Key(true); });
		Step([](auto& S) { S.Check(TEXT("viewport press"), 300.); S.Capture(TEXT("held")); S.Key(true, true); });
		Step([](auto& S) { S.Check(TEXT("viewport held"), 300.); S.Key(false); });
		Step([](auto& S)
		{
			S.Check(TEXT("viewport release"), 240.);
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
