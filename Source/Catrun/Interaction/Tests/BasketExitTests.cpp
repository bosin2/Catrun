#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Interaction/BasketExitMath.h"
#include "Interaction/CatrunHideBasket.h"
#include "Components/SceneComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBasketDirectionTest, "Catrun.Basket.CameraInputAndBlockedBack",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBasketDirectionTest::RunTest(const FString&)
{
	const FVector Front(1,0,0);
	const FVector Right = CatrunBasket::SelectDirection(-45,0,1,Front,Front);
	TestTrue(TEXT("D follows the quarter-view camera right axis"), Right.Equals(FVector(1,1,0).GetSafeNormal(),.001));
	const FVector Diagonal = CatrunBasket::SelectDirection(-45,1,1,Front,Front);
	TestTrue(TEXT("W+D combines into a normalized world direction"), Diagonal.Equals(Front,.001));
	TestTrue(TEXT("Key release preserves selection"), CatrunBasket::SelectDirection(-45,0,0,Right,Front).Equals(Right));
	TestTrue(TEXT("Back input cannot replace the last valid selection"), CatrunBasket::SelectDirection(0,-1,0,Right,Front).Equals(Right));
	TestTrue(TEXT("Opposing keys preserve selection"), CatrunBasket::SelectDirection(0,0,0,Right,Front).Equals(Right));
	const FVector RotatedFront(0,-1,0);
	TestTrue(TEXT("A rotated basket rejects world +Y"), CatrunBasket::SelectDirection(0,0,1,RotatedFront,RotatedFront).Equals(RotatedFront));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBasketArcTest, "Catrun.Basket.ArcEndpoints",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBasketArcTest::RunTest(const FString&)
{
	const FVector A(0,0,58), B(82,0,3);
	TestTrue(TEXT("Arc begins above the basket"), CatrunBasket::ArcPoint(A,B,90,0).Equals(A));
	TestTrue(TEXT("Arc ends at landing circle"), CatrunBasket::ArcPoint(A,B,90,1).Equals(B));
	TestTrue(TEXT("Middle rises above both endpoints"), CatrunBasket::ArcPoint(A,B,90,.5).Z>A.Z);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBasketFiveDirectionsTest, "Catrun.Basket.ExactlyFiveDirectionsAtAnyRotation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBasketFiveDirectionsTest::RunTest(const FString&)
{
	for (float CameraYaw : {-135.f, -45.f, 0.f, 17.f, 90.f})
	{
		for (int32 Yaw = -180; Yaw < 180; ++Yaw)
		{
			const FVector Opening = FRotator(0, Yaw, 0).Vector();
			int32 Allowed = 0;
			for (int32 Sector = 0; Sector < 8; ++Sector)
			{
				const FVector Direction = FRotator(0, CameraYaw + Sector * 45.f, 0).Vector();
				Allowed += CatrunBasket::IsDirectionAllowed(Direction, Opening, CameraYaw) ? 1 : 0;
			}
			if (Allowed != 5)
			{
				AddError(FString::Printf(TEXT("Camera %.1f, basket %d: expected five directions, got %d"), CameraYaw, Yaw, Allowed));
				return false;
			}
			TestFalse(TEXT("Directly behind the opening is blocked"),
				CatrunBasket::IsDirectionAllowed(-Opening, Opening, CameraYaw));
		}
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FBasketConfiguredDirectionTest, "Catrun.Basket.ExplicitDirectionOverridesCloth",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FBasketConfiguredDirectionTest::RunTest(const FString&)
{
	// 사용자 맵을 건드리지 않는 임시 월드에서 실제 바구니의 출구 계산을 검사한다.
	const UWorld::InitializationValues Settings = UWorld::InitializationValues().AllowAudioPlayback(false)
		.CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false);
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true,
		ERHIFeatureLevel::Num, &Settings);
	ACatrunHideBasket* Basket = World->SpawnActor<ACatrunHideBasket>();
	if (!TestNotNull(TEXT("Basket spawns"), Basket))
	{
		World->DestroyWorld(false);
		return false;
	}
	USceneComponent* Root = NewObject<USceneComponent>(Basket);
	Basket->SetRootComponent(Root);
	Root->RegisterComponent();
	USkeletalMesh* Mesh = LoadObject<USkeletalMesh>(nullptr,
		TEXT("/Game/Environment/Shared/Castle/Props/Hiding/HideBasket/Meshes/SK_HideBasket_Cloth.SK_HideBasket_Cloth"));
	TestNotNull(TEXT("Basket cloth asset loads"), Mesh);
	USkeletalMeshComponent* Cloth = NewObject<USkeletalMeshComponent>(Basket);
	Cloth->SetSkeletalMesh(Mesh);
	Basket->ExternalCloth = Cloth;
	Basket->OpenDirectionLocal = FVector(-1, 1, 0);
	const FVector ExpectedFront = FVector(-1, 1, 0).GetSafeNormal2D();
	for (float ClothYaw : {0.f, 90.f, 180.f, 270.f})
	{
		Cloth->SetWorldRotation(FRotator(0, ClothYaw, 0));
		TestTrue(TEXT("Explicit front does not follow the cloth bones or rotation"),
			Basket->GetOpenDirection().Equals(ExpectedFront, .001));
	}
	// 현재 창고 바구니: 카메라 -135도에서 A가 정면이면 W/WA/A/AS/S를 허용한다.
	const bool Allowed[8] = {true, false, false, false, true, true, true, true};
	for (int32 Sector = 0; Sector < 8; ++Sector)
	{
		const FVector Direction = FRotator(0, -135 + Sector * 45.f, 0).Vector();
		TestEqual(FString::Printf(TEXT("Storage basket input sector %d"), Sector),
			CatrunBasket::IsDirectionAllowed(Direction, Basket->GetOpenDirection(), -135), Allowed[Sector]);
	}
	const FVector South = FRotator(0, 45, 0).Vector();
	TestTrue(TEXT("S replaces A when A is the configured front"),
		CatrunBasket::SelectDirection(-135, -1, 0, ExpectedFront, Basket->GetOpenDirection()).Equals(South, .001));
	Basket->SetActorRotation(FRotator(0, 90, 0));
	Basket->SetActorScale3D(FVector(2, 3, 1));
	TestTrue(TEXT("Rotating the basket rotates its configured front; size does not distort it"),
		Basket->GetOpenDirection().Equals(FVector(-1, -1, 0).GetSafeNormal2D(), .001));
	Basket->OpenDirectionLocal = FVector::ZeroVector;
	TestFalse(TEXT("An unset direction cannot enable an exit"),
		CatrunBasket::IsDirectionAllowed(South, Basket->GetOpenDirection(), -135));
	World->DestroyWorld(false);
	return true;
}
#endif
