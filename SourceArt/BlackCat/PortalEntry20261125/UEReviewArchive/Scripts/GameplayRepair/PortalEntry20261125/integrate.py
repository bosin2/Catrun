"""Import the animation chat's delivered rig clips and edit only Stage1 departure.

Requires a reviewed local contract.json; never generates substitute animations.
Run in this worktree's isolated Python commandlet after receipt of the FBXs.
"""
from pathlib import Path
import datetime
import hashlib
import json
import math
import shutil
import sys

import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import stage1_departure_shots as old

h = old.h
h.CAMERAS = old.CAMERA_NAMES
AS = u.EditorAssetLibrary
OUT = ROOT / 'Saved/PortalEntry20261125'
SOURCE = ROOT / 'SourceArt/BlackCat/PortalEntry20261125'
FOLDER = '/Game/Cinematics/Stage1/Portal/PawProbe20261125'
SEQ = '/Game/Cinematics/Stage1/Portal/LS_Stage1_PortalExit'
SKELETON = '/Game/Characters/BlackCat/Final/Skeletons/SKEL_BlackCat_Final'
MESH = '/Game/Characters/BlackCat/Final/Meshes/SK_BlackCat_Final'
RESTORE = u.MovieSceneCompletionMode.RESTORE_STATE
OWN = 'CatrunPortalPawProbe20261125'
BONES = ('root', 'pelvis', 'chest', 'neck', 'head', 'ear_L', 'ear_R',
         'paw_F_L', 'paw_F_R', 'paw_H_L', 'paw_H_R', 'tail_01')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def package_file(package):
    return ROOT / 'Content' / (package.removeprefix('/Game/') + '.uasset')


def pose(clip, frame, compressed=False):
    options = u.AnimPoseEvaluationOptions()
    options.evaluation_type = u.AnimDataEvalType.COMPRESSED if compressed else u.AnimDataEvalType.SOURCE
    options.optional_skeletal_mesh = u.load_asset(MESH)
    options.should_retarget = compressed
    result = u.AnimPoseExtensions.get_anim_pose_at_time(clip, frame / 30., options)
    return {name: u.AnimPoseExtensions.get_bone_pose(result, name, u.AnimPoseSpaces.WORLD) for name in BONES}


def xyz(value):
    return [float(value.x), float(value.y), float(value.z)]


def seam(first, last_frame, second, first_frame, compressed=False):
    a, b = pose(first, last_frame, compressed), pose(second, first_frame, compressed)
    result = {}
    for bone in BONES:
        qa, qb = a[bone].rotation, b[bone].rotation
        dot = min(1., abs(qa.x*qb.x + qa.y*qb.y + qa.z*qb.z + qa.w*qb.w))
        result[bone] = {'distance_world_cm': 2. * (a[bone].translation-b[bone].translation).length(),
                        'angle_deg': math.degrees(2 * math.acos(dot))}
    return result


def import_clip(spec, skeleton):
    source = SOURCE / spec['file']
    assert source.is_file() and source.suffix.lower() == '.fbx', str(source)
    source_hash = digest(source)
    assert source_hash == spec['sha256'], (source.name, 'receipt hash changed')
    target = FOLDER + '/' + spec['asset']
    if AS.does_asset_exist(target):
        clip = u.load_asset(target)
        assert AS.get_metadata_tag(clip, 'PortalEntrySourceSHA256') == source_hash, 'Use a new asset name for a revised FBX'
        return clip
    task = u.AssetImportTask()
    task.filename = str(source)
    task.destination_path = FOLDER
    task.destination_name = spec['asset']
    task.automated, task.replace_existing, task.save = True, False, False
    options = u.FbxImportUI()
    options.set_editor_property('automated_import_should_detect_type', False)
    options.set_editor_property('mesh_type_to_import', u.FBXImportType.FBXIT_ANIMATION)
    options.set_editor_property('import_as_skeletal', True)
    options.set_editor_property('import_mesh', False)
    options.set_editor_property('import_animations', True)
    options.set_editor_property('import_materials', False)
    options.set_editor_property('import_textures', False)
    options.set_editor_property('skeleton', skeleton)
    data = options.get_editor_property('anim_sequence_import_data')
    for name, value in spec.get('import_settings', {}).items():
        data.set_editor_property(name, value)
    data.set_editor_property('use_default_sample_rate', True)
    data.set_editor_property('import_bone_tracks', True)
    task.options = options
    task.factory = u.FbxFactory()
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    imported = [u.load_asset(p) for p in task.imported_object_paths]
    assert len(imported) == 1 and isinstance(imported[0], u.AnimSequence), task.imported_object_paths
    clip = imported[0]
    assert clip.get_path_name().split('.')[0] == target, clip.get_path_name()
    assert clip.get_editor_property('skeleton') == skeleton
    clip.set_editor_property('enable_root_motion', False)
    AS.set_metadata_tag(clip, 'PortalEntrySourceSHA256', source_hash)
    AS.set_metadata_tag(clip, 'PortalEntryProductionChat', '01a2107b-42cf-7283-91ba-0c114fc29bba')
    return clip


