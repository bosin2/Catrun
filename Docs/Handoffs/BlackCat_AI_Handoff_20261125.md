# BlackCat 모델·애니메이션 AI 인계서

작성일: 2026-11-25, 한국 시간 기준. 사용자가 토큰 부족으로 다른 AI에게 인계하기 위해 요청한 문서입니다. **이 문서 작성 시점부터 모델 추가 수정은 중단했습니다.**

## 1. 다음 AI가 가장 먼저 알아야 할 현재 상태

**최신 작업은 `PortalCompact20261125`입니다. 이전 버전부터 다시 만들지 마세요.** 짧은 팔다리·큰 얼굴·각진 로우폴리 비율의 새 모델, 개별 애니메이션, 전체 Blender 미리보기, FBX까지 이미 생성했습니다. 아직 최신 결과를 사용자에게 최종 납품·승인받지는 않았습니다.

현재 남은 첫 작업은 **최종 포장 스크립트의 엄격한 이미지 비교 처리**입니다. 모델이나 FBX가 실패한 것이 아닙니다. 저장 후 다시 렌더한 이미지와 기존 이미지 사이에 **0179 프레임의 단 1픽셀, 채널값 1 차이**가 있어 `finalize.py`가 중단됐습니다. 0268·0280 프레임은 완전히 동일합니다. 이 때문에 최신 `handoff.json`과 합쳐진 `Comparison.png`는 아직 생성되지 않았습니다. 모델을 새로 만들거나 전체 모션을 다시 수정할 상황이 아닙니다.

현재 작업 폴더:

`C:/Users/whghk/.codex/worktrees/110f/Catrun/SourceArt/BlackCat/PortalCompact20261125`

## 2. 사용자가 시킨 내용과 우선순위

최신 직접 요청:

> 다리 너무 길어… 귀여운데 동작 보이고 짤막한 캐릭터고 메쉬 붕괴 없게 해줘… 모션은 괜찮은데 역동적인 느낌이 없긴 하네.

이에 따른 확정 방향:

1. **기존 큰 얼굴·눈·각진 로우폴리 정체성 유지.** 사실적인 고양이 해부학 재현이 목적이 아닙니다.
2. **짧고 통통하고 귀여운 캐릭터.** 동작을 보이게 하려고 팔·다리를 길게 늘리면 안 됩니다.
3. **어떤 동작인지 분명히 읽혀야 함.** 사실성보다 실루엣, 포즈, 박자와 자연스러운 연결을 우선합니다.
4. 다리를 접을 때 면이 안쪽으로 말리거나 꽈배기처럼 꼬이고 우글거리는 문제를 없앨 것. 폴리곤을 과도하게 늘려 해결하지 말 것.
5. 최근 사용자는 **동작 순서 자체는 괜찮다**고 했습니다. 순서를 다시 뒤집지 말고 짧은 비율과 역동성을 개선하는 작업입니다.
6. 인터넷의 실제 고양이·그림·영상·3D 모델 참고를 허용했고, Blender 스킬을 적극 활용하고 시각 검토를 반복하라고 했습니다.

최신 포탈 연출 순서:

**포탈 앞으로 걷기 → 앉기 → 귀·고개 갸웃 → 한 앞발로 수직 포탈에 실제 접촉 → 발 회수 → 엉덩이를 뒤로 빼고 좌우 두 번 → 압축 → 도약.**

과거 타 채팅의 ‘서서 바닥에 번진 빛을 먼저 찍고 그 뒤 갸웃’ 요구는 이후 사용자의 직접 수정으로 대체됐습니다. 그 과거 요구로 되돌리면 안 됩니다.

## 3. 완료한 작업 — 최신 Compact 버전

### 모델과 리그

