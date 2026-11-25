import bpy,json,math
import numpy as np
from pathlib import Path
from mathutils import Vector
O=Path(__file__).resolve().parents[1];a=bpy.data.objects['ARM_BlackCat_RigV2'];m=bpy.data.objects['SK_BlackCat_RigV2'];sc=bpy.context.scene
# Local shading only: all head, torso, ear, paw and tail facets retain flat shading.
jointnames=['forearm_L','forearm_R','shin_L','shin_R','hock_L','hock_R']
smoothcount=0
for p in m.data.polygons:
    if p.material_index!=0:continue
    c=sum((m.data.vertices[i].co for i in p.vertices),Vector())/len(p.vertices)
    if c.z<.066 and any((c-a.data.bones[n].head_local).length<.015 for n in jointnames):p.use_smooth=True;smoothcount+=1
# Keep lower muzzle travel modest and taper cheek weights towards the corners.
jaw=m.vertex_groups['jaw'];head=m.vertex_groups['head'];changed=0
for v in m.data.vertices:
    w=next((g.weight for g in v.groups if g.group==jaw.index),0)
    if w and v.co.z>.085 and any(p.material_index==0 and v.index in p.vertices for p in m.data.polygons):
        t=max(0,min(1,(.026-abs(v.co.x))/.012));removed=w*(1-t)
        if removed>1e-6:
            jaw.add([v.index],w*t,'REPLACE');old=next((g.weight for g in v.groups if g.group==head.index),0);head.add([v.index],old+removed,'REPLACE');changed+=1
for fc in a.animation_data.drivers:
    if fc.data_path=='pose.bones["CTRL_jaw"].rotation_euler':fc.driver.expression='-v*0.32'
    if fc.data_path=='pose.bones["CTRL_tongue"].location':fc.driver.expression='v*0.024'
# One-click neutral authoring template (action is stored; source opens in legacy Idle).
old=a.animation_data.action;a.animation_data.action=None
for p in a.pose.bones:p.matrix_basis.identity()
for k in ['bend','side_bend','twist']:a.pose.bones['CTRL_spine'][k]=0.
for k in ['blink_L','blink_R','look_x','look_z']:a.pose.bones['CTRL_face'][k]=0.
a.pose.bones['CTRL_jaw']['open']=0.;a.pose.bones['CTRL_tongue']['extend']=0.
a['controls_enabled']=1.
act=bpy.data.actions.new('V2_AUTHORING_TEMPLATE');act.use_fake_user=True;a.animation_data.action=act
a.keyframe_insert('["controls_enabled"]',frame=1)
for p in a.pose.bones:
    if p.name.startswith('CTRL_'):
        for channel in ['location','rotation_quaternion','rotation_euler']:p.keyframe_insert(channel,frame=1,group=p.name)
        for k in p.keys():
            if isinstance(p[k],(int,float)):p.keyframe_insert(f'["{k}"]',frame=1,group=p.name)
a.animation_data.action=old;a['controls_enabled']=0.;sc.frame_set(1);a.update_tag();bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=str(O/'SK_BlackCat_RigV2.blend'))
(O/'QA/finish.json').write_text(json.dumps({'joint_faces_smoothed':smoothcount,'jaw_vertices_tapered':changed,'global_subdivision':False,'body_rest_coordinates_edited':False},indent=2));print('FINISH_AUTHORING',smoothcount,changed)
