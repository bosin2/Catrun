#include "Editor/CatrunAuthoringLibrary.h"

#if WITH_EDITOR
#include "AssetCompilingManager.h"
#include "Components/SkyLightComponent.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "ImageUtils.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "UnrealClient.h"
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

bool UCatrunAuthoringLibrary::CaptureGameViewport(const UObject* WorldContext, const FString& Filename)
{
#if WITH_EDITOR
	if (!IsInGameThread() || !GEngine) return false;
	UWorld* World = GEngine->GetWorldFromContextObject(WorldContext, EGetWorldErrorMode::ReturnNull);
	if (!World || World->WorldType != EWorldType::PIE) return false;
	APlayerController* Controller = UGameplayStatics::GetPlayerController(World, 0);
	ULocalPlayer* Player = Controller ? Controller->GetLocalPlayer() : nullptr;
	FViewport* Viewport = Player && Player->ViewportClient ? Player->ViewportClient->Viewport : nullptr;
	if (!Viewport) return false;

	// Review artifacts are new files under this checkout, even with an isolated UserDir.
	FString Output = FPaths::ConvertRelativePathToFull(Filename);
	if (!FPaths::CollapseRelativeDirectories(Output)) return false;
	const FString SavedRoot = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir() / TEXT("Saved"));
	if (!FPaths::IsUnderDirectory(Output, SavedRoot) ||
		!FPaths::GetExtension(Output).Equals(TEXT("png"), ESearchCase::IgnoreCase) ||
		IFileManager::Get().FileExists(*Output)) return false;

	const FIntPoint Size = Viewport->GetRenderTargetTextureSizeXY();
	TArray<FColor> Pixels;
	if (Size.X <= 0 || Size.Y <= 0 || !GetViewportScreenShot(Viewport, Pixels) ||
		Pixels.Num() != int64(Size.X) * Size.Y) return false;
	for (FColor& Pixel : Pixels) Pixel.A = 255;
	TArray64<uint8> Png;
	FImageUtils::PNGCompressImageArray(Size.X, Size.Y, Pixels, Png);
	return !Png.IsEmpty() && IFileManager::Get().MakeDirectory(*FPaths::GetPath(Output), true) &&
		FFileHelper::SaveArrayToFile(Png, *Output);
#else
	return false;
#endif
}
