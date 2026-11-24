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
OLD_END = 575
WALK_START, WALK, STOP = 57, 177, 189
REAR, SIDE, JUMP, LIFT, AIR_END, END = 195, 231, 231, 255, 294, 312
HIDE, BLEND = AIR_END, 8
THRESHOLD_Y, WALK_SPEED = -15., 79.
START_Y = THRESHOLD_Y - 2 * WALK_SPEED
SPEED_PER_FRAME = .70
WALK_Y = START_Y - SPEED_PER_FRAME * WALK
INSPECT_Y = WALK_Y - SPEED_PER_FRAME * (STOP-WALK)/2
PORTAL_Y, ENTRY_Y = INSPECT_Y - 72., INSPECT_Y - 150.
CUTS = ((0,WALK_START), (WALK_START,REAR), (REAR,SIDE), (SIDE,END))
CAMERA_NAMES = ('DoorFace','FrontTracking','RearPortal','JumpFollow')
PREVIOUS_CAMERAS = ('DoorFace','DoorGlance','FrontTracking','RearPortal','SidePreparation','JumpFollow')
FOV = (72., 72., 89., 80.)
FOCUS = (78.,61.,262.,119.)
ATTACHED = frozenset((0,1))
CLIPS = (h.CLIP_DIR+'AN_BlackCat_CautiousWalk', h.CLIP_DIR+'AN_BlackCat_Idle', h.CLIPS[2])
RESTORE = u.MovieSceneCompletionMode.RESTORE_STATE
PAWS = ('paw_f_l', 'paw_f_r', 'paw_h_l', 'paw_h_r')
DOOR_TAG, RIGHT_TAG = 'CatrunDepartureRearDoor','CatrunDepartureRearDoorRight'
PROXY, DOOR_LABEL = 'DepartureRearDoorProxy','S1_Door_ExitToStage2_Open'
RIGHT_LABEL, FRAME_LABEL = 'S1_ExitToStage2_Leaf_R','S1_DoorFrame_ExitToStage2'
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
    # Blending to a stationary endpoint preserves a constant gait from each actual entry.
    rows=[(0,WALK_Y,25.2),(WALK,WALK_Y,25.2)]
    for i in range(1,13):
        t=i/12
        rows.append((WALK+(STOP-WALK)*t,WALK_Y-SPEED_PER_FRAME*(STOP-WALK)*(t-t*t/2),25.2))
    rows.append((JUMP+11*(LIFT-JUMP)/17.5,INSPECT_Y,25.2))
    for i in range(1,9):
        t=i/8
        rows.append((JUMP+(11+6.5*t)*(LIFT-JUMP)/17.5,INSPECT_Y-1.2*t*t,25.2))
    for i in range(1,65):
        t=i/64
        distance=.08*t+.92*t*t*(2-t)
        rows.append((LIFT+(AIR_END-LIFT)*t, INSPECT_Y-1.2+(ENTRY_Y-INSPECT_Y+1.2)*distance,
                     25.2+14*t+58*math.sin(math.pi*t)**1.25))
    rows.append((END,ENTRY_Y,39.2))
    return [(f,y) for f,y,z in rows],[(f,z) for f,y,z in rows]


Y_KEYS,Z_KEYS=cat_curve()


def position(frame, arrival=(101.,START_Y,25.2)):
    weight=min(frame/WALK,1.)
    target=(101.,h.interpolate(Y_KEYS,frame),h.interpolate(Z_KEYS,frame))
    return tuple(h.lerp(a,b,weight) for a,b in zip(arrival,target))


