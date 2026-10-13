#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "CatrunSoundVisualLibrary.generated.h"

class ASoundGridManager;
class UTexture2D;

// 소리 한 번의 전파 결과를 보관하는 데이터 묶음.
// 파동 블루프린트의 변수에 저장해서 사용한다.
USTRUCT(BlueprintType)
struct CATRUN_API FCatrunSoundVisualSnapshot
{
	GENERATED_BODY()

	// 전파 거리와 도달 여부 등을 숫자로 저장한 텍스처.
	UPROPERTY(BlueprintReadOnly, Category = "Sound|Visual")
	TObjectPtr<UTexture2D> DistanceTexture = nullptr;

	// 텍스처가 실제 맵의 어느 영역에 해당하는지 나타낸다.
	// R: 시작 X, G: 시작 Y, B: 가로 길이, A: 세로 길이.
	// 좌표와 길이의 단위는 모두 cm이다.
	UPROPERTY(BlueprintReadOnly, Category = "Sound|Visual")
	FLinearColor GridRect = FLinearColor(0.f, 0.f, 1.f, 1.f);

	// 소리 전파 격자 한 칸의 크기.
	UPROPERTY(BlueprintReadOnly, Category = "Sound|Visual")
	float CellSizeCm = 25.f;
};

// 블루프린트에서 사용할 소리 시각화 함수를 제공한다.
UCLASS()
class CATRUN_API UCatrunSoundVisualLibrary
	: public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	// OnSoundEmitted 이벤트를 받자마자 한 번 호출한다.
	// Delay 이후에는 다른 소리의 결과로 바뀌었을 수 있다.
	// Budget에는 같은 소리 이벤트에서 받은 값을 넣는다.
	// 성공하면 true를 반환하고 Snapshot에 결과를 저장한다.
	UFUNCTION(BlueprintCallable, Category = "Sound|Visual",
		meta = (DisplayName = "Capture Latest Sound Visual"))
	static bool CaptureLatestSoundVisual(
		ASoundGridManager* SoundManager,
		float Budget,
		FCatrunSoundVisualSnapshot& Snapshot);
};