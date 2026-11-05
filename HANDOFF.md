# Catrun 작업 인계

## 2026-11-05 게시 범위 — 최신 사용자 지시

사용자가 전체 메뉴→튜토리얼→Stage1→Stage2 플레이 검증 요청을 취소하고, 현재 저장 상태를 GitHub `bosin2/Catrun`의 `main`에 푸시하도록 요청했다. 따라서 이번에는 새 전체 플레이·추격 중 바구니 검증을 실행하지 않았다. 아래의 기존 국소 PIE/저장·재로드/빌드·검사 결과만 유효하며 전체 완주를 검증한 것으로 해석하지 않는다. 이전 절의 “커밋/푸시 안 함”은 각 작업 당시 기록이다. 현재 저장된 소스·에셋·설정·작업 문서를 게시 범위로 확정하고 `Saved/`, `.superpowers/`, 로컬 인증 설정은 제외한다.


## 2026-11-05 Stage2 바구니 배치 — 최신 추가 작업

사용자가 이전 도면을 기준으로 Stage2 바구니 배치를 요청했다. 원본 `C:/Users/whghk/Downloads/Stage 2 실측 도면.html`의 방4·방3 바구니와 방2 박스 은신 지점을 찾았다. 현재 축소된 방 구조에 맞춰 방4 `(1680,2300)`, 방3 `(2400,1970)`, 방2 `(2390,2820)`cm에 기존 은신 바구니를 저장했다. 방2 박스는 현재 바구니 은신 규칙에 맞췄다. 출구 월드 방향은 각각 `(0,-1)`, `(-1,-1)`, `(-1,-1)`이다. 초기 배치에서 실제 화면의 벽 가림이 발견되어 최종 위치를 안쪽으로 조정했다.

- 실제 변경 맵: `Content/Maps/Stage2.umap`, `Content/Maps/SoundTest_Stage2.umap`. 각 맵의 `Gameplay/Hiding/Stage2` 폴더에 `S2_Basket_Room4/Room3/Room2`와 각 `_Body/_Cloth`, 총9개 액터. 기존 BP/메시/천 재사용, 내부 중복 메시 숨김, 외부 참조와 충돌 연결 완료. 다른 액터의 배치·속성은 보존했다. C++/공용 BP 수정 없음.
- 배치/감사 스크립트: `Scripts/Stage2/place_hide_baskets.py`, `audit_saved_hide_baskets.py`. 최종 배치 스크립트는 기존3개 완전한 트리오를 재사용하도록 제한한다. 초기 추가가 필요한 다른 맵에 그대로 실행하지 않는다. 별도 에디터·백업·선행 증거를 요구한다.
- 최종 증거 기준: `Saved/GameplayRepair20261105/Stage2Baskets/`. Probe06 `212216-816560`, Author02 `212251-689446`, ColdAudit03 `212325-080327` 전부 양쪽 맵 성공. 맵별 진입3개·탈출15방향·통로16개·정적 경로16개 확인. 바구니 이동에 필요한 로컬 벽 거리215셀만 갱신, 최종 이동 전후 그리드 연결 동일. 초기 추가 시 기존 오래된 bake와 실제 벽 불일치는 네이티브 BuildGrid 및 실물 벽/연결 검사로 갱신했으며 상세 경위는 SDD ledger에 남겼다.
- 저장 맵을 다시 연 실제 PIE: `live-1793881510002057600.json`에서 세 바구니 ENTERING→HIDDEN→EXITING→OUTSIDE, 방4에서 자연 촛불 표식 해제, 캡슐 충돌·가시성·Walking 복원 통과. `armor-live-1793881466289909000.json`에서 새 방2 바구니를 돌아가는 실제 갑옷 경로 이동 통과. API로 검사 시작 위치를 배치한 국소 검증이며 전체 스테이지 수동 완주 증거는 아니다. 최종 방2 화면 `Live02/room200000.png`; 같은 최종 위치의 방3/4 화면 `Live01/room300000.png`, `room400000.png`에서 가시성 확인.
- 별도 Sol 소스/품질 리뷰와 Astra 통합 리뷰 완료. 전체 난이도·무방울 완주·동적 문 퍼즐을 포함한 완주는 검증 범위 밖이다. 새 라이브 에디터는 MCP로 실제 Stage2 응답을 확인했으며 PIE 종료→dirty[]→정상 QUIT_EDITOR 완료, 현재 Catrun 에디터 프로세스 없음. 로컬 저장 완료, 커밋/푸시 안 함.

배치 계획/상세 증거: `.superpowers/plans/2026-11-05-stage2-baskets.md`, `.superpowers/sdd/2026-11-05-stage2-baskets/`. 아래의 이전 게임플레이 수정 결과를 유지한다.


## 2026-11-05 재개 후 최신 상태 — 아래 중단 기록보다 우선

사용자가 재개했고 적절한 Computer Use도 허용했다. 이후 사용자 정정에 따라 **튜토리얼 키 안내/키 변경 연동 확장은 취소**했다. 이번에 추가했던 두 BP 변경은 다른 변경이 없음을 해시로 확인한 뒤 직전 원본으로 복구했다. `TutorialHintRevert01/report.json`과 `cold-compile.json`에서 원본 바이트·두 BP 컴파일 성공을 확인했다. 원래 처음 시작 안내·애니메이션·종료·인트로·계단 흐름을 유지한다. `finish_tutorial_hints.py`는 실행 즉시 중단하는 폐기된 스크립트이므로 다시 적용하지 않는다.

