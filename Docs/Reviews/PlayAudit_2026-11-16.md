# 플레이 감사 — 2026-11-16

검사 기준: main `0b564e714f3015e9e9922624d8a3250650650ce5`. 이번 요청은 문제점 조사와 제안이며, 게임 코드·맵·에셋은 수정하지 않았다. 독립 리뷰는 `Saved/PlayAudit20261116/evidence-review.md`에 있다.

## 우선 수정·결정 사항

| 우선순위 | 현재 확인한 사실 | 권장 방향 |
|---|---|---|
| 높음 | Stage1 시작점 `(880,2320)`에서 전경 문에 고양이가 가려져 위치를 읽기 어렵다. 정상 Visibility 채널 광선 6개 중 4개가 `S1_Door_LowerHall_East_Open`에 닿으며, 문은 원래 불투명 `M_BedroomDoor` 슬롯을 사용한다. | 특정 고양이/액터 예외 대신 전경 건축물에 공통 가림 재질 규칙을 적용한다. 문·문틀·벽·계단의 모든 슬롯과 원본/미러 맵을 함께 검사한다. 계단에 닿은 나머지 2개 광선만으로 계단 재질 고장을 단정하지 않는다. |
| 중간 | Stage1의 벽 22개에서 `MI_CastleStone_WallOcclusion`의 반투명 재질이 Nanite와 호환되지 않는다는 경고가 나온다. | 외관을 보존하는 masked/dither 경로로 통일하거나 필요한 메시의 Nanite 사용을 명시적으로 분리한다. 위 문 가림과 별개의 재질 호환 문제다. |
| 기획 결정 | **A·C 완료, B 미완료 상태로 Stage2 마지막 출구까지 실제 이동해 완료했다.** 출구 코드에는 모든 석상 완료 조건이 없다. | B를 필수 퍼즐로 만들지, 선택 경로로 둘지 정한다. 필수라면 완료 조건과 실제 문 연결을 함께 보완하고, 선택이라면 지름길·보상의 의미를 명확히 한다. 현재 기획에는 세 개 모두 필수라는 명시가 없어 즉시 계약 위반 버그로 단정하지 않는다. |
| 중간 진단 | Stage2 화면에 `108.009 MiB / 400 MiB`, 상주 레이트레이싱 지오메트리 20% 기준 초과 경고가 반복 표시된다. 완료 카드 위에도 겹친다. | 새 프로세스의 Stage2 직접 진입과 메뉴 경유 진입에서 상주 지오메트리를 비교해 원인을 좁힌다. 이는 전체 400MiB 풀 고갈이나 메모리 누수의 증거가 아니다. 예산 증가나 메시지 숨김을 원인 수정으로 취급하지 않는다. |

작은 정리 항목: 포털 BP 주석의 GUID 누락 경고 7개가 로드 시 나타난다. 맵 시작의 `SpawnActor failed because no class was specified`도 반복된다. 현재 GM_Cat의 HUDClass/DefaultPawnClass가 None인 것은 확인했으나, 호출 스택까지 확인하지 않아 해당 경고의 원인을 확정하지 않았다.

## 플레이 경험 개선 제안

- 방울을 들은 갑옷의 짧은 고개 돌림·시선·조사 방향을 더 명확히 읽게 한다. 첫 Stage1 캣홀은 갑옷이 방 쪽으로 확실히 들어간 뒤 반대로 나와야 했다. 소리 전파나 감지 반경을 바꿀 근거는 이번 검사에서 나오지 않았다.
- 석상/발판과 대응 문에 같은 문양·빛을 사용해 열린 경로를 기억하기 쉽게 한다. Stage2 Gate03은 세 석상을 푼 후에도 별도 일반 문으로 닫혀 있었다. 열린 Gate02를 이용한 중앙 경로는 실제 통과했다. 닫힌 문 자체를 충돌 버그로 분류하지 않는다.
- 첫 석상 이후 체크포인트 도달 시 짧은 비침해적 확인을 검토한다. 포획은 C와 그 문을 보존하지만 A/B는 초기화한다. 이것은 현재 요청된 동작이며, 저장 버그가 아니다. 모든 기존 BP 안내가 없다고 단정하지는 않는다.
- Stage2 완료 카드는 현재 큰 좌상단 사각 패널이다. 메뉴의 얇은 선·투명 배경 스타일과 표현을 맞추면 마무리가 더 자연스럽다. 기능 오류와 구분되는 디자인 제안이다.