def precise_compression():
    """Keep these small planted-paw translations; default key reduction loses them."""
    path = FOLDER + '/BCS_PortalPawPrecision'
    if AS.does_asset_exist(path):
        return u.load_asset(path)
    settings = u.AssetToolsHelpers.get_asset_tools().create_asset('BCS_PortalPawPrecision', FOLDER,
            u.AnimBoneCompressionSettings, u.AnimBoneCompressionSettingsFactory())
    codec = u.new_object(u.load_class(None, '/Script/Engine.AnimCompress_LeastDestructive'), outer=settings)
    settings.set_editor_property('codecs', [codec])
    settings.set_editor_property('error_threshold', .0001)
    settings.set_editor_property('force_below_threshold', True)
    return settings


def after(channel, frame, keys):
    """Keep original keys, interpolation and tangents through the accepted walk."""
    for key in list(channel.get_keys()):
        if key.get_time(time_unit=u.MovieSceneTimeUnit.TICK_RESOLUTION).frame_number.value > h.tick(frame):
            channel.remove_key(key)
    for at, value in keys:
        assert at >= frame
        channel.add_key(u.FrameNumber(h.tick(at)), value, 0., u.MovieSceneTimeUnit.TICK_RESOLUTION,
                        u.MovieSceneKeyInterpolation.LINEAR)


def axes(section, rows, end):
    section.set_range(0, end)
    section.set_completion_mode(RESTORE)
    for index, channel in enumerate(h.transform_channels(section)):
        h.write_keys(channel, [(f, values[index]) for f, values in rows], rows[0][1][index])


def animation(track, clip, first, last, rate=1., start=0., hold=0.):
    section = track.add_section()
    section.set_range(first, last)
    section.set_completion_mode(RESTORE)
    params = u.MovieSceneSkeletalAnimationParams()
    for name, value in (('animation', clip), ('play_rate', u.MovieSceneTimeWarpExtensions.make_time_warp(rate)),
                        ('start_frame_offset', u.FrameNumber(h.tick(start))),
                        ('first_loop_start_frame_offset', u.FrameNumber(h.tick(hold))),
                        ('force_custom_mode', True), ('skip_anim_notifiers', True)):
        params.set_editor_property(name, value)
    section.set_editor_property('params', params)
    return section


def ripple_material():
    target = FOLDER + '/M_PortalPawRipple'
    if AS.does_asset_exist(target):
        return u.load_asset(target)
    material = u.AssetToolsHelpers.get_asset_tools().create_asset('M_PortalPawRipple', FOLDER, u.Material, u.MaterialFactoryNew())
    material.set_editor_property('blend_mode', u.BlendMode.BLEND_ADDITIVE)
    material.set_editor_property('shading_model', u.MaterialShadingModel.MSM_UNLIT)
    material.set_editor_property('two_sided', True)
    edit = u.MaterialEditingLibrary
    uv = edit.create_material_expression(material, u.MaterialExpressionTextureCoordinate, -600, 0)
    opacity = edit.create_material_expression(material, u.MaterialExpressionScalarParameter, -600, 250)
    opacity.set_editor_property('parameter_name', 'RippleOpacity')
    opacity.set_editor_property('default_value', 0.)
    color = h.custom_expression(material, (-250, 0), 'One small blue contact wave',
        'float r=length((UV-.5)*2); float ring=exp(-pow((r-.63)/.115,2)); '
        'float core=.12*exp(-r*r*10); return float3(.015,.22,1.15)*(ring+core);',
        u.CustomMaterialOutputType.CMOT_FLOAT3, [('UV', uv)])
    assert edit.connect_material_property(color, '', u.MaterialProperty.MP_EMISSIVE_COLOR)
    assert edit.connect_material_property(opacity, '', u.MaterialProperty.MP_OPACITY)
    edit.layout_material_expressions(material)
    edit.recompile_material(material)
    return material


