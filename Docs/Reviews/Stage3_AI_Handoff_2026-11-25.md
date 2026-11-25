# Catrun Stage3 AI 인계 문서

작성일: 2026-11-25. 사용자가 토큰 소진으로 다른 AI에 인계하기 위해 요청한 문서다. **새 구현·새 검사는 중단하고 인계 자료를 정리한 상태**다. 아래 ‘적용 완료’, ‘검증 완료’, ‘아직 미검증’을 구분해서 이어받을 것.

## 1. 다음 AI가 먼저 알아야 할 현재 상태

- 본 프로젝트: `C:/Users/whghk/Catrun`. 본맵: `Content/Maps/Stage3.umap`. Unreal Content Browser에서는 **`/Game/Maps/Stage3`**, 검색어 **Stage3**. 별도 워크트리만 수정한 것이 아니라 **본파일에 저장했다**.
- 현재 브랜치: `main`. 인계 직전 읽은 HEAD: `302e979ab8b9325986d69b3d33870fd5ed0b984e`. 미커밋 변경이 많고 다른 채팅의 변경도 섞여 있다. `git reset/clean`, 전체 되돌리기, 무조건 전체 스테이징 금지.
- 현재 Stage3 SHA256: **`1ebff0f5ef36a6031d0a782fe6817b323d7981f1018a95a2dd86efcc0c50b65c`**. 작업 재개 전 다시 읽고 달라졌으면 현재 변경부터 확인할 것.
- 마지막 저장: `Saved/Stage3IntegrationRevision20261125/Comfort01/result.json`, `success=true`, `level_saved=true`. 바로 전 맵 백업: `Comfort01/Stage3_before.umap`.
- 마지막 적용: **문 카메라 이동 3초/복귀 2.6초, 기둥 전체 높이 9m, 성문 복도 바구니 X+16cm 이동**. 바구니 입력 검증은 완료, 카메라 재검사·기둥 GPU·최종 3장 화면은 남아 있다.
- 본 채팅의 최근 통합·후속 수정은 **커밋/푸시하지 않았다**. 과거 사용자의 푸시 허용/금지 번복 이력이 있으므로 과거 허용을 근거로 인계 중 자동 푸시하지 말 것. 이번 마지막 요청은 문서 작성이다.
- root가 실행했던 검사 프로세스는 종료됐다. 인계 시 조회된 UE는 사용자 에디터 PID **40748** 한 개이며 종료하거나 저장시키지 않았다. PID는 재확인 필요. 사용자 에디터에는 디스크 최신맵이 아직 반영되지 않았을 수 있으므로 오래 열린 맵을 그대로 저장해 덮어쓰지 말 것.
- 병렬 에이전트는 분석·스크립트 준비만 분담하고 **동일 맵의 적용/저장은 한 담당자**가 직렬 실행했다. 마지막 하위 에이전트 응답 중 usage limit가 발생했으므로 이전 에이전트가 계속 일한다고 가정하지 말 것.

## 2. 사용자 요청과 최신 우선순위

### 원래부터 요구한 것

1. 다른 활성 채팅의 Stage3 제작물을 모아 전부 임포트하고 본 프로젝트에 적용. 사용자 도면을 기준으로 맵 제작. 스테이지 1→2→3 진행 연결, 전체 플레이 회귀·품질·에셋 일관성 검사. 고양이 상호작용 애니메이션 자체검증 프롬프트도 요구했다.
2. Stage3가 ‘묵직하고 엄숙한 고딕 군사 경비시설’로 읽히도록 건축·조명·소품·퍼즐 구조물 통일. 고양이 실제 플레이 위치에서 에셋이 잘 보일 것. 따뜻한 촛불/벽등 국부광과 낮은 전체광, 넓은 중앙 러그가 있는 참고 이미지에 맞출 것.
3. Blender 메시를 다시 만들지 말고 Stage3 전용 Material Instance에서 Base Color를 보정. 텍스처의 석재 질감·Normal·ORM·UV 유지. Stage1·2 공유 원본 머티리얼 수정 금지. sRGB 숫자를 Multiply 입력으로 오인하지 말고 최종 Base Color 목표로 해석.
4. 상호작용/당김 장치는 상호작용 전에 투명해지면 안 됨. 고양이를 가리지 않는 뒤쪽 벽이 투명해지는 버그와 무게추 뒤 공간 부족 수정.
5. 미사용 에셋 조사와 컨셉에 맞는 배치. 제단실 벽을 도면대로 수정하고 고양이·갑옷 통행 확인. **크기/구조 수정은 방안 설명 후 승인**. 아래 B1안은 이미 명시 승인됨.
6. 신규 에셋을 5분마다 확인해 추가 납품분을 임포트·배치하라는 요청이 있었다. 감시는 현재 종료돼 있으며 재개하면 새 기준으로 확인할 것.

