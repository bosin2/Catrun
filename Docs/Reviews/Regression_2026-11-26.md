# 전체 스테이지 회귀검사 — 통합 전/후 비교 (2026-11-26)

07:25 기준 문서이고, 09시대에 Final02(포획 다듬기 Fix2)를 덧붙였다(맨 아래 절). **통합 뒤 남은 실패는 1단계(`tutorial_route`)이고 통합 전에도 같은 이유로 실패했다.** 통합으로 생긴 회귀 1건(승강기 도착 시작 지연)은 수정·빌드 뒤 다시 검사해 사라졌다.

판정은 종료코드가 아니라 보고서(`index.json`, `report.json`)로 했다. 대부분 체크포인트 배치와 적 격리 fixture가 들어간 자동 검사이며 **사람이 처음부터 끝까지 플레이한 완주가 아니다.**

## 검사한 상태

| 이름 | 대상 | DLL | 맵 |
|---|---|---|---|
| Baseline | 통합 전 고정 사본 `BaselineProject`(본 프로젝트와 해시 동일) | `Catrun_ElevatorRevision3` | Stage2 `da4c0287`, Stage3 `1ebff0f5`, Tutorial `177dbc65` |
| After01 | 06:06 통합본 | `UnrealEditor-Catrun.dll` 05:56 | Stage2 `51b961ee`, Stage3 `af85cd64`, Tutorial `2bdec84b` |
| After02 | 06:40 포탈 2차본(시퀀스 2개·BP 1개만 변경) | 05:56. `stage2_arrival_flow`만 07:05 | 같음 |
| Final01 | 커밋 대상 최종본(승강기 도착 수정 포함) | 07:05 `a1074c59…` | 같음 |
| Final02 | Final01 + 포획 다듬기 Fix2(표식 구슬 숨김·포획 카메라 컷, C++ 5개, 새 테스트 3개) | 08:53:05 `UnrealEditor-Catrun.dll` | 같음 |

Stage1 `bfd2163f`와 MainMenu `f98e2360`은 전후가 같다. 검사 중 Content·Source·Config·DLL·사용자 저장의 변경은 0건이다(단계별 전후와 Final01 전후 해시).

## 전후 비교

`완료`는 항목 수를 세지 않는 보고서가 성공한 것이다.

| 단계 | 구간 | 통합 전 | 통합 후 | 최종 확인 |
|---|---|---|---|---|
| native | 전체 | FAIL: 성공 139, 크래시 21, 실패 3 | PASS 167 | Final01 |
| bp_compile | 전체 | PASS 56 | PASS 56 | After02 |
| asset_sweep | 전체 | PASS 1612 | PASS 1697 | After02 |
| stage_sweep (맵 5개) | 전체 | PASS 136, 스킵 2 | PASS 136, 스킵 2 | After01 |
| progress_process | 저장 | PASS 4 | PASS 4 | After01 |
| tutorial_passages | Tutorial | PASS 완료 | PASS 완료 | After01 |
| **tutorial_route** | Tutorial | **FAIL** | **FAIL (같은 이유)** | After01 |
| stage1_departure | Stage1 | PASS 완료 | PASS 완료 | After02 |
| stage2_arrival | Stage1→2 | PASS 완료 | 의도된 변경으로 대체(아래) | |
| stage2_arrival_flow | Stage1→2 | (통합 뒤 신설) | PASS 완료 | Final01 |
| baskets_stage1_2 | Stage1·2 | PASS 완료 | PASS 완료 | After01 |
| baskets_wasd | Stage1·2 | PASS 완료 | PASS 완료 | After01 |
| stage2_statues | Stage2 | PASS 19 | PASS 19 | After01 |
| stage2_push_input | Stage2 | PASS 완료 | PASS 완료 | After01 |
| stage2_expansion | Stage2 | 미실행 | PASS 완료 | After02 |
| elevator_runtime | Stage2→3 | PASS 58 | 납품 검사로 대체 | |
| elevator_redirect | Stage2→3 | (통합 뒤 신설) | PASS 74 | Final01 |
| elevator_reentry | Stage2→3 | PASS 8 | PASS 8 | After01 |
| campaign | 전체 전환 | 미실행 | PASS 완료 | Final01 |
| stage3_puzzle | Stage3 | PASS 209 | PASS 209 | After01 |
| stage3_camera_pacing | Stage3 | PASS 76 | PASS 76 | After01 |
| stage3_reset_replay | Stage3 | PASS 53 | PASS 53 | After01 |
| stage3_placement | Stage3 | PASS 174 | PASS 174 | After01 |
| stage3_baskets | Stage3 | PASS 163 | PASS 163 | After01 |
| stage3_sound | Stage3 | PASS 24 | PASS 24 | After01 |
| stage3_push | Stage3 | PASS 49 | PASS 49 | Final01 |
| ui_routed, ui_live | UI | PASS 1, 1 | PASS 1, 1 | Final01 |

