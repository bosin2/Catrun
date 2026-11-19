"""Stage1 departure shot timing, edit operations, and pose calibration (30 fps)."""
import ast
import math
from pathlib import Path
import statistics
import types

import unreal as u


HERE = Path(__file__).resolve().parent


def definitions(file, last):
    """Load the existing helpers without executing their historical authoring entry points."""
    path = HERE / file
    tree = ast.parse(path.read_text(encoding='utf-8'))
    stop = next(i for i, n in enumerate(tree.body) if
                isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == last for t in n.targets)
                or isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                and isinstance(n.value.func, ast.Name) and n.value.func.id == last)
    m = types.ModuleType(path.stem)
    m.__file__ = str(path)
    exec(compile(ast.Module(body=tree.body[:stop], type_ignores=[]), str(path), 'exec'), m.__dict__)
    return m


h = definitions('upgrade_portal_paw_20261112.py', 'command')
OLD_END = 539
WALK = 386
BLEND = 4
EXTRA = WALK-350
END, JUMP, LIFT, AIR_END, HIDE = (f+EXTRA for f in (539,470,491,526,526))
INSPECT_Y, PORTAL_Y, ENTRY_Y = -450., -493.9189189189189, -558.
WALK_Y = INSPECT_Y + 8.96
CUTS = ((0, 406+EXTRA), (406+EXTRA, 464+EXTRA), (464+EXTRA, END))
CLIPS = (h.CLIP_DIR + 'AN_BlackCat_CautiousWalk', *h.CLIPS[1:])
RESTORE = u.MovieSceneCompletionMode.RESTORE_STATE
PAWS = ('paw_f_l', 'paw_f_r', 'paw_h_l', 'paw_h_r')
DOOR_TAG = 'CatrunDepartureRearDoor'
PROXY = 'DepartureRearDoorProxy'
DOOR_LABEL = 'S1_Door_ExitToStage2_Open'
DEFAULT_SECTION = h.property_section


def primary_section(binding, kind):
    if kind==u.MovieScene3DTransformTrack and 'CatrunCat' in map(str,binding.get_binding_tags()):
        # The independent heading/scale section has no translation keys.
        sections=h.property_track(binding,kind).get_sections()
        if len(sections)==2:
            return h.only(sec for sec in sections if h.transform_channels(sec)[1].get_keys())
    return DEFAULT_SECTION(binding,kind)


h.property_section=primary_section


def cat_curve():
    # A linear section weight interpolates from the actual captured XY to this FIXED
    # endpoint. Blending toward a moving target would multiply velocity during admission.
    rows = [(0., WALK_Y, 25.2), (WALK, WALK_Y, 25.2)]
    for i in range(1, 17):
        t = i / 16
        rows.append((WALK + 19.2*t, WALK_Y - 17.92*(t-t**3+.5*t**4), 25.2))
    rows.append((JUMP + 11 / (17.5/(LIFT-JUMP)), INSPECT_Y, 25.2))
    # The rear paws remain planted during the final short horizontal push.
    for i in range(1, 9):
        t = i / 8
        rows.append((JUMP + (11 + 6.5*t)*(LIFT-JUMP)/17.5, INSPECT_Y-1.2*t*t, 25.2))
    for i in range(1, 65):
        t = i / 64
        # Continuous takeoff, then acceleration into the portal. Keep the tail behind the depth core.
        distance = .08*t + .92*(t*t*(2-t))
        rows.append((LIFT + (AIR_END-LIFT)*t, INSPECT_Y-1.2+(ENTRY_Y-INSPECT_Y+1.2)*distance,
                     25.2 + 14*t + 58*math.sin(math.pi*t)**1.25))
    rows.append((END, ENTRY_Y, 39.2))
    return [(f,y) for f,y,z in rows], [(f,z) for f,y,z in rows]


Y_KEYS, Z_KEYS = cat_curve()


def position(frame, arrival=(101., -115., 25.2)):
    weight = min(frame/WALK,1.)
    target = (101., h.interpolate(Y_KEYS, frame), h.interpolate(Z_KEYS, frame))
    return tuple(h.lerp(a, b, weight) for a, b in zip(arrival, target))


def camera(rows):
    return [h.camera_key(round(f*WALK/350) if f<350 else f+EXTRA, xyz, aim) for f, xyz, aim in rows]