def camera_curves():
    # The door stays behind the face. A small rise shows its closure without reversing the axis.
    # At the walking cut both pawn-relative cameras share the exact incoming pose and lens.
    front=(85.,6.,7.)
    eyes=(8.,0.,0.)
    return [[h.camera_key(f,loc,target) for f,loc,target in rows] for rows in (
        [(0,(88.,5.,2.),eyes),(26,(88.,5.,3.),eyes),
         (42,(88.,9.,13.),(5.,0.,0.)),(WALK_START,front,eyes)],
        [(WALK_START,front,eyes),(96,(80.,5.,6.),eyes),(WALK,(64.,3.,4.),eyes),
         (STOP,(64.,3.,4.),eyes),(REAR,(64.,3.,4.),eyes)],
        [(REAR,(85.,PORTAL_Y+281.,13.),(101.,PORTAL_Y,90.)),
         (SIDE,(83.,PORTAL_Y+275.,13.),(101.,PORTAL_Y,90.))],
        [(SIDE,(17.,INSPECT_Y+27.,35.),(101.,INSPECT_Y+1.,24.)),
         (LIFT,(18.,INSPECT_Y+28.,36.),(101.,INSPECT_Y-5.,25.)),
         (266,(22.,INSPECT_Y+31.,47.),(101.,INSPECT_Y-27.,61.)),
         (280,(30.,INSPECT_Y+49.,59.),(101.,PORTAL_Y,80.)),
         (AIR_END,(41.,INSPECT_Y+65.,62.),(101.,PORTAL_Y,84.)),
         (END,(43.,INSPECT_Y+67.,62.),(101.,PORTAL_Y,84.))]
    )]


CAMERAS=camera_curves()
# Sequence-only values in the installed BlueLight's unitless scale and the fill's lumens.
LIGHT_KEYS=((0,300.),(WALK_START,360.),(96,1150.),(138,3500.),(WALK,8000.),(SIDE,8000.),(AIR_END,4800.))
SOFT_FILL='PortalApproachFill'
FILL_KEYS=((0,320.),(39,320.),(WALK_START,245.),(WALK,100.),(SIDE,180.),(LIFT,180.),(AIR_END,105.))
PREVIOUS_SEQUENCE_SHA='3f132fbb7d40b8bba9757404a48aa6eef91a73b6116b775a4ba70a2faa688165'


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
    speed = (SPEED_PER_FRAME*30.) / cm_s
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


def section(binding, kind):
    tracks=binding.find_tracks_by_type(kind)
    return h.property_section(binding,kind) if tracks else binding.add_track(kind).add_section()


def axes(section_, rows):
    section_.set_range(0,END)
    section_.set_completion_mode(RESTORE)
    for i,ch in enumerate(h.transform_channels(section_)):
        values=[(f,xyz[i]) for f,xyz in rows]
        h.write_keys(ch,values,values[0][1])


def leaf_curve(door):
    loc, rot, scale = door.get_actor_location(),door.get_actor_rotation(),door.get_actor_scale3d()
    rows=[]
    for f in (0,4,8,12,16,20,24,28,32,36,39,END-1):
        t=min(1.,f/39.)
        yaw=rot.yaw*(1-t*t*(3.-2.*t))
        rows.append((f,(*h.tuple3(loc),rot.roll,rot.pitch,yaw,*h.tuple3(scale))))
    return rows


def camera_tracks(seq,parts):
    cat=parts['bindings'][0]
    cut_track=h.only(t for t in seq.get_tracks() if isinstance(t,u.MovieSceneCameraCutTrack))
    for cut in list(cut_track.get_sections()):
        cut_track.remove_section(cut)
    for i,(name,curve,fov,(start,end)) in enumerate(zip(CAMERA_NAMES,CAMERAS,FOV,CUTS)):
        if i<2:
            camera=parts['bindings'][3+i]
        else:
            camera=seq.add_spawnable_from_class(u.CameraActor.static_class())
        camera.set_name(name)
        spawn=section(camera,u.MovieSceneSpawnTrack)
        spawn.set_range(0,END)
        spawn.set_completion_mode(RESTORE)
        h.only(spawn.get_all_channels()).set_default(True)
        axes(section(camera,u.MovieScene3DTransformTrack),curve)
        if i in ATTACHED:
            attach=section(camera,u.MovieScene3DAttachTrack)
            attach.set_range(0,END)
            attach.set_completion_mode(RESTORE)
            attach.set_constraint_binding_id(seq.get_binding_id(cat))
            for prop in ('attachment_location_rule','attachment_rotation_rule','attachment_scale_rule'):
                attach.set_editor_property(prop,u.AttachmentRule.KEEP_RELATIVE)
        component=camera.get_object_template().get_editor_property('camera_component')
        component.modify()
        component.set_field_of_view(fov)
        settings=component.get_editor_property('post_process_settings').copy()
        for prop,value in (('depth_of_field_fstop',2.4 if i==0 else 8.),
                           ('depth_of_field_focal_distance',FOCUS[i]),
                           ('motion_blur_amount',.08)):
            settings.set_editor_property('override_'+prop,True)
            settings.set_editor_property(prop,value)
        component.set_editor_property('post_process_settings',settings)
        component.set_editor_property('post_process_blend_weight',1.)
        cut=cut_track.add_section()
        cut.set_range(start,end)
        cut.set_camera_binding_id(seq.get_binding_id(camera))
        cut.set_completion_mode(u.MovieSceneCompletionMode.KEEP_STATE)


