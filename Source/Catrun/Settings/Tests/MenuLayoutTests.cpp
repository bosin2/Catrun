#if WITH_EDITOR && WITH_DEV_AUTOMATION_TESTS

#include "Blueprint/UserWidget.h"
#include "Components/Button.h"
#include "Components/ScrollBox.h"
#include "Components/TextBlock.h"
#include "Components/WidgetSwitcher.h"
#include "Engine/UserInterfaceSettings.h"
#include "Engine/World.h"
#include "Framework/Application/SlateApplication.h"
#include "Layout/ArrangedChildren.h"
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include "Rendering/DrawElements.h"
#include "Widgets/Layout/SDPIScaler.h"
#include "Widgets/SVirtualWindow.h"

namespace
{
struct FMenuViewport
{
	FIntPoint Size;
	int32 ExpectedChapterColumns;
};

const FMenuViewport Viewports[] = {
	{{1920, 1080}, 4},
	{{2560, 1080}, 4},
	{{1680, 1050}, 4},
	{{640, 360}, 3},
	{{520, 780}, 2},
	{{320, 700}, 1},
};

FSlateRect PaintBounds(const FGeometry& Geometry)
{
	const FVector2f Position = Geometry.GetAbsolutePosition();
	const FVector2f Size = Geometry.GetAbsoluteSize();
	return FSlateRect(Position.X, Position.Y, Position.X + Size.X, Position.Y + Size.Y);
}

FSlateRect PaintBounds(const UWidget& Widget)
{
	return PaintBounds(Widget.GetPaintSpaceGeometry());
}

bool HasArea(const FSlateRect& Bounds)
{
	return Bounds.Right > Bounds.Left && Bounds.Bottom > Bounds.Top;
}

bool Contains(const FSlateRect& Outer, const FSlateRect& Inner)
{
	constexpr float PaintTolerance = 1.f;
	return HasArea(Inner) && Inner.Left >= Outer.Left - PaintTolerance && Inner.Top >= Outer.Top - PaintTolerance
		&& Inner.Right <= Outer.Right + PaintTolerance && Inner.Bottom <= Outer.Bottom + PaintTolerance;
}

TSharedRef<SVirtualWindow> MakeVirtualViewport(UUserWidget& Widget, FIntPoint Size)
{
	const float Scale = GetDefault<UUserInterfaceSettings>()->GetDPIScaleBasedOnSize(Size);
	const TSharedRef<SVirtualWindow> Window = SNew(SVirtualWindow).Size(FVector2D(Size.X, Size.Y));
	Window->SetContent(SNew(SDPIScaler).DPIScale(Scale)[Widget.TakeWidget()]);
	return Window;
}

void PaintMenu(const TSharedRef<SVirtualWindow>& Window)
{
	// Auto-wrap uses the width from the previous paint. Give wrapping and the
	// scrollbar their normal follow-up layout passes without opening a window.
	for (int32 Pass = 0; Pass < 5; ++Pass)
	{
		Window->SlatePrepass(1.f);
		FSlateWindowElementList DrawElements(Window);
		Window->PaintWindow(FPlatformTime::Seconds(), 1.f / 60.f, DrawElements, FWidgetStyle(), true);
	}
}

UUserWidget* MakeDesignerInstance(UWorld& World, UClass* WidgetClass)
{
	UUserWidget* Widget = CreateWidget<UUserWidget>(&World, WidgetClass);
	if (Widget)
	{
		Widget->SetDesignerFlags(EWidgetDesignFlags::Designing);
	}
	return Widget;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunMenuLayoutTest, "Catrun.Settings.SavedMenuLayout",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCatrunMenuLayoutTest::RunTest(const FString&)
{
	if (!TestTrue(TEXT("Slate is initialized"), FSlateApplication::IsInitialized()))
	{
		return false;
	}
	UClass* SettingsClass = LoadClass<UUserWidget>(nullptr, TEXT("/Game/UI/Settings/WBP_Setting.WBP_Setting_C"));
	UClass* ChapterClass = LoadClass<UUserWidget>(nullptr, TEXT("/Game/UI/Continue/WBP_ChapterSelect.WBP_ChapterSelect_C"));
	if (!TestNotNull(TEXT("Saved settings widget"), SettingsClass) || !TestNotNull(TEXT("Saved chapter widget"), ChapterClass))
	{
		return false;
	}
	const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false)
		.CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false);
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
	if (!TestNotNull(TEXT("Detached widget world"), World))
	{
		return false;
	}
	ON_SCOPE_EXIT { World->DestroyWorld(false); };