### 확정된 후속 변경 및 번복

- 카메라는 최종적으로 **Stage3만 X축 반대 구도** 요청. 현재 yaw -135°, pitch -55°, 직교폭 900cm. Y축 반전 요청은 사용자 스스로 X축으로 정정했다. 도면과 화면의 좌우 방향 때문에 맵 자체를 또 뒤집지 말 것.
- 제단실 사용자 승인 원문: **“제단실 수정안 적용 승인”**. 외곽 10×6m 유지, 아래 ㄴ/ㄱ벽 각각 1.5×1.5m, 좌우 통로 1.25m/중앙 2.30m, E3 위로 50cm 이동, 갑옷 순찰 조정.
- 성문 홀은 원래 15×11m 고정 요구에서 **길이를 늘려 기둥 약 5개 정도 수용**으로 변경. 각 열 5개(총 10개)로 해석해 15×17m 적용, 러그 3×15m. 전체 개수인지 한 열인지 명시된 숫자라고 주장하지 말 것.
- 기둥 끝이 보이지 않게 하라는 이전 요청 → 최신 요청 **“기둥 끝보이는게 좋을거같아 기둥길이좀줄이자”**로 명시 변경. 34.5m 연장을 유지/복원하면 안 됨. 현재 원형 장식 포함 9m로 복원 저장.
- 문 열릴 때 카메라가 너무 빠르므로 Stage2 참조 → 3.0초 이동/2.6초 복귀로 저장.
- 바구니 위치 사용자 최종 답: **“그 성문쪽복도에잇는바구니”**. 대상은 제단실 옆 UpperCorridor 남쪽 입구의 `S3_Placement_Basket_ControlAnnex`. 이미 원인 확인·수정·실제 입력 검사 완료.
- 철창 먼지는 **Stage2가 완성되면 따라 적용**. Stage3가 더 낫다면 Stage2 작업 채팅에 전달하라는 조건부 요청. 실제 비교에서는 Stage2 최신 재질을 선택해 Stage3 전용 사본으로 적용했다. ‘Stage3가 더 낫다’는 조건이 성립하지 않아 역전달 메시지를 보내지 않았다.
- 첫 보석장치를 울렸을 때 로비 갑옷 **두 기가 함께 달려오는 것**이 명시 게임 요구. 시각 파동만 늘리는 것으로 완료하지 말 것.

## 3. 공간·색상 계약

치수는 외곽 가로×세로, 1m=100cm. 도면 좌표는 오른쪽 +X/위 +Y이고 저장 월드는 **(X,-Y,Z)**다.

