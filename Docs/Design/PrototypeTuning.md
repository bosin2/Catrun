> **과거 조정표 주의 · 2026-11-25:** 아래 수치는 여러 시점의 기록이다. 현행 값/정책은 [전체 기획서](GameDesign.md)의 이동53/79/134, 방울행동1초, 저장v4·완료퍼즐/남은시간, 일반시작점 복원, 스테이지별600/900초 임시 배분을 따른다. 아래 스키마1·동상미저장·2.8초·복구장치·옛시퀀스 길이를 최신 설정으로 재적용하지 않는다. 개별 최종값은 실제 BP/DA/맵 인스턴스를 확인한다.

# 프로토타입 조정 위치

2026-11-04 작업용 안내에서 시작해 방울·설정, 2026-11-11 포털·문 카메라 조정 위치를 반영했다. C++ 기본값과 배치된 Blueprint의 덮어쓴 값은 다를 수 있으므로 최종 PIE 검증 기록을 함께 확인한다.

| 조정 대상 | 언리얼에서 열 위치 | 담당 값 / 역할 |
|---|---|---|
| 스테이지별 게임 카메라 | 프로젝트 설정 → Catrun Level Flow → Camera Profiles | Tutorial 1.0, Stage1 1.15, Stage2 1.30. 원래 직교 카메라 너비에 곱한다. 튜토리얼은 원본 유지 |
| 게임 진행 경로 | 프로젝트 설정 → Catrun Level Flow → Stages | 메인메뉴와 플레이 가능한 맵 순서. Stage3 제외 |
| 바구니 위치·방향 | Tutorial/Stage1/Stage2 및 각 SoundTest 맵의 HideBasket 액터와 ExternalBody/ExternalCloth | 2026-11-11 기준 입구 월드 yaw: Tutorial180, Stage1 두 개0, Stage2 세 개90. 몸체·천·OpenDirectionLocal·ExitDirectionGuide를 함께 맞춘다. 좌표와 검사 절차는 `Docs/Reviews/BasketDoors_2026-11-11.md` 참고. 과거 배치 스크립트로 덮어쓰지 않는다 |
| 튜토리얼 복도/방 문 | Tutorial 및 SoundTest_Tutorial → `Door_Tutorial_Corridor`, `Door_Tutorial_Bedroom` | 복도는 문짝 메시/충돌 없이 문틀만 유지. 방 문은 bStartOpen=false 및 기존 갑옷 개방 유지 |
| Stage2 아래 일반 문 | Stage2 및 SoundTest_Stage2 → `S2_Gate_04_Bars`, `S2_Gate_07_Bars` | z=-261cm, NoCollision, SoundWall 태그 제거로 처음부터 열림. 석상 게이트02/05/11과 퍼즐 링크는 변경하지 않는다 |
| Stage2 최종 탈출구 | Stage2 및 SoundTest_Stage2 → `S2_Gate_00_Bars`, `S2_ExitCorridor_*`, `Flow_Stage2Complete` | 철창 z=-261cm/NoCollision. 문 밖200×400cm 복도, 기존 Stage1 벽·천장·검은 안개 에셋 재사용. 완료 트리거(715,-80,65), Extent(65,30,80), 중심 진입 필수. 새 시네마틱/Stage3 이동 없음 |
| Stage1→2 포털 구도·속도 | `/Game/Cinematics/Stage1/Portal/LS_Stage1_PortalExit` | 30fps, 총309프레임(10.3초). 걷기0–96, 살피기96–240, 점프240–285, 마무리285–309. 각 구간 끝은 다음 구간 시작이다. 카메라 Transform/FOV와 고양이 애니메이션 재생률을 Sequencer에서 함께 조정 |
| 포털 문양·발광 | 같은 폴더 `M_Stage1PortalBlue` | 기존 UV/마스크를 보존한 Custom 노드의 분할 원호·팔각형·마름모와 색/세기를 Material Editor에서 편집. 저장/이동 연결은 `BP_Stage1PortalExit` 소유 그대로 |
| 갑옷 회전 속도 | `/Game/Characters/LivingArmor/Blueprints/BP_LivingArmor` 클래스 기본값 | TurnPlayRate. 기본5; 기존2.5초 회전을 약0.5초에 재생 |
| 갑옷 재생 전환 | 같은 BP → LocomotionBlendSeconds / bUseBlueprintAnimation | 0.08초. 회전·문 클립 진입/이탈은 네이티브 루트 보정을 위해 0초. Final `ABP_ArmorPresentation`의 DefaultSlot 사용 |
| 붙잡기 애니메이션 | 같은 BP의 CapturePresentation 컴포넌트 | bUseBlueprintPresentation=true, CatPickupAnimation=`AN_BlackCat_CaughtHeld`, PickupPlayRate=1. 고양이 기존 이동 AnimBP는 그대로 복원 |
| 붙잡기 알림 | `/Game/Characters/LivingArmor/Final/Animations/AM_ArmorPickupPresentation` | CaptureGrab=2.3초, CaptureFinished=6.85초. 원본 7초 Pickup은 보존. 재생률/클립 변경 시 네이티브 제한 시간 이전인지 확인 |
| 재생별 세션 소유 | `/Game/Characters/LivingArmor/Blueprints/BP_CapturePlayback` | PickupMontage / CaughtCatClip 기본값. OriginSessionId·취소 상태는 조정값이 아닌 각 재생의 소유 정보 |
| 붙잡기 구도와 타이밍 | `/Game/Systems/Sound/DA_SoundSettings` → Armor Catch | CatchHoldOffset=(8,0,15), CatchGrabBlendTime=0.3, CatchGrabLatestTime=3, 카메라 전환=0.5, 암전=1, 검정 유지=0.3초 |
| 카메라 벽 검사 | CapturePresentation → CameraProbeRadius | 후보 카메라 위치와 이동 경로를 구체로 검사 |
| 촛불 몸체 충돌 | `/Game/Characters/CandleMonster/Blueprints/BP_Candle` → BlockingCapsule | 반지름·높이·상대 위치. 실제 메시와 통로 폭에 맞춰 조정 |
| 캣홀 주변 방울 금지 | 각 맵의 CatrunNoBellZone → Box | 몸체가 영역에 닿으면 입력 및 뒤늦은 방울 소리 발생을 차단 |
| 설명용 디버그 UI | 콘솔 `catrun.DebugGuidance 1` / `0` | 기본0. 정상 플레이 설명 패널은 숨기고 일시정지 메뉴는 유지 |
| 갑옷에게 잡히지 않는 디버그 모드 | 콘솔 `catrun.NoArmorCapture 1` 켜기 / `catrun.NoArmorCapture 0` 끄기 | 기본0. Shipping 제외 빌드에서 새 붙잡기만 차단하며 감지·추적·소리 반응·충돌은 유지한다. 끄면 감지 범위 안에서도 다시 잡힌다. 이미 시작된 붙잡기는 정상 진행한다. C++ 빌드 반영 후 사용 |
| 잡힘 방지 체크박스 | 설정 → 개발 → 갑옷에게 잡히지 않기 | 실제 `WBP_Setting`의 `NoArmorCaptureCheckBox`. 변경은 초안이며 `적용` 때 기존 C++ 디버그 변수에 반영한다. 현재 프로세스 실행 동안만 유지. Shipping에서는 개발 그룹 전체 숨김 |
| 이어하기 | 메인메뉴 → 이어하기 | 마지막으로 진입한 스테이지의 시작점부터 재개. 저장 없음·손상·지원하지 않는 저장 버전·누락된 맵이면 비활성화. 새 게임은 원래 인트로를 유지하며, 이어하기는 기존 재시작 경로로 인트로를 건너뜀 |
| 진행 저장 | `CatrunLevelFlow` / `CatrunProgressSave` | `CatrunProgress` 슬롯, 사용자0, 스키마1. 메뉴에서 새 게임/이어하기로 시작한 세션의 실제 구간 도착 시 저장. 에디터에서 맵을 직접 실행한 개발 플레이는 저장하지 않음. 고양이의 구간 내 위치·동상 상태는 저장 대상이 아님 |
| 옵션 값과 저장 | `/Game/UI/Settings/WBP_Setting` / `CatrunUserSettings` | 전체 음량, 창/테두리 없는 창, 화질, 프레임 제한, 수직동기화, 키 설정8개. 전체 키 초안을 먼저 검증하고 `적용`할 때 저장·반영한다. 닫기는 미적용 초안을 버림. 기존 전체 화면·사용자 지정 화질·비표준 FPS는 `현재 설정 유지`로 보존 |
| 키 설정 | 설정 → 조작 / `CatrunInputBindings` | 앞으로/뒤로/왼쪽/오른쪽/달리기/살금살금/방울/상호작용. 기본 W/S/A/D/LeftShift/LeftControl/SpaceBar/F. 단일 키만 허용하고 중복은 적용 시 거부한다. 물리 Shift/Ctrl 단독은 허용, 조합 키와 Esc 배정은 거부. 기존 게임패드 매핑은 유지 |
| 메뉴 디자인·BP 연결 | `/Game/UI/WBP_MainMenu`, `/Game/UI/Settings/WBP_Setting` | 기존 로고·발바닥·시작을 보존. 전체 반투명 배경(.68), 얇은 선, Designer의 카테고리/스크롤 본문/하단 버튼으로 편집한다. 마우스 클릭·휠이 기본, Tab은 보조. 호버/포커스 밑줄은 `UpdateSettingsAffordances`/`UpdateMenuAffordances`에서 수정 |
| 공용 설정 열기/닫기 | `CatrunSettingsSubsystem` / `CatrunSettingsWidget` | 메인메뉴 옵션과 인게임 Esc가 같은 BP를 연다. 닫기/Esc는 native 소유 상태를 복원한다. 키 선택 중 Esc는 선택만 취소. 원래 일시정지·다른 입력 잠금 보존. 화면/음량 초안은 BP, 키 검증과 상태 복원은 C++ |
| 갑옷 경로 디버그 | 콘솔 `catrun.DebugArmorPaths 1` / `0` | 기본0. 켰을 때만 DebugDrawPath가 활성화된 갑옷의 청록색 경로·자홍색 목표를 표시한다. 기존 맵의 true 값만으로는 표시되지 않는다. 황금색 소리 파동과 원래 파란 감지 영역은 별개 |
| 방울 연출·발음 시점 | `/Game/Systems/Player/Interaction/BP_CatActions` → TryBell의 BeginBellAction 입력 | EmitDelay=0.566667초, Duration=2.8초. 클립은 BP에서 조정하고 C++가 세션별 타이머·이동 복구를 소유한다. 포획 시작 시 방울을 먼저 취소해 만료된 타이머가 잡힘 자세를 덮어쓰지 않게 한다 |
| 방울 성공 표시 | `/Game/Systems/Sound/DA_SoundSettings` → Bell → Feedback | BellIndicatorDuration=1.2초(0이면 끔), BellIndicatorOffset=(0,0,65)cm, BellIndicatorSize=56 화면/UI 단위, BellIndicatorColor=(1,0.78,0.22,1). 오프셋은 액터 루트 기준이며 머리 소켓 위치를 검증한 값이 아님 |
| 방울 표시 BP 교체 | 같은 DA → BellIndicatorWidgetClass | 비워 두면 C++ 선으로 그리는 방울·울림 아이콘. 임의의 Widget Blueprint 클래스를 지정하면 첫 성공 표시 생성 시 사용하며, 공통 색상·크기·페이드는 C++가 적용. BP에서는 내부 모양·애니메이션을 편집하고 입력/포커스 또는 자체 표시 수명을 추가하지 않음 |
| 동상 밀기 | `/Game/Systems/Interaction/Puzzles/DA_StatuePuzzleSettings` | PushSpeed=100, 가속=160, 감속=240cm/s², ContactDistance=12. 기존 bRequireInteractKey=false 보존 |
| 동상 안착 | 같은 DA 및 Stage2/SoundTest_Stage2의 S2_StatuePuzzle → Links | SeatingOverlap=0.8, 축/높이 허용=12cm. 실제 밑면 반크기=(60,60), 최종 접근축 A:Y·B:X·C:Y. ActivationTolerance=18은 구형 설정 |
| 문 하강 | 같은 DA 및 Links | GateTravel=양수280cm가 최소 **하강** 거리, GateSpeed=140, GateFloorClearance=4cm. 실제 문 높이246cm. 바닥 오프셋 A/B=0, C=20cm. 발판2cm 하강 |
| 퍼즐 연결 | S2_StatuePuzzle → Links | A→Gate02, B→Gate05, C→Gate11. 기존 복구 받침대의 Puzzle 참조는 같은 네이티브 디렉터 유지 |
| 연출 카메라 | Stage2/SoundTest_Stage2의 S2_StatuePuzzle → Reveal | PreserveGameplayFraming=true, CameraTravelTime=3초, CameraReturnTime=2.6초, MaximumLockTime=10.5초(2026-11-11). 현재 게임 카메라 각도·투영·폭/FOV와 초점 거리감을 유지하고 평행 이동한다. 막힌 경로는 다른 역동적인 각도로 바꾸지 않는다. 네이티브가 실제 직교 렌더 원점의 충돌·뷰 인계·입력 소유권을 관리 |
| 방별 연출 조립 | `/Game/Systems/Interaction/Puzzles/Presentation/BP_StatuePresentation`; 배치 S2_StatuePresentation_A/B/C | 폭 설정3곳은 `ResolvePresentationOrthoWidth`를 사용한다. PreserveGameplayFraming 켜짐 상태에서는 CameraOffset=(350,350,1200)와 RevealOrthoWidth=650의 옛 저장값은 사용하지 않는다. 보존 모드를 끈 경우에만 구형 구도 설정으로 사용 |
| 연출 카메라 블러 | 같은 BP → RevealPostProcess | 네이티브 임시 CameraActor 기본 후처리를 복사하고 MotionBlurAmount만 오버라이드0. 검정 바를 추가하기 전에 적용. 원래 게임 카메라·전역 그래픽 값은 변경하지 않음 |
| 동상 눈 | 같은 BP → EyeParameter / EyeStrengthParameter / SeatedEyeColor / SeatedEyeStrength | EyesColor / EyesStrength; 정확한 안착 후 (1,0.005,0.002), 세기5. 각 동상의 기존 값을 런타임에 저장하고 해당 방 Reset에서만 복원. 몸체·룬 파라미터 보존 |
| 검정 바·진동 | 같은 폴더 `M_StatueRevealBars`; BP → BarHeight / RumbleStrength | 상하 각각0.075, Stage2와 미러의 진동0. 네이티브 소유 카메라에만 적용; Inactive/Reset/EndPlay에서 제거 |
| 문 밑 먼지 | 같은 폴더 `M_GateFloorDust`; BP Dust00~07 컴포넌트 | 원래 문 바닥에 고정된 8개 풀링 카드. 약1.05초 수명, 최대42cm 상승·소폭 수평흔들림, 최고불투명도0.22. 무충돌·그림자 없음. 종료/중단 시 숨김, 추가 액터 생성 없음 |

