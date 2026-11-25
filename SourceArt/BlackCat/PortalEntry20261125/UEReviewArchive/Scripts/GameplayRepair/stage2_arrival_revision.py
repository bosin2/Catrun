"""November Stage2 arrival revision, authored into the five existing camera bindings."""
import datetime
import json
import math
import os
from pathlib import Path
import shutil
import traceback

import unreal as u

END = 378
PORTAL_END = 91
REVEAL = 10
PORTAL_LOCATION = (1375., 3980.75, 0.)
EYE = (1374.7266, 3680.1402, 33.6515)
TARGETS = {'statue': (1575.,3600.,73.), 'plate': (1195.,3430.,5.6), 'gate': (1375.,3210.,103.)}
LABELS = {'statue':'S2_Prop_Statue_C', 'plate':'S2_Prop_Plate_C_Plate', 'gate':'S2_Gate_11_Bars'}
SEQUENCE_SHA = '8ff687392bd8d519d6858f82a270020fe6e6efc3a83c75170d6652796a9b57c3'
DIRECTOR_SHA = '6e7a82caf6e6c22b5b0257a5372db8f4993823ffdd5115fea195589e8ceaf773'
LOCKED_BLEND_DIRECTOR_SHA = 'acbb6aa0289ba37b1272b8d0b1c0bc1553c419fe4f88b86a6d567289f5670c3b'
UNLIT_REVISION_SHA = '4d41c38d86d32f3d8814eea2f7b50aad9760891c2569c5f20704a5af7dba6b97'
FIRST_LIGHTING_SHA = 'a7698fd8f0067c22bbf6de93ef47471cadd75b5591e6f296b4906e0992187029'
FIRST_LIGHTING_PEAKS = {'ArrivalCatKey':3600., 'ArrivalStatueKey':5600., 'ArrivalGateAndPlateKey':6800.}
# Positions, linear RGB, radius (cm), and peak lumens of three camera-side practical fills.
FILLS = {
    'ArrivalCatKey': ([(0,(1292.,3825.,148.)),(14,(1292.,3825.,148.)),(53,(1292.,3632.,120.)),
                       (78,(1292.,3632.,120.)),(128,(1292.,3586.,117.))], (.68,.80,1.), 375., 340.),
    'ArrivalStatueKey': ([(0,(1450.,3680.,159.))], (1.,.72,.49), 355., 425.),
    'ArrivalGateAndPlateKey': ([(0,(1290.,3365.,148.))], (.67,.78,1.), 440., 500.),
}
FILL_FADE_START = 286
FILL_FADE_END = 336
CUTS = (('Entrance',0,71), ('RearWalk',71,110), ('Face',110,140), ('Puzzle',140,246), ('FaceReturn',246,END))
CUT_RANGES={name:(first,last) for name,first,last in CUTS}
# Inclusive endpoint pairs, with pitch, yaw and horizontal FOV for each held cat-eye view.
GAZE_HOLDS=(('statue',140,158,9.,-36.,70.),('plate',196,216,-5.2,-125.7,66.),('gate',234,245,7.,-92.,58.))
HANDOFF_FRAME=336
REACTION_HOLD_END=266
SHOTS = (('emergence',0,71),('shoulder',71,110),('face',110,140),('statue',140,164),
         ('plate',164,211),('gate',211,246),('reaction and pullback',246,336),('gameplay hold',336,END))
SPANS = {'JumpDown':(5,44), 'Landing':(44,80), 'Walk':(76,128), 'Idle':(124,END)}
PERSPECTIVE = {'Entrance', 'RearWalk', 'Face', 'Puzzle'}


def aim(frame, eye, subject, framing):
    x,y,z = [b-a for a,b in zip(eye,subject)]
    return frame, [*eye, 0., math.degrees(math.atan2(z,math.hypot(x,y))),
                   math.degrees(math.atan2(y,x)), 1.,1.,1.], framing


