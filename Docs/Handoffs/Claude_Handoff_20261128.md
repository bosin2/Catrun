# Claude 인수인계 — 2026-11-28 (촛불 순찰·갑옷 영역·레버 소리·성문 진동·개발 옵션)

다음 Claude가 읽는 문서. 이 날짜 작업의 사실·결정·남은 일만 적는다. 이전 이력은 `HANDOFF.md`, 규칙은 `CLAUDE.md`·`Docs/Handoffs/AI_WorkGuide_20261125.md`.

## 상태 한 줄
- 모든 변경은 브랜치 **`claude/five-additional-tasks-255e82`** 한 커밋으로 GitHub(`bosin2/Catrun`)에 푸시했다(기준 `a7294e7`). main에는 병합하지 않았다.
- 작업은 main 체크아웃 `C:\Users\PC\Desktop\Catrun`에서 했고, 그 작업 트리에도 같은 내용이 미커밋으로 남아 있다.
- main에서 `CatrunEditor Win64 Development` 빌드 성공, `Automation RunTests Catrun` **184개, 실패 0**(일반 173 + 경고 11, 경고 11은 기존과 동일). 판정은 `index.json` 기준.
- 사용자가 최종 상태로 플레이테스트한 뒤 커밋을 요청했다.

## 사용자가 직접 한 작업 (같은 커밋에 포함)
- `Content/Maps/Stage1.umap`, `Stage2.umap`, `Stage3.umap`: 맵 로직 반영을 위한 객체 위치 수정. 사용자가 에디터에서 따로 작업했다.
- `Stage3.umap`에는 아래의 `ReleaseSoundBudget=500`도 들어 있다(MCP로 값 설정, 사용자가 저장). 저장 전 원본 백업은 `Saved/Backup_20261128_LeverSound/Stage3.umap`.
- `Config/DefaultEngine.ini`의 `SecurityToken` 한 줄은 에디터가 자동으로 넣은 것이라 커밋하지 않았다.
- Blueprint·재질·DataAsset은 수정하지 않았다(기존 BP 수정 금지 규칙).

## 변경 내용 (파일 → 동작)

### 1·2. 순찰 촛불 — `Monster/CatrunCandle.{h,cpp}`
- `bPatrolEnabled` 이고 경로점이 있는 촛불만 대상. **제자리 촛불은 기존 좌우 sweep 그대로.**
- 이동 순찰 중에는 sweep 없음: `SweepOffset`을 0으로 되돌리고 정면만 본다.
- `bPatrolFaceTravelDirection`(기본 true): 액터 yaw를 다음 지점 방향으로 `PatrolTurnSpeed`(180°/s)만큼 돌린다. 다 돌기 전에는 이동하지 않는다. 대기 중에도 회전한다. false면 배치 방향을 고정한다.
- `PatrolEncounterDistance`(40cm) 앞쪽 캡슐 스윕에서 **ACatrunArmor** 또는 **ACatrunStatuePuzzle.Links[].Statue**를 만나면 `ReversePatrol()`을 호출한다. 직전 지점으로 돌아가며, 첫 구간처럼 직전 지점이 없으면 반대쪽으로 간다. 이때 `PatrolEncounterPause`(0.3초)만큼 멈춘다.
- 뒤에서 오는 갑옷은 무시한다. 일반 벽·장애물에 막히면 기존처럼 멈춘다.
- loop 순찰도 `PatrolStep` 방향을 사용하도록 바꿨다(기본 +1이라 기존 동작은 같다).
- 현재 Stage2 촛불 3개(`BP_Candle_C_0~2`)는 **모두 `bPatrolEnabled=false`**다. 기획상 순찰을 켤지는 사용자 결정 사항이다.
- 테스트: `Catrun.PrototypeAI.CandlePatrolFacesAheadAndTurnsBackAtStatueOrArmor`.

### 3. 갑옷 이동 영역 시각화 — `Sound/SoundGridManager.{h,cpp}`
- 갑옷 경로 = SoundGridManager의 25cm 격자 위 4방향 A*(`Pathfinding/ArmorPathfinder`).
  - 설 수 있는 칸 = `SoundFloor` 위 + `SoundWall`/`SoundObstacle`/동상과 `ArmorClearance`(35cm) 이상 떨어진 칸.
  - 꺾을 때마다 비용 `ArmorTurnPenalty`가 붙는다. 문은 통과 레인으로만 지나간다.
  - 다시 굽기: SoundGridManager 디테일의 **Build Grid** 버튼 → 맵 저장.
- 추가한 것:
  - `bDebugDrawArmorArea`(에디터/PIE 표시), 콘솔 `catrun.DebugArmorArea 1`.
  - 파란색 = 갑옷이 설 수 있음, **주황색 = 바닥은 있으나 갑옷에게 좁음**, 빨간 선 = 벽 경계.
  - 표시는 **DrawDebugLine 가로 줄무늬**(같은 종류 칸이 이어지면 선 하나로 합침). `DrawDebugPoint`는 사용자 화면에서 안 보였다.
  - PIE에서는 고양이 반경 25m만 그린다.