- **공통 바닥 판정/바구니**: 캡슐 지지면 공통 판정과 모든 경사·높이·충돌 검사를 유지한다. 실제 진입 높이차로 고양이 캡슐까지 기울던 문제를 수평 yaw 회전으로 수정했다. 원래 선택 유지와 정확한 복원은 보존했다. 별도 배치 수정으로 Stage1/미러 첫 바구니 정면(-1,+1,0)을 저장해 AS 방향을 허용했다. 적용184641-014884, 별도 재로드184731-761839에서 실제 캡슐 지지/이동/도착 공간을 확인했다. 특정 바닥 예외는 없다.
- **포털 실제 통합 완료**: `/Game/Cinematics/Stage1/Portal/`의5개 에셋과 Stage1/미러 맵을 저장했다. 시퀀스·BP가 카메라/고양이 동작/암전/저장 후 이동을 소유하고 C++은 충돌·자원·저장 서비스를 제공한다. 별도 재로드 `PortalTransition/20261105-183758-018907/report.json` 성공. 실제 복도에 배치한 고양이를 정상 CharacterMovement로 안쪽까지 이동시킨 검사에서 front→face→rear, 프레임0..243, 약9.109초 후 Stage2와 입력 복귀를 기록했다. `LiveFinal01/portal-1793872876023105300.json`. 처음부터 스테이지를 완주한 증거는 아니다.
- **월드 수정 실제 저장 완료**: Tutorial/미러 계단 소리 그리드, Stage2/미러 촛불3개 위치 순찰, 갑옷 회전율 맵 override 반영. `WorldTuning/20261105-183854-010694` 작성 및 `20261105-184022-524153` 별도 재로드 성공. BP_LivingArmor 기본값은 이미 목표와 일치했다. 실제 Stage2 촛불3개 각각7초 동안 XY 위치 범위262.04cm 기록(`LiveFinal01/patrol.json`).
- **Stage2 문 카메라 실제 동작 확인**: 79.958% 근처 배치에서 정상 이동/퍼즐 Tick으로 완료한 검사에서 ToGate1.98초/Opening2초/Returning1.58초, 각도(-55,-135,0)와 OrthoWidth1170 유지, 철창-280cm, 원래 카메라·이동 입력 복귀(`LiveFinal01/calm-gate.json`). 강제 해결/수동 카메라 Tick을 사용하지 않았다.
- **설정 실제 조작 확인**: 마우스로 메뉴/카테고리/키 선택, 밑줄, Esc 키 선택 취소→닫기, 실제 이어하기→Stage2, 인게임 Esc 설정 열기/일시정지/닫기/복귀를 확인했다. 이후 발견한 “설정 닫은 뒤 첫 메뉴 클릭 소실”은 SButton 클릭 콜백의 일시적 캡처를 저장·복구하던 원인으로 수정했다. 일반 해제된 SButton만 제외하고 포커스/눌린 버튼/raw/custom 캡처는 보존한다. 새 실행 `LiveFinal02/mouse-retest.json`에서 실제 마우스로 설정 열기→Esc 닫기→이어하기 **한 번 클릭**→Stage2 진입을 확인했다. 검사 중 키/설정 적용·저장은 하지 않았다.
- **검사**: 게임플레이 통합 DLL `NativeRegressionBuild04` 성공, 실제 `IntegratedFinalTests01/AutomationReport/index.json` 71개 통과(69성공+경고 포함 성공2, 실패0). 그 뒤 설정 마우스 캡처 수정 DLL `SettingsMouseBuild01` 37.32초 성공, `SettingsMouseTests01/AutomationReport/index.json` 관련 검사 5개 통과(실패·경고0). 이전71개를 후속 수정까지 포함한 새 실행으로 표현하지 않는다. 독립 범위별/통합 리뷰와 마지막 설정 수정 리뷰 완료; 차단 지적 없음(`settings-capture-review.md`).
- `LiveFinal01`과 `LiveFinal02`는 root 소유 에디터만 사용했다. 각각 PIE 종료 후 dirty[] 확인, 정상 QUIT_EDITOR로 닫았다. 최종 프로세스 조회에서도 UnrealEditor 실행 없음. 로컬 변경 보존, **커밋/푸시 안 함**. 남은 검증은 실제 전체 메뉴→튜토리얼→Stage1→Stage2 수동 완주 및 애니메이션/연출의 주관적 조정이다. 에디터 그래픽 메모리/생성된 주석 GUID 경고는 관찰 기록이며 이번 플레이 수정과 무관한 광범위 설정 변경으로 확대하지 않았다.

위 모든 Saved 상대 경로의 기준은 `Saved/GameplayRepair20261105/`이다. 세부 진행은 `.superpowers/sdd/2026-11-05-gameplay-settings-repair/progress.md`. 사용자 지시대로 플레이 진행·조작감·충돌·AI에 집중하고, 취소된 키 안내/안내 상태 관리 작업을 다시 만들지 않는다.

## 2026-11-05 17:36 KST 이전 중단 기록 — 이후 재개로 해제됨

당시 사용자가 “여기까지, 나중에 다시 켤 테니 마무리”를 요청해 추가 구현·에디터 실행·검사를 멈췄다. 아래는 당시 기록이며, 현재 상태와 작업 범위는 문서 맨 위 재개 후 최신 상태를 따른다.

### 저장 및 실행 상태

- 현재 `main`, HEAD `b1779a466ec5d11aa1e0beaeb04e3ff15601dbec`. 이번 후속 수정은 로컬 파일에 저장되어 있으며 **커밋/푸시하지 않았다.** 기존 사용자 변경·백업을 보존했다. 문서 마감 전 `git status --porcelain=v1`은63개 항목이었다(파일 수와 동일하지 않음).
- 17:36 프로세스 확인 시 실행 중인 UnrealEditor/UnrealEditor-Cmd/UnrealBuildTool 및 작업용 빌드·저장 프로세스 없음. 서브에이전트 모두 완료 상태. 마지막 PortalAuthor12는 정상 종료했으며 실패한 미저장 Stage1 변경은 저장하지 않았다.
- 사용자는 실제 화면/플레이를 직접 검증한다. **Computer Use, OS 입력/포커스 변경, 자동 플레이/캡처, 사용자 에디터 중단 금지.** 재개 후 필요한 빌드·BP 컴파일·저장·별도 재로드·관련 native 검사는 가능하지만 통과한 변경 없는 검사를 반복하지 않는다.

