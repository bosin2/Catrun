#pragma once

#include "CoreMinimal.h"
#include "Engine/DeveloperSettings.h"
#include "GameFramework/Actor.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Subsystems/WorldSubsystem.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "CatrunLevelFlow.generated.h"

class UBoxComponent;
class UCatrunNoticeWidget;
class UCatrunPlayHUD;
class UCameraComponent;
class USpringArmComponent;

/** A single-use travel token. A different destination discards it rather than leaking into a later run. */
struct CATRUN_API FCatrunRestartIntent
{
	FString MapPackage;
	float FadeInDuration = 0.f;
	void Request(const FString& Package, float FadeDuration);
	void Clear();
	bool Consume(const FString& Package, float& OutFadeDuration);
};

/** Travel state belongs to one game session, including isolated PIE instances. */
UCLASS()
class CATRUN_API UCatrunFlowSession : public UGameInstanceSubsystem
{
	GENERATED_BODY()
public:
	FCatrunRestartIntent RestartIntent;
};

USTRUCT(BlueprintType)
struct FCatrunStageCameraProfile
{
	GENERATED_BODY()
	UPROPERTY(EditAnywhere, BlueprintReadOnly) FName StageId;
	/** Orthographic width or perspective spring-arm length multiplier, relative to authored values. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, meta=(ClampMin="1.0", ClampMax="3.0")) float DistanceScale = 1.f;
};

USTRUCT(BlueprintType)
struct FCatrunStageRoute
{
	GENERATED_BODY()
	UPROPERTY(EditAnywhere, BlueprintReadOnly)
	FName StageId;
	UPROPERTY(EditAnywhere, BlueprintReadOnly)
	TSoftObjectPtr<UWorld> Map;
};

/** Ordered playable maps. Add Stage3 only when its map is ready. */
UCLASS(Config=Game, DefaultConfig, meta=(DisplayName="Catrun Level Flow"))
class CATRUN_API UCatrunLevelFlowSettings : public UDeveloperSettings
{
	GENERATED_BODY()
public:
	UCatrunLevelFlowSettings();
	UPROPERTY(Config, EditAnywhere, Category="Maps")
	TSoftObjectPtr<UWorld> MainMenuMap;
	UPROPERTY(Config, EditAnywhere, Category="Maps")
	TArray<FCatrunStageRoute> Stages;
	UPROPERTY(Config, EditAnywhere, Category="Camera")
	TArray<FCatrunStageCameraProfile> CameraProfiles;

	int32 FindStageIndex(const FString& PackageName) const;
	float GetCameraDistanceScale(FName StageId) const;
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FCatrunStageCompleted, FName, StageId);

/** Rules and travel are native; existing Blueprint cinematics call the library when finished. */
UCLASS()
class CATRUN_API UCatrunLevelFlowSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()
public:
	static UCatrunLevelFlowSubsystem* Get(const UObject* WorldContextObject);
	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void Deinitialize() override;
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;

	bool StartGame();
	bool CompleteStage();
	bool ReturnToMenu();
	bool RestartStage();
	/** Stable for this world: consuming the travel token never changes subsequent BP query results. */
	UFUNCTION(BlueprintCallable, Category="Level Flow")
	bool ShouldSkipStageIntro();
	float GetRestartFadeInDuration();
	bool ApplyStageCameraProfile(UCameraComponent* Camera, USpringArmComponent* SpringArm);
	UFUNCTION(BlueprintCallable, Category="Level Flow")
	void SetPauseMenu(bool bOpen);
	bool IsTransitioning() const { return bTransitioning; }
	bool IsStageComplete() const { return bStageComplete; }

	UPROPERTY(BlueprintAssignable, Category="Level Flow")
	FCatrunStageCompleted OnStageCompleted;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Level Flow")
	bool bStageComplete = false;

private:
	bool TravelTo(const TSoftObjectPtr<UWorld>& Map, const FString& Options = FString());
	void FinishTravel();
	void ResolveRestartIntent();
	bool bRestartIntentResolved = false;
	bool bSkipStageIntro = false;
	float RestartFadeInDuration = 0.f;
	TWeakObjectPtr<UCameraComponent> GameplayCamera;
	TWeakObjectPtr<USpringArmComponent> GameplaySpringArm;
	float AuthoredOrthoWidth = 0.f;
	float AuthoredArmLength = 0.f;
	bool bTransitioning = false;
	FString PendingMap;
	FString PendingOptions;
	UPROPERTY(Transient)
	TObjectPtr<UCatrunPlayHUD> PlayHUD;
};

UCLASS()
class CATRUN_API UCatrunLevelFlowLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()
public:
	UFUNCTION(BlueprintCallable, Category="Catrun|Level Flow", meta=(WorldContext="WorldContextObject"))
	static bool StartNewGame(const UObject* WorldContextObject);
	UFUNCTION(BlueprintCallable, Category="Catrun|Level Flow", meta=(WorldContext="WorldContextObject"))
	static bool CompleteCurrentStage(const UObject* WorldContextObject);
	UFUNCTION(BlueprintCallable, Category="Catrun|Level Flow", meta=(WorldContext="WorldContextObject"))
	static bool ReturnToMainMenu(const UObject* WorldContextObject);
	UFUNCTION(BlueprintCallable, Category="Catrun|Level Flow", meta=(WorldContext="WorldContextObject"))
	static bool RestartCurrentStage(const UObject* WorldContextObject);
	UFUNCTION(BlueprintCallable, Category="Catrun|Level Flow", meta=(WorldContext="WorldContextObject"))
	static bool ShouldSkipStageIntro(const UObject* WorldContextObject);
	/** Call only on the restart branch, using the original intro's final playable transform. */
	UFUNCTION(BlueprintCallable, Category="Catrun|Level Flow", meta=(WorldContext="WorldContextObject"))
	static bool RestorePlayableStart(const UObject* WorldContextObject, APawn* Pawn, const FTransform& PlayableTransform, AActor* GameplayViewTarget = nullptr);
	/** Pass the pawn camera or original BP_QuarterViewCamera/tagged CatrunGameplayCamera, never a cinematic camera. */
	UFUNCTION(BlueprintCallable, Category="Catrun|Camera", meta=(WorldContext="WorldContextObject"))
	static bool ApplyStageCameraProfile(const UObject* WorldContextObject, UCameraComponent* Camera, USpringArmComponent* SpringArm);
};

/** Place at an existing doorway. Only the locally controlled cat can complete the stage. */
UCLASS()
class CATRUN_API ACatrunStageExit : public AActor
{
	GENERATED_BODY()
public:
	ACatrunStageExit();
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Exit")
	TObjectPtr<UBoxComponent> Trigger;
	UFUNCTION(BlueprintCallable, Category="Exit")
	bool TryCompleteFor(APawn* Pawn);
private:
	UFUNCTION()
	void HandleOverlap(AActor* OverlappedActor, AActor* OtherActor);
};
