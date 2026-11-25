import bpy,sys,json,bmesh,math
from pathlib import Path
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).parent));import build_sit_sleep as B
a=B.a;sc=B.sc;sc.render.fps=30;O=B.O
B.sit()
# Seated clips keep eyes open. Remove only their concealed lower-lid shells,
# whose side walls overlap the upper shells. Sleeping lids stay untouched.
hidden_lids=[v.index for v in B.m.data.vertices if sum(g.weight for g in v.groups if B.m.vertex_groups[g.group].name.startswith('Lid_Lower_'))>.5]
# Normalize four strongest influences, compensating bind coordinates so the
# displayed seated face stays at exactly the same location.
import numpy as np
transforms={p.name:np.array(p.matrix@B.rest[p.name].inverted()) for p in a.pose.bones};pruned=0;dropped=0.
for v in B.m.data.vertices:
 w=[(g.group,g.weight) for g in v.groups if g.weight>1e-4]
 if len(w)<=4:continue
 old=sum((transforms[B.m.vertex_groups[i].name]*s for i,s in w),np.zeros((4,4)));w.sort(key=lambda x:-x[1]);kept=w[:4];total=sum(s for i,s in kept);dropped=max(dropped,sum(s for i,s in w[4:]));new=sum((transforms[B.m.vertex_groups[i].name]*s/total for i,s in kept),np.zeros((4,4)));v.co=Vector((np.linalg.inv(new)@old@np.r_[np.array(v.co),1])[:3])
 for g in list(v.groups):B.m.vertex_groups[g.group].remove([v.index])
 for i,s in kept:B.m.vertex_groups[i].add([v.index],s/total,'REPLACE')
 pruned+=1
print('SEATED_WEIGHTS',pruned,'MAX_REMOVED',dropped,flush=True)
# Cap the cut neck inside the seated torso, leaving the visible face intact.
bm=bmesh.new();bm.from_mesh(B.m.data);bm.verts.ensure_lookup_table();bmesh.ops.delete(bm,geom=[bm.verts[i] for i in hidden_lids],context='VERTS');edges=[e for e in bm.edges if e.is_boundary]
if edges:bmesh.ops.holes_fill(bm,edges=edges,sides=0);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
loose=[v for v in bm.verts if not v.link_faces]
if loose:bmesh.ops.delete(bm,geom=loose,context='VERTS')
bmesh.ops.triangulate(bm,faces=[f for f in bm.faces if len(f.verts)>4])
bm.to_mesh(B.m.data);bm.free()
body=bpy.data.objects['BlackCat_SeatedBody'];bpy.ops.object.select_all(action='DESELECT');body.select_set(True);bpy.context.view_layer.objects.active=body
# Flatten only sub-millimeter sole undershoots introduced by decimation.
for v in body.data.vertices:
 mat=sum((transforms[body.vertex_groups[g.group].name]*g.weight for g in v.groups),np.zeros((4,4)));p=mat@np.r_[np.array(v.co),1]
 if p[2]<.0002:p[2]=.0002;v.co=Vector((np.linalg.inv(mat)@p)[:3])
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(angle_limit=1.151917,island_margin=.015);bpy.ops.object.mode_set(mode='OBJECT')
# A small internal stem attaches the original bell clapper to its housing.
clapper=[v for v in B.m.data.vertices if len(v.groups)==1 and B.m.vertex_groups[v.groups[0].group].name=='bell']
bell_matrix=a.pose.bones['bell'].matrix@B.rest['bell'].inverted();center=Vector((0,-.07356653,.07697054))
bpy.ops.mesh.primitive_cylinder_add(vertices=8,radius=.0007,depth=.012,location=center);stem=bpy.context.object;stem.name='Bell_InternalStem';bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
for v in stem.data.vertices:v.co=bell_matrix.inverted()@v.co
stem.data.materials.append(B.m.data.materials[6]);g=stem.vertex_groups.new(name='bell');g.add(list(range(len(stem.data.vertices))),1.,'REPLACE');mod=stem.modifiers.new('Armature','ARMATURE');mod.object=a;stem.parent=a
a.animation_data.action=None
for act in list(bpy.data.actions):bpy.data.actions.remove(act)
actions=[]
for name,end,ear,tail in [('AN_BlackCat_SitPose',31,False,False),('AN_BlackCat_SitEarTilt',121,True,False),('AN_BlackCat_SitTailTap',121,False,True),('AN_BlackCat_SitEarTail',121,True,True)]:
 act=bpy.data.actions.new(name);act.use_fake_user=True;prev={}
 for f in range(1,end+1):
  B.sit((f-1)/30,ear,tail);a.animation_data.action=act
  for p in a.pose.bones:
   q=p.rotation_quaternion.copy()
   if p.name in prev and q.dot(prev[p.name])<0:q.negate();p.rotation_quaternion=q
   prev[p.name]=q.copy()
  B.key(f)
 B.linear(act);actions.append(act)
a.animation_data.action=actions[-1];sc.frame_start=1;sc.frame_end=121;sc.frame_set(1)
sc.camera.location=(.32,-.45,.20);sc.camera.rotation_euler=(Vector((0,.015,.105))-sc.camera.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.wm.save_as_mainfile(filepath=str(O/'SK_BlackCat_Seated.blend'))
folder=O/'Previews'/'sit_frames';folder.mkdir(exist_ok=True);sc.render.resolution_x=600;sc.render.resolution_y=600
for f in range(1,122):
 sc.frame_set(f);sc.render.filepath=str(folder/f'{f-1:04}.png');bpy.ops.render.render(write_still=True)
print('SIT_ACTIONS_READY',flush=True)