CAMERAS = (
    camera([(0,(88,-272,49),(101,-94,21)),(90,(84,-327,46),(101,-183,20)),
            (190,(76,-390,43),(101,-288,20)),(285,(60,-449,39),(101,-389,22)),
            (350,(44,-484,36),(101,-455,24)),(405,(44,-487,36),(101,-461,24))]),
    camera([(406,(30,-262,13),(101,-482,82)),(428,(28,-244,13),(101,-482,83)),
            (463,(25,-212,13),(101,-483,84))]),
    camera([(464,(9,-414,39),(101,-448,21)),(483,(9,-414,39),(101,-448,19)),
            (491,(9,-413,36),(101,-449,24)),(503,(12,-399,43),(101,-468,71)),
            (518,(20,-366,55),(101,-501,73)),(526,(28,-345,61),(101,PORTAL_Y,79)),
            (538,(28,-345,61),(101,PORTAL_Y,79))]),
)
FOV = (66., 87., 84.)


def calibrate(mesh):
    options = u.AnimPoseEvaluationOptions()
    options.set_editor_property('evaluation_type', u.AnimDataEvalType.SOURCE)
    options.set_editor_property('optional_skeletal_mesh', mesh.get_skeletal_mesh_asset())
    options.set_editor_property('should_retarget', False)
    scale = mesh.get_world_transform().scale3d.y
    walk, inspect, jump = [h.load_asset(p) for p in CLIPS]
    for clip in (walk, inspect, jump):
        assert not clip.get_editor_property('enable_root_motion')
        assert clip.get_editor_property('skeleton') == mesh.get_skeletal_mesh_asset().get_editor_property('skeleton')

    def pose(clip, frame):
        sampled = u.AnimPoseExtensions.get_anim_pose_at_time(clip, frame/30, options)
        return {b: u.AnimPoseExtensions.get_bone_pose(sampled, b, u.AnimPoseSpaces.WORLD).translation
                for b in (*PAWS, 'pelvis','head')}

    n = round(walk.get_editor_property('sequence_length')*30)
    assert n == 288
    poses = [pose(walk, f) for f in range(n+1)]
    stance = [abs(a[b].y-c[b].y)*30*scale for a,c in zip(poses, poses[1:]) for b in PAWS
              if max(a[b].z,c[b].z) < 1.42 and abs(a[b].y-c[b].y) > .12]
    assert len(stance)>30, ('Insufficient planted-paw samples', len(stance), scale)
    cm_s = statistics.median(stance)
    assert 8 < cm_s < 20, ('Unexpected cautious gait speed at installed scale', cm_s, scale)
    speed = (abs(WALK_Y+80.)*30/WALK) / cm_s
    finish = pose(inspect,0)
    differences = [sum((a[b]-finish[b]).length()**2 for b in finish) for a in poses[:-1]]
    best = min(range(n), key=differences.__getitem__)
    # A first-loop offset shifts the first iteration while later cycles still use the entire clip.
    offset = (best - WALK*speed) % n
    return dict(stance_cm_s=cm_s, stance_samples=len(stance), mesh_scale=scale, rate=speed,
                end_source_frame=best, first_loop_offset=offset, boundary_rms=math.sqrt(differences[best]/len(finish))*scale)


def visibility(binding, visible, first=0):
    existing = binding.find_tracks_by_type(u.MovieSceneVisibilityTrack)
    if existing:
        track=h.only(existing)
        section=h.only(track.get_sections())
    else:
        track=binding.add_track(u.MovieSceneVisibilityTrack)
        track.set_property_name_and_path('bHidden','bHidden')
        section=track.add_section()
    section.set_range(0, END)
    section.set_completion_mode(RESTORE)
    channel = h.only(section.get_all_channels())
    for k in channel.get_keys():
        channel.remove_key(k)
    channel.set_default(True)
    channel.add_key(u.FrameNumber(0), visible if not first else True)
    if first:
        channel.add_key(u.FrameNumber(first), visible)


def door_profile(door):
    c = door.static_mesh_component
    center, extent = door.get_actor_bounds(False)
    loc = door.get_actor_location()
    rot = door.get_actor_rotation()
    scale = door.get_actor_scale3d()
    dx,dy = center.x-loc.x,center.y-loc.y
    assert extent.y > 60 and extent.x < 15 and abs(dy) > 55, ('Door pivot is not near an open leaf end', loc,center,extent)
    sign = min((-1,1),key=lambda s: abs(loc.x-s*dy-101))
    assert abs(loc.x-sign*dy-101) < 30 and abs(loc.y+sign*dx) < 60
    return [*h.tuple3(loc), rot.roll,rot.pitch,rot.yaw, *h.tuple3(scale)], rot.yaw+sign*90


