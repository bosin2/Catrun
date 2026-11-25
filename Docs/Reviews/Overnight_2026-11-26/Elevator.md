# Stage2→3 승강기 재연출 (2026-11-26)

## 상태
- 06:07 확인: 통합 담당이 본 프로젝트에 C++(후보와 같음), 새 에셋 13개(같음), 두 맵 배치(`Saved/ElevatorRedirect/author_apply.json` success)를 이미 적용했다. 이 세션이 본 프로젝트에 적용한 것은 없다(dry-run만). 본 프로젝트 검사는 아래 참고.
- **적용 뒤 바꾼 것 하나: 도착 먼지.** 06:04에 적용된 값은 `E23_CabinDust0~11`을 약 0.4배로 줄인다. 그런데 흰 알갱이의 실제 원인은 `M_E23_DustSoft` 컴파일 실패였고(회귀 세션) 본 프로젝트의 그 재질은 이미 수정된 상태다. 사용자는 먼지가 더 잘 보이길 원했으므로 크기를 원래대로 돌리는 값(`dust_scales`)을 `scripts`에 넣었다. `python apply_redirect.py map --apply`를 한 번 더 실행하면 먼지 크기만 되돌아간다(나머지 값은 같다). 후보에서 재실행해 보지는 않았다.
- 커밋·푸시 없음.
- 고양이 모델 Refine v4는 **사용자 승인 전**이다. 승인되지 않으면 `scripts/redirect_config.json`의 `cat`을 `{}`로 바꾸면 현재 78본 고양이로 배치된다. 이때는 아래 "현재 고양이로 쓸 때"를 따른다.

## 연출 순서
F → 1초 카메라 이동(띠·입력 잠금) → 올려다보기·점프·고리 당기기 → 착지 → 출발 충격·놀람 → 가장자리로 접근 → **바닥 시점에서 올라가는 고양이 얼굴(3.5초)** → **가장자리에서 내려다봄 → 몸을 돌려 안으로 걸음 → 한 바퀴 돌아 앞을 보고 식빵 → 눈을 감음(8.5초, 한 컷)** → 흔들리는 상승(3.6초) → 블랙아웃 → Stage3에서 객실이 올라오며 같은 식빵 → 잠금 충격·기상 → 하차 → 둘러보기 → 플레이 화면.

## 적용 순서
1. `python apply_redirect.py check`
2. C++: `elevator_redirect.patch`를 다른 패치와 함께 적용한다. 이 패치만 적용할 때는 `python apply_redirect.py native --apply`.
3. 본 프로젝트를 빌드한다(새 속성이 DLL에 있다. 헤더 변경이므로 에디터를 닫고 빌드).
4. `python apply_redirect.py assets --apply`
5. `python apply_redirect.py map` (dry-run) → `python apply_redirect.py map --apply`. 에디터를 닫은 상태에서 실행하며 대기열(light)을 스스로 잡는다.
6. 에디터 또는 `-game`으로 F부터 Stage3 복귀까지 한 번 재생한다.

순서를 바꾸지 말 것. 맵만 먼저 바꾸면 `map --apply`가 거부한다. DLL만 먼저 올라가면 승강기는 재생되지만 옛 클립을 새 컷 시간으로 자르므로 화면이 어긋난다.
되돌리기: `rollback --receipt <receipt>`(native, assets), 맵은 `Saved/ElevatorRedirect/Backups/Stage*_BeforeRedirect_*.umap`.