### 실제 반영된 것과 검증 범위

1. **공통 바닥 판정**: 특정 바구니·맵 예외 없이 `Source/Catrun/Perception/CatrunGroundSupport.{h,cpp}`에 실제 고양이 캡슐 크기와 충돌 응답을 쓰는 지지면 sweep을 구현했다. 바구니 진입/후보/복원, SafeRestore의 지면 탐색 fallback, 포털 경로 계산에 연결했다. 경사·바닥 없음·관통·장애물·기존 높이 범위 검사를 유지했다. 잘못된 입력에서 기존 선택/표시를 유지하던 원래 의도도 복원했다. 바구니의 배치 방향은 아직 수정하지 않았다.
2. **최신 C++ 전체 링크 성공**: `Saved/GameplayRepair20261105/SharedGroundRangeInputBuild02/result.json`은 `exit_code=0, linked=true`, build.log은24.68초 Succeeded. 공통 바닥 판정 최종 높이 범위 수정, BP 소유 포털 어댑터, 소유 pawn/controller 소멸 처리, 입력 바인딩 Tick 최적화를 포함한다. **이 버전에 추가된 회귀 검사는 아직 실행하지 않았다.** 예전 CurrentRepairTests02의56개 통과를 현재 버전 통과로 인용하지 않는다.
3. **Stage2 차분한 문 카메라와 설정 UI**는 앞 절차에서 실제 BP/맵에 저장하고 별도 재로드를 통과했다. 카메라 이동2초/복귀1.6초/흔들림0 및 기존 시점 보존. UI는 전체 반투명 배경·얇은 선·8개 키 설정·호버/포커스 밑줄·Esc·마우스 클릭/휠 중심. 실제 입력 및 시각적 만족도는 사용자 확인 항목이다. 변경 없이 재작업하지 않는다.
4. **포털 연출 에셋5개 실제 저장**: `/Game/Cinematics/Stage1/Portal/` 아래 `LS_Stage1_PortalExit`, `BP_Stage1PortalPresentation`, `BP_Stage1PortalExit`, `WBP_ExitTransition`, `M_Stage1PortalBlue`. PortalAuthor11 저장 증거는 `Saved/GameplayRepair20261105/PortalTransition/20261105-172648-542990/report.json`. **Stage1/SoundTest_Stage1 맵에는 아직 연결하여 저장하지 못했다.** 따라서 게임에서 연결 완료/시네마틱 재생 성공으로 보고하면 안 된다.
5. 연출 소유권은 사용자 지시대로 **실제 BP/Level Sequence**다. 카메라·고양이 이동/점프/포즈·포털·타이밍·암전·완료/저장/이동 순서는 BP/Sequence에서 편집한다. C++은 충돌/경로 계산·입력과 이동 자원 임대·저장 서비스에 한정한다. 이전 native director 설계는 폐기됐다.

### 다음 재개 첫 지점과 남은 작업

1. **공통 바닥 판정의 최신 회귀 검사를 실행**하고 결과 index.json까지 확인한다. 기존 `Saved/GameplayRepair20261105/run_automation.ps1 -Run <새 고유 이름> -Filter Catrun` 사용. 최신 DLL은 이미 링크됐으므로 소스 변경 없이 다시 빌드할 필요는 없다. 독립 소스 리뷰 `task-basket-support-implementation-review.md`에는 현재 차단 지적이 없다.
2. **포털 맵 저장의 구체적 차단부터 해결**한다. `Scripts/GameplayRepair/author_portal_transition.py:770`의 `geometry()/supported()`가 이전 ray 기반 지면 높이를 고정 INSPECT 높이와 비교하면서 실패했다. 최신 C++의 공통 캡슐 지지면 방식과 작성 스크립트가 맞지 않는 상태다. 실제 hit/지원 높이를 기록해 공통 방식에 맞추고, 허용 경사/충돌을 완화하거나 해당 바닥만 예외 처리하지 않는다. 최종 실패 증거: `Saved/GameplayRepair20261105/PortalTransition/20261105-172859-689318/report.json` (`completed=false`, `saved=[]`).
3. 포털 작성 스크립트에는 **기존5개 에셋을 재사용하는 resume 모드**가 있다. root만 `run_editor_script.ps1 -Run PortalAuthor13 -Script Scripts/GameplayRepair/author_portal_transition.py -Geometry -ExtraArgs '-catrunGeometryIsolated','-catrunPortalAuthor','-catrunPortalResumeMaps'`로 재개한다. 새 에셋을 삭제/재생성하지 않는다. 현재 Stage1과 미러 모두 아직 기존 출구다. 한 맵만 저장된 뒤 실패하면 다음 재시도는 이미 저장된 전용 출구 재사용을 확인해야 한다. 양쪽 맵 저장 후 audit-only와 해당 report baseline으로 별도 프로세스 재로드를 끝낸 뒤 다른 맵 수정을 한다.
4. `Scripts/GameplayRepair/finish_world_tuning.py`는 검토됐으나 **실제7개 패키지 변경은 아직 저장하지 않았다**: Tutorial/미러 계단 SoundFloor와 sound grid, Stage2/미러 촛불3개 위치 순찰·캡슐 높이, BP_LivingArmor와 기존값5인 맵 override 회전율3.333333. 최신 DLL의 `ExportBakedGridSnapshot`을 사용한다. `-catrunGeometryIsolated -catrunWorldAuthor`, 이후 `-catrunWorldAuditOnly -catrunWorldBaseline=<완료 report>`를 사용하는 기존 harness로 진행한다. 바구니 방향은 이 스크립트에서 보존한다.
5. **Stage1 첫 바구니 A+S 문제**: 새 저장맵 진단 `Saved/GameplayRepair20261105/BasketDirection/165136-546791/report.json`은 AS→world+Y, 현재 front-Y의 sector 제외, 역사적 A-front(-1,+1,0)의 sector 허용을 확인했다. 같은 목적지에서 ray는 바닥 장식 삼각형 normalZ .279에 걸리지만 실제 캡슐 sweep은 normalZ1의 지지면과 이동/도착 공간을 확인했다. 이는 저장맵 질의이며 실제 플레이 증거는 아니다. **공통 로직 수정과 바구니 명시적 방향 복원은 별개**다. 최신 `basket_direction_repair.py` probe→보고서 확인→guarded apply→fresh audit를 다른 맵 변경 뒤에 실행한다. 아직 방향 에셋 수정 없음.
6. `Scripts/GameplayRepair/finish_tutorial_hints.py`는 소스·독립 리뷰 완료, **WBP_Tutorial_KeyHint/BP_TutorialIntro 실제 수정은 아직**. 기존 인트로/위젯/애니메이션 보존, 유효 키 라벨과 최초 Continue 안내 상태만 연결한다. `-catrunHintAuthor`, 별도 `-catrunHintAudit`로 반영/확인한다. 일반 재시작에서 인트로·안내 반복을 만들지 않는다.
7. 입력 바인딩의 매 프레임 재조회는 변경 후 빌드/리뷰까지 완료했다. UMG17개 affordance의 Tick polling 개선은 **미수정 후보**다. 측정 없는 FPS 개선 주장을 하지 않는다. 이것 때문에 실제 맵/BP 통합을 미루거나 새 프레임워크를 만들지 않는다.

