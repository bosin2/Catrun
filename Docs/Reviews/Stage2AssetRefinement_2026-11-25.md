# Stage2 기존 에셋 수정 결과

상태: **완료.** Blender 수정 및 격리 Unreal 검증을 마친 동일 패키지를 본 프로젝트에 반영했다. 새 에셋 35개, 기존 두 맵과 연결된 미니맵 텍스처 1개를 갱신했다. Git 커밋·푸시는 하지 않았다.

사용자 승인: 기존 에셋 수정 기본안 진행. 중앙 구조물은 기존 크기를 유지할 필요 없이 이미 제작한 천구의로 교체.

## 수정 내용

| 대상 | 변경 | 보존 |
|---|---|---|
| 중앙 구조물 | 기존 조립 제단 10개를 기존 천구의로 교체. 원본 90%, 약 270×252×358cm | 기존 천구의 형태·5본·96초 회전·황동/반투명 남청 소재 |
| 천구의 메시 | 실제 면적 0 면 1개, 국소 면 방향, UV0 붕괴 14면 정리 | 정점 위치·웨이트·애니메이션. 기존 제작물을 활용 |
| 가고일 | 어깨·목·허벅지 연결부를 국소 정돈 | 얼굴·뿔·날개·꼬리·받침·UV·충돌·눈과 룬 소재 |
| 누름판 | 외곽 밝기 1.06, 중앙 0.74로 구분 강화 | 형상·UV·분리 구조·충돌·발광 제어 |
| 러그 3종 | 배치 크기에 맞춰 테두리·술·직조 크기 교정, 중앙 스무딩 및 굵은 요철 반복 정리 | 남청 문양·원래 염료 변화·위치·회전·바닥 점유 면적 |

책장, 건축 석재 및 금속은 기존 팔레트와 엔진 재질 연결을 대조했다. 수정이 필요한 결함 근거가 없는 부분은 유지했다. 신규 장식을 증설하지 않았다.

## 납품 위치

- Unreal 새 에셋: `/Game/Environment/Stage2/Refinement_20261125`
- 적용 레벨: `/Game/Maps/Stage2`, `/Game/Maps/SoundTest_Stage2`
- 중앙 액터 검색: `S2_Art_Armillary`
- Blender: `Production/Armillary/ArmillarySphere_Refined.blend`, `Production/Plate/PressurePlate_Refined.blend`, `Production/Gargoyle/SM_Stage2_PushStatue_Gargoyle_Refined.blend`
- 러그 최종 엔진용 Blender/FBX/텍스처: `Production/Textiles/engine_manifest_final.json`에 절대 경로 기록. 이전 `engine_manifest.json`은 중간본이므로 사용하지 않는다.

## 검증과 한계

