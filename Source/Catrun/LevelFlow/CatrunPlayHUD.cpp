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

#if !UE_BUILD_SHIPPING
static TAutoConsoleVariable<int32> CVarDebugGuidance(TEXT("catrun.DebugGuidance"), 0,
	TEXT("Show replacement objective, controls and state panels for debugging. Original tutorial UI is unaffected."), ECVF_Cheat);
#endif

namespace
{
	const FLinearColor Ink(.92f,.89f,.82f,1);
	const FLinearColor Accent(.64f,.85f,.82f,1);
	const FLinearColor Back(.025f,.035f,.05f,.88f);
	FText Copy(const FString& Value) { return FText::FromString(Value); }
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
	Block->SetFont(FCoreStyle::GetDefaultFontStyle("Regular", Size));
	Block->SetColorAndOpacity(Color);
	Block->SetAutoWrapText(true);
	Parent->AddChildToVerticalBox(Block)->SetPadding(FMargin(0,4));
	return Block;
}
UButton* UCatrunPlayHUD::AddButton(UVerticalBox* Parent, FName Name, const FString& Text, UTextBlock*& Label)
{
	auto* Button = WidgetTree->ConstructWidget<UButton>(UButton::StaticClass(), Name);
	Button->SetBackgroundColor(FLinearColor(.15f,.24f,.27f,1));
	Label = WidgetTree->ConstructWidget<UTextBlock>();
	Label->SetText(Copy(Text));
	Label->SetFont(FCoreStyle::GetDefaultFontStyle("Bold", 21));
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
			Border->SetBrushColor(Back);
			Border->SetPadding(FMargin(18,12));
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
		PausePanel->SetBrushColor(FLinearColor(.01f,.015f,.025f,.94f));
		PausePanel->SetHorizontalAlignment(HAlign_Center); PausePanel->SetVerticalAlignment(VAlign_Center);
		auto* PauseSlot = Root->AddChildToCanvas(PausePanel);
		PauseSlot->SetAnchors(FAnchors(0,0,1,1)); PauseSlot->SetOffsets(FMargin(0));
		auto* MenuSize = WidgetTree->ConstructWidget<USizeBox>(); MenuSize->SetWidthOverride(470);
		auto* MenuBox = WidgetTree->ConstructWidget<UVerticalBox>(); MenuSize->AddChild(MenuBox); PausePanel->AddChild(MenuSize);
		MenuTitle = AddText(MenuBox,TEXT("MenuTitle"),TEXT("잠깐, 숨 고르기"),32,Accent);
		MenuBody = AddText(MenuBox,TEXT("MenuBody"),TEXT("게임이 일시정지되었습니다."),20,Ink);
		UTextBlock* Label = nullptr;
		AddButton(MenuBox,TEXT("ResumeButton"),TEXT("계속하기"),Label)->OnClicked.AddDynamic(this,&UCatrunPlayHUD::ResumePlay);
		AddButton(MenuBox,TEXT("RestartButton"),TEXT("이 구간 처음부터"),Label)->OnClicked.AddDynamic(this,&UCatrunPlayHUD::RequestRestart);
		RestartLabel = Label;
		AddButton(MenuBox,TEXT("MainMenuButton"),TEXT("시작 메뉴로"),Label)->OnClicked.AddDynamic(this,&UCatrunPlayHUD::ReturnToMenu);
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
	FString Hint = TEXT("방울은 현재 위치에서 울려요. 울린 뒤 다른 길로 빠져나가세요.");
	FString State = TEXT("흔적 없음");
	if (ACatrunNoBellZone::IsBellForbidden(*Cat)) Hint=TEXT("캣홀 근처에서는 방울을 울릴 수 없어요. 통로를 벗어나세요.");
	if (Marked) { State=TEXT("표식 · 바구니로"); Hint=FString::Printf(TEXT("촛불에 발각됐어요. 바구니 가까이에서 %s를 눌러 표식을 지우세요."),*InteractKey); }
	if (Hidden) { State=TEXT("바구니 안 · 은신"); Hint=FString::Printf(TEXT("%s  바구니에서 나오기  ·  출구 앞이 안전한지 살펴보세요."),*InteractKey); }
	if (Restart && Restart->IsCatching()) { State=TEXT("붙잡혔어요"); Hint=TEXT("잠시 후 이 구간의 시작 지점에서 다시 시작합니다."); }
	if (Flow->IsStageComplete()) { Title=TEXT("현재 구간 완료!"); Body=TEXT("스테이지 2를 통과했어요. 이곳에 머물며 자유롭게 둘러볼 수 있어요."); State=TEXT("탈출 연습 완료"); Hint=TEXT("Esc 메뉴에서 다시 시작하거나 시작 메뉴로 돌아갈 수 있어요."); }
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
	RestartLabel->SetText(Copy(TEXT("이 구간 처음부터")));
	if (bOpen) SetKeyboardFocus();
}
void UCatrunPlayHUD::ResumePlay() { if (auto* Flow=UCatrunLevelFlowSubsystem::Get(this)) Flow->SetPauseMenu(false); }
void UCatrunPlayHUD::RequestRestart()
{
	if (!bMenuOpen) return;
	if (!bConfirmRestart)
	{
		bConfirmRestart=true;
		MenuTitle->SetText(Copy(TEXT("처음부터 다시 할까요?")));
		MenuBody->SetText(Copy(TEXT("이 구간의 동상·문·적·표식이 모두 초기화됩니다. 계속하기를 누르면 취소됩니다.")));
		RestartLabel->SetText(Copy(TEXT("진행을 포기하고 다시 시작")));
	}
	else if (auto* Flow=UCatrunLevelFlowSubsystem::Get(this))
	{
		if (!Flow->RestartStage()) { MenuBody->SetText(Copy(TEXT("지금은 재시작할 수 없어요. 계속하기로 돌아가세요."))); }
	}
}
void UCatrunPlayHUD::ReturnToMenu() { if (auto* Flow=UCatrunLevelFlowSubsystem::Get(this)) Flow->ReturnToMenu(); }
FReply UCatrunPlayHUD::NativeOnKeyDown(const FGeometry& Geometry, const FKeyEvent& Event)
{
	// Escape is owned by the shared settings subsystem in every playable map.
	return Super::NativeOnKeyDown(Geometry,Event);
}
