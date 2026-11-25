import bpy,json,pathlib,math
from mathutils import Matrix
OUT=pathlib.Path(__file__).resolve().parents[1]
ref=json.loads((OUT/'QA/source_animation_matrices.json').read_text());src=json.loads((OUT/'QA/source_inspection.json').read_text())
bones=next(o['bones'] for o in src['objects'] if o['type']=='ARMATURE');expected={b['name']:b['parent'] for b in bones}
results=[]
for name,frames in ref.items():
 bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.render.fps=30
 bpy.ops.import_scene.fbx(filepath=str(OUT/'FBX'/(name+'.fbx')),use_anim=True,anim_offset=0,ignore_leaf_bones=False,automatic_bone_orientation=False)
 arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');hier={b.name:b.parent.name if b.parent else None for b in arm.data.bones}
 a=arm.animation_data.action;mx=0;pos=0;rest=0;bad=[]
 original_rest={b['name']:Matrix(b['matrix']) for b in bones}
 # Imported axis mapping is undone by armature world transform; compare joint positions globally.
 for f,frame in enumerate(frames,1):
  bpy.context.scene.frame_set(f)
  for n,m in frame.items():
   p=arm.pose.bones[n];im=arm.matrix_world@p.matrix;sm=Matrix(m)
   pos=max(pos,(im.translation-sm.translation).length)
   ideform=im@(arm.matrix_world@arm.data.bones[n].matrix_local).inverted();sdeform=sm@original_rest[n].inverted()
   mx=max(mx,max(abs(ideform[i][j]-sdeform[i][j]) for i in range(4) for j in range(4)))
   if not all(math.isfinite(x) for r in im for x in r):bad.append((f,n))
 for b in bones:
  imported=arm.matrix_world@arm.data.bones[b['name']].matrix_local
  rest=max(rest,(imported.translation-Matrix(b['matrix']).translation).length)
 results.append({'file':name+'.fbx','hierarchy_equal':hier==expected,'bones':len(hier),'actions':len(bpy.data.actions),'frame_range':list(a.frame_range),'expected_range':[1,len(frames)],'fps':bpy.context.scene.render.fps,'armature_scale':list(arm.scale),'max_joint_position_error_game_cm':pos*200,'max_rest_joint_error_game_cm':rest*200,'max_skinning_matrix_component_error':mx,'nonfinite':len(bad)})
 print('REIMPORT',results[-1],flush=True)
(OUT/'QA/reimport.json').write_text(json.dumps(results,indent=2))