상세 리뷰·이전 계획: `.superpowers/sdd/2026-11-05-gameplay-settings-repair/` 및 `progress.md`. 다음에는 이 절부터 읽고 이어간다. 저장된 UI/카메라를 다시 처음부터 구현하거나 캡처 도구 작업을 재개하지 않는다.

## 2026-11-05 후속 수정 진행 상태 — 아래 이전 기록보다 우선

- Stage2와 SoundTest_Stage2의 문 카메라를 실제 저장했다. 플레이 중 각도·투영·폭/FOV·거리감을 유지하며 이동2초/복귀1.6초, 흔들림0, 최대잠금8초. BP의 세 폭 설정 경로도 native 보존 함수로 연결했다. 별도 프로세스의 저장값 재검사와 전용 회귀 검사2개, 독립 리뷰를 통과했다. 연속 프레임 검사는 최신 사용자 지시로 중단했으며 최종 화면/플레이 확인은 사용자 항목이다.
- 설정 UI는 실제 WBP_Setting/WBP_MainMenu에 저장했다. 전체 반투명 배경·얇은 선·키 설정8개·호버/포커스 밑줄·메뉴/인게임 공용 설정창·Esc 열기/닫기 코드가 반영됐다. 마우스 클릭/휠이 기본이며 Tab은 선택적인 보조 기능이다. 키 선택 중 Esc는 해당 선택을 취소한다. 전체 초안 검증을 통과한 적용만 저장하며 개발용 잡힘 방지도 적용 전까지 초안이다.
- UI 최신 저장 UIAuthor08, 별도 UIReloadAudit03 및 task-6-rereview2 통과. 실제 저장 위젯을 1920x1080/1280x720/960x540에서 렌더링한 PNG9개를 확인했다. 작은 화면의 키 목록은 스크롤되며 하단 버튼은 화면에 남는다. 이는 Designer 배치 증거이며 실제 클릭/휠 입력 검증과 다르다. 증거: Saved/GameplayRepair20261105/UI/actual-designer-20261105T065633809112Z. Designer CachedGeometry는0이므로 클릭 영역 수치 증거로 사용하지 않는다.
- 갑옷 회전 곡선 인계·문 후 순찰 재계획/잔여 재시도·중단된 소리 큐·촛불 위치 순찰의 native 로직, 바구니 후보/실제 탈출 경로 및 정확한 복원은 구현·독립 리뷰 완료. 최신 링크 빌드는 BasketFix1Build01, 실제 native 검사 CurrentRepairTests02는56개 통과(54성공+2경고 포함 성공), 실패0. 맵의 촛불 경로 활성화·갑옷 회전율 조정·바구니 방향 복원은 아직 별도 에셋 작업이다.
- 남은 작업: 튜토리얼 계단 SoundFloor/그리드, Stage2 촛불 경로와 미러, 갑옷 BP 회전율, 첫 바구니 명시 방향, 튜토리얼 현재 키 안내, 최초 Continue 안내 완료 상태, Stage1 복도→역사적 포털 연출→암전/실제 저장→Stage2. Task4 native 구현을 시작했으며 아직 빌드/완료로 취급하지 않는다. 원본 스토리보드는 .superpowers/sdd/2026-11-05-gameplay-settings-repair/historical-stage1-cinematic.md.
- 최신 지시: 연속 캡처·추가 UI/카메라 화면 검증·캡처 도구 보완을 중단하고 남은 구현/맵·BP 반영을 우선한다. 최종 시각/플레이 검증은 사용자가 나중에 직접 한다. 빌드·BP 컴파일·저장/재로드·관련 자동 검사는 허용되지만 이유 없는 반복/검증 확대는 하지 않는다. OS 입력·전면 활성화·사용자 에디터/플레이 중단 금지. Root만 에디터·빌드·에셋 저장을 실행한다.
- 상세 계획/작업 임대/증거는 .superpowers/plans/2026-11-05-gameplay-settings-repair.md와 해당 SDD progress.md를 따른다. 현재 main 로컬 변경이며 이번 후속 수정은 커밋/푸시하지 않았다.

## 2026-11-05 메뉴 1차 작업 기록 — 이전 상태

방울 발신 성공 표시를 추가했다. `UCatrunBellComponent::EmitBellSound`에서 실제 소리 발생이 성공한 뒤 고양이 위에 금색 방울·울림선 위젯을 1.2초 표시하고 마지막 0.25초 동안 사라지도록 구현했다. 튜토리얼 HUD에 의존하지 않으며 실패한 방울은 표시를 새로 만들거나 갱신하지 않는다. 잡힘·은신·퍼즐 정지 중에는 잔여 표시를 숨긴다. `DA_SoundSettings`의 `Bell|Feedback`에서 시간·루트 기준 높이·크기·색과 대체 Widget Blueprint를 조정한다. 기본 높이 65cm는 실제 머리 소켓에 연결한 값이 아니다. 이후 메뉴 작업의 정상 C++ 빌드에 방울 표시와 잡힘 방지 명령까지 반영했다. 실제 플레이는 사용자 확인 항목이다.

