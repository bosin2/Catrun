#include "CatrunRestartSubsystem.h"

#include "Camera/PlayerCameraManager.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"

namespace
{
	// Survives the level change (see the class comment).
	bool bFadeInPending = false;
	float PendingFadeInDuration = 1.f;
}

UCatrunRestartSubsystem* UCatrunRestartSubsystem::Get(const UObject* WorldContextObject)
{
	const UWorld* World = GEngine ? GEngine->GetWorldFromContextObject(WorldContextObject, EGetWorldErrorMode::ReturnNull) : nullptr;
	return World ? World->GetSubsystem<UCatrunRestartSubsystem>() : nullptr;
}

bool UCatrunRestartSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	const UWorld* World = Cast<UWorld>(Outer);
	return World && World->IsGameWorld();
}

bool UCatrunRestartSubsystem::TryBeginCatch()
{
	if (bCatching)
	{
		return false;
	}
	bCatching = true;
	return true;
}

void UCatrunRestartSubsystem::FadeOut(APawn* Cat, float Duration)
{
	APlayerController* Controller = Cat ? Cast<APlayerController>(Cat->GetController()) : UGameplayStatics::GetPlayerController(this, 0);
	if (Controller && Controller->PlayerCameraManager)
	{
		Controller->PlayerCameraManager->StartCameraFade(0.f, 1.f, Duration, FLinearColor::Black, false, true);
	}
}

void UCatrunRestartSubsystem::RestartLevel(float FadeInDuration)
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	bFadeInPending = true;
	PendingFadeInDuration = FadeInDuration;

	// The package name of a play-in-editor world starts with a prefix; the level to open does not.
	const FString LevelName = UWorld::RemovePIEPrefix(World->GetOutermost()->GetName());
	UGameplayStatics::OpenLevel(this, FName(*LevelName));
}

void UCatrunRestartSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);
	if (!bFadeInPending)
	{
		return;
	}
	bFadeInPending = false;

	// The new level starts black and fades in; the cat is at its start place again.
	APlayerController* Controller = UGameplayStatics::GetPlayerController(&InWorld, 0);
	if (Controller && Controller->PlayerCameraManager)
	{
		Controller->PlayerCameraManager->StartCameraFade(1.f, 0.f, PendingFadeInDuration, FLinearColor::Black, false, false);
	}
}
