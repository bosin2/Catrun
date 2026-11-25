# 연출 감사 보고서 (2026-11-25 23:37 시작 ~ 11-26 02:30 중단)

증거 루트: `Saved/DirectingAudit/20261125-233732/`(이하 R). 프레임은 `R/runs/<run>/frames/f<n 6자리>00000.png`, 텔레메트리는 `report.json` rows의 같은 n.
**미완 보고서다.** 사용 한도 때문에 묶음 C·D·E의 정밀 판독과 일부 재생 전에 중단했다(5절).

## 1. 요약
- S1 4건 · S2 18건 · S3 10건(추정·기존 한계 포함).
- 가장 시급한 5개: **E-01** 포획 카메라가 나무판만 비춤, **D-01** Stage3 끝에 "스테이지 2를 통과했어요", **U-01** 제목이 시계에 가림, **E-02** 포획 카메라 튐, **B-01** Stage2 도착 전 플레이 화면 노출.

## 2. 실행 환경
- HEAD `ceddc03`, main + 미커밋 `Stage2.umap`(23:16). 시작 직후 `R/Snapshot/Catrun`에 복사(맵·Config 해시가 기준과 동일)해 재생했다. 초기 시험 실행만 본 경로를 썼다.
- UE 5.8, DX11 offscreen 독립 PIE 창(뷰포트 약 1224x686), 고정 1/30초, UserDir 격리, `Shot showui`(UI 포함). main DLL에 `CaptureGameViewport`가 없고 빌드가 금지라 이 방식을 썼다.
- 캡처 무결성: 일부 프레임에 크기가 다른 에디터 뷰포트가 섞여 제외했다(예: capture n2·4·13·503·570·571, elev n1385~1387). 근거로 쓰지 않았다.
- UMG 애니메이션은 실시간 기반이라 제목·안내의 지속 시간은 판정하지 않았다. Esc·Tab은 Slate 전처리기라 주입되지 않아 Esc는 설정 API로 대체했다.
- 손플레이 완주가 아니다. fixture: 위치 순간이동, `catrun.NoArmorCapture`(exit·exitinput·stairs·stage2·elev·stage3b), 시간 예산 축소(timeout 24초, edge 30초, 메모리 값), edge의 갑옷 이동, 메뉴 시작은 버튼 delegate.
- 스킬: 사용 writing-plans, dispatching-parallel-agents, game-planning. **미호출** systematic-debugging, verification-before-completion. 원인 추적과 증거 확인은 일부만 직접 했다.
- 서브에이전트 완료: A, B(`R/findings/A.md`, `B.md`). C·D·E 미실행. 표의 "(에이전트)"는 메인이 다시 보지 않은 판독이다.

## 3. 허점
원인 경로는 `Source/Catrun` 기준.

