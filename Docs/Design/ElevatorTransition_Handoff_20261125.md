# Stage2 → Stage3 승강기 시네마틱 작업 인계

기준: 2026-11-25, 한국 시간. 사용자 요청으로 구현 진행을 멈추고 현재 상태를 문서화했다.

> **2026-11-26: 승강기 연출을 다시 만들어 적용했다.** 현재 기준은 `Docs/Reviews/Overnight_2026-11-26/Elevator.md`이며, 활성 DLL은 `UnrealEditor-Catrun.dll`이다. 아래는 Revision 3 기록이다.
>
> **적용 상태 갱신 (2026-11-25 23:35 KST): 3절 1)~4)를 본 프로젝트에 적용하고 재시작 후 확인까지 마쳤다.** 아래 0절, 2절 B, 3절의 "미실행/0회/적용 대기"와 이 문서 끝의 미완료 문구는 적용 전 기록이다.
>
> - 적용 전 확인: 에디터 PID 40748, `/Game/Maps/Stage2`, PIE=false, dirty=false.
> - 카메라·태그: 변경 33건(카메라 transform 1, FOV 1, 태그 31), `/Game/Maps/Stage2`만 저장. SHA256 `462cfe77…` → `3887fffa…`. 보고서 `Saved/ElevatorTransition/live_departure_apply.json`, 백업 `Saved/ElevatorTransition/Backups/Stage2_BeforeLiveDeparture_20261125_231300_26016.umap`. 저장 후 읽기 전용 재검사로 값·태그 31개·dirty=false 확인.
> - DLL: `published_for_next_launch`, `manifest_committed=true`. 보고서와 원본 manifest 백업은 후보 프로젝트 `Saved/ElevatorTransitionRevision3/Publish_20261125_141651_099059_fe40c8af`. canonical DLL은 변경 없음.
> - 재시작: 사용자 승인 후 미저장 변경이 없음을 확인하고 정상 종료(WM_CLOSE). 마지막 재실행 PID 43664가 `UnrealEditor-Catrun_ElevatorRevision3.dll`을 로드했고 Stage2 카메라·태그 값이 유지됨을 읽기 전용으로 확인했다.
> - 본 프로젝트 offscreen PIE(격리 저장): d3d12 58개 통과(`Saved/ElevatorTransition/MainRevision3_02_D3D12.log`, `Runtime/report.json`). 얼굴 샷 `07_PeekFromBelow00007`, `07b_PeekFaceMiddle00001`, `07c_PeekFaceRising00001`을 직접 확인해 후보와 대조했다. 실행 전 Runtime 백업은 `Saved/ElevatorTransition/Backups/Runtime_BeforeMainRevision3_20261125`.
> - **`run_runtime.ps1`은 기본값이 d3d11이다. 화면 판정에는 `-RHI d3d12`를 쓴다.** d3d11도 58개를 통과했지만(`Runtime/main_revision3_d3d11_report.json`) 얼굴 샷에서 눈·코·방울이 거의 검게 나왔다. 간접광(Lumen) 차이로 추정한다.
> - 메모리 때문에 검사 에디터와 작업 에디터를 동시에 띄우지 않았다.
> - 커밋·푸시 없음.

## 0. 다음 AI가 먼저 알아야 할 현재 상태

**최신 수정은 소스 작성, 별도 DLL 빌드, 실제 PIE 58개 검사, 얼굴 샷 이미지 확인까지 끝났다. 본 프로젝트 Stage2의 카메라·태그 저장과 새 DLL 활성화는 아직 실행하지 않았다.** 적용 스크립트 두 개는 준비됐고 각각 dry-run을 통과했다. 사용자가 인계 문서를 요청한 시점이 바로 실제 적용 직전이다.

- 실제 작업 프로젝트: `C:\Users\whghk\Catrun\Catrun.uproject`
- 이 채팅의 최초 cwd였던 `C:\Users\whghk\.codex\worktrees\1166\Catrun`에 적용하지 않았다. 이어서 작업할 때도 실제 프로젝트 경로를 확인한다.
- 검증용 별도 프로젝트: `C:\Users\whghk\.codex\workspaces\ElevatorRevision3_20261125_01a21074\Catrun`
- 본 프로젝트 소스에는 최신 C++ 수정이 있다. 그러나 현재 본 프로젝트 `UnrealEditor.modules`는 여전히 `Catrun: UnrealEditor-Catrun.dll`이다. 실행 중인 사용자 에디터도 이전 DLL을 사용한다.
- 별도 실행본의 최신 DLL: `Binaries\Win64\UnrealEditor-Catrun_ElevatorRevision3.dll`
- 본 프로젝트에 대한 최신 카메라 적용은 **0회**, DLL 게시도 **0회**다. `--apply` 명령을 실행했다고 주장하지 않는다.
- 검증용 에디터 PID 44228은 검사 성공 후 정상 종료했다. 사용자 에디터를 종료하거나 재시작하지 않았다.
- 이 승강기 작업에서 커밋·푸시·다른 채팅으로 메시지 전송을 하지 않았다.

