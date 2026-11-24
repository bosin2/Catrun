"""Create an isolated animation on the approved rig; never save the source file."""
import bpy,math,json,hashlib
from pathlib import Path
from mathutils import Vector,Quaternion
ROOT=Path('C:/Users/whghk/Catrun');OUT=ROOT/'Saved/Stage3Integration20261125/Animation';OUT.mkdir(parents=True,exist_ok=True)
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');mesh=next(o for o in bpy.data.objects if o.type=='MESH')
scene=bpy.context.scene;scene.render.fps=30
arm.animation_data.action=bpy.data.actions['AN_BlackCat_Idle'];scene.frame_set(1)
base={p.name:(p.location.copy(),p.rotation_quaternion.copy(),p.scale.copy()) for p in arm.pose.bones}
def geometry_hash():
    payload={'verts':[list(v.co) for v in mesh.data.vertices],'faces':[list(p.vertices) for p in mesh.data.polygons],
        'uv':[[list(d.uv) for d in layer.data] for layer in mesh.data.uv_layers],
        'weights':[[[g.group,g.weight] for g in v.groups] for v in mesh.data.vertices],
        'materials':[m.name for m in mesh.data.materials],
        'bones':[(b.name,b.parent.name if b.parent else None,[list(r) for r in b.matrix_local]) for b in arm.data.bones]}
    return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
before=geometry_hash();mouth_local=arm.pose.bones['head'].matrix.inverted()@Vector((0,-.110,.119))
def reset():
    for p in arm.pose.bones:
        loc,rot,scale=base[p.name];p.location=loc;p.rotation_mode='QUATERNION';p.rotation_quaternion=rot;p.scale=scale
def rotate(name,axis,angle):arm.pose.bones[name].rotation_quaternion=base[name][1]@Quaternion(axis,math.radians(angle))
def mouth():return arm.pose.bones['head'].matrix@mouth_local
def pose(neck,head,ear=0,tail=0):
    reset();rotate('neck',(1,0,0),neck);rotate('head',(1,0,0),head)
    rotate('ear_L',(0,0,1),ear);rotate('ear_R',(0,0,1),-ear)
    for i in range(1,8):rotate('tail_'+str(i).zfill(2),(0,0,1),tail*i/7)
    bpy.context.view_layer.update()
# At game scale 2, mesh root is 2.2cm above the supporting floor.
low,high=0.,60.
for _ in range(40):
    mid=(low+high)/2;pose(12,mid)
    if mouth().z>.094:low=mid
    else:high=mid
contact_head=(low+high)/2
pose(12,contact_head);contact=mouth().copy()
pose(-12,contact_head+4);pulled=mouth().copy()
def smooth(t):t=max(0.,min(1.,t));return t*t*(3-2*t)
def envelope(frame):
    if frame<=10:return 0,0,3*math.sin(math.pi*(frame-1)/9),0
    if frame<=25:
        a=smooth((frame-10)/15);return 12*a,contact_head*a,3*(1-a),2*a
    if frame<=30:return 12,contact_head,0,2
    if frame<=45:
        a=smooth((frame-30)/15);return 12-24*a,contact_head+4*a,-5*a,2+4*a
    if frame<=49:return -12,contact_head+4,-5,6
    a=1-smooth((frame-49)/24);return -12*a,(contact_head+4)*a,-5*a,6*a
action=bpy.data.actions.new('AN_BlackCat_ReleaseRing');arm.animation_data.action=action
samples=[];feet={n:arm.pose.bones[n].head.copy() for n in ['paw_F_L','paw_F_R','paw_H_L','paw_H_R']}
max_foot_error=0.;min_z=100.
for frame in range(1,74):
    scene.frame_set(frame);pose(*envelope(frame))
    for p in arm.pose.bones:
        p.keyframe_insert('location',frame=frame,group=p.name);p.keyframe_insert('rotation_quaternion',frame=frame,group=p.name);p.keyframe_insert('scale',frame=frame,group=p.name)
    m=mouth();samples.append({'frame':frame,'time':(frame-1)/30,'mouth_native':list(m),'mouth_actor_cm':[-m.y*200,m.x*200,m.z*200-24]})
    max_foot_error=max(max_foot_error,max((arm.pose.bones[n].head-v).length for n,v in feet.items()))
    ev=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();min_z=min(min_z,min(v.co.z for v in me.vertices));ev.to_mesh_clear()
scene.frame_start=1;scene.frame_end=73;scene.frame_set(1)
assert before==geometry_hash(),'Source geometry/rig altered'
assert max_foot_error<1e-6,(max_foot_error,'Foot movement')
assert min_z>-.0005,('Ground penetration',min_z)
assert abs(samples[24]['mouth_native'][2]-.094)<1e-5
assert Vector(samples[0]['mouth_native']).__sub__(Vector(samples[-1]['mouth_native'])).length<1e-6
# Export only this action; retain the armature object name used by the source skeleton.
for o in bpy.context.selected_objects:o.select_set(False)
arm.select_set(True);bpy.context.view_layer.objects.active=arm
fbx=OUT/'AN_BlackCat_ReleaseRing.fbx'
bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'ARMATURE'},
    apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Z',axis_up='Y',add_leaf_bones=False,
    use_armature_deform_only=True,armature_nodetype='NULL',bake_anim=True,bake_anim_use_all_actions=False,
    bake_anim_use_nla_strips=False,bake_anim_simplify_factor=0.,bake_anim_step=1.,use_custom_props=False)
blend=OUT/'SK_BlackCat_ReleaseRing.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend),copy=True)
report={'source':bpy.data.filepath,'geometry_and_rig_sha256_before':before,'geometry_and_rig_sha256_after':geometry_hash(),
    'bones':len(arm.data.bones),'frames':73,'fps':30,'seconds':2.4,'contact_frame':25,'pull_start_frame':30,'commit_frame':45,'release_frame':49,
    'contact_head_degrees':contact_head,'contact_native':list(contact),'pulled_native':list(pulled),
    'max_foot_drift_game_cm':max_foot_error*200,'min_mesh_z_game_cm':min_z*200,
    'samples':samples,'fbx':str(fbx),'blend':str(blend),'success':True}
(OUT/'animation_report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print('CAT_INTERACTION_AUTHORED',report['contact_native'],report['pulled_native'])