def patch(sequence, door, motion):
    parts = h.sequence_parts(sequence)
    upgrade=sequence.get_playback_end()==OLD_END
    assert upgrade or sequence.get_playback_end()==308
    sequence.modify()
    sequence.set_playback_end(END)
    for section in (parts['cat'], parts['light'], parts['light_transform'], *parts['camera_sections'], *parts['spawns']):
        section.set_range(0,END)
    for section,(a,b) in zip(parts['cuts'],CUTS):
        section.set_range(a,b)
    for ch,keys in zip(h.transform_channels(parts['cat'])[1:3], (Y_KEYS,Z_KEYS)):
        h.write_keys(ch,keys)
    h.EASING.set_ease_in_duration(parts['cat'],h.tick(WALK))
    easing=u.find_object(parts['cat'],'EaseInFunction')
    assert easing and easing.get_class().get_name()=='MovieSceneBuiltInEasingFunction',str(easing)
    easing.modify()
    easing.set_editor_property('type',u.MovieSceneBuiltInEasing.LINEAR)
    # The transform blender evaluates only channels with keys or defaults. Retain the
    # original short heading/scale handoff independently of the full-walk XY weight.
    pose=parts['bindings'][0].find_tracks_by_type(u.MovieScene3DTransformTrack)[0].add_section()
    pose.set_range(0,END)
    pose.set_blend_type(u.MovieSceneBlendType.ABSOLUTE)
    pose.set_completion_mode(parts['cat'].get_completion_mode())
    h.EASING.set_ease_in_duration(pose,h.tick(16))
    for i,(base,heading) in enumerate(zip(h.transform_channels(parts['cat']),h.transform_channels(pose))):
        if i<3:
            heading.remove_default()
        else:
            assert not base.get_keys() and base.has_default()
            heading.set_default(base.get_default())
            base.remove_default()
    for section, component, curve,fov in zip(parts['camera_sections'],parts['camera_components'], CAMERAS,FOV):
        component.modify()
        component.set_field_of_view(fov)
        for i,ch in enumerate(h.transform_channels(section)):
            h.write_keys(ch, [(f,axes[i]) for f,axes in curve], curve[0][1][i])
    anim = sorted(parts['anim_track'].get_sections(),key=h.span)
    specs = ((0,WALK+BLEND,0,motion['rate'],0,motion['first_loop_offset']), (WALK,JUMP,1,1.,0,0),
             (JUMP,LIFT,2,17.5/(LIFT-JUMP),0,0), (LIFT,AIR_END,2,18.5/(AIR_END-LIFT),17.5,0),
             (AIR_END,END,2,0.,0,36.-1/800))
    assert len(anim)==len(specs)
    for section,(a,b,clip,rate,start,offset) in zip(anim,specs):
        params = section.get_editor_property('params')
        params.set_editor_property('animation',h.load_asset(CLIPS[clip]))
        params.set_editor_property('play_rate', u.MovieSceneTimeWarpExtensions.make_time_warp(rate))
        params.set_editor_property('start_frame_offset',u.FrameNumber(h.tick(start)))
        params.set_editor_property('first_loop_start_frame_offset',u.FrameNumber(h.tick(offset)))
        section.set_editor_property('params',params)
        section.set_range(a,b)
        section.set_completion_mode(RESTORE)
    h.EASING.set_ease_out_duration(anim[0],h.tick(BLEND))
    h.EASING.set_ease_in_duration(anim[1],h.tick(BLEND))
    # The portal actor has yaw 180. Drive its blue light from 42 cm ahead of the approaching face.
    light_curves = {0:[(0,23),(WALK,23)],1:[(0,PORTAL_Y+80+45),(WALK,PORTAL_Y-WALK_Y+45),
                    (WALK+20,PORTAL_Y-INSPECT_Y+45),(LIFT,PORTAL_Y-INSPECT_Y+45),(AIR_END,-8)],
                    2:[(0,55),(WALK,57),(LIFT,64),(AIR_END,90)]}
    for i,ch in enumerate(h.transform_channels(parts['light_transform'])):
        h.write_keys(ch,light_curves.get(i,[]),[25.,-337.,68.,0.,0.,0.,1.,1.,1.][i])
    h.write_keys(h.only(parts['light'].get_all_channels()),[(0,430.),(WALK,540.),(463+EXTRA,810.),(LIFT,1100.),(AIR_END,1250.)])
    parts['fade'].set_range(AIR_END,END)
    h.write_keys(h.only(parts['fade'].get_all_channels()),[(AIR_END,0.),(530+EXTRA,0.),(END-1,1.)])
    visibility(parts['bindings'][0],False,HIDE)

    if upgrade:
        original=h.only(b for b in sequence.get_bindings() if DOOR_TAG in map(str,b.get_binding_tags()))
        proxy=h.only(b for b in sequence.get_bindings() if b.get_name()==PROXY)
    else:
        original=sequence.add_possessable(door)
        original.tag_binding(DOOR_TAG)
        proxy=sequence.add_spawnable_from_class(u.StaticMeshActor.static_class())
        proxy.set_name(PROXY)
    visibility(original,False)
    component=proxy.get_object_template().static_mesh_component
    component.set_mobility(u.ComponentMobility.MOVABLE)
    component.set_static_mesh(door.static_mesh_component.get_editor_property('static_mesh'))
    for i in range(door.static_mesh_component.get_num_materials()):
        component.set_material(i,door.static_mesh_component.get_material(i))
    component.set_collision_profile_name('NoCollision')
    component.set_editor_property('generate_overlap_events',False)
    spawn=h.property_section(proxy,u.MovieSceneSpawnTrack)
    spawn.set_range(0,END)
    spawn.set_completion_mode(RESTORE)
    h.only(spawn.get_all_channels()).set_default(True)
    move=h.property_section(proxy,u.MovieScene3DTransformTrack) if upgrade else proxy.add_track(u.MovieScene3DTransformTrack).add_section()
    move.set_range(0,END)
    move.set_completion_mode(RESTORE)
    axes, closed=door_profile(door)
    for i,ch in enumerate(h.transform_channels(move)):
        ks=[]
        if i==5:
            for f in (0,15,20,25,30,35,40,45,50,54,END-1):
                t=min(1.,max(0.,(f-15)/39))
                ks.append((f,h.lerp(axes[5],closed,t*t*(3-2*t))))
        h.write_keys(ch,ks,axes[i])


