# Stage3 아트 보강 — 총괄 인계 (2026-11-26 04:20)

본 프로젝트는 바꾸지 않았다. 미술 승인은 사용자 몫이다.

| 무엇 | 위치 |
|---|---|
| 적용 스크립트 | `C:/Users/whghk/Desktop/CastleKit/Stage3/Overnight_20261126/Scripts/apply_stage3_art.py` (사본 `deliver/`) |
| 전후 화면 26장 | `deliver/BeforeAfter/*.jpg` (원본 PNG는 `out/before`, `out/after`·`after2`·`after3`) |
| 에셋 원본 17종 | `C:/Users/whghk/Desktop/CastleKit/Stage3/Overnight_20261126` (README, 매니페스트, `QA/fbx_reimport.json`) |
| 새 러그 | `C:/Users/whghk/Desktop/CastleKit/Stage3/Rugs05_GateHall_20261125` |
| 본 프로젝트 dry-run | `out/main_dry/report_dry.json` — 성공, 충돌 0, 계획 78건 |
| 적용 전후 액터 대조 | `out/actor_diff.json` |

## 검증

- 본 프로젝트 dry-run: `Stage3.umap` SHA256 `1ebff0f5…0c50b65c`, 충돌 0. 저장·임포트 없음(실행 뒤 맵 해시 같음).
- 후보 적용(NullRHI, 새 임포트 + 맵 저장): 78건 성공. **2차 형태 기준**이며, 저장본 사본은 `out/Stage3_applied_candidate.umap`.
- 최종 형태 적용(d3d12, 새 임포트, 맵 저장 없이 PIE): 78건 성공, 촬영 성공.
- 적용 전후 액터: 1785 → 1834. 새 49개 모두 `S3_Art26_*`, 메시는 모두 NoCollision, 태그는 `Stage3Art20261126`뿐. 바뀐 기존 액터 29개는 계획과 일치(군기·걸이 이동 16, 숨김 12, 러그 1). 사라진 액터 0.
- 화면: 26곳을 적용 전후로 직접 열어 봤다. 최종 수정(등 그림자, 기둥 머리 별)은 01·04·20·22·24·25 여섯 곳만 다시 찍었고, 나머지는 그 직전 형태(`after2`, 일부 `after`)다. 차이는 등 두 개의 그림자와 기둥 머리 별 크기뿐이다.
- 안 한 것: 실제 플레이 통행·시야·소리 회귀, 성능 측정, 저장본을 다시 연 화면. NoCollision·태그 없음으로 영향이 없어야 하지만 회귀 세션 확인이 필요하다.

## 적용 순서

1. 다른 에디터가 Stage3을 열고 있지 않은지 확인한다. Stage3을 먼저 바꾼 작업이 있으면 그 뒤에 한다(이 스크립트는 자기 대상 액터만 검사하므로 맵 해시가 달라도 된다).
2. dry-run을 다시 돌려 충돌 0을 확인한다.
3. 적용한다. 맵 백업은 스크립트가 만든다.
4. `report_apply.json`의 `success`, `new_actors=49`, `saved_packages`를 본다.
5. 회귀 세션의 Stage3 항목을 돌린다.

환경변수 `S3ART_MODE=dry|import|apply`, `S3ART_OUT=<보고서 폴더>`, `S3ART_QUIT=1`, 선택 `S3ART_EXPECT=<맵 SHA256>`. 실행 예는 `tools/run_main_dry.py`에 있다(`S3ART_MODE`만 apply로 바꾸면 된다). NullRHI로 된다.

- 되돌리기: 백업 맵을 복원하고 `/Game/Environment/Stage3/Overnight_20261126` 폴더를 지운다. 기존 공용 에셋은 저장하지 않는다.
- 한 번 적용한 맵에 다시 실행하면 원본 상태 검사에서 멈춘다(정상).
- **파일 재제작 금지:** `build_assets.py`를 다시 돌리면 FBX 해시가 바뀐다. 매니페스트도 함께 갱신되므로 동작은 하지만, 이미 임포트했다면 다시 임포트된다.

## 바꾸는 것

기존 액터 29개
- 러그 `S3_GothicRug_GrandGate`: 메시 교체, Scale (1,1,1). 바운드가 같은지 검사한다.
- 대형 군기 `S3_Banner0/1`: 벽에서 22cm 앞으로.
- 군기·걸이 14개: 기둥 앞으로 10cm, 전시방 1쌍은 빈 벽으로 이동.
- 전시대의 잘못 기울어진 무기 8·철 띠 4: 숨김.

새 액터 49개: 벽·바닥·전시대·가구 장식 37, 기둥 머리 상감 10, 점광원 2(기존 벽등 광원 복제, 12.1cd·3200K).

| 새 에셋 | 크기 cm | 삼각형 | 배치 |
|---|---|---:|---:|
| SM_S3_GrandGateRug_300x1500 | 300×1500×0.6 | 3,768 | 교체 1 |
| SM_S3_GateBannerFrame | 224×54×530 | 2,168 | 2 |
| SM_S3_BannerStandoff | 99×20×14 | 232 | 6 |
| SM_S3_WallArmsTrophy | 106×14×121 | 936 | 4 |
| SM_S3_WallTagBoard | 115×5×85 | 958 | 2 |
| SM_S3_WallKeyRack | 80×6×49 | 1,844 | 2 |
| SM_S3_FloorMedallion_300 | 300×300×0.6 | 4,348 | 1 |
| SM_S3_FloorThreshold_240/220/170/120 | 길이×30×0.5 | 120~180 | 7 |
| SM_S3_FloorDrain_120 | 120×36×0.6 | 592 | 4 |
| SM_S3_ExhibitDressing_A/B | 94×241×45 | 2,824 / 2,508 | 1+1 |
| SM_S3_RackBackDressing | 122×6×62 | 1,680 | 3 |
| SM_S3_CabinetBackBands | 114×3×128 | 620 | 2 |
| SM_S3_PillarCapInlay | 139×139×0.9 | 360 | 10 |
| SM_S3_GuardLantern | 17×36×56 | 740 | 2 |

새 텍스처는 러그 9장뿐이고 나머지는 Stage3 공용 재질을 참조한다. `Overnight_20261126` 폴더는 약 37MB다.

## 사용자가 볼 점

- 러그 보조 별·짧은 변 문양, 하단 홀 바닥 문장, 기둥 머리 상감은 새로 정한 디자인이다. 기둥 높이 9m는 그대로이고 상감 두께만 0.9cm 더해진다.
- D2 잠금쇠 앞과 로비 동쪽 방이 밝아졌다. 어두운 방의 긴장감을 원하면 `S3_Art26_Lantern_*` 네 액터만 빼면 된다.
- 손대지 않은 관찰(승강기 톤, 바구니 채도, 기둥 가림 그림자, 끊긴 몰딩, 벽 속 `S3_Banner3`)은 `Overnight_20261126/README.md`에 있다.
