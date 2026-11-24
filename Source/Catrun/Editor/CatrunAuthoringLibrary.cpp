#include "Editor/CatrunAuthoringLibrary.h"

#if WITH_EDITOR
#include "AssetCompilingManager.h"
#include "Components/SkyLightComponent.h"
#include "Engine/Engine.h"
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

bool UCatrunAuthoringLibrary::RefreshSkyLighting(const UObject* WorldContext)
{
#if WITH_EDITOR
	if (!IsRunningCommandlet() || !IsInGameThread() || !GEngine) return false;
	UWorld* World=GEngine->GetWorldFromContextObject(WorldContext,EGetWorldErrorMode::ReturnNull);
	if (!World) return false;
	USkyLightComponent::UpdateSkyCaptureContents(World);
	return true;
#else
	return false;
#endif
}