def gameplay_view(lens):
    assert lens.projection_mode==u.CameraProjectionMode.ORTHOGRAPHIC
    settings_class=u.load_class(None,'/Script/Catrun.CatrunLevelFlowSettings')
    assert settings_class, 'Unable to resolve the native Level Flow settings class'
    settings=u.get_default_object(settings_class)
    profiles=settings.get_editor_property('CameraProfiles')
    profile=next((p for p in profiles if str(p.stage_id)=='Stage2' and math.isfinite(p.distance_scale)),None)
    scale=min(3.,max(1.,profile.distance_scale)) if profile else 1.
    view=lens.get_camera_view(0.)
    return {'xyz':[view.location.x,view.location.y,view.location.z],
            'pyr':[view.rotation.pitch,view.rotation.yaw,view.rotation.roll],
            'width':view.ortho_width*scale,'authored_width':view.ortho_width,'profile_scale':scale,
            'fov':view.fov,'aspect':view.aspect_ratio}


def paths(gameplay):
    # Aim at the full pressure plate, including its 150 cm frame. The previous
    # off-centre bearing cropped its left edge in the actual gameplay viewport.
    def look(frame,pitch,yaw,fov):
        return frame,[*EYE,0.,pitch,yaw,1.,1.,1.],fov
    gaze=[look(f,pitch,yaw,fov) for _,first,last,pitch,yaw,fov in GAZE_HOLDS for f in (first,last)]
    # Start in front of the cat, clear of the statue. The former camera at
    # (1517, 3669, 84) put the statue across the near plane during this reaction.
    subject=(1375.,3690.,28.)
    first=CUT_RANGES['FaceReturn'][0]
    front=aim(first,(1410.,3575.,56.),subject,160.)
    pitch1,yaw1,roll1=gameplay['pyr']
    pitch0,yaw0=front[1][4:6]
    yaw1=yaw0+(yaw1-yaw0+180.)%360.-180.
    start_radius=math.dist(subject[:2],front[1][:2])
    radius1=math.hypot(gameplay['xyz'][0]-1375.,gameplay['xyz'][1]-3700.)
    end_aim=[gameplay['xyz'][0]+radius1*math.cos(math.radians(yaw1)),
             gameplay['xyz'][1]+radius1*math.sin(math.radians(yaw1)),
             gameplay['xyz'][2]+radius1*math.tan(math.radians(pitch1))]
    # Let the established head reaction read before the camera pulls away.
    returning=[front,(REACTION_HOLD_END,list(front[1]),front[2])]
    for frame in (*range(REACTION_HOLD_END+4,HANDOFF_FRAME,5),HANDOFF_FRAME):
        t=(frame-REACTION_HOLD_END)/(HANDOFF_FRAME-REACTION_HOLD_END)
        s=t*t*(3.-2.*t)
        # Gain an overhead view before orbiting past the 150 cm statue. Raising
        # pitch at the same slow rate as yaw swept its wings across the cat.
        lift_t=min(t/.5,1.)
        lift=lift_t*lift_t*(3.-2.*lift_t)
        yaw,pitch=yaw0+(yaw1-yaw0)*s,pitch0+(pitch1-pitch0)*lift
        radius=start_radius+(radius1-start_radius)*s
        cx,cy,cz=[a+(b-a)*s for a,b in zip(subject,end_aim)]
        eye=[cx-radius*math.cos(math.radians(yaw)),cy-radius*math.sin(math.radians(yaw)),
             cz-radius*math.tan(math.radians(pitch))]
        returning.append((frame,[*eye,s*roll1,pitch,yaw,1.,1.,1.],front[2]*(gameplay['width']/front[2])**s))
    return {
        'Entrance':[aim(0,(1430.,3554.,91.),(1375.,3939.,100.),52.),
                    aim(10,(1430.,3554.,91.),(1375.,3939.,100.),52.),
                    aim(28,(1417.,3550.,75.),(1375.,3848.,61.),52.),
                    aim(49,(1401.,3558.,62.),(1375.,3755.,36.),52.),
                    aim(70,(1393.,3570.,54.),(1375.,3736.,30.),52.)],
        'RearWalk':[aim(71,(1413.,3858.,62.),(1367.,3590.,36.),70.),
                    aim(109,(1413.,3831.,62.),(1367.,3563.,36.),70.)],
        'Face':[aim(110,(1392.,3598.,42.),(1375.,3701.,28.),64.),
                aim(128,(1392.,3587.,42.),(1375.,3689.,28.),64.),
                aim(139,(1392.,3587.,42.),(1375.,3689.,28.),64.)],
        'Puzzle':gaze, 'FaceReturn':returning}


