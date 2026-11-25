# Blender 에셋 조사 기록 — 2026-11-24

## 조사 범위

- 원본: `C:/Users/whghk/Desktop/CastleKit`.
- 프로젝트: 현재 `3158/Catrun` 작업 폴더의 `Content`.
- Blender 5.2.1 백그라운드에서 백업 폴더를 제외한 blend 85개를 모두 열어 오브젝트·재질·UV·이미지 연결·액션 목록을 읽었다. 오류 0개. 원본 저장·수정은 하지 않았다.
- 아래 숫자는 파일 수다. 에셋 종류 수나 게임에서 사용 중인 개수가 아니다.
- `Backup`이 포함된 폴더의 16개 blend를 제외했다. 최상위 구버전·작업용 blend는 조사에 포함되므로, 85개 모두를 최종본으로 취급하지 않는다.
- FBX는 존재를 집계했으며 이번 조사에서는 재임포트하지 않았다. uasset는 파일명 대조만 했으며 현재 맵 참조·머터리얼 연결·충돌·성능을 검사한 것은 아니다.

| 파일 | 전체 | 백업 폴더 제외 |
|---|---:|---:|
| `.blend` | 101 | 85 |
| `.fbx` | 164 | 141 |
| `.png` | 311 | 278 |
| `.md` | 36 | 30 |
| `.json` | 40 | 25 |

## blend별 목록

`SM_/SK_ 메시`는 이름이 그 접두사로 시작하는 오브젝트다. 보조 메시·미리보기 바닥 등이 포함된 파일이 있어 메시 개수는 납품 개수와 다르다. 재질 상세와 대응 패키지 경로는 [CSV](AssetInventory_2026-11-24.csv)에 있다.

