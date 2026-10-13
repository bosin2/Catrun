# Catrun

Unreal Engine 5.8로 제작 중인 고양이 쿼터뷰 게임 프로젝트입니다.

## 게임 기획

- [기획 기준 요약과 미결정 사항](Docs/Design/GameDesign.md)
- [사용자 제공 기획서 원문](Docs/Design/GameDesign_Source.md)

## 프로젝트 열기

1. Unreal Engine 5.8을 설치합니다.
2. 저장소를 내려받고 `Catrun.uproject`를 엽니다.
3. 콘텐츠 브라우저에서 `/Game/Stage1`을 열어 현재 스테이지를 확인합니다. 튜토리얼은 `/Game/Tutorial`입니다.

프로젝트에서 활성화한 엔진 플러그인은 Modeling Tools Editor Mode, MCP Client Toolset, Model Context Protocol, Editor Toolset입니다.

## 구성

- `Content/Characters/BlackCat`: 고양이 캐릭터, 애니메이션, 블루프린트, 머티리얼
- `Content/Characters/LivingArmor`: 리빙아머 메시, 애니메이션 9종, 금속 머티리얼
- `Content/Environment/Stage1`: 스테이지 메시, 원본 모듈, 머티리얼, 텍스처, 책장 에셋
- `Content/Input`: Enhanced Input 액션과 매핑 컨텍스트
- `Content/Blueprints/GameModes`: 게임모드
- `Config`: 공유 프로젝트 설정

`Saved`, `Intermediate`, `DerivedDataCache`, 개인 에디터 설정과 로컬 백업은 버전 관리에서 제외합니다. 원본 Blender/FBX 작업 파일은 이 프로젝트 폴더 외부에 있어 포함하지 않습니다.

현재 가장 큰 에셋은 8MB 미만이며, 에셋 파일은 일반 Git 바이너리로 저장합니다. 이 저장소를 받는 데 Git LFS는 필요하지 않습니다.
