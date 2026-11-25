# Stage3 고딕 군사 경비시설 시각 수정 보고서

2026-11-25 검토 보고서. 메커니즘 24종과 성문 러그 임포트·배치를 완료했고, 최신 저장 맵의 **네이티브 회귀 167건·불투명 그래프 검사 644건·러그 GPU 3슬롯**이 통과했다. 첫 화면 검토에서 발견한 카메라 클립 저장 결함·철창 디더·도크 조명을 수정했다. `final_fixed` **13지점 × 3모드 = 39장**과 마지막 D0 프레임 수정 후 `final_lobby` 3장을 촬영했고 Lit 화면을 검토했다. 최신 cold-load 구조 검사는 통과, 보호 해시는 동시 작업 중인 다른 맵 2개만 달랐다. 전 스테이지 수동 플레이와 아래 남은 화면·로그 문제는 완료 판정에 포함하지 않는다.

레벨은 `/Game/Maps/Stage3`(Content Browser `Content/Maps`, 검색어 `Stage3`)이다. 새 패키지는 `/Game/Environment/Stage3/GothicRevision_20261125`에 분리했다. 커밋·푸시는 하지 않는다. 기준은 [사용자 원문](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/user_brief.txt)과 [후속 지시 포함 계획](C:/Users/whghk/Catrun/Docs/Plans/2026-11-25-stage3-gothic-revision.md)이다. 최신 지시는 상호작용 장치 항상 불투명, 새 호박색 랜턴 조명 레퍼런스, 중앙 성문 러그 반영이다.

[최종 납품 기록](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/final_delivery_manifest.json)에 저장 맵 해시, 검사·화면 경로와 Git 상태를 묶었다. Stage3 맵 SHA-256은 `7805256d4a1d921694c5cbd91b22f0e9e98519db30243f4918bf2f8524df836b`로 최신 cold-load 스냅샷과 일치한다. Git 인덱스는 비어 있고 HEAD는 기존 `bdcddbcb0f88170ab801fab011144f70c505e071` 그대로다.

## 1. 수정한 주요 항목

- 벽 받침·몰딩·다발형 벽부 기둥을 추가하고 반복 밀도를 조절했다. 전시대 두 곳은 경사진 석조 받침·흑철 고정구와 방패·검·창·도끼 혼합 구성이다.
- 동상/발판의 시각 요소를 중량추·도킹 데크·결속 프레임으로 대체했다. 원래 퍼즐 액터·충돌 컴포넌트·좌표·연결을 유지하고 별도 시각 액터를 붙여, 원래 컴포넌트 bounds에 의존하는 네이티브 판정을 보존했다.
- 도크 표시용 `BP_GothicDockPresentation`은 기존 `IsPuzzleSeated`를 읽는다. 포크 19 cm 하강, 핀 7.2 cm 삽입, 사슬 단부 약 5.847 cm 이동과 열린/닫힌 사슬 전환을 표현한다. 판정용 발판은 원래 동작대로 2 cm만 내려간다. D2에는 삼중 잠금쇠와 사슬·가이드·벽 인입 연결을 추가했다.
- **E 장치 하우징·고리·핀, 도크·사슬, D0/D1/D2 프레임·문짝/철창과 최종 성문 문짝은 항상 불투명**하다. 최신 **26개 MI·190개 바인딩**, 재로드 그래프 검사 **644건 통과**다. Opacity/Mask는 상수 1이고 활성 상태/카메라 MPC 입력이 없다. BaseColor·Normal·ORM·UV와 상속 파라미터 보존도 검사했다. [불투명 검증](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/QA/interactive_visibility.json)
- 도크/바닥 겹침은 **바닥 8개 타일의 시각 마스크와 비충돌 하부 캡 2개**로 정리했다. 원래 발판 높이·변환·바닥 충돌은 유지했다. [보정 기록](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/final_visibility.json)
- 벽/기둥 가림은 픽셀별 원통 절단에서 **벽과 장식/기둥 전체 그룹 단위 마스크**로 바꿨다. 그룹 중심·크기로 결정하고 그림자 패스는 유지한다. 상호작용 장치는 이 가림과 별개다.
- Stage3 카메라 인스턴스의 yaw 45°·arm 500 cm를 유지하고 SpringArm 충돌 검사를 껐다. 최초 수동 클립 설정은 컴포넌트 재생성 후 오래된 참조에 계속 쓰여 일부 값만 저장됐다. 속성 변경마다 CameraComponent를 다시 구해 near −2000 / far 10000 cm와 자동 갱신 해제를 저장했고, [후속 독립 재로드](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/final_repairs.json)와 `RegressionFinal02`의 실제 PIE 시작 조건에서 유지됨을 확인했다. 공용 카메라 Blueprint는 변경하지 않았다. `final_fixed` 성문 화면에서 이전에 잘린 기둥 단면이 사라지고 닫힌 상단이 보이는 것을 확인했다.

