import bpy,math,json
import numpy as np
from pathlib import Path
from mathutils import Quaternion,Vector
from mathutils.bvhtree import BVHTree
O=Path(__file__).resolve().parents[1]/'JointRepair';a=bpy.data.objects['ARM_BlackCat_RigV2'];m=bpy.data.objects['SK_BlackCat_RigV2'];sc=bpy.context.scene
def reset():
 a.animation_data.action=None
 for p in a.pose.bones:p.matrix_basis.identity()
 a['controls_enabled']=1.
 for p in a.pose.bones:
  if p.name.startswith('CTRL_IK_'):p['ik']=0.
 for k in ['bend','side_bend','twist']:a.pose.bones['CTRL_spine'][k]=0.
 for k in ['blink_L','blink_R','look_x','look_z']:a.pose.bones['CTRL_face'][k]=0.
 a.pose.bones['CTRL_jaw']['open']=0.;a.pose.bones['CTRL_tongue']['extend']=0.;a.update_tag();bpy.context.view_layer.update()
def evaluated():
 e=m.evaluated_get(bpy.context.evaluated_depsgraph_get());me=e.to_mesh();me.calc_loop_triangles();co=np.array([v.co[:] for v in me.vertices]);tris=np.array([t.vertices[:] for t in me.loop_triangles]);poly=np.array([t.polygon_index for t in me.loop_triangles]);e.to_mesh_clear();return co,tris,poly
region=m.data.attributes['V3_leg_region'];pf=np.array([x.value for x in region.data]);reset();base,tris,poly=evaluated();selected={k:np.where(pf[poly]==i)[0] for i,k in enumerate(['F_L','F_R','H_L','H_R'],1)}
def surface(co,ids):
 ts=tris[ids];tree=BVHTree.FromPolygons(co.tolist(),ts.tolist(),all_triangles=True,epsilon=0)
 pairs=[]
 for i,j in tree.overlap(tree):
  if j<=i or set(ts[i])&set(ts[j]):continue
  pairs.append((int(ids[i]),int(ids[j])))
 ar=np.linalg.norm(np.cross(co[ts[:,1]]-co[ts[:,0]],co[ts[:,2]]-co[ts[:,0]]),axis=1)/2
 return {'intersection_pairs':len(pairs),'examples':pairs[:5],'min_triangle_area':float(ar.min()),'near_zero_triangles':int((ar<1e-10).sum())}
report={'neutral':{k:surface(base,v) for k,v in selected.items()},'tests':{}}
for stem,angles,limb in [('forearm_',range(-90,121,5),'F'),('paw_F_',range(-60,91,5),'F'),('shin_',range(-90,121,5),'H'),('hock_',range(-60,91,5),'H'),('paw_H_',range(-60,91,5),'H')]:
 for side in ['L','R']:
  name=stem+side;rows=[]
  for angle in angles:
   reset();a.pose.bones['CTRL_'+name].rotation_quaternion=Quaternion((1,0,0),math.radians(angle));a.update_tag();bpy.context.view_layer.update();co,_,_=evaluated()
   row=surface(co,selected[limb+'_'+side]);row.update(angle=angle,finite=bool(np.isfinite(co).all()));rows.append(row)
  report['tests'][name]=rows;print('SCANNED',name,'max_overlap',max(r['intersection_pairs'] for r in rows),flush=True)
(O/'QA/joint_surface_scan.json').write_text(json.dumps(report,indent=2));print('SCAN_COMPLETE')
