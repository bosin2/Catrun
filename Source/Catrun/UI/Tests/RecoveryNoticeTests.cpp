#if WITH_DEV_AUTOMATION_TESTS

#include "Sound/CatrunNotice.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "Interaction/CatrunPuzzleSuspension.h"
#include "Monster/CatrunRestartSubsystem.h"
#include "Camera/PlayerCameraManager.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include "Slate/SObjectWidget.h"
#include "TimerManager.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunRecoveryNoticeTest,
	"Catrun.UI.Notice.BlockedRecoveryPreservesPresentationOwners",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCatrunRecoveryNoticeTest::RunTest(const FString&)
{
	const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(true)
		.CreateNavigation(false).CreateAISystem(false);
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
	if (!TestNotNull(TEXT("Recovery notice world"), World)) return false;
	GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
	ON_SCOPE_EXIT { GEngine->DestroyWorldContext(World); World->DestroyWorld(false); };
	World->InitializeActorsForPlay(FURL());
	auto* PC = World->SpawnActor<APlayerController>();
	auto* Cat = World->SpawnActor<ACharacter>();
	auto* Camera = World->SpawnActor<AActor>();
	auto* Owner = World->SpawnActor<AActor>();
	PC->Possess(Cat);
	PC->SetViewTarget(Cat);
	Cat->GetCharacterMovement()->DisableMovement();
	TestEqual(TEXT("Reported pawn starts with disabled movement"), Cat->GetCharacterMovement()->MovementMode,
		TEnumAsByte<EMovementMode>(MOVE_None));
	Cat->SetActorEnableCollision(false);
	auto* Restart = World->GetSubsystem<UCatrunRestartSubsystem>();
	auto* Notice = World->GetSubsystem<UCatrunNoticeSubsystem>();
	// Supply the real native widget without requiring a game viewport in this detached world.
	Notice->Widget = NewObject<UCatrunNoticeWidget>(World);
	auto* Widget = Notice->Widget.Get();
	if (!TestTrue(TEXT("Native notice widget initializes"), Widget->Initialize())) return false;
	const TSharedRef<SObjectWidget> SlateWidget = StaticCastSharedRef<SObjectWidget>(Widget->TakeWidget());
	auto CheckOpacity = [&](const TCHAR* What, float Expected)
	{
		// Route through the UMG Slate wrapper that calls the widget's NativeTick.
		SlateWidget->Tick(FGeometry(), 0.0, 0.f);
		TestEqual(What, Widget->GetRenderOpacity(), Expected);
	};
	Notice->ShowNotice(INVTEXT("Recovery instruction"), 8.f, ECatrunNoticePolicy::BlockedRecovery);
	CheckOpacity(TEXT("MOVE_None alone does not authorize a recovery notice"), 0.f);
	TestTrue(TEXT("Capture owns presentation before reporting failed recovery"), Restart->TryBeginCatch(Owner));
	Restart->ReportBlockedPawnRecovery(*Cat);
	TestTrue(TEXT("Production failure reports a blocked pawn"), Restart->HasBlockedPawnRecovery());
	CheckOpacity(TEXT("Recovery does not cover an active capture"), 0.f);
	Restart->CancelCatch(Owner);
	CheckOpacity(TEXT("Recovery instruction appears after capture ownership releases despite MOVE_None"), 1.f);
	TestTrue(TEXT("Ordinary gameplay HUD stays hidden"), UCatrunLevelFlowLibrary::ShouldHideGameplayHUD(World));
	TestEqual(TEXT("Recovery keeps its original duration"), World->GetTimerManager().GetTimerRemaining(Notice->HideTimer), 8.f);
	if (!PC->PlayerCameraManager) PC->PlayerCameraManager = World->SpawnActor<APlayerCameraManager>();
	auto* Fade = PC->PlayerCameraManager.Get();
	if (!TestNotNull(TEXT("Recovery camera manager"), Fade)) return false;
	Fade->SetManualCameraFade(1.f, FLinearColor::Black, false);
	CheckOpacity(TEXT("Recovery exception cannot paint over camera blackout"), 0.f);
	Fade->SetManualCameraFade(0.f, FLinearColor::Black, false);
	CheckOpacity(TEXT("Transparent fade restores the recovery instruction"), 1.f);
	Fade->StopCameraFade();

	// A previous pawn's failure cannot exempt the newly possessed pawn's movement lock.
	auto* ReplacementCat = World->SpawnActor<ACharacter>();
	ReplacementCat->SetActorEnableCollision(false);
	PC->Possess(ReplacementCat);
	PC->SetViewTarget(ReplacementCat);
	// Possess restarts ACharacter and restores its default movement mode.
	ReplacementCat->GetCharacterMovement()->DisableMovement();
	TestEqual(TEXT("Replacement pawn is MOVE_None after possession"), ReplacementCat->GetCharacterMovement()->MovementMode,
		TEnumAsByte<EMovementMode>(MOVE_None));
	TestTrue(TEXT("Original blocked pawn remains recorded after possession changes"), Restart->HasBlockedPawnRecovery());
	CheckOpacity(TEXT("Another pawn's recovery cannot bypass the current pawn's MOVE_None"), 0.f);
	PC->Possess(Cat);
	PC->SetViewTarget(Cat);
	Cat->GetCharacterMovement()->DisableMovement();
	TestEqual(TEXT("Reported pawn is MOVE_None after repossession"), Cat->GetCharacterMovement()->MovementMode,
		TEnumAsByte<EMovementMode>(MOVE_None));
	CheckOpacity(TEXT("Returning to the reported blocked pawn restores its instruction"), 1.f);

	PC->SetViewTarget(Camera);
	CheckOpacity(TEXT("A cinematic camera still hides recovery instructions"), 0.f);
	PC->SetViewTarget(Cat);
	PC->bCinematicMode = true;
	CheckOpacity(TEXT("Cinematic mode still hides recovery instructions"), 0.f);
	PC->bCinematicMode = false;
	PC->SetIgnoreMoveInput(true);
	CheckOpacity(TEXT("Input ownership still hides recovery instructions"), 0.f);
	PC->SetIgnoreMoveInput(false);
	auto* Suspension = World->GetSubsystem<UCatrunPuzzleSuspension>();
	TestTrue(TEXT("Puzzle reveal acquires its presentation"), Suspension->Acquire(Owner));
	CheckOpacity(TEXT("Puzzle reveal hides recovery instructions"), 0.f);
	Suspension->Release(Owner);
	auto* Flow = World->GetSubsystem<UCatrunLevelFlowSubsystem>();
	TestTrue(TEXT("Exit transition reserves its presentation"), Flow->ReserveExitTransition(Owner));
	CheckOpacity(TEXT("Transition hides recovery instructions"), 0.f);
	Flow->ReleaseExitTransition(Owner);
	CheckOpacity(TEXT("Released presentation restores the recovery instruction"), 1.f);

	auto* Settings = GetMutableDefault<UCatrunLevelFlowSettings>();
	const auto PreviousMenu = Settings->MainMenuMap;
	ON_SCOPE_EXIT { Settings->MainMenuMap = PreviousMenu; };
	Settings->MainMenuMap = TSoftObjectPtr<UWorld>(FSoftObjectPath(World->GetOutermost()->GetName()));
	CheckOpacity(TEXT("Main menu always hides recovery instructions"), 0.f);
	Settings->MainMenuMap = PreviousMenu;
	CheckOpacity(TEXT("Gameplay world restores the scoped recovery instruction"), 1.f);
	Cat->SetActorEnableCollision(true);
	CheckOpacity(TEXT("A cleared blocked-pawn condition cannot bypass MOVE_None"), 0.f);
	Cat->SetActorEnableCollision(false);

	// Policy belongs to each message, not to the widget's lifetime or its text.
	Notice->ShowNotice(INVTEXT("Routine notice"), 2.f);
	CheckOpacity(TEXT("A subsequent routine notice cannot inherit the recovery exception"), 0.f);
	TestEqual(TEXT("Replacement notice keeps its own duration"), World->GetTimerManager().GetTimerRemaining(Notice->HideTimer), 2.f);
	Restart->ReportBlockedPawnRecovery(*Cat);
	CheckOpacity(TEXT("A new recovery instruction explicitly opts back in"), 1.f);
	++GFrameCounter;
	World->GetTimerManager().Tick(0.f); // activate pending expiration
	++GFrameCounter;
	World->GetTimerManager().Tick(8.1f);
	TestTrue(TEXT("Recovery notice still expires normally"), Widget->GetVisibility() == ESlateVisibility::Collapsed);
	TestFalse(TEXT("Expired recovery timer is removed"), World->GetTimerManager().TimerExists(Notice->HideTimer));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunDeferredNoticeTest,
	"Catrun.UI.Notice.DeferredGameplayCountsReadableTime",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCatrunDeferredNoticeTest::RunTest(const FString&)
{
	const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(true)
		.CreateNavigation(false).CreateAISystem(false);
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
	if (!TestNotNull(TEXT("Deferred notice world"), World)) return false;
	GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
	ON_SCOPE_EXIT { GEngine->DestroyWorldContext(World); World->DestroyWorld(false); };
	World->InitializeActorsForPlay(FURL());
	auto* PC = World->SpawnActor<APlayerController>();
	auto* Cat = World->SpawnActor<ACharacter>();
	PC->Possess(Cat);
	PC->SetViewTarget(Cat);
	Cat->GetCharacterMovement()->SetMovementMode(MOVE_Walking);

	auto* Notice = World->GetSubsystem<UCatrunNoticeSubsystem>();
	Notice->Widget = NewObject<UCatrunNoticeWidget>(World);
	auto* Widget = Notice->Widget.Get();
	if (!TestTrue(TEXT("Native notice widget initializes"), Widget->Initialize())) return false;
	const TSharedRef<SObjectWidget> SlateWidget = StaticCastSharedRef<SObjectWidget>(Widget->TakeWidget());
	auto Step = [&](float Seconds)
	{
		++GFrameCounter;
		World->GetTimerManager().Tick(Seconds);
		SlateWidget->Tick(FGeometry(), 0.0, Seconds);
	};
	auto IsReadable = [Widget]
	{
		return Widget->GetVisibility() == ESlateVisibility::HitTestInvisible && Widget->GetRenderOpacity() > 0.f;
	};

	Notice->ShowNotice(INVTEXT("Checkpoint pending"), 2.f);
	Step(0.f);
	Notice->ShowNotice(INVTEXT("Checkpoint failed"), 5.f, ECatrunNoticePolicy::DeferredGameplay);
	Step(0.f);
	TestTrue(TEXT("A failure can be readable before a cinematic takes ownership"), IsReadable());
	Step(1.f);
	PC->SetIgnoreMoveInput(true);
	Step(0.f);
	Step(12.6f);
	TestFalse(TEXT("Failure does not cover the arrival cinematic"), IsReadable());
	PC->SetIgnoreMoveInput(false);
	Step(2.f); // Elapsed time since the previous hidden frame.
	TestTrue(TEXT("Failure is readable when gameplay presentation returns"), IsReadable());
	Step(3.9f);
	TestTrue(TEXT("The previously unread four seconds are available"), IsReadable());
	Step(0.2f);
	TestTrue(TEXT("Failure collapses after five readable seconds in total"), Widget->GetVisibility() == ESlateVisibility::Collapsed);

	PC->bCinematicMode = true;
	Notice->ShowNotice(INVTEXT("Checkpoint failed while hidden"), 5.f, ECatrunNoticePolicy::DeferredGameplay);
	Step(0.f);
	Step(13.f);
	TestFalse(TEXT("A failure received while hidden stays hidden"), IsReadable());
	PC->bCinematicMode = false;
	Step(0.f);
	TestTrue(TEXT("A failure received while hidden is readable at handoff"), IsReadable());
	Step(4.9f);
	TestTrue(TEXT("A failure received while hidden gets its full readable duration"), IsReadable());

	PC->bCinematicMode = true;
	Notice->ShowNotice(INVTEXT("Routine notice"), 2.f);
	Step(0.f);
	Step(2.1f);
	PC->bCinematicMode = false;
	Step(0.f);
	TestTrue(TEXT("An expired ordinary prompt and the failure it replaced stay collapsed"),
		Widget->GetVisibility() == ESlateVisibility::Collapsed);
	return true;
}

#endif