메인메뉴 이어하기와 설정을 구현했다. `CatrunProgress` 슬롯으로 마지막 도착 구간의 시작점을 저장하고 이어하기는 기존 인트로 건너뛰기 경로를 사용한다. 메뉴에서 새 게임/이어하기로 시작한 진행만 저장하므로 개발용 직접 맵 실행은 기록을 덮어쓰지 않는다. 설정에는 전체 음량·화면 모드·화질·프레임·VSync와 개발용 잡힘 방지 체크박스가 있다. UI는 실제 `WBP_MainMenu`/`WBP_Setting` Designer와 BP 그래프로 저장했으며, 진행 규칙과 설정 보관은 C++다. 원래 메인메뉴의 위젯 23개와 EventGraph 노드 61개는 보존했다. 옵션 닫기는 버튼으로 처리하며 Esc 닫기는 미구현이다. 세부 사용법은 `Docs/Design/PrototypeTuning.md`를 참조한다.

사용자가 에디터만 켜 둔 상태라고 확인한 뒤, 남아 있던 Stage2 PIE를 API로 종료했다. 미저장 패키지가 없음을 확인하고 원래 에디터를 정상 종료했다. 새 네이티브 빌드는 `Saved/Menu20261105/build-01.log`에서 43.71초 성공했다. Blueprint 작성/저장/재로드 컴파일은 숨겨진 commandlet으로 진행했으며 Computer Use·키보드 자동 조작·실제 플레이 검증은 하지 않았다. 에셋 원본 백업과 저장 그래프 감사 기록은 `Saved/Menu20261105`에 있다. 메뉴 작업 스킬/상태는 `.superpowers/sdd/2026-11-05-menu-settings/progress.md`에 기록했다.

튜토리얼 방울과 갑옷 문 통과 수정은 `Tutorial`과 `SoundTest_Tutorial`에 저장했다. 이전 유인 지점에서 갑옷까지 열린 경로의 전파 비용은 약 569였다. 두 맵의 플레이어 방울 예산을 650으로 설정했다. 닫힌 문은 기존 규칙대로 소리를 차단한다.

두 문의 `ArmorPassageHalfWidth`는 22cm다. 길찾기가 갑옷을 문 중앙으로 안내한다. 튜토리얼 갑옷은 원래 XY `(-80,900)`에 배치했고 크기는 0.85, 바닥 기준 캡슐 중심 Z는 87.25다. 두 맵을 저장하고 다시 열어 값을 확인했다. 방울·문 수정 시점의 네이티브 검사는 41개 통과했다.

사용자가 문을 지나간다고 알려왔으며, 이후 실제 플레이 검증은 사용자가 담당한다. 자동 플레이와 Computer Use는 중단했다. 메뉴→Stage1 연속 완주는 사용자 검증 항목이다. 갑옷 포획을 끄는 `catrun.NoArmorCapture 1` 명령을 추가했다. `0`은 일반 플레이로 복구하며 다음 새 포획부터 적용된다. 디버그 명령은 앞선 41개 검사 이후에 추가되었고, 이번 메뉴 작업 빌드에 반영했다. 이번 변경은 `main`의 `b1779a4` 이후 로컬 작업이며 커밋·푸시하지 않았다.

## 2026-11-04 중단 당시 기록

아래 내용은 수정 전 실패 증거와 남은 독립 작업의 기록이다. 튜토리얼 방울·문 상태와 자동 검증에 관한 지침은 위의 11월 5일 기록을 따른다.

## 1. 다음 첫 작업: 튜토리얼에서 방울이 갑옷에게 전달되지 않음

**목표:** 원래 시작 위치에서 방울로 갑옷을 유인하고 캣홀로 우회하여, 원래 계단 트리거를 통해 Stage1까지 실제로 탈출할 수 있게 한다. 소리 전파 연결을 먼저 진단하고, 원인이 확인된 코드 또는 튜토리얼 배치를 수정한다. 전역 감지 범위 축소·AI 비활성화·충돌 무시·플레이어 순간이동으로 완주를 주장하지 않는다.

### 마지막 실패의 확정 사실

근거: `Saved/Prototype20261104/Task5/TutorialCompleteRoute05/observations.json` 및 같은 폴더 `progress.json`.

| 항목 | 마지막 실행 결과 |
| --- | --- |
| 실행 경로 | 실제 OS 메뉴 Start → 기존 인트로 → 원래 시작점 → 이동·방울 → 캣홀 |
| 입력 구분 | 달리기는 원래 Enhanced Input `IA_Run` 주입, 방울은 기존 BP 동작 API 호출. 전 구간 수동 키보드 플레이로 표현하지 않는다. |
| 최초 플레이 위치 | `(170,-95,26.25)` |
| 실제 튜토리얼 카메라 | pitch `-55`, yaw `+45` |
| 방울 호출 | 게임 시간 `42.756749초`, 고양이 `(-209.998981,403.980912,26.25)` |
| 방울 종료 | `45.559204초` |
| 소리 발생 | `EditorAssets9.log:5950`, `size=2 budget=500 reached 806 cells` |
| 캣홀 통과 후 대기 위치 | `(-274.791879,537.800635,26.25)` |
| 갑옷 | `(-80,900,100)`에서 계속 `IDLE` |
| 소리 도달 값 | 갑옷 위치의 `GetRemainingBudgetAt`은 모든 표본에서 `-1` |
| 위험/문 상태 | 904개 표본 모두 표식 없음, capture `INACTIVE`, 두 문 닫힘 |
| 종료 | `62.291871초`, `wait_looking` 15초 제한 초과. `final=true`, **`success=false`** |

