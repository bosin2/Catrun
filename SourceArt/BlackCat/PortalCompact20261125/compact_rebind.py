"""Make the compact proportions the actual rest mesh and rebase native actions."""
import bpy,json
from mathutils import Vector,Matrix
def rebind(ns,actions):
 a=ns['a'];sc=ns['sc'];update=ns['update'];fc=ns['fcurves'];original=ns['original_names'];snapshots={}
 meshes=[o for o in sc.objects if o.type=='MESH' and any(mod.type=='ARMATURE' and mod.object==a for mod in o.modifiers)];mesh_samples={}
 for act in actions:
  a.animation_data.action=act;frames=[]
  for f in range(int(act.frame_range[0]),int(act.frame_range[1])+1):
   sc.frame_set(f);update();frames.append({p.name:p.matrix.copy() for p in a.pose.bones})
   if f in [1,7,32,53,55]:
    for o in meshes:
     ev=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();mesh_samples[(act.name,f,o.name)]=[v.co.copy() for v in me.vertices];ev.to_mesh_clear()
  snapshots[act.name]=frames
 a.animation_data.action=None
 src=ns['world'];dst=ns['compact_maps'](src,'neutral',0)
 for n in original:a.pose.bones[n].matrix=dst[n];update()
 points=[]
 for n in ['tail_03','tail_05','tail_07']:
  p=ns['mapped'](src[n].translation);p.z=max(.010,p.z);points.append(p)
 ns['B'].floor_tail(points)
 # Mixed weights stay exact only when all bones in an unchanged mesh
 # component receive one rigid bind-space transform. Binding eyelids or
 # tail bones in a curved animation pose would alter their later skinning.
 oldrest=ns['rest'];headD=a.pose.bones['head'].matrix@oldrest['head'].inverted()
 for n in ns['head_names']-{'collar','bell'}:
  a.pose.bones[n].matrix=headD@oldrest[n];update()
 collarD=a.pose.bones['collar'].matrix@oldrest['collar'].inverted()
 for n in ['collar','bell']:a.pose.bones[n].matrix=collarD@oldrest[n];update()
 tailD=Matrix.Translation(a.pose.bones['tail_01'].head-oldrest['tail_01'].translation)
 for n in ns['tail_names']:a.pose.bones[n].matrix=tailD@oldrest[n];update()
 ns['surface'].update(a)
 meshes=[o for o in sc.objects if o.type=='MESH' and any(mod.type=='ARMATURE' and mod.object==a for mod in o.modifiers)]
 verts={}
 for o in meshes:
  ev=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();verts[o.name]=[v.co.copy() for v in me.vertices];ev.to_mesh_clear()
 bpy.ops.object.select_all(action='DESELECT');a.select_set(True);bpy.context.view_layer.objects.active=a;bpy.ops.object.mode_set(mode='POSE');bpy.ops.pose.armature_apply(selected=False);bpy.ops.object.mode_set(mode='OBJECT')
 for o in meshes:
  assert len(o.data.vertices)==len(verts[o.name])
  for v,co in zip(o.data.vertices,verts[o.name]):v.co=co
  o.data.update()
 # Bone endpoints are shortened too; changing the length leaves the rest
 # matrix and skin bind orientation intact for these disconnected bones.
 bpy.ops.object.mode_set(mode='EDIT')
 for b in a.data.edit_bones:
  if b.name.startswith(('upperarm_','forearm_','thigh_','shin_','hock_','paw_','toes_')):b.length*=.70
 bpy.ops.object.mode_set(mode='OBJECT');update()
 kept={act.name for act in actions}
 for act in list(bpy.data.actions):
  if act.name not in kept:bpy.data.actions.remove(act)
 maxpos=0.;maxmatrix=0.;mesh_errors={o.name:0. for o in meshes}
 for act in actions:
  for curve in fc(act):curve.keyframe_points.clear()
  a.animation_data.action=None;prev={}
  for f,pose in enumerate(snapshots[act.name],1):
   a.animation_data.action=None
   for p in a.pose.bones:p.matrix=pose[p.name];update()
   a.animation_data.action=act
   for p in a.pose.bones:
    q=p.rotation_quaternion.copy()
    if p.name in prev and q.dot(prev[p.name])<0:q.negate();p.rotation_quaternion=q
    prev[p.name]=q.copy()
    for ch in ['location','rotation_quaternion','scale']:p.keyframe_insert(ch,frame=f,group=p.name)
  for curve in fc(act):
   for key in curve.keyframe_points:key.interpolation='LINEAR'
  for f,pose in enumerate(snapshots[act.name],1):
   sc.frame_set(f);update()
   for p in a.pose.bones:
    maxpos=max(maxpos,(p.matrix.translation-pose[p.name].translation).length)
    maxmatrix=max(maxmatrix,max(abs(p.matrix[i][j]-pose[p.name][i][j]) for i in range(4) for j in range(4)))
   for o in meshes:
    key=(act.name,f,o.name)
    if key in mesh_samples:
     ev=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();mesh_errors[o.name]=max(mesh_errors[o.name],max((v.co-ref).length for v,ref in zip(me.vertices,mesh_samples[key])));ev.to_mesh_clear()
 report={'compact_rest_applied':True,'native_pose_max_position_error_m':maxpos,'native_pose_max_matrix_error':maxmatrix,'mesh_max_vertex_error_m':mesh_errors,'bones':len(a.data.bones),'mesh_triangles':{o.name:sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes},'original_78_bind_changed_for_short_proportions':True,'old_source_actions_removed_from_compact_copy':True}
 (ns['O']/'QA'/'compact_rebind.json').write_text(json.dumps(report,indent=2),encoding='utf8')
 if maxpos>1e-5:raise RuntimeError('Rebinding changed native poses '+str(maxpos))
 return report
