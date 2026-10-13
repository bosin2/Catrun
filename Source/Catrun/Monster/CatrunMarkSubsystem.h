#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "CatrunMarkSubsystem.generated.h"

class ACatrunArmor;
class UPointLightComponent;
class UStaticMeshComponent;

/**
 * The candle mark (design doc 4.5). A candle that sees the cat puts a mark on it.
 *
 * While the cat is marked:
 *  - the closest armor knows where the cat really is and keeps coming for it,
 *  - a red orb floats above the cat so the player can see the mark.
 * The mark ends only when the cat goes into a hideout. It is gone after a level restart too
 * (the level is opened again, so this subsystem starts fresh).
 *
 * Which armors follow, and the sound, are provisional (to be discussed with the team), so every
 * number is a setting in DA_SoundSettings ("Mark" category).
 */
UCLASS()
class CATRUN_API UCatrunMarkSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	static UCatrunMarkSubsystem* Get(const UObject* WorldContextObject);

	// Puts the mark on the cat (nothing happens if it is already marked).
	void ApplyMark(APawn& Cat);
	void ClearMark(const TCHAR* Reason);
	bool IsMarked() const { return bMarked; }

	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual bool IsTickable() const override { return bMarked && Super::IsTickable(); }
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;

private:
	void CreateVisual(APawn& Cat);
	void DestroyVisual();
	void UpdateVisual();
	void UpdateFollowingArmor(const APawn& Cat);

	bool bMarked = false;
	float FollowTimer = 0.f;

	TWeakObjectPtr<ACatrunArmor> FollowingArmor;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMeshComponent> Orb;

	UPROPERTY(Transient)
	TObjectPtr<UPointLightComponent> Light;

	float OrbHeight = 80.f;
};
