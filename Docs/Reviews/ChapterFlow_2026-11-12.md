# 챕터 진행·복구와 연출 검토 — 2026-11-12

네이티브 빌드, 회귀 검사와 저장 에셋 콜드 감사를 마쳤다. 변경 기준은 `main`의 `8d360ba`이며, 후속 요청에 따라 이 문서에 기록한 게임 수정과 관련 스크립트·문서를 main 게시 범위로 확정했다. 기존 오디오 작업과 로컬 설정은 제외하고 보존했다. 아래 `Saved/` 증거 링크는 작업 PC에만 존재한다.

## 진행 저장과 맵 전환

- `CatrunProgressSave` 스키마 3에 `HighestUnlockedStageId`를 저장한다. 스키마 1·2의 기존 스테이지, 체크포인트 및 온보딩 정보는 읽을 수 있고 다음 정상 저장에서 승격한다. 새 게임과 앞 챕터 선택 후에도 도달한 최고 챕터를 유지한다. 선택한 챕터는 원래 시작 상태로 진입한다. 도달 기록은 실제 맵 도착을 확인한 뒤 반영한다. [저장과 도착 처리](../../Source/Catrun/LevelFlow/CatrunLevelFlow.cpp) · [스테이지 설정](../../Config/DefaultGame.ini)
- F3 저장은 대기·성공·실패를 알리고 실제 도착 저장의 재시도를 한 번으로 제한한다. F1 계단은 기존 성공 경로와 시퀀스를 유지하며 예약 거절과 뒤늦은 이동 실패에서 카메라·입력·포즈와 재시도 경로를 복구하도록 `BP_LevelExit`와 `BP_StairDescentDirector`를 연결했다. 두 BP의 메타데이터 재저장 뒤 별도 프로세스에서 그래프와 보존 대상 해시를 확인했다. F1 실패 복구 회귀 검사도 최종 통과했다. [F1 작성 스크립트](../../Scripts/GameplayRepair/repair_tutorial_travel_failure_20261112.py) · [콜드 감사](../../Saved/GameplayRepair20261112/TutorialTravelFailure/audit.json)
- Stage2는 C 석상이 발판에 안착하고 Gate11이 완전히 열린 뒤 포획 재시작에만 체크포인트를 전달한다. 복구 시 석상·발판·문·눈 발광을 되돌리며 공개 연출을 생략한다. 두 Stage2 맵에서 원래 시작 `(1375, 3700, 26.2)` 대신 Gate11 너머의 첫 후보 `(1375, 3100, 약 26)`에 실제 고양이 캡슐이 놓일 바닥과 여유 공간을 확인했다. 이동에 실패하거나 후보가 막히면 기존 안전 복구 경로를 사용한다. [복구 처리](../../Source/Catrun/Monster/CatrunRestartSubsystem.cpp) · [두 맵 콜드 감사](../../Saved/GameplayRepair20261112/CheckpointVisuals/161349-198438-35836/report.json)

## 메뉴·스테이지 제목·미니맵

- 이어하기는 기존 폰트와 실제 스테이지 이미지로 가로 카드 세 장을 구성한다. 마우스 클릭·호버와 Escape/뒤로 가기를 연결하고 잠긴 챕터는 비활성 상태로 표시한다. Stage1 썸네일은 연회장 중심으로 구도를 조정했고 Stage2는 디버그 표기를 걷어낸 이미지로 저장했다. `WBP_MainMenu`, `WBP_ChapterSelect`, `WBP_StageTitle`, `BP_StageEntryPresentation`과 썸네일 3개를 저장했다. [메뉴 에셋 저장](../../Saved/Chapters20261112/author.json) · [썸네일 저장](../../Saved/ChaptersFlow20261112/Captures/thumbnail_import.json)
- 제목은 `~ 마왕의 침실 ~`, `~ 연회장 ~`, `~ 마법회랑 ~`이다. 새 게임·진행·챕터 선택으로 실제 도착할 때 상단 중앙에 한 번 표시하고 포획 재시작에서는 생략한다. 페이드는 등장 0.5초, 유지 2.5초, 퇴장 0.7초로 `WBP_StageTitle`에서 조정한다. 6개 맵의 제목 액터와 위젯 구성을 콜드 감사에서 확인했다. [메뉴·제목 작성 스크립트](../../Scripts/Menu/author_chapter_selection.py) · [6개 맵 배치](../../Saved/Chapters20261112/maps.json) · [콜드 감사](../../Saved/Chapters20261112/audit.json)
- 미니맵은 화면 오른쪽 위에 실제 맵에서 캡처한 정적 바닥·벽 이미지와 발광 원을 겹친다. 플레이어는 초록색, 갑옷·촛불은 빨간색이다. 시작 시 적 목록을 구성하고 생성·삭제 이벤트로 갱신하며, 타이머는 등록된 마커 위치만 업데이트한다. 맵 종료 시 위젯·타이머·월드 등록을 해제한다. 좌표 투영·마커 수명 테스트가 통과했고, 별도 프로세스에서 6개 맵의 프레젠터와 텍스처, 좌표 설정을 확인했다. [미니맵 작성 스크립트](../../Scripts/Menu/author_minimap.py) · [위젯 수명과 좌표 처리](../../Source/Catrun/UI/CatrunMinimapWidget.cpp) · [콜드 감사](../../Saved/GameplayRepair20261112/Minimap/20261112-163225-415527/report.json)