| 공간 | 지정 치수 | 현재 예외/설명 |
|---|---|---|
| 입구 | 3×2m | 최하단 |
| 로비 | 11×6m | 입구 위 |
| 하단 복도 | 7×8m | 좁은 복도가 아니라 직사각 공간 |
| 마왕 물품 전시방 | 6×11m | 왼쪽 |
| 전시 물품 창고 | 9×7m | 중앙 오른쪽, 내부 ㄱ벽 |
| 중앙 복도 | 12.5×3m | 창고 위 |
| 긴 캣홀 | 7×1.5m | 제단실 오른쪽 아래 |
| 제단실 본체 | 10×6m | 유지 |
| 제단실 왼쪽 아래 추가부 | 5.5×1.5m | 현재 주실과 일부 중첩, 순수 추가 면적으로 오인 금지 |
| 제단실 구조물 | 1.5×1.5m | 승인 B1에서 아래 ㄴ/ㄱ벽 각각의 외곽으로 확정 |
| 상단 복도 | 3×8m | 성문 홀 입구~중간 문 6m |
| 성문 홀 | 원래 15×11m | 후속 요청으로 **15×17m** |

흐름: 입구→로비→하단 복도→전시방/창고→중앙 복도→캣홀·제단실→상단 복도→성문 홀.

최종 Base Color 목표(sRGB 0~255): 벽(101,97,95), 기둥(119,115,109), 바닥(150,146,139), 바닥 마름모(112,108,102), 성문 장식 석재(81,77,75), 흑철(52,50,54), 황동(150,134,107), 군기(101,49,62), 목재(89,72,61), 카펫(73,67,74). Stage3 전용 ColorTint/밝기 파라미터 사용. 이 인계 시 재질 전체 수치를 다시 측정한 것은 아니다. 기존 증거는 `Docs/Reviews/Stage3ColorCorrection20261125/README.md` 및 `evidence.json` 참조.

사용자 도면 원본: `C:/Users/whghk/AppData/Local/Temp/codex-clipboard-9b110b36-818e-4143-80b2-e54f108e29d4.png`. 분위기 참고: `C:/Users/whghk/AppData/Local/Temp/codex-clipboard-1f6879fe-03a7-47ce-9450-8264842e3655.png`. 임시 파일이 없어졌으면 기존 보고서의 도면/이미지 증거로 확인할 것.

## 4. 본파일에 적용 완료한 작업

| 항목 | 적용 결과 | 검증/상세 문서 |
|---|---|---|
| 뒤쪽 벽 오투명 | 과대 bounds·고양이 뒤 연장 검사 제거, 실제 카메라 방향의 9개 전경 ray로 판정 | `Stage3ReadabilityPushFix_2026-11-25.md` |
| 상호작용 장치 가시성 | 장치 불투명 재질 유지, 성문 프레임 합성 bounds 제거 | 같은 문서, 역사적 GPU 증거 |
| P1 밀기 공간 | 시작점 (-700,-1510,0), 뒤 여유 40→120cm. 관련 시각메시/받침도 이동 | native 보행·밀기·리셋 49/49, 당시 전체 퍼즐188/188 |
| 제단실 B1 | 6개 벽, 두께30/높이300cm, 개구부125/125/230cm, E3 로컬17개 위50cm, 갑옷 경로 조정 | `Stage3IntegratedRevision_2026-11-25.md` |
| 성문 홀 | 15×17m, 기둥10개, 러그3×15m, 성문/출구6m 이동, 미니맵 갱신 | 동일. 러그 Y스케일 늘려 문양 비율 변화는 있음 |
| 벽 모서리 | 9곳 벽체 및 몰딩60개 연결 | 동일 |
| 소품/적 | 바구니4개, 전시방 촛불 적1→2기(전체6기), 군기/걸이, 창고 촛불 | 동일 |
| 소리 반응 | Stage3 큰 장치1800cm, 방울500 별도, Small190/Medium250/전파속도600 유지, 가구6개 길찾기 장애물 반영 | 실제 첫 장치에 갑옷2기 반응31/31(이전 저장본) |
| 철창 먼지 | D1/D2 native 완료 이벤트, 8개 풀, .78초 먼지/.26초 흔들림, 리셋/재개방 정리 | dust 보고서 및 ResetReplay03 54/54(Comfort01 직전) |
| 최신 먼지 재질 | Stage2 Gaussian 구름 재질을 Stage3 전용 사본으로 복제, 16카드 재질만 변경 | `Stage3DustMatch_2026-11-25.md` |
| 최신 카메라 시간 | .65/.6→3.0/2.6초, watchdog8→10.5초, 구도/오프셋/문 속도 유지 | **저장 완료, 실제 타이밍 재검사 남음** |
| 최신 기둥 높이 | 34.5→9m. 원래 몸체8.4m+장식 .6m. 연장50개 비가시 보존·그룹명 분리, 활성40개 CPD 재계산 | **정적 저장검사 완료, 새 GPU/이미지 남음** |
| 최신 복도 바구니 | 벽 기단이 하부를 덮는 겹침. trio 전체(-320,-2045,0)→(-304,-2045,0), Z 유지 | 정적17/17 + 실제 입력16사례/163항목 완료, 최종 화면 남음 |

