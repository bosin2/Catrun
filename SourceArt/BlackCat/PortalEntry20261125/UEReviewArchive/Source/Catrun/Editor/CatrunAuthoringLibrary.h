#pragma once

#include "Kismet/BlueprintFunctionLibrary.h"
#include "CatrunAuthoringLibrary.generated.h"

/** Editor-only bridges for asset preparation and deterministic review captures. */
UCLASS()
class CATRUN_API UCatrunAuthoringLibrary : public UBlueprintFunctionLibrary
{

	GENERATED_BODY()
public:
	/** Finish queued meshes, textures and shaders before an offscreen capture. */
	UFUNCTION(BlueprintCallable, Category="Catrun|Editor Authoring", meta=(DevelopmentOnly))
	static bool FinishAssetCompilation();
	/** Commandlets do not tick the editor's pending skylight capture queue. */
	UFUNCTION(BlueprintCallable, Category="Catrun|Editor Authoring", meta=(DevelopmentOnly, WorldContext="WorldContext"))
	static bool RefreshSkyLighting(const UObject* WorldContext);
	/** Read this PIE player's viewport directly; global Shot can capture an editor viewport. */
	UFUNCTION(BlueprintCallable, Category="Catrun|Editor Authoring", meta=(DevelopmentOnly, WorldContext="WorldContext"))
	static bool CaptureGameViewport(const UObject* WorldContext, const FString& Filename);
};