## 이번 실제 실행에서 확인한 범위

| 흐름 | 결과와 제한 |
|---|---|
| MainMenu 시작 → 튜토리얼 | 원래 인트로 재생 관찰. 정상 이동·방울·캣홀·계단 오버랩으로 튜토리얼을 통과하고 Stage1에 자동 도착했다. |
| Stage1 첫 갑옷·바구니 | 방울 청취와 우회 이동, 갑옷이 방으로 진입한 뒤 캣홀 탈출, 창고 바구니 정면 진입·은신·탈출을 확인했다. 포획 후 원래 시작점으로 돌아왔다. |
| Stage1 나머지 경로 | 촛불 표식 후 추격/포획을 확인했으나 연회장·출구까지 연속 완주하지 않았다. 이번 검사만으로 Stage1→2 포털 시네마틱을 통과했다고 주장하지 않는다. |
| 옵션·이어하기 | 실제 저장된 BP 버튼 이벤트로 화면/조작 탭, 변경 없는 적용, 닫기, 일시정지/복귀, 시작 메뉴, 챕터 선택, Stage1/2 진입을 확인했다. 검사한 창 크기에서 글자/하단 버튼 잘림을 재현하지 못했다. 물리 마우스 호버나 OS 키 입력 검사는 아니다. |
| Stage2 C/A/B | 정상 이동 입력으로 각각 밀기·관성·안착을 거쳐 세 퍼즐을 모두 해결했다. 세 링크의 `complete=true`, `offset=-280`, Reveal INACTIVE, 원래 카메라·입력·HUD 복귀를 같은 표본에서 확인했다. |
| Stage2 되돌리기·바구니 | A 석상을 잘못 민 뒤 방의 복구 장치 가까이에서 정상 상호작용으로 되돌렸다. Room4 바구니 정면 진입·은신·탈출을 확인했다. |
| Stage2 포획 복구 | 중앙 촛불 표식 후 실제 갑옷 포획. `(1375,3100)`의 첫 석상 문 앞에서 재시작, C 완료/문 개방 유지, A/B 초기화, 정상 입력·카메라 복구를 확인했다. |
| Stage2 최종 탈출 | 복구 후 A만 다시 풀고 B를 풀지 않은 상태에서 중앙 촛불의 회전 타이밍을 맞춰 Gate02 통과. 마지막 갑옷을 정상 방울로 유인한 뒤 출구까지 달려 완료했다. `stage_complete=true`, MOVE_WALKING, 입력 잠금 없음, NoCapture=false, 완료 카드 확인. |

세 퍼즐을 모두 해결한 실행과 마지막 탈출 실행은 **포획 재시작으로 나뉜 실행**이다. 메인메뉴부터 모든 스테이지를 무중단으로 완주한 검증으로 합치지 않는다. Stage2 마지막 방울은 실제 로그의 방출 → 갑옷 청취(remaining143) → 소리 위치 도착 → Stage complete로 연결된다.

## 자동 회귀검사

`Saved/PlayAudit20261116/FullAutomation01/AutomationReport/index.json`: **121개 통과(일반116 + 경고 포함5), 실패0, 미실행0**, 프로세스 종료코드0. D3D12 오프스크린 렌더와 `-CatrunMinimapRender`를 켰으므로 미니맵 OffscreenPreview의 픽셀 검사 본문도 실행됐고, SavedMenuLayout도 통과했다.

경고가 붙은 검사는 레벨플로우의 D3D12 예약 가상 리소스 진단(258GB/256GB), 튜토리얼 BP 실패 복구, AI 테스트용 촛불 눈 뼈 누락, 테스트용 갑옷 회전 재생 fallback, 도어 재계획의 의도된 막힌 경로였다. 경고 없는 통과로 바꾸어 보고하지 않는다. D3D12 가상 예약량 진단은 앞의 108/400MiB 상주 지오메트리 경고와 다른 항목이며, 실제 GPU VRAM을 258GB 사용했다는 뜻이 아니다.

