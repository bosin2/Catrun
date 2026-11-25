# 시네마틱 조명·연출 수정 납품 (cine-polish, 2026-11-26)

본 프로젝트 Content·Source·Binaries·Config 변경 0건. 후보는 `C:/Users/whghk/.codex/workspaces/CinematicReview_20261125/Catrun`. 판정은 모두 **d3d12**, `-game`, 30fps 고정, 1280x720이다. 후보에는 다른 세션의 변경이 들어 있지 않다.

## 내용물
| 파일 | 내용 |
|---|---|
| `Native/cinematics.patch` | C++ 6개 파일 `git diff`. main에서 `git apply --check` 통과 |
| `apply_cinematics.py` | 시퀀스 2개 적용기. **기본 dry-run**, 해시 검사, 백업, 다른 파일 변경 감시 |
| `Sequences/author_cine.py`, `cine_values.json` | 실제 편집과 수치. 시퀀스 통째 복사가 아니라 트랙 단위 편집 |
| `baseline_hashes.json` | 검토한 시퀀스 원본 해시 |
| `Frames/*.jpg` | 같은 프레임 전(왼쪽)·후(오른쪽) |
| `D:/CatrunWork/cine-polish/Video/compare_*.mp4` | 정상 속도 전후 나란히 |

## 적용 순서
1. main에서 `git apply --check --ignore-whitespace <patch>` → `git apply --ignore-whitespace <patch>`. 겹치는 파일은 없음을 기준 시점에 확인했다(gameplay-bugs의 CatrunArmor·SoundGridManager와 다른 파일).
   gameplay-bugs의 `bShowDetectionDisplay` 기본값 변경과 함께 써도 된다(표시 설정은 그대로 두고 시네마틱 중에만 숨김).
2. 헤더가 바뀌므로 **전체 재빌드**한다. 오래된 obj 문제는 `Saved/Regression20261126/fixes/force_full_rebuild_touch.ps1` 참고.
3. 에디터를 모두 닫고 `python -B apply_cinematics.py`(dry-run) → 통과하면 `python -B apply_cinematics.py --apply`. 고양이 세션이 같은 시퀀스를 먼저 바꿨으면 `--allow-changed`를 붙인다. 고양이·애니메이션·컷·길이·페이드가 바뀌면 스크립트가 저장 없이 중단한다.
4. 되돌리기: 시퀀스는 `D:/CatrunWork/cine-polish/ApplyRuns/<시각>-apply/Backup`, C++은 `git apply -R`.

## 바꾼 것
- **LS_Tutorial**: 컷 구간에서만 존재하는 보조광 11개(`CINE_Fill_*`, cd 단위) 추가. `Cam_03_LookDemon`과 이어지는 `Cam_03B`의 시작 구도를 yaw +8°, 렌즈 40→31mm로 넓힘(3B는 f248까지 원래 값으로 복귀). 나머지 카메라·고양이·컷·페이드·길이 661f 유지.
- **LS_Tutorial_StairDescent**: 강도 0이던 전용 조명 2개에 값을 주고, 고정 카메라를 고양이를 따라 내려가는 카메라로 변경(초점 동반). 길이 165f·페이드 유지.
- **포획 카메라**(`CatrunCapturePresentationComponent`): 첫 틱에 구도를 한 번만 정하고 유지, 고양이가 보이는 앞·옆 우선, 벽에 막히는 블렌드는 첫 프레임 컷, 후보가 모두 탈락하면 위에서 내려다보는 안전 구도, 가까우면 화각 확대(60~90°), 카메라에 붙은 보조 스포트(1.6lx, 그림자 없음). 단계 시간·판정·애니메이션은 그대로.
- **시네마틱 중 시야/감지 바닥 표시와 "!" 숨김**(`VisionFanComponent`, `AlertMarkComponent`): 원근 시점일 때만 숨기고 시야 판정은 유지. 직교 카메라인 철창 연출과 창고 조작 시점은 그대로 보인다.
- **맵 전환 첫 프레임**(`CatrunRestartSubsystem`): 재시작·도착 첫 1프레임에 고양이 눈높이 화면이 번쩍이던 것을 검정으로 시작. 첫 구역(튜토리얼)은 메뉴와 이어지는 컷이라 제외.
- **시간초과**: 전체 1.6초와 문구는 그대로 두고, 어두운 붉은 페이드와 기존 `CS_GateImpact` 흔들림을 추가.

## 구간별 판정
LevelSequence는 전체 4개다(포탈 2개와 승강기는 담당 제외).