### 4·5. 레버(봉쇄 고리) 소리 범위 — `Interaction/CatrunStage3Objectives.{h,cpp}`, `Sound/SoundTypes.h`, `Sound/SoundGridManager.cpp`
- `FCatrunSoundEvent.BudgetOverride`를 추가했다(UPROPERTY 아님, 0 이하이면 무시).
- `ACatrunStage3Objectives::ReleaseSoundBudget`: 0이면 Large 기본값을 쓴다.
- **중요한 사실**: Stage3 SoundGridManager는 `/Game/Environment/Stage3/SoundReaction_20261125/DA_Stage3DeviceSoundSettings`를 쓰고, 여기서 **LargeBudget=1800**이다. 공용 `DA_SoundSettings`(500)가 아니다.
- `SoundGridManager.PlayerBellBudgetOverride=500`은 **고양이 방울** 범위다. 원래 설계값이므로 바꾸지 않았다.
- 사용자 요청으로 Stage3 `S3_Objectives.ReleaseSoundBudget = 500`으로 설정했다. 맵 저장은 확인했지만, 그 후 플레이로는 아직 검증 전이다. 로그에 `EmitSound: device from S3_Objectives ... budget=500`이 나와야 한다.
- 로그 보강:
  - 소리를 낼 때: `EmitSound: <bell|footstep|device> from <라벨> at (x,y), size= budget= reached=`
  - 갑옷이 들을 때: `<이름> (<라벨>) at (x,y) heard a sound (size, remaining)`. 기존 스크립트가 쓰는 "heard a sound" 문자열은 유지했다.
  - 통로 거리 = budget − remaining.

### 5. 최종 성문 진동 — `Interaction/CatrunStage3Objectives.cpp`
- 원인: `BP_S3Polish_Presenter`가 `CS_GateMotion`(duration −1, 무한)을 시작하고 멈추지 않는다. `CS_GateImpact`는 0.38초로 문제없다.
- C++ 수정:
  - 최종문이 `FinalGateDuration`에 도달하면 `StopAllInstancesOfCameraShake(GateMotionShake, false)`로 블렌드아웃한다.
  - D1/D2 동상 문은 퍼즐 `Completed` 이벤트에서 같은 처리를 한다.
- `GateMotionShake`는 UPROPERTY이고 기본값은 CS_GateMotion 경로다. BP는 수정하지 않았다.
- 화면 확인 전.

### 개발 탭 UI (Esc → 설정 → 개발) — `Settings/CatrunSettingsWidget.{h,cpp}`, `Settings/CatrunUserSettings.{h,cpp}`, `Player/CatrunSprintComponent.{h,cpp}`
- WBP_Setting BP는 그대로 두었다.
  - `NativeOnInitialized`에서 `NoArmorCaptureCheckBox`의 행을 반사(reflection)로 복제한다(`CopyLook`: Slot/Slots/Content/Parent/Navigation/delegate/instanced/transient 제외).
  - 복제한 행은 Slate 생성 전에 `DeveloperGroup` VerticalBox에 삽입된다.
- 순서: "갑옷에게 잡히지 않기"(기존) → **"갑옷 이동 영역 보기"**(`ArmorAreaCheckBox`, cvar `catrun.DebugArmorArea`) → **"스태미나 무제한"**(`InfiniteStaminaCheckBox`, cvar `catrun.InfiniteStamina`).
- 체크하면 즉시 적용되고 이번 실행에만 유지된다. `IsDeveloperModeAvailable()`일 때만 만든다(Shipping 제외).
- 스태미나 무제한: `AdvanceStamina` 맨 앞에서 최대값을 유지하고 지침을 해제한다. 달리기 자체는 정상이다.
- 방향키 포커스 목록(case 3)에 두 체크박스를 추가했다. BP의 Tab 순환 규칙에는 들어 있지 않다.
- 테스트: `Catrun.Settings.ArmorAreaRowBelowNoArmorCapture`(위치·라벨·스타일·높이·cvar), `Catrun.Player.DeveloperInfiniteStaminaNeverDrains`.

## 빌드·검증 방법 (이번에 쓴 것)
- 에디터가 켜져 있으면 Live Coding 때문에 UBT가 거부한다. 새 UPROPERTY/UFUNCTION이 있으므로 **에디터를 닫고** 빌드해야 한다.
  - `Build.bat CatrunEditor Win64 Development -Project=<main>\Catrun.uproject -WaitMutex -NoHotReload`
- 테스트: `UnrealEditor-Cmd.exe <uproject> -unattended -nop4 -nullrhi -nosound -UserDir=<임시> -ExecCmds="Automation RunTests Catrun" -TestExit="Automation Test Queue Empty" -ReportExportPath=<폴더>` → `index.json`.
- 맵 저장은 MCP `save_assets`/`save_actor`로 안 됐다(레벨을 에셋으로 못 찾음, 외부 액터 아님). 값을 설정한 뒤 사용자에게 Ctrl+S를 요청했다.

## 남은 일 / 확인 필요
1. 브랜치를 main에 병합할지는 팀 결정이다(PR 미생성).
2. Stage2 촛불 순찰을 켤지 결정(사용자).
3. Stage3 갑옷이 막히는 지점: 영역 표시의 주황색 구간을 보고 원인을 판정한다(통로 70cm 미만 / `SoundFloor` 누락 / 잘못된 `SoundObstacle` / 재굽기 누락).
