import bpy,json,pathlib,math,sys
from mathutils import Vector,Matrix
OUT=pathlib.Path(__file__).resolve().parents[1];sc=bpy.context.scene;arm=bpy.data.objects['ARM_BlackCat_Final'];mesh=bpy.data.objects['SK_BlackCat_Final']
manifest=json.loads((OUT/'manifest.json').read_text());targets={s:Vector(v) for s,v in json.loads((OUT/'QA/grip_surface_targets.json').read_text())['native_m'].items()}
samples={};qa={};matrices={}
names=[c['action'] for c in manifest['clips']]+[manifest['master']['action']]
for name in names:
 a=bpy.data.actions[name];arm.animation_data.action=a;n=int(a.frame_range.y);rows=[];q={'finite':True,'min_mesh_game_z_cm':1e6,'max_contact_error_cm':0,'max_foot_step_cm':0,'max_body_outside_platform_cm':0,'frames':n};mats=[];prevfeet=None
 for f in range(1,n+1):
  sc.frame_set(f);bpy.context.view_layer.update();dg=bpy.context.evaluated_depsgraph_get();ev=mesh.evaluated_get(dg);me=ev.to_mesh();vs=[v.co.copy() for v in me.vertices];ev.to_mesh_clear()
  q['min_mesh_game_z_cm']=min(q['min_mesh_game_z_cm'],min(v.z for v in vs)*200)
  q['max_body_outside_platform_cm']=max(q['max_body_outside_platform_cm'],max(max(abs(v.x)-.55,abs(v.y)-.5,0) for v in vs)*200)
  bone_mats={p.name:[list(r) for r in p.matrix] for p in arm.pose.bones};mats.append(bone_mats)
  q['finite'] &= all(math.isfinite(x) for mat in bone_mats.values() for r in mat for x in r)
  ft={n:list(arm.pose.bones[n].head*200) for n in ['paw_F_L','paw_F_R','paw_H_L','paw_H_R']}
  if prevfeet:q['max_foot_step_cm']=max(q['max_foot_step_cm'],max((Vector(ft[n])-Vector(prevfeet[n])).length for n in ft))
  prevfeet=ft
  mf=f+({'AN_BlackCat_Elevator_HangPull':24,'AN_BlackCat_Elevator_ReleaseLand':54}.get(name,0))
  contact= name.endswith(('MASTER_JumpPullLand','HangPull','JumpGrab','ReleaseLand')) and 24<=mf<=55
  drop=.09*(max(0,min(1,(mf-29)/19))**2)*(3-2*max(0,min(1,(mf-29)/19))) if mf<=48 else .09
  pads={s:list((arm.pose.bones['paw_F_'+s].matrix@Vector((0,.002,-.004)))*200) for s in targets}
  errors={s:(Vector(pads[s])/200-(v-Vector((0,0,drop)))).length*200 for s,v in targets.items()} if contact else {}
  if errors:q['max_contact_error_cm']=max(q['max_contact_error_cm'],*errors.values())
  rows.append({'frame':f,'seconds':(f-1)/30,'root_native_m':list(arm.pose.bones['root'].location),'root_game_cm':list(arm.pose.bones['root'].location*200),'feet_game_cm':ft,'front_pad_game_cm':pads,'front_ring_contact':contact,'contact_error_cm':errors,'mesh_min_game_z_cm':min(v.z for v in vs)*200})
 samples[name]=rows;qa[name]=q;matrices[name]=mats
 print('QA',name,q,flush=True)
 # Animation only. Bone hierarchy and object name are identical to source export.
 sc.frame_start=1;sc.frame_end=n
 # FBX without a mesh has no skin bind-pose block. Its default bone transforms
 # must be the original rest pose, not whichever animated frame QA ended on.
 for p in arm.pose.bones:
  p.matrix_basis=Matrix.Identity(4)
  for channel in ['location','rotation_quaternion','scale']:p.keyframe_insert(channel,frame=0,group=p.name)
 sc.frame_set(0);bpy.context.view_layer.update()
 bpy.ops.object.select_all(action='DESELECT');arm.select_set(True);bpy.context.view_layer.objects.active=arm
 bpy.ops.export_scene.fbx(filepath=str(OUT/'FBX'/(name+'.fbx')),use_selection=True,object_types={'ARMATURE'},apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Z',axis_up='Y',add_leaf_bones=False,use_armature_deform_only=True,armature_nodetype='NULL',bake_anim=True,bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False,bake_anim_simplify_factor=0.,bake_anim_step=1.,use_custom_props=False)
 for layer in a.layers:
  for strip in layer.strips:
   for bag in strip.channelbags:
    for curve in bag.fcurves:
     for key in list(curve.keyframe_points):
      if abs(key.co.x)<.01:curve.keyframe_points.remove(key)
(OUT/'QA/frame_samples.json').write_text(json.dumps(samples))
(OUT/'QA/numeric_qa.json').write_text(json.dumps(qa,indent=2))
(OUT/'QA/source_animation_matrices.json').write_text(json.dumps(matrices))
boundaries=[]
for a,b in [('LookPrepare','JumpGrab'),('JumpGrab','HangPull'),('HangPull','ReleaseLand'),('ReleaseLand','StartleTail'),('RideBalance','RideBalance'),('LoafIdle','LoafIdle'),('LoafIdle','LoafStartleRise')]:
 ma=matrices['AN_BlackCat_Elevator_'+a][-1];mb=matrices['AN_BlackCat_Elevator_'+b][0]
 boundaries.append({'from':a,'to':b,'max_matrix_delta':max(abs(ma[n][i][j]-mb[n][i][j]) for n in ma for i in range(4) for j in range(4))})
(OUT/'QA/boundaries.json').write_text(json.dumps(boundaries,indent=2));print('QA_EXPORT_DONE')