최신 기둥 설정에서도 Stage3 near=-4000/far=10000, yaw=-135/pitch=-55/width900 유지. cap을 잘라 시야를 확보하는 방식이 아니라 원형 장식 머리를 내려 복원한 것. 숨긴 연장부는 `S3_RetiredPillar_*`, 활성 기둥은 `S3_GrandPillar_*`다.

바구니 4개 월드 좌표(cm): Lobby(-170,-345,0), Exhibition(-970,-2195,0), Warehouse(605,-1410,0), ControlAnnex(-304,-2045,0). 액터 전체 bounds의 minZ=-15는 상호작용 영역을 포함하므로 메시가 매몰됐다는 증거가 아니다. 실제 본체 minZ=0, 천 minZ≈26.26, HiddenPointZ=26.25.

## 5. 검증 결과와 증거의 적용 시점

**예전 테스트를 최신 변경 후 다시 실행한 것처럼 보고하지 말 것.**

| 증거 | 결과 | 적용 범위/한계 |
|---|---|---|
| `Saved/Stage3GateFXRevision20261125/Regression02/report.json` | 209/209 | 당시 최종 통행·퍼즐, SHA ffe53c4d…; 최신 기둥/카메라/Annex 이동 이전 |
| `Saved/Stage3PlacementRevision20261125/RuntimeQA04.json` | 174/174 | 이전 바구니16사례+추가 통행 |
| `Saved/Stage3GateHallRevision20261125/RuntimeQA02.json` | 335/335 | 자연 순찰7기 최소2주기, 이전 높이 |
| `Saved/Stage3GateHallRevision20261125/RuntimeQAGPU01/report.json` | 8/8 | 이전 높이 기둥/불투명 장치/near 검사 |
| `Saved/Stage3GateFXRevision20261125/ResetReplay03/report.json` | 54/54 | Stage2 최신 먼지 적용 후, 카메라 속도 변경 전 |
| `Saved/Stage3IntegrationRevision20261125/Comfort01/result.json` | 저장/정적 검사 성공 | 최신 본맵 SHA1ebff0f5…; Stage1/2·문FX 파일 해시 보존 |
| `Saved/Stage3BasketHeightRevision20261125/RuntimeQA01.json` | **163/163, 16사례** | 최신맵 실제F/WASD, 숨기·탈출·blocked fallback·천동기화. 맵/변환보존, cleanup0 |
| `Saved/Stage3CameraPacingRevision20261125/Regression01/report.json` | **실패** | 관찰기 API오류, 카메라 타이밍 결함 판정 불가. 수정 후 재실행 필요 |

이전 기록의 전체 보호파일 1039개 중 1038개 동일, 1개 Stage2 맵은 다른 채팅이 실행 사이에 변경했다. 각 개별 저장/검사 전후 해시 보존과 작업 전체 기간 불변을 혼동하지 말 것.

실패 이력 보존: 초기 dust GPU `Stage2DustMatchQA01/02`는 .15~.26초 촬영창을 놓쳐 실패했다. ResetReplay03은 성공했지만 첫 사용 프레임 시간 안정성을 증명한 것은 아니다. D2의 .0716/.08175초 이미지에서는 먼지를 직접 확인했고 D1 초기 가시성은 충분한 이미지가 없다. 상세 실패/조건은 dust 문서에 있다.