def add_ripple(seq, material, contact, location, end):
    existing = [b for b in seq.get_bindings() if OWN in map(str, b.get_binding_tags())]
    for binding in existing:
        for child in binding.get_child_possessables():
            child.remove()
        binding.remove()
    actors = u.get_editor_subsystem(u.EditorActorSubsystem)
    temporary = actors.spawn_actor_from_class(u.StaticMeshActor.static_class(), u.Vector(), u.Rotator(), transient=True)
    assert temporary
    mesh = temporary.get_editor_property('static_mesh_component')
    mesh.set_static_mesh(u.load_asset('/Engine/BasicShapes/Plane'))
    mesh.set_material(0, material)
    mesh.set_collision_profile_name('NoCollision')
    mesh.set_editor_property('generate_overlap_events', False)
    mesh.set_editor_property('cast_shadow', False)
    mesh.set_editor_property('mobility', u.ComponentMobility.MOVABLE)
    temporary.set_actor_enable_collision(False)
    binding = seq.add_spawnable_from_instance(temporary)
    binding.set_name('PawContactRipple')
    binding.tag_binding(OWN)
    template = binding.get_object_template()
    template.set_actor_enable_collision(False)
    spawn = h.property_section(binding, u.MovieSceneSpawnTrack)
    spawn.set_range(contact, contact+11)
    spawn.set_completion_mode(RESTORE)
    h.only(spawn.get_all_channels()).set_default(True)
    transform = binding.add_track(u.MovieScene3DTransformTrack).add_section()
    rows = [(f, (*location, 0., 0., 0., scale, scale, 1.))
            for f, scale in ((contact, .025), (contact+4, .12), (contact+10, .22))]
    axes(transform, rows, end)
    before = {b.get_id().export_text() for b in seq.get_bindings()}
    child = seq.add_possessable(mesh)
    parent = child.get_parent()
    child.set_parent(binding)
    child.set_name('PawRippleMaterial')
    if parent.get_id().export_text() != binding.get_id().export_text():
        assert parent.get_id().export_text() not in before and not parent.get_child_possessables()
        parent.remove()
    assert actors.destroy_actor(temporary)
    assert child.is_valid(), 'Invalid component binding'
    track = child.add_track(u.MovieSceneComponentMaterialTrack)
    assert track, 'Could not add the material parameter track'
    track.set_material_info(u.ComponentMaterialInfo(material_slot_index=0, material_type=u.ComponentMaterialType.INDEXED_MATERIAL))
    section = track.add_section()
    section.set_range(contact, contact+11)
    section.set_completion_mode(RESTORE)
    info = u.MaterialParameterInfo(name='RippleOpacity')
    for at, value in ((contact, .55), (contact+2, .72), (contact+10, 0.)):
        section.add_scalar_parameter_key(info, u.FrameNumber(h.tick(at)), value, '', '', u.MovieSceneKeyInterpolation.LINEAR)
    return binding