- 팔다리 길이를 약 70%로 줄였습니다. 기본 rest pose와 실제 메시까지 짧은 비율로 재바인드했습니다. 애니메이션 중에만 짧아 보이게 한 것이 아닙니다.
- 얼굴 크기는 유지했습니다. 큰 얼굴을 몸 위쪽으로 가깝게 배치해 짧은 팔보다 얼굴이 먼저 포탈을 통과하지 않도록 조정했습니다.
- 몸통 단면 폭 +8%, 두께 +6%. 짧은 다리의 단면 두께와 발 크기는 유지했습니다.
- 몸통·다리: **568삼각형**. 이전 긴 버전의 632개보다 적습니다.
- 기존 얼굴·눈·귀·꼬리·장신구: **8,256삼각형**, 전체 **8,824삼각형**.
- 총 **108본 = 기존 이름 78개 + 표면 보조본 30개**. 짧은 비율 때문에 **기존 78본의 바인드 자세도 변경**됐습니다.
- 팔·다리의 표면 링을 6개에서 5개로 줄이고, 짧게 접힌 내부 관절을 그대로 외피에 드러내지 않도록 넓은 외곽 형태로 정리했습니다.
- 목·가슴의 급격한 꺾임, 뒷다리 접힘, 손목 링 회전의 겹침을 수정했습니다.
- 뒤통수에 남은 chest/breath 가중치가 짧은 몸통과 다르게 움직여 가시가 생기는 문제를 수정했습니다. 연결된 머리 외피 803정점만 head 100%로 정리했고 원래 얼굴 모양·면 수는 바꾸지 않았습니다.
- 이전 작업에서 원본 눈꺼풀 측면의 겹침을 0.3mm 정리한 내용도 유지했습니다.

### 모션과 역동성

- 최신 순서의 5개 편집 가능한 네이티브 액션을 제작했습니다.
- 접촉은 앞발을 잠깐 모았다가 빠르게 찍고 회수하는 속도 대비를 추가했습니다.
- 두 번 흔들기와 짧은 정지 이후 빠르게 압축하고, 최저 자세를 잠깐 유지합니다.
- 이륙은 긴 팔 대신 상체를 약 16도 위로 기울이며 짧은 앞발을 모아 내미는 형태로 바꿨습니다.
- Blender 미리보기의 상방 이동과 가속을 강화했습니다. 개별 FBX 클립에는 월드 이동을 굽지 않았습니다.
- 걷기→앉기, 앉기→준비, 준비→이륙, 이륙→공중의 연결을 맞췄습니다.
- 마지막으로 준비→이륙 첫 프레임에서 약 3.2mm 차이가 있던 앞발을 고정해 연결을 수정했습니다. 이후 모든 연결의 최대 본 위치 차이는 0.00000025m 미만입니다.

### 실제 검증 결과

- **297개 제작 프레임**에서 몸통·네 다리 각각 자체교차 0, 퇴화면 0, 의미 있는 바닥 관통 0.
- 위 전체 검사 뒤 수정한 이륙 첫 프레임은 이미 검사한 최종 압축 자세와 같게 맞췄고, 별도 네이티브 연결 검사를 통과했습니다. 전체 검사 파일의 pose 해시가 현재 스크립트와 다른 이유입니다.
- 준비 중 앞발 표면 이동: 왼쪽 약 `2.45e-8m`, 오른쪽 약 `2.38e-8m`.
- 준비 중 얼굴과 포탈의 여유: 가장 가까운 확인 프레임 약 **5.8mm**.
- 실제 발바닥의 포탈 접촉 오차: 약 `9.42e-9m`.
- 새 rest 재바인드 전후 정점 차이: 얼굴·장신구 약 `1.07e-7m`, 몸통·다리 약 `8.35e-7m`.
- 새 compact rest의 몸통 구조 QA 통과.
- 모델 FBX 1개 + 애니메이션 FBX 5개를 빈 Blender에 다시 가져와 검사했습니다. **최종 FBX 검사 전부 통과**했습니다.
- 정상 속도 30fps 영상 생성 완료. 시각 검토는 실제 렌더한 키포즈와 연속 프레임으로 했습니다. **전체 영상을 실시간 재생해 지각적으로 검토했다고 주장하지 않았습니다.**
- 검사 범위는 제작된 자세의 각 몸통/다리 내부 자체교차입니다. 모든 임의의 자세나 모든 부품 사이 교차가 없다고 보장하지 않습니다.

## 4. 최신 생성 파일 — 지금 바로 열 수 있음