새 AI에게 이 문서 경로를 주고 다음과 같이 요청하면 된다.

> 이 문서를 읽고 승강기 시네마틱 작업을 이어서 완료해. 검증된 Revision 3를 실제 프로젝트에 안전하게 적용하는 단계부터 진행하고, 기존 고양이 외형·리그와 다른 채팅의 수정은 보존해. 완료된 제작을 처음부터 다시 만들지 마.

## 1. 사용자가 시킨 작업과 확정된 연출

### 공간·에셋

1. Stage2 출구에서 안전한 복도로 들어가면 갑옷 추격을 끊는다.
2. 복도 진입 시 해당 복도의 카메라 가림 벽·천장을 치워 고양이와 통로를 보여 준다. 주변은 어둡고, 고양이 자체가 투명해지면 안 된다.
3. 복도 끝은 벽이 높고 닫힌 창고 느낌의 방이다. 주변에 상자들이 있고, 위쪽의 제한된 빛과 먼지 속에서 승강기만 돋보인다.
4. 승강기는 고딕/중세 분위기의 투박한 목재 판자 구조다. 고양이 전용 크기가 아니라 사람이 쓰던 장치에 고양이가 몰래 탄다.
5. 천장에 매달린 고리를 고양이가 충분히 높이 점프해서 잡고 당긴다. 사람 손높이 레버를 고양이 높이로 낮춘 장치가 아니다.
6. 승강기 내부는 세로로 길고, 앞면이 열려 카메라가 고양이와 고리를 볼 수 있어야 한다. 승강기 자체에 작은 조명이 달려 있다.

### 전체 진행

`복도 진입 / 추격 종료 → 창고 자유 이동 → 승강기 진입 / 주변 암흑 → F 상호작용 → 검정 띠 / 조작 잠금 / 카메라 접근 → 점프·고리 잡기·당기기 → 기계음 / 출발 충격 → 놀람 → 고양이가 아래를 내려다봄 / 바닥 카메라가 얼굴을 비추며 상승 → 어둠 속 흔들리는 상승 → 블랙아웃 → 식빵 자세 → 도착 잠금장치 충격 / 놀라 일어남 → 조심스럽게 하차 → 주변 둘러보기 → 플레이 카메라로 부드럽게 복귀 → Stage3 시작 문구`

### 이전 추가 요청

- 조명은 더 어둡고 부드러운 크림색으로 조절한다. 먼지는 더 잘 보이게 한다.
- 도착 후 고양이가 앞으로 조심스럽게 발을 디디며 내려온다. 주변을 둘러본다.
- 승강기는 도착 후에도 남는다. 바닥과 충돌을 유지하여 다시 들어갈 수 있어야 한다. 재상호작용은 없다.
- 고양이가 타면 약간 가라앉고, 내리면 조금 위로 튀었다가 안정되는 무게 반응을 넣는다.
- 기존 고양이 외형, 비율, 메시, 스켈레톤/리그를 유지한다. 승인된 에셋을 임의로 재제작하지 않는다.

### 이번에 고치라고 한 최신 요청

1. **바닥에서 고양이 얼굴을 올려다보며 승강기가 올라가는 샷 복원.** 고양이는 아래를 내려다봐야 한다.
2. **F를 누르기 전, 승강기에 들어가는 순간부터 승강기 구역 외의 모든 주변을 가린다.**
3. **이 구간에서는 미니맵을 표시하지 않는다.** 현재 구현 범위는 복도·창고·승강기 및 시네마틱이다.
4. **F를 누를 때 현재 카메라에서 고양이·고리가 있는 화면으로 자연스럽게 이동한 뒤 점프한다.**

### 현재 작업에서 제외해야 할 내용