| 원본 상대 경로 | SM_/SK_ 메시 | 같은 이름의 uasset 수 |
|---|---|---:|
| `BanquetChair/SM_BanquetChair.blend` | SM_BanquetChair | 1 |
| `BanquetTable/SM_BanquetTable_Long.blend` | SM_BanquetTable_Long | 1 |
| `Barrel/SM_Barrel.blend` | SM_Barrel | 1 |
| `BeddingSet/SM_BeddingSet_A.blend` | SK_DemonKing_A; SM_Blanket_DemonBed_A; SM_DemonBed_A; SM_Pillow_Large_A; SM_Pillow_Large_A_02; SM_Pillow_Small_A | 6 |
| `BedroomDoor/SM_BedroomDoorSet_A.blend` | SM_BedroomDoorFrame_A; SM_BedroomDoorLeaf_A | 2 |
| `BedsideTable/SM_BedsideTable_A.blend` | SM_BedsideTable_A | 1 |
| `BlackCat/Final/SK_BlackCat_Final.blend` | SK_BlackCat_Final | 1 |
| `BlackCat/PortalCinematic/SK_BlackCat_PortalCinematic.blend` | SK_BlackCat_Final | 1 |
| `BlackCat/StairDown/SK_BlackCat_StairDown.blend` | SK_BlackCat_Final | 1 |
| `CandleMonster/SK_CandleMonster_A.blend` | SK_CandleMonster_A | 1 |
| `CastleKit.blend` | SM_Floor_Stone_A | 2 |
| `CatFoodBag/SM_CatFood_Bag.blend` | SM_CatFood_Bag | 1 |
| `CatFoodBowl/SM_CatBowl_Food.blend` | SM_CatBowl_Food | 1 |
| `CatLitterBox/SM_CatLitterBox.blend` | SM_CatLitterBox | 1 |
| `CatTower/SM_CatTower.blend` | SM_CatTower | 1 |
| `CatToyBox/SM_CatToyBox.blend` | SM_CatToyBox | 1 |
| `CatWaterBowl/SM_CatBowl_Water.blend` | SM_CatBowl_Water; SM_CatBowl_WaterSurface | 2 |
| `CrateA/SM_Crate_A.blend` | SM_Crate_A | 1 |
| `CurtainSet/SM_CurtainSet_A.blend` | SM_Curtain_L_A; SM_Curtain_R_A; SM_CurtainRod_A | 3 |
| `DemonBed/SM_DemonBed_A.blend` | SM_DemonBed_A | 1 |
| `DemonKing/SK_DemonKing_A.blend` | SK_DemonKing_A | 1 |
| `DemonKingChair/SM_DemonKingChair.blend` | SM_DemonKingChair | 1 |
| `Fireplace/SM_Fireplace_Gothic.blend` | SM_Fireplace_Gothic | 1 |
| `FloorCandelabrum/SM_Candelabrum_Floor.blend` | SM_Candelabrum_Floor | 1 |
| `GothicWindow/SM_GothicWindowSet_A.blend` | SM_GothicWindowFrame_A; SM_GothicWindowInsert_A | 2 |
| `GrainSack/SM_Sack_Grain.blend` | SM_Sack_Grain | 1 |
| `HangingRack/SM_HangingRack.blend` | SM_HangingRack | 1 |
| `HideBasket/SK_HideBasket_Cloth.blend` | SK_HideBasket_Cloth | 1 |
| `HideBasket/SM_HideBasket.blend` | SM_HideBasket | 1 |
| `IndoorPlanter/SM_Planter_Indoor.blend` | SM_Planter_Indoor | 1 |
| `KitchenCounter/SM_Kitchen_Counter.blend` | SM_Kitchen_Counter | 1 |
| `KitchenHearth/SM_Kitchen_Hearth.blend` | SM_Kitchen_Hearth | 1 |
| `KitchenShelf/SM_Shelf_Kitchen.blend` | SM_Shelf_Kitchen | 1 |
| `LivingArmor/Final/SK_LivingArmor_Final.blend` | SK_LivingArmor_Final | 1 |
| `LogBasket/SM_LogBasket.blend` | SM_LogBasket | 1 |
| `PortraitSmall/SM_Portrait_Small.blend` | SM_Portrait_Small | 1 |
| `PrepTable/SM_PrepTable.blend` | SM_PrepTable | 1 |
| `RugBanquet/SM_Rug_Banquet.blend` | SM_Rug_Banquet | 1 |
| `RugLarge/SM_Rug_Large_A.blend` | SM_Rug_Large_A | 1 |
| `RugRound/SM_Rug_Round.blend` | SM_Rug_Round | 1 |
| `RugRunner/SM_Rug_Runner.blend` | SM_Rug_Runner | 1 |
| `RugSmall/SM_Rug_Small.blend` | SM_Rug_Small | 1 |
| `Sideboard/SM_Sideboard.blend` | SM_Sideboard | 1 |
| `SideTable/SM_SideTable.blend` | SM_SideTable | 1 |
| `SM_Bookshelf.blend` | SM_Bookshelf | 1 |
| `SM_Rug_Large.blend` | SM_Rug_Large | 1 |
| `SM_Wall_Corner.blend` | SM_Wall_Corner | 1 |
| `SM_Wall_DoorFrame.blend` | SM_Wall_DoorFrame | 1 |
| `SM_Wall_Straight.blend` | SM_Wall_Straight | 1 |
| `SmallTable/SM_SmallTable_A.blend` | SM_SmallTable_A | 1 |
| `Sofa/SM_Sofa_A.blend` | SM_Sofa_A | 1 |
| `SofaCushion/SM_Cushion_Sofa.blend` | SM_Cushion_Sofa | 1 |
| `SofaGothic/SM_Sofa_Gothic.blend` | SM_Sofa_Gothic | 1 |
| `Stage1/CatHoleTrim/SM_CatHoleTrim_Stage1.blend` | SM_CatHoleTrim_Stage1 | 1 |
| `Stage2/CatHoleTrim/SM_CatHoleTrim_Stage2.blend` | SM_CatHoleTrim_Stage2 | 1 |
| `Stage2/Doors/ArchedIronDoor/SM_Stage2_ArchedIronDoor_Assembly.blend` | SM_Stage2_ArchedIronDoor_Frame; SM_Stage2_ArchedIronDoor_Leaf_L; SM_Stage2_ArchedIronDoor_Leaf_R | 3 |
| `Stage2/Doors/RisingGate/SM_Stage2_RisingGate_Assembly.blend` | SM_Stage2_RisingGate_Bars; SM_Stage2_RisingGate_Frame | 2 |
| `Stage2/Floors/SM_Stage2_Floor_A_Plain.blend` | SM_Stage2_Floor_A_Plain | 1 |
| `Stage2/Floors/SM_Stage2_Floor_B_ArcaneLine.blend` | SM_Stage2_Floor_B_ArcaneLine | 1 |
| `Stage2/Floors/SM_Stage2_Floor_C_RuneFragment.blend` | SM_Stage2_Floor_C_RuneFragment | 1 |
| `Stage2/PortalFrame/SM_PortalFrame_Stone.blend` | SM_PortalFrame_Runes; SM_PortalFrame_Stone | 2 |
| `Stage2/Props/ArcaneStone/SM_Stage2_ArcaneStone_Assembly.blend` | SM_Stage2_ArcaneStone_Core; SM_Stage2_ArcaneStone_Frame | 2 |
| `Stage2/Props/Bookshelf_Open/SM_Stage2_Bookshelf_Open.blend` | SM_Stage2_Bookshelf_Open | 1 |
| `Stage2/Props/PressurePlate/SM_Stage2_PressurePlate_Assembly.blend` | SM_Stage2_PressurePlate_Frame; SM_Stage2_PressurePlate_Plate | 2 |
| `Stage2/Props/PushStatue_Gargoyle/SM_Stage2_PushStatue_Gargoyle.blend` | SM_Stage2_PushStatue_Gargoyle | 1 |
| `Stage2/Props/Rug_Runner/SM_Stage2_Rug_Runner.blend` | SM_Stage2_Rug_Runner | 1 |
| `Stage2/Props/StarChart_Plaque/SM_Stage2_StarChart_Plaque.blend` | SM_Stage2_StarChart_Plaque | 1 |
| `Stage2/Props/Tapestry_CastleHistory/SM_Stage2_Tapestry_CastleHistory.blend` | SM_Stage2_Tapestry_CastleHistory | 1 |
| `Stage2/Props/Tapestry_Constellation/SM_Stage2_Tapestry_Constellation.blend` | SM_Stage2_Tapestry_Constellation | 1 |
| `Stage2/Props/Window_StainedGlass/SM_Stage2_Window_StainedGlass.blend` | SM_Stage2_Window_StainedGlass | 1 |
| `Stage2/Walls/SM_Stage2_Wall_A_Plain.blend` | SM_Stage2_Wall_A_Plain | 1 |
| `Stage2/Walls/SM_Stage2_Wall_B_Rune.blend` | SM_Stage2_Wall_B_Rune | 1 |
| `Stage2/Walls/SM_Stage2_Wall_C_Arcane.blend` | SM_Stage2_Wall_C_Arcane | 1 |
| `StoneBench/SM_Bench_Stone.blend` | SM_Bench_Stone | 1 |
| `StonePlanter/SM_Planter_Stone.blend` | SM_Planter_Stone | 1 |
| `StorageShelf/SM_Shelf_Storage.blend` | SM_Shelf_Storage | 1 |
| `StudyProps/SM_PropSet_Study_A.blend` | SM_BookBundle_Thin_A; SM_BookStack_Lying_A; SM_BookStack_Thick_A; SM_Bottle_Ink_A; SM_Bottle_Round_A; SM_Bottle_Tall_A; SM_WoodBox_Flat_A; SM_WoodBox_Tall_A | 8 |
| `SupplyCrates/SM_SupplyCrates_Large.blend` | SM_SupplyCrates_Large | 1 |
| `TableCandle/SM_Candle_Table.blend` | SM_Candle_Table | 1 |
| `TableDressing/SM_TableDressing_Set.blend` | SM_TableDressing_Set | 1 |
| `TapestryArmorGuardian/SM_Tapestry_ArmorGuardian.blend` | SM_Tapestry_ArmorGuardian | 1 |
| `TapestryCastle/SM_Tapestry_Castle.blend` | SM_Tapestry_Castle | 1 |
| `TapestryMoonGarden/SM_Tapestry_MoonGarden.blend` | SM_Tapestry_MoonGarden | 1 |
| `TorchWall/SM_Torch_Wall.blend` | SM_Torch_Wall | 1 |
| `WallSconce/SM_WallSconce_A.blend` | SM_WallSconce_A | 1 |

