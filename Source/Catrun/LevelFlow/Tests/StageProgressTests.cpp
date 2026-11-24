#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "LevelFlow/CatrunProgressSave.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "CatrunCheckpointTestBackend.h"

namespace
{
const FString Stage1Package(TEXT("/Game/Maps/Stage1"));
const FString Stage2Package(TEXT("/Game/Maps/Stage2"));

UCatrunFlowSession* StageProgressSession(FCheckpointBackend& Backend)
{
	auto* Session = NewObject<UCatrunFlowSession>(NewObject<UGameInstance>());
	Session->SetSaveBackendForTest(&Backend, FSimpleDelegate::CreateLambda([&Backend] { Backend.Drain(); }));
	return Session;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunStageProgressMutationTest, "Catrun.LevelFlow.StageProgressStage1ResetOrdering", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunStageProgressMutationTest::RunTest(const FString&)
{
	FCheckpointBackend Backend;
	auto* Seed = NewObject<UCatrunProgressSave>();
	Seed->SchemaVersion = UCatrunProgressSave::CurrentSchemaVersion;
	Seed->StageId = Seed->HighestUnlockedStageId = TEXT("Stage2");
	Seed->Stage1RemainingMs = 123456;
	Seed->Stage2RemainingMs = 654321;
	Seed->Stage2SolvedMask = UCatrunProgressSave::AllPuzzleBits;
	Seed->bTutorialOnboardingCompleted = true;
	UGameplayStatics::SaveGameToMemory(Seed, Backend.Bytes);
	auto* Session = StageProgressSession(Backend);
	Session->AcceptTravel(Stage1Package, true, true, ECatrunArrivalRestart::Continue);
	Session->Arrive(Stage1Package);
	TestTrue(TEXT("Stage1 Continue reads its saved remaining time"), FMath::IsNearlyEqual(Session->GetRemainingSeconds(TEXT("Stage1")), 123.456f));
	Session->AdvanceClock(7.125f);
	Session->SaveCurrentCheckpoint(Stage1Package);
	Backend.Step();
	Backend.Step(); // The original elapsed-time write callback will arrive after the reset.
	const uint64 FailedReset = Session->AcceptTravel(Stage1Package, false, false, ECatrunArrivalRestart::SkipIntro, -1, 0.f, ECatrunProgressArrival::ResetStage);
	Session->CancelTravel(FailedReset);
	TestTrue(TEXT("Cancelled Stage1 reset retains current time"), FMath::IsNearlyEqual(Session->GetRemainingSeconds(TEXT("Stage1")), 116.331f));
	Session->AcceptTravel(Stage1Package, false, false, ECatrunArrivalRestart::SkipIntro, -1, 0.f, ECatrunProgressArrival::ResetStage);
	TestTrue(TEXT("Matching Stage1 reset arrival requests persistence"), Session->Arrive(Stage1Package));
	Session->SaveCurrentCheckpoint(Stage1Package);
	Backend.Drain();
	const auto* Reset = UCatrunProgressSave::Decode(Backend.Bytes);
	if (!TestNotNull(TEXT("Reset emits a strict v4 slot"), Reset)) return false;
	const double Budget = GetDefault<UCatrunLevelFlowSettings>()->GetClockBudget(TEXT("Stage1"));
	TestEqual(TEXT("Late Stage1 clock callback cannot undo the refill"), Reset->Stage1RemainingMs, FMath::RoundToInt32(Budget * 1000.));
	TestEqual(TEXT("Stage1 reset retains Stage2 unlock"), Reset->HighestUnlockedStageId, FName(TEXT("Stage2")));
	TestTrue(TEXT("Stage1 reset retains onboarding"), Reset->HasCompletedOnboarding());
	TestEqual(TEXT("New checkpoints omit old Stage2 remaining time"), Reset->Stage2RemainingMs, -1);
	TestEqual(TEXT("New checkpoints omit old Stage2 solves"), Reset->Stage2SolvedMask, 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunStageProgressFlushTest, "Catrun.LevelFlow.StageProgressPendingMenuAndShutdownDurability", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunStageProgressFlushTest::RunTest(const FString&)
{
	for (const bool bMenu : {false, true})
	{
		FCheckpointBackend Backend;
		Backend.bExists = false;
		auto* Session = StageProgressSession(Backend);
		Session->AcceptTravel(Stage1Package, true, true, ECatrunArrivalRestart::Continue);
		Session->Arrive(Stage1Package);
		Session->AdvanceClock(5.25f);
		Session->SaveCurrentCheckpoint(Stage1Package);
		Backend.Step(); // The platform owns the previous checkpoint write callback.
		Session->AdvanceClock(3.5f);
		const int32 ExpectedRemaining = FMath::RoundToInt32(double(Session->GetRemainingSeconds(TEXT("Stage1"))) * 1000.);
		if (bMenu)
		{
			Session->FlushTrackedProgress();
			Session->Arrive(TEXT("/Game/Maps/MainMenu"));
			TestTrue(TEXT("Continue must wait while last time write is pending"), Session->IsSavePending());
			TestEqual(TEXT("Continue stage comes from the session even before the first disk write"), Session->GetContinueStageId(), FName(TEXT("Stage1")));
			Backend.Drain();
			TestFalse(TEXT("Continue is reopened when final write settles"), Session->IsSavePending());
		}
		else
		{
			TestTrue(TEXT("Earlier checkpoint write is outstanding at quit"), Session->IsSavePending());
			Session->Deinitialize();
			TestTrue(TEXT("Shutdown returns only after both writes settle"), Backend.Pending.IsEmpty() && !Session->IsSavePending());
		}
		const auto* Saved = UCatrunProgressSave::Decode(Backend.Bytes);
		if (!TestNotNull(TEXT("Slot is immediately readable at the flush boundary"), Saved)) return false;
		TestEqual(TEXT("Flush records latest elapsed Stage1 time"), Saved->Stage1RemainingMs, ExpectedRemaining);
		auto* Reopened = StageProgressSession(Backend);
		Reopened->AcceptTravel(Stage1Package, true, false, ECatrunArrivalRestart::Continue);
		Reopened->Arrive(Stage1Package);
		TestEqual(TEXT("A new session resumes exact saved Stage1 milliseconds"),
			FMath::RoundToInt32(double(Reopened->GetRemainingSeconds(TEXT("Stage1"))) * 1000.), ExpectedRemaining);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunStageProgressShutdownRetryTest, "Catrun.LevelFlow.StageProgressShutdownRetriesPendingStage1Checkpoint", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunStageProgressShutdownRetryTest::RunTest(const FString&)
{
	FCheckpointBackend Backend;
	Backend.bExists = false;
	Backend.WriteResults = {false, true};
	auto* Session = StageProgressSession(Backend);
	Session->AcceptTravel(Stage1Package, true, false, ECatrunArrivalRestart::Continue);
	Session->Arrive(Stage1Package);
	Session->AdvanceClock(7.25f);
	const int32 ExpectedRemainingMs = FMath::RoundToInt32(double(Session->GetRemainingSeconds(TEXT("Stage1"))) * 1000.);
	Session->SaveCurrentCheckpoint(Stage1Package);
	Backend.Step(); // The platform write will fail once.
	TestTrue(TEXT("The Stage1 checkpoint is still pending at shutdown"), Session->IsSavePending());
	Session->Deinitialize();
	TestEqual(TEXT("Shutdown retries the newest operation exactly once"), Backend.Writes, 2);
	TestEqual(TEXT("Retry occurs after removing the failed partial slot"), Backend.Deletes, 1);
	TestFalse(TEXT("Shutdown drains the retry"), Session->IsSavePending());
	const auto* Save = UCatrunProgressSave::Decode(Backend.Bytes);
	if (!TestNotNull(TEXT("Immediate reopen sees a valid Stage1 checkpoint"), Save)) return false;
	TestEqual(TEXT("Retry includes the last elapsed time without another clock tick"), Save->Stage1RemainingMs, ExpectedRemainingMs);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunResumeWithoutWriteTest, "Catrun.LevelFlow.StageProgressSameChapterContinueNeedsNoWrite", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunResumeWithoutWriteTest::RunTest(const FString&)
{
	const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false);
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Init);
	auto& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
	Context.SetCurrentWorld(World);
	auto* Instance = NewObject<UGameInstance>();
	World->SetGameInstance(Instance);
	Instance->Init();
	FCheckpointBackend Backend;
	auto* Save = NewObject<UCatrunProgressSave>();
	Save->SchemaVersion = UCatrunProgressSave::CurrentSchemaVersion;
	Save->StageId = Save->HighestUnlockedStageId = TEXT("Stage2");
	Save->Stage1RemainingMs = 123456;
	Save->Stage2RemainingMs = 234567;
	Save->Stage2SolvedMask = UCatrunProgressSave::AllPuzzleBits;
	Save->bTutorialOnboardingCompleted = true;
	UGameplayStatics::SaveGameToMemory(Save, Backend.Bytes);
	const TArray<uint8> Original = Backend.Bytes;
	auto* Session = Instance->GetSubsystem<UCatrunFlowSession>();
	Session->SetSaveBackendForTest(&Backend);

	auto* Flow = World->GetSubsystem<UCatrunLevelFlowSubsystem>();
	TestTrue(TEXT("Continue admits the stored chapter"), Flow->ContinueGame());
	TestEqual(TEXT("Continue uses the ordinary stage map"), Context.TravelURL, Stage2Package);
	TestFalse(TEXT("Matching unchanged continue requires no arrival save"), Session->Arrive(Stage2Package));
	TestTrue(TEXT("Track the resumed stage despite the absence of an arrival save"), Session->IsTrackingWorld(Stage2Package));
	const auto* Settings = GetDefault<UCatrunLevelFlowSettings>();
	const float Stage2Budget = Settings->GetClockBudget(TEXT("Stage2"));
	TestEqual(TEXT("Continue ignores legacy Stage2 time and grants full budget"), Session->GetRemainingSeconds(TEXT("Stage2")), Stage2Budget);
	TestTrue(TEXT("Legacy Stage1 time stays available"), FMath::IsNearlyEqual(Session->GetRemainingSeconds(TEXT("Stage1")), 123.456f));
	TestTrue(TEXT("Legacy onboarding stays available"), Session->HasCompletedOnboarding());
	for (const auto Reason : {ECatrunProgressArrival::FailureRefill, ECatrunProgressArrival::ResetStage})
	{
		Session->AdvanceClock(Stage2Budget * .5f);
		TestEqual(TEXT("Active Stage2 clock still counts down"), Session->GetRemainingSeconds(TEXT("Stage2")), Stage2Budget * .5f);
		Session->AcceptTravel(Stage2Package, false, false, ECatrunArrivalRestart::SkipIntro, -1, 0.f, Reason);
		TestFalse(TEXT("Stage2 restart arrives without a checkpoint"), Session->Arrive(Stage2Package));
		TestEqual(TEXT("Stage2 restart grants full time"), Session->GetRemainingSeconds(TEXT("Stage2")), Stage2Budget);
	}
	Session->AdvanceClock(Stage2Budget * .25f);
	Session->FlushTrackedProgress();
	Session->Arrive(TEXT("/Game/Maps/MainMenu"));
	TestTrue(TEXT("Stage2 continue, restarts, clock and menu do not write"), Backend.Writes == 0 && Backend.Bytes == Original && !Session->IsSavePending());
	Context.TravelURL.Reset();
	Instance->Shutdown();
	TestTrue(TEXT("Stage2 shutdown leaves the legacy slot byte-identical"), Backend.Writes == 0 && Backend.Bytes == Original);
	World->SetGameInstance(nullptr);
	GEngine->DestroyWorldContext(World);
	World->DestroyWorld(false);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunStageProgressSchemaTest, "Catrun.LevelFlow.StageProgressStrictLegacyAndInvalidBytes", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunStageProgressSchemaTest::RunTest(const FString&)
{
	for (int32 Version : {1, 2, 3})
	{
		auto* Legacy = NewObject<UCatrunProgressSave>();
		Legacy->SchemaVersion = Version;
		Legacy->StageId = TEXT("Stage1");
		Legacy->HighestUnlockedStageId = Version >= 3 ? FName(TEXT("Stage2")) : NAME_None;
		Legacy->bTutorialOnboardingCompleted = Version >= 2;
		TArray<uint8> Bytes;
		UGameplayStatics::SaveGameToMemory(Legacy, Bytes);
		const ANSICHAR NewTag[] = "Stage2SolvedMask";
		bool bNewTagPresent = false;
		for (int32 Offset = 0; Offset + int32(sizeof(NewTag)) <= Bytes.Num(); ++Offset)
			if (FMemory::Memcmp(Bytes.GetData() + Offset, NewTag, sizeof(NewTag)) == 0)
			{
				bNewTagPresent = true;
				break;
			}
		TestFalse(TEXT("Actual legacy payload has no v4 puzzle tag"), bNewTagPresent);
		const auto* Decoded = UCatrunProgressSave::Decode(Bytes);
		if (!TestNotNull(TEXT("Legacy bytes pass the strict decoder"), Decoded)) return false;
		TestEqual(TEXT("Legacy schema defaults and tags survive"), Decoded->SchemaVersion, Version);
		TestEqual(TEXT("Legacy milliseconds have an unset sentinel"), Decoded->Stage2RemainingMs, -1);
		TestEqual(TEXT("Legacy saves do not invent a solved bit"), Decoded->Stage2SolvedMask, 0);
		TestEqual(TEXT("Legacy onboarding follows the original schema"), Decoded->HasCompletedOnboarding(), Version >= 2);
	}

	for (int32 InvalidValue : {-2, UCatrunProgressSave::MaxRemainingMs + 1})
	{
		auto* Invalid = NewObject<UCatrunProgressSave>();
		Invalid->SchemaVersion = UCatrunProgressSave::CurrentSchemaVersion;
		Invalid->StageId = TEXT("Stage2");
		Invalid->Stage2RemainingMs = InvalidValue;
		TArray<uint8> Bytes;
		UGameplayStatics::SaveGameToMemory(Invalid, Bytes);
		TestNull(TEXT("Invalid clock range fails strict decode"), UCatrunProgressSave::Decode(Bytes));
	}
	auto* BadMask = NewObject<UCatrunProgressSave>();
	BadMask->SchemaVersion = UCatrunProgressSave::CurrentSchemaVersion;
	BadMask->StageId = TEXT("Stage2");
	BadMask->Stage2SolvedMask = 8;
	FCheckpointBackend Backend;
	UGameplayStatics::SaveGameToMemory(BadMask, Backend.Bytes);
	const TArray<uint8> Original = Backend.Bytes;
	TestNull(TEXT("Unknown puzzle bits fail strict decode"), UCatrunProgressSave::Decode(Original));
	auto* Session = StageProgressSession(Backend);
	Session->AcceptTravel(Stage2Package, true, true, ECatrunArrivalRestart::Clear);
	Session->Arrive(Stage2Package);
	AddExpectedError(TEXT("Existing checkpoint or new payload could not be validated"), EAutomationExpectedErrorFlags::Contains, 1);
	Session->SaveCurrentCheckpoint(Stage2Package);
	Backend.Drain();
	TestTrue(TEXT("Invalid v4 baseline remains byte-identical"), Backend.Writes == 0 && Backend.Bytes == Original);
	return true;
}
#endif
