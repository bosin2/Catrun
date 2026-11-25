# Stage2 메인 로비 촛불 우회 보완 — 2026-11-25

원인: 로비 촛불의 감지 자체는 작동하지만, 기존 방향 65° / -115°와 ±15° 회전 범위 조합 때문에 벽면 경로에 노출되는 시간이 매우 짧았다. 수정 전 실제 PIE에서 서쪽 벽을 따라 정상 이동 입력으로 걸어 출구 쪽까지 도달해도 감지되지 않는 경로를 재현했다. 모든 위상에서 영구적으로 보이지 않는다는 의미는 아니다.

변경: Stage2와 SoundTest_Stage2에서 Candle_01 yaw 65°→90°, Candle_02 yaw -115°→-90°만 수정했다. 위치, 시야 30°, 거리 500cm, 회전 ±15°, 속도 13°/s, 끝점 대기 0.6초, 접촉 감지 45cm 및 전역 설정은 그대로 유지했다.

다른 채팅의 최신 엘리베이터/출구 변경을 먼저 새로 반영한 격리 사본에서 재검증했다. 저장 후 재로드 감사에서 Stage2 나머지 807개, SoundTest_Stage2 나머지 602개 액터의 위치/회전/스케일·정적 메시·재질·콜리전 프로필·태그가 유지됐다. 소리 격자 데이터도 변경하지 않았다. 원본 맵과 DLL 해시가 검증 시점과 같을 때만 두 맵을 반영했다.

## 최종 실제 PIE 결과

| 맵 | 경로 | 결과 | 감지 시 촛불까지 수평 거리 |
|---|---|---|---|
| SoundTest_Stage2 | west_walk | detected | 511.8 cm |
| SoundTest_Stage2 | east_walk | detected | 54.0 cm |
| SoundTest_Stage2 | armillary_west_edge_observe_then_sprint | unseen | - |
| Stage2 | west_walk | detected | 511.1 cm |
| Stage2 | east_walk | detected | 54.2 cm |
| Stage2 | armillary_west_edge_observe_then_sprint | unseen | - |

벽면 두 경로에서 native OnCatSpotted/IsTrackingCat와 표식 구체·빛의 실제 가시성을 확인했다. 감지는 45cm 접촉 범위 밖에서 발생했다. 천구의 서쪽 가장자리에서는 촛불의 실제 시야 머티리얼 각도가 95°를 지나는 순간을 기다렸다가 실제 IA_Run 입력으로 달려 통과할 수 있었다. 시간/AI/감지/속도를 변경하지 않았다.

검사 방법: 각 케이스마다 새 PIE를 시작하고 메인 로비 입구의 지면 위에 고양이만 한 번 배치한 뒤, 실제 CharacterMovement 이동과 Enhanced Input 달리기로 진행했다. 경로의 캡슐 충돌과 바닥 지지를 먼저 검사했다. 감지 케이스는 표식 확인 직후 종료했다. 두 맵 각 3개 경로 총 6개 최종 케이스가 통과했고, PIE 종료 및 테스트 전후 저장 맵 해시 불변을 확인했다.

범위: NullRHI 실제 게임 로직 검사이며 화면 렌더링 검사나 스테이지 전체 수동 완주 검사는 아니다. 모든 가능한 경로/시작 회전 위상을 전수검사한 결과도 아니다. 반복 가능한 벽면 우회 보완과 정상 타이밍 회피를 확인한 것이다.

근거: `Saved/Stage2LobbyCandle_20261125/publication.json`, `audit_saved.json`, `RuntimeQA/Runs/*/report.json`. 수정 전/중간 진단 실패 기록도 그대로 보존했다. 원본 백업은 `FinalOriginalBackup`에 있다. Git 커밋/푸시는 수행하지 않았다.
