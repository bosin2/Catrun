# Stage1 포탈 출구 + Stage2 포탈 도착 — 후보 납품 (2026-11-26)

상태: **사용자 검수 전.** 본 프로젝트에는 아무것도 쓰지 않았다. 후보 프로젝트: `C:/Users/whghk/.codex/workspaces/CompactPortal_20261125/Catrun`

## 먼저 볼 것
- `Review/AFTER_Stage1_to_Stage2_30fps.mp4` — 두 장면을 이어 붙인 정상 속도 영상
- `Review/BEFORE_Stage1_to_Stage2_30fps.mp4` — 같은 방법으로 찍은 현재 장면
- `Review/Compare_Stage1_*.jpg`, `Review/Compare_Stage2_*.jpg` — 같은 프레임 전후 비교

촬영: d3d12 offscreen PIE, 고정 30fps, 실제 Stage1 출구 겹침에서 시작. 출구 앞까지의 위치만 배치했다(손플레이 아님). 게임 UI(Slate)는 영상에 없다.
두 영상 모두 캡처 요청을 에디터 뷰포트가 대신 받은 프레임(BEFORE 7, AFTER 9개, `video_info.json`)을 바로 앞 프레임으로 채웠다. 게임 화면의 문제는 아니다.

## 2차 납품에서 달라진 것 (DirectingAudit 2026-11-26 포털 항목)
| 항목 | 처리 | 확인 |
|---|---|---|
| B-01 도착 전 플레이 화면 노출 | `BP_Stage2PortalArrival`이 BeginPlay부터 화면을 검게 덮고, 시퀀스 페이드(f0 검정 → f9 밝음)가 이어받는다. 시작이 실패하면 2초 뒤 스스로 푼다 | 시퀀스 첫 프레임 검정 확인. 시작이 막힌 시험에서 검은 화면이 유지되고 2초 뒤 풀리는 것도 확인. 시작 전 3틱의 화면 자체는 캡처를 에디터 뷰포트가 받아 직접 찍지 못함 |
| B-05 길이 | 출구 10.5초 + 도착 10.2초 = 20.7초(현재 10.3 + 12.7 = 23.0초). 스킵 입력은 만들지 않음 | 실제 재생 측정 |
| B-06 포탈 앞 멈춤 | 앉기·갸웃·접촉·흔들기로 채움. 고양이가 거의 안 움직이는 최장 구간 0.43초(갸웃 유지) | 본 이동량 측정 |
| B-09 검정→파랑→검정 | 푸른 조명 최대 8000 → 2600, 접촉·도약 컷은 카메라 쪽 푸른 조명으로 이어지게 함 | `audit_items.json` 머리 색 값 |
| B-10 정지 뒤 조작까지 1.4초 | 카메라가 멈추기 전에 인계 시작, 혼합 1.2초 → 0.4초. **0.3초** | 실제 재생 측정 |
| C-01 석상 전경·발판 잘림 | 발판 전체(화면 가로 22~75%)와 석상이 화면 안, 복귀 컷에서 석상이 앞을 가리지 않음 | 맵 크기 투영 |

새로 찾아 막은 문제: 게임의 `AcquireExitLease`는 카메라 페이드가 켜져 있으면 거절한다. 시퀀스 페이드는 끝나도 이 표시를 남기므로 그대로 두면 같은 월드의 Stage2→3 승강기가 시작되지 않을 수 있었다. 획득 직전과 도착 정리 뒤에 페이드를 끄도록 했고, 도착이 끝난 뒤 다시 획득되는 것을 실제 재생에서 확인했다.

## 바뀌는 것
**Stage1 출구** `LS_Stage1_PortalExit` (원본 312f, 지금 318f = 10.6초)
- 걷기 → 앉기 → 귀·고개 갸웃 → 앞발 접촉(f204–209) → 발 회수 → 엉덩이 두 번 → 압축 → 도약. 정면 걷기는 3.0초(원본 4초)로 줄었다.
- 플레이 고양이는 숨기고 위치만 움직인다. 새 고양이(Refine)는 시퀀스가 띄운다. 게임 고양이 메시·스켈레톤·맵은 그대로다.
- 정면 걷기와 접촉 컷 사이에 걸은 거리 약 70cm를 컷으로 건너뛴다.
- 접촉 컷에서만 카메라 앞 입자(PortalOrbitSparks)를 숨긴다.

