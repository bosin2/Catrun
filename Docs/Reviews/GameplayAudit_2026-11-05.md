# 현재 프로토타입 플레이 문제 감사 — 2026-11-05

> 과거 감사 기록: 아래는 후속 수정 전의 발견 사항이다. 현재 반영 상태는 [HANDOFF](../../HANDOFF.md) 상단을 따른다. 튜토리얼 최초 키 안내와 키 변경 연동 확장 제안은 사용자 지시로 취소됐으며 다시 적용하지 않는다.

## 범위와 확인 방법

현재 `main`의 로컬 변경을 포함한 C++와 실제 Blueprint 그래프/맵 속성을 읽었다. 갑옷·촛불, 플레이어·퍼즐, 메뉴·전환을 독립 에이전트 3명이 점검하고 메인이 증거를 대조했다. 게임 코드·설정·에셋은 수정하지 않았다. Computer Use, 입력 주입, 새 PIE, 빌드, 테스트는 실행하지 않았다. 켜져 있던 언리얼과 사용자의 플레이를 종료하거나 맵을 바꾸지 않았다.

로컬 MCP로 현재 에디터의 `MainMenu`와 아래 실제 에셋 속성/그래프를 조회했다. 첫 현재 맵 조회는 사용자의 PIE 중이어서 빈 값과 에디터 API 오류를 반환했다. 이후 사용자가 PIE를 끝낸 뒤 `MainMenu` 조회가 성공했다. 감사 증거는 `Saved/GameplayAudit20261105/`에 저장했다.

최근 **사용자 세션** 로그에는 MainMenu → Tutorial → Stage1 → Stage2 전환과 각 맵 로드가 기록되어 있다. 이는 전환 연결의 증거다. 감사 에이전트가 새 게임부터 모든 퍼즐을 직접 완주했다는 뜻은 아니며, 잡힘 방지 설정 여부나 Stage2 완주는 이 기록만으로 확정하지 않는다.

## 먼저 처리할 문제

### 1. 튜토리얼 계단 접근로에서 소리 이벤트가 버려짐 — P2, 현재 실행 로그 + 현재 맵 확인

- 사용자 세션에서 고양이가 `(-130,998,26)` 부근부터 계단 `Y1490 / Z-69`까지 이동할 때 `EmitSound: no floor cell near ...`가 15회 기록되었다.
- `SoundGridManager.cpp:224-228`은 이 경우 전파·청자 예약·시각화 이벤트 전에 `false`를 반환한다. 단순히 사운드 파일이 없는 것이 아니라 AI에게 전달할 게임플레이 소리 이벤트 자체가 생성되지 않는다.
- 현재 맵의 계단 입구 `StaticMeshActor_81`, 첫 계단 `82`, 마지막 계단 `90`, 하단 바닥 `91`에 `Tags=[]`임을 MCP로 확인했다. 사용 중인 `DA_SoundSettings.FloorTag`는 `SoundFloor`다. `CatrunGridData.cpp:92-95`의 베이크는 이 태그가 있는 바닥만 수집한다.
- 출구 트리거는 현재도 `(-130,1548,-16)`, 반범위 `(85,35,100)`, `WaitForCinematic=true`다. 누락 좌표는 출구 이전이다. 마지막 누락은 04:33:07 UTC, Stage1 전환은 04:33:13 UTC이므로 계단 연출 중의 무해한 경고로 제외하면 안 된다.
- 영향: 걸음·달리기 소리를 이용하는 위험 규칙이 접근로에서 끊긴다. 해당 지점의 방울 역시 같은 방출 함수로 실패할 조건이지만, 이번 로그에서 그 위치의 방울 입력을 직접 확인한 것은 아니다. 갑옷이 그곳을 절대 추격할 수 없다는 추가 결론도 보류한다.
- 수정 방향: 계단 접근로·하단까지 소리 그리드 범위와 높이 처리, 바닥 태그를 함께 점검한다. 닫힌 문의 소리 차단 규칙이나 전역 방울 예산을 다시 완화하는 방식은 원인에 맞지 않는다.

