#include "CatrunPlayHUD.h"
#include "Settings/CatrunInputBindings.h"
#include "CatrunLevelFlow.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/BoxComponent.h"
#include "Components/Button.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Engine/Font.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Interaction/CatrunBasketInteractionComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Monster/CatrunMarkSubsystem.h"
#include "Monster/CatrunRestartSubsystem.h"
#include "Sound/CatrunNoBellZone.h"
#include "Styling/CoreStyle.h"
#include "HAL/IConsoleManager.h"
#include "UI/CatrunHUDStyle.h"
#include "Brushes/SlateRoundedBoxBrush.h"

#if !UE_BUILD_SHIPPING
static TAutoConsoleVariable<int32> CVarDebugGuidance(TEXT("catrun.DebugGuidance"), 0,
	TEXT("Show replacement objective, controls and state panels for debugging. Original tutorial UI is unaffected."), ECVF_Cheat);
#endif

namespace
{
	const FLinearColor Ink = CatrunHUDStyle::Text;
	const FLinearColor Accent = CatrunHUDStyle::Brass;
	const FLinearColor Back = CatrunHUDStyle::Ink.CopyWithNewOpacity(.82f);
	FText Copy(const FString& Value) { return FText::FromString(Value); }
	// The same face as every other menu and notice.
	FSlateFontInfo CardFont(const ANSICHAR* Fallback, int32 Size)
	{
		if (const auto* Font = LoadObject<UFont>(nullptr, TEXT("/Game/Environment/Font/HSBombaram3_0_Regular_Font.HSBombaram3_0_Regular_Font")))
			return FSlateFontInfo(Font, Size, TEXT("Default"));
		return FCoreStyle::GetDefaultFontStyle(Fallback, Size);
	}
}

ACatrunGuidanceZone::ACatrunGuidanceZone()
{
	Area = CreateDefaultSubobject<UBoxComponent>(TEXT("Area"));
	SetRootComponent(Area);
	Area->SetBoxExtent(FVector(200,200,200));
	Area->SetCollisionEnabled(ECollisionEnabled::NoCollision);
}
bool ACatrunGuidanceZone::Contains(const FVector& Point) const
{
	return FBox(-Area->GetUnscaledBoxExtent(), Area->GetUnscaledBoxExtent()).IsInsideOrOn(Area->GetComponentTransform().InverseTransformPosition(Point));
}

UTextBlock* UCatrunPlayHUD::AddText(UVerticalBox* Parent, FName Name, const FString& Text, int32 Size, FLinearColor Color)
{
	auto* Block = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), Name);
	Block->SetText(Copy(Text));
	Block->SetFont(CardFont("Regular", Size));
	Block->SetColorAndOpacity(Color);
	Block->SetAutoWrapText(true);
	Parent->AddChildToVerticalBox(Block)->SetPadding(FMargin(0,4));
	return Block;
}
UButton* UCatrunPlayHUD::AddButton(UVerticalBox* Parent, FName Name, const FString& Text, UTextBlock*& Label)
{
	auto* Button = WidgetTree->ConstructWidget<UButton>(UButton::StaticClass(), Name);
	Button->SetBackgroundColor(CatrunHUDStyle::Rim);
	Label = WidgetTree->ConstructWidget<UTextBlock>();
	Label->SetText(Copy(Text));
	Label->SetFont(CardFont("Bold", 21));
	Label->SetColorAndOpacity(Ink);
	Label->SetMargin(FMargin(18,12));
	Button->AddChild(Label);
	Parent->AddChildToVerticalBox(Button)->SetPadding(FMargin(0,6));
	return Button;
}

