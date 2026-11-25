# BlackCat — 각진 로우폴리 수정본

최종 파일: `SK_BlackCat_UniformLowPoly.blend`

## 변경 내용

- 얼굴의 인상, 검정/초록/빨강/금색 배색, 귀와 꼬리는 기존 모델을 바탕으로 유지했습니다.
- 몸통과 네 다리가 연결되는 면 구조를 다시 만들었습니다. 아래쪽만 촘촘하던 구성을 줄이고 다리 전체를 큼직한 삼각 면과 Flat Shading으로 맞췄습니다.
- 다리 단면을 유지하는 보조 본, 몸을 낮출 때 어깨가 몸통 안으로 들어가는 것을 줄이는 보정, 정규화된 웨이트를 적용했습니다.
- FK 뒷무릎 컨트롤의 95도 이후 굽힘은 발목 관절에도 분배합니다. 입력 범위를 자르는 대신 한 관절에 과도한 굽힘이 몰리지 않게 했습니다. IK에서는 이 FK 보정을 적용하지 않습니다.
- UV를 다시 배치했습니다. 본체 5,214 triangles, 방울 내부 부품 80 triangles입니다.

## 사용

파일은 `V2_AUTHORING_TEMPLATE`의 기본 자세로 열립니다. Armature의 `controls_enabled=1`이 현재 컨트롤 방식입니다.

- `CTRL_body`: 몸 위치.
- `CTRL_spine`: bend / side_bend / twist.
- `CTRL_IK_F_L/R`, `CTRL_IK_H_L/R`: 네 발의 IK 목표. 각 컨트롤의 `ik=1`은 IK, `ik=0`은 FK입니다. 전환 전 자세를 맞춰야 합니다.
- `CTRL_upperarm`, `CTRL_forearm`, `CTRL_thigh`, `CTRL_shin`, `CTRL_hock`, `CTRL_paw_*`: FK 회전.
- `CTRL_face`: 눈 깜빡임과 시선. `CTRL_jaw`, `CTRL_tongue`: 입과 혀.
- `V2_TEST_Body`, `V2_TEST_PawReach`, `V2_TEST_Curl`은 관절 검사용 액션이며 게임용 완성 애니메이션이 아닙니다.

## 검증 범위

- 관절을 하나씩 조작한 358개 FK 입력 자세: 검사한 다리 내부의 관통/양의 면적 겹침 0, 면적이 거의 0인 다리 삼각형 0.
- 앞다리 굽힘과 뒷무릎 입력 -90~120도, 발/발목 입력 -60~90도를 5도 간격으로 검사했습니다. 깊은 뒷무릎 입력은 위의 관절 분배 보정이 적용된 결과입니다.
- 몸 낮추기+비틀기, 앞발 들기, 몸 말기: 각각 91프레임, 총 273프레임에서 새로 만든 하부 몸통과 다리의 면 관통/겹침 0.
- 기본 메쉬 QA 통과: 비정상 면 방향, 면적 0 면, 미할당 웨이트, 4개 초과 본 영향, 비매니폴드 모서리 없음.
- 회색 확대, 재질 렌더, 와이어 화면을 확인했습니다. 이 검증은 임의의 모든 관절 조합이나 모든 기존 애니메이션의 정상 동작을 보장하지 않습니다.

남겨 둔 QA 경고는 입 경계의 분리된 중복 좌표 8개, 기본 자세에서 얼굴 안에 숨겨지는 눈꺼풀 관련 내부 면 2개, 방울 안에 있어 지면에 닿지 않는 방울 내부 부품입니다. 목 연결부는 유지한 머리 안쪽으로 들어가는 구조이며 이 내부 연결은 노출된 몸통/다리 표면 검사와 구분합니다.

## 적용 상태

Blender 소스 수정본입니다. 원본 `Desktop/CastleKit/BlackCat/Final/SK_BlackCat_Final.blend`는 변경하지 않았습니다. Unreal 에셋 교체나 FBX 재임포트는 하지 않았습니다.

본의 바인드 자세와 피부 구조가 바뀌었으므로 기존 액션을 그대로 호환된다고 간주하면 안 됩니다. Unreal로 내보낼 때는 보조 본의 제약 조건과 얼굴 드라이버를 베이크하고, 메시/스켈레톤/애니메이션을 함께 재검증해야 합니다. Blender의 볼륨 유지 옵션만 켜서 해결한 모델은 아닙니다.

실제 렌더: `Previews/uniform_facets_review.png`, `Previews/uniform_motion_review.gif`, `Previews/gray_shin_L_120.png`.
검사 데이터: `QA/joint_surface_scan.json`, `QA/motion_surface.json`, `QA/asset_qa_v2.json`.
