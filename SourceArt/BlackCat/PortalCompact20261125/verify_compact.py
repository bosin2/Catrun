import bpy,json,sys
from pathlib import Path
from mathutils import Vector
HERE=Path(__file__).parent;sc=bpy.context.scene;a=next(o for o in sc.objects if o.type=='ARMATURE')
def pose(name,f):
 a.animation_data.action=bpy.data.actions[name];sc.frame_set(f);bpy.context.view_layer.update();return {p.name:p.matrix.copy() for p in a.pose.bones}
names=['AN_CompactPortal_WalkReview','AN_CompactPortal_SeatedListenTouch','AN_CompactPortal_HipsBackWiggle','AN_CompactPortal_SeatedTakeoff','AN_CompactPortal_AirReach'];joins=[]
for left,right in zip(names,names[1:]):
 p=pose(left,int(bpy.data.actions[left].frame_range[1]));q=pose(right,1);joins.append({'from':left,'to':right,'max_position_error_m':max((p[n].translation-q[n].translation).length for n in p)})
body=bpy.data.objects['BlackCat_PortalBody'];retained=bpy.data.objects['SK_BlackCat_Final'];pins={};portal=json.loads((HERE/'QA/contact_and_ground.json').read_text())['portal_plane_y'];clearance=[]
for side in ['L','R']:
 group=body.vertex_groups['QA_Foot_F_'+side].index;ids=[v.index for v in body.data.vertices if any(e.group==group and e.weight>.5 for e in v.groups)];values=[]
 for f in range(1,54):
  pose(names[2],f);ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();values.append([me.vertices[i].co.copy() for i in ids]);ev.to_mesh_clear()
 pins[side]=max((values[f][i]-values[0][i]).length for f in range(len(values)) for i in range(len(ids)))
for f in [1,14,38,53]:
 pose(names[2],f);ev=retained.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();clearance.append({'frame':f,'face_portal_gap_m':min(v.co.y for v in me.vertices)-portal});ev.to_mesh_clear()
report={'joins':joins,'prepare_forepaw_mesh_max_displacement_m':pins,'prepare_clearance':clearance,'bones':len(a.data.bones),'root_motion':False}
(HERE/'QA/native_verification.json').write_text(json.dumps(report,indent=2),encoding='utf8')
sys.path.insert(0,'C:/Users/whghk/.codex/skills/blender-asset-qa/scripts');import qa_check
a.data.pose_position='REST';bpy.context.view_layer.update();structural=qa_check.run(objects=[body.name],profile='game',eps=.0001,tol=.002);a.data.pose_position='POSE'
(HERE/'QA/compact_rest_structural.json').write_text(json.dumps(structural,indent=2),encoding='utf8')
bpy.ops.wm.open_mainfile(filepath=str(HERE/'SC_BlackCat_CompactPortal_Review.blend'));sc=bpy.context.scene
for f in [179,268,280]:
 sc.frame_set(f+1);sc.render.filepath=str(HERE/'QA'/f'native_reopen_{f:04}.png');bpy.ops.render.render(write_still=True)
# Identical camera and scale let the user judge the actual proportion change.
for label,path,act in [('before',HERE.parent/'PortalSeated20261125/SK_BlackCat_SeatedPortal_Review.blend','AN_Portal_SeatedListenTouch'),('after',HERE/'SK_BlackCat_CompactPortal.blend','AN_CompactPortal_SeatedListenTouch')]:
 bpy.ops.wm.open_mainfile(filepath=str(path));sc=bpy.context.scene;a=next(o for o in sc.objects if o.type=='ARMATURE');a.animation_data.action=bpy.data.actions[act];sc.frame_set(32)
 sc.render.engine='BLENDER_WORKBENCH';sc.render.resolution_x=700;sc.render.resolution_y=700;sc.render.resolution_percentage=100;sc.display.shading.color_type='MATERIAL';sc.display.shading.light='STUDIO';sc.display.shading.show_cavity=True;sc.display.shading.show_shadows=True;sc.display.shading.background_type='WORLD';sc.world=bpy.data.worlds.new('ComparisonWorld');sc.world.color=(.17,.18,.20)
 cam=bpy.data.objects.new('CompareCamera',bpy.data.cameras.new('CompareCamera'));sc.collection.objects.link(cam);sc.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=.30;cam.location=(.35,-.42,.16);cam.rotation_euler=(Vector((0,0,.11))-cam.location).to_track_quat('-Z','Y').to_euler()
 bpy.ops.mesh.primitive_plane_add(size=1,location=(0,0,-.001));mat=bpy.data.materials.new('CompareFloor');mat.diffuse_color=(.2,.22,.24,1);bpy.context.object.data.materials.append(mat)
 sc.render.filepath=str(HERE/'Previews'/f'Comparison_{label}.png');bpy.ops.render.render(write_still=True)
print('NATIVE_COMPACT_VERIFIED',json.dumps(report),flush=True)
