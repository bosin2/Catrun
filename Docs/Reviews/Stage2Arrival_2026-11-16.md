# 스테이지2 포털 도착 연출

Stage1 포털로 마법회랑에 처음 도착하는 약 12초의 연출을 제작하고 canonical Stage2에 저장했다. 소스/에셋/자동 재생을 별도로 검증했다.

- 대본: 포털에서 출현·착지 → 첫 석상/발판/닫힌 Gate11 → 회랑 방향 → 기존 플레이 카메라 복귀. 약 12초, 넓고 차분한 구도.
- 연결: 승인된 Stage1 포털 전환 URL에만 `FromStage1Portal`을 추가한다. 설정된 Stage2 맵과 전환 의도를 확인하는 순수 조회를 BP에서 사용한다. 이어하기·포획 복구·메뉴 재시작·직접 로드는 제외한다.
- 구현: 기존 게임플레이 잠금을 재사용하고, 연출은 별도 BP와 LevelSequence가 담당한다. 실제 플레이어 위치/충돌/AnimBP를 바꾸지 않고 시퀀스 소유 모델을 사용한다. 카메라 컷은 KeepState, 나머지 트랙은 RestoreState로 중단 시 외부 카메라 소유권을 보존한다.
- 범위: canonical Stage2만 연결. 기존 Stage1 출발, 튜토리얼, SoundTest 미러, 문·퍼즐·AI 감지/소리 규칙은 보존한다. 오디오는 추가하지 않았다.

## 확인된 근거

- `Saved/Stage2Arrival20261116/Build01.log`: CatrunEditor 빌드 성공.
- `Saved/Stage2Arrival20261116/Automation01/index.json`: LevelFlow 30개 통과, 실패/미실행 0. 기존 튜토리얼 테스트의 viewport 없는 상황에서 나오는 경고 성공 1개 포함.
- `Saved/Stage2Arrival20261116/current_geometry_and_clips.json`: 현재 저장 맵의 실제 시작점, 메시 변환, 카메라 투영과 애니메이션 샘플.
- AssetProbe03: 원본 JumpDown/Landing 자세 연결 및 전체 Landing 구간 확인. 걷기 발 접지 속도로 이동 거리 약 100.8cm 산출.
- 독립 리뷰: 네이티브 흐름, 제작 소스 및 실제 PIE 이미지 리뷰 통과. 소유권 상실 시 카메라를 덮어쓰던 문제를 리뷰에서 발견하고 카메라 컷 KeepState/완료 override None으로 수정한 후 검증했다.

## 통합 검증

- Author05: `Saved/Stage2Arrival20261116/20261116-103733-225861/report.json`. 새 BP 2개와 LevelSequence 1개, Stage2 맵에 director/sequence actor 2개 저장.
- 최종 Polish03: `Saved/Stage2Arrival20261116/20261116-105934-118140/report.json`. 마지막 샷을 7–8초 정지 → 8–10초 완만한 복귀 → 10–12초 실제 플레이 카메라로 블렌드하도록 조정했다. 새 BP의 주석 GUID 메타데이터도 다시 저장했다.
- 최종 cold Audit03: `Saved/Stage2Arrival20261116/20261116-110018-329990/report.json`. 별도 프로세스에서 다시 읽어 그래프 컴파일, 바인딩, 카메라 곡선, 트랙 범위/복원 정책, 패키지 해시 일치 확인. 원래 있던 569개 액터의 식별/변환/태그와 이번 범위 밖 콘텐츠 928개 해시 보존. 이 프로세스에는 새 BP의 NodeGuid 경고가 없다.
- Render01: `Saved/Stage2Arrival20261116/Frames/20261116-103928/report.json`. 18개 시퀀스 프레임 렌더, 원본 애니메이션 자세 변화, 실제 Pawn 위치/AnimBP 보존, Stop 후 시각 모델/카메라 제거 확인. 이 샘플은 마지막 카메라 곡선 보정 전 기록이다.
- Runtime04: `Saved/Stage2Arrival20261116/Runtime/20261116-110106/report.json`. 최종 에셋으로 실제 Stage1 출구 트리거 → 기존 출발 연출 → 자동 Stage2 도착 연출 → 입력/HUD/AI 정지 해제, QuarterView 폭1170 복귀 성공. 첫 재생 뒤 재호출 차단, 재시작/직접 로드 생략, 명시적 중단, 컷 직후 director 삭제, 외부 카메라를 선택한 뒤 Abort/직접 Stop, 조종권 재획득 시 정리까지 성공.
- Runtime04의 `arrival-title00000.png`, `arrival-room00000.png`, `arrival-gate00000.png`, `arrival-blend00000.png`를 메인/별도 Astra 리뷰어가 직접 확인했다. 제목과 첫 석상·발판·철창문이 샷 전체에 걸쳐 보이며 최종 복귀도 넓은 구도다. 실재생 기록에서 7–8초 카메라 정지도 확인했다.