def cat_rows():
    # Original mesh placement/rotation/scale and measured land-to-idle sole correction.
    return [(f,[1375.,y,2.2+z,0.,0.,-180.,2.,2.,2.]) for f,y,z in (
        (0,4000.,33.),(5,3996.,33.),(10,3978.,37.),(19,3922.,63.),
        (33,3795.,31.),(44,3746.,-.8207),(54,3746.,0.),(78,3746.,0.),
        (84,3743.,0.),(120,3704.,0.),(128,3700.,0.),(END-1,3700.,0.))]


def add_gentle_reaction(h,cat,animation):
    """Use a planted portion of the existing inspection clip if the head actually turns."""
    mesh=cat.get_object_template().skeletal_mesh_component.get_skeletal_mesh_asset()
    clip=h.asset('/Game/Characters/BlackCat/Final/Animations/Cinematics/AN_BlackCat_PortalInspect')
    assert clip.get_editor_property('skeleton')==mesh.get_editor_property('skeleton')
    if clip.get_editor_property('enable_root_motion'):
        return
    options=u.AnimPoseEvaluationOptions()
    options.set_editor_property('optional_skeletal_mesh',mesh)
    options.set_editor_property('evaluation_type',u.AnimDataEvalType.SOURCE)
    options.set_editor_property('should_retarget',False)
    def pose(f):
        sample=u.AnimPoseExtensions.get_anim_pose_at_time(clip,f/30.,options)
        def bone(n):
            return u.AnimPoseExtensions.get_bone_pose(sample,n,u.AnimPoseSpaces.WORLD)
        q=bone('head').rotation
        return (q.x,q.y,q.z,q.w),[h.vector(bone(n).translation) for n in h.PAWS]
    # At 2x installed mesh scale, cap paw travel at 3 cm and head turn at 16 degrees.
    count=int(clip.get_editor_property('sequence_length')*30)
    samples=[pose(f) for f in range(count)]
    windows=[]
    for f in range(count-34):
        turn=0.
        feet=0.
        for q,paws in samples[f:f+34]:
            dot=min(1.,abs(sum(a*b for a,b in zip(samples[f][0],q))))
            turn=max(turn,math.degrees(2.*math.acos(dot)))
            feet=max(feet,max(math.dist(a,b)*2. for a,b in zip(samples[f][1],paws)))
        if 2.<=turn<=16. and feet<=3.:
            windows.append((abs(turn-7.)+feet,f))
    if not windows:
        return
    _,offset=min(windows)
    idle=h.one(s for s in animation.get_sections() if s.get_start_frame()==SPANS['Idle'][0])
    idle_params=idle.get_editor_property('params')
    idle.set_range(SPANS['Idle'][0],264)
    after=h.section_range(animation.add_section(),286,END)
    after.set_editor_property('params',idle_params)
    reaction=h.section_range(animation.add_section(),258,292)
    params=u.MovieSceneSkeletalAnimationParams()
    params.set_editor_property('animation',clip)
    params.set_editor_property('first_loop_start_frame_offset',u.FrameNumber(offset*800))
    params.set_editor_property('force_custom_mode',True)
    params.set_editor_property('skip_anim_notifiers',True)
    reaction.set_editor_property('params',params)
    ease=u.MovieSceneSectionEasingExtensions
    for sec in (reaction,after): ease.set_ease_in_duration(sec,6*800)
    for sec in (idle,reaction): ease.set_ease_out_duration(sec,6*800)