**Stage2 도착** `LS_Stage2_PortalArrival` (원본 378f, 지금 303f = 10.1초)과 `BP_Stage2PortalArrival`
- 검은 화면 → 포탈에서 공중 자세로 튀어나와 앞발부터 착지(f8–28) → 일어나 걷기 → 포탈이 닫히는 앞에서 걷기(f56–84) → 앉아서 갸웃(f84–130) → 고양이 시점 동상·발판·철창(f130–214) → 뒤쪽에서 크레인으로 올라가 게임 화면(f214–294).
- 모델 전환은 고양이가 화면에 없는 시점 컷(f130–214) 안에서만 일어난다.
- BP 변경: 인계 시각 11.4 → 9.6초, 혼합 1.2 → 0.4초, 마무리 타이머 1.26 → 0.46초, 위의 페이드 처리. 준비 2초 중단, 임차·복구·제목 규칙은 그대로다.
- 유지: 시작 위치(1375, 3700), 입력 복구, 최종 쿼터뷰 폭 1170, 타이머는 제목·복귀 시점에 900초에서 시작.

## 새 에셋
| 경로 | 내용 |
|---|---|
| `/Game/Characters/BlackCat/Refine_20261125/SK_BlackCat_Refine` + `SK_BlackCat_Refine_Skeleton` | 공용 기준본. 다른 세션도 이 두 파일을 그대로 복사해서 쓴다 |
| `/Game/Cinematics/Stage1/Portal/RefinePortal20261126/` | 클립 7개(CompactPortal 5, JumpDown, Landing)와 `BCS_CinematicCatPrecision` |

교체 3개: `LS_Stage1_PortalExit`, `LS_Stage2_PortalArrival`, `BP_Stage2PortalArrival`. 해시·크기는 `manifest.json`.

임포트 설정: FBX `Desktop/CastleKit/BlackCat/Refine_20261125/FBX`(포탈 클립 v3), scale **1.0**, Import Normals, 루트모션·모프·피직스 없음, LeastDestructive(error 0.0001)·프레임 제거 안 함, 재질은 기존 `MI_BlackCat_*`. UE 본 수는 109(108 + 맨 위 `ARM_BlackCat` 노드, 참조 스케일 100). 원본 78본에는 없는 노드다. 압축 후 본 위치 오차는 7클립 전 프레임 최대 0.022cm.
다른 세션과 다를 수 있는 점: elevator 메모는 예전 경로 `/Game/Cinematics/Stage1/Portal/RefineCat20261126`를 가리킨다. cat-replace는 `/Game/Characters/BlackCat/Compact`에 다시 가져올 계획이었다. 둘 다 위 공용 경로의 파일로 맞춰야 스켈레톤이 하나가 된다.

## 적용 순서 (통합 담당 1명, 에디터를 모두 닫고)
**시퀀스 2개와 `BP_Stage2PortalArrival`은 반드시 함께 적용한다.** 새 도착 시퀀스(10.1초)에 옛 BP(인계 11.4초)를 쓰면 인계 전에 끝나 중단 처리된다. 스크립트는 셋을 한 번에 옮긴다.

1. `python -B apply_portal_cinematics.py` → 문제 0건인지 확인(결과 예: `dry_run.txt`)
2. `python -B apply_portal_cinematics.py --apply` → 교체 파일 3개를 `Saved/Backups/PortalCinematics-<시각>`에 백업한 뒤 복사
3. 새 에디터에서 두 시퀀스를 열어 본다. Stage1 출구부터 한 번 재생한다.
4. 되돌리기: `python -B apply_portal_cinematics.py --rollback <백업 폴더>`

