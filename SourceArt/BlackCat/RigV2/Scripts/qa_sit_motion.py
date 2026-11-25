import bpy,json,sys,math
from pathlib import Path
from mathutils import Vector
O=Path(__file__).resolve().parents[1]/'SitSleep';sc=bpy.context.scene;a=next(o for o in sc.objects if o.type=='ARMATURE');meshes=[o for o in sc.objects if o.type=='MESH'];out={}
for act in [x for x in bpy.data.actions if x.name.startswith('AN_BlackCat_Sit')]:
 a.animation_data.action=act;end=int(act.frame_range[1]);first=None;last=None;minz=1.;worst={};feet=[];tip=[];maxscale=0.
 for f in range(1,end+1):
  sc.frame_set(f);bpy.context.view_layer.update();matrices={p.name:p.matrix.copy() for p in a.pose.bones}
  if f==1:first=matrices
  last=matrices;feet.append({n:list(a.pose.bones[n].head) for n in ['paw_F_L','paw_F_R','paw_H_L','paw_H_R']});tip.append(list(a.pose.bones['tail_07'].tail));maxscale=max(maxscale,max(abs(s-1) for p in a.pose.bones for s in p.scale))
  for ob in meshes:
   ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();v=min(me.vertices,key=lambda v:v.co.z)
   if v.co.z<minz:minz=v.co.z;worst={'object':ob.name,'frame':f,'vertex':v.index,'position':list(v.co),'weights':[(ob.vertex_groups[g.group].name,g.weight) for g in ob.data.vertices[v.index].groups]}
   ev.to_mesh_clear()
 out[act.name]={'frames':[1,end],'min_z_m':minz,'lowest_point':worst,'max_bone_scale_error':maxscale,'loop_matrix_difference':max(abs(first[n][i][j]-last[n][i][j]) for n in first for i in range(4) for j in range(4)),'max_paw_anchor_displacement_m':max((Vector(p[n])-Vector(feet[0][n])).length for p in feet for n in p),'tail_tip_z_range_m':[min(p[2] for p in tip),max(p[2] for p in tip)]}
(O/'sit_motion_qa.json').write_text(json.dumps(out,indent=2));print(json.dumps(out),flush=True)
