import bpy,sys,json
from pathlib import Path
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).parent));import build_sit_sleep as B
a=B.a;sc=B.sc;O=B.O;original=bpy.data.actions['AN_BlackCat_Sleep'];names=[f'tail_{i:02}' for i in range(1,8)];poses=[]
for f in range(1,242):
 a.animation_data.action=original;sc.frame_set(f);B.update();a.animation_data.action=None;B.sleep_tail((f-1)/30);poses.append({n:a.pose.bones[n].matrix_basis.copy() for n in names})
fixed=original.copy();fixed.name='AN_BlackCat_SleepTailFixed';fixed.use_fake_user=True
for layer in fixed.layers:
 for strip in layer.strips:
  for bag in strip.channelbags:
   for fc in list(bag.fcurves):
    if any('"'+n+'"' in fc.data_path for n in names):bag.fcurves.remove(fc)
prev={}
for f,pose in enumerate(poses,1):
 a.animation_data.action=fixed;sc.frame_set(f)
 for n,mat in pose.items():
  p=a.pose.bones[n];p.rotation_mode='QUATERNION';p.matrix_basis=mat;q=p.rotation_quaternion.copy()
  if n in prev and q.dot(prev[n])<0:q.negate();p.rotation_quaternion=q
  prev[n]=q.copy()
 B.key(f,names)
for layer in fixed.layers:
 for strip in layer.strips:
  for bag in strip.channelbags:
   for fc in bag.fcurves:
    if any('"'+n+'"' in fc.data_path for n in names):
     for k in fc.keyframe_points:k.interpolation='LINEAR'
# Verify every non-tail pose across the complete original action.
err=0.
for f in range(1,242):
 a.animation_data.action=original;sc.frame_set(f);B.update();ref={p.name:p.matrix.copy() for p in a.pose.bones if p.name not in names}
 a.animation_data.action=fixed;sc.frame_set(f);B.update()
 err=max(err,max(abs(a.pose.bones[n].matrix[i][j]-mat[i][j]) for n,mat in ref.items() for i in range(4) for j in range(4)))
sc.frame_start=1;sc.frame_end=241;sc.render.fps=30;a.animation_data.action=fixed;sc.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(O/'SK_BlackCat_SleepTailFixed.blend'))
(O/'sleep_qa.json').write_text(json.dumps({'max_non_tail_matrix_difference':err,'source_unchanged':True,'original_action_retained':original.name,'fixed_action':fixed.name,'frames':[1,241],'fps':30},indent=2))
cam=bpy.data.objects.new('SleepPreview',bpy.data.cameras.new('SleepPreview'));sc.collection.objects.link(cam);sc.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=.29;cam.location=(.32,-.45,.22);cam.rotation_euler=(Vector((0,.02,.070))-cam.location).to_track_quat('-Z','Y').to_euler()
sc.render.engine='BLENDER_WORKBENCH';sc.render.resolution_x=600;sc.render.resolution_y=600;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.display.shading.color_type='MATERIAL';sc.display.shading.light='STUDIO';sc.display.shading.show_cavity=True;sc.display.shading.show_shadows=True;sc.display.shading.background_type='WORLD';sc.world=bpy.data.worlds.new('ReviewWorld');sc.world.color=(.24,.24,.24)
for label,act in [('sleep_before',original),('sleep_fixed',fixed)]:
 folder=O/'Previews'/label;folder.mkdir(exist_ok=True);a.animation_data.action=act
 for f in range(1,242,2):
  sc.frame_set(f);sc.render.filepath=str(folder/f'{(f-1)//2:04}.png');bpy.ops.render.render(write_still=True)
print('SLEEP_ACTION_READY',err,flush=True)