- 원본 .blend 27개 SHA256이 최초 감사와 현재 모두 일치한다. 배치 인벤토리는 580개 StaticMeshComponent, 고유 메시 99개다. 99개 전체의 원시 토폴로지 재검사를 했다는 의미는 아니다.
- 실제 Blender QA, 같은 조명의 PBR 비교, 독립 FBX 재임포트를 실시했다. 가고일 88,406 tris, 천구의 65,251 tris. 러그 Hall/Exit/Room4는 각각 32,544 / 21,280 / 41,760 tris.
- 러그 최종 엔진 텍스처: Hall 4096², Exit 2048×4096, Room4 4096². 법선 DX와 ORM은 데이터 맵으로 임포트한다.
- 허용 경고: 장식 카드의 의도된 열린 경계, 반복 섬유·술/아랫면의 UV 중첩 등은 자동 용접하지 않았다. 항목별 이유는 `IndependentQA/final_acceptance.json`에 기록했다.
- 두 맵 각각 수정 참조 12개, 보호 대상 액터 29개, 퍼즐 연결 보존. 러그 월드 경계 유지.
- 동시 진행된 바구니 교체를 최신 원본에서 다시 가져온 후 적용했다. 수정 대상 밖 액터 571/567개의 배치·태그·정적 메시 참조 요약이 유지됐다. 바구니 천의 개별 애니메이션 기능은 이 작업에서 별도 검증하지 않았다.
- 각 맵에서 고양이 4방향 sweep 모두 통과. 갑옷 sweep 4개 중 기존 촛불에 걸리는 2개는 교체 전후 같은 촛불에 막히고, 나머지 2개는 통과한다. 새 천구의로 추가 막힘이 생기지 않았다.
- 중앙 3높이×3위치의 9개 Visibility 선검사에서 새 충돌 프록시가 차단 역할을 유지한다. 소리 전파는 별도 그리드/경로 검사로 평가했다.
- 소리 그리드 97×178, 원점·셀 크기·보행/비용 데이터 유지. 중앙 범위의 edge mask 111개가 새 형상에 맞게 변했다. 경로 6개는 모두 연결돼 있으며, 0-clearance 동서 경로는 800→750cm, 갑옷 여유 35cm 경로는 850→850cm다. 소리 규칙은 유지하지만 기하 변경에 따른 경로가 완전히 동일한 것은 아니다.
- 미니맵은 1024² 실제 메시 외곽선으로 갱신. 새 프로세스 재실행은 저장 0개였으며, 다시 추출한 알파와 보이는 RGB 픽셀이 원본 생성 이미지와 일치했다. 최신 바구니 통합 후에도 건축 투영이 같음을 검증했다.
- 실제 Stage2 PIE에서 4.12초 자연 재생 동안 Globe/Meridian/Ecliptic 약 15.3°, Horizon 약 31.0° 회전을 확인했다. PIE 사본만 95초로 이동시킨 뒤 실제 96초 루프 경계를 통과했고 재생이 계속됐다. 저장된 메시·스켈레톤·애니메이션 및 실제 재질 슬롯 5개를 새 프로세스에서 확인했다.
- 실제 게임 카메라 캡처 1장으로 반투명 천구·황동·청록 중심부와 화면 내 배치를 확인했다. PIE 종료 후 두 맵 해시는 변하지 않았다. SoundTest_Stage2는 저장/충돌/그리드/미니맵을 검사했으며 별도 전체 PIE 플레이를 수행한 것은 아니다.
- 실제 플레이 전체 클리어 또는 모든 플랫폼 성능 검증은 이 에셋 작업의 자동 검사로 대체하지 않는다.

## 충돌 방지 및 복구

공유 Blender MCP/UI를 조작하지 않고 별도 background 프로세스와 물리적 Unreal 사본을 사용했다. 원본 Blender/FBX/텍스처를 덮어쓰지 않는다. 최종 반영은 새 에셋 폴더, 두 맵, 연결된 미니맵 텍스처만 대상으로 한다. 다른 채팅의 원본 패키지가 변경되면 해시 검사에서 반영을 중단하도록 구현했다. 원래 패키지는 `Production/PublicationBackup`에 보관한다.

근거: `engine_import.json`, `scene_apply.json`, `IndependentQA/final_acceptance.json`, `Minimap/Artifacts`, `EngineVisuals`, `RuntimeQA/Runs`, `publication.json`.

## 화면

아래는 격리 사본의 실제 게임 카메라 캡처다. 동일 해시의 검증 패키지를 본 프로젝트에 반영했다.

![실제 게임 카메라](C:/Users/whghk/.codex/workspaces/Stage2AssetReview_20261125_01a20e2d/Production/RuntimeQA/Runs/Stage2-20261125-013048-5f4c21a7/Gameplay_Armillary.png)

전체샷은 배치 검사 목적의 임시 보조광을 사용했으며, 보조광은 맵에 저장하지 않았다.

![Unreal 전체샷](C:/Users/whghk/.codex/workspaces/Stage2AssetReview_20261125_01a20e2d/Production/EngineVisuals/Chapter_Stage2_Overall_Inspection.png)