| 용도 | 절대경로 |
|---|---|
| 모델·개별 액션 | `C:/Users/whghk/.codex/worktrees/110f/Catrun/SourceArt/BlackCat/PortalCompact20261125/SK_BlackCat_CompactPortal.blend` |
| 전체 미리보기 씬 | `C:/Users/whghk/.codex/worktrees/110f/Catrun/SourceArt/BlackCat/PortalCompact20261125/SC_BlackCat_CompactPortal_Review.blend` |
| 30fps 영상 | `C:/Users/whghk/.codex/worktrees/110f/Catrun/SourceArt/BlackCat/PortalCompact20261125/Previews/CompactPortal_30fps.mp4` |
| 이전 비율, 같은 카메라 | `C:/Users/whghk/.codex/worktrees/110f/Catrun/SourceArt/BlackCat/PortalCompact20261125/Previews/Comparison_before.png` |
| 짧은 비율, 같은 카메라 | `C:/Users/whghk/.codex/worktrees/110f/Catrun/SourceArt/BlackCat/PortalCompact20261125/Previews/Comparison_after.png` |
| 새 모델 FBX | `C:/Users/whghk/.codex/worktrees/110f/Catrun/SourceArt/BlackCat/PortalCompact20261125/FBX/SK_BlackCat_CompactPortal.fbx` |
| 설명서 | `C:/Users/whghk/.codex/worktrees/110f/Catrun/SourceArt/BlackCat/PortalCompact20261125/README_KO.md` |

같은 `FBX` 폴더의 개별 애니메이션:

- `AN_CompactPortal_SeatedListenTouch.fbx` — 1–91f, 3초.
- `AN_CompactPortal_HipsBackWiggle.fbx` — 1–53f, 약 1.733초.
- `AN_CompactPortal_SeatedTakeoff.fbx` — 1–13f, 0.4초.
- `AN_CompactPortal_AirReach.fbx` — 1–19f, 0.6초.
- `AN_CompactPortal_WalkReview.fbx` — 1–121f, 4초.

전체 영상은 중복 연결 프레임을 제외해 **293프레임 / 9.7667초**입니다. 전체 씬은 1–293f로 재생됩니다. 주요 키포즈는 `Previews/frames`에 있습니다. `0151.png` 앉기, `0176.png` 접촉, `0268.png` 이륙, `0274.png` 공중을 먼저 보면 됩니다.

**아직 없는 파일:** 최신 폴더의 `handoff.json`, `Previews/Comparison.png`. 아래 포장 작업을 끝내면 생성됩니다.

## 5. 해야 할 작업 — 우선순위 순서

### A. 최종 포장 마무리

1. `PortalCompact20261125/finalize.py`의 실패를 확인합니다. `assert max(pixels.values())==0`에서 멈췄습니다.
2. 비교 결과는 0179프레임 **1픽셀에서 최대 채널 차이 1**, 0268·0280은 차이 0입니다. 메시/본 검사는 이미 통과했습니다. 이를 큰 모델 오류로 오해하지 마세요.
3. 수치·래스터 반올림 차이를 명시해 합리적인 허용 오차로 기록하거나, 최종 저장된 씬에서 해당 프레임을 다시 렌더하고 영상에 반영하는 방식으로 처리합니다. 검사를 몰래 무시하거나 모델 전체를 재제작하지 마세요.
4. `python SourceArt/BlackCat/PortalCompact20261125/finalize.py` 실행. 이 스크립트가 같은 배율의 전후 합성 이미지와 정확한 파일 해시·절대경로·프레임 정보가 담긴 `handoff.json`을 생성합니다.
5. 생성된 파일과 영상 경로를 확인하고 사용자에게 **짧은 비율 전후 비교 + 새 30fps 영상 + Blender/FBX 인계 링크**를 보여줍니다.

### B. 최신 사용자 미술 확인

- 최신 Compact 결과는 아직 사용자가 보거나 승인한 상태가 아닙니다. 짧은 비율이 충분한지, 역동성이 원하는 정도인지 사용자의 판단이 남았습니다.
- 사용자가 모션 순서는 괜찮다고 했으므로 임의로 순서를 다시 만들지 마세요.
- 검토자는 준비 자세의 정지컷만 보면 네 발 서기로도 읽힐 수 있다고 지적했습니다. 영상에서 앉기→가슴 낮춤→엉덩이 후퇴가 읽히는지 확인할 가치가 있습니다. 이것은 필수 재작업 확정 사항이 아닙니다.
- 실제 고양이처럼 만들겠다며 얼굴을 작게 하거나 다리를 다시 늘리지 마세요.

### C. UE 통합 — 아직 하지 않음

