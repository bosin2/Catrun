import bpy,math,json
import numpy as np
from pathlib import Path
from mathutils import Quaternion,Vector
from mathutils.bvhtree import BVHTree
O=Path(__file__).resolve().parents[1]/'UniformJointRepair';a=bpy.data.objects['ARM_BlackCat_RigV2'];m=bpy.data.objects['SK_BlackCat_RigV2'];sc=bpy.context.scene
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
def crosses(A,B):
 # BVH also reports touching triangles. Require penetration through a triangle
 # interior, or positive coplanar overlap area, before calling it a fold.
 na=np.cross(A[1]-A[0],A[2]-A[0]);nb=np.cross(B[1]-B[0],B[2]-B[0]);la=np.linalg.norm(na);lb=np.linalg.norm(nb)
 if min(la,lb)<2e-10:return False
 na/=la;nb/=lb
 if abs(np.dot(na,nb))>1-1e-7 and max(abs((A-B[0])@nb))<1e-8:
  axis=int(np.argmax(abs(nb)));P=np.delete(A,axis,axis=1).tolist();Q=np.delete(B,axis,axis=1)
  cross=lambda a,b:a[0]*b[1]-a[1]*b[0]
  orientation=np.sign(cross(Q[1]-Q[0],Q[2]-Q[0]))
  for k in range(3):
   U=Q[k];V=Q[(k+1)%3];out=[]
   for j in range(len(P)):
    S=np.array(P[j-1]);T=np.array(P[j]);ds=orientation*cross(V-U,S-U);dt=orientation*cross(V-U,T-U)
    if (ds>=0)!=(dt>=0):out.append((S+(T-S)*ds/(ds-dt)).tolist())
    if dt>=0:out.append(T.tolist())
   P=out
   if not P:return False
  area=abs(sum(cross(P[j-1],P[j]) for j in range(len(P))))*.5
  return area>1e-10
 for X,Y,n in [(A,B,nb),(B,A,na)]:
  u=Y[1]-Y[0];v=Y[2]-Y[0];uu=np.dot(u,u);uv=np.dot(u,v);vv=np.dot(v,v);den=uu*vv-uv*uv
  for j in range(3):
   S=X[j];T=X[(j+1)%3];d=np.dot(T-S,n)
   if abs(d)<1e-10:continue
   t=np.dot(Y[0]-S,n)/d
   if not 1e-6<t<1-1e-6:continue
   w=S+t*(T-S)-Y[0];wu=np.dot(w,u);wv=np.dot(w,v);b=(vv*wu-uv*wv)/den;c=(uu*wv-uv*wu)/den
   if min(b,c,1-b-c)>1e-6:return True
 return False

def surface(co,ids):
 ts=tris[ids];tree=BVHTree.FromPolygons(co.tolist(),ts.tolist(),all_triangles=True,epsilon=0)
 pairs=[]
 for i,j in tree.overlap(tree):
  if j<=i or set(ts[i])&set(ts[j]):continue
  if crosses(co[ts[i]],co[ts[j]]):pairs.append((int(ids[i]),int(ids[j])))
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
