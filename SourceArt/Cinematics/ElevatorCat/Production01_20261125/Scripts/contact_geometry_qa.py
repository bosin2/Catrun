import bpy,json,pathlib,math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
OUT=pathlib.Path(__file__).resolve().parents[1];sc=bpy.context.scene;arm=bpy.data.objects['ARM_BlackCat_Final'];mesh=bpy.data.objects['SK_BlackCat_Final'];ring=bpy.data.objects['SM_E23_ControlRing'];pull=bpy.data.objects['ROOT_ControlPull']
groups={g.index:g.name for g in mesh.vertex_groups}
headverts={v.index for v in mesh.data.vertices if any(groups[g.group] in ['head','neck','ear_L','ear_R','ear_tip_L','ear_tip_R'] and g.weight>.4 for g in v.groups)}
headfaces=[list(p.vertices) for p in mesh.data.polygons if all(v in headverts for v in p.vertices)]
feetverts={v.index for v in mesh.data.vertices if any(groups[g.group].startswith(('paw_','toes_')) and g.weight>.5 for g in v.groups)}
frontverts={s:{v.index for v in mesh.data.vertices if any(groups[g.group] in ['paw_F_'+s,'toes_F_'+s] and g.weight>.4 for g in v.groups)} for s in ['L','R']}
master=bpy.data.actions['AN_BlackCat_Elevator_MASTER_JumpPullLand'];arm.animation_data.action=master;rows=[]
for f in range(1,103):
 sc.frame_set(f);bpy.context.view_layer.update();ev=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();verts=[v.co.copy() for v in me.vertices];ev.to_mesh_clear()
 rv=[ring.matrix_world@v.co for v in ring.data.vertices];rt=BVHTree.FromPolygons(rv,[list(p.vertices) for p in ring.data.polygons]);ht=BVHTree.FromPolygons(verts,headfaces)
 pawdata={}
 if 24<=f<=55:
  for s,ids in frontverts.items():
   pf=[list(p.vertices) for p in mesh.data.polygons if all(i in ids for i in p.vertices)];pt=BVHTree.FromPolygons(verts,pf)
   pawdata[s]={'min_vertex_to_ring_surface_cm':min(rt.find_nearest(verts[i])[3] for i in ids)*200,'surface_intersection_pairs':len(pt.overlap(rt))}
 rows.append({'frame':f,'head_ring_surface_intersections':len(ht.overlap(rt)),'min_head_to_ring_cm':min(rt.find_nearest(verts[i])[3] for i in headverts)*200,'actual_paw_mesh':pawdata})
arm.animation_data.action=bpy.data.actions['AN_BlackCat_Elevator_PeekDown'];edge=[]
for f in range(1,int(arm.animation_data.action.frame_range.y)+1):
 sc.frame_set(f);ev=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh()
 edge.append({'frame':f,'foot_vertices_min_edge_clearance_cm':min(min(.55-abs(me.vertices[i].co.x),.5-abs(me.vertices[i].co.y)) for i in feetverts)*200,'pelvis_game_cm':list(arm.pose.bones['pelvis'].head*200)})
 ev.to_mesh_clear()
tailverts={v.index for v in mesh.data.vertices if any(groups[g.group].startswith('tail_') and g.weight>.5 for g in v.groups)}
arm.animation_data.action=bpy.data.actions['AN_BlackCat_Elevator_StartleTail'];tail=[]
for f in [1,12,61]:
 sc.frame_set(f);ev=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh()
 tail.append({'frame':f,'x_width_game_cm':(max(me.vertices[i].co.x for i in tailverts)-min(me.vertices[i].co.x for i in tailverts))*200,'bone_length_sum_cm':sum((arm.pose.bones['tail_%02d'%i].tail-arm.pose.bones['tail_%02d'%i].head).length for i in range(1,8))*200})
 ev.to_mesh_clear()
(OUT/'QA/contact_geometry.json').write_text(json.dumps({'master':rows,'peek':edge,'tail':tail,'scope':'Surface intersection checks of head vs ring and support foot vertex bounds. Does not certify all skin self-intersections.'},indent=2))
print('GEOMETRY_QA',max(r['head_ring_surface_intersections'] for r in rows),min(r['foot_vertices_min_edge_clearance_cm'] for r in edge),tail)
