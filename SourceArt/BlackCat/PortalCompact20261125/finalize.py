import json,hashlib
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
HERE=Path(__file__).parent.resolve()
def read(path):return json.loads((HERE/path).read_text(encoding='utf-8-sig'))
native=read('QA/native_verification.json');fbx=read('QA/fbx_roundtrip.json');rebind=read('QA/compact_rebind.json');surface=read('QA_Surface/motion_scan_all_frames.json');contact=read('QA/contact_and_ground.json');contract=read('QA/export_contract.json')
assert all(x['max_position_error_m']<1e-6 for x in native['joins'])
assert all(not x['bind_errors'] and (x['pose_roundtrip'] is None or x['pose_roundtrip']['pass']) for x in fbx)
assert max(rebind['mesh_max_vertex_error_m'].values())<1e-5
assert read('QA/compact_rest_structural.json')['pass']
pixels={}
for f in [179,268,280]:
 a=np.asarray(Image.open(HERE/f'Previews/frames/{f:04}.png')).astype(int);b=np.asarray(Image.open(HERE/f'QA/native_reopen_{f:04}.png')).astype(int);pixels[str(f)]=int(np.abs(a-b).max())
assert max(pixels.values())==0
canvas=Image.new('RGB',(1400,750),(35,38,42));draw=ImageDraw.Draw(canvas);font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',26)
for i,label in enumerate(['before','after']):
 canvas.paste(Image.open(HERE/f'Previews/Comparison_{label}.png').convert('RGB'),(i*700,50));draw.text((i*700+30,8),'이전' if i==0 else '짧은 비율 수정본',font=font,fill=(240,240,240))
canvas.save(HERE/'Previews/Comparison.png')
launch=contact['frames']['AN_CompactPortal_SeatedTakeoff'];lift=next(x['f'] for x in launch if min(x['feet']['H_L']['min_z'],x['feet']['H_R']['min_z'])>1e-5)
files=[HERE/'SK_BlackCat_CompactPortal.blend',HERE/'SC_BlackCat_CompactPortal_Review.blend',HERE/'Previews/CompactPortal_30fps.mp4',HERE/'Previews/Comparison.png']+sorted((HERE/'FBX').glob('*.fbx'))
out={'status':'compact_model_and_motion_ready_for_user_review','user_art_approval':False,'ue_runtime_verified':False,'new_mesh_and_skeleton_required':True,'supersedes':'PortalSeated20261125 long-limbed revision','blend':str(files[0]),'full_sequence_blend':str(files[1]),'video':str(files[2]),'comparison':str(files[3]),'mesh_fbx':contract['mesh_fbx'],'clips':contract['clips'],'fps':30,'video_frames':293,'video_duration_seconds':293/30,'limb_length_factor':.70,'body_width_factor':1.08,'body_depth_factor':1.06,'body_triangles':568,'retained_triangles':8256,'total_triangles':8824,'bones':108,'original_bone_rest_changed':True,'rest_shape_is_compact':True,'head_size_preserved':True,'root_motion_in_clips':False,'timing':{'sit':[1,19],'ear':[20,27],'head_tilt':[24,32],'hold':[32,43],'paw_gather':[49,52],'contact':[55,60],'paw_down':72,'two_wiggles':[14,38],'wiggle_stop':[38,41],'quick_compression':[44,50],'compression_hold':[50,53],'last_hind_ground_frame':lift-1,'first_hind_airborne_frame':lift,'launch_ends':13},'contact':{'paw':'paw_F_L','portal_plane_y_m':contact['portal_plane_y'],'palm_center_model_local_m':[.0274199955,contact['portal_plane_y'],.0521000028],'max_plane_error_m':max(abs(x) for x in contact['contact_distance_m'])},'qa':{'body_scan':str(HERE/'QA_Surface/motion_scan_all_frames.json'),'body_scan_frames':surface['sample_count'],'updated_launch_first_frame':'identical to previously validated final compression pose','native':native,'rebind':rebind,'native_reopen_pixel_max_difference':pixels,'fbx_roundtrip':str(HERE/'QA/fbx_roundtrip.json'),'compact_rest_structural':str(HERE/'QA/compact_rest_structural.json')},'recommended_ue_import':{'new_isolated_skeleton':True,'import_uniform_scale':100,'scale_verified_in_ue':False,'convert_scene':True,'convert_scene_unit':True,'force_front_x_axis':False,'preserve_local_transform':False,'sample_rate':30,'compression':'Preserve frame keys / LeastDestructive; default key reduction previously caused drift on this small rig.'},'limits':['Checks cover authored motion and each body/limb region, not every possible pose or every cross-part intersection.','Original source files and existing UE assets were not overwritten.','Flat-color UV stacking is intentional; not unique baked-texture UVs.','Normal-speed video was rendered; visual inspection used keyposes and frame sequences, not a claim of complete real-time playback perception.'],'files':[{'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]}
(HERE/'handoff.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
print('COMPACT_DELIVERY_READY',len(files),'files','hind liftoff',lift)