근거: `Saved/GameplayAudit20261105/user-session-log-snapshot.log:2423-2439`, `live-tuning-and-stairs.json`, `live-final-properties.json`; `Source/Catrun/Sound/SoundGridManager.cpp:224`, `Source/Catrun/Grid/CatrunGridData.cpp:92`.

### 2. Stage2 촛불의 위치 순찰이 없음 — P2, 요구 미완료 확정

- 현재 `ACatrunCandle::Tick`은 고정 위치에서 몸체와 시야를 회전하고 고양이를 추적한다. 위치를 옮기는 순찰 경로와 이동 구현은 없다.
- 현재 `BP_Candle`도 EventGraph 3개 노드에 별도의 위치 순찰 구현이 없다.
- 사용자가 명시한 “촛불이 위치를 옮기며 순찰” 요구는 아직 미완료다. “모든 촛불의 Tick이 고장 났다”는 진단과는 구분한다.
- 영향: 같은 위치의 시야 회전만 기다리면 되므로, 이동 경비를 피해 동선과 시간을 고르는 Stage2 플레이가 구현되지 않았다.
- 수정 방향: Stage2 전용 경로를 배치하고 벽·고양이·갑옷 충돌, 감지 중 정지, 시야 상실/문 연출 종료 후 복귀를 함께 구현한다. 튜토리얼 촛불의 고정 위치 규칙과 분리한다.

근거: `Source/Catrun/Monster/CatrunCandle.cpp:213`, `Saved/GameplayAudit20261105/live-player-and-candle-graphs.json`, `HANDOFF.md`의 남은 작업 2번.

### 3. Stage2 문 카메라 완화가 아직 미적용 — P2, 현재 맵 수치 확인

현재 `Stage2.CatrunStatuePuzzle_0.Reveal`의 이동 시간은 **0.65초**, 복귀는 **0.6초**다. A/B/C 세 `BP_StatuePresentation` 모두 화면 폭 **650**, 진동 강도 **0.0007**이다. 이전에 사용자가 지적한 빠르고 가까운 연출의 기존 값이 그대로 남아 있다.

완화 후보인 이동 2.0초 / 복귀 1.6초 / 폭 1050 / 진동 0.00015는 작성된 스크립트의 계획값일 뿐, 현재 맵 값이 아니다. 이 후보 자체가 최종적으로 좋은 구도라는 화면 검증도 아직 없다.

근거: `Saved/GameplayAudit20261105/live-tuning-and-stairs.json`, `live-more-properties.json`; `Scripts/Prototype/tune_stage2_reveal_camera.py:18-19`는 **감사 중 실행하지 않았다**.

### 4. 갑옷 회전·잡기 시작의 자세 불연속 원인이 남아 있음 — P2, 소스/설정 확인, 화면 재현은 미실행

- 잡기 시작 시 고양이를 향한 방향을 90도 단위 `SnapYaw`로 바꾸고 `SetActorRotation`으로 즉시 적용한다. 포획 시 갑옷의 방향이 순간적으로 바뀔 수 있는 코드다.
- 회전 중 소리를 들으면 원본 애니메이션의 실제 root 회전 곡선 대신 `경과시간/전체시간 × 90도`로 회전 인계를 계산한다. 원본 곡선이 비선형이면 중단 직전 포즈와 인계 방향이 달라진다.
- 현재 `BP_LivingArmor.TurnPlayRate=5`도 MCP로 확인했다. 빠른 재생과 위 두 인계 방식이 합쳐지면 방향 전환이 더 갑작스럽게 보일 수 있다.
- 원본 애니메이션 파일 자체가 손상되었다는 증거는 없다. 먼저 native 방향/캡슐과 BP 포즈의 인계를 수정·비교해야 한다. 이번 감사에서 화면을 직접 보고 자연스러움을 판정하지는 않았다.

