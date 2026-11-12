#include "Editor/CatrunAuthoringLibrary.h"

#if WITH_EDITOR
#include "AssetCompilingManager.h"
#endif

bool UCatrunAuthoringLibrary::FinishAssetCompilation()
{
#if WITH_EDITOR
	// This tool never waits on assets from a gameplay Blueprint or render worker.
	if (!IsRunningCommandlet() || !IsInGameThread()) return false;
	FAssetCompilingManager::Get().FinishAllCompilation();
	return true;
#else
	return false;
#endif
}