기본 적용 근거는 [통합 기록](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/application.json), [시각 액터](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/visuals_report.json), [기계 연결](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/connections_report.json), [표시 Blueprint](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/presentation_report.json)다. 생성·할당 성공과 실제 실행 검증은 구분한다.

## 2. 사용한 신규 에셋 목록

`Mechanisms03_20261125`의 **메시 24종**을 `/Game/Environment/Stage3/GothicRevision_20261125/Mechanisms_35042763fe1cc5f6`에 임포트했다. 아래는 수입 자원 전체이며 모두 레벨에 사용되었다는 뜻은 아니다.

| 분류 | 메시 이름 (`SM_S3_` 접두사 공통) |
| --- | --- |
| 중량추 2종 | `GateCounterweight`, `CounterweightPressureShoe` |
| 도킹 9종 | `DockArch`, `DockCaptureFork`, `DockChainTerminal`, `DockCrossPin`, `DockFloorFrame`, `DockPressureDeck`, `DockSheave`, `DockShortChain`, `DockShortChain_OpenPose` |
| 사슬 연결 6종 | `ChainConnection_Cover`, `ChainGuide_Bracket`, `ChainWallIntake`, `MechanismChain_Curve`, `MechanismChain_Link`, `MechanismChain_Straight` |
| 잠금 3종 | `GateLock_Bolt`, `GateLock_Housing`, `GateLock_Keeper` |
| 상태 표시 2종 | `MechanismIndicator_Flag`, `MechanismIndicator_Frame` |
| 벽 도르래 2종 | `WallPulley_Mount`, `WallPulley_Wheel` |

[메커니즘 임포트 결과](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/import_report.json)는 24종 성공·오류 0건이다. 납품 문서/QA 상태 갱신으로 freeze 비교가 실패한 [이전 시도](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/import_report_attempt02_prose_drift.json)는 보존했다. reconciliation은 manifest 자산 식별·bounds·삼각 수·원본 해시와 24종 실제 자산 입력이 동일한 범위에서 수행했다. 자산 입력 변경을 무시한 판정이 아니다.

성문 러그 `SM_S3_GrandGateRug_300x900`은 `/Game/Environment/Stage3/GothicRevision_20261125/Rug_25832f4f17613e08`에 임포트했다. 실측 약 300 × 900 × 0.6 cm, UV 채널 2개, 직물/테두리/문장 슬롯 3개이며 별도 충돌 형상은 없다. [임포트](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/rug_import_report.json)와 [배치](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/rug_placement_report.json) 모두 성공, 맵 저장 완료다. 첫 UV 조회 실패는 [실패 기록](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/RugImport/attempt01_uv_subsystem.json)에 보존했다.

러그 [Blender/FBX 독립 QA](C:/Users/whghk/Desktop/CastleKit/Stage3/Rugs04_20261125/QA/FINAL_QA.md)는 형상·UV·재임포트·PBR 검사를 통과했다. 기존 Blender 소스 82개와 기계 장치 24개, **총 106개 원본 해시가 동일**하다. 소스 판정은 Unreal 최종 화면이나 사용자 미술 승인을 대신하지 않는다.

Unreal 내부 생성 자원은 `SM_S3_SlopedStoneDisplay`, `BP_GothicDockPresentation`, 메커니즘/갑옷 MI, 가림 및 상호작용 불투명 복제 재질이다. 벽부 기둥·가구·무기·군기·벽등·촛대·경계석은 기존 Stage3 `FinalGuard` 자원을 재사용했다.

