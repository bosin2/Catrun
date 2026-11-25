# 방울 범위 · Stage2 책장 파동 · Stage3 갑옷 범위 — 납품 (2026-11-26)

작업 후보: `C:/Users/whghk/.codex/workspaces/GameplayBugs_20261126`. 본 프로젝트 Content·Source·Config·Binaries는 바꾸지 않았고 커밋하지 않았다.

## 1. 원인과 수정

| 버그 | 원인 | 수정 | 바뀌는 곳 |
|---|---|---|---|
| 방울 범위 불일치 | Tutorial·SoundTest_Tutorial만 `PlayerBellBudgetOverride`=650. 실제 전파와 화면 파동은 같은 Budget을 받는다(BP_CatrunSoundController 핀 연결, `PlayerBellBudget` 테스트) | 650→0(공유 500 사용). 500이면 방울 지점에서 갑옷까지 587이라 닿지 않으므로 `Armor_Tutorial` XY (-80,900)→(-80,760). 거리 약 451, 유인되는 침실 칸 101→98로 기존과 비슷 | 두 튜토리얼 맵 |
| Stage2 책장 파동 | 책장 6개(80×260×260)가 `SoundObstacle`만 있어 소리 격자에 전혀 없다. 파동이 책장을 직선으로 통과한다 | C++: 액터 태그 `SoundBlocker`가 덮는 칸은 소리·화면 파동이 돌아간다(닫힌 문과 같은 경로). 저장 격자·갑옷 길찾기·충돌은 그대로 | `SoundGridManager.*`, Stage2·SoundTest_Stage2 책장 6개 태그 |
| Stage3 갑옷 범위 안 보임 | 11월 12일 작업이 Tutorial/Stage1/Stage2 갑옷 인스턴스에만 표시를 켰다. 나중에 배치된 Stage3 6기는 기본값 false. 높이(Z 3cm)·반경 165·재질·카메라는 정상 | C++ 기본값 `bShowDetectionDisplay` true. SoundTest_Stage2의 `Armor_C_BellSentry`도 같은 원인으로 함께 켜진다 | `CatrunArmor.h`. Stage3.umap은 저장하지 않음 |

Stage3의 방울 override 500은 장치 소리(Large 1800)와 나누기 위한 값이라 유지한다.

## 2. 파일
- `gameplay_bugs.patch` — C++ 4개 수정, 테스트 2개 추가. 새 UPROPERTY 없음(기본값 변경 1개)
- `apply_maps.py` — 맵 속성만 다시 적용(기본 dry-run, 해시 검사, 백업, 저장 뒤 재로드 비교, 재실행 시 저장 안 함)
- `verify_maps.py` — 읽기 전용 검사(방울 500·범위 165·갑옷 표시·책장 태그)

## 3. 적용 순서
1. `git apply C:/Users/whghk/.codex/workspaces/GameplayBugs_20261126/Deliver/gameplay_bugs.patch` (main 작업 트리에서 `--check` 통과)
2. 빌드. 패치보다 맵을 먼저 저장해도 되지만 `verify_maps.py`는 새 DLL에서만 OK다.
3. dry-run: `UnrealEditor-Cmd.exe <Catrun.uproject> -run=pythonscript -script=<...>/Deliver/apply_maps.py -nullrhi -unattended`
   - 선택: `-GBExpect=Tutorial:177dbc65,SoundTest_Tutorial:6d8f58cb,Stage2:da4c0287,SoundTest_Stage2:febb5899` (04:36 현재 main과 일치). 다른 작업이 먼저 저장해 해시가 바뀌었으면 이 인자를 빼면 된다. 기존 값이 예상과 다르면 스스로 멈춘다.
4. 같은 명령에 `-GBApply`. 백업·보고서는 `Saved/GameplayBugs_20261126/<시각>/`
5. `verify_maps.py` → 로그에 `CATRUN_VERIFY_MAPS OK []`

본 프로젝트에서는 `apply_maps.py` dry-run을 아직 실행하지 않았다.

Stage2 로직 납품(`Stage2Work_20261126/deliver`)과 순서는 상관없다. 격자를 다시 구워도 영향이 없다. 되돌리기: 백업 맵 복원 + `git apply -R`.

