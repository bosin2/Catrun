# Stage3 재질·조명 수정 검증 (2026-11-25)

Unreal의 Stage3 전용 부모 18개와 Material Instance 24개를 생성해 716슬롯에 적용했다.
Blender 메시, Stage3 구조·충돌·게임플레이 속성은 변경하지 않았다.
카메라는 앞선 요청대로 yaw -135°에서 45°로 반전했으며, 아래 전후 비교는 둘 다 45°다.

## 최종 Base Color

ColorTint는 목표 sRGB를 IEC 공식으로 디코딩한 **Linear RGB**, Brightness는 1이다.
최종 식은 `원본 BaseColor / 원본 Linear RGB 평균 × ColorTint × Brightness`다.
대표색은 원본 mip0 전체 텍셀의 선형 RGB 평균이며, 텍스처의 밝고 어두운 무늬까지
모두 같은 RGB로 평탄화하는 방식이 아니다. 원본 텍스처/UV/Normal/ORM과 가림 처리를 보존했다.
화면의 조명·톤매핑 결과는 이 Base Color 수치와 다르다.

| 재질 | 목표 sRGB (0–255) | 실제 GPU 최대 채널 오차 |
|---|---|---:|
| 벽 | 101, 97, 95 | 0.31 |
| 기둥 | 119, 115, 109 | 0.52 |
| 바닥 | 150, 146, 139 | 0.59 |
| 바닥 마름모 | 112, 108, 102 | 0.76 |
| 성문 홀 장식 석재 | 81, 77, 75 | 0.20 |
| 흑철 | 52, 50, 54 | 0.97 |
| 황동 | 150, 134, 107 | 1.15 |
| 군기 | 101, 49, 62 | 0.58 |
| 목재 | 89, 72, 61 | 0.19 |
| 카펫 | 73, 67, 74 | 1.21 |

GPU 수치는 조명·노출 전 GBuffer BaseColor를 256×256 UV 평면에서 RGBA16F로 읽어
선형 평균 후 sRGB로 변환했다. 원본 mip0 계산과 GPU 압축·밉·GBuffer 양자화는 구분한다.
저장본의 24개 인스턴스를 모두 검사했으며 허용 오차는 2.5/255다.
석재는 GPU에서도 질감 변화가 확인된다. 흑철 5종은 BaseColor 표본의 미세 편차가 0이어서
처음의 일괄 질감 검사에서 표시됐다. 변경하지 않은 원본 흑철과 보정본을 256·1024 해상도로
직접 비교하니 모두 같은 특성이었다. 색 보정으로 새로 발생한 손실은 아니며, 원시 검사
표시를 증거에 그대로 남겼다. 흑철의 원래 BaseColor 무늬가 화면에서 보인다고 주장하지 않는다.

## 조명과 실제 카메라

키/필/스카이 강도를 1.4/1.7/2.0에서 0.45/0.14/0.35로 변경했다.
스카이는 중립 회색 큐브맵, 보조등은 220/500cd에서 18/40cd, 노출은 수동·보정 0이다.
물리 카메라 노출은 끄고 광원의 위치·색·반경은 유지했다.

입구·로비·전시방·창고·제단실·성문 홀에서 실제 소유된 플레이 카메라로 촬영했다.
고양이 위치와 카메라 각도는 동일하고, 카메라 위치는 추적·렌더 타이밍에 따라
최대 4.57cm 차이가 있다. NPC 정지 시점의 포즈·시야 표시도 소폭 다를 수 있다.
비교를 위해 별도 PIE에서 고양이 위치를 고정하고 NPC 틱을 정지했다. 패키지는 저장하지 않았으며,
이 촬영 자체는 수동 전체 플레이 완료 검사가 아니다. 셰이더 컴파일 완료 후 촬영한 최종본이다.
추가로 시야 표시 밖의 성문 홀 카펫과 가림 없는 로비를 확인했다. 고양이의 귀·꼬리·윤곽과
초록 눈은 구분된다. 가장 어두운 카펫 위에서는 몸·얼굴 내부 디테일의 대비가 낮다.

[전후 화면 6곳 비교](comparison.html) · [수치와 검사 증거](evidence.json)

## 보존 검사와 동시 작업

452개 액터의 변환·메시·컴포넌트·충돌이 동일하다. 전체 T3D를 비교해 정확한 재질
슬롯 및 허용된 조명·노출 필드를 제외한 게임플레이 속성 차이가 없음을 확인했다.
원본 그래프와 실제 1,095슬롯 검사 85건, 독립 색상 계산 172건을 통과했다.
379슬롯은 지정하지 않은 재질(모르타르·강철·양초·수호상 등)이라 원본을 유지했다.

수정된 저장 맵의 DX12 PIE 회귀검사 53건도 통과했다. 실제 순찰·타이머를 관찰한 뒤
위치를 제어하는 테스트 조건에서 석상 밀기, D1/D2, 장치 3개, 고양이 당기기 애니메이션,
중단·일시정지·입력 복구 및 마지막 문을 걸어 통과하는 완료 판정을 검사했다.
수동 전체 플레이나 난이도 평가로 주장하지 않는다.

동시에 진행된 바구니 채팅에서 다음 파일이 변경되어 전체 작업 폴더의 보존 해시 검사는
이 경로들을 별도 차이로 기록했다. 이 Stage3 수정은 해당 파일을 쓰거나 커밋에 포함하지 않는다.
Stage3 FinalGuard 원본과 나머지 보호 대상은 비교 기준과 같다.

- Content/Environment/Shared/Castle/Props/Hiding/BasketVariants20261125/Shared/Materials/M_Cloth_Stage1.uasset
- Content/Environment/Shared/Castle/Props/Hiding/BasketVariants20261125/Stage1/Meshes/SK_HideBasket_Stage1_Cloth.uasset
- Content/Environment/Shared/Castle/Props/Hiding/BasketVariants20261125/Stage2/Meshes/SK_HideBasket_Stage2_Cloth.uasset
- Content/Environment/Shared/Castle/Props/Hiding/BasketVariants20261125/Stage3/Meshes/SK_HideBasket_Stage3_Cloth.uasset
- Source/Catrun/Interaction/BasketExitMath.h
- Source/Catrun/Interaction/CatrunBasketInteractionComponent.cpp
- Source/Catrun/Interaction/Tests/BasketExitTests.cpp

## 파일 위치와 재실행

- 레벨: `/Game/Maps/Stage3`
- 새 재질: `/Game/Environment/Stage3/ColorCorrection_20261125/Instances`
- 부모: 같은 폴더의 `Parents`
- 검색어: `MI_CC_`
- 실행 지침: `Scripts/Stage3/ColorCorrection/Materials/README.md`

기존 `finalize_map.py`는 과거 조명과 장치 재질을 덮어쓰므로 수정된 레벨에 다시 실행하지 않는다.
검사 중 발견한 UE5.8 setter의 false 반환은 실제 값 재조회로 검증하도록 보완했고,
컴파일 도중의 임시 체크무늬 캡처는 최종 화면에서 제외했다.