이번 독립 기능 검사는 실제 PIE/native 입력·AI·충돌·렌더를 사용하되 시작위치 fixture/NPC 격리 등이 있다. **사람이 Stage1→2→3을 처음부터 끝까지 플레이한 최종 난이도·전환 회귀 완료로 주장하지 않는다.**

## 6. 남은 작업 — 다음 AI의 권장 순서

### A. 바로 이어서 할 3가지

1. **카메라 속도 실제 재검증**. 첫 실행의 Python `CameraActor.get_camera_component()`가 지원되지 않아 실패했다. `Scripts/Stage3/CameraPacingRevision20261125/verify.py`는 `get_component_by_class(unreal.CameraComponent)`로 수정했고 구문 확인 완료. 새 `Regression02`로 실행해 D1/D2 네 세션, 이동3초/복귀2.6초, 입력 잠금 해제·원래구도·먼지수명·리셋/재개방을 확인. 이전 실패 보고서 덮어쓰기 금지.
2. **새 9m 기둥 GPU + 실제 카메라 3장 확인**. `PillarHeightRevision20261125/combined_qa.py` 준비 완료/아직 실행 전. 한 프로세스에서 대표 전경/후경2케이스, 10기둥 CPD, GateMiddle/GateExtreme/AnnexBasket 3장 생성. PNG를 반드시 직접 열어 장식 머리, 잘린 몸통, 바구니 겹침을 확인. ‘스크립트 성공=미술 완료’ 아님.
3. `Stage3CameraPillarsBasket_2026-11-25.md`에 결과 갱신하고 사용자에게 완료/한계 보고. 최신 맵은 이미 저장했으므로 통과했다는 이유로 다시 저장할 필요 없음.

### B. 오래된 원래 목표 중 상태 재확인이 필요한 것

- Stage1→2→3 **전체 실제 플레이/전환 회귀**는 이 후속 작업에서 새로 완료하지 않았다. `Docs/Reviews/Stage3Evidence/StageProgressProcess.json`, `Docs/Reviews/MainIntegrationEvidence20261125/` 등 기존 증거를 먼저 읽고 현재 저장본/다른 채팅의 엘리베이터 변경과 일치하는지 확인.
- 고양이 상호작용 애니메이션 제작/자체검증: `Docs/Design/Stage3/CatInteraction_ProductionPrompt.md`가 존재한다. 현재 Stage3에서는 기존 native 당김·바구니 천 애니메이션 테스트가 있었으나 모든 신규 애니메이션 제작/납품 상태를 이 인계에서 재확인한 것은 아니다.
- 에셋 납품: 정식FBX99/99 임포트 및 Stage3 메시116종 사용조사는 이전 기록 기준. 마지막 실제 납품스캔18:40:25 KST,2405파일 변경0. **현재 이후 신규 납품 여부는 미확인**, 감시 실행 안 남음. 재개 시 새 스캔하고 변경분만 검토·임포트. 17:32~18:29 기록공백57분45초가 있었으므로 연속5분감시 완료 주장 금지.
- 직접미배치17종 중 DockShortChain은 퍼즐 의존성 있음. 나머지16종은 미참조 후보/예비모듈로 보존. 전부 억지 배치하거나 삭제하지 말 것. 목록 `Saved/Stage3PlacementRevision20261125/postplacement_asset_usage01.md/.json`.
- D1 초기 먼지 시각 증거, 첫 발동 프레임 시간 안정성은 남은 품질 항목. 최신 Stage2와 추가 비교할 때 새 결과를 확인하고 다른 채팅의 파일을 임의 덮어쓰지 말 것.
- 방 전체 비례확대는 승인된 요구가 아니다. 현재 통행 검사로 전체 확대 필요성이 입증되지 않았으며, 성문 홀 외 다른 방 크기를 임의 확대하지 말 것.
- ‘모든 오류가 없다’, 사용자 미술 승인, 전체 잠입 난이도 검증은 미완료/미확정. 이미 통과한 독립 검사만 정확히 보고.

