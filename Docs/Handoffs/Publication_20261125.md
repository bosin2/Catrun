# 2026-11-25 GitHub main 통합 기록

사용자의 최신 요청에 따라 실행 중이던 세 채팅의 인계 문서 작성 종료를 확인한 뒤, 완료된 제작 파일과 문서를 함께 게시한다. 이전 문서의 '푸시하지 않음'은 해당 채팅 종료 당시의 기록이다.

## 인계 문서

- [Stage3](../Reviews/Stage3_AI_Handoff_2026-11-25.md)
- [Stage2 → Stage3 승강기](../Design/ElevatorTransition_Handoff_20261125.md)
- [BlackCat 모델·애니메이션](BlackCat_AI_Handoff_20261125.md)
- [Stage1 → Stage2 과거 검증본](../Reviews/Stage1To2CinematicReview_2026-11-25.md)

## 포함 범위와 상태

- 본 프로젝트에 저장된 Stage2/Stage3 맵·전용 에셋·소스·제작/검증 스크립트와 리뷰 문서.
- 승강기 Revision 2 콘텐츠 및 Revision 3 소스와 적용 스크립트. Revision 3의 본맵 카메라 저장과 새 DLL 활성화는 여전히 미완료다. 게시 과정에서 에디터를 조작하거나 미완료 적용을 실행하지 않았다.
- BlackCat 작업 사본 `110f`에만 있던 제작 파일을 같은 `SourceArt/BlackCat` 상대경로로 복사했다. 기존 동일 파일은 유지했으며, 복사한 파일은 SHA256으로 대조했다. Blender 자동 백업 `.blend1`, 실행 로그, 캐시는 추가하지 않았다.
- 최신 Compact 모델/클립/영상은 생성됐으나 최종 포장, 사용자 미술 승인, Unreal 통합은 미완료다. 과거 버전도 의존 소스 및 제작 이력으로 보존하며 승인본으로 간주하지 않는다.
- 작업 사본 `7b1c`의 완료된 Stage1→2 검증 자료는 `SourceArt/BlackCat/PortalEntry20261125/UEReviewArchive`에 원래 상대경로와 binary patch로 보존했다. 이후 연출 지시로 대체된 버전이므로 현재 게임 시퀀스를 덮어쓰지 않았다.
- 다른 작업 사본의 기존 UI·디자인 문서는 이미 main에 통합돼 있음을 비교했다. main보다 오래된 사본으로 되돌리지 않았다.

## 검증의 범위

각 인계서의 실제 검사 결과와 미검증 항목을 그대로 유지한다. 이번 게시 작업은 파일 대조, Git 변경 검토, 텍스트 오류/자격증명 점검, LFS 및 원격 커밋 확인을 수행한다. 새 게임 빌드·PIE·미술 승인을 수행했다는 뜻은 아니다. Stage3 카메라/기둥 최종 확인도 남아 있다.

인계서에 적힌 절대경로는 제작 당시 위치다. BlackCat의 저장소 내 파일은 위 상대경로에서 찾을 수 있다. `Saved` 아래 실행 증거와 DLL 등 로컬 생성물은 기존 Git 제외 정책을 유지한다.
