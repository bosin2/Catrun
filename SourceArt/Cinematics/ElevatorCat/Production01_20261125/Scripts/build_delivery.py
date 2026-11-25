import json,pathlib,csv,hashlib,math
OUT=pathlib.Path(__file__).resolve().parents[1]
read=lambda p:json.loads((OUT/p).read_text())
m=read('manifest.json');q=read('QA/numeric_qa.json');ri=read('QA/reimport.json');p=read('QA/preservation_reload.json');g=read('QA/contact_geometry.json');b=read('QA/boundaries.json');samples=read('QA/frame_samples.json')
assert p['original_data_equal_after_save_reload']
assert all(x['finite'] and x['min_mesh_game_z_cm']>=-.001 for x in q.values())
assert all(x['hierarchy_equal'] and x['bones']==78 and x['actions']==1 and x['frame_range']==x['expected_range'] and x['max_joint_position_error_game_cm']<.001 and x['max_rest_joint_error_game_cm']<.001 and x['max_skinning_matrix_component_error']<.0001 and x['nonfinite']==0 for x in ri)
assert max(x['max_matrix_delta'] for x in b)<1e-5
assert max(x['head_ring_surface_intersections'] for x in g['master'])==0
assert min(x['foot_vertices_min_edge_clearance_cm'] for x in g['peek'])>0
assert q[m['master']['action']]['max_contact_error_cm']<.01
for clip in m['clips']:
 rows=samples[clip['action']];clip['root_start_native_m']=rows[0]['root_native_m'];clip['root_end_native_m']=rows[-1]['root_native_m'];clip['root_start_game_cm']=rows[0]['root_game_cm'];clip['root_end_game_cm']=rows[-1]['root_game_cm']
 clip['preview']='Previews/'+clip['id']+'_'+clip['action'].replace('AN_BlackCat_Elevator_','')+'.mp4'
 assert (OUT/clip['fbx']).stat().st_size>1000 and (OUT/clip['preview']).stat().st_size>1000
