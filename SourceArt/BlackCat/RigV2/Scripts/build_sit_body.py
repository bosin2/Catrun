import sys,bpy,bmesh,math,json
from pathlib import Path
from mathutils import Vector,Matrix
sys.path.insert(0,str(Path(__file__).parent))
import build_sit_sleep as B
B.sit();a=B.a;m=B.m;sc=B.sc;O=B.O
# A dedicated seated mesh: retain the original face, ears, collar, bell and tail.
# This is not a replacement for the shared UE mesh or a general locomotion rig.
fur={i for p in m.data.polygons if p.material_index==0 for i in p.vertices}
remove=[]
for v in m.data.vertices:
 tail=sum(g.weight for g in v.groups if m.vertex_groups[g.group].name.startswith('tail_'))
 keep_face=v.co.z>.083 and v.co.y<-.047
 if v.index in fur and v.co.z<.104 and tail<.5 and not keep_face:remove.append(v.index)
bm=bmesh.new();bm.from_mesh(m.data);bm.verts.ensure_lookup_table();bmesh.ops.delete(bm,geom=[bm.verts[i] for i in remove],context='VERTS');bm.to_mesh(m.data);bm.free();m.data.update()
parts=[]
def ellipsoid(name,center,radii):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=16,location=center)
 ob=bpy.context.object;ob.name=name;ob.scale=radii;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);parts.append(ob)
ellipsoid('SeatedTorso',(0,.029,.044),(.035,.033,.039))
ellipsoid('Chest',(0,.000,.071),(.030,.027,.028))
for sign in [-1,1]:
 ellipsoid('Haunch',(sign*.027,.033,.027),(.024,.028,.025))
 ellipsoid('BackPaw',(sign*.033,.005,.010),(.013,.018,.010))
 ellipsoid('FrontShoulder',(sign*.022,-.010,.052),(.014,.015,.021))
 ellipsoid('FrontLeg',(sign*.019,-.024,.029),(.011,.012,.024))
 ellipsoid('FrontPaw',(sign*.019,-.030,.009),(.012,.016,.009))
bpy.ops.object.select_all(action='DESELECT')
for ob in parts:ob.select_set(True)
bpy.context.view_layer.objects.active=parts[0];bpy.ops.object.join();body=bpy.context.object;body.name='BlackCat_SeatedBody'
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
mod=body.modifiers.new('Union','REMESH');mod.mode='VOXEL';mod.voxel_size=.0022;mod.use_smooth_shade=False;bpy.ops.object.modifier_apply(modifier=mod.name)
mod=body.modifiers.new('Relax','SMOOTH');mod.factor=1.;mod.iterations=4;bpy.ops.object.modifier_apply(modifier=mod.name)
mod=body.modifiers.new('UniformFacets','DECIMATE');mod.ratio=min(1,290/len(body.data.polygons));bpy.ops.object.modifier_apply(modifier=mod.name)
body.data.materials.append(m.data.materials[0])
for p in body.data.polygons:p.use_smooth=False
# Bind the newly seated skin back through the current pose. All existing bind
# matrices and bone names remain unchanged. No procedural animation handler.
for n in ['pelvis','chest','forearm_L','forearm_R','paw_F_L','paw_F_R']:body.vertex_groups.new(name=n)
import numpy as np
for v in body.data.vertices:
 x,y,z=v.co;side='L' if x>0 else 'R'
 if y<-.015 and z<.057 and abs(x)>.003:
  w={'forearm_'+side:1.} if z>.017 else {'paw_F_'+side:1.}
 else:
  t=max(0,min(1,(z-.049)/.042));t=t*t*(3-2*t);w={'pelvis':1-t,'chest':t}
 mat=sum((np.array(a.pose.bones[n].matrix@B.rest[n].inverted())*s for n,s in w.items()),np.zeros((4,4)))
 v.co=Vector((np.linalg.inv(mat)@np.r_[np.array(v.co),1])[:3])
 for n,s in w.items():
  if s>0:body.vertex_groups[n].add([v.index],s,'REPLACE')
mod=body.modifiers.new('Armature','ARMATURE');mod.object=a;body.parent=a
cam=bpy.data.objects.new('SitPreview',bpy.data.cameras.new('SitPreview'));sc.collection.objects.link(cam);sc.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=.31
if not sc.world:sc.world=bpy.data.worlds.new('ReviewWorld')
sc.render.engine='BLENDER_WORKBENCH';sc.render.resolution_x=800;sc.render.resolution_y=800;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.display.shading.color_type='MATERIAL';sc.display.shading.light='STUDIO';sc.display.shading.show_cavity=True;sc.display.shading.show_shadows=True;sc.display.shading.background_type='WORLD';sc.world.color=(.24,.24,.24)
for label,loc in [('front',(0,-.5,.14)),('side',(.5,0,.14)),('threequarter',(.32,-.45,.20))]:
 cam.location=loc;cam.rotation_euler=(Vector((0,.015,.105))-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=str(O/'Previews'/f'clean_sit_{label}.png');bpy.ops.render.render(write_still=True)
print('BODY',len(body.data.vertices),len(body.data.polygons),flush=True)
bpy.ops.wm.save_as_mainfile(filepath=str(O/'SK_BlackCat_Seated_Working.blend'))
