#pragma once
#include "CoreMinimal.h"
#include "InputCoreTypes.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Subsystems/LocalPlayerSubsystem.h"
#include "Tickable.h"
#include "CatrunInputBindings.generated.h"
class UInputMappingContext;
UENUM(BlueprintType)
enum class ECatrunInputSlot : uint8 { Forward, Back, Left, Right, Run, Sneak, Bell, Interact };
USTRUCT(BlueprintType)
struct CATRUN_API FCatrunKeyboardBindings
{
 GENERATED_BODY()
 UPROPERTY(EditAnywhere, BlueprintReadWrite) TArray<FKey> Keys;
 FCatrunKeyboardBindings();
 FKey Get(ECatrunInputSlot Slot) const;
 bool Validate(FText& Error) const;
 bool operator==(const FCatrunKeyboardBindings& Other) const { return Keys == Other.Keys; }
 bool operator!=(const FCatrunKeyboardBindings& Other) const { return !(*this == Other); }
};
UCLASS()
class CATRUN_API UCatrunInputBindings : public UBlueprintFunctionLibrary
{
 GENERATED_BODY()
public:
 UFUNCTION(BlueprintPure, Category="Catrun|Settings") static FKey GetEffectiveKey(ECatrunInputSlot Slot);
 UFUNCTION(BlueprintPure, Category="Catrun|Settings") static FText GetEffectiveKeyLabel(ECatrunInputSlot Slot);
 static bool IsKeyboardKey(FKey Key);
 static FVector2D GetMovementInput(TFunctionRef<bool(FKey)> IsDown);
 // Only known authored gameplay contexts are cloned; all non-key mapping data remains intact.
 static bool IsGameplayContext(const UInputMappingContext* Context);
 static void RemapContext(UInputMappingContext* Copy, const UInputMappingContext* Original, const FCatrunKeyboardBindings& Bindings);
};

class UEnhancedInputLocalPlayerSubsystem;
class UEnhancedPlayerInput;
/** Local clones follow late Blueprint context additions and player-input replacement on travel. */
UCLASS()
class CATRUN_API UCatrunInputBindingSubsystem : public ULocalPlayerSubsystem, public FTickableGameObject
{
 GENERATED_BODY()
public:
 virtual void Initialize(FSubsystemCollectionBase& Collection) override;
 virtual void Deinitialize() override;
 virtual void Tick(float DeltaTime) override;
 virtual TStatId GetStatId() const override;
 virtual bool IsTickable() const override;
 virtual bool IsTickableWhenPaused() const override { return true; }
 virtual UWorld* GetTickableGameObjectWorld() const override { return GetWorld(); }
 void RefreshBindings();
private:
 UFUNCTION() void ContextAdded(const UInputMappingContext* Context);
 UFUNCTION() void ContextRemoved(const UInputMappingContext* Context);
 UPROPERTY(Transient) TMap<TObjectPtr<UInputMappingContext>, TObjectPtr<UInputMappingContext>> ContextCopies;
 TWeakObjectPtr<UEnhancedInputLocalPlayerSubsystem> InputSubsystem;
 TWeakObjectPtr<UEnhancedPlayerInput> LastPlayerInput;
 FCatrunKeyboardBindings LastBindings;
 FDelegateHandle BindingsChangedHandle;
 bool bReplacing = false;
};
