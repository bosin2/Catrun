import json,hashlib
from pathlib import Path
import numpy as np
from PIL import Image
HERE=Path(__file__).parent.resolve()
def read(p):return json.loads((HERE/p).read_text(encoding='utf8'))
native=read('QA/native_joins_and_bind.json');roundtrip=read('QA/fbx_roundtrip.json');contract=read('QA/export_contract.json');ground=read('QA/contact_and_ground.json')
pixel={}
for f in [179,268,280]:
 x=np.asarray(Image.open(HERE/f'Previews/frames/{f:04}.png')).astype(int);y=np.asarray(Image.open(HERE/f'QA/native_reopen_{f:04}.png')).astype(int);pixel[str(f)]=int(np.abs(x-y).max())
assert all(x==0 for x in pixel.values()),pixel
assert all(not x['bind_errors'] and (x['pose_roundtrip'] is None or x['pose_roundtrip']['pass']) for x in roundtrip)
assert max(x['max_position_error_m'] for x in native['joins'])<1e-6
clips=contract['clips']
beats={
 'AN_Portal_SeatedListenTouch':{'sit':[1,19],'ear':[20,27],'head_tilt':[24,32],'hold':[32,43],'paw_reach':[46,57],'contact':[57,64],'return':[65,79],'used_paw':'paw_F_L','palm_center_local_m':[.042,-.105,.068]},
 'AN_Portal_HipsBackWiggle':{'hips_back':[1,14],'two_wiggles':[14,38],'sway_extrema':[17,23,29,35],'sway_amplitude_m':.009,'stop':[38,41],'compression':[41,53],'front_paws_locked':True},
 'AN_Portal_SeatedTakeoff':{'front_paws_extend':[1,6],'last_hind_support_frame':9,'first_hind_liftoff_frame':10,'next':'AN_Portal_AirReach','next_frame':1,'minimum_blend_frames':0},
 'AN_Portal_AirReach':{'existing_PortalJumpIn_used':False,'note':'Custom reaching airborne pose; supersedes previous f18 JumpIn join.'},
 'AN_Portal_WalkReview':{'last_step_flows_into_seated_clip':True,'final_frame_matches_touch_first':True}}
for c in clips:c['beats']=beats[c['action']]
files=[HERE/'SK_BlackCat_SeatedPortal_Review.blend',HERE/'SC_BlackCat_PortalReview.blend',HERE/'Previews/PortalSeated_30fps.mp4']+list((HERE/'FBX').glob('*.fbx'))
out={
 'status':'revised_blender_motion_and_new_rig_ready_for_review','ready_for_new_rig_import_review':True,'ready_for_existing_78_bone_animation_only_import':False,'visual_user_approval':False,'ue_runtime_verified':False,
 'supersedes':'PortalEntry20261125 standing ground-tap clips; latest user requires seated tilt then vertical portal contact',
 'blend':str(files[0]),'full_sequence_blend':str(files[1]),'normal_speed_video':str(files[2]),'mesh_fbx':contract['mesh_fbx'],'clips':clips,
 'fps':30,'preview_frames':293,'preview_video_duration_seconds':293/30,'body_triangles':632,'retained_face_and_accessory_triangles':8256,'total_triangles':8888,'original_bone_count':78,'additional_surface_bones':34,'total_bones':112,
 'original_bind_unchanged':native['original_bind_max_matrix_difference']==0,'original_parents_unchanged':native['original_parents_preserved'],'root_motion_in_individual_clips':False,'preview_only_actor_trajectory':True,
 'recommended_ue_import':{'import_uniform_scale':100,'scale_verified_in_ue':False,'basis':'same export axis/unit contract as previously UE-verified original source','convert_scene':True,'convert_scene_unit':True,'force_front_x_axis':False,'preserve_local_transform':False,'sample_rate':30,'compression':'Preserve per-frame keys; default key reduction previously caused visible foot drift on this small rig.'},
 'preview_sequence_1based':{'walk':[1,120],'seated':[121,210],'prepare':[211,262],'takeoff':[263,274],'flight':[275,293]},
 'qa':{'native':native,'native_reopen_pixel_max_differences':pixel,'contact_max_plane_error_m':max(abs(x) for x in ground['contact_distance_m']),'body_min_z_by_clip':{n:min(f['body_min_z'] for f in rows) for n,rows in ground['frames'].items()},'fbx_roundtrip':str(HERE/'QA/fbx_roundtrip.json'),'surface_scan':str(HERE/'QA_Surface/motion_scan_all_frames.json'),'retained_structural':str(HERE/'QA_Retained/classified_structural.json')},
 'limitations':['Requires new 112-bone mesh and skeleton as an isolated asset, not only animation imports on the old 78-bone mesh.','Existing UE map, skeleton, mesh and sequences were not modified.','Checks cover authored poses; they do not guarantee every arbitrary pose or all cross-part intersections.','Flat-color stacked UVs and ten hidden back-to-back eyelid cap pairs are retained intentionally.','Normal-speed video was generated; visual assessment used rendered keyposes and frame sequences, not a claim of full normal-speed playback perception.'],
 'skill_inventory':str(HERE/'skill_inventory.json'),'readme':str(HERE/'README_KO.md'),
 'files':[{'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]}
(HERE/'handoff.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
(HERE/'revision_status.json').write_text(json.dumps({k:out[k] for k in ['status','ready_for_new_rig_import_review','ready_for_existing_78_bone_animation_only_import','visual_user_approval','ue_runtime_verified','supersedes']},ensure_ascii=False,indent=2),encoding='utf8')
print('HANDOFF_READY',len(files),'files',out['preview_video_duration_seconds'])
