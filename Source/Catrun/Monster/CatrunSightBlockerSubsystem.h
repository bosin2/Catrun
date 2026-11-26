#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "CatrunSightBlockerSubsystem.generated.h"

class UPrimitiveComponent;

/**
 * Components whose simple collision (not only their render triangles) blocks sight.
 *
 * Sight normally traces complex (render) geometry. A hidden gameplay proxy, such as a Stage 3 counterweight's
 * statue mesh inside a 120x120x150 box, would leak sight beside the visible block. Such proxies register here and
 * CatrunPerception::SightDistance also tests their simple collision. An empty registry costs nothing.
 */
UCLASS()
class CATRUN_API UCatrunSightBlockerSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	static UCatrunSightBlockerSubsystem* Get(const UWorld* World);

	void Register(UPrimitiveComponent& Component);
	bool IsRegistered(const UPrimitiveComponent* Component) const;
	// Number of live registered components (stale entries pruned).
	int32 Num();
	// Live registered components (stale entries pruned).
	const TArray<TWeakObjectPtr<UPrimitiveComponent>>& GetBlockers();

private:
	void Prune();

	TArray<TWeakObjectPtr<UPrimitiveComponent>> Blockers;
};