## 4. 검증 (후보, 새 DLL, 저장된 후보 맵)

| 항목 | 고치기 전 | 고친 뒤 |
|---|---|---|
| 맵 값 | `Out/red_map_parity.log`: Tutorial 650, Stage3 갑옷 6기 꺼짐, 책장 차단 0/6 | `verify_maps.py` 7개 맵 `OK []` |
| 책장 전파 | `Out/auto_red2.log`: `Catrun.Sound.Blocker.TallShelfIsBypassedNotPenetrated` 실패 | 통과. 화면 전후 `Out/sheet_wave_compare.png`(d3d12) |
| Stage3 범위 | `Out/sheet_s3_before.png` 6기 모두 없음 | `Out/sheet_s3_near.png` 6기 모두 보임, 실행 중 Visible=true·Z 3·반경 165 |
| 전체 자동화 `Catrun` | — | `Out/auto_full_report/index.json` 성공 165(경고 10)·실패 0·미실행 0 |
| 맵 적용 | — | `Out/apply/20261126-022117/report.json` 4개 맵, 대상 밖 액터·소리 격자 불변 |

튜토리얼 완주(`verify_tutorial_route_20261125.py`)
- nullrhi 실행은 방울 전에 촛불 표식으로 잡혀 실패한다. **수정 전 본 프로젝트도 똑같이 실패한다**(회귀 세션 Baseline 04:18, 표식 37.5초, 방울 0회). 이번 수정과 무관한 검사 환경 문제다.
- d3d12 실행(`Out/route_gpu.log`, 수정본): 방울 1 → 갑옷이 침실 문을 열고 옴 → 캣홀 통과 → 방울 2 → 갑옷이 별실로 들어옴까지 표식·포획 없이 통과. 이후 스크립트의 사전 캡슐 검사가 침실 문턱(`StaticMeshActor_40`)에서 멈췄다(실제 이동 실패가 아님).
- 같은 조건 비교(nullrhi, 시작 위치만 방울 지점으로 옮긴 fixture, 이후 실제 이동·AI·방울 동작). 원본 = 원본 Tutorial 맵 + ElevatorRevision3 DLL, 수정 = 수정 맵 + 새 DLL:

| 출발 시점 | 원본 | 수정 |
|---|---|---|
| 갑옷이 별실에서 둘러볼 때 | 성공 `Out/route_base_look.txt` | **성공** `Out/route_fx.txt` (방울 2회 유인 → 침실 문 → 계단 → Stage1 자동 이동) |
| 원본 스크립트 조건(갑옷이 이미 돌아갈 때) | 포획 `Out/route_base_orig.txt` (출발 1.7초 뒤) | 포획 `Out/route_fix_orig.txt` (출발 1.7초 뒤) |

  즉 원본 완주 스크립트는 현재 본 프로젝트에서도 실패하며, 그 실패는 이번 수정과 무관하다. 검사용 사본은 `Tools/route_source*.py`, `Tools/route_wrap*.py`다(사전 캡슐 검사는 기록만).
- 인트로부터 촛불 구간까지 포함한 한 번의 연속 완주 성공은 아직 없다(d3d12 실행은 촛불·방울 2회까지 통과).

## 5. 남은 것
- 밝은 촛대 옆 성문 홀 바닥에서는 남색 링이 다른 곳보다 옅다. 보이기는 한다. 더 진하게 하려면 `DetectionDisplayOpacity`(.12)를 올린다(미술 결정).
- 갑옷이 복도 문에 가까워져 문 앞(약 185cm)에서 걷기 190·달리기 250 소리를 듣는다. 기존 배치(약 300)에서는 안 들렸다. 별실 안(약 308)은 안전하다.
- 튜토리얼 침실 닫힌 문 옆 x≈-62.5 칸의 간선이 열려 있어 소리가 샌다(GateBox가 -68까지). 이번에 고치지 않았다.
- 문서 M04와 GameDesign 87행의 "튜토리얼 650" 문구, 일회성 스크립트 `finish_world_tuning.py:494`의 650 확인은 갱신하지 않았다.
- 후보의 `Binaries`·`Intermediate`(약 300MB)는 본 반영 뒤 지워도 된다.