## 3. 구역별 배치 요약

| 구역 | 적용한 시각 구성 |
| --- | --- |
| 입구 | 벽등 한 쌍, 받침/몰딩, 전고 기둥 제외 |
| 로비 | 벤치·장비 보관장·군기·벽등, 중앙 이동 공간 유지 |
| 하단 홀 | 벽 쪽 작전 테이블·벤치·군기, 벽등과 독립 촛대 |
| 전시방 | 경사 석재 전시대 두 곳, 혼합 무기, 방패대·군기·국소광 |
| 창고 | 기존 장애물 7개 보존, 북쪽 통로를 피해 벽 쪽 정비대 추가 |
| 중앙 복도 | 벽등 리듬·군기, 도크/잠금 연결 노출 |
| 긴 캣홀 | 소량의 벽등/건축 정리, 기존 고양이 전용 동선 유지 |
| 제단실·추가 구간 | 중량추·도크·사슬 인입 구조, 불투명 E 장치·목표 주변 벽등 |
| 상단 복도 | 간격을 둔 벽등·군기·몰딩 |
| 성문 홀·EXIT | 큰 기둥·군기·벽등·촛대, 경계석·문턱과 중앙 3 × 9 m 러그 |
| D1·D2 | 원래 게이트 구조 보존, 구동 표현과 D2 삼중 잠금쇠 |

러그는 중심 (−200, 3450, 0.2) cm, 월드 XY 범위 (−350, 3000)~(−50, 3900) cm에 `NoCollision`으로 배치했다. 겹치는 장식 축 4개만 숨기고 경계석·문턱을 유지했다. 창고 원래 장애물 7개를 전부 새 가구로 재설계했다고 주장하지 않는다.

새 충돌 가구는 로비 벤치/보관장, 하단 작전 테이블/벤치, 전시방 방패대, 창고 정비대 총 6개다. Regression01의 실제 보행 경로 8건은 통과했다. 이 표본으로 모든 자유 이동·적 시야까지 검증한 것은 아니다.

## 4. 조명·머티리얼 수정 요약

최신 호박색 랜턴 레퍼런스를 반영한 [reference_lighting.json](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/reference_lighting.json)은 `success=true`, `map_saved=true`다. 벽등 **3200 K**, 독립 촛대 2900 K, 출구 쪽 성문 홀 벽등 28/29는 각각 **약 21.45 cd**다. 주광 0.18, 보조광 **0.55**, SkyLight 0.30, 수동 노출 bias 0, Bloom 0.12로 저장했다. 이는 초기 4200/3900 K와 Tuning02 이후의 최신 값이다. 수치 저장과 최종 화면의 레퍼런스 일치 판정은 구분한다.

후속 [final_repairs](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/final_repairs.json)에서는 전시방 벽등 10의 범위를 360→600 cm, 광도를 14.3→22 cd로 조정해 기존 등불이 도크까지 닿도록 했다. 광원 위치는 유지했다. D0·D1·D2 프레임/철창과 최종 성문 문짝도 불투명 범위에 추가했다. 저장 성공과 최종 영상 확인은 구분한다.

| 역할 | 목표 BaseColor (sRGB 0–255) |
| --- | --- |
| 벽 / 기둥·몰딩 | 101/97/95 · 119/115/109 |
| 일반 바닥 / 포인트석 / 성문 장식석 | 150/146/139 · 112/108/102 · 81/77/75 |
| 흑철 / 사슬·도르래 / 낡은 황동 | 52/50/54 · 72/71/74 · 150/134/107 |
| 군기 / 목재 / 카펫·천 | 101/49/62 · 89/72/61 · 73/67/74 |

원본 텍스처의 선형색 평균으로 정규화한 뒤 목표 선형색과 밝기를 적용한다. 중량추 암석은 납품 `dark_stone` 목표 89/86/82를 사용한다. Stage3 갑옷 6개의 steel 슬롯에는 72/71/74 전용 MI를 적용했다. 러그 바탕은 73/67/74, 테두리·문장은 150/134/107이며 황동색이어도 비금속 직물이다. 러그 소스 금속 채널은 모든 픽셀 0이다.

