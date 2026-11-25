#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "Monster/CatrunArmor.h"

// Stage3 갑옷 6기는 새로 배치되면서 맵마다 켜 주던 범위 표시를 받지 못했다.
// 배치 작업에 기대지 않도록 기본값과 실제 배치 블루프린트가 모두 표시를 켠 상태여야 한다.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FArmorRangeDefaultTest, "Catrun.Monsters.NewArmorShowsCatchRangeByDefault",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FArmorRangeDefaultTest::RunTest(const FString&)
{
	UClass* Placed = LoadClass<ACatrunArmor>(nullptr, TEXT("/Game/Characters/LivingArmor/Blueprints/BP_LivingArmor.BP_LivingArmor_C"));
	if (!TestNotNull(TEXT("Placed armor blueprint loads"), Placed)) return false;
	const ACatrunArmor* Defaults[] = { GetDefault<ACatrunArmor>(), GetDefault<ACatrunArmor>(Placed) };
	for (const ACatrunArmor* Armor : Defaults)
	{
		TestTrue(*FString::Printf(TEXT("%s shows its catch range"), *Armor->GetName()), Armor->bShowDetectionDisplay);
		TestTrue(*FString::Printf(TEXT("%s range is not transparent"), *Armor->GetName()), Armor->DetectionDisplayOpacity > 0.05f);
	}
	return true;
}

#endif
