# 맵 결함 수정 납품 (2026-11-26)

본 프로젝트에는 저장하지 않았다. 두 스크립트는 기본이 dry-run이고, 후보 프로젝트에 실제로 적용해 검사한 뒤 본 프로젝트 dry-run까지 통과했다(`main maps unchanged: True`).
기준 SHA256: Tutorial `177dbc65…`, Stage3 `1ebff0f5…`, Stage1 `bfd2163f…`, Stage2 `da4c0287…`(전체 값 `../baseline_sha256.csv`).

## 판정

| 맵 | 항목 | 판정 | 근거(`../out/`) |
|---|---|---|---|
| Stage1 | 벽 22개 Nanite/반투명 | 이미 해결 | 22개 `disallow_nanite=true` (`probe_s13t.json`), d3d12 로그 경고 없음 |
| Stage1 | 시작점 불투명 문 | 이미 해결 | 4슬롯 Masked 가림 재질, `stage1_spawn/spawn.png`에서 고양이 보임 |
| Stage1 | 갑옷 이동 6사례 | 정상 | `armor_pie_Stage1.json`. 탁자 밑 목표는 82cm 앞, 열린 문짝 아래 목표는 14cm 앞에서 멈추고 정상 복귀 |
| Stage3 | D1 초기 먼지 | 이미 해결 | `D1_dust_shown_vs_hidden.png`(같은 카메라, 나이 0.08~0.4초), 실시간 d3d12 최대 프레임 48ms(`dust_D1_timing`). 재질이 아니라 예전 0.6초 카메라 복귀가 원인 |
| Stage3 | 작전 탁자 밑 길찾기 | **고침(1번)** | `armor_pie_Stage3.json` → `armor_pie_Stage3_after.json` |
| Tutorial | 캣홀 벽 확장과 격자 불일치 | **고침(2번)** | `apply/tutorial_grid_*` |
| Stage2 | `Candle_02` 외 | 담당 이전 | `../STAGE2_FINDINGS.md` |

## 1. `apply_furniture_clearance.py` — Stage3
- 증상: 로비 갑옷이 (12.5,-1112.5)로 갈 때 `S3_Gothic_LowerStrategy`에 2.4초 막히고 345cm 앞에서 조사를 포기.
- 원인: 길찾기 여유는 Z+30 광선으로 굽는다. 탁자 다리 사이로 광선이 지나가 탁자 밑이 통로로 읽힌다. 갑옷 캡슐은 막힌다.
- 변경: 탁자 충돌 범위 안에 숨김 표식 6개(`S3_Gothic_LowerStrategy_PathClear_00~05`, 폴더 MapDefects20261126)를 추가하고 격자를 다시 굽는다. 태그 `SoundObstacle`(갑옷 여유만, 소리 모서리 무관), QueryOnly·모든 채널 Ignore·숨김·그림자/내비 없음.
- 바뀌는 값: `WallDistance` 54칸. `Walkable/CostMultiplier/EdgeMask` 0칸. 기존 액터 변경 0.
- 후보 결과: 345cm → 9.6cm 도착, 정체 2.40초 → 0.05초, 초소 복귀. 나머지 11사례의 도착·복귀 유지(탁자와 벽 사이 목표 1건은 125→144cm 앞에서 멈추지만 정체 2.4초가 사라짐, 탁자 밑 목표는 118→76cm).
- 새 프로세스 재검사: 저장된 격자 = 다시 구운 격자.

## 2. `apply_tutorial_grid.py` — Tutorial
- 증상: 저장 격자가 11-25 벽 확장 전 모습이다(재굽기 시 EdgeMask 41·WallDistance 62칸 변경). 별관과 캣홀 앞 공간 사이 소리 거리가 실제 벽보다 짧게 계산된다(181 → 210cm).
- 원인: `fit_tutorial_cathole_20261125.py`가 만든 벽 4개(`SM_CatHole_BedroomWallExtension`, `BedroomReturn`, `CorridorWallExtension`, `CorridorReturn`)에 `SoundWall` 태그가 없고 격자도 다시 굽지 않았다. **태그 없이 재굽기만 하면 벽 자리에 구멍이 생기므로 반드시 이 스크립트를 쓴다.**
- 변경: 벽 4개에 `SoundWall` 태그, 격자 재굽기. 위치·충돌·메시 변경 없음.
- 유지 확인(격자 계산): 침실(-210,404)→갑옷 새 위치(-80,760) 402cm, 기존 위치(-80,900) 552cm, 캣홀 통과 75cm 모두 전후 동일. 60cm 캣홀은 소리 열림, 갑옷 통과 불가. 갑옷이 설 수 있는 칸 1080→1074(확장 벽 옆 7칸 빠지고 1칸 추가).
- 후보 결과: 갑옷 이동 6사례 전후 동일(`armor_pie_Tutorial.json` / `_after3.json`), 새 프로세스 재검사 변경 0칸.
- 방울 범위(650→500)와 `Armor_Tutorial` 이동은 게임플레이 버그 세션 담당이며 이 스크립트는 건드리지 않는다. 어느 쪽을 먼저 적용해도 된다.