근거: `Source/Catrun/Monster/CatrunArmor.cpp:173-175`, `:768`; `Saved/GameplayAudit20261105/live-final-properties.json`.

### 5. 첫 인트로 도중 종료 후 이어하기하면 조작 안내를 한 번도 못 봄 — P2, 현재 코드 + BP 그래프 확인

- 새 게임은 Tutorial 도착 시점에 진행을 저장한다. 인트로 완료 여부는 저장하지 않는다.
- 이어하기는 항상 `SkipIntro` 경로를 사용한다.
- 현재 `BP_TutorialIntro`의 이 경로는 `SetAnimInstanceClass → RestorePlayableStart`에서 끝난다. `RestorePlayableStart.then`은 미연결이다. 조작 안내 위젯 생성은 정상 `FinishIntro` 경로에만 있다.
- 재현 조건: 처음 새 게임을 시작하고 인트로가 끝나기 전에 종료 → 다음 실행에서 이어하기. 플레이 자체는 가능하지만 처음 배우는 조작 안내가 없다.
- 일반적인 잡힘 후 재시작에서 인트로와 문구를 생략하는 것은 사용자 의도다. 그 동작을 되돌릴 문제가 아니라, 최초 안내 미완료 상태와 반복 재시작을 구분할 문제다.

근거: `Source/Catrun/LevelFlow/CatrunLevelFlow.cpp:236-244`, `:410-417`; `Saved/GameplayAudit20261105/live-intro-graphs.json:4050`, `:2870`. 독립 리뷰도 현재 MCP 그래프에서 같은 연결을 확인했다. 이 새 이어하기 시나리오는 직접 플레이하지 않았다.

## 추가 재현이 필요한 항목

### 튜토리얼 일시정지·메뉴 복귀 누락 가능성 — 우선 확인

`CatrunLevelFlow.cpp:319`는 Tutorial에서 조기 반환하므로 공통 HUD와 Esc/P 입력 처리가 실행되지 않는다. 현재 `GM_Cat`은 기본 `Engine.PlayerController`, HUD `None`이며, `GM_Cat`/`BP_Cat`/`WBP_Tutorial_KeyHint` 전체 그래프에서도 대체 pause 경로를 찾지 못했다. **Tutorial LevelScript 자체는 이번 읽기 API에서 확인하지 못했다.** 따라서 “공통 기능 제외”는 확정이나, 사용자 입력으로 Esc/P를 눌렀을 때 결과는 재현 항목으로 남긴다. 누락이 맞다면 인트로·문구를 건드리지 않고 pause 기능만 독립 연결해야 한다.

근거: `Source/Catrun/LevelFlow/CatrunLevelFlow.cpp:319`, `Saved/GameplayAudit20261105/live-player-and-candle-graphs.json`, `live-map-properties.json`.

### 문 연출 시작과 소리 도착이 겹치면 갑옷이 그 소리를 잃음 — 조건부 소스 결함

동상 마지막 밀기의 발소리가 전파 중일 때 문 연출이 시작되면, 소리 관리자는 예약 이벤트를 큐에서 제거하고 전달하지만 갑옷은 퍼즐 정지 상태라 즉시 반환한다. 연출 후 이 이벤트를 다시 전달하는 경로가 없다. “잠깐 정지 후 재개” 과정에서 조사 원인이 사라질 수 있다. 현재 맵에서 해당 프레임 타이밍을 직접 재현하지 않았다. 방울은 Busy 종료 대기 때문에 대개 연출 전에 도착하므로, 우선 재현 대상은 마지막 밀기의 발소리다.

근거: `Source/Catrun/Sound/SoundGridManager.cpp:279-290`, `Source/Catrun/Monster/CatrunArmor.cpp:125`, `Source/Catrun/Interaction/CatrunPuzzleRevealComponent.cpp:36`.