## 해석 시 주의

- 현재 포즈의 Skeletal Mesh 바운딩박스는 Rest Pose 크기가 아니다. 예를 들어 BlackCat Final의 저장 상태 치수와 제작 기록의 Rest Pose 치수가 다르므로 둘을 섞어 스케일을 고치지 않는다.
- 노드가 연결된 Principled 입력의 기본 숫자는 최종 재질값이 아니다. 실제 텍스처/노드 출력을 확인해야 한다.
- 같은 이름의 패키지가 있다는 사실만으로 해당 blend와 내용이 같거나 현재 레벨에 배치됐다고 판단할 수 없다.
- 현재 조사에서 읽은 원시 데이터와 스크립트는 작업 폴더의 `Saved/DesignGuideAudit/`에 보관했다. 이 위치는 일반적으로 Git 추적 대상이 아니다.

## 확인한 기존 화면

아래는 이번에 새로 실행·렌더한 화면이 아니라 기존 저장 이미지를 읽고 복사한 참고 자료다. 파일 경로의 날짜가 있는 경우 그 시점의 기록이며 현재 맵의 실시간 증거가 아니다.

| 문서 내 파일 | 원래 경로 |
|---|---|
| [Tutorial_Existing.png](Tutorial_Existing.png) | `C:\Users\whghk\Catrun\Saved\ChaptersFlow20261112\Captures\ImportSources\T_Chapter_Tutorial.png` |
| [Stage1_Existing.png](Stage1_Existing.png) | `C:\Users\whghk\Catrun\Saved\StageRevision20261123\MinimapRoutedGreen03\Frames\Stage1-released.png` |
| [Stage2_Existing.png](Stage2_Existing.png) | `C:\Users\whghk\Catrun\Saved\StageRevision20261123\MinimapRoutedGreen03\Frames\Stage2-released.png` |
| [DemonBed_Existing.png](DemonBed_Existing.png) | `C:\Users\whghk\Desktop\CastleKit\DemonBed\DemonBed_Beauty.png` |