## 포털·설정 발바닥·이동 조정

- Stage1 포털 시퀀스는 30 fps로 308프레임, 약 10.27초다. 첫 3.2초의 와이드 보행 다음에 푸른 얼굴 조명·클로즈업, 뒤쪽 포털 구도, 웅크림과 느린 점프로 이어진다. 점프는 시퀀스 안에서 구간을 리타이밍했다. 청록색 테두리, 어두운 반투명 중심과 보라색 소용돌이는 `M_Stage1PortalBlue`에서 조정한다. 양쪽 Stage1 맵에서 저장된 시퀀스를 다시 열어 캡슐·카메라 충돌, 시야선과 착지 바닥을 검사했다. [시퀀스·재질 작성](../../Scripts/GameplayRepair/upgrade_portal_paw_20261112.py) · [콜드 감사](../../Saved/CinematicPolish20261112/PortalPaw/20261112-155556-548554/report.json)
- 설정 발바닥은 `WBP_Setting`의 기존 36×36 실루엣에 `M_UI_SettingsPawMetal`을 연결했다. 금속 느낌은 UI 재질의 명암으로 조정한다. 포털 시퀀스·포털 재질·발바닥 재질·설정 위젯 네 에셋의 저장과 콜드 재로드를 확인했다. [에셋 작성 보고서](../../Saved/CinematicPolish20261112/PortalPaw/20261112-153946-512546/report.json)
- `BP_Cat.UpdateMovementSpeed`의 살금살금·걷기·달리기를 각각 48→53, 74→79, 119→124 cm/s로 고정했다. 일반 이동의 증가분을 빼고 계산해 석상 밀기 상한은 각각 48·74·100 cm/s로 유지된다. `BP_LivingArmor.ArrivalLookPlayRate`는 0.8이며 수색 클립과 상태가 함께 3.0→3.75초가 된다. 새 소리와 포획이 수색을 중단할 수 있다. 두 BP를 저장하고 6개 맵의 고양이·갑옷 16체 값을 콜드 검증했다. [조정 스크립트](../../Scripts/GameplayRepair/tune_locomotion_search_20261112.py) · [콜드 검증](../../Saved/ChaptersFlow20261112/LocomotionSearch/verify.json)

## 최종 검사

- Build06에서 네이티브 DLL 링크가 완료됐다. Tests04는 103개 중 성공 100개, 경고 포함 성공 3개, 실패 0개다. 경고는 게임 뷰포트가 없는 F1 테스트 환경과 기존 갑옷 회전·문 재탐색 테스트에서 발생했다. [빌드 결과](../../Saved/GameplayRepair20261105/ChapterFlowBuild20261112_06/result.json) · [자동 검사 결과](../../Saved/GameplayRepair20261105/ChapterFlowTests20261112_04/AutomationReport/index.json)
- 6개 맵에서 제목·미니맵 프레젠터 각각 하나를 확인했다. 이전 콜드 보고서와 비교해 기존 액터, 바구니 12개, 문·퍼즐 설정, 저장 그리드와 캡처 지형 해시가 일치했다. 감사 전후의 맵 파일 해시도 동일했다. [맵 보존 감사](../../Saved/ChaptersFlow20261112/preserved_stage_maps_audit.json) · [캡처 매니페스트](../../Saved/ChaptersFlow20261112/Captures/manifest.json)
- 6개 맵의 Map Check는 오류·경고 0개였다. 커맨드렛에는 기존 포털 블루프린트 주석의 `NodeGuid` 누락과 엔진·플러그인 경고가 기록됐다. [최종 콜드 감사 로그](../../Saved/GameplayRepair20261105/IntegrationBatch20261112_09/Editor.log)
- 검사 범위는 빌드, 네이티브 자동 검사, 저장 에셋 콜드 로드, 충돌 검사, 오프스크린 정적 캡처다. Computer Use와 PIE 없이 진행했다. 실제 화면 조작, 시퀀스 재생 및 전체 플레이는 미검증이다. Stage3는 미구현 범위다.
