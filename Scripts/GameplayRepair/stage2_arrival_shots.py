"""Edit the existing Stage2 arrival tracks. Distances and orthographic widths are centimetres."""
import datetime
import json
import math
import os
from pathlib import Path
import shutil
import traceback

import unreal as u
from stage2_arrival_graph import arrival_timing, audit_graph


END = 504
PORTAL_END = 91
CUTS = (('Entrance', 0, 89), ('RearWalk', 89, 200), ('Face', 200, 230),
        ('Puzzle', 230, 306), ('FaceReturn', 306, END))
PLANES = {'Surface': (1.05, 1.80), 'PortalDepthCore': (1.05, 1.80), 'PortalAetherHalo': (1.18, 2.02)}
ORIGINAL_LS = '74966a96a1f9783f0bc136482f4457e08aebd7196b7041063c228a43af3701f5'
ORIGINAL_BP = '764bd1be1ab27631e3feb8055e66da9dd4979eef701b6aeaf95798e3cddc7cc7'
PERSISTENT = ('Gameplay Cat Visibility', 'CosmeticCat', 'ArrivalPortal')
STYLE_COMPONENT = 'PortalOrbitSparks'
STYLE_MESH = '/Game/Cinematics/Stage1/Portal/Followup20261112/SM_PortalOrbitSparks.SM_PortalOrbitSparks'
ANIM_SPANS = {'JumpDown': (18, 57), 'Landing': (57, 93), 'Walk': (89, 200), 'Idle': (196, END)}


POV_EYE = (1374.7266, 3680.1402, 33.6515)
# Eye-centred, level-roll gaze; values are (frame, pitch, yaw, horizontal FOV).
POV_GAZE = ((230,12.,3.,94.), (239,12.,3.,94.),
            (250,9.2,-16.,90.), (267,3.,-61.,78.),
            (284,-3.1,-110.,61.), (295,-5.6,-126.7,55.), (305,-5.6,-126.7,55.))


def shot_paths(cat_pov=True):
    def at(frame, eye, aim, width):
        look = u.MathLibrary.find_look_at_rotation(u.Vector(*eye), u.Vector(*aim))
        return (frame, [*eye, 0., look.pitch, look.yaw, 1., 1., 1.], width)

    first_face = at(200, (1385, 3590, 38.5), (1375, 3689, 28.5), 84)
    return_start = at(306, (1439, 3632, 41.5), (1375, 3689, 28.5), 84)
    statue = ((1625, 3616, 301), (1575, 3690, 66), 460)
    plate = ((1245, 3356, 240.6), (1195, 3430, 5.6), 425)
    paths = {
        'Entrance': [at(0, (1545, 3690, 182), (1375, 3930, 96), 490),
                     at(18, (1545, 3690, 182), (1375, 3930, 96), 490),
                     at(57, (1545, 3690, 182), (1375, 3890, 85), 490)],
        'RearWalk': [at(89, (1405, 3930, 81), (1375, 3785.8, 21), 145),
                     at(97, (1405, 3926, 81), (1375, 3781.8, 21), 145),
                     at(190, (1405, 3835, 81), (1375, 3690.8, 21), 145),
                     at(199, (1405, 3830, 81), (1375, 3685.8, 21), 145)],
        'Face': [first_face],
        'Puzzle': [at(230, *statue), at(249, *statue),
                   at(267, (1435, 3486, 270.8), (1385, 3560, 35.8), 610),
                   at(285, *plate), at(305, *plate)],
        'FaceReturn': [return_start, (324, return_start[1], 84)]}
    if cat_pov:
        paths['Puzzle']=[(f,[*POV_EYE,0.,pitch,yaw,1.,1.,1.],fov) for f,pitch,yaw,fov in POV_GAZE]
    yaw0, pitch0 = return_start[1][5], return_start[1][4]
    end_yaw, end_pitch, end_radius = 212., -50., 276.5
    end_aim = [1515 + end_radius * math.cos(math.radians(end_yaw)),
               3815 + end_radius * math.sin(math.radians(end_yaw)),
               359 + end_radius * math.tan(math.radians(end_pitch))]
    for f in [*range(334, 443, 10), 443]:
        t = (f - 324) / 119.
        s = t*t*(3. - 2.*t)
        aim = [a + (b-a)*s for a, b in zip((1375., 3689., 28.5), end_aim)]
        radius = math.hypot(64, 57)*(1-s) + end_radius*s
        yaw = yaw0 + (end_yaw-yaw0)*s
        pitch = pitch0 + (end_pitch-pitch0)*s
        eye = [aim[0] - radius*math.cos(math.radians(yaw)), aim[1] - radius*math.sin(math.radians(yaw)),
               aim[2] - radius*math.tan(math.radians(pitch))]
        paths['FaceReturn'].append((f, [*eye, 0., pitch, yaw, 1., 1., 1.], 84*(910/84)**s))
    return paths