[최초 GPU 검사](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/GPU/report.json)는 새 메커니즘 MI 5개·갑옷 MI 1개·가림 대표 6개, **12건 통과**다. 256 × 256 UV 평면을 `SCS_BASE_COLOR → RGBA16F`로 렌더한 선형 평균을 sRGB로 변환했다. 채널 허용오차 2.5/255, 최대 실측 오차 1.208794/255 미만이다. 후속 [GPU_Visibility2](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/GPU_Visibility2/report.json)도 **12건 통과**했다. 월드 MPC 및 액터 집합 복원도 확인했다. 이는 대표 재질 검사이며 26개 불투명 MI 각각의 전 상태 GPU 시험을 뜻하지 않는다.

BaseColor·Normal·ORM 연결과 색상/텍스처 상속은 그래프 검사로 확인했다. 분산 0인 철재를 일괄 실패시키지 않았다. 이전 원본 철재도 같은 GPU 양자화 한계를 보였기 때문이다. 별도 [러그 GPU 검사](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/GPU_Rug/report.json)는 직물·테두리·문장 **3건 모두 통과**, 최대 실측 오차 **0.733696/255**다. MPC와 원래 액터 집합 복원도 확인했다. 위 12건과 별도 실행이며 Lit 조명 일치 판정을 대신하지 않는다.

실제 플레이 카메라의 수정 전후 비교다. 같은 이름의 고양이 표본 위치를 사용했으며, 카메라 충돌·클립 보정과 장식 변경도 포함하므로 조명만 바꾼 픽셀 대조 실험은 아니다.

| 구역 | 수정 전 | 수정 후 | 화면에서 확인한 변화 |
| --- | --- | --- | --- |
| 성문 홀 | [이전 화면](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/before/GateHall_Lit.png) | [현재 화면](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/final_fixed/GateHall_Lit.png) | 차가운 회색 전역 톤에서 따뜻한 등불·중성 주변광으로 변경, 러그 테두리·문장 추가, 잘린 기둥 상단 복원 |
| 성문 출구 후속 진단 | [이전 화면](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/before/GateHallExit_Lit.png) | [가장 최근 Lit](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/pillar_diagnostic/GateHallExit_Lit.png) | 정상 그림자 상태에서 러그·기둥 확인. 앞선 촬영의 밝고 각진 띠는 이번에 재현되지 않았으며 경위는 아래에 보존 |
| 제단실 | [이전 화면](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/before/Altar_Lit.png) | [현재 화면](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/final_fixed/Altar_Lit.png) | 벽등과 재질 대비 강화, E 하우징 불투명 유지, 중량추·도크 구조 노출 |
| 전시방 도크 | [이전 화면](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/before/Weight1_Lit.png) | [현재 화면](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/final_fixed/Weight1_Lit.png) | 단순 검은 발판에서 프레임·사슬·데크 구조로 변경, 기존 벽등이 도크까지 닿도록 범위 조정 |

## 5. 아직 미확인인 항목과 검증 범위

