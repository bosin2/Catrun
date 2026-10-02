#pragma once

#include "CoreMinimal.h"
#include "UObject/Interface.h"
#include "SoundTypes.generated.h"

// Design doc 1.1 / 3.3: loudness grade used directly by minion decisions.
UENUM(BlueprintType)
enum class ECatrunSoundSize : uint8
{
	Small	UMETA(DisplayName = "Small (小)"),
	Medium	UMETA(DisplayName = "Medium (中)"),
	Large	UMETA(DisplayName = "Large (大)")
};

UENUM(BlueprintType)
enum class ECatrunSoundKind : uint8
{
	Bell,
	Footstep,
	Device
};

UENUM(BlueprintType)
enum class ECatrunSoundSource : uint8
{
	Cat,
	Armor,
	Device
};

// Who is allowed to hear the sound (design doc 3.3: armor footsteps are Cat-only).
UENUM(BlueprintType)
enum class ECatrunSoundTarget : uint8
{
	Minion,
	Cat
};

USTRUCT(BlueprintType)
struct FCatrunSoundEvent
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	ECatrunSoundSource Source = ECatrunSoundSource::Cat;

	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	ECatrunSoundKind Kind = ECatrunSoundKind::Bell;

	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	ECatrunSoundSize Size = ECatrunSoundSize::Large;

	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	ECatrunSoundTarget Target = ECatrunSoundTarget::Minion;

	// World location snapshot taken at the moment the sound is made.
	// Listeners use this as a destination, never the emitter's live position.
	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FVector Location = FVector::ZeroVector;

	UPROPERTY(BlueprintReadWrite)
	TObjectPtr<AActor> Instigator = nullptr;
};

UINTERFACE(BlueprintType, MinimalAPI)
class UCatrunSoundListener : public UInterface
{
	GENERATED_BODY()
};

// Implement on any actor that can hear sounds (armor, candle, cat).
class ICatrunSoundListener
{
	GENERATED_BODY()

public:
	// Which sounds this listener receives (Minion for armor/candle, Cat for the player).
	UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "Sound")
	ECatrunSoundTarget GetListenerGroup() const;

	// RemainingBudget is the sound budget left at the listener's position (always > 0 here).
	UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "Sound")
	void OnSoundHeard(const FCatrunSoundEvent& Event, float RemainingBudget);
};