- 사용자가 보낸 “철창 열림·Stage2 먼지 비교 후 다른 채팅에 전달”은 바로 다음에 **잘못 보낸 채팅이라고 취소했다.** 실행하거나 다른 채팅에 전달하지 않았다. 이 인계에서 재개하지 않는다.
- 초기 Runway/AI 영상 제작은 연결 문제 이후 현재 구현의 선행 조건이 아니다. 생성 영상이 완성됐다는 증거는 없으며, 영상 제작을 다시 시작할 필요가 없다.
- Stage3의 더 큰 전경 공개/추가 이동 공간은 최종 미술 방향이 확정되지 않았다. 현재는 기존 플레이 가능한 입구로 연결한다.

## 2. 완료된 작업

### A. 이전 제작·Revision 2 — 기존 납품 기록과 증거가 있음

상세: `C:\Users\whghk\Catrun\Docs\Design\ElevatorTransition_Delivery.md`

- Stage2 안전 복도·창고·승강기, Stage3 도착부, 레벨 전환, 입력/타이머 소유권과 취소·스킵 처리.
- 모델·재질·애니메이션 가져오기. 이전 cold audit 기록상 정적 메시 35개, 충돌 hull 38개, 가져온 애니메이션 10개, 재질 8개, 텍스처 21개.
- 애니메이션은 기존 BlackCat 스켈레톤을 사용한다. C06 이동 궤적은 제공된 30Hz CSV와 UE 스케일에 맞춰 복구했다. 원본 소스 애니메이션은 보존했다.
- F 검정 띠, 점프/고리 당김 카메라, 상승·블랙아웃·식빵·도착 충격.
- 조명: 승강기 실용등 125→35, 창고 상부 1100→400, 부드러운 크림색. 창고 먼지 160개, 승강기와 함께 이동하는 먼지 32개. 일부 큰 먼지 입자로 가독성 보완.
- 하차: 기존 CautiousWalk를 2배 재생, 이동속도 26cm/s에 맞춤. 기존 스켈레톤으로 3.2초 둘러보기 클립 추가.
- 하차 카메라가 고양이를 따라 이동하고, 실제 게임 카메라로 1.1초 블렌드한 뒤 Stage3 제목 표시. 제목은 시계 아래로 이동.
- 승강기 바닥·벽 충돌 유지, 도착 후 F 상호작용 없음. 약 4cm 하중 침하와 최대 약 +0.65cm 반동, 감쇠된 상하 움직임.
- 도착 후 재진입 때 플레이 카메라를 가리는 천장·뒤/왼쪽 벽·모서리 프레임만 화면에서 숨김. 바닥과 먼 쪽 벽은 유지하고 나가면 복원.
- 이전 실제 PIE 39개 검사, 별도 재진입 가림 8개 검사, 무게/제목 네이티브 검사 5개 통과 기록이 있다.

이전 증거:

- `C:\Users\whghk\Catrun\Saved\ElevatorTransition\Runtime\revision2_functional_final.json`
- `C:\Users\whghk\Catrun\Saved\ElevatorTransition\Runtime\reentry_visibility_final.json`
- `C:\Users\whghk\Catrun\Saved\ElevatorTransition\ArrivalNativeFinal03\Report\index.json`
- `C:\Users\whghk\Catrun\Saved\ElevatorTransition\cold_import_audit.json`

### B. 최신 Revision 3 — 코드와 검증 완료, 본 프로젝트 최종 적용 대기

수정한 핵심 소스:

- `C:\Users\whghk\Catrun\Source\Catrun\LevelFlow\CatrunElevatorTransition.h`
- `C:\Users\whghk\Catrun\Source\Catrun\LevelFlow\CatrunElevatorTransition.cpp`

