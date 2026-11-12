# 2026-11-12 후속 프레젠테이션·포획 통합

바구니 천 부착 후면의 진입/탈출 차단과 배치·F 안내·방울·전체 지도 수정은 `BasketUsability_2026-11-12.md`에 기록했다. 이 문서는 그 뒤 사용자가 감시 채팅으로 추가 요청한 범위다. 사운드 제작은 중단 상태다. Computer Use, 화면 입력, PIE, 수동 플레이는 사용하지 않는다.

## 구현 범위

- 설정: 개발자 모드 하단 상태 문구의 고정 높이를 제거하고 버튼 줄바꿈과 스크롤을 정리했다. 중복 개발 안내를 접었다. 원래 마우스 클릭·호버·Escape 그래프는 보존했다.
- 이어하기: 실제 맵에서 침실 창, 연회장 식탁/벽난로, 마법회랑 석상/스테인드글라스를 1280×720으로 촬영했다. 카드는 16:9 사진과 동일한 폭을 유지하며 창 폭에 맞춰 3/2/1열로 줄바꿈한다. 예전 HorizontalBox에서 남은 좌측24 여백을 없애 WrapBox의34 간격만 적용한다. 저장·해금·선택 로직은 변경하지 않는다.
- HUD: 기존 LevelFlow/재시작/퍼즐/카메라·입력 소유 상태를 조회해 시네마틱과 메인메뉴에서 상태 표시·미니맵·저장 안내·방울 표시를 숨긴다. 같은 월드의 연출 종료/취소 시 기존 표시 선택과 지도 확대 상태가 돌아온다. 설정을 열면 지도를 접는 기존 동작은 유지한다. 저장 데이터 처리는 계속된다. 메인메뉴 정적 식별만 기존 월드 서브시스템에 FName으로 캐시하고, 동적 소유 상태는 즉시 평가한다.
- 포획: 기존 RestartSubsystem을 단일 포획 소유자로 사용한다. 첫 유효 갑옷만 고양이 포즈·카메라·입력·재시작을 소유하며 다른 갑옷은 접근과 애니메이션을 멈추고 대기한다. 실패·취소·소유자 삭제에는 이전 행동을 복구하며, 예약 여행은 정확히 해당 소유자의 요청만 취소한다.
- 적 표시: 감지/전파 수치는 유지한다. 갑옷 표시만 실제 고양이 중심 감지 경계에 맞춘 낮은 불투명도(0.12)의 남색으로 바꾼다. Stage2 및 미러의 촛불은 최신 요청에 따라 위치 순찰을 끄고 제자리 시야 회전을 유지한다.
- 포털: 기존 고양이 애니메이션과10.27초 길이를 보존하고 공간/포털 중심의 세 와이드 구도로 바꿨다(FOV84/84/76). 첫 카메라를 뒤로 빼고 낮춰 전신을 담고 두 번째 구도에도 발 아래 여백을 확보했다. 반투명 구름 소용돌이·외부 광륜·깊이를 기록하는 중심 면을 분리했다. 입장 완료284프레임에서 고양이를 가리고 Stop에는 가시성을 복원한다. 기존 푸른 얼굴 조명 외에120루멘의 약한 보조광 하나로 접근하는 고양이와 바닥을 구분한다. 연출은 BP/Level Sequence/재질 소유이며 외부 에셋은 사용하지 않는다.

## 검증 기록

