# 책장 가림·포털 시네마틱 수정

기준 main `5826054`. 사용자 확인: 언리얼만 켜 둔 상태. 사용자 에디터의 MCP로 적용·검증했고 OS 마우스/키보드는 조작하지 않았다. 이번 범위는 로컬 수정이며 푸시하지 않는다.

## 원인과 변경

- Stage2의 책장은 벽과 같은 가림 함수를 쓰면서도 점무늬 masked 렌더링이었다. SoundTest_Stage2는 원래 불투명 재질이었다. 두 맵의 여섯 책장을 원래 `MF_WallOcclusion`과 벽의 설정·1→0.12 연속 투명도로 통일했다.
- 여러 면이 겹치는 책장은 단순한 반투명 변환만으로 내부 면이 중첩되고 고양이를 가렸다. 가림 중에는 CustomDepth의 가장 앞면만 블렌딩한다. 가림 해제 시 원래 표면 출력을 쓰는 깊이 기록 재질로 돌아가 목재 조명·그림자와 바닥 표시의 가림을 유지한다. 원래 책장의 위치·형태·충돌·소리 태그는 보존한다.
- 각 맵에 여섯 깊이 전용 복제와 여섯 반투명 표시 복제를 부착한다. 충돌·내비게이션·오버랩·중복 그림자·간접광 기여가 없다. 새 C++ Tick이나 전역 렌더 설정 변경은 없다. CustomDepth가 이미 활성화된 실제 프로젝트 설정을 사용한다.
- 출발은 짧은 반대축 컷을 없애고 4컷으로 연결했다. 앞면 카메라 전환 위치·렌즈를 맞추고 점프 준비와 비행을 같은 카메라로 연결했다. 출발 파란 조명 정점36500→8000(기존 unitless), 보조광1750→320lm, 카메라 bloom0.42→0.15. 원래 포털 발광 재질은 그대로다.
- 도착은 얼굴 구도를 넓혀 고양이가 동상에 가려지지 않게 했다. 동상→발판→철창은 고양이 눈높이 시점을 유지한다. 마지막 복귀는 약131도/1.67초에서53.41도/3초로 줄이고 정확한 플레이 카메라 위치·폭에 연결했다. 보조광1400/1600/1900→340/425/500lm이며 필요한 장면에 맞춰 켜지고 복귀 끝에는0이다. 맵 전체 노출은 바꾸지 않는다.
- 전체 길이 출발10.4초/도착12.6초와 문·포털·애니메이션 바인딩, 기존 전환/감지/저장/제목·입력 정책은 유지한다.

## 재작성 경로

- `Scripts/GameplayRepair/repair_stage2_bookshelf_front_layer_20261124.py`: 현재 열린 Stage2 또는 SoundTest_Stage2에서 audit/apply/cold. 공통 검사 함수는 `repair_stage2_bookshelf_fade_20261124.py`.
- 책장 최종 재질4개: `/Game/Environment/Shared/Castle/Architecture/OcclusionRepairs/BookshelfWallFade/`, 검색어 `WallFade_Clear`, `WallFade_FrontLayerHandoff`.
- `Scripts/GameplayRepair/repair_cinematic_readability_20261124.py`: 두 기존 시퀀스의 카메라·광원만 갱신한다. 조정값은 `stage1_departure_shots.py`, `stage2_arrival_revision.py`.
- 기존 시네마틱 렌더/런타임 검사 도구도 새 컷 범위·렌즈·광원 곡선을 읽도록 갱신했다.

## 검증과 한계

