import bpy,json,math
from pathlib import Path
O=Path(__file__).resolve().parents[1]/'SitSleep';sc=bpy.context.scene;a=next(o for o in sc.objects if o.type=='ARMATURE');m=next(o for o in sc.objects if o.type=='MESH');ids=[v.index for v in m.data.vertices if sum(g.weight for g in v.groups if m.vertex_groups[g.group].name.startswith('tail_'))>.5];out={}
for name in ['AN_BlackCat_Sleep','AN_BlackCat_SleepTailFixed']:
 a.animation_data.action=bpy.data.actions[name];minimum=1;angle=0;first={};last={}
 for f in range(1,242):
  sc.frame_set(f);bpy.context.view_layer.update();ev=m.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();minimum=min(minimum,min(me.vertices[i].co.z for i in ids));ev.to_mesh_clear();directions=[(a.pose.bones[f'tail_{i:02}'].tail-a.pose.bones[f'tail_{i:02}'].head).normalized() for i in range(1,8)];angle=max(angle,max(math.degrees(x.angle(y)) for x,y in zip(directions,directions[1:])));last={p.name:p.matrix.copy() for p in a.pose.bones if p.name.startswith('tail_')}
  if f==1:first=last
 out[name]={'min_tail_surface_z_m':minimum,'max_adjacent_tail_segment_angle_degrees':angle,'tail_loop_matrix_difference':max(abs(first[n][i][j]-last[n][i][j]) for n in first for i in range(4) for j in range(4))}
(O/'sleep_motion_qa.json').write_text(json.dumps(out,indent=2));print(json.dumps(out),flush=True)
