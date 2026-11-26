# UI 점검·수정 납품 (2026-11-26)

본 프로젝트는 수정하지 않았다. 커밋·푸시도 하지 않았다. 후보는 `C:/Users/whghk/.codex/workspaces/UIFix_20261126/Catrun`.

## 적용 순서

1. `python -B apply_uifix.py` (dry-run이 기본. 25개 파일의 원본 해시를 확인하고 하나라도 다르면 멈춘다)
2. `python -B apply_uifix.py --apply` (백업: 본 프로젝트 `Saved/UIFixBackup/<시각>`)
3. C++ 빌드. 빌드 전에는 새 카드·포커스·시계 이동이 동작하지 않는다(에셋만 먼저 들어가도 깨지지는 않는다).
4. `Catrun` 자동화 테스트.

- 다른 세션이 같은 소스 파일을 먼저 바꿨다면 `--only asset --apply` 후 `--only source --patch-source --apply`(내부에서 `git apply --check`). 충돌하면 `uifix_source.patch`를 손으로 합친다. `CatrunElevatorTransition.*`는 건드리지 않았다.
- 되돌리기: `python -B apply_uifix.py --rollback <백업 폴더>`
- 스크립트 자체는 복사본에서 적용 → 재실행(0개) → 되돌리기 → `--patch-source` 적용 → 해시 변조 시 멈춤까지 확인했다.
- 임시 캡처 도우미 `UIReviewLibrary.*`는 납품에 들어 있지 않다.

## 화면별 점검 표

| 화면 | 문제 | 처리 |
|---|---|---|
| 메인메뉴 | 화살표·패드가 전혀 먹지 않음(포커스가 게임 뷰포트) | 이어하기 가능하면 이어하기, 아니면 시작하기에 포커스. 뷰포트로 빠지면 복귀. 강조 표시는 기존처럼 키보드·패드 입력 때만 |
| 메인메뉴 | 저장 안내가 메뉴와 왼쪽이 어긋나고 흐림 | 글자 시작 위치를 맞추고 20pt·그림자 |
| 이어하기 | **Stage3 카드가 없음**(설정에는 4구역, 썸네일도 있음) | 네 번째 카드 추가. 16:9·21:9·16:10에서 한 줄 4장 |
| 이어하기 | 카드·뒤로 버튼이 포커스 불가라 마우스 전용 | 포커스 가능, Tab 순환, 화살표, 패드 B로 닫기, 열 때 가장 최근 구역에 포커스 |
| 설정 | 위·아래·패드 이동이 막혀 있음(Tab만) | 목록·행·하단 버튼을 화살표/패드로 이동, 패드 B로 닫기. 펼친 목록·키 입력 대기 중에는 개입하지 않음 |
| 설정 | `100%` 잘림 / 키 행에서 기본값이 다음 행 이름에 붙음 / 기본값 15pt | 폭 100, 행 76, 18pt |
| 설정 | 기본값 표기 `SpaceBar·LeftShift·LeftControl`이 실제 표시와 다름 | `Space Bar·Left Shift·Left Ctrl` |
| 설정 | 1단위 밑줄이 1080p 미만에서 사라져 선택·포커스가 안 보임 | 2단위 (설정 17개, 이어하기 5개, 바구니 1개) |
| 일시정지(게임 중 설정) | 하단 버튼이 두 줄로 벌어짐 | 한 줄. 배경 가림 .68→.80 |
| 재시작 확인 | 포커스 갇힘·Esc·취소 정상 | 변경 없음 |
| HUD 시계 | 승강기 창고·칸에서 승강기와 고리를 가림 | 그 구간에서만 비어 있는 우상단으로 이동, 벗어나면 복귀 |
| HUD 시계 | 구역 제목, 튜토리얼 키 안내와 겹침 | 그동안 시계를 숨기고 끝나면 0.3초 페이드 인. 새 맵 첫 0.9초도 대기 |
| 미니맵 | 시네마틱·암전·메뉴 중 우상단에 사각 테두리 잔상 | 외곽선이 불투명도를 따르게 수정 |
| 안내 문구(방울·상호작용·저장·실패) | 다른 글꼴, 바탕 없음, 긴 문장 한 줄, 바구니 안내와 겹침(82%/83%) | 공통 글꼴·먹색 판·960 줄바꿈·73% 위치. 글자가 판 위쪽에 붙던 것을 세로 가운데로 맞춤(한 줄·두 줄, 완료 안내판 포함) |
| 방울 금지 | `방울을 울릴수없습니다` | `방울을 울릴 수 없습니다` (테스트 포함) |
| 튜토리얼 키 안내 | 금색 글자가 크림색 자판에서 거의 안 보임 | 짙은 갈색. 보조 문구 불투명도 1 |
| 튜토리얼 키 안내 | 키를 바꿔도 기본 키로 안내 | 바꾼 키만 실제 키로 교체 |
| 튜토리얼 키 안내 | 첫 프레임에 완전 불투명으로 번쩍임 | 시작 불투명도 0 |
| 바구니 안내 | 20pt, 그림자 없음 | 26pt, 그림자 |
| Tab 미니맵 | 확대·복귀, 21:9·16:10에서 겹침 없음 | 변경 없음 |
| 구역 제목 | 시계와 겹침 | 위 시계 처리로 해결 |
| 완료 | Stage3에서 “스테이지 2를 통과했어요”, 다른 색·글꼴 | `최후의 경비 구역 통과`처럼 실제 구역 이름, HUD 색·공통 글꼴. 엔딩 연출은 미정이라 그대로 |
| 실패 문구 | “타이틀로”, “구간” 등 용어 혼용 | “시작 메뉴로”, “구역” |

