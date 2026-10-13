#include "CatrunBasketExitPreview.h"
#include "BasketExitMath.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"

UCatrunBasketExitPreview::UCatrunBasketExitPreview()
{
	PrimaryComponentTick.bCanEverTick = false;
	SetCollisionEnabled(ECollisionEnabled::NoCollision);
	SetGenerateOverlapEvents(false);
	SetCastShadow(false);
	SetCanEverAffectNavigation(false);
	NumCustomDataFloats = 1;
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Mesh(TEXT("/Engine/BasicShapes/Sphere"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> Material(TEXT("/Game/Systems/Interaction/Hiding/Visual/M_BasketExitArc"));
	SetStaticMesh(Mesh.Object);
	SetMaterial(0, Material.Object);
	SetVisibility(false);
}

void UCatrunBasketExitPreview::HidePath()
{
	SetVisibility(false);
	bHasPath = false;
}

void UCatrunBasketExitPreview::ShowPath(const FVector& Start, const FVector& End, const FCatrunBasketPreviewStyle& Style)
{
	if (bHasPath && LastStart.Equals(Start, .1) && LastEnd.Equals(End, .1)) return;
	TArray<FTransform> Transforms;
	Transforms.Reserve(48);
	auto Segment = [&](const FVector& A, const FVector& B)
	{
		const FVector Delta = B - A;
		Transforms.Emplace(Delta.Rotation(), (A+B)*.5,
			FVector(Delta.Size()/100., Style.LineWidth/100., Style.LineWidth/100.));
	};
	for (int32 Index=0; Index<16; ++Index)
	{
		Segment(CatrunBasket::ArcPoint(Start, End, Style.ArcHeight, Index/16.f),
			CatrunBasket::ArcPoint(Start, End, Style.ArcHeight, Index/16.f+.04f));
	}
	for (int32 Index=0; Index<32; ++Index)
	{
		const float A = Index * UE_TWO_PI / 32.f;
		const float B = (Index+1) * UE_TWO_PI / 32.f;
		Segment(End + FVector(FMath::Cos(A), FMath::Sin(A), 0)*Style.CircleRadius,
			End + FVector(FMath::Cos(B), FMath::Sin(B), 0)*Style.CircleRadius);
	}
	if (GetInstanceCount() != Transforms.Num())
	{
		ClearInstances();
		AddInstances(Transforms, false, true, false);
	}
	else
	{
		BatchUpdateInstancesTransforms(0, Transforms, true, false, true);
	}
	for (int32 Index=0; Index<Transforms.Num(); ++Index)
		SetCustomDataValue(Index, 0, Index<16 ? Style.DashOpacity : Style.CircleOpacity, false);
	UMaterialInstanceDynamic* MID = Cast<UMaterialInstanceDynamic>(GetMaterial(0));
	if (!MID) MID = CreateDynamicMaterialInstance(0);
	if (MID) MID->SetVectorParameterValue(TEXT("GuideColor"), Style.Color);
	MarkRenderStateDirty();
	SetVisibility(true);
	LastStart = Start;
	LastEnd = End;
	bHasPath = true;
}