발각 없이 방울→캣홀 구간을 통과한 것은 확인했지만, 갑옷 유인과 전체 탈출은 실패했다. 방울 애니메이션만 재생된 무발음 문제가 아니라 실제 소리 이벤트가 발생했음도 확인했다. 다만 `GetRemainingBudgetAt`은 **최근 소리**의 거리장 조회이므로 다음 진단은 방울 이벤트 직후의 스냅샷과 listener 전달 기록을 묶어야 한다.

### 원인 가설과 반드시 지킬 기획

- `Docs/Design/GameDesign_Source.md:89-93`, `Docs/Design/GameDesign.md:49`는 **닫힌 문이 소리를 막는다**고 명시한다. `SoundPropagation.cpp`의 닫힌 문 차단 자체를 버그로 단정하거나, 갑옷을 유인하려고 전역 벽/문 차단을 없애지 않는다.
- 현재 코드는 닫힌 `GateBox`에 속한 그리드 칸을 차단하며, 도달하지 못한 listener에는 청각 이벤트를 예약하지 않는다. 하지만 이번 실패가 정확히 어느 문/그리드 경계/우회 경로/예산에서 발생했는지는 아직 셀 단위로 입증하지 않았다.
- 먼저 캣홀 또는 열린 통로를 통한 소리 연결, 문의 GateBox가 통로까지 덮는지, 베이크된 walkable/edge, 실제 음원·갑옷의 매핑 셀을 확인한다. 기획상 허용되는 유인 위치와 갑옷 배치도 함께 검토한다. 단순 예산 증가를 먼저 적용하지 않는다.
- 가까운 갑옷 감지의 실제 설정은 `150 + 고양이 시야 반경15 = 165cm`다. 옛 C++ 기본값60으로 탈출 경로를 계산하지 않는다. 튜토리얼 촛불 표식 페널티는 활성 상태로 유지한다.

### 재개 직후 실행 순서

1. 아래 Git 상태와 사용자 변경을 확인한다. 기존 stash를 다시 적용하지 않는다. 현재 에디터/PIE/저장되지 않은 패키지 상태를 읽고, 사용자 작업을 보존한다.
2. UE5.8 프로젝트를 확인하고 실제 MCP 현재 맵 조회로 연결을 증명한다. 포트·프로세스·툴 목록만으로 연결 성공을 주장하지 않는다.
3. Route05를 기준으로 방울 이벤트의 음원 셀, 갑옷 셀, `Walkable`, 양방향 `EdgeMask`, `ClosedGateCells`, 문별 GateBox/셀, 실제 거리장과 pending listener를 기록한다. 가능하면 읽기 전용 그리드 비교로 차단 지점을 찾는다.
4. 닫힌 문 정책을 유지하면서, 캣홀/열린 경로의 잘못된 차단 또는 실제 유인 가능한 배치를 바로잡는다. 수정 전에 필요한 범위와 계획을 짧게 보여주고, Tutorial과 SoundTest_Tutorial의 대응 변경을 함께 보존한다.
5. 방울로 인한 `OnSoundHeard` → 조사 이동 → 문 상호작용 → 고양이 우회가 발생하는지 검증한다. 촛불 표식으로 움직인 갑옷을 방울 유인 성공으로 기록하지 않는다.
6. 원래 메뉴/인트로/시작점에서 실제 이동·충돌·AI를 유지해 캣홀→복도→계단 겹침→자동 Stage1 전환까지 연속 완주한다. 실패 시 최초 차단·감지 원인을 기록하고 제한 시간 내 종료한다.
7. 별도 리뷰 에이전트로 변경과 증거를 검증한 뒤 다음 단위로 넘어간다.

관련 코드: `Source/Catrun/Sound/SoundPropagation.cpp::Run`, `SoundGridManager.cpp::RefreshDoorGates`, `NotifyDoorStateChanged`, `EmitSound`, `DeliverPendingSounds`, `GetRemainingBudgetAt`, `CatrunDoor.cpp`, `Source/Catrun/Monster/CatrunArmor.cpp::OnSoundHeard_Implementation`.

## 2. Git 및 중단 상태

- 프로젝트: `C:\Users\whghk\Catrun`, UE5.8.2.
- 현재 브랜치: **`main`**. 게시 커밋: **`b1779a466ec5d11aa1e0beaeb04e3ff15601dbec`**, 제목 **`리펙토링`**.
- `origin`: `https://github.com/bosin2/Catrun.git`. 직전 푸시 후 원격 main과 로컬 HEAD 일치, 작업 트리 clean을 실제 확인했다. 이 인계 문서와 이번 기록 보완은 그 이후 작성된 로컬 문서 변경이다.
- GitHub Desktop이 브랜치를 main으로 바꾸며 작업을 stash에 보관했었다. `23564029576a902c0c7180da2850f9f3f44dbe79`를 **apply만** 하여 복원·커밋·푸시했으며 stash는 보존했다. 현재 main에 이미 반영되어 있으므로 **다시 apply/pop하지 않는다**. 예전 `codex/playable-prototype-20261104` 브랜치는 아직 `0f1800a`이므로 무심코 전환해 최신 작업을 잃은 것으로 오인하지 않는다.
- 게시 파일374개. 자동 생성 Python 캐시43개는 로컬에 보존하고 제외했으며 `.gitignore`에 캐시 규칙을 추가했다. `Saved`, 빌드 산출물, 로컬 자격 증명은 게시하지 않았다.
- 구현 에이전트/자동 이동 콜백은 중단했고, 담당자가 시작한 PIE도 종료했다. 중단 뒤 새 게임 테스트·빌드·게임 수정은 하지 않았다. **현재 에디터 프로세스가 열려 있는지는 재개할 때 다시 확인**한다.
- 모든 구현 임대/에디터 조작 권한은 종료된 것으로 취급하고 재개 시 재배정한다. 동시에 두 에이전트가 UI/MCP 또는 같은 에셋을 수정하지 않는다.

