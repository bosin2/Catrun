# Stage2 천구의 B안 Unreal 반영 — 2026-11-25

사용자가 승인한 낮은 받침·화려한 천구의 B안과 신비로운 청록색 발광을 원본 Catrun 프로젝트에 반영했다. 기존 천구의 액터를 교체했으며, 기존 Blender 디자인 원본과 이전 Unreal 에셋은 보존했다.

## 위치와 변경 범위

- 맵: `/Game/Maps/Stage2`, `/Game/Maps/SoundTest_Stage2`
- 액터 검색: `S2_Art_Armillary`, 충돌 액터 `S2_Art_Armillary_Collision`
- 에셋 폴더: `/Game/Environment/Stage2/ArmillaryB_20261125`
- 최종 메시: `Meshes/CentimeterNative/SK_Stage2_Armillary_B_Mystic_CM`
- 신규 패키지 19개: 메시·스켈레톤·애니메이션·충돌 메시, 재질 11개, 4K 텍스처 4개.
- 기존 패키지 변경 3개: 위 두 맵과 `/Game/UI/Minimap/T_Floorplan_Stage2`.
- 받침 지름 155cm, 높이 28cm. 전체 245×245×288.25cm, 액터 스케일 1.
- 기존 구체·세 링·변형 본 5개·96초 회전을 유지하고 금속 꽃받침, 별 장식, 청록 수정/별자리, 8초 발광 셰이더를 적용했다.

## 검증

격리 프로젝트에서 저장·재실행·실제 PIE를 수행한 후, 검증한 파일의 SHA256과 원본 프로젝트에 반영된 파일 22개의 SHA256이 동일함을 확인했다. 배포 직전 두 원본 맵과 미니맵이 작업 시작 기준 해시를 유지하는지도 검사했다.

- 실제 PIE 자동 회전: 약 4.15초 관찰, 네 회전 본 변화 확인. 루트 이동 없음.
- 96초 끝부분으로 PIE 사본만 이동한 뒤, 실제 루프가 1.38초 위치로 넘어가 계속 재생됨을 확인.
- 실제 고양이 이동 입력을 4초 가해 받침대에 멈춤을 확인. 측면 이탈/단차 상승 없음. 별도로 중앙 12방향 캡슐 검사와 주변 4개 우회 경로 검사 수행.
- 형상에 맞춘 볼록 충돌체 19개. 장식 링·사슬을 커다란 보이지 않는 상자로 막지 않는다. 받침 올라타기는 비활성화했다.
- 두 맵의 천구의 외 액터 583개/579개와 퍼즐 연결을 검사했다. 주변 길찾기 경로 연결이 유지된다.
- 미니맵을 새 충돌 형상으로 갱신하고 저장된 텍스처의 알파/가시 RGB 픽셀 일치를 확인했다.
- 실제 게임 화면 및 전체/근접 에디터 이미지 확인. 검사 조명은 임시이며 맵에 저장하지 않았다.

## 수입 과정에서 해결한 문제

FBX 수입 후 메시 경계와 재생 포즈의 단위가 달라 본체가 축소되는 문제를 발견했다. 센티미터 기준 FBX를 별도로 만들고, 수정하지 않은 원본 애니메이션의 **압축 재생 포즈**에서 회전 키를 읽어 최종 스켈레톤 기준 위치·스케일로 애니메이션 트랙을 다시 저장했다. 2,881개 키와 96초 길이를 유지했고, 저장 전 회전 범위 및 표본 쿼터니언 보존을 검사했다. 이후 새 프로세스의 PIE에서 본 중심 높이 175cm와 실제 회전을 확인했다.

최종 FBX를 다시 수입할 때도 이 후처리와 재생 검사가 필요하다. UE5.8의 SOURCE 평가가 이 경우 정지 자세를 반환하므로, SOURCE 결과만으로 회전 보존을 판정하지 않는다. 실패한 수입 후보들은 원본 프로젝트에 배포하지 않았다.

## 증거와 복구

- 실제 게임 이미지: `Saved/Stage2ArmillaryB_20261125/Gameplay_Armillary.png`
- 세부 보고서/해시: `Saved/Stage2ArmillaryB_20261125/`
- 격리 작업·원본 백업: `C:/Users/whghk/.codex/workspaces/Stage2ArmillaryB_20261125_01a20e2d/UnrealIntegration` (`OriginalBackup`)
- Blender 승인본: `C:/Users/whghk/.codex/workspaces/Stage2ArmillaryB_20261125_01a20e2d/ArmillarySphere_B_Mystic.blend`
- 최종 단위 변환 FBX: `C:/Users/whghk/.codex/workspaces/Stage2ArmillaryB_20261125_01a20e2d/UnrealExport/ScaleFix/CentimeterNative/SK_Stage2_Armillary_B_Mystic_CM.fbx`

이번 검사는 천구의 표시·애니메이션·충돌 및 주변 연결에 한정한다. 스테이지 전체 수동 클리어는 수행하지 않았다. Unreal 투명 셰이더는 Blender Cycles의 굴절과 완전히 같지는 않다. Git 커밋/푸시는 수행하지 않았다.