- **기존 UE 스켈레톤에 애니메이션만 임포트하면 안 됩니다.** 새 108본 모델과 변경된 rest를 새 스켈레톤에 함께 가져와야 합니다.
- 기존 UE 모델, 공유 스켈레톤, 맵, 시퀀스는 이 작업에서 수정하지 않았습니다.
- 기존 스테이지 연출 담당 AI가 새 모델 사용 방식, 카메라·포탈 위치·이동 궤적을 통합해야 합니다. 별도 지시 없이 다른 채팅에 메시지를 보내거나 UE 에셋을 덮어쓰지 마세요.
- 원래 전체 출발 연출 목표는 9–12초이며, 기존 문/정면 걷기 등을 합친 UE 전체 길이는 별도로 조정해야 합니다. 이 Blender 영상 9.77초가 곧 UE 전체 시네마틱 길이라는 뜻은 아닙니다.
- 최종 실제 스테이지 1 출구 진입, 정상 속도 연속 영상, 발 접촉·정적·두 번 흔들기·압축·도약의 카메라 가독성 검증은 아직 남았습니다.

## 6. 프레임·좌표·임포트 계약

- 30fps. Blender 전방 -Y, 위 Z. 소스 단위 m.
- 왼쪽 앞발 `paw_F_L`로 접촉합니다.
- 새 포탈 기준면: 모델 로컬 **Y=-0.0799028556m**.
- 발바닥 접촉 중심: 약 **(0.0274199955, -0.0799028556, 0.0521000028)m**.
- 접촉 클립: 귀 20–27f, 고개 24–32f, 정지 32–43f, 앞발 모으기 49–52f, 접촉 55–60f, 발 복귀 72f.
- 준비 클립: 두 번 흔들기 14–38f, 멈춤 38–41f, 빠른 압축 44–50f, 최저 압축 유지 50–53f.
- 이륙의 실제 마지막 뒷발 접지/첫 이륙 프레임은 `QA/contact_and_ground.json`에서 `finalize.py`가 계산하도록 되어 있습니다. 코드상 예상은 마지막 접지 5f, 첫 이륙 6f입니다. 생성된 handoff의 실측 결과를 우선하세요.
- 개별 클립은 제자리. 월드 이동은 미리보기 씬에만 있습니다.
- 기존 PortalJumpIn f18 접합 계약은 최신 버전에서 사용하지 않습니다. 짧은 전용 이륙·공중 클립을 사용합니다.
- FBX: -Y forward/Z up, leaf bone 없음, 매 프레임 베이크, 키 단순화 0.
- 권장 UE import_uniform_scale=100은 이전 원본과 같은 내보내기 계약에 따른 값입니다. **새 모델의 실제 UE 크기는 아직 검증하지 않았습니다.**
- 이전 UE 통합 담당자가 작은 리그의 기본 애니메이션 키 감축에서 앞발 약 1.48cm 드리프트를 관찰했습니다. 프레임 보존/LeastDestructive 본 압축을 검토해야 합니다.

## 7. 구현 파일과 재실행 시 주의점

최신 폴더 내 역할:

| 파일 | 역할 |
|---|---|
| `create_revision.py` | 기존 동작을 읽어 짧은 비율로 변환, 타이밍·몸 기울기·접지 보정 |
| `body_surface.py` | 568삼각형 외피, 30개 표면 본, 짧은 관절의 외곽과 링 연결 |
| `retained_mesh_cleanup.py` | 눈꺼풀 겹침 정리와 머리 외피 웨이트 정리 |
| `compact_rebind.py` | 짧은 neutral을 실제 rest로 적용하고 모든 액션을 월드 본 행렬 기준으로 다시 베이크 |
| `bake_review.py` | 개별 액션·모델 파일·전체 씬·프레임 렌더 생성 |
| `export_revision.py` | 모델/애니메이션 FBX 6개와 빈 씬 재가져오기 검사 |
| `verify_compact.py` | 연결·앞발 접지·포탈 여유·기본 메시 QA·재열기 렌더·전후 비교 렌더 |
| `finalize.py` | 최종 비교 이미지·handoff·해시 포장. 현재 1픽셀 비교에서 중단 |

**의존 파일을 지우지 마세요.** 최신 스크립트는 아래 과거 폴더의 일부 코드를 재사용합니다. 결과물이 거절된 버전이라도 소스 의존성입니다.