- Runtime05: `Saved/Stage2Arrival20261116/Runtime/20261116-110325/report.json`. Runtime04 시나리오 전체 재통과. 0.8/3.63/7.57/10.83초에 실제 생성된 고양이 메시 1개와 포털 메시 5개 모두 NoCollision/overlap false 확인. Sequencer가 고양이 actor 충돌 플래그를 true로 두더라도 실제 충돌을 제공하는 모든 primitive가 비활성임을 구분해 기록했다. 정상 완료 후 추적한 고양이/포털/카메라 spawnable 제거도 확인했다. 명시적 Stop의 별도 scrub 검증과 함께 보며, 모든 재로드에서 spawnable 전체 목록을 다시 수집한 검사는 아니다.
- 소유 Catrun 프로세스 정상 종료. 테스트 전 저장 파일/게임 설정/에디터 설정 3개를 원본으로 복원하고 SHA256 일치 확인: `Saved/Stage2Arrival20261116/restored-user-state.json`. 다른 프로젝트의 실행 중 에디터/MCP는 보존했다. 명시적 보호 대상 13개 패키지 해시도 최종 일치했다.

## 수정 위치

- `/Game/Cinematics/Stage2/Arrival/LS_Stage2_PortalArrival`: 카메라 구도/곡선, 고양이 JumpDown → Landing → Walk → Idle, 포털 시각 모델. 카메라 원본은 직교 투영이다.
- `/Game/Cinematics/Stage2/Arrival/BP_Stage2PortalArrival`: 도착 조건/준비 재시도, 연출 잠금, 시간 감시, 완료/중단 정리. 10초부터 2초 동안 기존 플레이 카메라로 돌아간다.
- `/Game/Cinematics/Stage2/Arrival/BP_Stage2ArrivalPortal`: 이번 도착 전용 포털 복제. 이전 Stage1 포털 에셋은 수정하지 않았다.
- `Source/Catrun/LevelFlow/CatrunLevelFlow.*`: 유효한 Stage1 포털 이동에만 도착 옵션을 싣고 BP에 순수 조건 조회를 제공한다. 저장/퍼즐/리스폰 규칙은 그대로다.
- 재현 도구: `Scripts/GameplayRepair/author_stage2_arrival.py`의 probe/author/polish/audit 및 `stage2_arrival_graph.py`, `render_stage2_arrival.py`, `verify_stage2_arrival_runtime.py`. 신규 생성 후 별도 polish 프로세스가 주석 GUID 메타데이터를 보존한다. 기존 에셋이 있을 때 author는 덮어쓰지 않는다.

## 검증 범위와 남은 관찰

- 화면/마우스 조작 없이 숨김 오프스크린 PIE를 사용했다. 실제 게임 월드와 자동 이동 연결을 검사했지만, API로 출구 체크포인트에 배치했으므로 **전체 스테이지 손플레이 완주와는 다르다**. 이어하기/포획 복귀의 도착 생략은 네이티브 의도 검사와 BP 분기로 검증했으며 모든 메뉴/포획 경로를 다시 손플레이하지 않았다.
- 외부 카메라 보존은 외부 시점 선택 직후 명시적 Abort/직접 Stop으로 확인했다. 감시 타이머만으로 외부 전환을 발견하는 상황을 독립적으로 재현한 것은 아니다.
- 실제 PIE에서 기존 레이 트레이싱 상주 지오메트리 진단 `87.792 MiB / 400 MiB`, 기존 Stage1 반투명/Nanite 재질 및 Stage1 BP 주석 GUID 경고가 남는다. 이번 새 BP 경고만 해결했고 기존 그래픽 설정/예산이나 출발 에셋은 변경하지 않았다.
- 첫 숨김 런타임은 기존 Stage1을 불러오는 동안 엔진 BoxComponent의 worker-thread ShowFlag assertion으로 종료됐다. 후속 검사에만 `-onethread`를 적용했고, 숨김 창 CPU 제한에 의한 준비 타이밍 문제는 프로세스 전용 `bThrottleCPUWhenNotForeground=False`로 분리했다. 프로젝트 그래픽/스레드 설정을 변경한 해결로 보고하지 않는다.
- SoundTest_Stage2 미러에는 연결하지 않았다. 오디오는 계속 중단 상태이며 이번 요청은 커밋/푸시 없이 로컬 저장이다.

최종 독립 리뷰: `.superpowers/sdd/2026-11-16-stage2-portal-arrival/final-review.md`. 작업 복구 기록은 같은 폴더의 `progress.md`에 남겼다.
