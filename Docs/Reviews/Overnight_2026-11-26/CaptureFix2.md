# Fix2: 포획 중 표식 구슬 숨김, Stage3 포획 카메라 튐 (2026-11-26)

기준: 본 프로젝트 `21f22e7`. 후보 Source를 이 커밋과 같게 맞춘 뒤 작업했다. 본 프로젝트는 바꾸지 않았다.

## 적용
1. main에서 `git apply --check --ignore-whitespace capture_fix2.patch` → `git apply --ignore-whitespace capture_fix2.patch` (08:41 `--check` 통과)
2. 헤더가 바뀌므로 전체 재빌드(오래된 obj 주의)
3. 되돌리기: `git apply -R capture_fix2.patch`

## 바뀐 것 (5개 파일, 에셋·맵 변경 없음)
| 파일 | 내용 |
|---|---|
| `CatrunMarkSubsystem.h/.cpp` | `SetVisualSuppressed(Owner, bool)`: 표식 구슬과 붙은 붉은 점광원의 **보이기만** 끈다. 여러 소유자가 겹쳐도 되고, 마지막 소유자가 풀면 다시 보인다. 사라진 소유자는 다음 갱신 때 정리되어 구슬을 계속 숨기지 못한다. 숨긴 동안 새로 찍힌 표식도 숨긴 채로 만든다. 표식 여부·따라오는 갑옷·타이머는 그대로 |
| `CatrunCapturePresentationComponent.h/.cpp` | 포획이 성립한 시점(갑옷 준비 뒤)에 숨김을 잡고, `Cleanup`(중단·실패·종료·EndPlay 모두 여기를 거침)에서 푼다. 성공한 포획은 재시작으로 레벨이 다시 열리므로 표식도 새로 시작한다 |
| 같은 컴포넌트 | 카메라가 막혀 목표 위치로 바로 옮기거나(snap), 진입 블렌드가 끝난 뒤 한 프레임에 `CameraCutDistance`(기본 20cm)보다 많이 움직이면 `SetGameCameraCutThisFrame`. 진입 블렌드의 빠른 이동(최대 62cm)은 컷으로 치지 않는다. 카메라 위치·구도 선택은 그대로 |
| `Tests/CapturePresentationPolishTests.cpp` | 새 네이티브 테스트 3개 |

새 테스트:
- `Catrun.Monsters.MarkVisualSuppressionKeepsMark`: 숨김 중 표식 유지, 겹친 소유자, 숨김 중 새 표식, 사라진 소유자 정리
- `Catrun.PrototypeAI.CaptureHidesMarkVisualOnlyWhileOwning`: 실제 포획 시작 → 구슬·빛 숨김, 표식 유지 → 중단 뒤 다시 보임
- `Catrun.PrototypeAI.CaptureCameraCutsOnlyJumps`: 68cm snap·정착 뒤 튐은 컷, 2.4cm 흔들림·62cm 진입 블렌드는 컷 아님

## 검사 (후보, 전체 재빌드 뒤)
| 검사 | 결과 |
|---|---|
| 빌드 | 전체(컴파일 90개) 성공, 이어서 테스트 수정 뒤 증분 성공 |
| 네이티브 전체 `Catrun` (NullRHI) | **실패 0**: 성공 160 + 경고 10, 미실행 0 (`D:/CatrunWork/cine-polish/Tests/fix2b`). 첫 실행은 새 테스트가 추상 클래스 `UObject`를 만들다 ensure 1건으로 실패해 테스트만 고쳤다 |
| 포획 재생 Stage2·Stage3 각 3사례 (d3d12, 30fps, 재확인 때와 같은 배치) | 오류 0. 6사례 모두 카메라 이동량 상위값이 수정 전과 같다(코드가 구도를 바꾸지 않음) |
| Stage2 `Armor_03` | 수정 전 26프레임부터 끝까지 보이던 주황 구슬과 붉은빛이 수정 후 포획 내내 없다 (`Frames/mark_orb_Stage2_2.jpg`) |
| Stage3 `S3_Armor_LobbyPatrol` | 130프레임 68cm 이동은 같지만, 수정 전 크게 번지던 프레임이 수정 후 번짐 없는 컷이 된다 (`Frames/camera_cut_Stage3_1.jpg`) |

영상(정상 속도, 왼쪽 수정 전·오른쪽 수정 후): `D:/CatrunWork/cine-polish/Video/fix2_cap_Stage2_2.mp4`, `fix2_cap_Stage3_1.mp4`. 수정 전 프레임은 같은 날 07:32 재확인 실행(`Runs/merged2-073200`), 수정 후는 `Runs/fix2-083010`.

## 한계
- 68cm 자리 이동 자체는 남는다(한 프레임 점프 컷). 부드럽게 옮기려면 막힌 경로를 돌아가는 카메라 경로가 필요해 이번에는 컷 표시만 했다.
- 고양이가 포획 중 새로 찍히는 경우는 네이티브 테스트로만 확인했다(재생 사례 없음).
- 위치 배치·적 정지 fixture를 썼다. 손플레이가 아니다.
