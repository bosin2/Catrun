#include "Catrun.h"

#include "Engine/Engine.h"
#include "HAL/IConsoleManager.h"
#include "Misc/CoreDelegates.h"
#include "Misc/PackageName.h"
#include "Modules/ModuleManager.h"

DEFINE_LOG_CATEGORY(LogCatrunSound);

namespace
{
	// While the monster systems are built in copies of the team's maps, the game must open the
	// copies instead of the originals, without changing the team's blueprints (the main menu
	// widget opens the level "Tutorial" by name). The redirect can be switched off in the console:
	//   catrun.LevelRedirects 0
	TAutoConsoleVariable<int32> CVarLevelRedirects(
		TEXT("catrun.LevelRedirects"), 1,
		TEXT("1 = the game opens the sound test copies (SoundTest_*) instead of the original maps listed in Catrun.cpp."));

	struct FLevelRedirect
	{
		const TCHAR* ShortName;	// the level as the team's blueprints name it
		const TCHAR* Target;	// the copy to open instead (long package name)
	};

	const FLevelRedirect LevelRedirects[] =
	{
		{ TEXT("Tutorial"), TEXT("/Game/Maps/SoundTest_Tutorial") },
	};

	// Runs at the start of every frame. A level change that a blueprint asked for in the last frame
	// is waiting in the world context as TravelURL; if it points to an original map, point it to
	// the copy (options after a '?' are kept).
	void RedirectPendingTravel()
	{
		if (!GEngine || CVarLevelRedirects.GetValueOnGameThread() == 0)
		{
			return;
		}
		for (const FWorldContext& ReadOnlyContext : GEngine->GetWorldContexts())
		{
			// The engine only hands out read-only contexts, but the travel request has to be changed.
			FWorldContext& Context = const_cast<FWorldContext&>(ReadOnlyContext);
			if (Context.TravelURL.IsEmpty())
			{
				continue;
			}
			FString Map = Context.TravelURL;
			FString Options;
			const int32 OptionsStart = Map.Find(TEXT("?"));
			if (OptionsStart != INDEX_NONE)
			{
				Options = Map.Mid(OptionsStart);
				Map.LeftInline(OptionsStart);
			}
			const FString ShortName = FPackageName::GetShortName(Map);
			for (const FLevelRedirect& Redirect : LevelRedirects)
			{
				if (ShortName.Equals(Redirect.ShortName, ESearchCase::IgnoreCase))
				{
					UE_LOG(LogCatrunSound, Log, TEXT("Level redirect: %s -> %s"), *Context.TravelURL, Redirect.Target);
					Context.TravelURL = FString(Redirect.Target) + Options;
					break;
				}
			}
		}
	}
}

class FCatrunModule : public FDefaultGameModuleImpl
{
public:
	virtual void StartupModule() override
	{
		BeginFrameHandle = FCoreDelegates::OnBeginFrame.AddStatic(&RedirectPendingTravel);
	}

	virtual void ShutdownModule() override
	{
		FCoreDelegates::OnBeginFrame.Remove(BeginFrameHandle);
	}

private:
	FDelegateHandle BeginFrameHandle;
};

IMPLEMENT_PRIMARY_GAME_MODULE(FCatrunModule, Catrun, "Catrun");