## 3. 저장된 구현과 검증 범위

- 메인메뉴 인트로의 원래 8개 컷/고양이 바인딩 복구와 메뉴 커서 연결을 검증했다. 사용자가 인트로는 정상이라고 확인했다. 이 문제를 새 증거 없이 다시 열지 않는다.
- 정식 흐름은 MainMenu → Tutorial → Stage1 → Stage2. SoundTest 맵의 시스템을 정식 맵에 통합했다. Stage3는 이번 프로토타입 범위 밖이다.
- 포획 세션·입력/카메라 복원, 재시작 시 인트로/문구 생략, 바구니 상태·안전 복구, 상호 Pawn 충돌, 캣홀 방울 금지와 정확한 안내 `방울을 울릴수없습니다`, 동상 안착/문 하강/눈·먼지·검은 띠의 기본 연결 작업은 저장되어 있다. 개별 테스트 통과가 모든 동선의 플레이 완료를 뜻하지 않는다.
- 원래 최종 리뷰의 3건은 수정·독립 재리뷰를 통과했다: 방울 직후 포획의 늦은 복원 콜백, Busy 중 동상 안착 시 연출 대기, AI 경로 디버그 표시 기본 비활성화. `.superpowers/sdd/2026-11-04-playable-prototype/final-fix-rereview.md` 참조.
- 마지막 전체 네이티브 검사: `Saved/Prototype20261104/Task5/FinalFix02/AutomationReport/index.json`, **39개 성공**. 같은 폴더 Build/Automation result는 exit0. 이는 당시 실행 결과이며, 다음 변경 뒤의 새 빌드/검사를 대신하지 않는다.
- 실제 출구 겹침과 단계 전환의 개별 검사, 바구니 실제 F 입력, 동상 일부 실제 밀기 입력 증거는 있다. **메뉴부터 Stage2까지 전 구간을 연속 수동 완주했다는 증거는 아직 없다.**
- 최종 4개 맵 cook 및 완성본 통합 검증은 미실행이다. 기존 `-game` 실행은 에디터 실행 파일 기반의 독립 실행이며 패키징된 게임이 아니다.

### 최신 튜토리얼 저장 변경

두 맵 `Content/Maps/Tutorial.umap`, `Content/Maps/SoundTest_Tutorial.umap` 모두:

- native 침실문과 같은 위치에서 통로를 막던 정적 중복 문짝 `StaticMeshActor_8 / SM_Tutorial_BedroomDoor_Open` 제거. native 문/프레임은 유지. 원래 실제 캡슐 hit Y434.7과 이전 경로의 정체 지점이 일치했다.
- 갑옷 `(-80,900,100)`.
- 촛불은 원래 위치 `(-20,390,10)` 유지, yaw `-100`, 표식 페널티 활성.
- 위 배치는 저장됐지만 **현재 유인 실패가 있어 최종 플레이 가능 배치로 승인된 상태는 아니다**.
- 이전 복제본은 `.superpowers/sdd/2026-11-04-playable-prototype/tutorial-playable-before/`에 보존. 불필요한 원본 롤백/재복제는 하지 않는다.

## 4. 남은 독립 작업 단위

튜토리얼 소리 연결과 완주 검증이 최우선이다. 이후 구현 담당과 별도 리뷰 담당을 나누고 메인이 통합한다.

| 순서 | 작업 | 현재 상태와 다음 행동 |
| --- | --- | --- |
| 1 | 튜토리얼 실제 클리어 | 위 1절부터. closed-door 규칙과 소리/이동 그리드를 대조하여 원인 입증 후 최소 수정. |
| 2 | Stage2 촛불 **위치 순찰** | 사용자가 명시한 요구. 기존 40도 몸체/시야 왕복 회전은 실제로 작동하지만 위치 이동은 없다. 새 patrol 컴포넌트·테스트는 **아직 작성되지 않았다**. 계획과 before 백업만 존재. |
| 3 | 갑옷 애니메이션·포획 방향 전환 | 원본 전체 클립 손상은 입증되지 않았다. 선형 중단 yaw와 실제 root 곡선 불일치, 5배속 turn, 0초 body blend, 포획 시작 yaw snap을 우선 수정. native root와 BP 포즈의 이중 회전을 피한다. 구현은 아직 시작하지 않았다. |
| 4 | 공통 게임플레이 리팩토링 | 방울의 BP 5초 판정/사용시각과 C++ 쿨다운 단일화, native 타입 기반 상태 조회, 카메라 A→B→A 기준값 재확대 방지, 바구니 복원 이중 탐색 제거. 계획만 완료. BP 패치 스크립트도 아직 작성되지 않았다. |
| 5 | Stage2 문 포커스 완화 | 이동2.0초/복귀1.6초/폭1050/진동0.00015를 첫 비교 후보로 계획. 현재0.65/0.6/650/0.0007. `Scripts/Prototype/tune_stage2_reveal_camera.py`는 작성·문법 확인만 했으며 **실행하지 않았다**. A/B/C 및 두 Stage2 맵에 적용 후 화면 검증 필요. |
| 6 | 통합 검증·저장·종료 | 개별 리뷰→새 네이티브 빌드/전체 자동검사→실제 메뉴/재시작/단계 흐름→4맵 cook→미확인 사항 정리. 모든 작업 완료 시 저장 확인 후 언리얼 정상 종료. |

촛불 순찰은 기본 비활성/튜토리얼 고정, Stage2 3개와 대응 SoundTest 3개에 경로를 배치한다. 감지 중 이동 정지·시야 상실 후 기존 경로 재개, 퍼즐 연출 중 정지/종료 후 재개, 재시작 초기화, Pawn/벽/바닥 안전이 필요하다. SceneComponent root의 `SetActorLocation(...sweep=true)`만으로 offset 캡슐이 스윕된다고 가정하지 않는다. 실제 capsule 형상·스케일·오프셋으로 검사하며 테스트는 직접 Tick 호출만이 아닌 UWorld scheduler와 실제 배치 BP를 포함한다.

