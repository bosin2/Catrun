# 플레이 흐름 연결

2026-11-03. 목표는 메뉴에서 현재 구현된 구간을 순서대로 실행하는 것이다. 스테이지 3은 제작 목표에 유지하지만 아직 맵과 완료 규칙이 없어 이번 실행 경로에는 넣지 않는다.

2026-11-11 출구 수정: Stage2와 SoundTest_Stage2 모두 Gate00을 열고 스테이지1 형태의 짧은 외부 복도를 추가했다. 완료 판정은 문을 통과한 뒤다. 아래의 초기 메뉴/맵 전환 설명과 과거 PIE 기록은 당시 기준이며, 최신 통합 상태는 `HANDOFF.md`를 따른다.

| 구간 | 실행 맵 | 다음 행동 |
|---|---|---|
| 시작 메뉴 | `/Game/Maps/MainMenu` | 기존 시작 버튼 → 튜토리얼 |
| 튜토리얼 | `/Game/Maps/SoundTest_Tutorial` | 기존 계단 연출의 `BP_LevelExit.CompleteTransition` → 스테이지 1 |
| 스테이지 1 | `/Game/Maps/SoundTest_Stage1` | 기존 `S1_DoorFrame_ExitToStage2` 안쪽 출구 → 스테이지 2 |
| 스테이지 2 | `/Game/Maps/Stage2` 및 SoundTest 미러 | 열린 `S2_Gate_00`을 지나 외부 복도 도달 → 같은 맵에 남고 완료 안내 |

사용자 결정: 스테이지 2 완료 후 자동으로 메뉴로 보내지 않고 현재 맵에 머무른다. 완료 이후에는 갑옷의 새 포획을 막고, 중복 완료 이벤트도 막는다. 고양이 이동은 유지한다. 미확정인 스테이지 3 목표·엔딩은 추가하지 않았다.

## 조작과 전환

- 게임 기본 시작 맵은 MainMenu.
- 스테이지 1·2의 `Esc` 또는 `P`: 일시정지 메뉴. 튜토리얼은 기존 UI를 사용하며 추가 HUD·메뉴를 생성하지 않는다. 계속하기 / 이 구간 처음부터 / 시작 메뉴로 버튼을 제공한다. PIE의 Esc 종료 단축키와 겹칠 때는 P를 사용한다.
- 전체 재시작은 메뉴에서 진행 포기를 한 번 더 확인한 뒤 실행한다. 퍼즐·적·표식·완료 상태를 새 월드로 초기화한다. 계속하기는 재시작 확인을 취소한다.
- 일반 플레이에서 R 즉시 재시작은 제거했다. 에디터 PIE에서만 `catrun.DebugRestart 1`로 켤 수 있으며 기본값은 0이다. 패키지에서는 이 단축키를 제공하지 않는다.
- 동상 방의 푸른 복구 장치에 접근해 F: 그 방의 동상만 초기 위치로 복구한다. 적·표식·플레이어·다른 방 동상은 유지한다. [튜토리얼 안내와 복구 장치](Playability.md) 참조.
- 공통 전환은 추가 페이드 없이 OpenLevel을 호출한다. 기존 인트로·계단 시네마틱의 페이드는 해당 BP가 소유한다. (2026-11-04 사용자 요청으로 추가 페이드 철회)
- 기존 튜토리얼 도착 옵션 `FromTutorial`을 유지한다. 스테이지 1→2의 새 시네마틱은 이번 작업에 포함하지 않는다.
- 자동 포획 재시작은 기존 RestartSubsystem을 유지하되, 이미 구간 전환·완료된 경우 뒤늦은 포획이나 재시작이 덮어쓰지 않도록 검사한다.

## 배치와 설정