def apply(seq, clips, contract):
    parts = h.sequence_parts(seq)
    previous = h.describe_sequence(seq)
    seq.modify()
    probe, prep = clips['probe'], clips['prep']
    probe_start = old.STOP
    prep_start = probe_start + contract['probe_frames']
    takeoff_start = prep_start + contract['prep_frames']
    bridge_end = takeoff_start + contract['takeoff_frames']
    lift = takeoff_start + contract['takeoff_liftoff_frame']
    air_end, end = bridge_end + contract['air_frames'], bridge_end + contract['air_frames'] + 18
    assert 270 <= end <= 360, ('Departure must fit 9-12 seconds', end)
    assert takeoff_start < lift <= bridge_end
    contact = probe_start + contract['contact_frame']
    seq.set_playback_end(end)
    # Extend existing owned track ranges, keeping all binding GUIDs.
    for binding in seq.get_bindings():
        for track in binding.get_tracks():
            for section in track.get_sections():
                if section.get_end_frame() == previous['end']:
                    section.set_end_frame(end)
    for section in seq.get_tracks():
        for part in section.get_sections():
            if part.get_end_frame() == previous['end']:
                part.set_end_frame(end)
    animations = sorted(parts['anim_track'].get_sections(), key=h.span)
    assert animations[0].get_editor_property('params').animation.get_path_name().split('.')[0] == old.CLIPS[0]
    # The delivered first pose begins the downward look (about six degrees
    # from Idle). Blend it across the four stationary lead-in frames.
    animations[1].set_end_frame(probe_start+4)
    h.EASING.set_ease_out_duration(animations[1], h.tick(4))
    for section in animations[2:]:
        parts['anim_track'].remove_section(section)
    first = animation(parts['anim_track'], probe, probe_start, prep_start,
                      probe.sequence_length*30/contract['probe_frames'])
    h.EASING.set_ease_in_duration(first, h.tick(4))
    animation(parts['anim_track'], prep, prep_start, takeoff_start,
              prep.sequence_length*30/contract['prep_frames'])
    jump = u.load_asset(old.CLIPS[2])
    if 'takeoff' in clips:
        bridge = clips['takeoff']
        animation(parts['anim_track'], bridge, takeoff_start, bridge_end,
                  bridge.sequence_length*30/contract['takeoff_frames'])
    else:
        animation(parts['anim_track'], jump, takeoff_start, bridge_end,
                  (contract['jump_air_source_frame']-contract['jump_takeoff_source_frame'])/contract['takeoff_frames'],
                  contract['jump_takeoff_source_frame'])
    animation(parts['anim_track'], jump, bridge_end, air_end,
              (36.-contract['jump_air_source_frame'])/contract['air_frames'], contract['jump_air_source_frame'])
    animation(parts['anim_track'], jump, air_end, end, 0., 0., 36.-1/800)
    # World translation starts only when the hind feet have pushed off.
    flight = [(old.STOP, old.INSPECT_Y, 25.2), (lift, old.INSPECT_Y, 25.2)]
    for i in range(1, 81):
        t = i/80.
        distance = .08*t+.92*t*t*(2-t)
        flight.append((lift+(air_end-lift)*t, old.INSPECT_Y+(old.ENTRY_Y-old.INSPECT_Y)*distance,
                       25.2+14*t+contract.get('arc_height_cm', 80.)*math.sin(math.pi*t)**1.25))
    flight.append((end, old.ENTRY_Y, 39.2))
    for index in (1, 2):
        after(h.transform_channels(parts['cat'])[index], old.STOP, [(f, row[index-1]) for f, *row in flight])
    hidden = h.property_section(parts['bindings'][0], u.MovieSceneVisibilityTrack)
    channel = h.only(hidden.get_all_channels())
    for key in list(channel.get_keys()):
        channel.remove_key(key)
    channel.set_default(True)
    # Visibility tracks encode "visible", even when the bound property is bHidden.
    channel.add_key(u.FrameNumber(0), True)
    channel.add_key(u.FrameNumber(air_end), False)
    # Preserve the original opening and four-second front walk exactly.
    cuts = ((0, old.WALK_START), (old.WALK_START, probe_start), (probe_start, prep_start), (prep_start, end))
    for cut, span in zip(parts['cuts'], cuts):
        cut.set_range(*span)
    side = -1. if contract['contact_bone'].endswith('_L') else 1.
    probe_eye = (101.+side*53., old.INSPECT_Y-46., 27.)
    probe_aim = (101., old.INSPECT_Y-6., 23.)
    prep_eye = (101.+side*63., old.INSPECT_Y+62., 28.)
    prep_aim = (101., old.INSPECT_Y-18., 29.)
    follow = [h.camera_key(f, prep_eye, prep_aim) for f in (prep_start, lift)]
    # Track the actual higher arc, then settle at its apex as the portal occludes
    # the cat. A slow monotonic tilt cropped the ears during the initial rise.
    for frame in range(lift+1, air_end+1):
        t = min((frame-lift)/(air_end-lift), .54)
        sampled = lift+(air_end-lift)*t
        y = h.interpolate([(f,y) for f,y,z in flight], sampled)
        z = h.interpolate([(f,z) for f,y,z in flight], sampled)
        eye = (prep_eye[0]+side*8*t, prep_eye[1]+7*t, prep_eye[2]+.55*(z-25.2))
        aim = (101., max(old.PORTAL_Y, y-18*(1-t)), z+3.8)
        follow.append(h.camera_key(frame, eye, aim))
    follow.append(h.camera_key(end, eye, aim))
    camera_rows = [[h.camera_key(f, probe_eye, probe_aim) for f in (probe_start, prep_start)], follow]
    for index, curve, fov in zip((2, 3), camera_rows, (78., 76.)):
        axes(parts['camera_sections'][index], curve, end)
        component = parts['camera_components'][index]
        component.set_field_of_view(fov)
        settings = component.get_editor_property('post_process_settings').copy()
        for name, value in (('depth_of_field_fstop', 16.), ('motion_blur_amount', .035),
                            ('depth_of_field_focal_distance', 67. if index==2 else 95.)):
            settings.set_editor_property('override_'+name, True)
            settings.set_editor_property(name, value)
        component.set_editor_property('post_process_settings', settings)
    after(h.only(parts['light'].get_all_channels()), old.STOP,
          [(old.STOP, 8000.), (lift, 8000.), (air_end, 4800.)])
    fill = old.fill_binding(seq)
    fill_section = h.property_section(fill, u.MovieSceneFloatTrack)
    fill_channel = h.only(fill_section.get_all_channels())
    old_fill = [(f/800., v) for f, v in h.key_data(fill_channel)]
    fill_at_stop = h.interpolate(old_fill, old.STOP)
    after(fill_channel, old.STOP, [(old.STOP, fill_at_stop), (old.STOP+5, 200.), (lift, 200.), (air_end, 105.)])
    # Retain all existing light motion through the stop, then track the high arc.
    for section, xoffset, yoffset, zoffset in ((parts['light_transform'], 19., -41., 24.),
                (h.property_section(fill, u.MovieScene3DTransformTrack), -52., -43., 57.)):
        for index, channel in enumerate(h.transform_channels(section)):
            rows = []
            for f, y, z in flight:
                local = (-xoffset/1.25, (old.PORTAL_Y-y-yoffset)/1.25, (z+zoffset+.8)/1.25,
                         0.,0.,0.,1.,1.,1.)
                rows.append((f, local[index]))
            after(channel, old.STOP, rows)
    parts['fade'].set_range(air_end, end)
    h.write_keys(h.only(parts['fade'].get_all_channels()), [(air_end, 0.), (air_end+3, 0.), (end-1, 1.)])
    contact_pose = pose(probe, contract['contact_frame']*probe.sequence_length*30/contract['probe_frames'])
    foot = contact_pose[contract['contact_bone']].translation
    # The handoff measures the deformed sole centroid in the original Blender
    # rig's meter axes. FBX converts Blender -Y forward into this skeleton's +Y.
    point = contract['contact_point_blender_local_m']
    sole = (100*point[0], -100*point[1], 100*point[2])
    assert math.dist(sole[:2], (foot.x, foot.y)) < 4., ('Sole/rig axis mismatch', sole, xyz(foot))
    contact_position = (101.-2*sole[0], old.INSPECT_Y-2*sole[1], .28)
    material = ripple_material()
    add_ripple(seq, material, contact, contact_position, end)
    current = h.describe_sequence(seq)
    assert current['bindings'] == previous['bindings'], 'An existing binding GUID changed'
    assert current['cat']['ease_ticks'] == previous['cat']['ease_ticks']
    for index in range(2):
        assert current['cameras'][index]['keys'] == previous['cameras'][index]['keys']
        assert current['cameras'][index]['fov'] == previous['cameras'][index]['fov']
    for axis in range(9):
        prefix = lambda row: [key for key in row['cat']['keys'][axis] if key[0] < h.tick(old.STOP)]
        assert prefix(current) == prefix(previous), ('Changed original walk', axis)
    return {'sequence': current, 'material': material, 'timing': dict(probe_start=probe_start,
            contact=contact, prep_start=prep_start, takeoff_start=takeoff_start, lift=lift,
            bridge_end=bridge_end, air_end=air_end, end=end), 'contact_position': contact_position}