| 검사 | 현재 상태와 해석 |
| --- | --- |
| 메커니즘 24종 / 러그 임포트·배치 | 성공. reconciliation과 원래 실패 기록 보존 |
| 상호작용 장치 불투명 | 최신 재로드 그래프 26 MI·190 바인딩·644건 통과. 중간 검사에서 누락된 D0 프레임 5바인딩을 발견해 추가 후 재검사 |
| GPU 대표 재질 | 최초 12건·GPU_Visibility2 12건·러그 3슬롯 통과 |
| 이전 색상 수정 회귀 53건 | [이전 단계 기록](C:/Users/whghk/Catrun/Saved/Stage3MaterialCorrection20261125/regression_final/report.json). 이번 전면 수정의 최종 회귀로 재사용하지 않음 |
| 이번 Regression01 | [79건 통과·실패 0](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/Regression/report.json). 네이티브 53 + 실제 보행 8 + 도크 닫힘 18. 실행 당시 저장 상태의 결과 |
| 확장 도킹 회귀 | [325건 통과](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/RegressionDock/20261125-120046/report.json). 실제 수행 범위는 아래 설명 |
| 중간 화면 | `after` 36장, `reference_review01` 12장. 최신 조명·수동 클립·러그가 모두 반영된 최종 자료가 아님 |
| 최신 13지점 × 3모드 | [final_fixed](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/final_fixed/report.json) 39장 완료·Lit 13장 검토. 마지막 D0 프레임 수정 후 [final_lobby](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/final_lobby/report.json) 3장 재촬영·Lit 재검토. 이전 `final`은 수정 전 증거로 보존 |
| 성문 기둥 후속 진단 | `pillar_diagnostic`의 Lit/NoShadows/Roughness/Metallic/WorldNormal 5장 검토. 정상 그림자 Lit부터 앞선 밝은 띠가 재현되지 않음. 맵·재질 저장 없음 |
| 마지막 네이티브 회귀 | [RegressionFinal03](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/RegressionFinal03/report.json) **167건 통과·실패 0**. 저장 맵의 실제 D3D12 PIE, 카메라 유지·러그 비충돌·상호작용 전/중/후 불투명·원래 퍼즐·보행·최종 출구 검사 포함 |
| 구조·충돌·참조·원본 해시 | 최신 [final_v4 비교](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/QA/final_v4/comparison.json) 10/11 통과. 구조·퍼즐·참조·기존 충돌·적 경로 검사 통과, 두 다른 맵 해시 차이로 원시 `success=false` 유지 |
| 사용자 미술 승인 / 전 스테이지 수동 플레이 | 미확인. **Stage1 → Stage2 → Stage3 전체 수동 플레이를 다시 수행하지 않았다.** |

확장 도킹 검사는 양쪽 도크의 실제 전환 도중 `0 < Alpha < 1`에서 네이티브 `ResetStatue`를 호출해 열린 상태 복귀를 확인했다. 네이티브 `TryPushStatue`로 반복 재안착·초기화하며 좌표 누적 없음, 원래 bounds 보존, 발판 2 cm 하강 한 번, 고정 프레임/아치/도르래, 사슬 한 개 표시와 시각 액터 비충돌을 검사했다. 이미 완료된 **실제 네이티브 퍼즐에 새 presenter를 생성한 뒤 첫 tick의 닫힌 표시**도 검증했다. 이는 디스크 체크포인트 복원이 아니며 `disk_checkpoint_restore_tested=false`다.

마지막 회귀의 실패 기록도 보존했다. [첫 시도](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/RegressionFinal/report.json)는 카메라 유지 조건을 통과하지 못해 저장 참조 처리를 수정했다. [두 번째 시도](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/RegressionFinal02/report.json)는 Device1 애니메이션 표본이 정확히 10개여서 `>10` 조건에 실패했다. 동일 조건을 완화하지 않고 D3D12 회귀를 단독 재실행한 세 번째 시도는 통과했다. 두 번째 실패의 정확한 원인을 자원 부족으로 확정하지는 않는다.

`final_fixed` Lit 13장과 `final_lobby` Lit을 실제 크기로 검토했다. 따뜻한 벽등 주변광과 중성 바닥·그림자의 분리가 보이며 고양이 실루엣은 열린 바닥 위에서 구분된다. 러그의 테두리·문장이 성문 중앙 축에 보이고 명백한 바닥 겹침은 관찰되지 않았다. Altar의 E 하우징과 AltarAnnex의 철창·프레임이 불투명하며 이전 철창 디더 점무늬는 보이지 않는다. Weight1 데크의 이전 바닥 간섭이 해소됐고 기존 등불 범위 확대로 데크 주변과 가장자리 대비가 개선됐다. 성문 기둥은 닫힌 상단을 보이며 잘린 원통 단면은 사라졌다. 셰이더 미완료 체크무늬는 검토한 Lit 화면에 없다. [후속 화면 검토 기록](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/QA/visual_review_final_fixed_20261125.json)

