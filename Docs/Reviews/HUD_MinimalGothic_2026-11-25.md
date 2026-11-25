# HUD 수정 검증 — 2026-11-25

범위: `5825/Catrun` 작업 트리의 플레이 상태 HUD와 미니맵 프레임·색상. [디자인 기준](../Design/HUD_MinimalGothic_2026-11-25.md).

## 확인 결과

- Unreal 5.8.2 / Win64 Development Editor 네이티브 빌드 성공.
- `Catrun.UI.` 에디터 자동 검사: **11개 성공, 0개 실패**. 표시 소유자, 미니맵 좌표·확대 배치·적/랜드마크 수명, 복구 안내, 새 상태 HUD 검사를 포함한다.
- 새 상태 HUD를 실제 `WBP_PlayerStatus`에서 생성하여 Slate로 렌더링했다. 정상, 충전 중, 고갈/사용 불가, 튜토리얼과 960×540·1920×1080·2560×1080 출력 확인. 숫자/상태 텍스트 및 기존 카드 숨김, 상태 변화의 좌하단 영역 한정, HUD 숨김 시 투명 픽셀 확인을 통과했다.
- 별도 D3D12 Stage1 게임 실행에서 `Catrun.UI.Status.LiveStage`: **1개 성공, 0개 실패**. 라이브 스태미나/방울 상태 연결, HUD 단일 인스턴스, 플레이 중 숫자 텍스트 제거를 확인했다. 실제 게임 화면에서 시계·세로 막대·방울 링·도면과 마커가 보인다.
- D3D11의 검증용 낮은 텍스처/그림자 설정으로 같은 라이브 검사를 재실행하여 성공했다. 1280×720 최종 캡처에는 VRAM 경고가 없고, 세 HUD 영역이 겹치지 않는 것을 확인했다. 이 그래픽 설정은 검증 프로세스에만 적용했다.
- `git diff --check` 통과. 에디터 실행이 자동 추가한 로컬 Android File Server 설정은 원복했다.

## 증거 위치

작업 트리의 `Saved/HUDDesign20261125/` 아래:

- `Report/index.json`, `Automation.log`: 에디터 검사 11개.
- `EditorUser/Saved/HUDDesign20261125/`: 상태별 실제 Slate 출력 PNG 6개. 오프스크린 PNG의 감마와 실제 뷰포트 색은 다를 수 있으므로 색상은 게임 캡처로 확인한다.
- `LiveReport/index.json`, `LiveStage.log`: D3D12 라이브 검사.
- `GameUser/Saved/HUDDesign20261125/Stage1-live.png`: 첫 실제 게임 캡처.
- `LiveLightReport/index.json`, `LiveLight.log`: 가벼운 렌더 설정에서 재검증한 라이브 검사.
- `Stage1-final.png`: 최종 실제 게임 캡처. 원본은 `GameLightUser/Saved/HUDDesign20261125/Stage1-live.png`.

## 한계

첫 D3D12 게임 캡처에 VRAM 예산 초과 경고가 나타났다. 이 기록은 HUD 기능 검증이며 GPU 성능 통과를 의미하지 않는다. 여러 에디터가 실행된 환경에서 검사했고, 전체 스테이지 연속 수동 완주와 사용자 미술 승인은 범위 밖이다. 원본 작업 폴더의 열려 있는 에디터를 교체하거나 Git 게시하지 않았다.

## 후속 미니맵 아이콘 수정

- 노란 고양이 얼굴(28), 붉은 투구(26), 불꽃과 짧은 몸통만 남긴 촛불(24)로 교체했다. 단위는 DPI 적용 전 Slate 크기다. 짙은 외곽선과 서로 다른 실루엣을 사용한다.
- 네이티브 빌드 성공. 최종 코드의 `Catrun.UI.Minimap` **7개 검사 성공, 0개 실패**.
- 실제 렌더 픽셀에서 고양이 노랑·갑옷 빨강을 검사했다. 축소·확대 중간·확대 유지·복귀 상태 모두 좌표 정렬과 마커 크기 변화를 통과했다. 단순 클래스 교체 확인에 그치지 않는다.
- 최종 검사 결과: `Saved/MinimapGlyphs20261125/Final/Report/index.json`, 로그 `Automation.log`, 실제 위젯 출력 `Previews/`.
- 최종 Stage1 라이브 검사 **1개 성공, 0개 실패**. 1280×720 실제 플레이 캡처에서 노란 고양이 얼굴, 붉은 투구, 단순 촛불이 도면 위에서 구분되는 것을 확인했다. 검증용 D3D11 낮은 그래픽 설정을 사용했다.
- 라이브 결과는 `Saved/MinimapGlyphs20261125/Final/LiveReport/index.json`, 최종 캡처는 `Saved/MinimapGlyphs20261125/Stage1-final.png`. 이전 실패한 색상 출력은 최종 근거로 사용하지 않는다.

## 최신 정정: 매우 단순한 반투명 표시

사용자가 위 이모지 표현을 과하다고 지적했다. 해당 표현은 최종 디자인에서 폐기한다.

- 눈·코·하이라이트·외곽선을 제거했다. 고양이는 노란 귀 실루엣, 갑옷은 틈 하나의 붉은 투구, 촛불은 단색 불꽃 하나다.
- 크기를 22/20/18 Slate 단위로 축소하고 78% 불투명도로 통일했다. 겹치는 장식 조각이 없어 실루엣 안의 투명도가 일정하다.
- 프레임 바탕은 42%, 내부 보조 바탕은 8%, 도면은 72% 불투명도. 테두리는 1 Slate 단위로 줄였다.
- 네이티브 빌드와 미니맵 자동 검사 7개 통과. 색상 픽셀·프레임 투명도·지도 확대와 좌표 정렬을 검사했다.
- 최신 근거는 `Saved/MinimapGlyphs20261125/Simple/Report/index.json`, `Automation.log`, `Previews/`다. 위의 이모지 캡처와 구분한다.
- Stage1 라이브 검사도 1개 통과했다. 실제 배경이 미니맵 바탕 너머로 보이며, 작은 단색 실루엣의 색과 위치가 유지되는 것을 확인했다. 최종 화면은 `Saved/MinimapGlyphs20261125/Simple/Stage1-final.png`, 실행 결과는 같은 폴더의 `LiveReport/index.json`이다.
