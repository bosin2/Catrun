#include "CatrunPuzzleReset.h"
#include "CatrunPuzzleSuspension.h"
#include "CatrunStatuePuzzle.h"
#include "CatrunBasketInteractionComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/PointLightComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "LevelFlow/CatrunLevelFlow.h"
#include "Monster/CatrunRestartSubsystem.h"
#include "Sound/CatrunNotice.h"
#include "UObject/ConstructorHelpers.h"

ACatrunPuzzleReset::ACatrunPuzzleReset()
{
	SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
	Pedestal = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Pedestal"));
	Pedestal->SetupAttachment(RootComponent);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Shape(TEXT("/Engine/BasicShapes/Cylinder"));
	Pedestal->SetStaticMesh(Shape.Object);
	Pedestal->SetRelativeScale3D(FVector(.5,.5,.16));
	Pedestal->SetRelativeLocation(FVector(0,0,8));
	// A small floor marker, not a new routing obstacle.
	Pedestal->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	auto* Light = CreateDefaultSubobject<UPointLightComponent>(TEXT("RecoveryGlow"));
	Light->SetupAttachment(RootComponent);
	Light->SetRelativeLocation(FVector(0,0,40));
	Light->SetLightColor(FLinearColor(.25f,.7f,1.f));
	Light->SetIntensity(35);
	Light->SetAttenuationRadius(120);
	Light->SetCastShadows(false);
}

bool ACatrunPuzzleReset::CanInteract(APawn* Cat) const
{
	if (UCatrunPuzzleSuspension::IsSuspended(this)) return false;
	if (!Cat || !IsValid(Puzzle) || PuzzleId.IsNone() || FVector::DistSquared(Cat->GetActorLocation(), GetActorLocation()) > FMath::Square(InteractionRange)) return false;
	const auto* Actions = Cat->FindComponentByClass<UCatrunBasketInteractionComponent>();
	if (Actions && (Actions->Busy || Actions->IsHidden)) return false;
	FHitResult Hit;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(RecoveryReach), false, Cat);
	Params.AddIgnoredActor(this);
	return !GetWorld()->LineTraceSingleByChannel(Hit, Cat->GetActorLocation(), GetActorLocation()+FVector(0,0,25), ECC_Visibility, Params);
}

ACatrunPuzzleReset* ACatrunPuzzleReset::FindNearby(APawn* Cat)
{
	if (!Cat) return nullptr;
	ACatrunPuzzleReset* Best = nullptr;
	double Distance = TNumericLimits<double>::Max();
	for (TActorIterator<ACatrunPuzzleReset> It(Cat->GetWorld()); It; ++It)
		if (It->CanInteract(Cat) && FVector::DistSquared(Cat->GetActorLocation(), It->GetActorLocation()) < Distance)
		{
			Best = *It;
			Distance = FVector::DistSquared(Cat->GetActorLocation(), It->GetActorLocation());
		}
	return Best;
}

bool ACatrunPuzzleReset::TryUse(APawn* Cat)
{
	if (Cat != UGameplayStatics::GetPlayerPawn(this, 0) || !CanInteract(Cat)) return false;
	if (auto* Flow = UCatrunLevelFlowSubsystem::Get(this); Flow && (Flow->IsTransitioning() || Flow->IsStageComplete())) return false;
	if (auto* Restart = UCatrunRestartSubsystem::Get(this); Restart && Restart->IsCatching()) return false;
	const bool bReset = Puzzle->ResetStatue(PuzzleId);
	if (auto* Notice = UCatrunNoticeSubsystem::Get(this))
		Notice->ShowNotice(bReset ? FText::FromString(TEXT("이 방의 동상을 원위치로 되돌렸습니다."))
			: FText::FromString(TEXT("동상의 처음 위치가 막혀 있습니다. 자리를 비운 뒤 다시 사용하세요.")), 3.f);
	return bReset;
}
