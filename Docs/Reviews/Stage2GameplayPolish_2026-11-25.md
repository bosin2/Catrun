# Stage2 동상·로비·철창 수정 및 검증

2026-11-25. `Content/Maps/Stage2.umap`, `Content/Maps/SoundTest_Stage2.umap`에 반영했다. 다른 채팅의 최신 엘리베이터 변경을 포함한 원본 맵으로 재적용한 뒤, 원본 해시가 유지되는 것을 확인하고 검증한 패키지만 복사했다.

## 변경 내용

- 하단 C 동상 발판에 `Armor_C_BellSentry`를 배치했다. 벨로 경비를 유인하면 동상을 밀 시간이 생긴다. 도착 후 탐색은 약 12초이며 이후 주둔지로 복귀한다. 이 경비만 발소리를 무시하고, 벨·장치 소리·표식·포획 규칙은 유지한다. 기존 경비의 설정은 바꾸지 않았다.
- 로비 `Candle_01`은 X를 1105에서 1075로 30cm 이동하고 yaw를 65도로, `Candle_02`는 기존 위치에서 yaw를 -99도로 조정했다. 두 촛불의 회전 반각은 0.5도다. 새로운 벽이나 차단 볼륨은 추가하지 않았다. 천구의와 기존 장식을 유지했다.
- A/B/C 철창은 새 설정 사본에서 하강 속도를 140에서 110cm/s로 낮췄다. 이동 중 약한 화면 진동, 바닥에 닿는 순간 0.26초의 짧은 충격 진동, 0.78초의 작은 바닥 먼지를 연결했다. 8개의 기존 비충돌 먼지 평면이 시작 순간 카메라를 향하도록 하여 실제 화면에서 읽히게 했다.
- 기존 카메라 이동 3초·복귀 2.6초·잠금 상한 10.5초와 게임플레이 구도를 유지했다. 초기 진입에는 먼지가 나오지 않으며 초기화·중단 시 효과와 입력 잠금을 정리한다.

새 에셋은 `/Game/Environment/Stage2/GameplayPolish_20261125` 아래 설정 1개와 `Presentation/Build_03`의 프레젠테이션 Blueprint·재질 3개다. 기존 프레젠테이션 원본 3개 패키지는 해시가 보존됐다. 실험용 Blueprint와 실패한 생성 폴더는 원본 프로젝트에 넣지 않았다.

네이티브 변경은 `CatrunArmor.h/.cpp`의 기본값 false인 인스턴스별 `bIgnoreFootstepSounds`와 관련 회귀 검사 1개다. 원본 프로젝트 빌드는 성공했고, 검증한 DLL과 반영 후 DLL의 해시가 같다.

## 실제 검증

| 검사 | 결과 | 증거 |
| --- | --- | --- |
| 하단 C, 정상 시작 위치에서 실제 이동·밀기 | 벨 사용 후 발판·철창 완료 및 입력 복귀, 무벨 밀기 차단, 발소리 유인 차단: 3/3 | `Saved/Stage2GameplayPolish_20261125/Evidence/lower_native.json` |
| 로비 양방향 걷기·달리기 및 이전 우회 경로 | 13/13 안전 통과 실패. 12개는 실제 촛불 이벤트와 보이는 표식, 1개는 촛불 표식 전 네이티브 갑옷 포획 | `Evidence/lobby_native.json` |
| B 우회 | 실제 B 문 완료 후 고양이 시작 위치만 준비하고, 실제 `IA_Sneak` 입력으로 11개 지점을 이동. 발소리·표식·포획 없이 도착 | `Evidence/b_detour_native.json` |
| 철창 프레젠테이션 | A/B/C 완료, A 초기화, A director 종료: 5/5. 바닥 아래 하강, 효과 시간, 카메라·이동·시점 입력 복귀 확인 | `Evidence/gate_native.json` |
| 네이티브 회귀 검사 | `ArmorFootstepOptInPreservesBellAndDevice`: 성공 1, 실패 0 | `Evidence/native_unit.json` |
| 두 저장 맵 변경 범위 | 허용한 촛불·신규 경비·설정 참조·프레젠테이션만 변경. 기존 액터 요약, 프레젠테이션 변수와 카메라 설정, 원본 재질 해시 확인 | `Evidence/scope.json` |

로비는 추가로 실제 엔진 충돌·시야 쿼리를 이용해 2cm 격자와 최대 0.1도 간격의 회전 위상을 검사했다. 시야 반경과 거리에서 각각 2cm를 줄인 조건에서도 감지 영역을 피하는 남북 연결 경로가 없었다. 유한 격자·위상 검사이며 연속 공간의 수학적 보증이나 모든 플레이 상황의 증명으로 해석하지 않는다.

철창 검사는 실제 마지막 밀기와 네이티브 이벤트를 사용하되 동상·고양이 위치를 준비한 프레젠테이션 검사다. B 우회도 B 퍼즐 전체를 처음부터 푼 검사가 아니다. 전체 스테이지의 수동 플레이 완료를 주장하지 않는다. 최종 화면은 분리된 Unreal PIE에서 실제 렌더링한 A/B/C 이미지로 확인했다.

## 확인 파일

- 결과 및 반영 해시: `Saved/Stage2GameplayPolish_20261125/verified_delivery.json`, `publication.json`
- 변경 직전 원본 맵 및 소스 백업: `Saved/Stage2GameplayPolish_20261125/BeforeOriginal`
- 실제 화면: `Saved/Stage2GameplayPolish_20261125/Screenshots/A_complete_impact.png`, `B_complete_impact.png`, `C_complete_impact.png`
- 작성·검사 스크립트 사본: `Saved/Stage2GameplayPolish_20261125/Scripts` — 이 작업의 분리된 스냅샷 환경을 대상으로 한 기록이며 일반 게임 실행용 진입점이 아니다.

이 작업 소유의 별도 에디터만 사용했다. 다른 채팅의 에디터나 Blender 프로세스를 종료하지 않았고, Git 커밋·푸시는 하지 않았다.
