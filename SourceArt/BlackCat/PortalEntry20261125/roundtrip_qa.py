import bpy,json,math
from pathlib import Path
from mathutils import Matrix
O=Path(__file__).parent;src=json.loads((O/'source_reference.json').read_text());samples=json.loads((O/'source_pose_samples.json').read_text());out={}
for name,poses in samples.items():
 bpy.ops.wm.read_factory_settings(use_empty=True);sc=bpy.context.scene;sc.render.fps=30
 bpy.ops.import_scene.fbx(filepath=str(O/(name+'.fbx')),use_anim=True,automatic_bone_orientation=False,anim_offset=0.)
 a=next(o for o in sc.objects if o.type=='ARMATURE');bpy.context.view_layer.objects.active=a;a.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
 for b in a.data.edit_bones:b.use_connect=False
 bpy.ops.object.mode_set(mode='OBJECT');errors=[];rot=[];scaleerr=[];root=[]
 for i,pose in enumerate(poses):
  sc.frame_set(i+1);bpy.context.view_layer.update()
  for n,rows in pose.items():
   ref=Matrix(rows);actual=a.pose.bones[n].matrix;errors.append((ref.translation-actual.translation).length);angle=math.degrees(ref.to_quaternion().rotation_difference(actual.to_quaternion()).angle);rot.append(min(angle,abs(360-angle)));scaleerr.append(max(abs(x-y) for x,y in zip(ref.to_scale(),actual.to_scale())))
  root.append(a.pose.bones['root'].head.length)
 resterr=max(max(abs(a.data.bones[b['name']].matrix_local[i][j]-b['rest'][i][j]) for i in range(4) for j in range(4)) for b in src['bones'])
 out[name]={'bones':len(a.data.bones),'meshes':sum(o.type=='MESH' for o in sc.objects),'actions':len(bpy.data.actions),'range':list(a.animation_data.action.frame_range),'scale':list(a.scale),'max_position_error_m':max(errors),'max_rotation_error_degrees':max(rot),'max_scale_error':max(scaleerr),'max_rest_matrix_error':resterr,'max_root_motion_m':max(root),'bone_names_match':set(a.data.bones.keys())=={b['name'] for b in src['bones']},'hierarchy_match':all((a.data.bones[b['name']].parent.name if a.data.bones[b['name']].parent else None)==b['parent'] for b in src['bones'])}
from io_scene_fbx import parse_fbx as parse
def settings(path):
 tree,version=parse.parse(str(path));gs=next(e for e in tree.elems if e.id==b'GlobalSettings');props=next(e for e in gs.elems if e.id==b'Properties70');return {e.props[0].decode():[x.decode() if isinstance(x,bytes) else x for x in e.props[4:]] for e in props.elems}
out['fbx_settings']={'original':settings(Path('C:/Users/whghk/Desktop/CastleKit/BlackCat/PortalCinematic/AN_BlackCat_PortalJumpIn.fbx')),'new':settings(O/'AN_BlackCat_PortalPawEar.fbx')}
(O/'QA'/'fbx_roundtrip.json').write_text(json.dumps(out,indent=2));print(json.dumps(out),flush=True)