## 7. 실행 환경과 복사 가능한 명령

UE5.8 경로: `C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor.exe`. PowerShell, 작업디렉터리 `C:/Users/whghk/Catrun`.

아래 런처는 숨긴 분리 에디터, 고유 UserDir/로그, `-NoSaveConfig -SaveToUserDir -Multiprocess`를 사용한다. 실행 즉시 PID/로그를 출력하므로 **프로세스 생성만으로 완료라고 보고하지 말고 결과 JSON을 기다릴 것**. Root 검사프로세스는 한 번에 하나만 실행. 사용자 에디터나 다른 채팅 PID 종료 금지.

```powershell
Set-Location 'C:\Users\whghk\Catrun'
Get-FileHash 'Content\Maps\Stage3.umap' -Algorithm SHA256

# 1) 수정된 카메라 observer 재실행. Regression02 미사용 여부 확인 후 실행.
$env:CATRUN_CAMERA_PACING_PASS='Regression02'
.\Scripts\Stage3\IntegrationRevision20261125\run.ps1 `
  -Script 'CameraPacingRevision20261125/verify_entry.py' `
  -Name 'CameraPacingRegression02' -NullRHI

# 앞 실행 종료/JSON 확인 후 2) 실제 GPU + 플레이 카메라 3장
$env:CATRUN_COMFORT_QA_PASS='01'
.\Scripts\Stage3\IntegrationRevision20261125\run.ps1 `
  -Script 'PillarHeightRevision20261125/combined_qa.py' `
  -Name 'ComfortGPUVisual01'
```

GPU combined 결과:

- `Saved/Stage3PillarHeightRevision20261125/CombinedQA01/report.json`
- `Saved/Stage3PillarHeightRevision20261125/RuntimeQAGPU01/report.json`
- `Saved/Stage3IntegrationRevision20261125/ComfortVisual01/report.json`
- 같은 폴더 `GateMiddle_Lit.png`, `GateExtreme_Lit.png`, `AnnexBasket_Lit.png`.

바구니는 이미 최신 저장본으로163/163 통과했으므로 새 변경/실패가 없으면 반복하지 않아도 된다. 필요할 경우만 새 번호로:

```powershell
$env:CATRUN_STAGE3_BASKET_HEIGHT_QA_PASS='02'
.\Scripts\Stage3\IntegrationRevision20261125\run.ps1 `
  -Script 'BasketHeightRevision20261125/run_runtime_qa.py' `
  -Name 'BasketHeightRuntime02' -NullRHI
```

납품 스캔 소스 `C:/Users/whghk/Desktop/CastleKit/Stage3`. `python Scripts/Stage3/PlacementRevision20261125/delivery_watch.py`는1회샘플이며 자동 임포트/상주감시가 아니다. 보고파일 `Saved/Stage3PlacementRevision20261125/delivery_watch.json`.

기존 `D2EarlyGPU`의 복귀1.2초 후 Inactive 조건은 새 복귀2.6초와 맞지 않아 그대로 실행하면 false failure. 새 pacing harness는 실제 Inactive까지 기다린다. 과거 34.5m 전용 GateHall runtime/GPU assertions도 최신 9m의 합격 기준으로 재사용 금지. 새 PillarHeight helper 사용.

## 8. 파일 소유권·안전한 수정 경계