- After01 뒤의 변경은 포탈 시퀀스 2개, `BP_Stage2PortalArrival`, `CatrunElevatorTransition.cpp`(TryBegin 도착쪽)뿐이다. 이 변경이 닿지 않는 단계는 최종 DLL에서 다시 돌리지 않았다.
- `campaign`: 튜토리얼 인트로→계단→Stage1→실제 포탈 출구→Stage2 도착 연출→같은 월드의 승강기에서 F→Stage3 조작 복귀. 포탈 2차본에서 3회 통과했고 Stage2 승강기는 매번 첫 시도에 시작했다.
- `native`는 이름 기준 새 검사 4개, 없어진 검사 0개다. 경고를 포함한 성공은 10개다.

## 통합으로 생겼다가 고친 것

**승강기 Stage3 도착이 2프레임 늦게 시작** (경고 `Elevator could not start: Gameplay input/camera is owned by another action`)

- 원인: `UCatrunRestartSubsystem::OnWorldBeginPlay`가 모든 구역에 0.1초 시작 암전을 켜면서 도착 승강기의 `AcquireExitLease`가 `bEnableFading`을 다른 연출로 보고 거절했다. 그동안 입력이 풀리고 게임 카메라였다(`campaign`에서 실제 시간 약 1.2초).
- 수정: `Saved/Regression20261126/fixes/elevator_arrival_startfade.patch`. 총괄 세션이 적용해 07:05에 빌드했다.
- 확인: 분리 사본에서 네이티브 167·승강기 74 통과. 최종본에서 경고 0건, 도착 첫 표본이 `ARRIVAL`·입력 잠금·승강기 카메라로 통합 전과 같다. 화면 번쩍임 자체는 프레임으로 보지 않았다.

## 통합으로 해결된 것

| 항목 | 통합 전 | 통합 후 |
|---|---|---|
| 포획 검사 크래시 | 크래시 21·실패 3. `CatrunArmor.h`가 예전 수정 시각으로 복사돼 `Module.Catrun.3/4` obj가 다시 컴파일되지 않음(`fixes/force_full_rebuild_touch.ps1` 참고) | 24개 모두 통과. 05:53 이후 전체 재컴파일 확인 |
| 승강기 먼지 `M_E23_DustSoft` | 재질 컴파일 실패로 회색 기본 재질 | 컴파일 실패 로그 0건. 도착 화면에는 작고 밝은 점으로 보임(부드러움 판단은 사용자 몫) |

포획 크래시는 실제 포획 코드의 결함이 아니었다. 통합 전 15:54 정식 DLL에서도 같은 검사 2개가 죽었으므로 승강기 Revision 3 탓도 아니다(`OldDllNative/result.json`).

## 의도된 변경에 맞춰 바꾼 검사

원본 검사 파일은 고치지 않았고 `Scripts/Regression20261126`의 실행기에서만 보정했다.

| 단계 | 바뀐 기대값 | 처리 |
|---|---|---|
| stage2_arrival | 도착 연출 재구성(컷·모델 표시 구간, 378→303프레임). 원본 검사는 11프레임 모델 표시 조건에서 실패 | `stage2_arrival_flow`: 입력 잠금·제목·퍼즐 보존·재시작·이어하기는 원본 그대로. 카메라 인계는 "정지"에서 "프레임당 변화가 튀지 않음"으로 변경(실측 인계 직전 약 27, 인계 때 약 23/프레임) |
| elevator_runtime | 재연출 시간·카메라 | 납품된 74개 검사(원본 58 + 새 16)로 교체 |
| stage2_expansion | 동상 A의 미는 방향(11-25 방2 개편) | 방향만 X축으로 |
| campaign | 승강기 F 시작 | Stage2 출구 겹침 대신 객실에서 F |
| stage1_departure | 방울을 BP가 소유 | 같은 조건의 방울 소리를 관리자로 직접 발생 |
| stage3_reset_replay, stage3_push | 카메라 복귀 2.6초, 나중에 놓인 물체 | 대기 시간, 걷는 거리 |

튜토리얼 방울 500, 갑옷 위치, 액터 수(Stage2 953→1051, Stage3 1792→1847), 문구 변경은 통과한 검사에 실패를 만들지 않았다.

## 남은 실패

**tutorial_route** — 통합 전과 같은 실패. 검사의 고정 경로가 (-180, -95)에서 촛불에 발각되고(전 37.46초, 후 37.43초) 방울을 울리기 전에 포획된다(전 46.5초, 후 46.1초). 갑옷 위치 변경 탓이 아니다. 이 검사의 최근 성공 기록은 11-16이다. 게임플레이 세션도 d3d12에서 다른 이유로 실패한다고 기록했다. **사람이 하는 튜토리얼 완주는 확인되지 않았다.**

## 새 로그 경고 (실패 아님)

