#if WITH_DEV_AUTOMATION_TESTS && PLATFORM_WINDOWS
#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "LevelFlow/CatrunAtomicSaveGame.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "LevelFlow/CatrunProgressSave.h"
#include "LevelFlow/CatrunProgressWriter.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Guid.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Misc/ScopeExit.h"
#include "UObject/Package.h"

namespace
{
constexpr TCHAR ProcessRootPrefix[] = TEXT("CatrunStageProgressProcess-");
constexpr TCHAR ProcessSlot[] = TEXT("CatrunProgress");
const FString ProcessTutorial(TEXT("/Game/Maps/Tutorial"));
const FString ProcessStage1(TEXT("/Game/Maps/Stage1"));
const FString ProcessStage2(TEXT("/Game/Maps/Stage2"));

FString NormalizeProcessPath(const FString& Path)
{
	FString Result = FPaths::ConvertRelativePathToFull(Path);
	FPaths::NormalizeDirectoryName(Result);
	return Result;
}

struct FProgressSlotPathAccess : FCatrunAtomicSaveGameSystem
{
	static FString GetBackendPath(FCatrunAtomicSaveGameSystem& Backend)
	{
		// Call the inherited virtual on the real backend selected by the writer.
		return (Backend.*(&FProgressSlotPathAccess::GetSaveGamePath))(ProcessSlot);
	}
};

class FProgressProcessWorld
{
public:
	explicit FProgressProcessWorld(UGameInstance& Instance, const TCHAR* ShortName)
	{
		const FString Directory = TEXT("/Temp/CatrunProgressProcess/") + FGuid::NewGuid().ToString(EGuidFormats::Digits);
		const auto Init = UWorld::InitializationValues().AllowAudioPlayback(false).CreatePhysicsScene(false)
			.CreateNavigation(false).CreateAISystem(false);
		World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, CreatePackage(*(Directory / ShortName)),
			true, ERHIFeatureLevel::Num, &Init);
		GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
		World->SetGameInstance(&Instance);
	}

	~FProgressProcessWorld()
	{
		World->SetGameInstance(nullptr);
		GEngine->DestroyWorldContext(World);
		World->DestroyWorld(false);
	}

	UCatrunLevelFlowSubsystem* GetFlow() const { return World->GetSubsystem<UCatrunLevelFlowSubsystem>(); }
	FString GetPackage() const { return World->GetOutermost()->GetName(); }

	FString TakeTravelURL() const
	{
		FWorldContext* Context = GEngine->GetWorldContextFromWorld(World);
		FString URL = MoveTemp(Context->TravelURL);
		Context->TravelURL.Reset();
		return URL;
	}