- 실제 Stage1 출구 접근 fixture 후 네이티브 시퀀스→Stage2 로드→도착→플레이 카메라·입력 복귀 통과. `Saved/VisualRepair20261124/CinematicsPIE/final2-20261124-225827-083052/report.json`: 16장, success=true, 설정/dirty 복구. 첫 위치만 배치했으며 전체 스테이지 손플레이는 아니다.
- 실제 화면 비교에서 검은 털과 얼굴 구분을 회복했다. 도착 마지막 카메라의 샘플 최대 yaw 속도는 약113.2→26.4도/초로 감소했다. 비활성 창에서 샘플 간격이 약10시퀀스 프레임이므로 모든 렌더 프레임의 무결점을 보장하는 검사는 아니다.
- 최종 `portal_fade` 이미지는 페이드 직전 포털 프레임이며 완전 검은 종료 화면의 증거로 사용하지 않는다. 기존 fade 트랙 보존과 실제 맵 전환 완료를 별도로 확인했다. 이번 캡처는 제목 위젯 상태를 기록하지 않는다.
- 단순 alpha, blue-noise, clear-depth 없는 front-layer 실험은 최종본에서 제외했다. 이 작업에서 만든 사용되지 않는 시험 재질6개는 참조 검증 후 Saved/VisualRepair20261124/ArchivedTrials에 보관하고 Content에서 정리했다.
- 책장 중앙/끝/가림 해제의 두 맵 화면 검증 완료. 초기 진단 하네스의 `Visibility`/`Custom`을 프로파일로 조회하던 경고는 채널과 실제 캡슐 응답 검사로 수정하고 최종 기록을 다시 수집했다. 한 번의 하네스 enum 조회 실패도 기록을 보존하고 실제 노출된 `CollisionResponseType.ECR_BLOCK`으로 교정했다. 게임 충돌 로직은 수정하지 않았다.
- C++·게임플레이 BP는 바꾸지 않았으며 앞선 병합의 자동화140개 결과를 이번 자산 수정의 재실행 결과로 사용하지 않는다.

## 최종 확인

- `BookshelfPIE/final3-20261124-230818-528777/report.json`, `BookshelfPIE/mirror3-20261124-230742-104086/report.json`: 각3장, success=true. 중앙·끝은 Visibility6개 광선 모두 책장을 지나고 가림 해제 위치는0개. 바닥 배치는 실제 Pawn↔WorldStatic 양방향 Block 검사를 통과했다.
- `BookshelfBoundaryPIE/final-20261124-230850-850580/report.json`: 시작 위치만 배치한 뒤 실제 CharacterMovement 입력으로 통로를 왕복했다.31개 이동 표본/4장, success=true. 가림 진입/최대/복원 상태에서 고양이 식별과 책장 외형 확인. 투명도는 CPU 추정으로 프레임을 정했으며 GPU 값을 직접 읽은 검사가 아니다.
- 제한: 반투명 전환이 막 시작해 거의 불투명한 순간에는 바닥의 파란 갑옷 범위선이 비쳐 보일 수 있다. 완전히 가림이 해제되면 깊이·그림자와 범위선 가림이 복원된다. 샘플에서 책장 전체의 두드러진 밝기 튐은 관찰하지 않았다. 모든 프레임에서 범위선 관통이 없다고 주장하지 않는다.
- 저장 후 재로드 검사: Stage2 `BookshelfFrontLayer/Stage2-cold-20261124-230809-849216`, 미러 `SoundTest_Stage2-cold-20261124-230947-527804`. 두 맵 재적용도 requires_update/saved=[]이며 cinematic apply도 saved=[]다. 현재 에디터에서 재로드한 검사이고 별도 새 프로세스 부팅 검사는 아니다.
- 변경 Python7개 AST 통과, `git diff --check` 통과. 새 재질의 컴파일 실패는 관찰되지 않았다. 별도 리뷰 에이전트의 소스·실제 이미지 검토는 `Saved/VisualRepair20261124/final-review.md`에 기록했다.
- 원래 MainMenu/PIE종료/dirty0으로 복귀하고 사용자 에디터를 켜뒀다. FPS·백그라운드 설정과 원래 `catrun.NoArmorCapture=1`을 복원했다. 기존 저장·게임설정은 바이트 불변, 테스트로 변경된 에디터 사용자 설정은 백업 복원 후 SHA256 일치 확인. `final-editor-state.json`, `restored-user-state.json` 참조.

위 상대 검사 경로의 공통 루트는 `Saved/VisualRepair20261124/`이다. 원래 전파·적 감지·퍼즐·저장 시스템과 기존 미게시 작업은 보존했다.