## 적용 순서
1. 다른 세션의 Tutorial·Stage3 변경(게임플레이 버그 `apply_maps.py`, Stage3 아트 `apply_stage3_art.py`)을 먼저 저장한다. 두 스크립트 모두 액터·격자 단위라 SHA가 달라져도 된다.
2. 에디터에서 해당 맵을 닫고, 각 스크립트를 dry-run한다. 마지막 줄이 `CATRUN_MAPFIX … OK saved=False`인지 본다.
3. `CATRUN_MAPFIX_APPLY=1`로 다시 실행한다. 백업 `.umap`과 `report.json`은 `Saved/MapDefects_20261126/`에 남는다(`CATRUN_MAPFIX_OUT`으로 변경 가능).
4. 환경변수를 지우고 한 번 더 dry-run한다. 튜토리얼은 변경 0칸, Stage3는 `already_fixed=true`와 `grid_matches_level=true`여야 한다.

```powershell
$env:CATRUN_MAPFIX_MAP='Stage3'   # furniture 스크립트용
# $env:CATRUN_MAPFIX_APPLY='1'    # 저장할 때만
& 'C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' 'C:\Users\whghk\Catrun\Catrun.uproject' -run=pythonscript '-script=C:/Users/whghk/.codex/workspaces/MapDefects_20261125/apply/apply_tutorial_grid.py' -nullrhi -unattended -nop4 -nosplash -NoSound -Multiprocess -NoSaveConfig -SaveToUserDir '-UserDir=C:\Users\whghk\.codex\workspaces\MapDefects_20261125\UserMain'
```

멈추는 조건: 예상 밖 구역의 격자 변화, 소리 데이터 변화(Stage3), 기존 액터 변화, 실행 중 맵 파일 변경. Stage3는 저장 격자가 현재 배치와 이미 다르면 멈춘다(그때는 다른 편집의 격자 처리부터 확인).
되돌리기: 백업 `.umap` 복원.

## 검증하지 않은 것
- 두 수정 모두 NullRHI 네이티브 AI 이동과 격자 비교다. 사람이 처음부터 끝까지 플레이한 검사는 아니다. 시작 시 소리 사건을 갑옷에 직접 전달한 fixture를 썼다.
- Stage3 표식의 d3d12 화면은 **미확인**(GPU 대기 13번째라 취소). 표식은 bHiddenInGame·액터 숨김·그림자 끔으로 저장된다. 확인하려면 `tools/run_gpu.ps1 -Script tools/stage_shot.py -Map Stage3`, `CATRUN_SHOT_POS=-180,-1120`.
- MainMenu에도 같은 벽 확장이 있으나 플레이 맵이 아니라 손대지 않았다. `SoundTest_Tutorial`은 벽 확장이 적용되지 않은 보조 맵이다.

## 남긴 선택지·후속
- 코드: `ACatrunArmor::TickWalking`이 복귀 중 정체도 도착으로 처리해 초소 밖에 남는다(`../STAGE2_FINDINGS.md` 3-2).
- 코드: `BakeWallDistance`가 Z+30 한 높이만 본다. 갑옷 높이도 함께 보면 탁자·천구의 유형이 한 번에 해결되지만 세 맵 길찾기가 모두 바뀐다.
- 맵 체크의 빈 StaticMesh 경고(`BP_HideBasket` Stage1 2·Stage2 3·Stage3 4, Tutorial `StaticMeshActor_190`·`CatrunDoor_1`)는 실행 증상이 없어 두었다.
- 먼지가 낱개 점처럼 보이는 모양은 미술 판단이다.
