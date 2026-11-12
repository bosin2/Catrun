#pragma once

#include "Kismet/BlueprintFunctionLibrary.h"
#include "CatrunAuthoringLibrary.generated.h"

/** Small editor-commandlet bridge for deterministic, static asset captures. */
UCLASS()
class CATRUN_API UCatrunAuthoringLibrary : public UBlueprintFunctionLibrary
{

	GENERATED_BODY()
public:
	/** Finish queued meshes, textures and shaders before an offscreen capture. */
	UFUNCTION(BlueprintCallable, Category="Catrun|Editor Authoring", meta=(DevelopmentOnly))
	static bool FinishAssetCompilation();
};