남은 화면 한계도 있다. 전고가 모두 보이는 성문 전경 기둥은 러그 일부를 가린다. 성문 두 표본의 고양이는 보이지만, AltarAnnex 표본에서는 불투명 철창 뒤 고양이 대부분이 가려진다. Weight1의 검은 데크·사슬 세부 대비는 여전히 낮고 표본 자세에서는 고양이 몸통과 앞쪽 다리가 겹친다. 성문 출구 왼쪽 위 조명 풀은 참고 사진보다 밝고 노란 편이며, 입구·상단 복도에서는 벽 그룹 가림으로 넓은 검은 외부 공간이 드러난다. 참고 사진과 전체 구성이 일치했다거나 모든 시각 결함을 제거했다는 판정은 아니다.

`final_fixed` 성문 Lit 오른쪽 기둥 아래쪽의 밝고 각진 띠는 별도 [실제 카메라 5모드 진단](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/pillar_diagnostic/report.json)으로 추적했다. 새 [Lit 화면](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/pillar_diagnostic/GateHallExit_Lit.png)과 그림자를 끈 화면에서 재현되지 않았다. Roughness·WorldNormal에 대응하는 띠가 없고 기둥 Metallic은 0이다. 이 표본에서 고정된 텍스처/노멀 결함 근거는 찾지 못했으며, 그림자 유무를 바꾸기 전 Lit부터 정상이라 그림자 원인으로 확정하지 않았다. 일시적 렌더 이력 문제는 가능성일 뿐이며 원래 결함 화면은 보존했다. 진단 실행은 맵·머티리얼을 저장하지 않았다.

자유 이동·적 시야/추격·창고 LOS의 전수 수동 검토, 촛불 적 밀랍 색 요구 충족 여부와 사용자 미술 승인은 아직 확인하지 않았다. 네이티브 안내의 동상/발판 용어는 유지되어 외형과 문구가 다를 수 있다.

실행 로그의 진단도 남겼다. [단독 회귀 실행 로그](C:/Users/whghk/Catrun/Saved/Stage3Integration20261125/GothicFinalRegression03.log)에 엔진 초기화 전 `LogAutomationTest: Error: Condition failed`가 15건 있다. 별도 [상세 진단 실행](C:/Users/whghk/Catrun/Saved/Stage3Integration20261125/GothicEngineSmokeDiagnostics.log:2338)으로 `FUnifiedErrorTest_CreateErrorMessage` 7건, `FUnifiedErrorTest_CreateErrorMessageWithContext` 4건, `FStructuredLogFormatTest` 4건임을 확인했다. 모두 UE Core 시작 `RunSmokeTests`의 메시지/포맷 검사이며 Catrun 회귀 assertion은 아니다. UnifiedError 11건은 로컬 소스의 영문 기대값·실제 지역화 문자열(`NSLOCTEXT`)·실행 중 한국어 출력이 일치해 로케일 차이 설명을 강하게 뒷받침한다. StructuredLogFormat 4건도 영문 기대값과 `LOCTEXT` 비교가 있으나 개별 실패 하위 사례는 확정하지 못했다. 엔진이나 전역 언어 설정은 변경하지 않았다. 별도로 기존 에디터가 사용하는 `127.0.0.1:8000`에 보조 실행의 MCP listener가 바인딩하지 못한 로그도 있다. 따라서 게임 회귀 통과와 별개로 **전체 로그 오류 0건**이라고 주장하지 않는다.

보호 해시 동시 작업 주석: [최초 기준](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/QA/before/snapshot.json)과 [최신 final_v4](C:/Users/whghk/Catrun/Saved/Stage3GothicRevision20261125/QA/final_v4/after/snapshot.json) 비교는 1,002개 중 **1,000개 동일**이다. 비교 대상 Source·Config·공용 재질·기존 캐릭터는 같고 차이는 `Content/Maps/Stage2.umap`, `Content/Maps/Tutorial.umap`뿐이다. Stage2 변경은 [동시 천구의 B안 보고서](C:/Users/whghk/Catrun/Docs/Reviews/Stage2ArmillaryB_2026-11-25.md)에 명시되어 있다. Tutorial은 root가 다른 채팅의 고양이/벽 투명 처리로 확인했다고 전달했다. 이 설명으로 원시 실패를 통과로 덮어쓰거나 다른 작업을 되돌리지 않았다. 최신 비교의 원래 퍼즐·목표·링크·충돌·창고 7개·적 경로 검사는 통과했다.
