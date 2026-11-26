# Catrun 외부 코드 사용 범위

2026-11-03 사용자 결정: 이번 후보 중 AsyncLoadingScreen과 ActionRoguelike 두 개만 사용한다.

## AsyncLoadingScreen — 프로젝트 플러그인

- 원본: https://github.com/truong-bui/AsyncLoadingScreen
- 버전: 1.7.0, UE 5.8.0 대상
- 고정 커밋: `77f3cdcfc32afa2422d1208e04b61df3bd9a52dc`
- 원본 ZIP SHA-256: `EE4DB98806E27ADCF64F234EA99584C46875A2C6730A8F3D07E3A7752D609413`
- 위치: `Plugins/AsyncLoadingScreen`. 소스와 기본 에셋을 포함하며 upstream 소스는 수정하지 않았다.
- 라이선스: MIT. 플러그인의 `LICENSE`와 원본 저작권 표기를 보존한다.
- 활성화: `Catrun.uproject`.
- 화면 설정: `Config/DefaultGame.ini`의 `/Script/AsyncLoadingScreen.LoadingScreenSettings`.

OpenLevel로 맵을 여는 동안 어두운 배경, 고양이 발자국 로딩 표시, 한국어 안내를 표시한다. 로딩 완료 시 자동으로 닫고 최소 표시 시간을 강제하지 않는다. 기존 재시작의 페이드와 맵 목적지 결정은 기존 코드가 담당한다. 수동 StopLoadingScreen 호출이나 게임 모듈 의존성 추가는 필요하지 않다.

PIE에서는 MoviePlayer 로딩 표시를 검증할 수 없다. Standalone 또는 패키지에서 맵 이동과 재시작을 검사한다. 현재 설정은 OpenLevel 전환용이며 스트리밍 전환이나 Sequencer 시네마틱을 구현하는 기능은 아니다.

설정은 Project Settings → Game → Async Loading Screen에서도 편집 가능하다. 현재 Startup Loading Screen은 원본 기본값을 유지한다. 추후 시작 영상을 추가할 경우 이 플러그인의 Startup 설정과 영상 패키징 규칙을 따른다.

## ActionRoguelike — 설계·구조 참고

- 원본: https://github.com/tomlooman/ActionRoguelike
- 현재 기본 브랜치 README 기준 UE 5.8.
- 프로젝트에 소스·에셋을 복사하거나 런타임 의존성으로 추가하지 않는다.
- 참고한 실제 코드:
  - [RogueAction.h](https://github.com/tomlooman/ActionRoguelike/blob/master/Source/ActionRoguelike/ActionSystem/RogueAction.h): 실행 가능 판정, 실행 상태, 쿨다운 조회, 연출 함수 구분.
  - [RogueActionComponent.h](https://github.com/tomlooman/ActionRoguelike/blob/master/Source/ActionRoguelike/ActionSystem/RogueActionComponent.h): 시작·종료 이벤트, 행동 일괄 종료, 컴포넌트 단위 상태 관리.

Catrun에서는 기존 컴포넌트를 유지하면서 공통 판정·쿨다운은 C++ 한 곳에서 결정하고 BP는 입력 요청과 연출 이벤트를 연결하는 기준으로 활용한다. 구체적 적용 기준은 현행 [GameDesign.md](GameDesign.md)를 따른다. 이 문서를 추가했다고 방울·갑옷 구조 정리가 완료된 것은 아니다.

원본에 포함된 에셋은 별도 이용 조건이 있다. 현재는 구조만 참고하며, 직접 코드나 에셋을 가져올 때는 해당 항목의 이용 조건을 별도로 확인한다.

## 이번에 추가하지 않는 후보

Cog, SPUD, Grasp는 도입 대상에서 제외한다. 기존 Unreal 기본 플러그인과 기존 프로젝트 의존성은 이 후보 제한과 별개다.

## 적용 검증 — 2026-11-03

- Unreal 5.8.2 CatrunEditor Development 빌드 성공 (`Saved/Logs/AsyncLoadingScreen_Build.log`).
- `Scripts/Loading/verify_loading_settings.py`를 Unreal Python commandlet에서 실행: 한국어 문구, Center 레이아웃, 실제 발자국 Texture 참조, 자동 종료 설정 확인 (`Saved/Loading/settings-verification.json`).
- `UnrealEditor.exe -game -RenderOffscreen` Standalone에서 플러그인 DLL 로드, Entry → Stage2 OpenLevel, 맵 로드 완료 후 TestExit 코드 0 확인 (`Saved/Logs/LoadingStandalone.log`).
- 위 확인은 패키지 빌드·시각 검수·전체 플레이 검증을 포함하지 않는다.