| 항목 | 실제 구현/검증 상태 |
|---|---|
| 진입 즉시 주변 숨김 | 로컬 PlayerController의 HiddenPrimitiveComponents로 주변 지오메트리를 가림. 충돌·AI·원래 액터 숨김 상태를 삭제하지 않음. 고양이·승강기·등·고리 및 허용 태그 부품 유지. 실제 PIE 확인. |
| 광원·안개 처리 | 프리미티브가 아닌 외부 광원/안개 등의 표시 상태를 별도로 관리하고 소유한 변경만 복원. |
| 미니맵 | 복도·창고·승강기에서 F 전부터 Collapsed 유지, 구간 이탈/도착 후 복원. 실제 UI 상태 검사 통과. |
| F 카메라 | 현재 시점에서 FrontCamera로 1초 Cubic 블렌드. PendingViewTarget 블렌드가 실제 끝날 때까지 점프 클립 시작 대기. 중간 위치와 즉시 입력 잠금 확인. |
| 아래 얼굴 샷 | 고정 바닥 카메라 위치 `(729,-1310,14)`, 수평 FOV 36. 양 눈 소켓 중간을 회전으로 추적. 렌즈 위치는 상승하지 않음. |
| 얼굴 샷 길이 | C06 원본 3.4~5.77초 구간만 재생속도 0.74. 실제 화면 유지 3.194초, 얼굴 높이 약 106.85cm 증가, 최대 시선 추적 오차 약 0.473도. |
| 기존 기능 보존 | 정상 전환, 취소, 일시정지, 하차·둘러보기·카메라 복귀·제목, 무게 반응·재진입·스킵·직접 Stage3 진입을 포함해 최종 58개 검사 통과. |

**수정 원인:** 예전 `E23_Shot_Below`가 `(735,-1350,-32)`에 있어 창고 바닥 `Z=-5..0` 아래에서 위를 보고 있었다. 이전 실제 `07_PeekFromBelow00005.png`는 검은 화면이었다. 주변 숨김도 상승 중간에야 적용되어 샷을 가렸다. 이번에는 카메라 위치와 숨김 시작 시점을 모두 고쳤다. 단순 상태 검사만 통과한 것을 얼굴이 보이는 증거로 취급하면 안 된다.

### C. 이번 최종 증거 — 실제 렌더링 확인

읽기 편하도록 핵심 증거 10개를 본 프로젝트 아래에 복사했다. 게임 파일을 변경한 것이 아니라 기존 검증 결과의 복사본이다.

`C:\Users\whghk\Catrun\Saved\ElevatorTransition\Revision3Handoff_20261125`

- `runtime_report.json`: success=true, error=null, 최종 58개 모두 통과.
- `build_report.json`: UBT compilation 성공 + 별도 경로 수동 링크 성공. 일반 전체 링크 빌드라고 표현하지 않는다. 본 프로젝트 DLL/manifest의 해시와 타임스탬프 보존 확인.
- `publish_dryrun_report.json`: 다음 실행용 DLL 적용 준비 검사 통과, manifest_committed=false.
- `candidate_camera_author_report.json`: 후보 Stage2에 적용한 카메라 위치/FOV 및 승강기 허용 태그 31개 목록.
- `03_CabinBeforeF.png`: F 전 주변 암흑·미니맵 없음.
- `03b_FCameraBlend.png`: F 카메라 중간 이동 화면.
- `05_HangPull.png`: 고리 당김 구도.
- `07_PeekFromBelow.png`, `07b_PeekFaceMiddle.png`, `07c_PeekFaceRising.png`: 실제 아래 얼굴 샷 시작·중간·끝. 세 장 모두 직접 확인했다. 얼굴과 눈이 프레임 안에 있으며 승강기가 올라간다.
- `evidence_manifest.json`: 복사본과 원본 경로, SHA256.

실제 중간 얼굴 샷:

![승강기 바닥 시점 얼굴 샷](C:/Users/whghk/Catrun/Saved/ElevatorTransition/Revision3Handoff_20261125/07b_PeekFaceMiddle.png)

검사 한계도 유지한다. 초기 복도/창고/승강기 진입은 테스트 위치 배치 fixture를 사용했다. 무중단 수동 전체 완주 검사가 아니다. PC 입력 경유 Tab 이후 Collapsed 유지 검사이며, OS/Slate 경유 실제 Tab 키 주입 검사는 아니다. 실제 Slate Tab 자동화는 별도 `Catrun.UI.Minimap.RoutedHoldAcrossStages`에 있다.

## 3. 다음 AI가 해야 할 작업 — 우선순위 순

### 1) 현재 상태 재확인

- 이 문서 작성 후 다른 채팅이 파일이나 에디터를 바꿀 수 있다. 실제 프로젝트 경로, PID, PIE 여부, 맵 dirty 상태, 소스/DLL/manifest 해시를 다시 확인한다.
- 마지막 확인에서 사용자 에디터는 PID **40748**, MCP `http://127.0.0.1:8000/mcp`, 현재 `/Game/Maps/Stage2`, PIE=false, Stage2 dirty=false였다. PID를 영구 사실로 취급하지 않는다.
- 다른 채팅도 Unreal/Blender/소스/맵 작업을 하고 있다. 다른 프로세스를 종료하지 않는다.
- 후보의 `Content/Maps`는 물리 복사지만, 다른 Content 폴더·Plugins·Source·Scripts는 본 프로젝트를 가리키는 junction이다. 후보에서 연결된 에셋을 저장하지 않는다.