- `PresentationFollowupBuild20261112_03`: 최종 네이티브 링크 성공.
- `PresentationFollowupTests20261112_02`: **114개 성공(일반110+경고 포함4), 실패0, 미실행0**. 포획 경쟁/취소/여행, HUD 복원/메뉴 식별, 바구니/저장/전환 회귀, 저장 UMG의 네 가지 창 크기와 개발자·게임 버튼 조합을 포함한다. 경고는 메시 없는 AI 픽스처3개와 게임 뷰포트 없는 기존 F1 픽스처1개다.
- 이전 테스트01은 분리된 테스트 월드에 WorldContext가 없는데 seamless travel을 조회하던 결함을 드러냈다. 컨텍스트 확인을 먼저 하도록 수정한 뒤 위 전체 검사가 성공했다. 사용자 에디터가 아닌 작업 전용 숨김 프로세스였다.
- 독립 Astra 최종 코드 리뷰: 요청 범위 잔여 P1/P2 없음. 정적 리뷰와 자동 검사를 실제 플레이 수용 검사로 표시하지 않는다.
- `EnemyPresentationApply20261112_01`: 원본/미러6맵의 갑옷 표시와 Stage2 촛불 설정 저장. 현재 액터 위치·순찰 경로·감지 수치와 범위 밖 콘텐츠를 보존했다.
- `PresentationColdAudit20261112_01`: 새 프로세스에서6맵 적 설정,4맵 바구니 앞쪽 진입/후면 차단/앞쪽 탈출,6맵 지도와 F 안내/방울 타이밍, 설정·이어하기 위젯/캡처를 검증했다. 읽기 전후 콘텐츠924패키지 해시 동일. 상세 `Saved/GameplayRepair20261112/PresentationColdAudit.json`.
- `PortalFollowupAuthor20261112_03`와 `PortalFollowupAudit20261112_01`: 시퀀스·BP·재질5개 저장과 별도 프로세스 재로드 성공. 맵·애니메이션 클립·전환 BP/UMG는 보존했다.
- `PortalFollowupRender20261112_01`: 저장 시퀀스10프레임에서3개 실제 카메라/고양이 골격 포즈/조명 평가,284프레임 가림과 Stop 복원, 원본 패키지 보존을 확인했다. 최초 렌더에서 첫 구도의 고양이 잘림과 가는 포털 선 위주 표현을 발견해 후속 시각 보정을 진행했다.
- `PortalRefineAuthor20261112_01`/`PortalRefineAudit20261112_01`: 카메라 두 구도와 재질3개 보정 및 별도 프로세스 재로드 성공. `PortalFillAuthor20261112_02`/`PortalFillAudit20261112_01`: Presentation BP의 보조광 하나 추가와 재로드 성공. 기존 BlueLight·애니메이션·가림/복원·컷·맵 해시 유지.
- **최종 렌더 `PortalFillRender20261112_01`**: `Saved/GameplayRepair20261112/PortalFollowup/Frames/20261112-202227-020615/report.json`, PNG10개.0프레임 전신/120프레임 발 여백,248프레임 도약,275~283프레임 포털 앞에 남은 뒷부분,284프레임 완전 가림을 메인/별도 리뷰 에이전트가 확인했다.3카메라·골격 포즈 변화·Stop 상태 복원·원본 해시 보존 모두 성공. 표본 프레임에 벽/포털 잘림 없음.0프레임 발은 하단에 가깝고60프레임 고양이는 여전히 어두운 실루엣이다. 연속 재생의 속도감·게임 페이드·UMG까지 검증했다는 의미는 아니다.

## 조정 위치

- `Scripts/Menu/author_settings_continue_followup.py`: UMG 레이아웃, 촬영 이미지 연결. `/Game/UI/Settings/WBP_Setting`, `/Game/UI/Continue/WBP_ChapterSelect`.
- `Scripts/GameplayRepair/author_portal_followup.py`: 카메라 키/FOV/컷, 포털 재질. `/Game/Cinematics/Stage1/Portal/LS_Stage1_PortalExit`, `BP_Stage1PortalPresentation`, `M_Stage1PortalBlue`, `Followup20261112/`.
- `Scripts/GameplayRepair/refine_portal_followup.py`: 최종 와이드 구도/구름 흐름 재질. `author_portal_fill.py`: BP의 `PortalApproachFill`(120루멘, 반경350cm, 위치는 포털 로컬(-40,-230,105)). 원래 작성 스크립트를 완료 자산에 다시 적용하지 말고 각 author/audit 기준 보고서를 사용한다.
- `Scripts/GameplayRepair/render_portal_followup.py`: 저장 시퀀스 평가와 오프스크린 프레임 증거. 게임 전용 페이드/UMG와 연속 재생 감각은 이 정적 캡처의 범위 밖이다.
- `Scripts/GameplayRepair/author_enemy_presentation_followup.py`: 여섯 맵의 갑옷 표시, 두 Stage2 맵의 촛불 위치 순찰. 맵/패키지 백업과 범위 외 해시를 검증한다.
- `Source/Catrun/LevelFlow/CatrunLevelFlow.*`: HUD 표시 자격과 정적 월드 식별. `Monster/CatrunRestartSubsystem.*`: 포획 소유권, `Monster/CatrunArmor.*`: 대기/복원.

현재 작업은 로컬 저장하며 이번 묶음의 커밋·푸시는 별도 요청 전 수행하지 않는다. 중단한 오디오 초안과 다른 사용자 작업은 보존한다.