- `Flow_ExitToStage2`: SoundTest_Stage1 `(101, 65, 65)`, BoxExtent `(65, 30, 80)`.
- `Flow_Stage2Complete`: Stage2와 SoundTest_Stage2 `(715, -80, 65)`, BoxExtent `(65, 30, 80)`, `bRequireCenterInside=true`. 바깥에서 캡슐만 닿는 것으로 완료되지 않는다.
- 트리거는 실제 플레이어 폰만 받는다. 다른 액터·은신/행동 중인 고양이는 완료시키지 않는다.
- 스테이지2 출구 철창은 바닥 아래로 내리고 충돌을 제거했다. 기존 문틀·문턱에 폭200cm/길이400cm의 바닥과 벽·천장·검은 안개를 이어 끝부분을 가린다. 옆벽·끝벽은 추락을 막는다. 동상·발판의 규칙과 배치는 변경하지 않는다.
- 공통 맵 순서·메뉴: `Config/DefaultGame.ini`의 `CatrunLevelFlowSettings`. 에디터 Project Settings에서도 편집할 수 있다.
- 기본 맵: `Config/DefaultEngine.ini`. 패키징 대상 4개 맵은 `DefaultGame.ini`에 명시했다.
- Stage3 준비 후 Stages 배열의 끝에 해당 맵을 추가하면 Stage2 출구는 다음 맵으로 진행한다. 마지막 맵의 완료 안내·최종 엔딩은 당시 확정 기획에 맞춰 교체한다.

현재 게임플레이가 모인 SoundTest 맵들을 사용한다. 원본 Tutorial·Stage1·Stage2를 덮어쓰거나 이름을 바꾸지 않았다. 원본 맵을 직접 열어 테스트할 때는 StageId 별칭으로 다음 실행 맵을 찾는다. 예전 `catrun.LevelRedirects`와 전역 TravelURL 가로채기는 제거했다.

## 코드·BP 역할

- `CatrunLevelFlow`: 맵 순서, 중복 전환 방지, 완료, 재시작·메뉴 복귀.
- `ACatrunStageExit`: 플레이어의 출구 진입 감지.
- 기존 WBP_MainMenu 및 BP_LevelExit: 버튼·연출 연결을 유지하고 마지막 호출을 C++ 흐름 함수로 연결.
- `OnStageCompleted`: 추후 BP 연출을 붙일 수 있는 완료 이벤트.
- `UCatrunPlayHUD`: 목표·구역 안내, 현재 표식/은신/포획 상태, 조작표, 완료 안내와 일시정지 메뉴. `ACatrunGuidanceZone`의 배치·문구·우선순위는 레벨에서 편집한다.

## 재현·검증 범위

- `Scripts/LevelFlow/setup_level_flow.py`: 변경 전 에셋을 Saved/Flow/Backups에 보존하고, 메뉴·튜토리얼 출구·Stage1/2 출구를 연결한다.
- `Scripts/LevelFlow/verify_level_flow_pie.py`: 실제 메뉴 이벤트·튜토리얼 완료 함수·출구 overlap·재시작·메뉴 복귀를 확인한다. 점검용 순간이동을 쓰므로 전체 동선·난이도·계단 영상 품질 검증은 아니다.
- Catrun 자동 테스트 12개 통과(기존 10개 + 경로 해석/완료 후 포획 방지 2개).
- UE 5.8.2 CatrunEditor 빌드 통과.
- 맵을 지정하지 않은 `-game -RenderOffscreen` 실행에서 기본 MainMenu 월드가 실제로 시작되고 검증용 종료 코드 0을 반환했다(`Saved/Logs/FlowStandalone.log`). 패키징된 실행 파일 검증은 아니다.
- 실제 PIE 세션에서 메뉴 시작 → 튜토리얼 완료 호출 → Stage1/2 출구 overlap → Stage2 유지·중복 완료 거부 → 재시작 후 완료 상태 초기화·시작 위치 복원 → 메뉴 복귀 → 다시 시작을 통과했다. 결과는 `Saved/Flow/pie-flow.json`과 `Saved/Logs/FlowPIE.log`에 기록된다.
- 위 최초 흐름 검증은 렌더링 없이 진행했다. 이후 HUD·복구·메뉴 변경 검증은 [Playability.md](Playability.md)에 별도로 기록한다. 패키지 빌드·수동 전체 플레이는 별도다.