- `SourceArt/BlackCat/PortalSeated20261125/create_revision.py`
- `SourceArt/BlackCat/PortalEntry20261125/build_portal.py`
- `SourceArt/BlackCat/RigV2/Scripts/build_sit_sleep.py`
- `C:/Users/whghk/Desktop/CastleKit/BlackCat/PortalCinematic/SK_BlackCat_PortalCinematic.blend`

최신 `create_revision.py`를 다른 스크립트에서 실행할 때는 **`# BEGIN_PREVIEW`** 앞부분을 사용하세요. 과거처럼 `cam=preview_setup()` 문자열로 자르면 내부 문자열에서 잘려 오류가 납니다.

재바인드의 중요한 함정: 혼합 웨이트 꼬리를 굽힌 자세 그대로 새 rest로 만들면 이후 모션에서 약 10.7mm 틀어졌습니다. 수정 완료된 방법은 **기존 꼬리 모든 본에 동일한 rest translation을 적용**하는 것입니다. 머리·장신구도 구성요소별 동일한 rigid bind 변환을 사용합니다. 이 부분을 단순한 ‘현재 평가 메시를 rest로 저장’으로 되돌리지 마세요.

FBX 애니메이션 전용 내보내기는 메시 BindPose가 없으므로 `export_revision.py`에 원래/현재 rest를 FBX Model 기본값으로 쓰는 `rest_model_writer`가 있습니다. 제거하면 클립 첫 포즈가 bind로 쓰여 호환성이 깨집니다. 재임포트 검사에서는 `anim_offset=0`과 원래 `use_connect` 값을 복원합니다.

## 8. 실행 환경

- 작업 루트: `C:/Users/whghk/.codex/worktrees/110f/Catrun`
- 셸: PowerShell.
- Blender: `C:/Program Files/Blender Foundation/Blender 5.2/blender.exe` (확인 버전 5.2.1 LTS).
- Python, Pillow, numpy, ffmpeg 사용 가능.
- **다른 작업자의 live Blender/UE 세션을 건드리지 말고 격리된 background Blender를 사용하세요.**

필요할 때만 전체 베이크하는 명령:

```powershell
Set-Location 'C:/Users/whghk/.codex/worktrees/110f/Catrun'
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --factory-startup -b 'C:/Users/whghk/Desktop/CastleKit/BlackCat/PortalCinematic/SK_BlackCat_PortalCinematic.blend' -t 2 --disable-autoexec --python-exit-code 1 -P SourceArt/BlackCat/PortalCompact20261125/bake_review.py
```

현재는 모델·액션 수정 없이 포장만 남았으므로 위 전체 베이크부터 다시 할 필요가 없습니다.

원본 파일은 보존했습니다:

`C:/Users/whghk/Desktop/CastleKit/BlackCat/Final/SK_BlackCat_Final.blend`

확인한 SHA256: `07a220d70764ff0cda34e77da3344797847b77547de8df7aa88a5eb6df8c3327`.

## 9. 과거 작업의 상태 — 최신과 혼동 금지

### SitSleep20261125

과거 요청한 앉은 자세, 귀 갸웃·꼬리 탁탁, 수면 꼬리 수정 작업 사본입니다.

- `C:/Users/whghk/.codex/worktrees/110f/Catrun/SourceArt/BlackCat/SitSleep20261125/SK_BlackCat_SeatedLowPoly.blend`
- `C:/Users/whghk/.codex/worktrees/110f/Catrun/SourceArt/BlackCat/SitSleep20261125/SK_BlackCat_SleepTailFixed.blend`

이전 작업 기록상 수면은 꼬리 이외 본을 보존하고 꼬리 급격한 접힘과 바닥 관통을 줄였습니다. 이번 최신 Compact 턴에서 수면 결과를 다시 검증하거나 Compact 새 리그로 이전하지 않았습니다. **이 과거 파일이 최신 짧은 모델에도 적용됐다고 말하면 안 됩니다.** 독립적인 과거 산출물로 보존합니다.

### PortalEntry20261125 — 대체된 방향