| 구간 | 판정 | 근거·비고 |
|---|---|---|
| MainMenu | 문제 없음 | 수정 전 재생만 확인 |
| LS_Tutorial 인트로 | **수정함** | A-01 부채꼴 노출, A-04 마왕 컷, 얼굴·점프·착지 컷 어두움. `Frames/intro.jpg` |
| 인트로 뒤 조작 복귀 | 다른 세션 | 제목-시계 겹침, 키 안내 번쩍임, 미니맵 외곽선은 ui-fix에 전달 |
| LS_Tutorial_StairDescent | **수정함** | A-09, 조명 0, f104 이후 빈 계단. `Frames/stair.jpg` |
| Stage1 도착 첫 프레임 | **수정함** | 검정으로 시작 |
| Stage1 출구 복도 B-02 | 고치지 않음 | 복도 외벽에 벽 페이드가 없어 약 1.2초 가림. 해결은 Stage1 맵의 벽 페이드 추가나 출구 발동 시점 변경이라 맵·포탈 담당과 겹침 |
| 포획 Framing~Fading Stage1·2·3 (9사례) | **수정함** | E-01, E-02, B-08. `Frames/cap_*.jpg`. Stage1_0·Stage2_1은 등 뒤 구도였고 Stage1_0은 173번째 프레임에 851cm 이동했음 |
| 튜토리얼 포획 | **수정함**(책상 옆 1사례) | 복도 위치 fixture로는 12초 안에 포획이 시작되지 않아 일반 사례는 재생 못 함 |
| 재시작 페이드 | **수정함** | 첫 프레임 번쩍임 제거 |
| 시간초과 B-03 | **수정함** | 소리는 새 음원이 필요해 제외 |
| Stage2 철창 A·B·C | 문제 없음 | B·C는 동상 배치 fixture |
| Stage3 D1·D2 문 카메라 | 문제 없음 | D1은 동상 배치 fixture. Stage2와 달리 위아래 검은 띠가 없음 → **결정 필요** |
| Stage3 봉쇄 장치 3개 | 문제 없음 | 승강기 구조물이 새까만 실루엣으로 보임(승강기·맵 담당) |
| Stage3 대문 D-05 | **결정 필요** | 대문을 비추는 카메라가 없음. 설계안: 대문이 열리기 시작할 때 기존 문 공개 카메라를 재사용(이동 3초·복귀 2.6초, 그동안 적 정지). 결말(M09)과 묶여 있고 좌우 문짝·아치가 시야 검사에 걸리는지 확인이 필요해 넣지 않음 |
| Stage3 완료 문구 | 다른 세션 | "스테이지 2를 통과했어요" → ui-fix에 전달 |
| 로딩 화면 | 재생 못 함 | AsyncLoadingScreen은 `Shot` 캡처에 잡히지 않음 |

### 결정이 필요한 것
- 침대 벽등 `BP_Tutorial_Flame_Bed`(MainMenu·Tutorial)만 단위가 UNITLESS라 다른 벽등(145lm)보다 약 50배 어둡다. 게임플레이 조명이라 손대지 않았다.
- 점프 컷(f465~570)은 천장이 없어 배경이 검다(A-07, 세트 문제). 고양이만 보조광으로 분리했다.

## 검증
| 검사 | 결과 |
|---|---|
| 후보 빌드(전체 → 증분) | 성공. 소스는 `cinematics.patch`와 같다 |
| 최종 재생 `Runs/after2-*` | 인트로, 계단, Stage1 도착, 책상 옆 포획, Stage1·2·3 포획 1사례씩. 오류 0 |
| 1차 수정 재생 `Runs/after1-*` | 포획 9사례, 시간초과. 이후 포획 화각 60~85→60~90°, 시간초과 붉은색 0.05→0.02, 점프·착지 보조광 축소만 바뀜. **시간초과의 최종 색은 다시 재생하지 않았다** |
| 포획 카메라 이동 | 최종 4사례 모두 첫 컷 뒤 프레임당 70cm 넘는 이동 0건(수정 전 Stage1_0 851cm). 1차 9사례의 최대는 Stage3_1 67cm와 Stage1_0 블렌드 62cm |
| 책상 옆 포획 E-01 | 나무판 대신 방 전체 구도에서 갑옷이 보임(`Frames/cap_desk_and_final_fov.jpg`). 고양이는 책상과 갑옷에 대부분 가려진다. fixture는 감사 좌표(84,157,36)에 고양이를 두고 갑옷을 옮긴 것 |
| Stage1 도착 첫 프레임 | 검정으로 시작 확인(`Frames/stage1_arrival_first_frames.jpg` 네 번째 칸) |
| 네이티브 자동화 1차(`Tests/t1`, NullRHI) | 성공 153 + 경고 9, **실패 1**. 실패는 `LevelFlow.StageClockPausesAndOwnsTimeoutOnce`: 새 도착 첫 프레임 검정이 화면 없는 검사 월드의 시계를 멈춤. 실제 게임 화면이 있을 때만 동작하도록 고쳤고 **재실행 결과는 아래 줄** |
| 포획 테스트 `Catrun.PrototypeAI.Capture*` | 1차에서 전부 성공(기준 실행의 크래시는 회귀 세션 분석대로 오래된 obj 탓) |
| 자동화 2차(`Tests/t2`, 최종 DLL, NullRHI) | **실패 0**: 성공 153 + 경고 10, 미실행 0. 1차에서 실패한 시계 테스트도 통과 |
| 본 프로젝트 적용 dry-run(최종 수치) | **통과**: 저장 0, 시퀀스 해시가 검토 기준과 일치. `D:/CatrunWork/cine-polish/ApplyRuns/20261126-052004-dry` |
| 보호 검사 | 편집 전후 컷·길이·페이드·애니메이션·고양이 트랙 동일(스크립트가 매번 검사). 예외는 위에 적은 카메라 2개와 계단 카메라·조명뿐 |

## 한계
- 위치 순간이동, 적 정지, 동상 배치, 시간 가속(시간초과), `catrun.NoArmorCapture`를 fixture로 썼다. 손플레이 완주가 아니다.
- 카메라 컷 첫 사용 때 보이는 갈색 테두리 1프레임은 쿠킹하지 않은 실행에서 후처리 재질이 준비되기 전 표시다. 같은 실행의 철창 B에서는 나오지 않아 게임 결함으로 보지 않았다. 패키지 실행으로는 확인하지 않았다.
- 1280x720의 왼쪽 위 "Preparing Shaders" 글자와 재시작 직후 몇 프레임의 단색 벽도 같은 이유다.
- 이 수정은 화면을 AI가 직접 보고 판단한 것이며 사용자 미술 승인이 아니다.
