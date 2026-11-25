import bpy,json,math
from pathlib import Path
HERE=Path(__file__).parent;sc=bpy.context.scene;a=next(o for o in sc.objects if o.type=='ARMATURE')
def pose(action,frame):
 a.animation_data.action=bpy.data.actions[action];sc.frame_set(frame);bpy.context.view_layer.update()
 return {p.name:p.matrix.copy() for p in a.pose.bones}
joins=[]
for left,right in [('AN_Portal_WalkReview','AN_Portal_SeatedListenTouch'),('AN_Portal_SeatedListenTouch','AN_Portal_HipsBackWiggle'),('AN_Portal_HipsBackWiggle','AN_Portal_SeatedTakeoff'),('AN_Portal_SeatedTakeoff','AN_Portal_AirReach')]:
 p=pose(left,int(bpy.data.actions[left].frame_range[1]));q=pose(right,1)
 joins.append({'from':left,'to':right,'all_bones':len(p),'max_position_error_m':max((p[n].translation-q[n].translation).length for n in p),'max_matrix_error':max(abs(p[n][i][j]-q[n][i][j]) for n in p for i in range(4) for j in range(4))})
body=bpy.data.objects['BlackCat_PortalBody'];pins={}
retained=bpy.data.objects['SK_BlackCat_Final'];head_clearance=[]
for f in [1,14,38,53]:
 pose('AN_Portal_HipsBackWiggle',f);ev=retained.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();head_clearance.append({'frame':f,'min_y':min(v.co.y for v in me.vertices),'clearance_to_portal_m':min(v.co.y for v in me.vertices)+.105});ev.to_mesh_clear()
for side in ['L','R']:
 g=body.vertex_groups['QA_Foot_F_'+side].index;ids=[v.index for v in body.data.vertices if any(e.group==g and e.weight>.5 for e in v.groups)];samples=[]
 for f in range(1,54):
  pose('AN_Portal_HipsBackWiggle',f);ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();samples.append([me.vertices[i].co.copy() for i in ids]);ev.to_mesh_clear()
 pins[side]=max((samples[f][i]-samples[0][i]).length for f in range(len(samples)) for i in range(len(ids)))
original={n:{'parent':b.parent.name if b.parent else None,'matrix':[list(row) for row in b.matrix_local]} for n,b in a.data.bones.items() if not n.startswith('PSkin_')}
bpy.ops.wm.open_mainfile(filepath='C:/Users/whghk/Desktop/CastleKit/BlackCat/PortalCinematic/SK_BlackCat_PortalCinematic.blend')
orig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');diff=max(abs(orig.data.bones[n].matrix_local[i][j]-v['matrix'][i][j]) for n,v in original.items() for i in range(4) for j in range(4))
report={'joins':joins,'prepare_mesh_forepaw_max_displacement_m':pins,'prepare_face_portal_clearance':head_clearance,'original_bones_preserved':len(original),'original_bind_max_matrix_difference':diff,'original_parents_preserved':all((orig.data.bones[n].parent.name if orig.data.bones[n].parent else None)==v['parent'] for n,v in original.items())}
(HERE/'QA'/'native_joins_and_bind.json').write_text(json.dumps(report,indent=2),encoding='utf8')
bpy.ops.wm.open_mainfile(filepath=str(HERE/'SC_BlackCat_PortalReview.blend'));sc=bpy.context.scene
for frame in [180,269,281]:
 sc.frame_set(frame);sc.render.filepath=str(HERE/'QA'/f'native_reopen_{frame-1:04}.png');bpy.ops.render.render(write_still=True)
print('NATIVE_REVIEW_CHECKED',json.dumps(report),flush=True)