갑옷 계획은 실제 root 곡선으로 중단 회전 인계, Framing 동안 최단 yaw 보간, root를 제외한 Inertialization 단일 노드 연결이다. 연결된 AnimBP 전체 재작성은 피한다. 원본1배속/현재5배속과 최종 포즈를 캐릭터가 보이는 카메라로 비교하며, root 수치만으로 자연스러워졌다고 주장하지 않는다. 문 애니메이션의 음수 X 미러와 손/위치 인계도 별도 검증한다.

방울 리팩토링은 기존 클래스/입력/클립/관찰 디스패처를 보존하며 C++가 admission·쿨다운·실제 소리 발생을 소유하도록 한다. Entering/Hidden/Exiting 바구니 단계는 모두 안전 상태로 유지하되 방울 Busy를 포획 면역으로 바꾸지 않는다.

## 5. 재사용할 문서·증거와 실패 방지

주요 로컬 작업 폴더: `.superpowers/sdd/2026-11-04-playable-prototype/` (Git에서 제외된 로컬 기록).

- `tutorial-playable-implementation.md`: 최신 튜토리얼 변경과 Route01–05 경과.
- `stage2-candle-patrol-plan.md`, `stage2-candle-diagnosis.md`: 촛불 위치 이동의 정확한 구현·충돌·검증 계약.
- `armor-motion-implementation-plan.md`, `armor-motion-user-analysis.md`: root/포즈/포획 분리 및 실제 엔진 API 확인.
- `gameplay-refactor-preflight.md`: 방울·상태·카메라·바구니의 파일별 수정 범위와 테스트.
- `user-playtest-adjustment-plan.md`: 사용자 피드백과 카메라 후보. 문서 앞부분의 과거 진행 상태보다 **이 HANDOFF의 중단 상태가 최신**이다.
- `progress.md`: 누적 작업 기록. 과거 에디터 PID, 임대, branch, “대기 중” 표현을 현재 상태로 재사용하지 않는다.
- 공개 문서 `Docs/Reviews/Prototype_2026-11-04.md`는 작업별 증거/한계를 설명한다. `Docs/Design/ImplementationResponsibilities.md`는 일부 오래된 제안이 남아 있으며 구현 완료 목록이 아니다.
- `Docs/Design/GameDesign_Source.md`를 원문으로, `GameDesign.md`의 명시적인 최신 사용자 결정을 우선 적용한다. 캣홀 방울 금지·튜토리얼 표식 등 최신 결정을 되돌리지 않는다.

반복하지 말아야 할 실패:

- Route01은 방울 전에 촛불 표식으로 갑옷이 출발했다. 이 실행을 방울 전달 증거로 사용하지 않는다. 더 오래된 모든 실행의 원인이 표식이었다고 일반화하지도 않는다.
- Route02/03은 protected/private Python 접근 때문에 이동 전 종료한 검사 스크립트 오류였다. 실제 게임 동작 실패와 구분한다.
- Route04는 침대 캡슐 충돌로 중단했다. Route05가 사용한 우회점을 기준으로 재개하고, 고양이 속도 프로퍼티를 강제로 올리지 않는다.
- 맵 이동 전에 Python UWorld/액터 참조를 해제한다. 과거 맵 복제 후 참조 누수로 에디터가 충돌했다. `ue_remote.py --isolated`, 함수 범위와 GC를 활용하고 콜백을 반드시 해제한다.
- 이미 연결된 BP 그래프를 통째로 재구성해 에디터가 충돌한 적이 있다. exact before 백업, 좁은 링크 변경, 엄격한 컴파일·저장·재로드를 사용한다.
- `Saved`와 `.superpowers`의 기존 증거·백업을 지우거나 덮어쓰지 않는다. 새 실행은 새 이름/폴더를 쓴다.

## 6. 재개용 명령과 운영 규칙

아래는 **다음에 작업 재개를 요청받았을 때** 사용할 명령이다. 이번 문서 작성에서는 실행하지 않았다.

```powershell
Set-Location C:\Users\whghk\Catrun
git status --short --branch
git log -1 --oneline
python -X utf8 Scripts/Prototype/verify_editor_connection.py
python -X utf8 Scripts/Prototype/ue_remote.py
```

MCP endpoint는 `http://127.0.0.1:8000/mcp`. 에디터가 없다면 UE5.8의 `UnrealEditor.exe`로 `Catrun.uproject /Game/Maps/MainMenu`를 열고 `-ExecCmds="ModelContextProtocol.StartServer 8000"` 및 새 로그 이름을 사용한다. live 맵 확인 뒤 임시 Python 연결을 이용한다. 사용자에게 보이지 않는 helper는 숨김 창으로 실행한다.

네이티브 DLL 링크 전에는 저장/PIE 상태를 확인해 에디터를 정상 종료한다. 빌드와 editor asset writer를 동시에 실행하지 않는다. `Scripts/Prototype/verify_final_build.ps1 -Phase Build|Automation|Cook -Run <새이름>`을 재사용할 수 있으며 각 phase를 별도 실행한다. UBA 권한 오류가 실제로 발생하면 `-NoUBA`를 사용한다. cook 대상은 MainMenu/Tutorial/Stage1/Stage2다.

사용자 지침: 불필요한 승인창/확인 질문 없이 승인된 작업을 진행하고, 실제 게임 수정 전 계획을 보여준다. 사용자가 직접 플레이하면 자동 조작을 멈추고, 명시적 중단은 즉시 따른다. 오디오 파일 삽입은 후순위, Stage3/각성 시스템은 이번 범위 밖이다. 구현·표현·검증 사실과 제안을 섞지 말고 짧은 한국어 진행 상황을 전달한다.

새 대화 재개 문구: **“C:\Users\whghk\Catrun\HANDOFF.md를 읽고, 튜토리얼 방울 소리가 갑옷에게 전달되지 않는 문제부터 이어서 진행해.”**
