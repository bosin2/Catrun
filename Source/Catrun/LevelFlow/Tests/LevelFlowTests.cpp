#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "Monster/CatrunRestartSubsystem.h"
#include "Engine/World.h"
#include "Engine/GameInstance.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Sound/CatrunNotice.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunFlowRoutesTest, "Catrun.LevelFlow.RouteResolution", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunFlowRoutesTest::RunTest(const FString&)
{
	auto* Settings = NewObject<UCatrunLevelFlowSettings>();
	Settings->Stages.Reset();
	auto& Tutorial = Settings->Stages.AddDefaulted_GetRef();
	Tutorial.StageId = TEXT("Tutorial");
	Tutorial.Map = TSoftObjectPtr<UWorld>(FSoftObjectPath(TEXT("/Game/Maps/PlayableTutorial.PlayableTutorial")));
	auto& Stage = Settings->Stages.AddDefaulted_GetRef();
	Stage.StageId = TEXT("Stage1");
	Stage.Map = TSoftObjectPtr<UWorld>(FSoftObjectPath(TEXT("/Game/Maps/PlayableStage1.PlayableStage1")));
	TestEqual(TEXT("Configured map follows stage ordering"), Settings->FindStageIndex(TEXT("/Game/Maps/PlayableStage1")), 1);
	TestEqual(TEXT("PIE map resolves to the same route"), Settings->FindStageIndex(TEXT("/Game/Maps/UEDPIE_0_PlayableStage1")), 1);
	TestEqual(TEXT("Original art map alias remains usable"), Settings->FindStageIndex(TEXT("/Game/Maps/Stage1")), 1);
	TestEqual(TEXT("Unknown map cannot advance"), Settings->FindStageIndex(TEXT("/Game/Maps/Unknown")), INDEX_NONE);
	TestEqual(TEXT("Menu is not a playable stage"), Settings->FindStageIndex(TEXT("/Game/Maps/MainMenu")), INDEX_NONE);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunFlowCatchGuardTest, "Catrun.LevelFlow.CompletionBlocksCapture", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunFlowCatchGuardTest::RunTest(const FString&)
{
	const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false);
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
	auto* Flow = World->GetSubsystem<UCatrunLevelFlowSubsystem>();
	auto* Restart = World->GetSubsystem<UCatrunRestartSubsystem>();
	if (TestNotNull(TEXT("Flow subsystem exists"), Flow) && TestNotNull(TEXT("Restart subsystem exists"), Restart))
	{
		Flow->bStageComplete = true;
		TestFalse(TEXT("Completed stage rejects capture"), Restart->TryBeginCatch());
		TestFalse(TEXT("Completion does not leave catch state set"), Restart->IsCatching());
		Flow->bStageComplete = false;
		TestTrue(TEXT("Normal stage can still catch the cat"), Restart->TryBeginCatch());
		TestFalse(TEXT("A second armor cannot begin another catch"), Restart->TryBeginCatch());
	}
	World->DestroyWorld(false);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunRestartIntentTest, "Catrun.LevelFlow.RestartIntentConsumption", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunRestartIntentTest::RunTest(const FString&)
{
	FCatrunRestartIntent Intent;
	float Fade = -1.f;
	TestFalse(TEXT("Fresh start has no restart intent"), Intent.Consume(TEXT("/Game/Maps/Tutorial"), Fade));
	Intent.Request(TEXT("/Game/Maps/UEDPIE_0_Tutorial"), .75f);
	TestTrue(TEXT("Restart follows clean package across PIE reload"), Intent.Consume(TEXT("/Game/Maps/UEDPIE_0_Tutorial"), Fade));
	TestEqual(TEXT("Fade duration survives the reload token"), Fade, .75f);
	TestFalse(TEXT("Intent is consumed exactly once"), Intent.Consume(TEXT("/Game/Maps/Tutorial"), Fade));
	TestEqual(TEXT("A fresh world cannot inherit an old fade"), Fade, 0.f);
	Intent.Request(TEXT("/Game/Maps/Tutorial"), 1.f);
	TestFalse(TEXT("Different destination does not skip its intro"), Intent.Consume(TEXT("/Game/Maps/Stage1"), Fade));
	TestFalse(TEXT("Mismatch invalidates stale token"), Intent.Consume(TEXT("/Game/Maps/Tutorial"), Fade));
	Intent.Request(TEXT("/Game/Maps/Tutorial"), 1.f);
	Intent.Clear();
	TestFalse(TEXT("New game clears restart intent"), Intent.Consume(TEXT("/Game/Maps/Tutorial"), Fade));
	FCatrunRestartIntent OtherSession;
	Intent.Request(TEXT("/Game/Maps/Tutorial"), 1.f);
	TestFalse(TEXT("Another PIE session has independent intent"), OtherSession.Consume(TEXT("/Game/Maps/Tutorial"), Fade));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunCameraProfilesTest, "Catrun.LevelFlow.StageCameraProfiles", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunCameraProfilesTest::RunTest(const FString&)
{
	const auto* Defaults = GetDefault<UCatrunLevelFlowSettings>();
	TestEqual(TEXT("Tutorial retains original width"), Defaults->GetCameraDistanceScale(TEXT("Tutorial")), 1.f);
	TestEqual(TEXT("Stage1 default is farther"), Defaults->GetCameraDistanceScale(TEXT("Stage1")), 1.15f);
	TestEqual(TEXT("Stage2 default is farther again"), Defaults->GetCameraDistanceScale(TEXT("Stage2")), 1.30f);
	auto* Settings = NewObject<UCatrunLevelFlowSettings>();
	Settings->CameraProfiles.Reset();
	auto& Custom = Settings->CameraProfiles.AddDefaulted_GetRef();
	Custom.StageId = TEXT("Stage2"); Custom.DistanceScale = 1.6f;
	TestEqual(TEXT("Tuning maps by StageId independently of route order"), Settings->GetCameraDistanceScale(TEXT("Stage2")), 1.6f);
	Custom.StageId = TEXT("Tutorial");
	TestEqual(TEXT("Even edited tutorial settings cannot alter its camera"), Settings->GetCameraDistanceScale(TEXT("Tutorial")), 1.f);
	TestEqual(TEXT("Unconfigured stage preserves its authored camera"), Settings->GetCameraDistanceScale(TEXT("Unknown")), 1.f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunCameraBaselineTest, "Catrun.LevelFlow.CameraBaselineIsolation", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunCameraBaselineTest::RunTest(const FString&)
{
	const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false);
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
	// Spawning into a world without initialized actors skips controller registration/camera-manager creation.
	World->InitializeActorsForPlay(FURL());
	auto* Settings = GetMutableDefault<UCatrunLevelFlowSettings>();
	TGuardValue<TArray<FCatrunStageRoute>> RestoreRoutes(Settings->Stages, Settings->Stages);
	auto& Route = Settings->Stages.AddDefaulted_GetRef();
	Route.StageId = TEXT("Stage1"); Route.Map = TSoftObjectPtr<UWorld>(FSoftObjectPath(World->GetOutermost()->GetName()));
	auto* Flow = World->GetSubsystem<UCatrunLevelFlowSubsystem>();
	APlayerController* PC = World->SpawnActor<APlayerController>();
	APawn* Pawn = World->SpawnActor<APawn>();
	PC->Possess(Pawn);
	ACameraActor* Gameplay = World->SpawnActor<ACameraActor>();
	Gameplay->Tags.Add(TEXT("CatrunGameplayCamera"));
	Gameplay->GetCameraComponent()->SetProjectionMode(ECameraProjectionMode::Orthographic);
	Gameplay->GetCameraComponent()->SetOrthoWidth(900.f);
	PC->SetViewTarget(Gameplay);
	TestTrue(TEXT("Fixture registers a controller and camera view"), PC->PlayerCameraManager && PC->GetViewTarget() == Gameplay);
	TestTrue(TEXT("Fixture map resolves to its temporary stage route"), Settings->FindStageIndex(World->GetOutermost()->GetName()) != INDEX_NONE);
	TestTrue(TEXT("External authored gameplay camera is accepted"), Flow->ApplyStageCameraProfile(Gameplay->GetCameraComponent(), nullptr));
	TestEqual(TEXT("Orthographic scale uses authored width"), Gameplay->GetCameraComponent()->OrthoWidth, 1035.f);
	Flow->ApplyStageCameraProfile(Gameplay->GetCameraComponent(), nullptr);
	TestEqual(TEXT("Repeated application cannot compound zoom"), Gameplay->GetCameraComponent()->OrthoWidth, 1035.f);
	ACameraActor* Capture = World->SpawnActor<ACameraActor>();
	Capture->GetCameraComponent()->SetOrthoWidth(444.f);
	PC->SetViewTarget(Capture);
	TestFalse(TEXT("Temporary view target is rejected"), Flow->ApplyStageCameraProfile(Capture->GetCameraComponent(), nullptr));
	TestFalse(TEXT("Inactive gameplay camera cannot be recaptured during presentation"), Flow->ApplyStageCameraProfile(Gameplay->GetCameraComponent(), nullptr));
	PC->SetViewTarget(Gameplay);
	Flow->ApplyStageCameraProfile(Gameplay->GetCameraComponent(), nullptr);
	TestEqual(TEXT("Return from capture retains original baseline"), Gameplay->GetCameraComponent()->OrthoWidth, 1035.f);
	TestEqual(TEXT("Capture width is untouched"), Capture->GetCameraComponent()->OrthoWidth, 444.f);
	World->DestroyWorld(false);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunBellFeedbackTextTest, "Catrun.LevelFlow.ExactBellDenial", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunBellFeedbackTextTest::RunTest(const FString&)
{
	TestEqual(TEXT("Native and BP feedback share the exact required copy"), UCatrunNoticeSubsystem::BellDeniedText().ToString(), FString(TEXT("방울을 울릴수없습니다")));
	return true;
}
#endif