### 순찰 도중 문을 열면 목표점 대신 원래 배치 위치로 향함 — 현재 배치의 직접 발현은 미확인

순찰도 `bReturningToPost=true`를 사용하는데, 문 열기 후에는 이 플래그만 보고 `PostLocation`으로 재계획한다. 해당 조건에서 목표 순찰점을 건너뛰는 코드 결함이 있다. 다만 현재 정식 맵의 MCP 조회에서 순찰점이 있는 갑옷은 Stage1 하단 복도 1기뿐이며, 두 점 `(500,2170)` / `(500,1840)` 사이에 현재 문 2개가 직접 놓여 있지 않다. 그러므로 지금 플레이에서 항상 경비가 되돌아간다는 상위 문제로 과장하지 않는다. 향후 문을 지나는 순찰 배치 전 수정이 필요하다.

근거: `Source/Catrun/Monster/CatrunArmor.cpp:530-539`, `:954`, `:402-406`; `Saved/GameplayAudit20261105/live-map-properties.json`, `live-tuning-and-stairs.json`, `live-more-properties.json`.

### 표시 시야와 실제 시야 차단 판정이 다름 — 배치별 재현 필요

`VisionFanComponent.cpp:104-115`의 표시용 ray는 WorldStatic 중 SoundWall/Obstacle 또는 native Door만 차단한다. 실제 감지는 `CatrunPerceptionPolicy.cpp:13-17`의 Visibility 검사도 사용한다. 따라서 동적 퍼즐문/동상 앞에서 보이는 위험 영역과 실제 감지 범위가 달라질 가능성이 있다. 이번 감사에서는 현재 gate/statue의 충돌 설정과 촛불 시야 교차까지 확정하지 않았으므로 조건부 점검 항목이다.

## 오류로 단정하지 않은 기록

- Stage1 벽 22종의 Nanite/반투명 재질 경고는 현재 로그에서 확인했다. 설치된 UE5.8 소스를 확인하면 지원하지 않는 조합은 일반 StaticMesh fallback 렌더링으로 전환한다. 이 경고만으로 벽 투명화 실패·고양이 가림·벽 소실을 확정하지 않는다.
- 갑옷의 끝점 17cm 정체 로그는 기존 도착 허용 처리 안에 들어간다. 그 한 줄만으로 경로 영구 정체라고 판단하지 않는다.
- 원래 인트로가 고장 났다는 새 증거는 없다. 사용자 확인과 기존 복구를 뒤집지 않는다.
- 이전 튜토리얼 방울 예산 500 문제는 현재 그대로가 아니다. MCP에서 현재 예산 650을 확인했다. 이번 계단 소리 누락은 예산이 아니라 유효 시작 그리드가 없는 실패다.
- 바구니가 현재 어떤 동선에서도 안전하다는 결론은 내리지 않았다. 이번 읽기 감사에서는 새로 확정할 바구니 결함을 찾지 못했다.

## 다음 작업 순서

1. 튜토리얼 계단 소리 그리드 누락을 수정하고 접근로의 걷기/달리기/방울을 각각 확인한다.
2. Tutorial Esc/P 일시정지와 메뉴 복귀를 사용자가 확인한다. 누락이면 기존 인트로를 유지하며 별도 연결한다.
3. Stage2 촛불 위치 순찰을 구현하고 퍼즐·충돌·감지와 함께 검증한다.
4. 갑옷 회전/포획 포즈 인계와 Stage2 문 카메라를 별도 작업으로 조정한다.
5. 최초 안내 완료 상태를 저장해 Continue 안내 누락을 보완하고, 소리 이벤트와 연출 정지의 경계 사례를 검사한다.

이번 작업에서 수정한 제품 파일은 없다. 이 보고서와 `Saved/GameplayAudit20261105`의 감사 자료만 추가했다. Git 커밋·푸시는 하지 않았다.