TSharedRef<SWidget> UCatrunPlayHUD::RebuildWidget()
{
	SetIsFocusable(true);
	if (WidgetTree && !WidgetTree->RootWidget)
	{
		auto* Root = WidgetTree->ConstructWidget<UCanvasPanel>();
		WidgetTree->RootWidget = Root;
		auto MakeCard = [&](FName Name, FVector2D Anchor, FVector2D Position, FVector2D Alignment, float Width, UBorder*& Border)
		{
			Border = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), Name);
			const FSlateRoundedBoxBrush CardBrush(Back, 4.f);
			Border->SetBrush(CardBrush);
			Border->SetPadding(FMargin(18,18,18,6)); // The face is bottom-heavy; keep the visible text centered.
			Border->SetVisibility(ESlateVisibility::HitTestInvisible);
			auto* Fixed = WidgetTree->ConstructWidget<USizeBox>();
			Fixed->SetWidthOverride(Width);
			auto* Box = WidgetTree->ConstructWidget<UVerticalBox>();
			Fixed->AddChild(Box); Border->AddChild(Fixed);
			auto* CanvasSlot = Root->AddChildToCanvas(Border);
			CanvasSlot->SetAnchors(FAnchors(Anchor.X,Anchor.Y));
			CanvasSlot->SetAlignment(Alignment); CanvasSlot->SetPosition(Position); CanvasSlot->SetAutoSize(true);
			return Box;
		};
		UBorder* Guide = nullptr;
		auto* Objective = MakeCard(TEXT("GuideCard"), FVector2D(0,0), FVector2D(24,24), FVector2D::ZeroVector, 360, Guide);
		GuidePanel = Guide;
		GuidePanel->SetVisibility(ESlateVisibility::Collapsed);
		ObjectiveTitle = AddText(Objective,TEXT("ObjectiveTitle"),TEXT("탈출 준비"),23,Accent);
		ObjectiveBody = AddText(Objective,TEXT("ObjectiveBody"),TEXT("주변을 살피며 출구로 이동하세요."),18,Ink);
		UBorder* StateCard = nullptr;
		auto* StateBox = MakeCard(TEXT("StateCard"),FVector2D(1,0),FVector2D(-24,24),FVector2D(1,0),220,StateCard);
		StatePanel = StateCard;
		StatePanel->SetVisibility(ESlateVisibility::Collapsed);
		Status = AddText(StateBox,TEXT("CatStatus"),TEXT("흔적 없음"),20,Accent);
		AddText(StateBox,TEXT("MenuHint"),TEXT("Esc  메뉴"),16,Ink);
		UBorder* Bottom = nullptr;
		auto* BottomBox = MakeCard(TEXT("ControlCard"),FVector2D(.5,1),FVector2D(0,-18),FVector2D(.5,1),660,Bottom);
		ControlsPanel = Bottom;
		ControlsPanel->SetVisibility(ESlateVisibility::Collapsed);
		Context = AddText(BottomBox,TEXT("ContextHint"),TEXT("주변을 살펴보세요."),19,Accent);
		AddText(BottomBox,TEXT("Controls"),TEXT("WASD 이동   ·   Ctrl 살금살금   ·   Shift 달리기   ·   Space 방울   ·   F 상호작용"),16,Ink);

		PausePanel = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(),TEXT("PausePanel"));
		PausePanel->SetBrushColor(CatrunHUDStyle::Ink.CopyWithNewOpacity(.94f));
		PausePanel->SetHorizontalAlignment(HAlign_Center); PausePanel->SetVerticalAlignment(VAlign_Center);
		auto* PauseSlot = Root->AddChildToCanvas(PausePanel);
		PauseSlot->SetAnchors(FAnchors(0,0,1,1)); PauseSlot->SetOffsets(FMargin(0));
		auto* MenuSize = WidgetTree->ConstructWidget<USizeBox>(); MenuSize->SetWidthOverride(470);
		auto* MenuBox = WidgetTree->ConstructWidget<UVerticalBox>(); MenuSize->AddChild(MenuBox); PausePanel->AddChild(MenuSize);
		MenuTitle = AddText(MenuBox,TEXT("MenuTitle"),TEXT("잠깐, 숨 고르기"),32,Accent);
		MenuBody = AddText(MenuBox,TEXT("MenuBody"),TEXT("게임이 일시정지되었습니다."),20,Ink);
		UTextBlock* Label = nullptr;
		AddButton(MenuBox,TEXT("ResumeButton"),TEXT("계속하기"),Label)->OnClicked.AddDynamic(this,&UCatrunPlayHUD::ResumePlay);
		ResumeLabel = Label;
		AddButton(MenuBox,TEXT("RestartButton"),TEXT("스테이지 처음부터 다시 시작"),Label)->OnClicked.AddDynamic(this,&UCatrunPlayHUD::RequestRestart);
		RestartLabel = Label;
		MainMenuButton = AddButton(MenuBox,TEXT("MainMenuButton"),TEXT("시작 메뉴로"),Label);
		MainMenuButton->OnClicked.AddDynamic(this,&UCatrunPlayHUD::ReturnToMenu);
		PausePanel->SetVisibility(ESlateVisibility::Collapsed);
	}
	return Super::RebuildWidget();
}

