#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "CatrunPuzzleReset.generated.h"

class ACatrunStatuePuzzle;
class UStaticMeshComponent;

/** A local, physical recovery interaction. Never resets enemies, marks or other rooms. */
UCLASS()
class CATRUN_API ACatrunPuzzleReset : public AActor
{
	GENERATED_BODY()
public:
	ACatrunPuzzleReset();
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly) TObjectPtr<UStaticMeshComponent> Pedestal;
	UPROPERTY(EditInstanceOnly, BlueprintReadOnly, Category="Recovery") TObjectPtr<ACatrunStatuePuzzle> Puzzle;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Recovery") FName PuzzleId;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Recovery", meta=(ClampMin="30")) float InteractionRange = 105.f;
	UFUNCTION(BlueprintCallable, Category="Recovery") bool TryUse(APawn* Cat);
	UFUNCTION(BlueprintPure, Category="Recovery") bool CanInteract(APawn* Cat) const;
	static ACatrunPuzzleReset* FindNearby(APawn* Cat);
};