	bool TrackStageFixture(UCatrunFlowSession& Session) const
	{
		// Bind the fixture's current source world package before calling its normal
		// exit entry point. The destination stays the configured production package.
		const FString Package = GetPackage();
		Session.AcceptTravel(Package, true, false, ECatrunArrivalRestart::Preserve);
		Session.Arrive(Package);
		return Session.IsTrackingWorld(Package);
	}

private:
	UWorld* World = nullptr;
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCatrunStageProgressCrossProcessTest, "Catrun.LevelFlow.StageProgressCrossProcess",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FCatrunStageProgressCrossProcessTest::RunTest(const FString&)
{
	const TCHAR* CommandLine = FCommandLine::Get();
	FString Mode;
	if (!FParse::Value(CommandLine, TEXT("CatrunProgressProcessMode="), Mode))
	{
		AddInfo(TEXT("Skipped: cross-process progress requires the opt-in runner and isolated -UserDir."));
		return true;
	}
	const bool bWrite = Mode == TEXT("write");
	const bool bRead = Mode == TEXT("read");
	const bool bReset = Mode == TEXT("reset");
	const bool bReadReset = Mode == TEXT("readreset");
	if (!TestTrue(TEXT("A supported cross-process mode was requested"), bWrite || bRead || bReset || bReadReset)) return false;

	FString RunRoot;
	if (!TestTrue(TEXT("Opt-in run requires an absolute run root and -SaveToUserDir"),
		FParse::Value(CommandLine, TEXT("CatrunProgressProcessRoot="), RunRoot) && !RunRoot.IsEmpty()
		&& !FPaths::IsRelative(RunRoot) && FParse::Param(CommandLine, TEXT("SaveToUserDir")))) return false;
	RunRoot = NormalizeProcessPath(RunRoot);
	const FString RunFolderName = FPaths::GetCleanFilename(RunRoot);
	FGuid RunId;
	FString Marker;
	if (!TestTrue(TEXT("Run root contains the runner's unique isolation marker"),
		RunFolderName.StartsWith(ProcessRootPrefix)
		&& FGuid::ParseExact(RunFolderName.RightChop(UE_ARRAY_COUNT(ProcessRootPrefix) - 1), EGuidFormats::Digits, RunId)
		&& FFileHelper::LoadFileToString(Marker, *(RunRoot / TEXT("progress-process.marker")))
		&& Marker.TrimStartAndEnd().Equals(RunId.ToString(EGuidFormats::Digits), ESearchCase::IgnoreCase))) return false;
	const FString UserDir = NormalizeProcessPath(RunRoot / TEXT("User"));
	const FString SavedDir = NormalizeProcessPath(UserDir / TEXT("Saved"));
	const FString ExpectedSlot = NormalizeProcessPath(SavedDir / TEXT("SaveGames/CatrunProgress.sav"));
	FString UserDirArgument;
	if (!TestTrue(TEXT("UE resolved the custom user directory and saved directory to the isolated root"),
		FParse::Value(CommandLine, TEXT("UserDir="), UserDirArgument) && !UserDirArgument.IsEmpty()
		&& !FPaths::IsRelative(UserDirArgument) && NormalizeProcessPath(UserDirArgument).Equals(UserDir, ESearchCase::IgnoreCase)
		&& NormalizeProcessPath(FPaths::ProjectUserDir()).Equals(UserDir, ESearchCase::IgnoreCase)
		&& NormalizeProcessPath(FPaths::ProjectSavedDir()).Equals(SavedDir, ESearchCase::IgnoreCase))) return false;
	bool bAtomic = false;
	auto* Backend = FCatrunProgressWriter::GetPlatformBackend(&bAtomic);
	if (!TestTrue(TEXT("The production Windows atomic backend is active"), Backend && bAtomic)) return false;
	auto& AtomicBackend = *static_cast<FCatrunAtomicSaveGameSystem*>(Backend);
	if (!TestTrue(TEXT("The actual default backend targets only the isolated slot"),
		NormalizeProcessPath(FProgressSlotPathAccess::GetBackendPath(AtomicBackend)).Equals(ExpectedSlot, ESearchCase::IgnoreCase))) return false;
	const auto Existence = Backend->DoesSaveGameExistWithResult(ProcessSlot, 0);
	const auto ExpectedExistence = bWrite ? ISaveGameSystem::ESaveExistsResult::DoesNotExist : ISaveGameSystem::ESaveExistsResult::OK;
	if (!TestTrue(TEXT("Write requires a fresh slot and reopen modes require an existing slot"), Existence == ExpectedExistence)) return false;
	AddInfo(FString::Printf(TEXT("Cross-process stage progress [%s] using '%s'"), *Mode, *ExpectedSlot));

	const auto* Settings = GetDefault<UCatrunLevelFlowSettings>();
	const FName Stage1Id(TEXT("Stage1")), Stage2Id(TEXT("Stage2"));
	const float Stage1Budget = Settings->GetClockBudget(Stage1Id), Stage2Budget = Settings->GetClockBudget(Stage2Id);
	const float Stage1Elapsed = FMath::Min(13.125f, Stage1Budget * .25f);
	const float Stage2Elapsed = Stage2Budget * .25f;
	const int32 Stage1AllocationMs = FMath::RoundToInt32(double(Stage1Budget) * 1000.);
	const int32 ExpectedStage1Ms = FMath::RoundToInt32(Stage1AllocationMs - double(Stage1Elapsed) * 1000.);

	auto* Instance = NewObject<UGameInstance>();
	Instance->Init();
	ON_SCOPE_EXIT { Instance->Shutdown(); };
	auto* Session = Instance->GetSubsystem<UCatrunFlowSession>();
	if (!TestNotNull(TEXT("Game instance initializes the real flow session"), Session)) return false;

	if (bWrite)
	{
		{
			FProgressProcessWorld Menu(*Instance, TEXT("ProgressMenu"));
			if (!TestTrue(TEXT("New Game requests native tutorial travel"), Menu.GetFlow()->StartGame())
				|| !TestEqual(TEXT("New Game targets the shipped Tutorial package"), Menu.TakeTravelURL(), ProcessTutorial)
				|| !TestTrue(TEXT("Matching Tutorial arrival is tracked"), Session->Arrive(ProcessTutorial))) return false;
		}
		Session->MarkOnboardingCompleted(ProcessTutorial);
		{
			FProgressProcessWorld Tutorial(*Instance, TEXT("Tutorial"));
			if (!TestTrue(TEXT("Tutorial fixture binds source-world tracking"), Tutorial.TrackStageFixture(*Session))
				|| !TestTrue(TEXT("Tutorial completion requests Stage1"), Tutorial.GetFlow()->CompleteStage())
				|| !TestEqual(TEXT("Tutorial completion targets the shipped Stage1 package"), Tutorial.TakeTravelURL(), ProcessStage1 + TEXT("?FromTutorial"))
				|| !TestTrue(TEXT("Matching Stage1 arrival is tracked"), Session->Arrive(ProcessStage1))) return false;
		}
		{
			FProgressProcessWorld Stage1(*Instance, TEXT("Stage1"));
			if (!TestTrue(TEXT("Stage1 fixture binds source-world tracking"), Stage1.TrackStageFixture(*Session))) return false;
			Session->AdvanceClock(Stage1Elapsed);
			if (!TestTrue(TEXT("Stage1 completion requests Stage2"), Stage1.GetFlow()->CompleteStage())
				|| !TestEqual(TEXT("Stage1 completion targets the shipped Stage2 package"), Stage1.TakeTravelURL(), ProcessStage2)
				|| !TestTrue(TEXT("Matching Stage2 arrival is tracked"), Session->Arrive(ProcessStage2))) return false;
		}
		TestTrue(TEXT("Accepted Stage2 chapter arrival schedules the existing checkpoint"), Session->SaveCurrentCheckpoint(ProcessStage2) != 0);
		Session->AdvanceClock(Stage2Elapsed);
		TestEqual(TEXT("Stage2 still counts down during the live attempt"), Session->GetRemainingSeconds(Stage2Id), Stage2Budget - Stage2Elapsed);
		TestTrue(TEXT("Chapter write is pending at the orderly shutdown boundary"), Session->IsSavePending());
		return true;
	}

	const auto* Disk = Session->LoadSavedProgress();
	if (!TestNotNull(TEXT("A fresh process can read the slot through the production decoder"), Disk)) return false;
	TestEqual(TEXT("The slot is written using schema v4"), Disk->SchemaVersion, UCatrunProgressSave::CurrentSchemaVersion);
	TestEqual(TEXT("The slot retains Stage2 as the Continue target"), Disk->StageId, Stage2Id);
	TestEqual(TEXT("The slot retains the Stage2 unlock"), Disk->HighestUnlockedStageId, Stage2Id);
	TestTrue(TEXT("The slot retains completed onboarding"), Disk->HasCompletedOnboarding());
	TestEqual(TEXT("The slot preserves exact Stage1 time"), Disk->Stage1RemainingMs, ExpectedStage1Ms);
	TestEqual(TEXT("The chapter slot omits Stage2 remaining time"), Disk->Stage2RemainingMs, -1);
	TestEqual(TEXT("The chapter slot omits Stage2 solves"), Disk->Stage2SolvedMask, 0);
	{
		FProgressProcessWorld Menu(*Instance, TEXT("ProgressMenu"));
		if (!TestTrue(TEXT("Continue starts from the freshly loaded slot"), Menu.GetFlow()->ContinueGame())
			|| !TestEqual(TEXT("Continue requests the ordinary Stage2 map URL"), Menu.TakeTravelURL(), ProcessStage2)) return false;
		TestFalse(TEXT("Matching unchanged Continue does not request another save"), Session->Arrive(ProcessStage2));
	}
	TestTrue(TEXT("Continue tracks the arriving stage"), Session->IsTrackingWorld(ProcessStage2));
	TestEqual(TEXT("Continue grants the full Stage2 clock"), Session->GetRemainingSeconds(Stage2Id), Stage2Budget);
	TestEqual(TEXT("Continue still carries the saved Stage1 clock"),
		FMath::RoundToInt32(double(Session->GetRemainingSeconds(Stage1Id)) * 1000.), ExpectedStage1Ms);
	TestFalse(TEXT("Reading and continuing do not leave a write pending"), Session->IsSavePending());

	if (bReset)
	{
		FProgressProcessWorld Stage2(*Instance, TEXT("Stage2"));
		if (!TestTrue(TEXT("Stage2 fixture binds source-world tracking"), Stage2.TrackStageFixture(*Session))) return false;
		Session->AdvanceClock(Stage2Elapsed);
		if (!TestTrue(TEXT("Native manual restart admits a full stage reset"), Stage2.GetFlow()->RestartStage())
			|| !TestEqual(TEXT("Manual restart reloads the matching stage"), Stage2.TakeTravelURL(), Stage2.GetPackage())) return false;
		TestEqual(TEXT("Restart admission leaves the old world's clock unchanged"), Session->GetRemainingSeconds(Stage2Id), Stage2Budget - Stage2Elapsed);
		TestFalse(TEXT("Stage2 reset arrival does not request a checkpoint"), Session->Arrive(Stage2.GetPackage()));
		TestEqual(TEXT("Stage2 reset arrival grants its full clock"), Session->GetRemainingSeconds(Stage2Id), Stage2Budget);
	}
	if (bRead)
	{
		FProgressProcessWorld Stage2(*Instance, TEXT("Stage2"));
		if (!TestTrue(TEXT("Stage2 fixture binds source-world tracking"), Stage2.TrackStageFixture(*Session))) return false;
		Session->AdvanceClock(Stage2Elapsed);
		if (!TestTrue(TEXT("Stage2 can return to the menu without an intermediate checkpoint"), Stage2.GetFlow()->ReturnToMenu())) return false;
		TestFalse(TEXT("Menu arrival requests no save"), Session->Arrive(Stage2.TakeTravelURL()));
	}
	TestFalse(TEXT("Stage2 clock, reset and menu do not enqueue a write"), Session->IsSavePending());
	return true;
}
#endif