void UCatrunPlayHUD::NativeTick(const FGeometry& Geometry, float DeltaSeconds)
{
	Super::NativeTick(Geometry,DeltaSeconds);
	if (UCatrunLevelFlowLibrary::ShouldHideGameplayHUD(this))
	{
		if (GuidePanel) GuidePanel->SetVisibility(ESlateVisibility::Collapsed);
		if (StatePanel) StatePanel->SetVisibility(ESlateVisibility::Collapsed);
		if (ControlsPanel) ControlsPanel->SetVisibility(ESlateVisibility::Collapsed);
		RefreshDelay = 0; // Restore through the existing preference-aware refresh, never force HUD on.
		return;
	}
	RefreshDelay -= DeltaSeconds;
	if (RefreshDelay <= 0) { RefreshDelay=.15f; Refresh(); }
}
void UCatrunPlayHUD::Refresh()
{
	APawn* Cat = GetOwningPlayerPawn();
	auto* Flow = UCatrunLevelFlowSubsystem::Get(this);
	if (!Cat || !Flow || !ObjectiveTitle) return;
 const FString InteractKey=UCatrunInputBindings::GetEffectiveKeyLabel(ECatrunInputSlot::Interact).ToString();
 if (auto* Controls=Cast<UTextBlock>(WidgetTree->FindWidget(TEXT("Controls"))))
  Controls->SetText(Copy(FString::Printf(TEXT("%s/%s/%s/%s 이동 · %s 살금살금 · %s 달리기 · %s 방울 · %s 상호작용"),
   *UCatrunInputBindings::GetEffectiveKeyLabel(ECatrunInputSlot::Forward).ToString(),
   *UCatrunInputBindings::GetEffectiveKeyLabel(ECatrunInputSlot::Back).ToString(),
   *UCatrunInputBindings::GetEffectiveKeyLabel(ECatrunInputSlot::Left).ToString(),
   *UCatrunInputBindings::GetEffectiveKeyLabel(ECatrunInputSlot::Right).ToString(),
   *UCatrunInputBindings::GetEffectiveKeyLabel(ECatrunInputSlot::Sneak).ToString(),
   *UCatrunInputBindings::GetEffectiveKeyLabel(ECatrunInputSlot::Run).ToString(),
   *UCatrunInputBindings::GetEffectiveKeyLabel(ECatrunInputSlot::Bell).ToString(),*InteractKey)));
	bool bDebugGuidance = false;
#if !UE_BUILD_SHIPPING
	bDebugGuidance = CVarDebugGuidance.GetValueOnGameThread() != 0;
#endif
	if (!bDebugGuidance && !Flow->IsStageComplete())
	{
		GuidePanel->SetVisibility(ESlateVisibility::Collapsed);
		StatePanel->SetVisibility(ESlateVisibility::Collapsed);
		ControlsPanel->SetVisibility(ESlateVisibility::Collapsed);
		return;
	}
	const auto* Actions = Cat->FindComponentByClass<UCatrunBasketInteractionComponent>();
	const auto* Mark = UCatrunMarkSubsystem::Get(this);
	const auto* Restart = UCatrunRestartSubsystem::Get(this);
	const bool Hidden = Actions && Actions->IsHidden;
	const bool Marked = Mark && Mark->IsMarked();
	FString Title = TEXT("출구를 찾아서");
	FString Body = TEXT("갑옷은 방울로 유인하고, 촛불의 시야를 피해 출구로 이동하세요.");
	ACatrunGuidanceZone* Best = nullptr;
	for (TActorIterator<ACatrunGuidanceZone> It(GetWorld()); It; ++It)
		if (It->Contains(Cat->GetActorLocation()) && (!Best || It->Priority > Best->Priority)) Best=*It;
	if (Best) { Title=Best->Title.ToString(); Body=Best->Message.ToString(); }
	FString Hint = TEXT("방울은 현재 위치에서 울립니다. 울린 뒤 다른 길로 빠져나가세요.");
	FString State = TEXT("흔적 없음");
	if (ACatrunNoBellZone::IsBellForbidden(*Cat)) Hint=TEXT("캣홀 근처에서는 방울을 울릴 수 없습니다. 통로를 벗어나세요.");
	if (Marked) { State=TEXT("표식 · 바구니로"); Hint=FString::Printf(TEXT("촛불에 발각됐습니다. 바구니 가까이에서 %s를 눌러 표식을 지우세요."),*InteractKey); }
	if (Hidden) { State=TEXT("바구니 안 · 은신"); Hint=FString::Printf(TEXT("%s  바구니에서 나오기  ·  출구 앞이 안전한지 살펴보세요."),*InteractKey); }
	if (Restart && Restart->IsCatching()) { State=TEXT("붙잡힘"); Hint=TEXT("잠시 후 이 구간의 시작 지점에서 다시 시작합니다."); }
	if (Flow->IsStageComplete())
	{
		const auto* Stages=GetDefault<UCatrunLevelFlowSettings>();
		const int32 Index=Stages->FindStageIndex(GetWorld()->GetOutermost()->GetName());
		const FText StageName=Stages->Stages.IsValidIndex(Index) ? Stages->GetStageDisplayName(Stages->Stages[Index].StageId) : FText::GetEmpty();
		Title=FString::Printf(TEXT("%s 통과"),*StageName.ToString()); Body=TEXT("이곳에 머물며 둘러볼 수 있습니다. Esc를 누르면 다시 시작하거나 시작 메뉴로 돌아갈 수 있습니다."); State=TEXT("통과"); Hint=Body; }
	ObjectiveTitle->SetText(Copy(Title)); ObjectiveBody->SetText(Copy(Body)); Context->SetText(Copy(Hint)); Status->SetText(Copy(State));
	Status->SetColorAndOpacity(Marked && !Hidden ? FLinearColor(1,.45f,.4f,1) : Accent);
	// Keep the level's opening and stair cinematics readable.
	const auto* Character = Cast<ACharacter>(Cat);
	const bool bIntroMovementLocked = Character && Character->GetCharacterMovement()->MovementMode == MOVE_None
		&& !(Actions && Actions->Busy) && !(Restart && Restart->IsCatching());
	const auto Display = (GetOwningPlayer()->IsMoveInputIgnored() || bIntroMovementLocked) && !Flow->IsStageComplete()
		? ESlateVisibility::Collapsed : ESlateVisibility::HitTestInvisible;
	GuidePanel->SetVisibility(Display);
	StatePanel->SetVisibility(bDebugGuidance ? Display : ESlateVisibility::Collapsed);
	ControlsPanel->SetVisibility(bDebugGuidance ? Display : ESlateVisibility::Collapsed);
}
void UCatrunPlayHUD::SetMenuOpen(bool bOpen)
{
	bMenuOpen=bOpen; bConfirmRestart=false;
	PausePanel->SetVisibility(bOpen ? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
	MenuTitle->SetText(Copy(TEXT("잠깐, 숨 고르기")));
	MenuBody->SetText(Copy(TEXT("게임이 일시정지되었습니다.")));
	ResumeLabel->SetText(Copy(TEXT("계속하기")));
	RestartLabel->SetText(Copy(TEXT("스테이지 처음부터 다시 시작")));
	MainMenuButton->SetVisibility(ESlateVisibility::Visible);
	if (bOpen) SetKeyboardFocus();
}
void UCatrunPlayHUD::ResumePlay()
{
	if (bConfirmRestart) { SetMenuOpen(true); return; }
	if (auto* Flow=UCatrunLevelFlowSubsystem::Get(this)) Flow->SetPauseMenu(false);
}
void UCatrunPlayHUD::RequestRestart()
{
	if (!bMenuOpen) return;
	if (!bConfirmRestart)
	{
		bConfirmRestart=true;
		MenuTitle->SetText(Copy(TEXT("처음부터 다시 할까요?")));
		MenuBody->SetText(Copy(TEXT("현재 스테이지의 퍼즐 진행과 남은 시간을 초기화합니다. 해금한 구역은 유지됩니다.")));
		ResumeLabel->SetText(Copy(TEXT("취소")));
		RestartLabel->SetText(Copy(TEXT("초기화하고 다시 시작")));
		MainMenuButton->SetVisibility(ESlateVisibility::Collapsed);
		if (auto* Cancel = GetWidgetFromName(TEXT("ResumeButton"))) Cancel->SetKeyboardFocus();
	}
	else if (auto* Flow=UCatrunLevelFlowSubsystem::Get(this))
	{
		SetMenuOpen(true);
		if (!Flow->RestartStage()) MenuBody->SetText(Copy(TEXT("지금은 다시 시작할 수 없습니다.")));
	}
}
void UCatrunPlayHUD::ReturnToMenu() { if (auto* Flow=UCatrunLevelFlowSubsystem::Get(this)) Flow->ReturnToMenu(); }
FReply UCatrunPlayHUD::NativeOnKeyDown(const FGeometry& Geometry, const FKeyEvent& Event)
{
	if (bMenuOpen && bConfirmRestart && Event.GetKey() == EKeys::Escape)
	{
		if (!Event.IsRepeat()) SetMenuOpen(true);
		return FReply::Handled();
	}
	return Super::NativeOnKeyDown(Geometry,Event);
}
