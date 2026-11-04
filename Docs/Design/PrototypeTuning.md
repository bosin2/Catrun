# 프로토타입 조정 위치

2026-11-04 작업용 안내다. Task4c 애니메이션과 Task4d 동상·문 연출 값을 반영했다. C++ 기본값과 배치된 Blueprint의 덮어쓴 값은 다를 수 있으므로 최종 PIE 검증 기록을 함께 확인한다.

| 조정 대상 | 언리얼에서 열 위치 | 담당 값 / 역할 |
|---|---|---|
| 스테이지별 게임 카메라 | 프로젝트 설정 → Catrun Level Flow → Camera Profiles | Tutorial 1.0, Stage1 1.15, Stage2 1.30. 원래 직교 카메라 너비에 곱한다. 튜토리얼은 원본 유지 |
| 게임 진행 경로 | 프로젝트 설정 → Catrun Level Flow → Stages | 메인메뉴와 플레이 가능한 맵 순서. Stage3 제외 |
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
| 갑옷 경로 디버그 | 콘솔 `catrun.DebugArmorPaths 1` / `0` | 기본0. 켰을 때만 DebugDrawPath가 활성화된 갑옷의 청록색 경로·자홍색 목표를 표시한다. 기존 맵의 true 값만으로는 표시되지 않는다. 황금색 소리 파동과 원래 파란 감지 영역은 별개 |
| 방울 연출·발음 시점 | `/Game/Systems/Player/Interaction/BP_CatActions` → TryBell의 BeginBellAction 입력 | EmitDelay=0.566667초, Duration=2.8초. 클립은 BP에서 조정하고 C++가 세션별 타이머·이동 복구를 소유한다. 포획 시작 시 방울을 먼저 취소해 만료된 타이머가 잡힘 자세를 덮어쓰지 않게 한다 |
| 동상 밀기 | `/Game/Systems/Interaction/Puzzles/DA_StatuePuzzleSettings` | PushSpeed=100, 가속=160, 감속=240cm/s², ContactDistance=12. 기존 bRequireInteractKey=false 보존 |
| 동상 안착 | 같은 DA 및 Stage2/SoundTest_Stage2의 S2_StatuePuzzle → Links | SeatingOverlap=0.8, 축/높이 허용=12cm. 실제 밑면 반크기=(60,60), 최종 접근축 A:Y·B:X·C:Y. ActivationTolerance=18은 구형 설정 |
| 문 하강 | 같은 DA 및 Links | GateTravel=양수280cm가 최소 **하강** 거리, GateSpeed=140, GateFloorClearance=4cm. 실제 문 높이246cm. 바닥 오프셋 A/B=0, C=20cm. 발판2cm 하강 |
| 퍼즐 연결 | S2_StatuePuzzle → Links | A→Gate02, B→Gate05, C→Gate11. 기존 복구 받침대의 Puzzle 참조는 같은 네이티브 디렉터 유지 |
| 연출 카메라 | S2_StatuePuzzle → Reveal | 이동0.65초, 복귀0.6초, 최대잠금8초. 네이티브가 충돌·뷰·입력 소유권을 관리 |
| 방별 연출 조립 | `/Game/Systems/Interaction/Puzzles/Presentation/BP_StatuePresentation`; 배치 S2_StatuePresentation_A/B/C | CameraOffset=(350,350,1200), 원래 문 중심 기준 월드 오프셋. 안전 검사로 Y 반전 가능. RevealOrthoWidth=650; 원래 직교 너비·투영·종횡비로 시작/복귀 |
| 연출 카메라 블러 | 같은 BP → RevealPostProcess | 네이티브 임시 CameraActor 기본 후처리를 복사하고 MotionBlurAmount만 오버라이드0. 검정 바를 추가하기 전에 적용. 원래 게임 카메라·전역 그래픽 값은 변경하지 않음 |
| 동상 눈 | 같은 BP → EyeParameter / EyeStrengthParameter / SeatedEyeColor / SeatedEyeStrength | EyesColor / EyesStrength; 정확한 안착 후 (1,0.005,0.002), 세기5. 각 동상의 기존 값을 런타임에 저장하고 해당 방 Reset에서만 복원. 몸체·룬 파라미터 보존 |
| 검정 바·미세 진동 | 같은 폴더 `M_StatueRevealBars`; BP → BarHeight / RumbleStrength | 상하 각각0.075, 진동UV진폭0.0007. 네이티브 소유 카메라에만 적용; Returning에서 진동 중지, Inactive/Reset/EndPlay에서 제거 |
| 문 밑 먼지 | 같은 폴더 `M_GateFloorDust`; BP Dust00~07 컴포넌트 | 원래 문 바닥에 고정된 8개 풀링 카드. 약1.05초 수명, 최대42cm 상승·소폭 수평흔들림, 최고불투명도0.22. 무충돌·그림자 없음. 종료/중단 시 숨김, 추가 액터 생성 없음 |

C++는 탐지 우선순위, 경로·충돌, 상태 전이, 재시작과 복구를 담당한다. BP/AnimBP는 애니메이션·재질·화면 효과를 담당하며, 연결이 빠져도 게임 진행이 멈추지 않도록 C++의 제한 시간 복구를 유지한다. 오디오 에셋은 이번 작업에 추가하지 않는다.

동상 검증은 `Scripts/Prototype/verify_task4d_routes.py`(API로 미는 쪽 배치·네이티브 충돌/가속 경로 검사), `verify_task4d_recovery.py`(반복 복구·카메라 인계·막힌 문 제한 시간), `task4d_validate_visual.py`(실제 PIE 화면)로 구분한다. 기존 `Scripts/Stage2/verify_statue_routes.py`는 새 경로 검증 진입점이며 위로 올라가는 문 단정은 폐기했다. 전체 패키징/출시 검증과 실제 키보드 입력 샘플은 별도 통합 검증 항목이다.

`verify_task4d_lifecycle.py`는 하강 도중 Reset 후 완전 복귀(문 오프셋0), 실제 스테이지 재시작과 메인메뉴 이동을 검사한다. `setup_task4d_presentation.py` 재실행은 저장된 그래프·핀 값·참조를 검증하고 완성된 그래프를 다시 만들지 않는다. Task4d 소유 매니페스트와 그래프 스냅샷은 `Saved/Prototype20261104/Task4d`에 보존한다. 실행 시 에디터 단독 사용권, PIE 종료, `ue_remote.py --isolated`가 필요하다.

붙잡기 중 취소되거나 바구니가 사라지면 원래 상태를 복구한다. 원래 위치가 막혔을 때는 가까운 같은 층의 안전한 위치를 검사한다. 안전한 복귀를 입증할 수 없으면 기존 스테이지 재시작을 요청해 고양이가 충돌이 꺼진 채로 남지 않게 한다.