|ID|구간·이벤트|렌즈|현상|의도·규칙 근거|증거|판정|심각도|원인 위치|수정 방향|M|
|---|---|---|---|---|---|---|---|---|---|---|
|E-01|튜토리얼 포획|2·7|책상 옆 포획 8.6초 내내 나무판 확대만 보인다. 갑옷·고양이가 안 나오고 고양이는 (84,157,36)에 멈춘다|CapturePresentation.md:7-9(벽 한계만 기록)|tutcapture n1253~1511, cam (139,217,26) 고정|확인됨(자동 보행이 책상에 막힌 상태)|S1|Monster/CatrunCapturePresentationComponent.cpp:201 후보 전부 탈락 시 return, :156 직교 카메라 위치 사용. 탈락 이유는 추정|실패 시 피사체를 보는 안전 구도로 대체| |
|D-01|Stage3 출구|1·10·11|"현재 구간 완료! 스테이지 2를 통과했어요. 이곳에 머물며 자유롭게…" 문구뿐이고 결말이 없다|GameDesign.md:221|stage3b n1822·1852(`review/end1852_crop.png`)|확인됨(포획 끔 fixture)|S1|LevelFlow/CatrunPlayHUD.cpp Refresh의 IsStageComplete 고정 문구|단계별 문구 분기, 결말은 기획 결정|M09|
|U-01|제목(튜토리얼·Stage1·Stage2)|10|제목 가운데가 시계 판에 덮여 읽히지 않는다. Stage3만 정상|GameDesign.md:268, ChapterFlow_2026-11-12.md:14|menu n868, stairs n951, exit n803 / 정상 elev n1958|확인됨|S1|UI/CatrunPlayerStatusWidget.cpp:109. 제목 배치는 추정|Stage3 배치를 전 구간에 적용| |
|A-08|튜토리얼 안내|1·6|다음 구역의 시간 제한 설명이 관찰된 문구에 없다|GameDesign.md:187|menu·stairs·introinput texts 이벤트(에이전트)|추정(튜토리얼 전체 플레이 미재생)|S1|안내 없음(추정)|계단 앞 1줄 안내| |
|E-02|포획 Framing|2·3|0.5초 전환 중 카메라가 수 미터 튄다|CapturePresentation.md|s1capture_exit n10→11 577cm, tutcapture n669→670 443cm, capture n1057→1058 299cm, edge n1094→1095 396cm(에이전트 수치)|확인됨|S2|같은 파일 :170-208 매 틱 후보 재선정|후보를 첫 틱에 고정| |
|B-01|Stage1→2|3|도착 시네마틱 전에 쿼터뷰 플레이 화면이 먼저 보인다(3틱, 화면 증거 1장)|GameDesign.md:268|exit n405, rows n405~407; exitinput rows n359~361|확인됨(PIE, 패키지 미확인)|S2|도착 director가 3틱 뒤 제어, 암전 인계 없음(추정)|검은 화면으로 시작| |
|B-02|Stage1 출구 복도|2|문을 지나 약 1.2초 고양이가 안 보이고 화면 대부분이 검다|GameDesign.md:263|exit n55~91|확인됨|S2|출구 벽 가림(추정)|벽 페이드 또는 발동 앞당김| |
|U-02|시네마틱·암전·포획·시간초과|3·10|빈 미니맵 테두리가 남는다|GameDesign.md:268|menu n840, timeout n785, exit n403, tutcapture n1300|확인됨|S2|UI/CatrunMinimapWidget.cpp:314-316 외곽선(에이전트)|숨길 때 Collapsed| |
|B-03|시간초과|1·5·11|마왕 각성이 작은 흰 문구와 암전뿐(약 1.6초), 갑옷 포획 8.6초보다 약하다|GameDesign.md:205|timeout n740~785|확인됨|S2|Monster/CatrunRestartSubsystem.cpp:122-147|조명·흔들림·소리 신호| |
|B-04|경고 30%·15%|6·7|시계 얇은 호의 색만 바뀌고 호도 짧아져 거의 안 보인다|GameDesign.md:190|timeout n541·640(`review/clock.png`)|확인됨|S2|CatrunPlayerStatusWidget.cpp Arc 폭 2.5|문턱 순간 맥동·소리| |
|A-01|인트로|1·6|게임용 촛불 시야 부채가 갑자기 켜져 인트로 동안 보인다|GameDesign.md:268|menu n186~835|확인됨, 의도 미정|S2|Monster/CatrunCandle.cpp:250(에이전트)|시네마틱 중 숨김| |
|A-02|첫 조작|2|고양이가 침대 보·안내 문구 뒤 어두운 바닥에 묻힌다|GameDesign.md:263|menu n868~1147|확인됨|S2|시작 위치(추정)|위치·배치 조정| |
|A-03|추격|2·7|가구에 고양이가 가려 약 7초 상황을 못 읽는다|-|tutcapture n1048~1252(에이전트)|확인됨|S2|가구 가림 처리 없음(추정)|가구 페이드·실루엣|M06|
|A-04|LookDemon 컷|1·2|잠든 마왕 얼굴이 잘리고 어둡다|GameDesign_Source.md:7|menu n331~495(에이전트)|확인됨|S2|Cam_03_LookDemon|마왕이 읽히는 구도| |
|A-05|재시작|9|재시작 1.1초 뒤 80cm 걷고 표식이 찍혔다(1회)|GameDesign.md:154|tutcapture n920→953|확인됨(1회)|S2|부채 위상(추정)|시작 유예| |
|B-05|포털 출발+도착|5|건너뛰기 없이 약 23초. Space·Enter·F·P 무효|정책 없음|exit n92→786, exitinput|확인됨|S2|스킵 입력 없음|스킵 정책 결정| |
|B-06|포털 앞|5|약 2.1초 특별한 동작 없이 멈춤. 앞발 탐색은 main에 없음(312f)|Stage1To2CinematicReview|exit n279~342(에이전트)|기존 한계(7b1c 미반영)|S2|LS_Stage1_PortalExit|병합 여부 결정| |
|C-01|Stage2 도착|2|석상 전경·발판 잘림|같은 문서|exit n603·667|기존 한계(7b1c 미반영)|S2|LS_Stage2_PortalArrival|병합 여부 결정| |
|D-02|승강기 F 전|2|화면이 거의 검고 칸이 위쪽 끝에서 시계에 덮인다|ElevatorTransition_Handoff:38·46|elev n694~739|확인됨(DX11)|S2|E23_View_Warehouse 구도(추정)|칸을 내리거나 시계 숨김| |
|D-03|승강기 도착|5|하차 보행 약 10.8초, F부터 조작 복귀까지 약 40.6초|Handoff:80-81(26cm/s는 의도)|elev n1503~1827, n739→1957|확인됨, Space 스킵 미시험|S2|E23 director|보행 축약 검토| |
|D-04|승강기 얼굴 컷|2|아래 카메라 얼굴이 검다|Handoff:12|elev n1091~1157|기존 한계(DX11), DX12 미재생|S2|조명|DX12로 재확인| |
|D-05|Stage3 성문|2·11|기둥이 앞을 가리고 성문이 화면 오른쪽 끝에 걸린다. 완료 뒤에도 갑옷이 쫓는다|GameDesign_Source.md:7|stage3b n1741~2002|확인됨(포획 끔 fixture)|S2|카메라·기둥(추정)|성문을 보여 주는 카메라|M09|
|X-01|소리|7|BGM 참조 0, 시퀀스 오디오 트랙 없음. 방울과 승강기 3종만 참조|GameDesign.md:277|`R/static/audio_referencers.json`, `sequences.json`|추정(정적 확인)·기존 한계|S3|에셋 미연결|-| |
|A-06|잠 깨기|8|방울이 떠 보인다|-|menu n316(에이전트)|확인됨|S3|추정|방울·이불 조정| |
|A-07|인트로 배경|2|천장 없는 검은 공간|-|menu n646~720|확인됨|S3|세트|구도·세트 보강| |
|A-09|계단 컷|5|고양이가 나간 뒤 빈 계단 약 1초|-|stairs n890~|확인됨|S3|LS_Tutorial_StairDescent|페이드 앞당김| |
|A-10|키캡|10|글자가 베이지 위 베이지|-|menu n868|확인됨|S3|WBP_Tutorial_KeyHint|대비 보강| |
|B-07|Stage1 첫 화면|2|절반이 외벽, 불꽃만 떠 있다|-|stairs n951|확인됨|S3|추정|시작 구도| |
|B-08|포획|2|"!"가 화면 위로 잘리고 감지 원이 남는다|-|s1capture_exit n155~247|확인됨|S3|AlertMark·링|포획 중 숨김| |
|B-09|포털|4|고양이가 검정→파랑→검정|-|exit n217~327|확인됨|S3|BlueLight(추정)|조명 완화| |
|B-10|도착 끝|3|카메라 정지 뒤 조작까지 1.4초|-|exit n744~786(에이전트)|확인됨|S3|시퀀스|정지 단축| |
|X-02|문구 톤|10|"방울을 울릴수없습니다" 띄어쓰기, "~했어요/~했습니다" 혼용|GameDesign.md:83|Sound/CatrunNotice.cpp:106 외|추정(정적 확인)|S3|문구|톤 통일| |