def verify_sequence(seq):
    s=h.describe_sequence(seq)
    assert s['end']==END and tuple(s['cuts'])==CUTS, (s['end'],s['cuts'])
    assert [x['clip'].split('.')[0] for x in s['animations']]==[CLIPS[0],CLIPS[1],CLIPS[2],CLIPS[2],CLIPS[2]]
    assert [tuple(x['range']) for x in s['animations']]==[(0,WALK+BLEND),(WALK,JUMP),(JUMP,LIFT),(LIFT,AIR_END),(AIR_END,END)]
    for i,expected in enumerate((Y_KEYS,Z_KEYS),1):
        keys=s['cat']['keys'][i]
        assert len(keys)==len(expected) and all(abs(t-h.tick(f))<=1 and abs(v-w)<.001 for (t,v),(f,w) in zip(keys,expected))
    assert [c['fov'] for c in s['cameras']]==list(FOV)
    parts=h.sequence_parts(seq)
    assert parts['cat'].get_end_frame()==END and h.EASING.get_ease_in_duration(parts['cat'])==h.tick(WALK)
    assert u.find_object(parts['cat'],'EaseInFunction').get_editor_property('type')==u.MovieSceneBuiltInEasing.LINEAR
    heading=h.only(section for section in h.property_track(parts['bindings'][0],u.MovieScene3DTransformTrack).get_sections()
                   if section!=parts['cat'])
    assert all(not ch.has_default() and not ch.get_keys() for ch in h.transform_channels(heading)[:3])
    assert all(not ch.has_default() and not ch.get_keys() for ch in h.transform_channels(parts['cat'])[3:])
    assert h.EASING.get_ease_in_duration(heading)==h.tick(16)
    one_door=h.only(b for b in seq.get_bindings() if DOOR_TAG in map(str,b.get_binding_tags()))
    proxy=h.only(b for b in seq.get_bindings() if b.get_name()==PROXY)
    assert 'NoCollision'==str(proxy.get_object_template().static_mesh_component.get_collision_profile_name())
    assert h.property_section(one_door,u.MovieSceneVisibilityTrack).get_completion_mode()==RESTORE
    assert str(h.property_track(one_door,u.MovieSceneVisibilityTrack).get_property_path())=='bHidden'
    return s