본 프로젝트 파일이 원본 또는 1차 납품(05:52 적용본)이면 진행하고, 그 밖에는 멈춘다. 이때 덮지 말고 `Tools/author_bp.py`, `author_stage1.py`, `author_stage2.py`를 새 원본에 다시 실행한다(작성 기준 원본은 후보 `Saved/CompactPortal/Before`). 1차 위에 바로 적용해도 된다. 다른 세션이 `LS_Stage2_PortalArrival`을 고쳤다면 여기에 해당한다.

## 다시 만들 때
- 고양이 개선본: `Tools/cat_source.json`의 폴더·FBX 경로만 바꾸고 `import_cat.py` 실행. 같은 폴더에 다른 FBX가 있으면 멈춘다.
- 카메라·조명·타이밍: `Tools/shots.json`(Stage1), `Tools/shots2.json`(Stage2). 작성은 항상 본 프로젝트 원본에서 다시 시작한다.
- 실행: `launch_slot.py null|gpu <스크립트> <이름>`(공용 대기열). 캡처는 `D:/CatrunWork/portal/runs`.

## 검사 결과
`Review/qa.json`, `Review/cold_check.json` 참고. 아래 표는 최종 파일 기준으로 갱신한다.

| 항목 | 결과 |
|---|---|
| 실제 출구 재생 검사 | 19/19 통과 (최종 파일, d3d12) |
| 출발 길이 | 10.60초 |
| 앞발 접촉 오차(본 기준) | 0.0000cm |
| 걷기 발 미끄러짐 평균(출발 / 도착) | 0.021 / 0.017 cm/프레임 |
| 준비 앞발 / 마지막 접지까지 뒷발 이동 | 0.0003 / 0.0135 cm |
| 엉덩이 흔들기 극점 | f244, f250, f256, f262 |
| 도약 상승 / 끝에서 꼬리가 포탈을 지난 거리 | 72.0 / 24.8 cm |
| 도착 착지 앞발 / 앉은 발 이동 | 0.46 / 0.00 cm |
| 두 모델이 동시에 보인 프레임 | 0 |
| Stage2 제목 시각 / 종료 폭 / 남은 시간 | 10.27초 / 1170 / 898.8초 (원본: 12.77초 / 1170 / 898.8초) |
| 도착 뒤 출구 임차 재획득 | 성공(승강기 시작 조건) |
| 새 프로세스 재로드(무저장) | 성공, 없는 참조 0, 더티 패키지 0 |
| 본 프로젝트 dry-run | 문제 0건 (`dry_run.txt`) |


## 남은 것 / 확인 못 한 것
- 사용자 미술 검수(두 장면 구도·밝기·속도, Stage1 컷에서 거리를 건너뛰는 것, Stage2 복귀 컷이 정면 얼굴 대신 뒤쪽에서 올라가는 것).
- 소리는 새로 만들지 않았다. 실제 속도 사람 눈 재생이 아니라 연속 프레임·시트로 검토했다.
- 정면 걷기를 4초에서 3.0초로 줄인 것은 길이 단축 요구(B-05)와 예전 4초 요구가 부딪혀 한 판단이다. 되돌리려면 `shots.json`의 cut·stop을 30씩 늘린다(출구 11.6초).
- 7b1c 작업 사본의 도착 보정(컷 구도 수정)은 본 프로젝트에 들어가 있지 않았고, 이번 재구성이 그 요구(발판 잘림, 석상 가림)를 대신한다.
- cine-polish의 네이티브 패치(새 스테이지를 0.1초 검은 페이드로 시작)와 함께 쓸 때의 순서는 합쳐서 확인하지 않았다. BP는 페이드를 끄고 획득하므로 시작이 막히지는 않는다.
- 물결 효과는 화면에 보이지 않고 Stage2 시퀀스에 Stage1 맵 참조를 남겨 뺐다.
- 기존 검사 스크립트(`verify_stage1_departure_runtime.py`, `verify_stage2_arrival_runtime.py`, `stage1_departure_shots.py`, `stage2_arrival_revision.py`)는 옛 길이·컷·카메라 값을 고정해 두어 적용 뒤에는 실패하는 것이 정상이다. 전체 회귀의 `stage1_departure`, `stage2_arrival` 단계가 여기에 해당하며 값 갱신이 필요하다(이번에 고치지 않음).