m['status']='Review delivery. C05 tail volume puff excluded. Original skin folds retained; no zero-self-intersection claim. Unreal import and runtime outside scope.'
m['preview_sampling_fps']=15;m['new_skeleton_bones']=0;m['new_morph_targets']=0;m['unreal_imported']=False
(OUT/'manifest.json').write_text(json.dumps(m,indent=2))
with (OUT/'root_contact_tracks.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.writer(f);w.writerow(['action','frame','seconds','root_native_x_m','root_native_y_m','root_native_z_m','root_game_x_cm','root_game_y_cm','root_game_z_cm','front_L_x_cm','front_L_y_cm','front_L_z_cm','front_R_x_cm','front_R_y_cm','front_R_z_cm','grip_active'])
 for name,rows in samples.items():
  for r in rows:w.writerow([name,r['frame'],r['seconds'],*r['root_native_m'],*r['root_game_cm'],*r['front_pad_game_cm']['L'],*r['front_pad_game_cm']['R'],r['front_ring_contact']])
with (OUT/'events.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.writer(f);w.writerow(['clip','event','frame','seconds'])
 for e,fr in m['events_master'].items():w.writerow(['MASTER',e,fr,(fr-1)/30])
 for cid,events in m['events'].items():
  for e,fr in events.items():w.writerow([cid,e,str(fr),str([(v-1)/30 for v in fr]) if isinstance(fr,list) else (fr-1)/30])
summary={'original_preservation_pass':True,'animation_only_fbx_count':len(ri),'bone_count':78,'vertices':p['snapshots'][0]['vertices'],'triangles':p['snapshots'][0]['triangles'],'material_slots':7,'max_grip_marker_error_game_cm':q[m['master']['action']]['max_contact_error_cm'],'min_head_ring_clearance_game_cm':min(x['min_head_to_ring_cm'] for x in g['master']),'head_ring_surface_intersections':0,'min_support_foot_edge_margin_game_cm':min(x['foot_vertices_min_edge_clearance_cm'] for x in g['peek']),'max_fbx_joint_error_game_cm':max(x['max_joint_position_error_game_cm'] for x in ri),'max_fbx_rest_error_game_cm':max(x['max_rest_joint_error_game_cm'] for x in ri),'max_fbx_skinning_matrix_error':max(x['max_skinning_matrix_component_error'] for x in ri),'max_boundary_matrix_delta':max(x['max_matrix_delta'] for x in b),'tail_puff_delivered':False,'unreal_runtime_verified':False,'skin_self_intersections_zero':False,'visual_check':'All 15fps preview samples, three views, reviewed in sequential temporal sheets; close renders for grip/landing/startle. Not a full 30fps real-time playback observation.'}
(OUT/'QA/delivery_summary.json').write_text(json.dumps(summary,indent=2))
names=['고리 올려다보기·준비','높이 점프해 고리 잡기','매달려 당기기','놓기·착지','출발 놀람·꼬리 반응 — 부풀기 제외','아래로 빼꼼','상승 균형 대기','식빵 대기','식빵에서 놀라 일어나기']
table='\n'.join(f'| {c["id"]} | {n} | 1–{c["frames"][1]} | {c["seconds"]:.3f}초 | {"루프" if c["loop"] else "단발"} |' for c,n in zip(m['clips'],names))
doc=f'''# 승강기 고양이 애니메이션 제작본

2026-11-25 · 기존 BlackCat 외형/78본 보존 · 30fps · 검토용 납품

9개 Action과 점프→당김→착지 연속 마스터, 애니메이션 전용 FBX 10개를 제작했다. **C05의 꼬리 부풀기는 제외**되어 있다. 놀람·귀 반응·꼬리 반응은 제작했다. 사용자 아트 승인 및 Unreal 연결/재생은 별도다.

## 열어볼 파일

- [전체 3방향 모션 프리뷰](Previews/ALL_09_ThreeViews.mp4)
- [클립별 프리뷰 페이지](Previews/index.html)
- [Blender 원본](SK_BlackCat_Elevator.blend)
- [애니메이션 FBX 폴더](FBX/)
- [정량 검수 요약](QA/delivery_summary.json)
- [프레임별 루트·접촉 CSV](root_contact_tracks.csv), [이벤트 CSV](events.csv), [manifest](manifest.json)
- 최종 접촉 근접 렌더: `QA/Stills_Final/`. 이전 `QA/Stills/`와 기존 sheet 파일은 수정 이력이며 최종 판정 근거가 아니다.

## 클립

| ID | 동작 | 프레임 | 길이 | 반복 |
|---|---|---|---|---|
{table}

모든 이름은 `AN_BlackCat_Elevator_`로 시작한다. C08은 기존 Sleep의 식빵 자세·호흡을 새 Action으로 복제했다. C09는 기존 StandUp을 짧게 재타이밍하고 놀람·눈/귀 선행을 추가했다. 원래 11개 Action은 수정하지 않았다.

## 보존 및 현재 게임과의 대조

현재 BP_Cat의 CharacterMesh0를 읽기 전용으로 조회하여 `/Game/Characters/BlackCat/Final/Meshes/SK_BlackCat_Final`, Mesh Scale (2,2,2), 상대 Z -24cm, Yaw -90도를 확인했다. 게임 스켈레톤의 78본 이름과 원본 후보가 일치한다. 근거는 `QA/live_character.json`, `QA/live_unreal_rig.json`이다. 엔진 내부 메시 정점/UV를 역수출하여 원본과 완전 비교한 것은 아니다.

원본 후보의 SHA256은 `{p['source_sha256']}`이며 승강기 납품 측정 원본과 같다. 제작 전후 원본 파일 해시 및 작업 blend 저장/재로드 후 메시 정점·토폴로지·UV·웨이트·재질 노드 값·오브젝트 변환·본 이름/부모/Rest Pose·원래 11개 Action 키/핸들을 비교했다. 모두 동일하다. 고양이는 {summary['vertices']:,} vertices, {summary['triangles']:,} triangles, 7 material slots, 78 bones다. 새 본/모프/메시/웨이트 수정은 없다.

열려 있던 Blender 사용자 장면은 사용하지 않았다. 별도 background 프로세스만 사용했다. 승강기 원본은 읽고 작업 blend에 참조 사본을 추가했으며 원본 파일을 저장하지 않았다.

## 좌표·루트 계약

- 원본 고양이는 native meter, -Y 전방, +Z 위이며 Mesh/Armature Scale 1을 유지한다. 게임 배율은 2다.
- 검사용 승강기 사본만 전체를 균일하게 0.5배로 배치했다. 따라서 **게임 cm = preview native m × 200**이다. 발판 상면 중앙이 검사용 원점이다. 고양이를 늘려 고리에 맞추지 않았다.
- FBX에는 기존 root 본의 이동이 포함된다. 점프 Actor 경로나 별도 Z 이동을 동시에 적용하면 이중 이동이 된다. 기존 스켈레톤을 선택하여 애니메이션만 임포트하고 메시 생성·Skeleton 업데이트·레퍼런스 포즈 변경을 하지 않는다.
- C02→C03→C04는 마스터 1–25 / 25–55 / 55–102에서 분리했다. 경계 프레임은 중복된 같은 포즈다. C03/C04 루트는 원점으로 재정규화하지 않았다. 각 클립의 시작/끝 루트와 오프셋은 manifest에 있다. 연속 시네마틱에는 마스터 사용이 가장 단순하다.
- root Z 최고점은 게임 89cm이며 고리 당김 동안 18cm 내려온다. 월드 중력/캐릭터 점프 물리 결과가 아니라 제작된 시네마틱 궤적이다.
- 기존 Actor의 캡슐 중심과 Mesh 상대 Z -24cm는 별도 변환이다. CSV는 발판/메시 기준이며 Actor 절대 위치 자료가 아니다. 엔진 배치에서 이 기준을 대조해야 한다.

## 접촉·이벤트

실제 승강기 소켓은 고리 하단 Z130→112cm다. 링 표면에서 좌우 접점을 별도로 잡았으며 게임 기준 X ±6.419cm, Y -24.707cm, Z132.431cm→114.431cm다. 좌우 발을 같은 점에 겹치지 않았다. 참조 ROOT_ControlPull과 사슬/고리는 함께 18cm 내려갔다가 놓은 뒤 복귀한다.

마스터 프레임: 이륙 7, 양 앞발 잡기 24, 당김 시작 29, 최대 당김 48, 놓기 55, 착지 73, 안정 102. 출발 충격은 C05 f9이며 당김 중에 객실을 출발시키는 이벤트는 없다. C09는 1–37프레임 식빵을 읽고 f38 충격, f39 눈을 뜨고 f42부터 일어난다. 이번 작업은 무음이다.

## 검사 결과와 한계

- 원본 보존 및 저장/재로드 비교 통과.
- 전 프레임 변환 유한값, 바닥 최저점 검사 통과. 준비·균형·놀람·빼꼼의 명시적 접지 구간은 월드 발 위치를 고정했다.
- 고리 접촉 마커 최대 오차 {summary['max_grip_marker_error_game_cm']:.8f}cm. 실제 앞발 메시와 링의 표면 접촉도 확인했다. 발로 감싸는 부분의 작은 표면 겹침은 의도한 접촉이다.
- 머리–링 표면 교차 0건, 최소 간격 {summary['min_head_ring_clearance_game_cm']:.3f}cm. 빼꼼 지지 발 메시의 바닥 가장자리 최소 여유 {summary['min_support_foot_edge_margin_game_cm']:.3f}cm. 머리만 가장자리 밖으로 내민다.
- 별도 Blender 프로세스에서 FBX 10개 재임포트: 78본 계층, 1 Take, 프레임 범위, 30fps, Armature Scale 1 확인. 최대 관절 위치 오차 {summary['max_fbx_joint_error_game_cm']:.8f}cm, Rest joint 오차 {summary['max_fbx_rest_error_game_cm']:.8f}cm, skinning matrix 성분 오차 {summary['max_fbx_skinning_matrix_error']:.8f}.
- 애니메이션 전용 FBX의 기본 본 포즈를 올바르게 기록하기 위해 export 직전 임시 f0 Rest 키를 사용하고, Take 범위는 1–끝으로 한정했다. 임시 키는 제작 blend와 납품 Take에 포함되지 않는다. Blender 재임포트는 `anim_offset=0`으로 검사했다.
- 3방향 프리뷰는 실제 Blender EEVEE 결과이며 15fps로 전체 길이를 샘플링했다. 모든 샘플을 순차 temporal sheet로 검토했다. 30fps 전 프레임 정량 검사와 구분한다. 실시간 전체 영상 재생을 직접 관찰한 검사는 아니다.
- 원본 Idle/Sleep부터 눈꺼풀·방울·접합부 등의 비인접 삼각형 교차가 검출된다. 새 자세에서도 피부 접힘부 교차가 남아 있다. 따라서 **전신 자체 교차 0 또는 최종 아트 합격을 선언하지 않는다**. 외형·웨이트 보존 조건에 따라 원본 메시를 임의 수리하지 않았다. `QA/skin_intersections.json`에 원본 기준과 새 자세의 표본을 함께 기록했다.
- Unreal 임포트·맵/BP/코드·Sequencer·런타임·소리·Git push는 수행하지 않았다.

## 꼬리 부풀기 예외

기존 7개 tail 본에 방사 방향 스케일을 주어 Blender에서 두께를 늘리고 길이를 유지하는 실험을 했다. 하지만 애니메이션 전용 FBX 재임포트에서 꼬리 관절이 최대 약 7.48cm 어긋나 제외했다. 납품용 C05는 단순 꼬리 반응이며 이를 '꼬리 펑 완료'로 취급하지 않는다.

실험은 `Experiments/SK_BlackCat_Elevator_TailPuff_Unvalidated.blend`, 실패 근거는 `QA/tail_puff_failed_reimport.json`에 분리했다. 이 파일은 엔진용 납품 원본이 아니다. 최소 예외 후보는 기존 메시의 `TailPuff` 모프 1개이며 별도 승인 전에는 추가하지 않는다.

## 재현 순서

원본 blend를 별도 background Blender에서 열어 `Scripts/author.py`, 생성된 작업 blend에서 `finalize_motion.py` → `remove_unportable_puff.py` → `settle_collar.py` → `refine_collar.py` 순서로 실행한다. 이후 `qa_export.py`, `contact_geometry_qa.py`, `skin_intersections.py`, `verify_preservation.py`, 새 빈 프로세스의 `reimport.py`를 실행한다. `author.py`만 재실행하면 미검증 꼬리 실험 상태가 포함되므로 중간 산출물을 납품본으로 사용하지 않는다. 최종 렌더는 `render_review.py -- full`, 패키징은 `package_previews.py`다.
'''
(OUT/'DELIVERY.md').write_text(doc,encoding='utf-8')
html=OUT/'Previews/index.html'
if html.exists():html.write_text(html.read_text(encoding='utf-8').replace('<h1>Elevator Cat · 9 Animations</h1>','<h1>Elevator Cat · 9 Animations</h1><p><strong>C05: tail flick only. Tail volume puff is excluded after failed FBX round-trip. Review delivery; original skin folds remain.</strong></p>'),encoding='utf-8')
paths=[OUT/'SK_BlackCat_Elevator.blend',OUT/'manifest.json',OUT/'DELIVERY.md',*sorted((OUT/'FBX').glob('*.fbx')),*sorted((OUT/'Previews').glob('*.mp4'))]
(OUT/'delivery_sha256.json').write_text(json.dumps({str(f.relative_to(OUT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in paths},indent=2))
print('DELIVERY_CHECKS_PASSED',summary)