## C++ 변경 (`CatrunElevatorTransition.h/.cpp`만)
| 항목 | 내용 |
|---|---|
| 새 속성 | `LoafCamera`, `PeekLights`, `LoafLights`, `AscentHiddenActors`, `AscentShownActors`, `CinematicMesh`. 모두 비우면 보조광·구조물 전환·메시 교체가 꺼진다 |
| 컷 | 출발 6번째 클립(`PeekLoafIn`) 안에서 정면 → 바닥 → 안쪽 카메라. 마지막 클립은 반복 식빵, 3.6초 |
| 상승 | 부드럽게 출발한 뒤 일정 속도. 레일 이음매의 작은 덜컹. 카메라는 높이만 따라가고 흔들림은 따라가지 않아 객실이 흔들려 보인다 |
| 컷 첫 프레임 | `SetGameCameraCutThisFrame`(이전에는 두 컷이 섞여 번짐) |
| 도착 | 카메라를 승강장에 두고 객실만 올라온다(이전에는 카메라가 바닥판을 뚫고 올라옴) |
| 하차 | 고양이가 Stage3 조명도 받는다(이전에는 밝은 바닥 위 검은 실루엣) |
| 복귀 | 고양이의 화면 위치를 유지하며 이동하고 직교 화면과 같은 크기로 끝난다(이전에는 화면 아래로 빠지고 끝에서 크기가 튐) |
| F 이전 | 객실에 타면 대기 카메라가 객실을 비춘다(이전에는 시계에 가려짐, 감수 D-02) |
| 메시 | 소유하는 동안만 `CinematicMesh`를 입고 복원. 루트 이동이 큰 포즈가 가림 판정으로 사라지지 않게 경계를 넓힘 |

## 맵 변경 (E23 태그 액터만)
- Stage2: `E23_Director` 값, `E23_Shot_Below`·`E23_Shot_Ring`·`E23_Shot_Ascent` 위치·화각, 새 액터 `E23_Shot_Loaf`, `E23_Lift_FaceFill`, `E23_Shot_FloorBounce`, `E23_Lift_LoafFill`, `E23_Guide_Up_*` 8개, `E23_Lift_RopeUp_*` 5개(모두 평소에는 숨김).
- Stage3: `E23_Director`(클립 4개, `CinematicMesh`, 복귀 1.6초), `E23_Shot_Arrival` 각도·화각, `E23_CabinDust0~11` 크기(위 "상태" 참고), `E23_Lift_*`·`E23_Guide_*` 30개의 라이팅 채널 0 추가(플레이 화면에서 새까만 실루엣).
- 값은 모두 `scripts/redirect_config.json`에 있다.

## 새 에셋
`manifest.json`에 경로와 SHA256. `payload/`가 실제 파일이다.
- `/Game/Cinematics/Stage1/Portal/RefineCat20261126/SK_BlackCat_Refine`, `SK_BlackCat_Refine_Skeleton`: 승강기 전용 사본. 본 프로젝트에는 같은 FBX를 가져온 `/Game/Characters/BlackCat/Refine_20261125/SK_BlackCat_Refine`도 있다(다른 세션). 둘로 나뉘어 있을 뿐 동작에는 문제가 없다. 하나로 합치려면 `scripts/import_refine.py`의 `MESHDIR`를 그 경로로 바꿔 클립을 다시 가져오고 `redirect_config.json`의 `cat.mesh`를 바꾼다.
- `/Game/Cinematics/ElevatorTransition/RefineCat/`: 승강기 클립 8개, `PeekLoafIn`, `CautiousWalk`, 압축 설정 1개.
- 새 클립 원본·재제작 스크립트: `animation/`. 78본 원본 동작을 만든 뒤 Refine 변환 스크립트로 옮긴다.

## 현재 고양이로 쓸 때
78본 클립은 `animation/AN_BlackCat_Elevator_PeekLoafIn_78bone.fbx`다. 이것을 `scripts`의 이전 가져오기(후보 `Scripts/ElevatorRedirect/import_clip.py`)로 가져와야 한다. 후보의 `Content/Cinematics/ElevatorTransition/Animations`에 가져온 사본이 있으나 이번 `payload`에는 넣지 않았다.

