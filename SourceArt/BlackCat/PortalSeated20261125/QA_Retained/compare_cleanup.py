import bpy,sys,json
from pathlib import Path
from mathutils import Vector
HERE=Path(__file__).parent;sys.path.insert(0,str(HERE.parent));from retained_mesh_cleanup import cleanup
sc=bpy.context.scene;a=next(o for o in sc.objects if o.type=='ARMATURE');m=bpy.data.objects['SK_BlackCat_Final']
samples=[152,179,223,261,268,280];before={}
def coordinates():
 bpy.context.view_layer.update();ev=m.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();p=[v.co.copy() for v in me.vertices];ev.to_mesh_clear();return p
for f in samples:sc.frame_set(f);before[f]=coordinates()
sc.frame_set(152);cam=sc.camera;cam.animation_data_clear();cam.location=(.20,-.42,.19);cam.rotation_euler=(Vector((0,-.035,.14))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.28
sc.render.resolution_x=700;sc.render.resolution_y=700;sc.render.filepath=str(HERE/'face_before.png');bpy.ops.render.render(write_still=True)
changes=cleanup(m,a)
sc.render.filepath=str(HERE/'face_after.png');bpy.ops.render.render(write_still=True)
delta={}
for f in samples:
 sc.frame_set(f);after=coordinates();ds=[(x-y).length for x,y in zip(before[f],after)];delta[f]={'max_vertex_delta_m':max(ds),'changed_over_1e5':sum(d>1e-5 for d in ds)}
(HERE/'motion_delta.json').write_text(json.dumps({'changes':changes,'frame_deltas':delta},indent=2))
print(json.dumps(delta,indent=2))