### 2) 본 프로젝트의 카메라·승강기 허용 태그 적용

준비된 스크립트:

`C:\Users\whghk\Catrun\Scripts\ElevatorTransition\apply_departure_shots_live.py`

기본 실행은 read-only 계획 점검. 이미 실제 main MCP에 대해 dry-run을 통과했다:

`C:\Users\whghk\Catrun\Saved\ElevatorTransition\live_departure_dryrun.json`

실제 적용 명령(아직 미실행):

```powershell
Set-Location -LiteralPath 'C:\Users\whghk\Catrun'
python -B Scripts/ElevatorTransition/apply_departure_shots_live.py --apply --expected-editor-pid 40748 --report Saved/ElevatorTransition/live_departure_apply.json
```

- PID가 바뀌었다면 소유 프로세스/프로젝트를 확인한 후 실제 PID로 바꾼다.
- 현재 로드된 Stage2의 E23 카메라 1개와 승강기 부품 태그 31개만 바꾼다. 카메라·director·pivot까지 총 34개 대상 액터를 검사한다.
- 기존 맵을 백업한다. 소유 태그, camera/director 참조, 후보 계약, 맵 파일 해시, 대상 액터의 현재 상태, PIE/dirty 상태를 검사한다.
- 저장 호출은 `save_assets(['/Game/Maps/Stage2'])` 한 번이다. 빈 목록을 넘기면 다른 dirty asset까지 저장할 수 있으므로 사용하지 않는다.
- **후보 Stage2.umap을 main에 통째로 복사하면 안 된다.** 다른 채팅의 최신 맵 작업을 덮어쓸 수 있다.
- MCP에는 원자적 전체 트랜잭션이 없다. 짧은 적용 중 관련 없는 액터에 사용자가 동시에 메모리 편집을 하는 경우까지 완전 감지는 못 한다. guard 실패 시 저장을 강행하거나 자동 rollback하지 말고 현재 상태부터 조사한다.
- 현재 main 카메라 ref: `/Game/Maps/Stage2.Stage2:PersistentLevel.CameraActor_2`, component는 `.CameraComponent`.
- 최종 위치 `(729,-1310,14)`, 회전 pitch 약 `45.329366`, yaw 약 `-94.366681`, roll 0, scale 1. FOV 36.
- ObjectTools의 속성 키는 **`FieldOfView`, `bConstrainAspectRatio`**이다. snake_case는 사용하지 않는다.

### 3) 검증된 DLL을 다음 에디터 실행용으로 적용

준비된 스크립트:

`C:\Users\whghk\Catrun\Scripts\ElevatorTransition\publish_revision3.py`

마지막 dry-run 성공 기록:

`C:\Users\whghk\.codex\workspaces\ElevatorRevision3_20261125_01a21074\Catrun\Saved\ElevatorTransitionRevision3\Publish_20261125_103920_056253_89c569ee\publish-report.json`

적용 명령(아직 미실행):

```powershell
Set-Location -LiteralPath 'C:\Users\whghk\Catrun'
$elevatorCandidate = 'C:\Users\whghk\.codex\workspaces\ElevatorRevision3_20261125_01a21074\Catrun'
python -B Scripts/ElevatorTransition/publish_revision3.py --build-report "$elevatorCandidate\Saved\ElevatorTransitionRevision3\Build_20261125_102452_9469\build-report.json" --qa-log "$elevatorCandidate\Saved\ElevatorTransition\Revision3Candidate01.log" --apply
```

- 본 프로젝트의 사용 중인 canonical DLL을 덮어쓰지 않는다. 검증된 underscore 이름 DLL/PDB를 별도 이름으로 복사하고, 원본 manifest를 백업한 뒤 Catrun 항목만 원자적으로 변경한다.
- source/DLL/manifest 해시가 빌드/검사 당시와 달라졌으면 중단하도록 되어 있다. 체크를 제거해서 강행하지 않는다. 다른 채팅의 새 빌드가 있다면 최신 소스를 포함해 다시 합쳐 검증해야 한다.
- `UnrealEditor-Catrun_ElevatorRevision3.dll`은 실제 후보 콜드 로딩을 확인한 이름이다. underscore를 임의로 `-1234` 형태로 바꾸지 않는다. 하이픈 suffix는 에디터 자동 hot-reload 감시 대상이 될 수 있다.
- **적용 성공 후에도 현재 열린 에디터는 이전 DLL이다. 저장 후 재시작해야 새 코드가 적용된다.** 사용자 에디터를 강제로 닫거나 기존 작업을 잃게 하지 않는다. 최종 안내에 재시작 필요를 반드시 명시한다.