게임 규칙, 저장, 게임 조작 키는 바꾸지 않았다.

## 남은 문제

- 새 게임 직후 인트로 첫 1프레임에 “진행을 저장하고 있습니다.”가 보인다(시네마틱이 조작을 가져가기 전 프레임). 고치지 않았다.
- 재시작 확인 창의 버튼 글자(`취소`)도 같은 글꼴이라 조금 위로 치우쳐 있다. 고치지 않았다.
- 포커스 사각형은 엔진 기본 파란 점선이다. 톤과 다르지만 일부 행(콤보·체크박스)의 유일한 포커스 표시라 유지했다.
- 바구니 안내가 길어질 때(`[W/A/S/D] 방향 선택`) 밑줄은 92 폭 그대로다.
- 로딩 화면, Stage1 포털 저장 표시(`WBP_ExitTransition`)는 화면으로 확인하지 못했다.
- 왼쪽 스틱 이동은 키 이벤트로만 보냈고 실제 패드로는 확인하지 못했다.
- 옛 문구를 검사·기록하는 파일이 남아 있다: `Docs/Design/GameDesign.md:83`, `Scripts/Prototype/{promote_canonical_maps,validate_bell_action_path,validate_canonical_runtime}.py`. 다른 작업자의 문서라 바꾸지 않았다.

## 검증 결과

- 최종 소스·에셋으로 빌드 성공(`Out/build_fix9.log`).
- `Catrun` 전체 자동화(NullRHI): **165개 통과(경고 포함 10), 실패 0** — `D:/CatrunWork/ui/Runs/test5-*/Report/index.json`
- D3D12 렌더 테스트 `Catrun.UI`+`Catrun.Settings`(`-CatrunHUDRender`): **25개 통과, 실패 0** — `D:/CatrunWork/ui/Runs/testgpu1-*/Report/index.json`
- 새 테스트: `Catrun.UI.Status.ClockYieldsToTitleAndLift`, `Catrun.UI.Notice.ReadableLayout`. `SavedMenuLayout`은 4장 기준과 포커스 가능 여부, 2560x1080·1680x1050을 추가했고 `ExactBellDenial`은 새 띄어쓰기로 바꿨다.
- 실제 `-game` D3D12 캡처(UI 포함, 실제 Slate 키 이벤트): 1600x900, 1680x720(21:9), 1440x900(16:10).

### 캡처 경로

- 같은 화면 전후 나란히: `D:/CatrunWork/ui/Compare/*.jpg` 162장 (왼쪽 전, 오른쪽 후)
- 원본: 전 `D:/CatrunWork/ui/Runs/before_all-*/shots`, 후 `D:/CatrunWork/ui/Runs/after3-*/shots`. 포커스 기록은 각 `report.json`
- 전 캡처의 1600x900 일부는 888x500으로 찍혀 확대해 비교했다. 1680x720과 1440x900은 같은 크기다.
- 승강기 시계: `Compare/s2_cabin_*`, `s2_warehouse_*` / 제목: `s3_hud_*` / 키 안내: `tut_tab_1600x900` / 완료: `s3_complete_*`