def patch(seq,left,right,motion):
    assert seq.get_playback_end()==OLD_END,seq.get_playback_end()
    seq.modify()
    h.CAMERAS=('Front_BackwardTracking','Face_BlueInspection','Rear_PortalJump')
    parts=h.sequence_parts(seq)
    seq.set_playback_end(END)
    cat=parts['bindings'][0]
    for part in h.property_track(cat,u.MovieScene3DTransformTrack).get_sections():
        part.set_range(0,END)
    for ch,keys in zip(h.transform_channels(parts['cat'])[1:3],(Y_KEYS,Z_KEYS)):
        h.write_keys(ch,keys)
    h.EASING.set_ease_in_duration(parts['cat'],h.tick(WALK))
    anim=sorted(parts['anim_track'].get_sections(),key=h.span)
    specs=((0,WALK+BLEND,0,motion['rate'],0,motion['first_loop_offset']),(WALK,JUMP,1,1.,0,0),
           (JUMP,LIFT,2,17.5/(LIFT-JUMP),0,0),(LIFT,AIR_END,2,18.5/(AIR_END-LIFT),17.5,0),
           (AIR_END,END,2,0.,0,36.-1/800))
    assert len(specs)==len(anim)
    for part,(a,b,i,rate,start,offset) in zip(anim,specs):
        params=part.get_editor_property('params')
        params.set_editor_property('animation',h.load_asset(CLIPS[i]))
        params.set_editor_property('play_rate',u.MovieSceneTimeWarpExtensions.make_time_warp(rate))
        params.set_editor_property('start_frame_offset',u.FrameNumber(h.tick(start)))
        params.set_editor_property('first_loop_start_frame_offset',u.FrameNumber(h.tick(offset)))
        part.set_editor_property('params',params)
        part.set_range(a,b)
        part.set_completion_mode(RESTORE)
    h.EASING.set_ease_out_duration(anim[0],h.tick(BLEND))
    h.EASING.set_ease_in_duration(anim[1],h.tick(BLEND))
    camera_tracks(seq,parts)
    # Portal parent is at 180 degrees and scaled to 125%. Keep fill in front of the face.
    rows=[]
    for f in (0,WALK_START,96,138,WALK,STOP,LIFT,AIR_END):
        _,y,z=position(f)
        rows.append((f,(16.,(PORTAL_Y-y+36.)/1.25,(z+25.)/1.25,0.,0.,0.,1.,1.,1.)))
    axes(parts['light_transform'],rows)
    parts['light'].set_range(0,END)
    h.write_keys(h.only(parts['light'].get_all_channels()),LIGHT_KEYS)
    parts['fade'].set_range(AIR_END,END)
    h.write_keys(h.only(parts['fade'].get_all_channels()),[(AIR_END,0.),(AIR_END+3,0.),(END-1,1.)])
    visibility(cat,False,HIDE)
    original=h.only(b for b in seq.get_bindings() if DOOR_TAG in map(str,b.get_binding_tags()))
    h.only(b for b in seq.get_bindings() if b.get_name()==PROXY).remove()
    original.remove_track(h.property_track(original,u.MovieSceneVisibilityTrack))
    other=seq.add_possessable(right)
    other.tag_binding(RIGHT_TAG)
    for binding,actor in ((original,left),(other,right)):
        axes(section(binding,u.MovieScene3DTransformTrack),leaf_curve(actor))


def fill_binding(seq):
    matches=[b for b in seq.get_bindings() if b.get_name()==SOFT_FILL]
    assert len(matches)<=1
    return matches[0] if matches else None