def place_sequence(h,seq,portal,gameplay):
    import stage2_arrival_shots as old
    bs=old.bindings(seq)
    assert seq.get_playback_end()==504 and 'Stone' not in bs
    seq.modify()
    seq.set_playback_end(END)
    for binding in bs.values():
        for track in binding.get_tracks():
            for sec in track.get_sections():
                if sec.get_end_frame()==504:
                    sec.set_range(sec.get_start_frame(),END)
    cat=bs['CosmeticCat']
    old.set_transforms(cat,cat_rows(),END)
    visible,=old.section(cat,u.MovieSceneVisibilityTrack).get_channels_by_type(u.MovieSceneScriptingBoolChannel)
    k,= [k for k in visible.get_keys() if k.get_value()]
    k.set_time(u.FrameNumber(REVEAL))
    anim,=cat.find_tracks_by_type(u.MovieSceneSkeletalAnimationTrack)
    for sec in anim.get_sections():
        clip=sec.get_editor_property('params').animation.get_name().removeprefix('AN_BlackCat_')
        sec.set_range(*SPANS[clip])
    add_gentle_reaction(h,cat,anim)

    pb=bs['ArrivalPortal']
    old.set_transforms(pb,[(0,[*PORTAL_LOCATION,0.,0.,0.,1.25,1.25,1.25])],PORTAL_END)
    temp=h.ACTORS.spawn_actor_from_class(portal.generated_class(),u.Vector(),u.Rotator(),transient=True)
    try:
        child=old.component_binding(seq,pb,temp.get_editor_property('Stone'),'Stone')
        tr=child.add_track(u.MovieSceneVisibilityTrack)
        tr.set_property_name_and_path('bHiddenInGame','bHiddenInGame')
        v,=h.section_range(tr.add_section(),0,PORTAL_END).get_channels_by_type(u.MovieSceneScriptingBoolChannel)
        v.set_default(False)
        v.add_key(u.FrameNumber(0),False)
    finally:
        h.ACTORS.destroy_actor(temp)
    apply_cameras(seq,gameplay)


def apply_cameras(seq,gameplay):
    import stage2_arrival_shots as old
    seq.modify()
    bs=old.bindings(seq)
    master,=seq.get_tracks()
    cuts=sorted(master.get_sections(),key=lambda part:part.get_start_frame())
    shots=paths(gameplay)
    for part,(n,first,last) in zip(cuts,CUTS,strict=True):
        assert part.get_camera_binding_id().export_text()==seq.get_binding_id(bs[n]).export_text()
        part.modify()
        part.set_range(first,last)
        cam=bs[n].get_object_template().get_editor_property('CameraComponent')
        cam.modify()
        perspective=n in PERSPECTIVE
        cam.set_editor_property('projection_mode',u.CameraProjectionMode.PERSPECTIVE if perspective else u.CameraProjectionMode.ORTHOGRAPHIC)
        cam.set_editor_property('field_of_view' if perspective else 'ortho_width',shots[n][0][2])
        if n=='FaceReturn':
            cam.set_editor_property('field_of_view',gameplay['fov'])
            cam.set_editor_property('aspect_ratio',gameplay['aspect'])
        old.set_transforms(bs[n],[(f,row) for f,row,_ in shots[n]],END)
        if n+'Lens' in bs:
            sec=old.section(bs[n+'Lens'],u.MovieSceneFloatTrack)
            sec.set_range(0,END)
            ch,=sec.get_channels_by_type(u.MovieSceneScriptingFloatChannel)
            old.set_curve(ch,[(f,lens) for f,_,lens in shots[n]])


