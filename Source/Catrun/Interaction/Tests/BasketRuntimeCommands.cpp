#if WITH_DEV_AUTOMATION_TESTS
#include "HAL/IConsoleManager.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "InputKeyEventArgs.h"

// Process-local offscreen integration tests use the real player input path.
// Not compiled into Shipping; no production tick, state, or key interception.
static FAutoConsoleCommandWithWorldAndArgs BasketTestKey(
 TEXT("Catrun.Basket.TestKey"), TEXT("Automation: <key> <down|up>"),
 FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args,UWorld* World)
 {
  if (!World || !World->IsGameWorld() || Args.Num()!=2) return;
  if (APlayerController* PC=World->GetFirstPlayerController())
  {
   const bool bDown=Args[1].Equals(TEXT("down"),ESearchCase::IgnoreCase);
   PC->InputKey(FInputKeyEventArgs(nullptr,INPUTDEVICEID_NONE,FKey(*Args[0]),bDown ? IE_Pressed : IE_Released,bDown ? 1.f : 0.f,false,0));
  }
 }));
#endif