def bind_fill(seq,portal,parent):
    # Reuse the existing movable portal component. Old sequence IDs remain valid on both maps.
    component=h.only(c for c in portal.get_components_by_class(u.PointLightComponent) if c.get_name()==SOFT_FILL)
    assert component.get_editor_property('mobility')==u.ComponentMobility.MOVABLE
    assert component.get_editor_property('intensity_units')==u.LightUnits.LUMENS
    guid=lambda binding:binding.get_id().export_text()
    before={guid(b) for b in seq.get_bindings()}
    fill=seq.add_possessable(component)
    auto_parent=fill.get_parent()
    found,expected,child=guid(auto_parent),guid(parent),guid(fill)
    after={guid(b) for b in seq.get_bindings()}
    diagnostic=dict(component=component.get_path_name(),registered_parent=found,expected_parent=expected,
                    child=child,new_guids=sorted(after-before),existing_guids=sorted(before))
    print('CATRUN_DEPARTURE_FILL_BINDING',diagnostic)
    assert child not in before and expected in before,diagnostic
    if found==expected:
        assert after-before=={child},diagnostic
    else:
        assert found not in before and after-before=={found,child},diagnostic
        assert auto_parent.get_possessed_object_class()==portal.get_class(),diagnostic
        assert {guid(b) for b in auto_parent.get_child_possessables()}=={child},diagnostic
        fill.set_parent(parent)
        assert not auto_parent.get_child_possessables(),diagnostic
        auto_parent.remove()
    fill.set_name(SOFT_FILL)
    assert guid(fill.get_parent())==expected and {guid(b) for b in seq.get_bindings()}==before|{child},diagnostic
    return fill


def apply_presentation(seq):
    """Reframe existing cameras and lights, keeping every installed binding GUID."""
    seq.modify()
    cut_track=h.only(t for t in seq.get_tracks() if isinstance(t,u.MovieSceneCameraCutTrack))
    cameras={b.get_name():b for b in seq.get_bindings() if b.get_name() in PREVIOUS_CAMERAS}
    ids={seq.get_binding_id(b).export_text():n for n,b in cameras.items()}
    active={n:(first,last) for n,(first,last) in zip(CAMERA_NAMES,CUTS,strict=True)}
    for cut in list(cut_track.get_sections()):
        name=ids[cut.get_camera_binding_id().export_text()]
        if name in active:
            cut.modify()
            cut.set_range(*active[name])
        else:
            cut_track.modify()
            cut_track.remove_section(cut)
    h.CAMERAS=CAMERA_NAMES
    parts=h.sequence_parts(seq)
    for i,(part,component,curve,fov) in enumerate(zip(parts['camera_sections'],parts['camera_components'],CAMERAS,FOV,strict=True)):
        part.modify()
        for axis,channel in enumerate(h.transform_channels(part)):
            values=[(frame,row[axis]) for frame,row in curve]
            for key in list(channel.get_keys()):
                channel.remove_key(key)
            channel.set_default(values[0][1])
            for frame,value in values:
                channel.add_key(u.FrameNumber(frame),value,0.,u.MovieSceneTimeUnit.DISPLAY_RATE,u.MovieSceneKeyInterpolation.AUTO)
        component.modify()
        component.set_field_of_view(fov)
        settings=component.get_editor_property('post_process_settings').copy()
        for prop,value in (('bloom_intensity',.15),('depth_of_field_fstop',3.5 if i==0 else 8.),
                           ('depth_of_field_focal_distance',FOCUS[i]),('motion_blur_amount',.06)):
            settings.set_editor_property('override_'+prop,True)
            settings.set_editor_property(prop,value)
        component.set_editor_property('post_process_settings',settings)
        component.set_editor_property('post_process_blend_weight',1.)
    for part,keys in ((parts['light'],LIGHT_KEYS),(h.property_section(fill_binding(seq),u.MovieSceneFloatTrack),FILL_KEYS)):
        part.modify()
        h.write_keys(h.only(part.get_all_channels()),keys,keys[0][1])