def layout(h,world):
    actors={a.get_actor_label():a for a in h.actors_in(world)}
    frame,back=[actors['S2_Layout_EntrancePortal'+n] for n in ('Frame','Backing')]
    assert math.dist(h.vector(frame.get_actor_location()),PORTAL_LOCATION)<.02
    assert math.dist(h.vector(frame.get_actor_scale3d()),(.9375,)*3)<.002
    assert back.get_actor_enable_collision()
    for k,label in LABELS.items():
        actor=actors[label]
        assert math.dist(h.vector(actor.get_actor_location())[:2],TARGETS[k][:2])<.02
    gate=actors[LABELS['gate']]
    assert abs(gate.get_actor_location().z+20.)<.05 and gate.get_actor_enable_collision()
    return {k:h.vector(actors[label].get_actor_location()) for k,label in LABELS.items()}


def light_sequence(h,seq):
    import stage2_arrival_shots as old
    seq.modify()
    for name,(positions,color,radius,lumens) in FILLS.items():
        binding = h.spawnable(seq.add_spawnable_from_class(u.PointLight.static_class()),name)
        spawn = old.section(binding,u.MovieSceneSpawnTrack)
        spawn.set_range(0,END)
        template = binding.get_object_template()
        template.set_actor_enable_collision(False)
        component = template.get_editor_property('PointLightComponent')
        component.set_editor_property('mobility',u.ComponentMobility.MOVABLE)
        component.set_editor_property('intensity_units',u.LightUnits.LUMENS)
        component.set_editor_property('use_inverse_squared_falloff',True)
        component.set_light_color(u.LinearColor(*color,1.))
        component.set_attenuation_radius(radius)
        component.set_intensity(lumens)
        component.set_editor_property('cast_shadows',True)
        component.set_editor_property('source_radius',24.)
        component.set_editor_property('soft_source_radius',32.)
        component.set_editor_property('indirect_lighting_intensity',0.)
        component.set_editor_property('volumetric_scattering_intensity',0.)
        old.set_transforms(binding,[(frame,[*xyz,0.,0.,0.,1.,1.,1.]) for frame,xyz in positions],END)
        actor = h.ACTORS.spawn_actor_from_class(u.PointLight,u.Vector(),u.Rotator(),transient=True)
        try:
            bulb=old.component_binding(seq,binding,actor.get_editor_property('PointLightComponent'),name+'Bulb')
            old.float_track(bulb,'Intensity',fill_keys(name),END)
        finally:
            h.ACTORS.destroy_actor(actor)


def retune_lights(seq):
    import stage2_arrival_shots as old
    bindings=old.bindings(seq)
    seq.modify()
    for name,(_,_,_,peak) in FILLS.items():
        component=bindings[name].get_object_template().get_editor_property('PointLightComponent')
        component.modify()
        component.set_intensity(peak)
        section=old.section(bindings[name+'Bulb'],u.MovieSceneFloatTrack)
        section.modify()
        channel,=section.get_channels_by_type(u.MovieSceneScriptingFloatChannel)
        old.set_curve(channel,fill_keys(name))


def fill_keys(name):
    peak=FILLS[name][3]
    if name=='ArrivalStatueKey':
        return [(0,65.),(110,65.),(142,peak),(171,peak),(202,85.),(286,85.),(336,0.),(END-1,0.)]
    if name=='ArrivalGateAndPlateKey':
        return [(0,65.),(161,65.),(198,peak),(244,peak),(270,110.),(286,110.),(336,0.),(END-1,0.)]
    return [(0,peak),(FILL_FADE_START,peak),(FILL_FADE_END,0.),(END-1,0.)]


