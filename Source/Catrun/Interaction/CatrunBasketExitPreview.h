#pragma once
#include "CoreMinimal.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "CatrunBasketExitPreview.generated.h"

USTRUCT(BlueprintType)
struct FCatrunBasketPreviewStyle
{
	GENERATED_BODY()
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Preview", meta=(ClampMin="0"))
	float ArcHeight = 90.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Preview", meta=(ClampMin="0", ClampMax="1"))
	float DashOpacity = .45f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Preview", meta=(ClampMin="0", ClampMax="1"))
	float CircleOpacity = .20f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Preview", meta=(ClampMin="1"))
	float CircleRadius = 12.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Preview", meta=(ClampMin=".1"))
	float LineWidth = 2.4f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Preview")
	FLinearColor Color = FLinearColor(.65f, 1.3f, 1.7f);
};

/** 메시 인스턴스 48개를 재사용하고, 경로가 달라질 때만 배치를 갱신한다. */
UCLASS()
class CATRUN_API UCatrunBasketExitPreview : public UInstancedStaticMeshComponent
{
	GENERATED_BODY()
public:
	UCatrunBasketExitPreview();
	void ShowPath(const FVector& Start, const FVector& End, const FCatrunBasketPreviewStyle& Style);
	void HidePath();
private:
	FVector LastStart = FVector::ZeroVector;
	FVector LastEnd = FVector::ZeroVector;
	bool bHasPath = false;
};