이 검사는 실제 전체 플레이와 별도다. 물리 Tab 누름/놓음, Esc, 키 재지정 후 실제 키보드·마우스 포커스/호버, 새로운 프로세스에서의 실제 저장 파일 로딩 수용 검사는 이번 플레이 범위에 포함하지 않았다.

## 종료와 보존

소유 Catrun PIE 에디터의 dirty map/content는 0개였고 정상 종료했다. 최종 자동화 프로세스도 종료했다. 기존 사용자 `CatrunProgress.sav`, `GameUserSettings.ini`, `EditorPerProjectUserSettings.ini`와 자동화가 사용하는 기존 미니맵 미리보기2개를 각각 원본 SHA256으로 복원했다. 근거: `Saved/PlayAudit20261116/restored-state.json`. 다른 프로젝트 에디터는 보존했다.

이번 결과물은 이 보고서·HANDOFF와 `Saved/PlayAudit20261116/`의 검사 자료다. 게임 코드·맵·에셋·공유 설정은 변경하지 않았으며 커밋·푸시하지 않았다. 시작 전 있던 오디오/도구/로컬 설정 변경도 그대로 보존했다.

## 재현 근거와 검사 방식

- 전용 Catrun 에디터와 실제 MCP 8001을 사용했다. 다른 프로젝트의 에디터/MCP8000과 사용자의 데스크톱 입력은 건드리지 않았다.
- 실제 PIE에 Enhanced Input 이동·달리기·살금살금·방울·상호작용을 주입했다. 메뉴는 실제 BP 버튼 delegate를 호출했다. 무적/NoCapture, 위치 순간이동, 퍼즐 플래그 강제 변경, 적 규칙 변경은 사용하지 않았다.
- 단일 스레드 오프스크린 실행 및 기록 부하가 있으므로 이 실행의 프레임 속도를 제품 성능 벤치마크로 쓰지 않는다. 초기 Slate 프레임 입력의 홀드 편차, 실패한 continuous-input 실험, 잘못 선택한 경로, Python API 오류는 검사 도구 한계이며 게임 결함으로 세지 않는다.
- 최초 `occluders.json`은 Visibility를 collision profile로 잘못 조회해 폐기했다. 수정한 `occluders-channel.json`의 정상 trace channel 결과만 사용했다.
- `final-state.json`의 보호된 save 필드 조회는 실패했으므로 디스크 저장 내용 검증 근거로 사용하지 않는다. 기존 진행도는 사전 백업했고 검사 후 원본으로 돌린다.

주요 자료(프로젝트 상대 경로):

- `Saved/PlayAudit20261116/Run01/TutorialCompleteRoute01/observations.json`
- `Saved/PlayAudit20261116/Run02/stage1-live-spawn00000.png`, `occluders-channel.json`
- `Saved/PlayAudit20261116/Run02/stage1-committed-escape-drive.json`, `stage1-hidden.json`, `stage1-basket-exit-north-drive.json`
- `Saved/PlayAudit20261116/Run02/final_progression_runtime.json`: Stage2 game=317.2606466에 A/B/C 완료 + 카메라·입력 복구 동시 확인
- `Saved/PlayAudit20261116/Run02/final_progression_runtime_tail.jsonl`, `after-retry-pause.json`
- `Saved/PlayAudit20261116/Run02/stage2-timed-through-to-exit-hall-drive.json`, `stage2-final-bell-escape-drive.json`
- `Saved/PlayAudit20261116/Run02/final-state.json`, `stage2-final-complete00000.png`
- `Saved/PlayAudit20261116/Run02/Editor.log`, `systems-notes.md`, `route-notes.md`, `ui-save-notes.md`, `evidence-review.md`

Stage2 최종 유인 경로: 출구 홀 `(937,735)`에서 방울 → 행동 종료 후 `(937,920)→(650,920)→(650,100)→(715,100)→(715,-80)`. 이 경로에서는 방울이 실제로 사용되었으므로 “방울 없이 클리어 가능”으로 확대 해석하지 않는다.
