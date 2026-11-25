import bpy,bmesh,json,math
import numpy as np
from pathlib import Path
from mathutils import Vector,Quaternion
O=Path(__file__).resolve().parents[1];a=next(o for o in bpy.data.objects if o.type=='ARMATURE');m=next(o for o in bpy.data.objects if o.type=='MESH');s=bpy.context.scene
a.animation_data.action=None
for p in a.pose.bones:p.matrix_basis.identity()
bpy.context.view_layer.update()
co=np.array([v.co[:] for v in m.data.vertices]);names=[g.name for g in m.vertex_groups]
w=np.zeros((len(co),len(names)))
for v in m.data.vertices:
 for g in v.groups:w[v.index,g.group]=g.weight
np.savez(O/'QA/source_arrays.npz',co=co,weights=w,names=np.array(names),edges=np.array([e.vertices[:] for e in m.data.edges]))
seen=set();adj=[[] for _ in co]
for e in m.data.edges:
 i,j=e.vertices;adj[i].append(j);adj[j].append(i)
components=[]
for i in range(len(co)):
 if i in seen:continue
 stack=[i];seen.add(i);ids=[]
 while stack:
  j=stack.pop();ids.append(j)
  for k in adj[j]:
   if k not in seen:seen.add(k);stack.append(k)
 ar=co[ids];weights=w[ids].sum(0)
 components.append(dict(count=len(ids),indices=ids,min=ar.min(0).tolist(),max=ar.max(0).tolist(),groups={names[k]:round(float(v),2) for k,v in enumerate(weights) if v>1}))
r={'components':components,'tests':{}}
camera=bpy.data.objects.new('QA_Camera',bpy.data.cameras.new('QA_Camera'));s.collection.objects.link(camera);s.camera=camera;camera.data.type='ORTHO';camera.data.ortho_scale=.29;camera.location=(.45,-.45,.27);camera.rotation_euler=(Vector((0,0,.10))-camera.location).to_track_quat('-Z','Y').to_euler()
s.render.engine='BLENDER_WORKBENCH';s.render.resolution_x=700;s.render.resolution_y=700;s.render.resolution_percentage=100;s.display.shading.light='STUDIO';s.display.shading.color_type='MATERIAL';s.display.shading.show_shadows=True;s.display.shading.show_cavity=True
for mat in bpy.data.materials:
 if mat.node_tree:
  p=next((n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
  if p:mat.diffuse_color=p.inputs['Base Color'].default_value
torso=[i for i in range(len(co)) if sum(w[i,names.index(n)] for n in ['pelvis','lumbar','spine','chest'])>.8 and abs(co[i,0])>.01 and co[i,2]>.065]
for name,rots in [('single_joint_twist',{'spine':90}),('distributed_twist',{'pelvis':22.5,'lumbar':22.5,'spine':22.5,'chest':22.5})]:
 for p in a.pose.bones:p.matrix_basis.identity()
 for n,d in rots.items():a.pose.bones[n].rotation_quaternion=Quaternion((0,1,0),math.radians(d))
 bpy.context.view_layer.update()
 mats=[np.array((a.pose.bones[n].matrix@a.data.bones[n].matrix_local.inverted()).to_3x3()) for n in names]
 mins=[float(np.linalg.svd(sum(w[i,j]*mats[j] for j in range(len(names))),compute_uv=False).min()) for i in torso]
 r['tests'][name]={'min_local_scale':min(mins),'p10_local_scale':float(np.percentile(mins,10)),'torso_vertices':len(torso)}
 s.render.filepath=str(O/'Previews'/('diagnosis_'+name+'.png'));bpy.ops.render.render(write_still=True)
(O/'QA/deformation_diagnosis.json').write_text(json.dumps(r,indent=2))
print('DIAGNOSIS_DONE')