	for (const FMenuViewport& Viewport : Viewports)
	{
		const FIntPoint Size = Viewport.Size;
		const FString Label = FString::Printf(TEXT("%dx%d"), Size.X, Size.Y);
		const FSlateRect Screen(0, 0, Size.X, Size.Y);
		UUserWidget* Settings = MakeDesignerInstance(*World, SettingsClass);
		UUserWidget* Chapter = MakeDesignerInstance(*World, ChapterClass);
		if (!TestNotNull(TEXT("Settings designer instance"), Settings) || !TestNotNull(TEXT("Chapter designer instance"), Chapter))
		{
			return false;
		}

		UTextBlock* Status = Cast<UTextBlock>(Settings->GetWidgetFromName(TEXT("SettingsStatus")));
		UWidgetSwitcher* Categories = Cast<UWidgetSwitcher>(Settings->GetWidgetFromName(TEXT("CategorySwitcher")));
		UWidget* DeveloperPage = Settings->GetWidgetFromName(TEXT("DeveloperGroup"));
		UWidget* DeveloperTab = Settings->GetWidgetFromName(TEXT("DeveloperCategoryButton"));
		UWidget* Travel = Settings->GetWidgetFromName(TEXT("GameplayActions"));
		if (!TestNotNull(TEXT("Settings status"), Status) || !TestNotNull(TEXT("Category switcher"), Categories)
			|| !TestNotNull(TEXT("Developer page"), DeveloperPage) || !TestNotNull(TEXT("Developer tab"), DeveloperTab)
			|| !TestNotNull(TEXT("In-game settings actions"), Travel))
		{
			return false;
		}
		const TSharedRef<SVirtualWindow> SettingsWindow = MakeVirtualViewport(*Settings, Size);
		Status->SetText(FText::FromString(TEXT("키 입력을 마치거나 Esc로 취소한 뒤 적용하세요. 변경한 설정은 적용을 누르면 저장됩니다.")));
		for (const bool bDeveloper : {false, true})
		{
			const ESlateVisibility Visibility = bDeveloper ? ESlateVisibility::Visible : ESlateVisibility::Collapsed;
			DeveloperTab->SetVisibility(Visibility);
			DeveloperPage->SetVisibility(Visibility);
			Categories->SetActiveWidgetIndex(bDeveloper ? Categories->GetChildIndex(DeveloperPage) : 0);
			for (const bool bInGame : {false, true})
			{
				Travel->SetVisibility(bInGame ? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
				PaintMenu(SettingsWindow);
				const FString State = FString::Printf(TEXT("%s developer=%d in-game=%d"), *Label, bDeveloper, bInGame);
				const FSlateRect Message = PaintBounds(*Status);
				TestTrue(State + TEXT(" status inside viewport"), Contains(Screen, Message));
				const FVector2D TextDesired = Status->GetDesiredSize();
				const FVector2D TextAllotted = Status->GetPaintSpaceGeometry().GetLocalSize();
				TestTrue(State + TEXT(" status height accommodates wrapped text"), TextAllotted.Y + 1.f >= TextDesired.Y);
				for (const FName ButtonName : {FName(TEXT("DefaultsButton")), FName(TEXT("ApplyButton")), FName(TEXT("CloseButton")),
					FName(TEXT("RestartButton")), FName(TEXT("MainMenuButton"))})
				{
					if (!bInGame && (ButtonName == TEXT("RestartButton") || ButtonName == TEXT("MainMenuButton")))
					{
						continue;
					}
					UWidget* Button = Settings->GetWidgetFromName(ButtonName);
					if (!TestNotNull(State + TEXT(" ") + ButtonName.ToString(), Button))
					{
						return false;
					}
					const FSlateRect Bounds = PaintBounds(*Button);
					TestTrue(State + TEXT(" footer button in viewport: ") + ButtonName.ToString(), Contains(Screen, Bounds));
					TestTrue(State + TEXT(" footer button follows message: ") + ButtonName.ToString(), Bounds.Top >= Message.Bottom - 1.f);
				}
			}
		}

		const TSharedRef<SVirtualWindow> ChapterWindow = MakeVirtualViewport(*Chapter, Size);
		PaintMenu(ChapterWindow);
		UWidget* Grid = Chapter->GetWidgetFromName(TEXT("ChapterCardGrid"));
		UWidget* Back = Chapter->GetWidgetFromName(TEXT("ChapterBack"));
		UScrollBox* Scroll = Cast<UScrollBox>(Chapter->GetWidgetFromName(TEXT("ChapterCardScroll")));
		if (!TestNotNull(TEXT("Chapter card grid"), Grid) || !TestNotNull(TEXT("Chapter back button"), Back)
			|| !TestNotNull(TEXT("Chapter card scroll box"), Scroll))
		{
			return false;
		}
		TestTrue(Label + TEXT(" back button stays visible"), Contains(Screen, PaintBounds(*Back)));
		FArrangedChildren Cards(EVisibility::Visible);
		Grid->GetCachedWidget()->ArrangeChildren(Grid->GetPaintSpaceGeometry(), Cards);
		if (!TestEqual(Label + TEXT(" arranged chapter card count"), Cards.Num(), 4))
		{
			return false;
		}
		const FSlateRect ScrollBounds = PaintBounds(*Scroll);
		const FSlateRect FirstCard = PaintBounds(Cards[0].Geometry);
		int32 Columns = 0;
		for (int32 Index = 0; Index < Cards.Num(); ++Index)
		{
			const FSlateRect Card = PaintBounds(Cards[Index].Geometry);
			TestTrue(Label + TEXT(" card inside scroll width"), HasArea(Card)
				&& Card.Left >= ScrollBounds.Left - 1.f && Card.Right <= ScrollBounds.Right + 1.f);
			if (FMath::IsNearlyEqual(Card.Top, FirstCard.Top, 1.f))
			{
				++Columns;
			}
		}
		TestEqual(Label + TEXT(" first-row chapter columns"), Columns, Viewport.ExpectedChapterColumns);
		for (const FName ButtonName : {FName(TEXT("TutorialButton")), FName(TEXT("Stage1Button")), FName(TEXT("Stage2Button")),
			FName(TEXT("Stage3Button")), FName(TEXT("ChapterBack"))})
		{
			const UButton* Button = Cast<UButton>(Chapter->GetWidgetFromName(ButtonName));
			TestTrue(Label + TEXT(" keyboard and gamepad can focus ") + ButtonName.ToString(), Button && Button->GetIsFocusable());
		}
		if (Viewport.ExpectedChapterColumns < 4)
		{
			TestTrue(Label + TEXT(" remaining chapter rows scroll"), Scroll->GetScrollOffsetOfEnd() > 0.f);
			Scroll->ScrollToEnd();
			PaintMenu(ChapterWindow);
			UWidget* LastCard = Chapter->GetWidgetFromName(TEXT("Stage3Button"));
			if (TestNotNull(TEXT("Final chapter button"), LastCard))
			{
				TestTrue(Label + TEXT(" final chapter reachable by scrolling"), Contains(PaintBounds(*Scroll), PaintBounds(*LastCard)));
			}
		}
	}
	return true;
}

#endif
