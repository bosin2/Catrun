#pragma once
#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "CatrunPuzzleSuspension.generated.h"

class UCharacterMovementComponent;
class USkeletalMeshComponent;

/** One short puzzle reveal owns this guard. Gameplay timers remain at their current values. */
UCLASS()
class CATRUN_API UCatrunPuzzleSuspension : public UTickableWorldSubsystem
{
	GENERATED_BODY()
public:
	static UCatrunPuzzleSuspension* Get(const UObject* Context);
	UFUNCTION(BlueprintPure, Category="Puzzle|Reveal", meta=(WorldContext="Context"))
	static bool IsSuspended(const UObject* Context);
	bool Acquire(UObject* Owner);
	void Release(const UObject* Owner);
	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;
	virtual void Deinitialize() override;
private:
	void FreezeActors();
	void Restore();
	TWeakObjectPtr<UObject> RevealOwner;
	bool bAcquired = false;
	// Only components that we actually changed are restored.
	TArray<TWeakObjectPtr<UCharacterMovementComponent>> Movements;
	TArray<TWeakObjectPtr<USkeletalMeshComponent>> Meshes;
};