- root 통합/저장: `Scripts/Stage3/IntegrationRevision20261125/`.
- 카메라 담당: `Scripts/Stage3/CameraPacingRevision20261125/`.
- 기둥 담당: `Scripts/Stage3/PillarHeightRevision20261125/`.
- 바구니 담당: `Scripts/Stage3/BasketHeightRevision20261125/`.
- 본맵 재생성 방지 계약: `Scripts/Stage3/layout.py` 기둥900/Annex(-304,2045,0), `IntegrationRevision20261125/apply_core.py` pillar900, `PlacementRevision20261125/apply.py` Annex(-304,-2045,0)까지 최신화했고 py_compile 통과. **이것은 현재 맵을 재생성하라는 지시가 아니다.** `build_map.py`의 기존맵 보호 차단을 제거하지 말 것.
- Comfort01 적용 helper는 최초 상태3450cm/옛 바구니 겹침 등을 전제로 한다. 이미 적용된 본맵에 재실행하지 말 것. 새 수정 필요 시 최신 맵SHA/백업/보호해시를 잡고 작은 별도 pass로 수행.
- Unreal MCP는 연결된 대상이 Stage2/다른 에디터일 수 있다. 현재 프로젝트/맵/PIE 여부를 확인하기 전에 맵 로드·저장하지 말 것. 포트8000이나 tool목록만으로 현재 Stage3 작업 가능을 주장하지 말 것.
- 에디터 시작이70~110초 이상 걸릴 수 있고 메모리는16GB로 제한적. 필요 없는 동시 UE를 추가하지 말 것. 사용자 에디터 종료 권한으로 해석하지 말 것.
- Git worktree는 여러 개 존재(인계 직전 본체+12개). 전부 같은 완성 상태가 아니므로 일괄 merge 금지. 현재 본파일을 기준으로 목적·HEAD·변경을 확인하고 필요한 납품만 통합.
- CatAudioDirector AGENTS 지침은 오디오 제작에만 해당. 이번 문서/카메라/바구니/기둥 작업에서 유료생성이나 오디오 배치 요청은 없음.

## 9. 관련 보고서와 다른 채팅

- 최신 수정 상세: `Docs/Reviews/Stage3CameraPillarsBasket_2026-11-25.md`
- 전체 승인안 적용/통행/자연순찰/에셋조사: `Docs/Reviews/Stage3IntegratedRevision_2026-11-25.md`
- 제단실 승인 설계: `Docs/Reviews/Stage3LayoutPlacementApproval_2026-11-25.md`
- 벽 투명/밀기 해결: `Docs/Reviews/Stage3ReadabilityPushFix_2026-11-25.md`
- 최신 먼지 비교/복제: `Docs/Reviews/Stage3DustMatch_2026-11-25.md`
- 현재 Stage3 먼지 재질: `/Game/Environment/Stage3/GateFX_20261125/Stage2DustMatch01/M_Stage3GateDust`
- 기준 Stage2 재질: `/Game/Environment/Stage2/GameplayPolish_20261125/Presentation/Build_03/M_GateFloorDust`, 비교 당시 SHA `0702ec0428c5f701e30871d19c5856a07b567860cd3e816e629218e52eb432ac`.
- Stage2 작업 채팅: **스테이지 2 에셋 품질 검사**, ID `01a20e2d-bbd3-7760-bacc-61831d69a83d`, host local. 비교했던 완료시각18:52:30 KST 이후 추가 작업이 있었으므로 최신 상태 재확인 필요.
- 보조 전달 채팅 ID `01a2106c-7c72-7ef3-9335-46ef0d096e51`. 전달 내용을 사용자 승인/나중 번복과 함께 읽을 것.
- 디자인 원문 `Docs/Design/GameDesign_Source.md`, 현행 `GameDesign.md`와 후속 사용자 지시 우선. 문서 존재 자체가 새 변경/배포 승인 아님.

## 10. 다음 AI에게 전달할 짧은 시작 문구

> C:/Users/whghk/Catrun/Docs/Reviews/Stage3_AI_Handoff_2026-11-25.md를 먼저 읽고 이어서 작업해 주세요. 최신 Stage3 본맵에는 카메라3초/2.6초, 기둥9m, 성문복도 바구니16cm 이동이 저장됐습니다. 바구니163/163은 완료입니다. 카메라 Regression02와 새 기둥GPU/실제카메라3장 검사는 아직 안 했습니다. 이전 실패증거와 다른 채팅 변경을 보존하고, 동일맵은 한 담당자만 저장하세요. 과거 생성기로 재생성하거나 자동 커밋/푸시하지 말고 최신 사용자 지시를 따르세요.
