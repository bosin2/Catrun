import bpy,json,pathlib,math
from mathutils import Vector,Quaternion,Matrix
from mathutils.bvhtree import BVHTree
OUT=pathlib.Path(__file__).resolve().parents[1];sc=bpy.context.scene;arm=bpy.data.objects['ARM_BlackCat_Final'];mesh=bpy.data.objects['SK_BlackCat_Final'];pb=arm.pose.bones
arm.animation_data.action=bpy.data.actions['AN_BlackCat_Elevator_MASTER_JumpPullLand'];sc.frame_set(24);base=pb['collar'].matrix.copy();base=Matrix.LocRotScale(base.translation,Quaternion((1,0,0),math.radians(30))@base.to_quaternion(),base.to_scale())
groups={g.index:g.name for g in mesh.vertex_groups};mesh.data.calc_loop_triangles();tri=[list(t.vertices) for t in mesh.data.loop_triangles]
def dominant(t):
 scores={}
 for i in t:
  for g in mesh.data.vertices[i].groups:scores[groups[g.group]]=scores.get(groups[g.group],0)+g.weight
 return max(scores,key=scores.get)
labs=[dominant(t) for t in tri];cf=[t for t,l in zip(tri,labs) if l=='collar'];af=[t for t,l in zip(tri,labs) if l.startswith(('forearm','upperarm'))];hf=[t for t,l in zip(tri,labs) if l=='head'];tf=[t for t,l in zip(tri,labs) if l in ['chest','neck']];rows=[]
for angle in [-20,-10,0,10,20]:
 for y in [-.01,-.005,0,.005,.01]:
  for z in [-.01,-.005,0,.005]:
   m=base.copy();m=Matrix.LocRotScale(m.translation+Vector((0,y,z)),Quaternion((1,0,0),math.radians(angle))@m.to_quaternion(),m.to_scale());pb['collar'].matrix=m;bpy.context.view_layer.update()
   ev=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();vs=[v.co.copy() for v in me.vertices];ev.to_mesh_clear();ct=BVHTree.FromPolygons(vs,cf)
   a=len(ct.overlap(BVHTree.FromPolygons(vs,af)));h=len(ct.overlap(BVHTree.FromPolygons(vs,hf)));t=len(ct.overlap(BVHTree.FromPolygons(vs,tf)))
   rows.append({'angle':angle,'y':y,'z':z,'arm':a,'head':h,'torso':t,'score':a*8+h*2+t+abs(angle)*.2+(abs(y)+abs(z))*1000})
(OUT/'QA/collar_trials_v2.json').write_text(json.dumps(rows,indent=2));print(sorted(rows,key=lambda x:x['score'])[:10])