원본 78본 스켈레톤 호환의 서서 바닥 찍기/갸웃/준비/이륙 연결 3개 FBX와 `.blend`를 만들었고 타 채팅이 UE 임포트까지 확인했습니다. 하지만 이후 사용자가 **앉아서 갸웃한 뒤 포탈에 접촉**하라고 수정했으므로 최신 요구에는 맞지 않습니다. 과거 handoff에 `ready_for_import=true`가 남아 있어도 현재 승인본이 아닙니다.

### PortalSeated20261125 — 다리가 길어 사용자 거절

앉아서 접촉하는 순서, 632삼각형 몸통·다리, 112본(78+34), 영상·FBX를 만들었습니다. 사용자가 모션 순서는 괜찮으나 **다리가 너무 길다**고 했습니다. 최신 Compact는 이 버전을 짧게 수정한 것입니다. 이 폴더의 handoff를 최종본으로 다시 납품하지 마세요.

## 10. 타 채팅·원본 참조

- 스테이지 통합 담당 채팅 ID: `01a21157-6b87-7bb0-8ad2-1b7f5c569e9e`.
- 해당 작업 사본: `C:/Users/whghk/.codex/worktrees/7b1c/Catrun`.
- 이전 UE 참조: `C:/Users/whghk/.codex/worktrees/7b1c/Catrun/Saved/PortalEntry20261125/Reference/reference.json` 및 Idle/PortalJumpIn reference FBX.
- 기존 UE 스켈레톤: `/Game/Characters/BlackCat/Final/Skeletons/SKEL_BlackCat_Final`.
- 기존 JumpIn: `/Game/Characters/BlackCat/Final/Animations/Cinematics/AN_BlackCat_PortalJumpIn`.
- 다른 제작 요청 전달 채팅: `01a211a0-4d53-7fa1-ae2a-56870000867f`.

새 Compact 모델은 이 기존 78본 스켈레톤에 애니메이션만 넣는 계약을 대체합니다. 명시적인 사용자 지시 없이 다른 채팅으로 메시지를 보내지는 않았습니다.

## 11. 적용한 스킬과 참고 자료

외부 Blender 스킬 24개를 추가해 총 33개를 설치했습니다. 필요한 지침을 직접 읽어 적용했고, 외부 사람 고용이나 유료 생성은 하지 않았습니다.

설치 목록:
`C:/Users/whghk/.codex/worktrees/110f/Catrun/SourceArt/BlackCat/PortalSeated20261125/skill_inventory.json`

핵심 스킬 경로:

- `C:/Users/whghk/.codex/skills/blender-core/SKILL.md`
- `C:/Users/whghk/.codex/skills/blender-animation/SKILL.md`
- `C:/Users/whghk/.codex/skills/blender-character-rigging/SKILL.md`
- `C:/Users/whghk/.codex/skills/blender-asset-qa/SKILL.md`
- `C:/Users/whghk/.codex/skills/blender-export-pipelines/SKILL.md`
- Scenario Blender animation/rigging/previs 스킬도 같은 skills 폴더에 있습니다.

참고한 레퍼런스:

- 앉아서 유리에 앞발 접촉: https://www.youtube.com/watch?v=XFxOXZxUt_U
- 가슴을 낮추고 도약: https://www.youtube.com/watch?v=RbTU1OMSXzo
- 엉덩이 흔들기: https://www.youtube.com/watch?v=gDXlnyFGjR0
- 로우폴리 3D 참고: https://sketchfab.com/3d-models/low-poly-cat-f43a414c031e44a28453d74a190397d1
- 단순한 면·실루엣 참고: https://sneznyj.itch.io/cube-cats

## 12. 인수 AI에게 주는 짧은 실행 지시

> 이 문서의 최신 PortalCompact 산출물부터 확인하라. 사용자는 기존 얼굴과 로우폴리를 유지한 짧고 귀여운 캐릭터, 읽히는 모션과 면 붕괴 방지를 원한다. 모델·FBX·영상은 이미 생성됐으며, 최종 포장 스크립트만 1픽셀 반올림 차이로 중단됐다. 이를 근거 있게 처리하고 handoff와 전후 비교를 생성해 사용자에게 보여라. 과거 긴 다리 버전이나 서서 바닥 찍는 모션으로 돌아가지 말고, 기존 UE 공유 에셋을 덮어쓰지 마라. UE 실제 통합과 사용자 미술 승인은 아직 완료되지 않았다.