def audit_lights(seq,peaks=None):
    import stage2_arrival_shots as old
    bs=old.bindings(seq)
    settings={}
    for name,(positions,color,radius,lumens) in FILLS.items():
        if peaks is not None:
            lumens=peaks[name]
        bulb=bs[name+'Bulb']
        assert old.guid(bulb.get_parent())==old.guid(bs[name])
        template=bs[name].get_object_template()
        assert isinstance(template,u.PointLight) and not template.get_actor_enable_collision()
        component=template.get_editor_property('PointLightComponent')
        assert component.get_editor_property('mobility')==u.ComponentMobility.MOVABLE
        assert component.get_editor_property('intensity_units')==u.LightUnits.LUMENS
        assert abs(component.get_editor_property('attenuation_radius')-radius)<.01
        assert abs(component.get_editor_property('intensity')-lumens)<.01
        tinted=component.get_light_color()
        assert max(abs(x-y) for x,y in zip((tinted.r,tinted.g,tinted.b),color))<.01
        track,=bulb.find_tracks_by_type(u.MovieSceneFloatTrack)
        assert str(track.get_property_path())=='Intensity'
        channel,=old.section(bulb,u.MovieSceneFloatTrack).get_channels_by_type(u.MovieSceneScriptingFloatChannel)
        expected=fill_keys(name) if peaks is None else [(0,lumens),(FILL_FADE_START,lumens),(FILL_FADE_END,0.),(END-1,0.)]
        assert abs(channel.get_default()-expected[0][1])<.01
        keys=[(old.frameof(k),k.get_value()) for k in channel.get_keys()]
        assert keys==expected
        spawn=old.section(bs[name],u.MovieSceneSpawnTrack)
        assert (spawn.get_start_frame(),spawn.get_end_frame())==(0,END)
        settings[name]={'lumens':lumens,'radius':radius,'linear_color':[tinted.r,tinted.g,tinted.b],'intensity_keys':keys}
    return settings


def audit_cameras(seq,gameplay):
    import stage2_arrival_shots as old
    bs=old.bindings(seq)
    def curve(channel,expected):
        assert all(old.frameof(k)==f and abs(k.get_value()-v)<.002 for k,(f,v) in zip(channel.get_keys(),expected,strict=True))
    tr,=seq.get_tracks()
    shot_paths=paths(gameplay)
    for sec,(name,first,last) in zip(sorted(tr.get_sections(),key=lambda s:s.get_start_frame()),CUTS,strict=True):
        assert (sec.get_start_frame(),sec.get_end_frame())==(first,last)
        assert sec.get_camera_binding_id().export_text()==seq.get_binding_id(bs[name]).export_text()
        shots=shot_paths[name]
        channels=old.section(bs[name],u.MovieScene3DTransformTrack).get_channels_by_type(u.MovieSceneScriptingDoubleChannel)
        for i,channel in enumerate(channels):
            curve(channel,[(f,row[i]) for f,row,_ in shots])
        lens=bs[name].get_object_template().get_editor_property('CameraComponent')
        perspective=name in PERSPECTIVE
        assert lens.projection_mode==(u.CameraProjectionMode.PERSPECTIVE if perspective else u.CameraProjectionMode.ORTHOGRAPHIC)
        assert abs((lens.field_of_view if perspective else lens.ortho_width)-shots[0][2])<.01
        if name=='FaceReturn':
            assert abs(lens.field_of_view-gameplay['fov'])<.01 and abs(lens.aspect_ratio-gameplay['aspect'])<.001
            assert math.dist(shots[-1][1][:3],gameplay['xyz'])<.02 and abs(shots[-1][2]-gameplay['width'])<.02
        if name+'Lens' in bs:
            tr,=bs[name+'Lens'].find_tracks_by_type(u.MovieSceneFloatTrack)
            assert str(tr.get_property_path())==('FieldOfView' if perspective else 'OrthoWidth')
            ch,=old.section(bs[name+'Lens'],u.MovieSceneFloatTrack).get_channels_by_type(u.MovieSceneScriptingFloatChannel)
            curve(ch,[(f,lens) for f,_,lens in shots])