문제없음: Stage1 타이머는 시네마틱·포획 중 멈춤, 포획 중 시간초과 이중 재시작 없음(edge n1085→1344), 출구 진입이 포획보다 우선(edge n1367), Stage3 장치 3개·동상 2개·완료 경로 작동(stage3b), 포털·도착 중 설정이 열리지 않음(exitinput).

## 4. 감정곡선 메모
- 튜토리얼: 호기심은 좋으나 안 보이는 마왕, 가려진 첫 조작, 나무판 포획으로 긴장이 끊긴다.
- Stage1→2: 얼굴 클로즈업까지 쌓인 긴장이 정지와 화면 번쩍임으로 식는다. 마왕 각성이 가장 약한 실패다.
- 승강기는 이완 구간으로 길다. Stage3는 성문이 안 보이고 "스테이지 2" 문구로 끝나 "집으로 돌아간다"가 전달되지 않는다.

## 5. 재생하지 못한 것과 다음 방법
|항목|이유|다음|
|---|---|---|
|A: 튜토리얼 바구니·방울 유인·갑옷 문 개방(`tut`)|다른 세션 UE와 메모리 경합으로 충돌|`R/tools/run2.ps1 -Scenario tut -Map /Game/Maps/Tutorial`|
|C: 동상 C·B 철창|fixture가 한 방향만 밀어 실패. A만 재생(stage2 n1321~1576)|`-Scenario stage2b -Map /Game/Maps/Stage2`|
|C·D·E 정밀 판독|사용 한도. stage2·stage3·stage3b·elev·misc·capture·edge는 재생했으나 표 항목 외는 안 봄|`R/AGENT_BRIEF.md`로 서브에이전트 실행|
|E: 표식 중 바구니, 캣홀 가림, 방울 금지 문구|misc에서 포획과 fixture가 겹쳐 무효|`-Scenario mark -Map /Game/Maps/Stage1`|
|승강기 DX12 비교·Space 스킵|미실행|`-Scenario elev -Tag dx12 -RHI d3d12 -Map /Game/Maps/Stage2`|
|Tab 확대, 실제 Esc, 로딩 화면, 오디오 재생 로그|주입·PIE 한계, 로그 미수집|라우팅 자동화·패키지 실행|
|갑옷 96cm에서 23초 미포획(capture n321~985)|차폐 여부 미판독|해당 프레임 판독(M11)|

## 6. 변경 확인
- 게임 파일(Content·Config·Source·Plugins·Binaries·uproject·SaveGames)의 목록·크기·시각과 맵·ini·세이브 해시가 시작 전과 같다(변경 0건). HEAD 동일.
- 감사가 만든 것은 `Saved/DirectingAudit/`와 이 파일뿐이다. 그 사이 `CLAUDE.md`, `Scripts/Regression20261126/`, `Docs` 삭제·수정이 git 상태에 새로 나타났다. 이 감사가 만든 것이 아니며, 병행 중인 다른 세션의 변경으로 보인다(`R/baseline/git-status-before.txt`, `-after.txt`).