| 경고 | 위치 | 담당 |
|---|---|---|
| `BP_Stage2PortalArrival` 주석 노드 4개 NodeGuid 없음(쿠킹 결정성 경고, 다시 저장하라는 안내) | 포탈 2차본 | 시네마틱 |
| 비나나이트 VSM 마킹 작업 큐 오버플로 1건 | `elevator_redirect`(After01) | 시네마틱·성능 |
| Stage2 `StaticMeshActor_840`과 `679` 같은 위치(기존 12쌍에 추가) | MAP CHECK | Stage2 |

## 미확인

- 사람이 하는 처음부터 끝까지의 완주, 난이도·제한시간 체감, Shipping 패키지 실행.
- 화면: 승강기 도착 1장만 직접 보았다(통합 전·후). 포탈·포획·UI·Stage2·3 아트의 화면 판정은 하지 않았다.
- 포획 감지 범위 표시·책장 파동의 화면 모습(자동화 검사는 통과).
- 통합 전 `stage2_expansion`과 `campaign` 결과가 없어 두 단계는 전후 비교가 아니라 통합 후 통과만 확인했다.
- `BP_LivingArmor_C_0 found no path`(`baskets_wasd`), `EmitSound: no floor cell`(승강기 객실)은 통합 전부터 있었고 원인을 조사하지 않았다.
- 통합 전부터 있는 맵·에셋 항목: Tutorial `StaticMeshActor_190`·`CatrunDoor_1` 빈 메시 경고, `BP_HideBasket` 빈 메시 경고(보이는 빈 메시는 0개), `SM_Tutorial_DoorFrame` Nanite+반투명 슬롯 2개, 리디렉터 6개.

## 다시 돌리기

```powershell
python -B -u Scripts/Regression20261126/run_regression.py run After03 --compare After01
```

- 단계 선택 `--only native,campaign`, 다시 `--redo`. 실행은 모두 `Saved/UESlot` 대기열을 거친다.
- 결과 `Saved/Regression20261126/<LABEL>/SUMMARY.md`. 격리 사본 안에는 본 프로젝트로 이어지는 정션이 있으므로 이 폴더는 지우지 말고 이름을 바꾼다.
- `stage2_arrival`과 `elevator_runtime`은 통합본에서 항상 실패하므로 `--skip stage2_arrival,elevator_runtime`을 붙인다.
- `ElevatorTransition/verify_reentry_visibility.py` 원본은 시작할 때 에셋을 다시 저장한다. 실행기는 그 줄을 메모리에서만 뺀다.
- `stale_objects.py`는 obj보다 새로운 헤더를 찾는다. 헤더가 예전 시각으로 들어온 경우는 찾지 못하므로 통합 빌드는 `fixes/force_full_rebuild_touch.ps1` 뒤에 한다.
- 증거: `Saved/Regression20261126/Baseline`, `After01`, `After02`, `FixTrial`, `Final01`, `Final02`, `OldDllNative`, 크래시 콜스택 `Baseline/native`.

## Final02 — 포획 다듬기 Fix2 (DLL 08:53:05)

요청받은 4단계를 본 프로젝트에서 다시 돌렸다. 모두 통과했고 이전과 비교해 줄어든 결과는 없다(`COMPARE_After01_Final02.md`, 회귀 0건).

| 단계 | 이전 | Final02 |
|---|---|---|
| native | PASS 167 (Final01) | **PASS 170**. 새 검사 3개 성공, 없어진 검사 0개, 경고 포함 성공 10개로 같음 |
| stage_sweep (포획→재시작·수동 재시작·6초 시간초과 포함, 맵 5개) | PASS 136, 스킵 2 (After01) | PASS 136, 스킵 2 |
| campaign | PASS 완료 (Final01) | PASS 완료 |
| elevator_redirect | PASS 74 (Final01) | PASS 74, `Elevator could not start` 0건 |

- 새 검사: `Catrun.Monsters.MarkVisualSuppressionKeepsMark`, `Catrun.PrototypeAI.CaptureHidesMarkVisualOnlyWhileOwning`, `Catrun.PrototypeAI.CaptureCameraCutsOnlyJumps` 모두 오류·경고 0.
- 로그: native·campaign 경고 종류와 개수가 Final01과 같다. `stage_sweep`에 새로 보인 것은 이미 기록한 `BP_Stage2PortalArrival` 주석 노드 경고(After01이 포탈 2차본 이전이라 생긴 차이)뿐이다. `elevator_redirect`의 VSM 큐 오버플로 1건은 이번에는 나오지 않았다.
- 각 단계 전후로 Content·Source·Config·DLL·사용자 저장 변경 0건.
- 미확인: 표식 구슬이 실제 화면에서 숨는 모습과 포획 카메라 컷의 프레임 화면 판정은 하지 않았다(자동화 검사와 상태 값만 확인). 포획이 들어가는 다른 단계(`tutorial_route`, 바구니, Stage3 퍼즐 등)는 요청 범위 밖이라 Fix2로 다시 돌리지 않았다.