def audit(h,seq,director,world,pawn,cam,gameplay):
    import stage2_arrival_shots as old
    from stage2_arrival_graph import revision_graph
    bs=old.bindings(seq)
    assert seq.get_playback_end()==END and seq.get_playback_start()==0
    assert (seq.get_display_rate().numerator,seq.get_display_rate().denominator)==(30,1)
    actors=h.actors_in(world)
    director_actor=h.one(h.tagged(actors,h.DIRECTOR_TAG))
    holder=h.one(h.tagged(actors,h.SEQUENCE_TAG))
    assert director_actor.get_editor_property('ExpectedGameplayView')==cam and director_actor.get_editor_property('CinematicActor')==holder
    assert holder.get_editor_property('level_sequence_asset')==seq and not holder.playback_settings.auto_play and holder.playback_settings.pause_at_end
    assert h.PAWN_TAG in map(str,bs['Gameplay Cat Visibility'].get_binding_tags())
    assert old.guid(bs['Stone'].get_parent())==old.guid(bs['ArrivalPortal'])
    def curve(channel,expected):
        assert all(old.frameof(k)==f and abs(k.get_value()-v)<.002 for k,(f,v) in zip(channel.get_keys(),expected,strict=True))
    def transform(binding,rows):
        sec=old.section(bs[binding],u.MovieScene3DTransformTrack)
        channels=sec.get_channels_by_type(u.MovieSceneScriptingDoubleChannel)
        for index,ch in enumerate(channels):
            curve(ch,[(f,row[index]) for f,row in rows])
    transform('CosmeticCat',cat_rows())
    transform('ArrivalPortal',[(0,[*PORTAL_LOCATION,0.,0.,0.,1.25,1.25,1.25])])
    for name,kind,keys in (('CosmeticCat',u.MovieSceneVisibilityTrack,[(0,False),(REVEAL,True)]),
                           ('ArrivalPortal',u.MovieSceneSpawnTrack,[(0,True),(PORTAL_END,False)]),
                           ('Stone',u.MovieSceneVisibilityTrack,[(0,False)])):
        ch,=old.section(bs[name],kind).get_channels_by_type(u.MovieSceneScriptingBoolChannel)
        curve(ch,keys)
    anim,=bs['CosmeticCat'].find_tracks_by_type(u.MovieSceneSkeletalAnimationTrack)
    sections=sorted((s.get_editor_property('params').animation.get_name().removeprefix('AN_BlackCat_'),
                     s.get_start_frame(),s.get_end_frame()) for s in anim.get_sections())
    expected=[(n,*span) for n,span in SPANS.items() if n!='Idle']
    reaction=any(n=='PortalInspect' for n,_,_ in sections)
    if reaction:
        expected.extend([('Idle',124,264),('PortalInspect',258,292),('Idle',286,END)])
    else:
        expected.append(('Idle',*SPANS['Idle']))
    assert sections==sorted(expected),sections
    audit_cameras(seq,gameplay)
    resolved,collision=old.verify_component_locators(h,world,seq,pawn)
    return {'structure':old.signature(seq),'director':revision_graph(director),'shots':SHOTS,
            'layout':layout(h,world),'locators':resolved,'spawnable_collision':collision,
            'reaction':'PortalInspect' if reaction else 'brief Idle response','actual_gameplay_target':gameplay}


def comparable_audit(audit):
    snapshot=json.loads(json.dumps(audit))
    tracks=snapshot['structure']['CosmeticCat']['tracks']
    animation,=(t for t in tracks if t['type']=='MovieSceneSkeletalAnimationTrack')
    # The editor may enumerate these sections differently after reloading the package.
    animation['sections'].sort(key=lambda s:(s['span'],s['clip'],json.dumps(s,sort_keys=True)))
    return snapshot