def apply_lens_and_fill(seq,portal):
    seq.modify()
    parent=h.only(b for b in seq.get_bindings() if 'CatrunPortal' in map(str,b.get_binding_tags()))
    fill=fill_binding(seq)
    if not fill:
        fill=bind_fill(seq,portal,parent)
        track=fill.add_track(u.MovieSceneFloatTrack)
        track.set_property_name_and_path('Intensity','Intensity')
        intensity=track.add_section()
        intensity.set_range(0,END)
        intensity.set_completion_mode(RESTORE)
    apply_presentation(seq)
    parts=h.sequence_parts(seq)
    # Parent transform has yaw 180 and 125% uniform scale. Neutral fill comes
    # from the camera-facing side of the fur, the blue key comes from the opposite cheek.
    fill_rows=[]
    blue_rows=[]
    for f in (0,39,WALK_START,96,138,WALK,STOP,SIDE,LIFT,266,280,AIR_END):
        _,y,z=position(f)
        def local(xw,yw,zw):
            return ((101.-xw)/1.25,(PORTAL_Y-yw)/1.25,(zw+.8)/1.25,0.,0.,0.,1.,1.,1.)
        fill_rows.append((f,local(49.,y-43.,z+57.)))
        blue_rows.append((f,local(120.,y-41.,z+24.)))
    axes(section(fill,u.MovieScene3DTransformTrack),fill_rows)
    parts['light_transform'].modify()
    axes(parts['light_transform'],blue_rows)
    parts['light'].modify()
    h.write_keys(h.only(parts['light'].get_all_channels()),LIGHT_KEYS)


def verify_sequence(seq):
    h.CAMERAS=CAMERA_NAMES
    s=h.describe_sequence(seq)
    assert s['end']==END and tuple(s['cuts'])==CUTS,s['cuts']
    assert [x['clip'].split('.')[0] for x in s['animations']]==[CLIPS[0],CLIPS[1],CLIPS[2],CLIPS[2],CLIPS[2]]
    assert [tuple(x['range']) for x in s['animations']]==[(0,WALK+BLEND),(WALK,JUMP),(JUMP,LIFT),(LIFT,AIR_END),(AIR_END,END)]
    assert [c['fov'] for c in s['cameras']]==list(FOV)
    assert s['cat']['ease_ticks']==h.tick(WALK)
    assert not any(b.get_name()==PROXY for b in seq.get_bindings())
    for tag,yaw in ((DOOR_TAG,-100.),(RIGHT_TAG,100.)):
        b=h.only(b for b in seq.get_bindings() if tag in map(str,b.get_binding_tags()))
        part=h.property_section(b,u.MovieScene3DTransformTrack)
        assert part.get_completion_mode()==RESTORE and not b.find_tracks_by_type(u.MovieSceneVisibilityTrack)
        keys=h.key_data(h.transform_channels(part)[5])
        assert abs(keys[0][1]-yaw)<.01 and abs(keys[-1][1])<.01
    assert len(s['light']['keys'])==len(LIGHT_KEYS)
    assert all(abs(actual-v)<.01 and t==h.tick(f) for (t,actual),(f,v) in zip(s['light']['keys'],LIGHT_KEYS))
    parts=h.sequence_parts(seq)
    fill=fill_binding(seq)
    assert fill and fill.get_parent().get_id().export_text()==parts['bindings'][1].get_id().export_text()
    fill_keys=h.key_data(h.only(h.property_section(fill,u.MovieSceneFloatTrack).get_all_channels()))
    assert fill_keys==[(h.tick(f),v) for f,v in FILL_KEYS],fill_keys
    for index,component in enumerate(parts['camera_components']):
        settings=component.get_editor_property('post_process_settings')
        assert settings.override_bloom_intensity and abs(settings.bloom_intensity-.15)<.001
        assert abs(settings.depth_of_field_focal_distance-FOCUS[index])<.01
    for part,curve in zip(parts['camera_sections'],CAMERAS):
        for i,ch in enumerate(h.transform_channels(part)):
            keys=h.key_data(ch)
            assert len(keys)==len(curve) and all(t==h.tick(f) and abs(v-row[i])<.001
                                                for (t,v),(f,row) in zip(keys,curve))
    assert all(h.property_section(parts['bindings'][3+i],u.MovieScene3DAttachTrack).get_constraint_binding_id().export_text()
               ==seq.get_binding_id(parts['bindings'][0]).export_text() for i in ATTACHED)
    return s