def bindings(seq):
    result = {b.get_name(): b for b in seq.get_bindings()}
    assert len(result) == len(seq.get_bindings()), 'Duplicate binding names'
    return result


def section(binding, typ):
    track, = binding.find_tracks_by_type(typ)
    part, = track.get_sections()
    return part


def frameof(key):
    return key.get_time(u.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value


def set_curve(channel, keys, interpolation=u.MovieSceneKeyInterpolation.AUTO):
    for key in list(channel.get_keys()):
        channel.remove_key(key)
    channel.set_default(keys[0][1])
    for f, v in keys:
        channel.add_key(u.FrameNumber(f), v, 0., u.MovieSceneTimeUnit.DISPLAY_RATE, interpolation)


def set_transforms(binding, rows, stop=END):
    tracks = binding.find_tracks_by_type(u.MovieScene3DTransformTrack)
    part = section(binding, u.MovieScene3DTransformTrack) if tracks else binding.add_track(u.MovieScene3DTransformTrack).add_section()
    part.set_range(0, stop)
    part.set_completion_mode(u.MovieSceneCompletionMode.RESTORE_STATE)
    channels = part.get_channels_by_type(u.MovieSceneScriptingDoubleChannel)
    assert len(channels) == 9
    for i, ch in enumerate(channels):
        set_curve(ch, [(f, v[i]) for f, v in rows])


def float_track(binding, name, keys, stop):
    track = binding.add_track(u.MovieSceneFloatTrack)
    track.set_property_name_and_path(name, name)
    part = track.add_section()
    part.set_range(0, stop)
    part.set_completion_mode(u.MovieSceneCompletionMode.RESTORE_STATE)
    channel, = part.get_channels_by_type(u.MovieSceneScriptingFloatChannel)
    set_curve(channel, keys)


def guid(binding):
    return binding.get_id().export_text()


def component_binding(seq, parent, component, name):
    # FindOrAddBinding recursively registers the owner. A transient editor actor
    # cannot necessarily be rediscovered by its world locator between calls.
    before={guid(b) for b in seq.get_bindings()}
    child = seq.add_possessable(component)
    after={guid(b) for b in seq.get_bindings()}
    temporary=child.get_parent()
    diagnostic={'component':component.get_path_name(),'owner':component.get_owner().get_path_name(),
                'child':guid(child),'registered_parent':guid(temporary),'destination':guid(parent),
                'new_guids':sorted(after-before)}
    print('STAGE2_COMPONENT_REGISTRATION',json.dumps(diagnostic))
    assert after-before=={guid(temporary),guid(child)},diagnostic
    assert temporary.get_possessed_object_class()==component.get_owner().get_class(),diagnostic
    assert child.get_possessed_object_class()==component.get_class(),diagnostic
    child.set_parent(parent)
    child.set_name(name)
    assert guid(child.get_parent())==guid(parent),diagnostic
    assert not temporary.get_child_possessables(),diagnostic
    temporary.remove()
    assert {guid(b) for b in seq.get_bindings()}-before=={guid(child)},diagnostic
    return child


def migrate_seq(h, seq, portal, lens):
    old = bindings(seq)
    assert set(old) == {*PERSISTENT, 'Entrance', 'Puzzle', 'GateAndReturn'}
    seq.modify()
    seq.set_playback_end(END)
    section(old[PERSISTENT[0]], u.MovieSceneVisibilityTrack).set_range(0, END)
    cat = old['CosmeticCat']
    section(cat, u.MovieSceneSpawnTrack).set_range(0, END)
    vis = section(cat, u.MovieSceneVisibilityTrack)
    vis.set_range(0, END)
    channel, = vis.get_channels_by_type(u.MovieSceneScriptingBoolChannel)
    keys = sorted(channel.get_keys(), key=frameof)
    assert [(frameof(k), k.get_value()) for k in keys] == [(0, False), (5, True)]
    keys[1].set_time(u.FrameNumber(23))
    cat_transform = section(cat, u.MovieScene3DTransformTrack)
    cat_transform.set_range(0, END)
    channels = cat_transform.get_channels_by_type(u.MovieSceneScriptingDoubleChannel)
    old_keys = [[(frameof(k), k.get_value()) for k in ch.get_keys()] for ch in channels]
    shifted = []
    for row in zip(*old_keys, strict=True):
        f = row[0][0]
        assert all(k[0] == f for k in row)
        values = [k[1] for k in row]
        values[1] -= {0:26., 5:26., 14:18., 28:5.}.get(f, 0.)
        shifted.append((END if f == 360 else f+18, values))
    set_transforms(cat, [(0, shifted[0][1]), *shifted])
    animation, = cat.find_tracks_by_type(u.MovieSceneSkeletalAnimationTrack)
    for part in animation.get_sections():
        clip = part.get_editor_property('params').animation.get_name().removeprefix('AN_BlackCat_')
        part.set_range(*ANIM_SPANS[clip])

    pb = old['ArrivalPortal']
    # Explicit false spawn key at 91 works even with a restoring spawn section.
    spawn = section(pb, u.MovieSceneSpawnTrack)
    spawn.set_range(0, END)
    ch, = spawn.get_channels_by_type(u.MovieSceneScriptingBoolChannel)
    ch.set_default(True)
    ch.add_key(u.FrameNumber(0), True)
    ch.add_key(u.FrameNumber(PORTAL_END), False)
    set_transforms(pb, [(0, [1375., 3983., 0., 0., 0., 0., 1., 1., 1.])], PORTAL_END)
    temporary = h.ACTORS.spawn_actor_from_class(portal.generated_class(), u.Vector(), u.Rotator(), transient=True)
    try:
        for name, xy in PLANES.items():
            obj = temporary.get_editor_property(name)
            child = component_binding(seq, pb, obj, name)
            t = obj.get_relative_transform()
            r = t.rotation.rotator()
            assert all(abs(v-w)<.01 for v,w in zip(h.vector(t.scale3d), (*xy, 1.))), name
            rows = [(f, [*h.vector(t.translation), r.roll, r.pitch, r.yaw, xy[0]*s, xy[1]*s, 1.])
                    for f, s in ((0,1.), (62,1.), (72,.8), (86,.02))]
            set_transforms(child, rows, PORTAL_END)
            track = child.add_track(u.MovieSceneVisibilityTrack)
            track.set_property_name_and_path('bHiddenInGame', 'bHiddenInGame')
            part = h.section_range(track.add_section(), 0, PORTAL_END)
            visible, = part.get_channels_by_type(u.MovieSceneScriptingBoolChannel)
            visible.set_default(True)
            visible.add_key(u.FrameNumber(0), True)
            visible.add_key(u.FrameNumber(87), False)
        light = component_binding(seq, pb, temporary.get_editor_property('BlueLight'), 'BlueLight')
        float_track(light, 'Intensity', [(0,650.), (62,650.), (72,520.), (87,0.)], PORTAL_END)
    finally:
        h.ACTORS.destroy_actor(temporary)

    cuts, = seq.get_tracks()
    for part in list(cuts.get_sections()):
        cuts.remove_section(part)
    paths = shot_paths(cat_pov=False)
    for name, first, end in CUTS:
        if name in old:
            camera = old[name]
        elif name == 'FaceReturn':
            camera = old['GateAndReturn']
            camera.set_name(name)
        else:
            camera = seq.add_spawnable_from_class(u.CameraActor.static_class())
            camera.set_name(name)
        h.section_range(section(camera, u.MovieSceneSpawnTrack), 0, END)
        comp = camera.get_object_template().get_editor_property('CameraComponent')
        for prop in ('projection_mode','field_of_view','aspect_ratio','constrain_aspect_ratio'):
            comp.set_editor_property(prop, lens.get_editor_property(prop))
        path = paths[name]
        comp.set_editor_property('ortho_width', path[0][2])
        set_transforms(camera, [(f, row) for f, row, _ in path])
        if name in ('Puzzle', 'FaceReturn'):
            temp = h.ACTORS.spawn_actor_from_class(u.CameraActor, u.Vector(), u.Rotator(), transient=True)
            try:
                child = component_binding(seq, camera, temp.get_component_by_class(u.CameraComponent), name+'Lens')
                float_track(child, 'OrthoWidth', [(f,w) for f,_,w in path], END)
            finally:
                h.ACTORS.destroy_actor(temp)
        part = cuts.add_section()
        part.set_range(first,end)
        part.set_camera_binding_id(seq.get_binding_id(camera))
        part.set_completion_mode(u.MovieSceneCompletionMode.KEEP_STATE)


def signature(seq):
    """Cold-readable values of every authored track including section ownership and channels."""
    result = {}
    for name, b in sorted(bindings(seq).items()):
        parent = b.get_parent()
        item = {'guid':b.get_id().export_text(), 'parent':parent.get_id().export_text(),
                'tracks':[], 'tags':sorted(map(str,b.get_binding_tags()))}
        if name in {entry[0] for entry in CUTS}:
            c = b.get_object_template().get_editor_property('CameraComponent')
            item['lens'] = [str(c.projection_mode), c.ortho_width, c.aspect_ratio, c.field_of_view]
        for track in b.get_tracks():
            data = {'type':track.get_class().get_name(), 'sections':[]}
            if isinstance(track,u.MovieScenePropertyTrack):
                data['property'] = str(track.get_property_path())
            for part in track.get_sections():
                row = {'span':[part.get_start_frame(),part.get_end_frame()], 'completion':str(part.get_completion_mode())}
                if isinstance(part,u.MovieSceneSkeletalAnimationSection):
                    p=part.get_editor_property('params')
                    row.update(clip=p.animation.get_path_name(),rate=p.play_rate.export_text(),
                               offset=p.first_loop_start_frame_offset.value, skip_notifies=p.skip_anim_notifiers,
                               custom=p.force_custom_mode)
                curves = []
                for cls in (u.MovieSceneScriptingBoolChannel,u.MovieSceneScriptingDoubleChannel,u.MovieSceneScriptingFloatChannel):
                    for ch in part.get_channels_by_type(cls):
                        curves.append({'name':str(ch.get_name()), 'default':ch.get_default(),
                            'keys':[[frameof(k),k.get_value()] for k in ch.get_keys()]})
                if curves:
                    # Scripting channel UObject names get generated anew on each visit.
                    for curve in curves:
                        del curve['name']
                    row['channels']=curves
                data['sections'].append(row)
            item['tracks'].append(data)
        result[name]=item
    return result


def close(a,b):
    return abs(a-b)<.002


def live_collision(actor, name, expected_names):
    assert actor and isinstance(actor,u.Actor),('Missing spawned actor',name)
    primitives=list(actor.get_components_by_class(u.PrimitiveComponent))
    names={p.get_name() for p in primitives}
    assert primitives and expected_names<=names,(name,sorted(expected_names),sorted(names))
    result={'actor_collision_flag':actor.get_actor_enable_collision(),'primitives':{}}
    if name=='ArrivalPortal':
        assert not result['actor_collision_flag'],name
    for p in sorted(primitives,key=lambda item:item.get_name()):
        row={'collision':str(p.get_collision_enabled()),'overlaps':p.get_editor_property('generate_overlap_events'),
             'query':p.is_query_collision_enabled(),'physics':p.is_physics_collision_enabled(),
             'simulating':p.is_simulating_physics()}
        assert p.get_collision_enabled()==u.CollisionEnabled.NO_COLLISION and not any(
            row[k] for k in ('overlaps','query','physics','simulating')),(name,p.get_name(),row)
        result['primitives'][p.get_name()]=row
    return result


def verify_component_locators(h,world,seq,pawn):
    """Resolve saved-style component references against actual sequence spawnables."""
    seq_player,holder=u.LevelSequencePlayer.create_level_sequence_player(
        world,seq,u.MovieSceneSequencePlaybackSettings())
    resolved={}
    try:
        holder.set_binding_by_tag(h.PAWN_TAG,[pawn],False)
        seq_player.play()
        seq_player.pause()
        pos=u.MovieSceneSequencePlaybackParams()
        pos.set_editor_property('frame',u.FrameTime(u.FrameNumber(1),0.))
        pos.set_editor_property('position_type',u.MovieScenePositionType.FRAME)
        pos.set_editor_property('update_method',u.UpdatePositionMethod.SCRUB)
        seq_player.set_playback_position(pos)
        parts=bindings(seq)
        def live(name):
            return h.one(seq_player.get_bound_objects(seq.get_binding_id(parts[name])))
        portal_children=[*PLANES,'BlueLight']
        if 'Stone' in parts:
            portal_children.append('Stone')
        if STYLE_COMPONENT in parts:
            portal_children.append(STYLE_COMPONENT)
        meshes={'Stone','Runes',*PLANES}
        if STYLE_COMPONENT in parts:
            meshes.add(STYLE_COMPONENT)
        cat=live('CosmeticCat')
        assert isinstance(cat,u.SkeletalMeshActor) and cat.get_editor_property('skeletal_mesh_component')
        collision={'CosmeticCat':live_collision(cat,'CosmeticCat',{cat.get_editor_property('skeletal_mesh_component').get_name()}),
                   'ArrivalPortal':live_collision(live('ArrivalPortal'),'ArrivalPortal',meshes)}
        for child,parent in [*((n,'ArrivalPortal') for n in portal_children),
                             ('PuzzleLens','Puzzle'),('FaceReturnLens','FaceReturn')]:
            actor=live(parent)
            actual=live(child)
            expected=actor.get_component_by_class(u.CameraComponent) if child.endswith('Lens') else actor.get_editor_property(child)
            assert actual==expected and actual.get_owner()==actor,(child,actual,expected,actor)
            resolved[child]=[parent,actual.get_name(),actual.get_class().get_name()]
            if child=='Stone':
                assert actual.get_editor_property('hidden_in_game') or not actual.is_visible(),actual
            if child==STYLE_COMPONENT:
                assert isinstance(actual,u.StaticMeshComponent)
                assert actual.get_path_name()==actor.get_path_name()+'.'+STYLE_COMPONENT,actual.get_path_name()
                mesh=actual.get_editor_property('static_mesh')
                assert mesh and mesh.get_path_name()==STYLE_MESH,mesh
                resolved[child].append(mesh.get_path_name())
        return resolved,collision
    finally:
        seq_player.stop()
        h.ACTORS.destroy_actor(holder)


def check(h,seq,director,portal,world,cam,cat_pov=True):
    bs=bindings(seq)
    expected={*PERSISTENT,*PLANES,'BlueLight','PuzzleLens','FaceReturnLens',*(n for n,_,_ in CUTS)}
    if STYLE_COMPONENT in h.components(portal):
        expected.add(STYLE_COMPONENT)
        assert STYLE_COMPONENT in bs and guid(bs[STYLE_COMPONENT].get_parent())==guid(bs['ArrivalPortal'])
    assert set(bs)==expected,(sorted(bs),sorted(expected))
    assert seq.get_playback_start()==0 and seq.get_playback_end()==END
    assert (seq.get_display_rate().numerator, seq.get_display_rate().denominator)==(30,1)
    assert (seq.get_tick_resolution().numerator,seq.get_tick_resolution().denominator)==(24000,1)
    assert h.PAWN_TAG in map(str,bs[PERSISTENT[0]].get_binding_tags())
    assert bs['ArrivalPortal'].get_object_template().get_class()==portal.generated_class()
    for n in ('CosmeticCat','ArrivalPortal'):
        assert not bs[n].get_object_template().get_actor_enable_collision(),n
    actors=h.actors_in(world)
    d=h.one(h.tagged(actors,h.DIRECTOR_TAG))
    holder=h.one(h.tagged(actors,h.SEQUENCE_TAG))
    assert d.get_editor_property('CinematicActor')==holder and d.get_editor_property('ExpectedGameplayView')==cam
    assert holder.get_editor_property('level_sequence_asset')==seq
    assert not holder.playback_settings.auto_play and holder.playback_settings.pause_at_end
    graph=audit_graph(director)
    graph['timing']=arrival_timing(director)
    assert all(close(v,w) for v,w in zip(graph['timing'],[14.8,18.8]))
    master,=seq.get_tracks()
    ordered=sorted(master.get_sections(),key=lambda s:s.get_start_frame())
    paths=shot_paths(cat_pov)
    for part,(name,first,last) in zip(ordered,CUTS,strict=True):
        assert (part.get_start_frame(),part.get_end_frame())==(first,last)
        assert part.get_camera_binding_id()==seq.get_binding_id(bs[name]) or (
            part.get_camera_binding_id().export_text()==seq.get_binding_id(bs[name]).export_text())
        assert part.get_completion_mode()==u.MovieSceneCompletionMode.KEEP_STATE
        path=paths[name]
        lens=bs[name].get_object_template().get_editor_property('CameraComponent')
        perspective=cat_pov and name=='Puzzle'
        projection=u.CameraProjectionMode.PERSPECTIVE if perspective else u.CameraProjectionMode.ORTHOGRAPHIC
        assert lens.projection_mode==projection and close(lens.field_of_view if perspective else lens.ortho_width,path[0][2]),name
        channels=section(bs[name],u.MovieScene3DTransformTrack).get_channels_by_type(u.MovieSceneScriptingDoubleChannel)
        for i,ch in enumerate(channels):
            assert all(frameof(k)==f and close(k.get_value(),vals[i]) for k,(f,vals,_) in zip(ch.get_keys(),path,strict=True)),(name,i)
        if name+'Lens' in bs:
            child=bs[name+'Lens']
            assert guid(child.get_parent())==guid(bs[name])
            track,=child.find_tracks_by_type(u.MovieSceneFloatTrack)
            assert str(track.get_property_path())==('FieldOfView' if perspective else 'OrthoWidth'),name
            ch,=section(child,u.MovieSceneFloatTrack).get_channels_by_type(u.MovieSceneScriptingFloatChannel)
            assert all(frameof(k)==f and close(k.get_value(),v) for k,(f,_,v) in zip(ch.get_keys(),path,strict=True))
    for name in (*PLANES,'BlueLight'):
        assert guid(bs[name].get_parent())==guid(bs['ArrivalPortal'])
    for name,xy in PLANES.items():
        channels=section(bs[name],u.MovieScene3DTransformTrack).get_channels_by_type(u.MovieSceneScriptingDoubleChannel)
        for ch,scale in zip(channels[6:8],xy):
            assert all(frameof(k)==f and close(k.get_value(),scale*s) for k,(f,s) in zip(ch.get_keys(),[(0,1.),(62,1.),(72,.8),(86,.02)],strict=True))
        hidden,=section(bs[name],u.MovieSceneVisibilityTrack).get_channels_by_type(u.MovieSceneScriptingBoolChannel)
        assert [(frameof(k),k.get_value()) for k in hidden.get_keys()]==[(0,True),(87,False)]
    energy,=section(bs['BlueLight'],u.MovieSceneFloatTrack).get_channels_by_type(u.MovieSceneScriptingFloatChannel)
    assert [(frameof(k),k.get_value()) for k in energy.get_keys()]==[(0,650.),(62,650.),(72,520.),(87,0.)]
    pt=section(bs['ArrivalPortal'],u.MovieScene3DTransformTrack).get_channels_by_type(u.MovieSceneScriptingDoubleChannel)
    assert [ch.get_default() for ch in pt[:3]]==[1375.,3983.,0.]
    spawning,=section(bs['ArrivalPortal'],u.MovieSceneSpawnTrack).get_channels_by_type(u.MovieSceneScriptingBoolChannel)
    assert [(frameof(k),k.get_value()) for k in spawning.get_keys()]==[(0,True),(91,False)]
    cat=bs['CosmeticCat']
    visible,=section(cat,u.MovieSceneVisibilityTrack).get_channels_by_type(u.MovieSceneScriptingBoolChannel)
    assert [(frameof(k),k.get_value()) for k in visible.get_keys()]==[(0,False),(23,True)]
    anim,=cat.find_tracks_by_type(u.MovieSceneSkeletalAnimationTrack)
    spans={p.get_editor_property('params').animation.get_name().removeprefix('AN_BlackCat_'):(p.get_start_frame(),p.get_end_frame()) for p in anim.get_sections()}
    assert spans==ANIM_SPANS
    return {'bindings':signature(seq),'cuts':[(n,f,t) for n,f,t in CUTS],'director':graph}


def migrate_puzzle_pov(seq):
    bs=bindings(seq)
    camera=bs['Puzzle'].get_object_template().get_editor_property('CameraComponent')
    assert camera.projection_mode==u.CameraProjectionMode.ORTHOGRAPHIC
    track,=bs['PuzzleLens'].find_tracks_by_type(u.MovieSceneFloatTrack)
    assert str(track.get_property_path())=='OrthoWidth'
    seq.modify()
    camera.modify()
    camera.set_editor_property('projection_mode',u.CameraProjectionMode.PERSPECTIVE)
    camera.set_editor_property('field_of_view',POV_GAZE[0][3])
    rows=shot_paths()['Puzzle']
    set_transforms(bs['Puzzle'],[(f,transform) for f,transform,_ in rows])
    track.modify()
    track.set_property_name_and_path('FieldOfView','FieldOfView')
    ch,=section(bs['PuzzleLens'],u.MovieSceneFloatTrack).get_channels_by_type(u.MovieSceneScriptingFloatChannel)
    set_curve(ch,[(f,fov) for f,_,fov in rows])


def run(h,mode):
    out=h.ROOT/'Saved/PresentationFix20261119/Stage2ArrivalAuthor'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    out.mkdir(parents=True)
    report={'mode':mode,'pid':os.getpid(),'completed':False,'saved':[]}
    def persist():
        (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    def hashes():
        return {p.relative_to(h.ROOT).as_posix():h.digest(p) for p in sorted((h.ROOT/'Content').rglob('*')) if p.is_file()}
    allowed={h.file_for(p).relative_to(h.ROOT).as_posix() for p in (h.SEQUENCE,h.DIRECTOR)}
    try:
        assert not h.ED.get_game_world() and not h.dirty()
        assert all(u.SystemLibrary.get_console_variable_int_value(name)==0 for name in h.CVARS)
        report['before']=hashes()
        persist()
        if mode=='migrate':
            report['backups']={}
            for key in sorted(allowed):
                destination=out/'Before'/key
                destination.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(h.ROOT/key,destination)
                assert h.digest(destination)==report['before'][key],key
                report['backups'][key]=str(destination)
            persist()
        assert h.LEVEL.load_level(h.MAP)
        world=h.ED.get_editor_world()
        pawn,cam,lens=h.pawn_and_camera(h.actors_in(world))
        seq,director,portal=[h.asset(p) for p in (h.SEQUENCE,h.DIRECTOR,h.PORTAL)]
        old=bindings(seq)
        report['preserved_guids']={n:old[n].get_id().export_text() for n in PERSISTENT}
        needs_seq=seq.get_playback_end()!=END
        needs_bp=close(arrival_timing(director)[0],10.)
        if mode=='migrate':
            if needs_seq:
                assert h.digest(h.file_for(h.SEQUENCE))==ORIGINAL_LS,'Unexpected existing sequence bytes'
                migrate_seq(h,seq,portal,lens)
            if needs_bp:
                assert h.digest(h.file_for(h.DIRECTOR))==ORIGINAL_BP,'Unexpected existing director bytes'
                arrival_timing(director,True)
            puzzle=bindings(seq)['Puzzle'].get_object_template().get_editor_property('CameraComponent')
            if puzzle.projection_mode==u.CameraProjectionMode.ORTHOGRAPHIC:
                before=check(h,seq,director,portal,world,cam,cat_pov=False)['bindings']
                migrate_puzzle_pov(seq)
                after=signature(seq)
                report['pov_changed_bindings']=[k for k in before if before[k]!=after[k]]
                assert set(before)==set(after) and set(report['pov_changed_bindings'])=={'Puzzle','PuzzleLens'}
                assert all(before[k]['guid']==after[k]['guid'] and before[k]['parent']==after[k]['parent'] for k in before)
                needs_seq=True
        report['structure']=check(h,seq,director,portal,world,cam)
        report['structure']['resolved_components'],report['actual_collision']=verify_component_locators(h,world,seq,pawn)
        assert report['preserved_guids']=={n:bindings(seq)[n].get_id().export_text() for n in PERSISTENT}
        if mode=='cold':
            with Path(h.arg('catrunStage2ArrivalBaseline')).open(encoding='utf8') as stream:
                base=json.load(stream)
            assert base['completed'] and base['pid']!=os.getpid() and report['before']==base['after']
            assert json.loads(json.dumps(report['structure']))==base['structure']
            if 'actual_collision' in base:
                assert report['actual_collision']==base['actual_collision']
        if mode=='migrate':
            assert h.dirty()<={h.SEQUENCE,h.DIRECTOR},h.dirty()
            for required,pkg,obj in ((needs_seq,h.SEQUENCE,seq),(needs_bp,h.DIRECTOR,director)):
                if required:
                    assert h.AS.save_loaded_asset(obj,False),pkg
                    report['saved'].append(pkg)
                    persist()
        assert not h.dirty(),h.dirty()
        report['completed']=True
    except Exception:
        report['error']=traceback.format_exc()
        raise
    finally:
        report['after']=hashes()
        before=report.get('before',{})
        report['changed']=sorted(k for k in before.keys()|report['after'].keys() if before.get(k)!=report['after'].get(k))
        report['unexpected']=sorted(set(report['changed'])-(allowed if mode=='migrate' else set()))
        report['completed']=report['completed'] and not report['unexpected']
        persist()
        print('STAGE2_ARRIVAL_MIGRATION',report['completed'],str(out/'report.json'))
        assert not report['unexpected'],report['unexpected']