def main():
    assert not h.dirty(), h.dirty()
    contract = json.loads((SOURCE / 'contract.json').read_text(encoding='utf-8'))
    assert contract['production_status'] == 'received_and_reviewed'
    run = OUT / ('Integration-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    run.mkdir(parents=True)
    protected = {package: digest(package_file(package)) for package in (MESH, SKELETON, old.CLIPS[2])}
    report = {'success': False, 'contract_sha256': digest(SOURCE/'contract.json'), 'saved': []}
    try:
        skeleton = u.load_asset(SKELETON)
        clips = {name: import_clip(spec, skeleton) for name, spec in contract['clips'].items()}
        compression = precise_compression()
        for clip in clips.values():
            clip.set_editor_property('bone_compression_settings', compression)
            clip.set_editor_property('allow_frame_stripping', False)
        report['clips'] = {name: {'path': clip.get_path_name(), 'seconds': clip.sequence_length} for name, clip in clips.items()}
        for name, clip in clips.items():
            assert abs(clip.sequence_length*30-contract[name+'_frames']) < .01, (name, clip.sequence_length)
            roots = [pose(clip, frame)['root'].translation for frame in (0, clip.sequence_length*15, clip.sequence_length*30)]
            assert all(point.length() < .01 for point in roots), ('Unexpected root motion/scale', name, roots)
        report['entry_pose'] = seam(u.load_asset(old.CLIPS[1]), 12., clips['probe'], 0.)
        entry_body = [value for bone, value in report['entry_pose'].items() if bone not in ('head','ear_L','ear_R')]
        assert max(b['distance_world_cm'] for b in entry_body) < .3, report['entry_pose']
        assert max(b['angle_deg'] for b in report['entry_pose'].values()) < 8., report['entry_pose']
        report['seams'] = {'probe_to_prep': seam(clips['probe'], clips['probe'].sequence_length*30, clips['prep'], 0.)}
        if 'takeoff' in clips:
            report['seams']['prep_to_takeoff'] = seam(clips['prep'], clips['prep'].sequence_length*30, clips['takeoff'], 0.)
            report['seams']['takeoff_to_air'] = seam(clips['takeoff'], clips['takeoff'].sequence_length*30,
                                                   u.load_asset(old.CLIPS[2]), contract['jump_air_source_frame'])
        for name, bones in report['seams'].items():
            assert max(r['distance_world_cm'] for r in bones.values()) < 1., (name, bones)
            assert max(r['angle_deg'] for r in bones.values()) < 8., (name, bones)
        sequence = u.load_asset(SEQ)
        backup = OUT / 'Before/LS_Stage1_PortalExit.uasset'
        if not backup.exists():
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(package_file(SEQ), backup)
        result = apply(sequence, clips, contract)
        material = result.pop('material')
        report.update(result)
        allowed = {SEQ, material.get_path_name().split('.')[0], compression.get_path_name().split('.')[0],
                   *(clip.get_path_name().split('.')[0] for clip in clips.values())}
        assert set(h.dirty()) <= allowed, ('Unexpected dirty packages', h.dirty())
        for asset in (compression, *clips.values(), material, sequence):
            assert AS.save_loaded_asset(asset, False), asset.get_path_name()
            report['saved'].append(asset.get_path_name())
        assert not h.dirty(), h.dirty()
        assert all(digest(package_file(package)) == value for package, value in protected.items())
        report['success'] = True
        (OUT / 'integration_latest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    finally:
        (run / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print('PORTAL_ENTRY_INTEGRATION', str(run/'report.json'), report['success'])


if __name__ == '__main__':
    main()
