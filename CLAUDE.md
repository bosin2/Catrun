# Catrun — Claude 작업 지침

Codex로 진행하던 프로젝트를 Claude가 이어받기 위한 진입 문서다. (2026-11-25 작성)
게임: 《마왕님, 고양이가 도망갑니다》 — UE 5.8, 고정 쿼터뷰 잠입·유인·환경 퍼즐.

## 먼저 읽을 순서
1. `Docs/Handoffs/AI_WorkGuide_20261125.md` — 가장 잘 정리된 인계 지침(규칙·우선순위·남은 작업)
2. `Docs/Design/GameDesign.md` — **현행 기획 기준** 
3. `Docs/Design/GameDesign_Source.md` — 사용자 원본 기획. 현행과 다르면 현행+최신 사용자 지시가 우선
4. `Docs/Reviews/TeamAgenda_2026-11-25.md` — 미결정 안건 M01~M11. **AI가 임의로 확정하지 않는다**
5. `Docs/Reviews/ProjectAudit_2026-11-25.md` — 기획↔구현 차이 F01~F08
6. `HANDOFF.md` — 누적 이력(110KB+). 여러 섹션에 "최신"이 붙어 있으니 맨 위 날짜 섹션만 현재로 보고, 나머지는 이력으로 취급

`AGENTS.md`는 **오디오(Cat Audio Director) 작업 전용** 규칙이다. 일반 작업에 확대 적용하지 않는다.

## 작업 환경 사실
- 실제 프로젝트: `C:\Users\whghk\Catrun` (main). `.codex/worktrees/*`, `.codex/workspaces/*` 사본에 적용하지 않는다.
- `.codex/workspaces/ElevatorRevision3_*` 후보 프로젝트는 Content(Maps 제외)·Source·Scripts·Plugins가 **main으로 연결된 junction**이다. 거기서 저장하면 main이 바뀐다.
- 에디터 조작은 Unreal 내장 MCP(`.mcp.json`: `http://127.0.0.1:8000/mcp`)로 백그라운드 처리한다. 사용자는 화면 직접 조작보다 백그라운드 작업을 선호한다.
- 검사용 에디터와 작업 에디터를 동시에 띄우지 않는다(메모리).
- 화면 판정 캡처는 `-RHI d3d12`. `Scripts/ElevatorTransition/run_runtime.ps1` 기본값 d3d11은 얼굴이 검게 나온다.
- 자동화 결과는 종료코드가 아니라 `index.json`의 성공/실패 수로 판정한다(종료코드 0인데 실패가 있던 전례).
- 현재 활성 DLL은 `Binaries/Win64/UnrealEditor-Catrun_ElevatorRevision3.dll`(`UnrealEditor.modules`가 가리킴). 일반 `UnrealEditor-Catrun.dll`은 이전 빌드다. 다음 정상 빌드 때 이름이 돌아오는 것이 정상.

## 보존해야 할 규칙 (요약 — 상세는 AI_WorkGuide 4절)
- Stage2는 도달/해금만 저장. 이어하기·포획·시간초과·재시작은 일반 시작점·초기 퍼즐·전체 제한시간. 중간 저장/Gate11 재시작 부활 금지. Stage1 시간 저장은 유지.
- 소리는 열린 연결을 따라 전파(벽 관통 거리 판정 금지). 갑옷만 소리를 듣는다. 캣홀 방울 금지는 최신 규칙.
- 고양이 외형·메시·스켈레톤(78본) 보존. Stage3 반대편 카메라는 Stage3 전용.
- 기존 맵·BP·재질·시네마틱·사용자 저장을 덮어쓰지 않는다. 맵(.umap)은 바이너리라 병합 불가 — 통째 복사 금지, 수정 전 백업.
- 수치·구조·엔딩 등 미정 기획은 제안만 하고 사용자 결정을 받는다.
- 커밋·푸시는 사용자가 요청할 때만.

## 정식 맵
`/Game/Maps/` MainMenu · Tutorial · Stage1 · Stage2 · Stage3. `SoundTest_*`는 보조용이며 정식 맵과 다르다(NoBellZone 누락). 루트의 `Content/Stage1.umap`, `Content/Tutorial.umap`(1KB)은 10월 잔재다.