### 4) 적용 결과 정리

- `live_departure_apply.json`의 성공과 main Stage2 저장, publish report의 `published_for_next_launch`/`manifest_committed=true`를 확인한다.
- 이미 58개 검사는 후보에서 끝났다. 똑같은 검사를 이유 없이 계속 반복하지 않는다. 새 코드/맵 차이가 생겼거나 실제 적용의 불일치가 있을 때만 필요한 범위를 다시 확인한다.
- 가능하고 사용자 작업을 방해하지 않을 때 재시작 후 실제 main DLL 로드와 Stage2 카메라 값을 확인한다. 아직 재시작 안 했다면 현재 실행 화면에 반영됐다고 말하지 않는다.
- `ElevatorTransition_Delivery.md`, `ElevatorTransition_Implementation.md`, 이 인계 문서의 Revision 3 적용 상태를 갱신한다.
- 사용자에게 수정 세 가지(바닥 얼굴 샷/진입 암흑·미니맵/F 카메라 이동), 검증 범위, 재시작 필요 여부를 짧게 전달한다.

## 4. 이어서 작업할 파일·도구

아래 경로는 모두 실제 main 프로젝트 기준이다.

| 파일/경로 | 역할 |
|---|---|
| `Source/Catrun/LevelFlow/CatrunElevatorTransition.h`, `.cpp` | 전체 승강기 시네마틱, 새 구역 가림/미니맵/F 블렌드/아래 얼굴 카메라 |
| `Source/Catrun/LevelFlow/CatrunElevatorWeightComponent.h`, `.cpp` | 이전에 완료된 하중·반동. 이번 Revision 3에서 변경 안 함 |
| `Scripts/ElevatorTransition/verify_runtime.py` | 최신 58개 실제 PIE 검사, 최종 통과한 버전 |
| `Scripts/ElevatorTransition/refine_departure_shots.py` | 후보/격리 에디터의 카메라·태그 author. main에는 live 전용 스크립트를 쓸 것 |
| `Scripts/ElevatorTransition/probe_peek_pose.py` | C06 눈/머리 위치와 바닥 가림 읽기 전용 진단 |
| `Scripts/ElevatorTransition/author_revision3_and_verify.py` | 후보 프로젝트에서만 camera author 후 실제 검사 |
| `Scripts/ElevatorTransition/prepare_revision3_candidate.py` | Maps 물리 복사·기타 junction·자체 binaries를 가진 후보 준비 |
| `Scripts/ElevatorTransition/build_revision3_candidate.ps1` | UBT compile-only 후 후보 경로로 별도 링크. `-Compile` 없으면 준비만 |
| `Scripts/ElevatorTransition/run_runtime.ps1` | 숨긴 offscreen 검사 에디터, 별도 user save, `-ProjectRoot`, `-RHI` 지원 |
| `Scripts/ElevatorTransition/remote.py` | 작업용 Python remote UDP 6777 채널. main MCP 8000과 구분 |
| `Scripts/Prototype/ue_mcp.py` | main 8000 MCP 클라이언트 |
| `Docs/Design/ElevatorTransition_Delivery.md` | 이전 납품·한계·증거 |
| `Docs/Design/ElevatorTransition_Implementation.md` | 구현 기록 |

콘텐츠 브라우저:

- 레벨 폴더 `/Game/Maps`, 레벨 `Stage2`, `Stage3`.
- 아웃라이너 검색: `E23_Director`, `E23_View_Warehouse`, `E23_Shot_Ring`, `E23_Shot_Below`.
- 승강기 모델·재질: `/Game/Environment/ElevatorTransition`.
- 시네마틱 애니메이션: `/Game/Cinematics/ElevatorTransition/Animations`.

## 5. 시행착오 — 반복하지 말 것