C++는 탐지 우선순위, 경로·충돌, 상태 전이, 재시작과 복구를 담당한다. BP/AnimBP는 애니메이션·재질·화면 효과를 담당하며, 연결이 빠져도 게임 진행이 멈추지 않도록 C++의 제한 시간 복구를 유지한다. 오디오 에셋은 이번 작업에 추가하지 않는다.

2026-11-05 메뉴 작업에는 GitHub의 [Anthropic frontend-design 스킬](https://github.com/anthropics/skills/blob/main/skills/frontend-design/SKILL.md)을 적용했다. 프로젝트의 HSBombaram 글꼴과 CatJelly/MenuLine 에셋을 사용한다. 후속 수정에서 박스형 패널을 전체 반투명 배경·얇은 구분선·금색 호버 밑줄로 교체했다. 외부 UI 코드나 아트를 복사하지 않았다. 최신 C++ 회귀 검사는56개 통과했고, UIAuthor08 뒤 별도 UIReloadAudit03에서 두 저장 BP 컴파일·숫자 배치값·연결을 확인했다. 실제 위젯 Designer 렌더9장(1920/1280/960 폭)의 목록 스크롤과 하단 버튼 배치를 확인했다. 게임 화면의 DPI·실제 마우스/키 입력·소리 크기 검증과 구분한다.

방울 성공 표시는 BP 디스패처와 대체 키 경로 모두 실제 `EmitSound` 성공 이후에만 갱신한다. 소리 거부·입력 차단은 새 표시를 만들지 않는다. 로컬 플레이어의 고양이 루트에 붙인 화면 공간 위젯 하나를 재사용하며 마지막 최대0.25초에 사라진다. 붙잡힘·퍼즐 일시정지·액터 숨김·바구니 진입/숨기/탈출 동안 남은 표시를 취소하고, 컴포넌트 종료 시 제거한다. Tutorial의 HUD 생성 여부와 DebugGuidance 설정에는 의존하지 않는다. 새 C++ 위젯과 설정 필드는 11월 5일 메뉴 작업의 정상 네이티브 빌드에 포함되어 컴파일됐다. PIE·실제 화면/높이·BP 교체 동작은 검증하지 않았으며 플레이 검증은 사용자가 직접 진행한다.

동상 검증은 `Scripts/Prototype/verify_task4d_routes.py`(API로 미는 쪽 배치·네이티브 충돌/가속 경로 검사), `verify_task4d_recovery.py`(반복 복구·카메라 인계·막힌 문 제한 시간), `task4d_validate_visual.py`(실제 PIE 화면)로 구분한다. 기존 `Scripts/Stage2/verify_statue_routes.py`는 새 경로 검증 진입점이며 위로 올라가는 문 단정은 폐기했다. 전체 패키징/출시 검증과 실제 키보드 입력 샘플은 별도 통합 검증 항목이다.

`verify_task4d_lifecycle.py`는 하강 도중 Reset 후 완전 복귀(문 오프셋0), 실제 스테이지 재시작과 메인메뉴 이동을 검사한다. `setup_task4d_presentation.py` 재실행은 저장된 그래프·핀 값·참조를 검증하고 완성된 그래프를 다시 만들지 않는다. Task4d 소유 매니페스트와 그래프 스냅샷은 `Saved/Prototype20261104/Task4d`에 보존한다. 실행 시 에디터 단독 사용권, PIE 종료, `ue_remote.py --isolated`가 필요하다.

붙잡기 중 취소되거나 바구니가 사라지면 원래 상태를 복구한다. 원래 위치가 막혔을 때는 가까운 같은 층의 안전한 위치를 검사한다. 안전한 복귀를 입증할 수 없으면 기존 스테이지 재시작을 요청해 고양이가 충돌이 꺼진 채로 남지 않게 한다.