def run(h,mode):
    import stage2_arrival_shots as old
    from stage2_arrival_graph import revision_graph
    dest=h.ROOT/'Saved/StageRevision20261123/ArrivalAuthor'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    dest.mkdir(parents=True)
    report={'mode':mode,'pid':os.getpid(),'saved':[],'completed':False}
    paths_by_pkg={p:h.file_for(p) for p in (h.MAP,h.SEQUENCE,h.DIRECTOR,h.PORTAL)}
    def hashes():
        return {k:h.digest(p) for k,p in paths_by_pkg.items()}
    try:
        assert not h.ED.get_game_world() and not h.dirty(),h.dirty()
        assert all(u.SystemLibrary.get_console_variable_int_value(n)==0 for n in h.CVARS)
        report['before']=hashes()
        if h.ED.get_editor_world().get_path_name().split('.')[0]!=h.MAP:
            assert h.LEVEL.load_level(h.MAP)
        world=h.ED.get_editor_world()
        layout(h,world)
        pawn,cam,lens=h.pawn_and_camera(h.actors_in(world))
        gameplay=gameplay_view(lens)
        seq,director,portal=[h.asset(p) for p in (h.SEQUENCE,h.DIRECTOR,h.PORTAL)]
        guids={n:old.guid(b) for n,b in old.bindings(seq).items()}
        before_graph=report['before'][h.DIRECTOR]==DIRECTOR_SHA
        locked_blend=report['before'][h.DIRECTOR]==LOCKED_BLEND_DIRECTOR_SHA
        before_seq=seq.get_playback_end()!=END
        has_lighting=any(name in guids or name+'Bulb' in guids for name in FILLS)
        first_lighting=report['before'][h.SEQUENCE]==FIRST_LIGHTING_SHA
        installed_revision=report['before'][h.SEQUENCE]=='c5ed595207d4f7bd413b4c08eb568d5b4cbca14b665919fb6312225198e7ce30'
        update_cameras=not before_seq and (installed_revision or first_lighting or not has_lighting)
        if mode=='revise':
            for pkg in (h.SEQUENCE,h.DIRECTOR):
                target=dest/'Before'/paths_by_pkg[pkg].name
                target.parent.mkdir(exist_ok=True)
                shutil.copy2(paths_by_pkg[pkg],target)
                assert h.digest(target)==report['before'][pkg]
            if before_seq:
                assert report['before'][h.SEQUENCE]==SEQUENCE_SHA
                place_sequence(h,seq,portal,gameplay)
            elif update_cameras:
                apply_cameras(seq,gameplay)
            if not has_lighting:
                assert before_seq or report['before'][h.SEQUENCE]==UNLIT_REVISION_SHA, 'Unrecognized arrival sequence before lighting pass'
                light_sequence(h,seq)
            elif first_lighting or installed_revision:
                retune_lights(seq)
            revision_graph(director,apply=before_graph,unlock_blend=locked_blend)
        report['audit']=audit(h,seq,director,world,pawn,cam,gameplay)
        if mode=='revise' or has_lighting:
            report['audit']['cinematic_lights']=audit_lights(seq)
        assert all(old.guid(old.bindings(seq)[n])==gid for n,gid in guids.items())
        if mode=='revision_cold':
            baseline=json.loads(Path(h.arg('catrunStage2ArrivalBaseline')).read_text(encoding='utf8'))
            assert baseline['completed'] and baseline['pid']!=os.getpid()
            assert report['before']==baseline['after'] and comparable_audit(report['audit'])==comparable_audit(baseline['audit'])
        if mode=='revise':
            assert h.dirty()<={h.SEQUENCE,h.DIRECTOR},h.dirty()
            for needed,obj,pkg in ((before_seq or update_cameras,seq,h.SEQUENCE),(before_graph or locked_blend,director,h.DIRECTOR)):
                if needed:
                    assert h.AS.save_loaded_asset(obj,False)
                    report['saved'].append(pkg)
        assert not h.dirty(),h.dirty()
        report['completed']=True
    except Exception:
        report['error']=traceback.format_exc()
        raise
    finally:
        report['after']=hashes()
        assert all(report['before'][p]==v for p,v in report['after'].items() if p not in report['saved']) if 'before' in report else True
        (dest/'report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
        print('STAGE2_ARRIVAL_REVISION',report['completed'],str(dest/'report.json'))
