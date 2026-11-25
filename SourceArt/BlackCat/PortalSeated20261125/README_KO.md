# BlackCat 앉아서 포탈 탐색 — 2026-11-25 수정본

최신 사용자 지시인 **걷기 → 앉기 → 귀·고개 갸웃 → 앞발로 수직 포탈 접촉 → 엉덩이를 뒤로 빼고 두 번 흔들기 → 압축 → 도약**으로 다시 제작했습니다. 실제 고양이의 해부학을 그대로 재현하는 대신 기존 큰 얼굴과 각진 스타일, 동작이 읽히는 실루엣을 우선했습니다. 이전 `PortalEntry20261125`의 서서 바닥을 찍는 동작은 이번 요구에 맞는 제작본이 아닙니다.

## 열어 볼 파일

- `Previews/PortalSeated_30fps.mp4`: 30fps, 약 9.77초. 걷기부터 도약까지 Blender에서 렌더한 연속 미리보기입니다.
- `SC_BlackCat_PortalReview.blend`: 위 영상의 실제 재생 가능한 전체 씬. 1–293프레임, 카메라·기준 포탈·접촉 표시 포함.
- `SK_BlackCat_SeatedPortal_Review.blend`: 개별 편집 가능한 액션과 수정 메시. 미리보기용 바닥·포탈을 제외한 작업본.
- `FBX/`: 별도 신규 스켈레탈 메시 1개와 애니메이션 5개. 기존 UE 스켈레톤에 애니메이션만 덮어쓰면 안 됩니다.
- `handoff.json`: 절대경로, 프레임, 접촉 좌표, 호환성, 검사 결과.

## 동작 구간 — 30fps, 각 액션의 로컬 프레임

| 액션 | 범위 | 주요 박자 |
|---|---:|---|
| AN_Portal_SeatedListenTouch | 1–91 | 1–19 앉기, 20–27 귀, 24–32 고개, 32–43 갸웃 유지, 46–57 앞발 뻗기, 57–64 실제 접촉, 65–79 회수·접지 |
| AN_Portal_HipsBackWiggle | 1–53 | 1–14 엉덩이 뒤로, 14–38 좌우 두 주기, 38–41 멈춤, 41–53 압축 |
| AN_Portal_SeatedTakeoff | 1–13 | 앞발을 먼저 위·앞으로, 뒷발은 9까지 접지, 10부터 이륙 |
| AN_Portal_AirReach | 1–19 | 앞발을 뻗은 공중 자세와 머리의 작은 후속 움직임 |
| AN_Portal_WalkReview | 1–121 | 기존 걷기에 새 표면용 보조본을 베이크한 검토용 4초 클립 |

접촉한 발은 왼쪽 앞발입니다. 포탈 기준면은 모델 로컬 Y=-0.105m, 발바닥 접촉 중심은 약 (0.042, -0.105, 0.068)m입니다. 좌표와 프레임은 메시의 실제 발바닥으로 검사했습니다. 게임의 포탈 크기·배치는 이 새 접촉 위치에 맞춰야 합니다.

## 메시와 호환성

몸통·다리는 632개 삼각형으로 구성했고 Subdivision을 추가하지 않았습니다. 얼굴·눈·귀·꼬리·목걸이·방울은 원본을 유지한 8,256삼각형이며, 합계는 8,888삼각형입니다. 원본 전체의 14,910삼각형보다 적습니다. 숨은 아래 눈꺼풀의 겹친 측면을 좌우 0.3mm 정리하고 목 뒤 52개 정점의 가중치를 최대 4개로 정규화했습니다.

원래 78개 본의 이름·계층·바인드 행렬을 유지하고 표면 보조본 34개를 추가했습니다. 총 112개 본이며 보조본도 일반 애니메이션 키로 저장됩니다. 재생에 Python 핸들러나 외부 플러그인은 필요하지 않습니다. 새 표면은 추가 본을 사용하므로 **새 메시·스켈레톤을 별도 에셋으로 함께 가져와야 합니다.** 기존 BlackCat 공유 스켈레톤과 메시, 맵, UE 시퀀스는 수정하지 않았습니다.

기존 PortalJumpIn의 공중 자세로 되돌아가면 앞발이 다시 처지는 문제가 있어 이번 수정본은 전용 이륙·공중 클립을 사용합니다. 이전 납품의 JumpIn source f18 접합 계약은 이번 버전에는 적용하지 않습니다. 개별 클립은 제자리이며, 영상의 월드 이동은 미리보기 씬에만 있습니다.

FBX는 원본 계약인 Forward -Y / Up Z, leaf bone 없음, 매 프레임 베이크, 키 단순화 0을 유지했습니다. UE 권장 import_uniform_scale=100은 이전 원본과 같은 내보내기 계약에 따른 값이며, **이 새 112본 메시의 UE 실측 검증은 아직 수행하지 않았습니다.** FBX의 Blender 재가져오기 결과는 `QA/fbx_roundtrip.json`에 있습니다.

## 검사 범위와 남은 제한

- 제작된 289개 정수 프레임에서 몸통과 네 다리 각각의 자체교차·퇴화면 0. 이는 모든 가능한 자세나 모든 부품 사이 교차를 보장하는 뜻은 아닙니다.
- 단색 검정 재질용 UV가 의도적으로 겹칩니다. 이 UV는 고유 텍스처를 굽는 용도가 아닙니다.
- 눈꺼풀 내부의 숨은 마주 보는 면 10쌍은 외형·눈꺼풀 구조 보존을 위해 유지했습니다.
- 방울 내부 추는 의도된 분리 부품으로 별도 검사했습니다. 본체와 추의 구조 검사는 각각 통과했습니다.
- 정상 속도 영상, 접촉·회수·압축·이륙의 측면/3분의 4 키포즈를 만들고 이미지로 검토했습니다. 사용자 미술 승인이나 실제 UE 출구 플레이 검증을 완료했다는 뜻은 아닙니다.

## 참고 자료와 적용한 스킬

실제 고양이 동작은 자세를 그대로 복제하지 않고 접촉·체중 이동·점프 준비의 의미를 참고했습니다.

- [앉아서 앞발을 유리에 대는 동작 — RINA TAKEI](https://www.youtube.com/watch?v=XFxOXZxUt_U)
- [가슴을 낮추고 뒤로 준비한 뒤 도약 — Tom & Mimi](https://www.youtube.com/watch?v=RbTU1OMSXzo)
- [골반 흔들기와 도약 참고](https://www.youtube.com/watch?v=gDXlnyFGjR0)
- [IndieCats Low Poly Cat — 넓은 면과 읽히는 앞발 자세](https://sketchfab.com/3d-models/low-poly-cat-f43a414c031e44a28453d74a190397d1)
- [Animated Cube Cats — 단순한 면과 실루엣 참고](https://sneznyj.itch.io/cube-cats)

외부 스킬 24종을 추가하여 Blender 관련 스킬은 총 33종입니다. 설치 목록과 경로는 `skill_inventory.json`에 있습니다. [EL4CTEO/blender-skills](https://github.com/EL4CTEO/blender-skills)의 animation, character-rigging, stylized-npr, asset-qa, export-pipelines와 [Scenario Blender 스킬](https://github.com/scenario-labs/skills/tree/main/skills/dcc/blender)의 animation, rigging, previs 지침을 읽어 적용했습니다. 외부 사람을 고용하거나 유료 생성 서비스로 바꾸지 않았습니다.