1. **카메라 좌표만 보고 얼굴이 보인다고 주장하지 않는다.** 이전 below 샷은 바닥에 가려 완전 검정이었다. 이번에는 실제 시작/중간/끝 이미지까지 확인했다.
2. `HiddenPrimitiveComponents`는 reflected property지만 보호된 필드다. Python의 `get_editor_property('hidden_primitive_components')` 또는 PascalCase 직접 읽기는 실패했다. `pc.console_command`도 Python에 노출되지 않았다.
3. 최종 검사는 `SystemLibrary.execute_console_command`의 read-only `getall PlayerController HiddenPrimitiveComponents NAME=... OUTER=...`와 `flushlog`를 사용하여 현재 플레이어의 실제 내부 목록을 로그에서 읽는다. 별도 로그 `-abslog`가 필요하다.
4. 기존 `HideDuringAscent`에는 창고뿐 아니라 고정 레일·도르래도 들어 있다. “전부 숨겨져야 한다”는 검사는 틀린 조건이다. 창고는 가리고 승강기 부품은 유지하는 것으로 테스트를 고쳤다.
5. 1초 F 블렌드를 추가했으므로 기존 `.8초 후 Departure` 검사는 빠르다. 최종 스킵 테스트는 1.3초 후 검사한다. 준비 컷도 timeline 1.45초 이후로 조정했다.
6. `Shot showui`는 에디터 UI까지 포함한다. 얼굴 샷 07/07b/07c는 `Shot`으로 뷰포트만 캡처했다. 이미지 파일을 편집해서 결과를 만들지 않았다.
7. 검사 로그에는 위 Python 검사 도구 수정 전의 실패 이력도 있다. 최종 `Runtime/report.json`의 58개 성공과 최종 이미지가 최신 증거다. 게임 C++는 이 검사 도구 수정 때문에 다시 바뀌지 않았다.
8. 열린 에디터 때문에 main DLL을 바로 링크하지 않는다. 이번 빌드는 로컬 UE5.8 소스에서 `-ActionTypeFilter=Compile`가 기존 출력 삭제 전에 적용되는 것을 확인한 뒤 사용했다. 원본 DLL/manifest는 보존했다.
9. main에서 `-ModuleWithSuffix`를 임의 사용하면 manifest 갱신/자동 hot-reload를 일으킬 수 있다. 검증한 후보/underscore 게시 절차를 따른다.
10. 전체 `author_scene.py` 또는 `refine_arrival_scene.py`를 지금 다시 돌리지 않는다. 이전 Stage2/Stage3 제작과 다른 채팅 수정에 불필요하게 영향을 줄 수 있다.

## 6. 남아 있는 제작 한계와 이번 범위 밖 사항

- 기존 C05에는 놀람/꼬리 움직임은 있으나 **꼬리가 방사형으로 부푸는 tail puff는 실제 구현되지 않았다.** 완료했다고 말하지 않는다.
- 일부 전달된 모션에 피부 접힘/관통이 있다. 이번 수정은 기존 리그·외형·모션을 보존하는 카메라/표시 처리다.
- 세 기계음은 로컬 임시 합성 Foley이며 최종 승인된 사운드가 아니다. 새 BGM/소리 전파 시스템 변경은 이번 범위가 아니다.
- 더 넓은 Stage3 전경 공개, 추가 이동 공간은 사용자 방향 결정이 필요한 후속 미술 사항이다.
- AI 영상 생성이 완료된 것이 아니며, 현재 인계의 필수 다음 단계도 아니다.

## 7. 병렬 작업 상태

- `elevator_entry_fix`: native 가림·미니맵·블렌드·추적/길이 수정과 읽기 리뷰 완료.
- `elevator_build_path`: 안전한 후보 빌드와 다음 실행용 게시 스크립트, live MCP 읽기 조사 완료.
- `elevator_below_shot`: 카메라/pose 진단·후보 author 및 main live 적용 스크립트 작성, 실제 dry-run까지 완료. 이후 추가 offline mock 검사 도중 사용량 한도로 종료됐으므로 그 추가 검사는 완료 증거가 없다.
- 인계 시점에 계속 돌아가는 작업용 PIE는 없다. 이전 에이전트를 기다릴 필요 없이 파일과 검증 보고서를 기준으로 진행한다.

**이 문서의 가장 중요한 미완료 항목은 3절의 main 카메라 저장 → 검증 DLL 적용 → 재시작 반영 확인이다. 새로 에셋이나 고양이 애니메이션을 제작하는 단계가 아니다.**
