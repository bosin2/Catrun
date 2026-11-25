# 밤샘 통합 작업 (2026-11-25 밤 ~ 11-26 아침)

사용자가 자는 동안 여러 세션이 후보 프로젝트에서 작업하고, 총괄 세션이 본 프로젝트에 순서대로 합쳤다. 이 폴더의 나머지 문서는 각 작업의 납품 기록 사본이다. "본 프로젝트에 적용하지 않았다"는 문구는 납품 당시 상태이며, 아래 표의 항목은 11-26 05:52~07:05에 적용했다.

| 작업 | 기록 | 적용 |
|---|---|---|
| 방울 범위 통일(튜토리얼 650→500), 책장 파동, Stage3 갑옷 범위 표시 | GameplayBugs.md | C++, Tutorial·Stage2·SoundTest 2개 맵 |
| UI 점검·수정 | UI.md | C++, 위젯 5개 |
| Stage2 논리 오류 6건과 아트 | Stage2.md | 액터 81개, 에셋 21개, 격자 |
| Stage3 아트, 새 러그 | Stage3Art.md | 액터 49개, 에셋 |
| Stage3 탁자 길찾기, 튜토리얼 캣홀 격자 | MapDefects.md | 격자, 표식 6개 |
| 시네마틱 조명, 포획 카메라, 시간초과 | Cinematics.md | C++, 시퀀스 2개 |
| Stage1 포탈 출구, Stage2 포탈 도착(2차본) | Portal.md | 시퀀스 2개, BP 1개 |
| 인트로·계단 고양이, 포획 자세, 갑옷 손동작 | CatAndCapture.md, ArmorHands.md, BlackCatRefine.md | 시퀀스 2개, 애니메이션 2개 |
| Stage2→3 승강기 재연출 | Elevator.md | C++, Stage2·3, 에셋 |
| 승강기 먼지 재질의 끊긴 입력 복구 | `Saved/Regression20261126/fixes` | 재질 1개 |
| Stage3 도착 첫 프레임 회귀 수정 | [회귀검사](../Regression_2026-11-26.md) | C++ |

- 사용자 결정(11-26): 플레이 고양이는 바꾸지 않고 시네마틱만 Compact 계열을 쓴다. 새 고양이의 미술 승인은 아직이다.
- 검사 결과와 미확인 항목은 [회귀검사](../Regression_2026-11-26.md), 통합 전 연출 점검은 [감수 보고서](../DirectingAudit_2026-11-26.md)를 본다.
- 통합 전 백업: `D:\CatrunWork\integration_backup_0555`, 로컬 Git ref `refs/backup/overnight_20261126_before`. 작업별 백업은 각 문서에 있다.
- 실제 빌드는 전체 재빌드였다. 오래된 obj가 섞이면 자동화가 크래시한 전례가 있으니 소스를 파일 복사로 넣을 때 수정 시각을 확인한다.
- 중복: 같은 새 고양이 메시가 `Characters/BlackCat/Refine_20261125`와 `Cinematics/Stage1/Portal/RefineCat20261126`에 있다. 승강기가 뒤의 것을 쓴다.