## 검사와 화면
- 검사: `verify_report.json`, 실제 PIE d3d12, **74개 모두 통과**(기존 58개 + 새 16개). 새 검사는 안쪽 컷 길이·위치·연속성, 식빵 위치의 블랙아웃 연속(Stage2·Stage3 차이 0.1cm), 보조광·구조물 전환과 복원, 안쪽 컷 도중 취소, 플레이 고양이 메시·재질·ABP 복원(취소·도착·스킵)이다. 기존 검사 문장은 그대로 두고 사본에만 더했다(`scripts/verify_redirect.py`).
- 첫 실행에서는 늦은 취소 뒤 메시 위치가 1e-14cm 달라 완전 일치 검사 1개가 실패했다. 그 항목만 1e-4 허용으로 바꿨다(기존 취소 검사는 완전 일치 그대로 통과).
- **본 프로젝트(적용 뒤, 06:25~06:27)**: 같은 검사를 저장 없이 격리 UserDir·d3d12로 실행해 **74개 모두 통과**. 실행 전후 맵·DLL·승강기 애니메이션 해시 같음. 결과 `C:/Users/whghk/Catrun/Saved/ElevatorRedirect/main_verify_report.json`.
- 얼굴 컷 눈 측정(본 프로젝트, 84표본): 양쪽 눈 모두 렌즈에서 막힌 표본 0, 화면 높이 0.29~0.42(검은 띠 안쪽 0.10~0.90), 가로 0.43~0.56. 선 검사는 화면에서 사라지는 컬링을 잡지 못하므로 5프레임 간격 시트 `D:/CatrunWork/elevator/G03_below.png`로 함께 확인했다.
- 영상: `Elevator_Full_30fps.mp4` 1280x720, 49초, 고정 30fps의 실제 `-game` d3d12 화면. 모든 프레임을 이어 붙였고 화면 편집은 없다. Stage2 → Stage3 로딩 구간의 실제 대기 시간은 들어 있지 않다.
- 전후: `BeforeAfter.png`, `frames/`. 이전 사진은 에디터 뷰포트 비율이고 새 사진은 16:9다.
- 직접 본 것: 컷마다 정지 프레임. 실시간 재생을 눈으로 본 검토나 사람의 수동 플레이는 아니다.
- 검사 한계는 이전과 같다(복도·창고·승강기 진입은 위치 배치 fixture).

| 찾은 문제 | 고친 방법 | 화면 확인 |
|---|---|---|
| 얼굴이 검은 실루엣 | 승강기에 붙은 약한 크림색 보조광 + 바닥 반사광(얼굴 컷에서만) | 확인 |
| 내려다본 뒤 뒷걸음질로 돌아옴 | 몸을 돌려 걸어 들어와 식빵까지 새 클립 | 확인 |
| 상승 중 객실이 도르래·가로보를 뚫음, 허공의 밧줄 막대 | 상승 중 숨기고 레일·밧줄을 위로 연장 | 확인 |
| Refine 고양이가 얼굴 컷 중간에 사라짐 | 경계 확장(루트 이동 때문에 가림 판정) | 확인 |
| 컷 첫 프레임 번짐 | 카메라 컷 표시 | 확인 |
| 도착 카메라가 바닥판 통과 | 카메라 고정 | 확인 |
| 하차 때 검은 고양이 | 라이팅 채널 | 확인 |
| 복귀 때 고양이가 화면 밖, 끝에서 크기 튐 | 화면 위치 유지, 직교 크기에 맞춤 | 확인. 1~2프레임의 작은 원근 차이는 남음. 이동 중 벽이 잠깐 앞을 지나지만 고양이는 보임 |
| F 전 객실이 시계에 가림 | 대기 카메라 구도 | 확인 |
| Stage3 승강기 외부가 검은 덩어리 | 라이팅 채널 0 | 확인 |

## 감수 항목과 남은 제안 (적용 동결 요청으로 더 바꾸지 않음)
- D-02(F 전 칸이 위쪽에 걸림): 구도를 바꿔 칸 전체가 화면 높이 5~80%에 보인다. 시계는 위쪽 도르래에만 걸친다.
- D-03(늘어짐): **바꾸지 않았다.** 지금은 F부터 조작 복귀까지 46.2초(Stage3 로딩 제외)로, 식빵 장면이 들어가 이전 40.6초보다 길다. 하차 보행 10.8초는 그대로다. 줄일 때의 후보: 하차 컷을 이미 60cm 걸은 상태로 시작(-2.3초), 보행 26→30cm/s와 재생 배율 2→2.31(-1.0초), 둘러보기 끝과 복귀 겹치기(-0.7초), 놀람 뒤 정지 구간(-0.4초), 기상 뒤 정지 구간(-0.45초), 상승 3.6→3.0초(-0.6초). 합치면 약 -5.5초. C++와 Stage3 값 변경, 재검사가 필요하다.
- `Shot_Ring`은 구도 변화가 적고 오른쪽이 어둡다. 화각을 줄여 완화했지만 객실 정중앙 구도는 아니다.
- 꼬리 부풀기, 임시 기계음 3종, Stage3 전경 공개는 이번 범위가 아니다.