### 실행 화면으로 확인하지 못한 것

- 마감까지 GPU 차례가 오지 않은 항목: 이어하기에서 Tab·아래 화살표로 `뒤로`에 가는 수정(빌드·테스트만 통과. Esc와 패드 B 닫기, 카드 사이 이동은 화면에서 확인), 포획·시간초과 화면의 전후 캡처, 한 줄로 줄인 `다음 구역부터 제한 시간이 있습니다.`의 최종 문구(두 줄짜리 이전 문구가 뜨는 것까지는 화면에서 확인).
- 남아 있던 캡처 실행은 통합을 위해 취소했다. 대기열에 이 세션의 실행은 없다.
- D3D12 렌더 테스트 25개는 `build_fix7` 소스로 실행했다. 이후 바뀐 것은 시계 경고 그리기, 판 여백, 문구, 시간 제한 안내이며 `build_fix9`로는 전체 165개와 실제 화면만 확인했다.
- 실제 패드 장치와 실제 플레이 완주.

## 파일

- `manifest.json` 파일별 원본·새 해시 / `payload/` 적용할 파일 / `uifix_source.patch` C++ 20개 파일의 git patch(프로젝트 루트 기준) / `apply_uifix.py`
- 에셋 5개: `WBP_ChapterSelect`, `WBP_Setting`, `WBP_MainMenu`, `WBP_BasketInteractPrompt`, `WBP_Tutorial_KeyHint`. 저장에 쓴 스크립트는 `../Tools/author.py`, `../Tools/author2_steps.py`.

## 연출 감수(DirectingAudit_2026-11-26) 추가 항목

| 항목 | 처리 | 확인 |
|---|---|---|
| D-01 | 완료 문구를 실제 구역 이름으로. 결말은 정하지 않음 | 화면 `Compare/s3_complete_*` |
| U-01 | 제목이 떠 있는 동안 시계를 숨김(제목 위치는 그대로, Stage3 포함) | 화면 `s3_hud_*`, 테스트 |
| U-02 | 미니맵 외곽선이 숨김을 따름 | 시네마틱·메뉴·설정 화면. 포획·시간초과는 미촬영 |
| B-04 | 30% 이하 안쪽 테두리 전체를 호박색, 15% 이하 붉은색 + 남은 구간을 문자판에도 표시, 호 두께 2.5→4.5→6. 시계 맥박 금지 기준에 따라 움직임·소리는 넣지 않음. 문턱값은 그대로 | 화면 `Runs/after_hint-*/shots/final_warning*`, `final_urgent*` |
| A-10 | 키캡 글자를 짙은 갈색으로 | 화면 `tut_tab_1600x900` |
| D-02 | 창고·칸에서 시계를 우상단으로 | 화면 `s2_warehouse_*`, `s2_cabin_*` |
| X-02 | 방울 띄어쓰기, 동상 되돌리기·봉쇄 장치·완료·안내 문구를 `~습니다`로 통일 | 테스트·정적 확인 |
| A-08 | 튜토리얼 계단 420cm 안에 처음 들어오면 `다음 구역부터 제한 시간이 있습니다.` 4초, 한 번 | 화면 `after_hint-*/shots/tut_timelimit_*` |
| 키 안내 번쩍임 | 시작 불투명도 0 | 연속 12프레임 `after_hint-*/shots/flash_*` |

`CatrunPuzzleReset.cpp`, `CatrunStage3Objectives.cpp`는 문구 줄만 바뀌었다. Stage3 세션이 먼저 들어가면 `--patch-source`를 쓴다.

## 통합 순서 확인 (05:23, 본 프로젝트 Source 복사본)

- gameplay → cinematics → ui → elevator 순서로 4개 모두 충돌 없이 적용된다. **`git apply --ignore-whitespace`가 필요하다.** 없으면 본 프로젝트 파일의 CRLF 때문에 gameplay·cinematics·elevator 패치가 실패한다(ui 패치는 단독으로는 통과).
- cinematics가 `CatrunRestartSubsystem.cpp`를 먼저 고치므로 ui는 `python -B apply_uifix.py --apply --only source --patch-source` → `--apply --only asset` 순으로 쓴다. 해시 검사 방식(`--only source`만)은 의도대로 멈춘다.
