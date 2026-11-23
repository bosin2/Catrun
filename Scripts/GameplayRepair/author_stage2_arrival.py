"""Probe, author or cold-audit the canonical Stage2 arrival in a fresh UE commandlet.

Use -culture=en -catrunStage2Arrival=probe|author|polish|audit with the four geometry CVars set to 0.
Audit also takes -catrunStage2ArrivalBaseline=<completed author report.json>.
Author only saves the canonical Stage2 map and three new arrival packages.
After authoring, use a fresh polish process to persist editor-generated comment
GUID metadata, then cold-audit against that polish report.
"""

import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import statistics
import sys
import traceback

import unreal as u


ROOT = Path(u.Paths.project_dir()).resolve()
sys.path[:0] = [str(ROOT / 'Scripts/GameplayRepair'), str(ROOT / 'Scripts/Menu')]
from menu_graph import compile_bp
from stage2_arrival_graph import PAWN_TAG, audit_graph, author_director


MAP = '/Game/Maps/Stage2'
BASE = '/Game/Cinematics/Stage2/Arrival'
SEQUENCE = BASE + '/LS_Stage2_PortalArrival'
DIRECTOR = BASE + '/BP_Stage2PortalArrival'
PORTAL = BASE + '/BP_Stage2ArrivalPortal'
PORTAL_SOURCE = '/Game/Cinematics/Stage1/Portal/BP_Stage1PortalPresentation'
PACKAGES = (SEQUENCE, DIRECTOR, PORTAL, MAP)
ANIM = '/Game/Characters/BlackCat/Final/Animations/AN_BlackCat_'
CLIPS = ('JumpDown', 'Landing', 'Walk', 'Idle')
PAWS = ('paw_f_l', 'paw_f_r', 'paw_h_l', 'paw_h_r')
DIRECTOR_TAG = 'CatrunAuthoredStage2Arrival'
SEQUENCE_TAG = 'CatrunAuthoredStage2ArrivalSequence'
FPS, TICKS_PER_SECOND = 30, 24000
END, HANDOFF, BLEND = 360, 10.0, 2.0
PORTAL_LOCATION = (1375., 4009., 0.)
CVARS = ('Editor.AsyncStaticMeshCompilation', 'Editor.AsyncSkinnedAssetCompilation',
         'p.EnableDeferredPhysicsCreation', 'p.Chaos.EnableAsyncInitBody')

# Orthographic shots preserve the game's projection throughout the return blend.
# Each path row gives a display frame, camera position and point of interest.
SHOTS = (
    ('Entrance', 0, 90, 650., (
        (0, (1580., 3660., 220.), (1375., 3935., 90.)),
        (90, (1550., 3690., 223.), (1375., 3905., 83.)),
    )),
    ('Puzzle', 90, 210, 790., (
        (90, (1605., 3930., 269.), (1330., 3505., 45.)),
        (210, (1530., 3880., 277.), (1330., 3475., 55.)),
    )),
    ('GateAndReturn', 210, END, 850., (
        (210, (1515., 3740., 286.), (1375., 3260., 78.)),
        (240, (1515., 3740., 286.), (1375., 3260., 78.)),
        (300, (1515., 3815., 400.), (1345., 3555., 27.)),
        (END, (1515., 3815., 400.), (1345., 3555., 27.)),
    )),
)

AS = u.EditorAssetLibrary
ED = u.get_editor_subsystem(u.UnrealEditorSubsystem)
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
ACTORS = u.get_editor_subsystem(u.EditorActorSubsystem)
OUT = ROOT / 'Saved/Stage2Arrival20261116' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
REPORT = {'process_id': os.getpid(), 'completed': False, 'saved': []}


def persist(phase):
    REPORT['phase'] = phase
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'report.json').write_text(json.dumps(REPORT, ensure_ascii=False, indent=2), encoding='utf-8')


def arg(name):
    match = re.search(r'(?:^|\s)-' + name + r'=(?:"([^"]+)"|(\S+))',
                      u.SystemLibrary.get_command_line(), re.I)
    return (match.group(1) or match.group(2)) if match else None


def file_for(package):
    return ROOT / ('Content/' + package.removeprefix('/Game/') + ('.umap' if package == MAP else '.uasset'))


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def owned_hashes():
    return {package: digest(file_for(package)) if file_for(package).exists() else None for package in PACKAGES}


def protected_hashes():
    excluded = {file_for(package) for package in PACKAGES}
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted((ROOT / 'Content').rglob('*'))
            if p.is_file() and p.suffix.lower() in {'.uasset', '.umap', '.uexp', '.ubulk'} and p not in excluded}


def backup():
    REPORT['backups'] = {}
    for package in PACKAGES:
        path = file_for(package)
        if path.exists():
            target = OUT / 'Before' / path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            assert digest(target) == digest(path)
            REPORT['backups'][package] = {'path': str(target), 'sha256': digest(target)}
    persist('backed_up')


def dirty():
    return {p.get_name() for p in [*u.EditorLoadingAndSavingUtils.get_dirty_map_packages(),
                                   *u.EditorLoadingAndSavingUtils.get_dirty_content_packages()]}


def asset(package):
    obj = AS.load_asset(package)
    assert obj, package
    return obj


def one(items):
    items = list(items)
    assert len(items) == 1, items
    return items[0]


def vector(v):
    return [float(v.x), float(v.y), float(v.z)]


def transform(t):
    return {'translation': vector(t.translation), 'rotation': t.rotation.rotator().export_text(),
            'scale': vector(t.scale3d)}


def components(bp):
    subsystem = u.get_engine_subsystem(u.SubobjectDataSubsystem)
    lib = u.SubobjectDataBlueprintFunctionLibrary
    objects = (lib.get_associated_object(lib.get_data(handle))
               for handle in subsystem.k2_gather_subobject_data_for_blueprint(bp))
    return {obj.get_name().removesuffix('_GEN_VARIABLE'): obj for obj in objects if isinstance(obj, u.ActorComponent)}


def tagged(actors, tag):
    return [actor for actor in actors if tag in map(str, actor.tags)]


def actors_in(world):
    return list(u.GameplayStatics.get_all_actors_of_class(world, u.Actor))


def snapshot(actors):
    """Map authoring adds two actors. Record every other actor's identity/placement."""
    return {a.get_name(): [a.get_class().get_path_name(), a.get_actor_label(),
                           transform(a.get_actor_transform()), list(map(str, a.tags))] for a in actors
            if not {DIRECTOR_TAG, SEQUENCE_TAG}.intersection(map(str, a.tags))}


def pawn_and_camera(actors):
    pawn = one(a for a in actors if isinstance(a, u.Character) and a.get_actor_label() == 'BP_Cat_Player')
    camera = one(a for a in actors if a.get_class().get_name() == 'BP_QuarterViewCamera_C')
    lens = one(camera.get_components_by_class(u.CameraComponent))
    assert lens.projection_mode == u.CameraProjectionMode.ORTHOGRAPHIC
    assert (pawn.get_actor_location() - u.Vector(1375., 3700., 26.2)).length() < .15
    return pawn, camera, lens


def clip_samples(mesh):
    options = u.AnimPoseEvaluationOptions()
    options.set_editor_property('evaluation_type', u.AnimDataEvalType.SOURCE)
    options.set_editor_property('optional_skeletal_mesh', mesh)
    options.set_editor_property('extract_root_motion', False)
    options.set_editor_property('incorporate_root_motion_into_pose', False)
    options.set_editor_property('should_retarget', False)
    reports = {}
    for name in CLIPS:
        clip = asset(ANIM + name)
        length = clip.get_editor_property('sequence_length')
        assert clip.get_editor_property('skeleton') == mesh.get_editor_property('skeleton')
        assert not clip.get_editor_property('enable_root_motion'), name
        root = u.AnimationLibrary.extract_root_track_transform(clip, 0.)
        rows = []
        for frame in range(round(length * FPS) + 1):
            t = min(frame / FPS, length)
            sampled_root = u.AnimationLibrary.extract_root_track_transform(clip, t)
            assert (sampled_root.translation - root.translation).length() < .05, (name, frame)
            root_dot = sum(getattr(root.rotation, axis) * getattr(sampled_root.rotation, axis) for axis in 'xyzw')
            assert 1 - abs(root_dot) < .001, (name, frame, 'rotating animation root')
            pose = u.AnimPoseExtensions.get_anim_pose_at_time(clip, t, options)
            positions = {bone: vector(u.AnimPoseExtensions.get_bone_pose(pose, bone, u.AnimPoseSpaces.WORLD).translation)
                         for bone in (*PAWS, 'pelvis', 'head')}
            rows.append(positions)
        reports[name] = {'length': length, 'root': transform(root), 'samples': rows}
    return reports


def pose_distance(a, b):
    return sum((x - y) ** 2 for bone in a for x, y in zip(a[bone], b[bone]))


def motion(samples, mesh_scale):
    """Keep the measured JumpDown/Landing boundary and choose a walk window fit to idle."""
    jump, landing, walk, idle = [samples[name]['samples'] for name in CLIPS]
    assert pose_distance(jump[-1], landing[0]) < 1., 'JumpDown and Landing poses no longer match'
    assert pose_distance(landing[-1], idle[0]) < 4., 'Landing recover pose drifted'
    start = min(range(24), key=lambda i: pose_distance(landing[-1], walk[i]))
    end = min(range(start + 103, start + 114), key=lambda i: pose_distance(walk[i], idle[0]))
    stance_speeds = [(a[bone][1] - b[bone][1]) * FPS * mesh_scale
                     for a, b in zip(walk[start:end], walk[start + 1:end + 1]) for bone in PAWS
                     if max(a[bone][2], b[bone][2]) < 1.42 and a[bone][1] - b[bone][1] > .2]
    stride = statistics.median(stance_speeds) * (end - start) / FPS
    contact_delta = (min(jump[-1][bone][2] for bone in PAWS) - min(idle[0][bone][2] for bone in PAWS)) * mesh_scale
    return {'windows': [('JumpDown', 0, 39, .30, (len(jump) - 1) / FPS - .001),
                        ('Landing', 39, 75, 0., (len(landing) - 1) / FPS - .001),
                        ('Walk', 71, 182, start / FPS, end / FPS),
                        ('Idle', 178, END, 0., (END - 178) / FPS)],
            'walk_distance': stride, 'landing_z_adjustment': -contact_delta,
            'pose_distances': {'jump_to_landing': pose_distance(jump[-1], landing[0]),
                               'land_to_walk': pose_distance(landing[-1], walk[start]),
                               'walk_to_idle': pose_distance(walk[end], idle[0])}}


def probe(world, actors, pawn, camera, lens):
    mesh = one(pawn.get_components_by_class(u.SkeletalMeshComponent))
    capsule = one(pawn.get_components_by_class(u.CapsuleComponent))
    samples = clip_samples(mesh.get_skeletal_mesh_asset())
    plan = motion(samples, float(mesh.get_world_transform().scale3d.y))
    targets = {'Portal': (1375., 4005., 90.), 'Statue': (1575., 3690., 80.),
               'Plate': (1195., 3430., 6.), 'Gate11': (1375., 3210., 102.)}
    visible = u.TraceTypeQuery.TRACE_TYPE_QUERY1
    sightlines = []
    for name, _, _, _, keys in SHOTS:
        for frame, position, _ in keys:
            for target, point in targets.items():
                hit = u.SystemLibrary.line_trace_single(world, u.Vector(*position), u.Vector(*point),
                    visible, False, [pawn, camera], u.DrawDebugTrace.NONE, False)
                blocker = hit.to_dict().get('hit_actor') if hit else None
                sightlines.append([name, frame, target, blocker.get_actor_label() if blocker else None])
    geometry = {a.get_actor_label(): [vector(p) for p in a.get_actor_bounds(False)] for a in actors
                if re.search(r'SM_Stage2_Wall_16[67]|SM_Stage2_Wall_170|S2_Gate_(04|11)|'
                             r'S2_Prop_(Statue_C|Plate_C)', a.get_actor_label())}
    return {'pawn': transform(pawn.get_actor_transform()), 'mesh_relative': transform(mesh.get_relative_transform()),
            'mesh_world': transform(mesh.get_world_transform()), 'mesh': mesh.get_skeletal_mesh_asset().get_path_name(),
            'capsule': [capsule.get_scaled_capsule_radius(), capsule.get_scaled_capsule_half_height()],
            'camera': {'view': transform(lens.get_world_transform()), 'projection': str(lens.projection_mode),
                       'ortho_width': lens.ortho_width, 'fov': lens.field_of_view, 'aspect': lens.aspect_ratio},
            'geometry': geometry, 'sightlines': sightlines, 'clips': samples, 'motion': plan}


def primitive_components(actor):
    # Sequencer templates are unregistered archetypes: the actor's runtime
    # OwnedComponents cache can be empty even though its serialized subobjects exist.
    found = list(actor.get_components_by_class(u.PrimitiveComponent))
    if isinstance(actor, u.SkeletalMeshActor):
        found.append(actor.get_editor_property('skeletal_mesh_component'))
    elif actor.get_class().get_path_name().startswith(PORTAL + '.'):
        for name in ('Stone', 'Runes', 'Surface', 'PortalDepthCore', 'PortalAetherHalo'):
            found.append(actor.get_editor_property(name))
    return list({item.get_path_name(): item for item in found if item}.values())


def disable_collision(actor):
    actor.set_actor_enable_collision(False)
    for item in primitive_components(actor):
        item.set_collision_profile_name('NoCollision')
        item.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
        item.set_editor_property('generate_overlap_events', False)


def copy_portal():
    portal = AS.duplicate_asset(PORTAL_SOURCE, PORTAL)
    assert portal and portal.get_path_name().startswith(PORTAL + '.')
    items = components(portal)
    primitives = [c for c in items.values() if isinstance(c, u.PrimitiveComponent)]
    assert len(primitives) >= 5, list(items)
    for item in primitives:
        item.set_collision_profile_name('NoCollision')
        item.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
        item.set_editor_property('generate_overlap_events', False)
        item.set_editor_property('mobility', u.ComponentMobility.MOVABLE)
    items['BlueLight'].set_intensity(650.)
    compile_bp(portal)
    return portal


def section_range(section, first, last):
    section.set_range(first, last)
    section.set_completion_mode(u.MovieSceneCompletionMode.RESTORE_STATE)
    return section


def spawnable(binding, name):
    assert binding.get_object_template(), name
    binding.set_name(name)
    track = one(binding.find_tracks_by_type(u.MovieSceneSpawnTrack))
    section = section_range(one(track.get_sections()), 0, END)
    one(section.get_channels_by_type(u.MovieSceneScriptingBoolChannel)).set_default(True)
    return binding


def transform_track(binding, defaults, keys=()):
    section = section_range(binding.add_track(u.MovieScene3DTransformTrack).add_section(), 0, END)
    channels = section.get_channels_by_type(u.MovieSceneScriptingDoubleChannel)
    assert len(channels) >= 9
    for channel, value in zip(channels, defaults):
        channel.set_default(value)
    for frame, values in keys:
        for channel, value in zip(channels, values):
            channel.add_key(u.FrameNumber(frame), value, 0., u.MovieSceneTimeUnit.DISPLAY_RATE,
                            u.MovieSceneKeyInterpolation.AUTO)


def polish_camera(sequence):
    """Update only this task's editable camera curves; preserve all other tracks."""
    sequence.modify()
    for name, _, _, _, keys in SHOTS:
        binding = one(b for b in sequence.get_bindings() if b.get_name() == name)
        section = one(one(binding.find_tracks_by_type(u.MovieScene3DTransformTrack)).get_sections())
        channels = section.get_channels_by_type(u.MovieSceneScriptingDoubleChannel)
        assert len(channels) == 9
        rows = []
        for frame, position, target in keys:
            rotation = u.MathLibrary.find_look_at_rotation(u.Vector(*position), u.Vector(*target))
            rows.append((frame, [*position, rotation.roll, rotation.pitch, rotation.yaw, 1., 1., 1.]))
        for index, channel in enumerate(channels):
            for key in list(channel.get_keys()):
                channel.remove_key(key)
            channel.set_default(rows[0][1][index])
            for frame, values in rows:
                channel.add_key(u.FrameNumber(frame), values[index], 0., u.MovieSceneTimeUnit.DISPLAY_RATE,
                                u.MovieSceneKeyInterpolation.AUTO)


def visibility(binding, visible, reveal=None):
    track = binding.add_track(u.MovieSceneVisibilityTrack)
    track.set_property_name_and_path('bHidden', 'bHidden')
    section = section_range(track.add_section(), 0, END)
    channel = one(section.get_channels_by_type(u.MovieSceneScriptingBoolChannel))
    channel.set_default(visible)
    channel.add_key(u.FrameNumber(0), visible)
    if reveal is not None:
        channel.add_key(u.FrameNumber(reveal), True)


def author_cat(sequence, pawn, plan):
    binding = spawnable(sequence.add_spawnable_from_class(u.SkeletalMeshActor.static_class()), 'CosmeticCat')
    template = binding.get_object_template()
    mesh = template.get_editor_property('skeletal_mesh_component')
    assert mesh
    source = one(pawn.get_components_by_class(u.SkeletalMeshComponent))
    mesh.set_skeletal_mesh_asset(source.get_skeletal_mesh_asset())
    for index in range(source.get_num_materials()):
        mesh.set_material(index, source.get_material(index))
    disable_collision(template)
    mesh.set_editor_property('mobility', u.ComponentMobility.MOVABLE)

    base = source.get_world_transform()
    rotation = base.rotation.rotator()
    scale = vector(base.scale3d)
    x, playable_y, foot_z = vector(base.translation)
    landing_y = playable_y + plan['walk_distance']
    rows = ((0, 4021., 33.), (5, 4003., 37.), (14, 3948., 63.),
            (28, landing_y + .22 * (4003. - landing_y), 31.),
            (39, landing_y, plan['landing_z_adjustment']), (49, landing_y, 0.),
            (73, landing_y, 0.), (79, landing_y - 4., 0.), (172, playable_y + 5., 0.),
            (182, playable_y, 0.), (END, playable_y, 0.))
    keys = [(frame, [x, y, foot_z + z, rotation.roll, rotation.pitch, rotation.yaw, *scale]) for frame, y, z in rows]
    transform_track(binding, keys[0][1], keys)
    visibility(binding, False, reveal=5)

    track = binding.add_track(u.MovieSceneSkeletalAnimationTrack)
    for name, first, last, offset, end in plan['windows']:
        section = section_range(track.add_section(), first, last)
        params = u.MovieSceneSkeletalAnimationParams()
        params.set_editor_property('animation', asset(ANIM + name))
        params.set_editor_property('play_rate', u.MovieSceneTimeWarpExtensions.make_time_warp((end - offset) * FPS / (last - first)))
        params.set_editor_property('first_loop_start_frame_offset', u.FrameNumber(round(offset * TICKS_PER_SECOND)))
        params.set_editor_property('force_custom_mode', True)
        params.set_editor_property('skip_anim_notifiers', True)
        section.set_editor_property('params', params)
        ease = u.MovieSceneSectionEasingExtensions
        frames_to_ticks = TICKS_PER_SECOND // FPS
        if name in ('Walk', 'Idle'):
            ease.set_ease_in_duration(section, 4 * frames_to_ticks)
        if name in ('Landing', 'Walk'):
            ease.set_ease_out_duration(section, 4 * frames_to_ticks)


def author_sequence(pawn, lens, portal, plan):
    folder, name = SEQUENCE.rsplit('/', 1)
    sequence = u.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, u.LevelSequence, u.LevelSequenceFactoryNew())
    assert sequence
    sequence.set_display_rate(u.FrameRate(FPS, 1))
    sequence.set_tick_resolution_directly(u.FrameRate(TICKS_PER_SECOND, 1))
    sequence.set_playback_start(0)
    sequence.set_playback_end(END)
    real = sequence.add_possessable(pawn)
    real.set_name('Gameplay Cat Visibility')
    real.tag_binding(PAWN_TAG)
    visibility(real, False)
    author_cat(sequence, pawn, plan)

    location = u.Vector(*PORTAL_LOCATION)
    temp = ACTORS.spawn_actor_from_class(portal.generated_class(), location, u.Rotator())
    assert temp
    try:
        disable_collision(temp)
        binding = spawnable(sequence.add_spawnable_from_instance(temp), 'ArrivalPortal')
        disable_collision(binding.get_object_template())
        transform_track(binding, [*PORTAL_LOCATION, 0., 0., 0., 1., 1., 1.])
    finally:
        assert ACTORS.destroy_actor(temp)

    cuts = sequence.add_track(u.MovieSceneCameraCutTrack)
    for name, first, last, width, path in SHOTS:
        camera = spawnable(sequence.add_spawnable_from_class(u.CameraActor.static_class()), name)
        component = camera.get_object_template().get_editor_property('CameraComponent')
        component.set_editor_property('projection_mode', lens.projection_mode)
        component.set_editor_property('ortho_width', width)
        component.set_editor_property('field_of_view', lens.field_of_view)
        component.set_editor_property('aspect_ratio', lens.aspect_ratio)
        component.set_editor_property('constrain_aspect_ratio', lens.get_editor_property('constrain_aspect_ratio'))
        keys = []
        for frame, position, target in path:
            look = u.MathLibrary.find_look_at_rotation(u.Vector(*position), u.Vector(*target))
            keys.append((frame, [*position, look.roll, look.pitch, look.yaw, 1., 1., 1.]))
        transform_track(camera, keys[0][1], keys)
        cut = section_range(cuts.add_section(), first, last)
        cut.set_camera_binding_id(sequence.get_binding_id(camera))
        # The lease restores its owned view. Sequencer must not restore over a newer view owner.
        cut.set_completion_mode(u.MovieSceneCompletionMode.KEEP_STATE)
    return sequence


def place(world, camera, sequence, director):
    existing = actors_in(world)
    assert not (tagged(existing, DIRECTOR_TAG) or tagged(existing, SEQUENCE_TAG))
    actor = ACTORS.spawn_actor_from_class(u.LevelSequenceActor.static_class(), u.Vector(), u.Rotator())
    actor.set_actor_label('Stage2 Portal Arrival - Editable Sequence')
    actor.set_editor_property('tags', [u.Name(SEQUENCE_TAG)])
    actor.set_editor_property('level_sequence_asset', sequence)
    settings = actor.get_editor_property('playback_settings')
    settings.set_editor_property('auto_play', False)
    settings.set_editor_property('pause_at_end', True)
    actor.set_editor_property('playback_settings', settings)
    controller = ACTORS.spawn_actor_from_class(director.generated_class(), u.Vector(), u.Rotator())
    controller.set_actor_label('Stage2 Portal Arrival - Blueprint Director')
    controller.set_editor_property('tags', [u.Name(DIRECTOR_TAG)])
    controller.set_editor_property('CinematicActor', actor)
    controller.set_editor_property('ExpectedGameplayView', camera)


def collision_audit(template):
    assert not template.get_actor_enable_collision(), template.get_name()
    primitives = primitive_components(template)
    assert primitives, template.get_name()
    for item in primitives:
        assert item.get_collision_enabled() == u.CollisionEnabled.NO_COLLISION, item.get_name()
        assert not item.get_editor_property('generate_overlap_events'), item.get_name()
    return sorted(item.get_name() for item in primitives)


def track_audit(track):
    rows = []
    for section in track.get_sections():
        expected = (u.MovieSceneCompletionMode.KEEP_STATE if isinstance(section, u.MovieSceneCameraCutSection)
                    else u.MovieSceneCompletionMode.RESTORE_STATE)
        assert section.get_completion_mode() == expected
        row = {'span': [section.get_start_frame(), section.get_end_frame()],
               'completion': str(section.get_completion_mode())}
        assert 0 <= row['span'][0] < row['span'][1] <= END, row['span']
        if isinstance(section, u.MovieSceneSkeletalAnimationSection):
            params = section.get_editor_property('params')
            assert params.get_editor_property('skip_anim_notifiers') and params.get_editor_property('force_custom_mode')
            row['animation'] = params.get_editor_property('animation').get_path_name()
            row['offset'] = params.get_editor_property('first_loop_start_frame_offset').value
        if isinstance(section, u.MovieSceneCameraCutSection):
            row['camera'] = section.get_camera_binding_id().export_text()
        if isinstance(section, u.MovieScene3DTransformSection):
            row['curves'] = [{'default': channel.get_default(), 'keys': [
                [key.get_time(u.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value, key.get_value()]
                for key in channel.get_keys()]} for channel in
                section.get_channels_by_type(u.MovieSceneScriptingDoubleChannel)]
        if isinstance(section, u.MovieSceneBoolSection):
            channel = one(section.get_channels_by_type(u.MovieSceneScriptingBoolChannel))
            row['values'] = [key.get_value() for key in channel.get_keys()]
            row['default'] = channel.get_default()
        rows.append(row)
    return {'track': track.get_class().get_name(), 'sections': rows}


def audit(world, sequence, director, portal, camera):
    assert (sequence.get_playback_start(), sequence.get_playback_end()) == (0, END)
    rate = sequence.get_display_rate()
    assert (rate.numerator, rate.denominator) == (FPS, 1)
    tick = sequence.get_tick_resolution()
    assert (tick.numerator, tick.denominator) == (TICKS_PER_SECOND, 1)
    map_actors = actors_in(world)
    controller = one(tagged(map_actors, DIRECTOR_TAG))
    player = one(tagged(map_actors, SEQUENCE_TAG))
    assert controller.get_class() == director.generated_class()
    assert controller.get_editor_property('CinematicActor') == player
    assert controller.get_editor_property('ExpectedGameplayView') == camera
    assert isinstance(controller.get_editor_property('ExitTransition'), u.CatrunExitTransitionComponent)
    assert player.get_editor_property('level_sequence_asset') == sequence
    settings = player.get_editor_property('playback_settings')
    assert not settings.get_editor_property('auto_play') and settings.get_editor_property('pause_at_end')
    assert settings.get_editor_property('finish_completion_state_override') == u.MovieSceneCompletionModeOverride.NONE

    bindings = {b.get_name(): b for b in sequence.get_bindings()}
    assert set(bindings) == {'Gameplay Cat Visibility', 'CosmeticCat', 'ArrivalPortal', *(shot[0] for shot in SHOTS)}
    real = bindings['Gameplay Cat Visibility']
    assert PAWN_TAG in map(str, real.get_binding_tags()) and not real.get_object_template()
    cat = bindings['CosmeticCat']
    assert len(cat.find_tracks_by_type(u.MovieSceneSkeletalAnimationTrack)) == 1
    assert bindings['ArrivalPortal'].get_object_template().get_class() == portal.generated_class()
    assert not any(a.get_class() == portal.generated_class() for a in map_actors)
    collision = {name: collision_audit(bindings[name].get_object_template()) for name in ('CosmeticCat', 'ArrivalPortal')}
    portal_primitives = [c for c in components(portal).values() if isinstance(c, u.PrimitiveComponent)]
    assert len(portal_primitives) == len(collision['ArrivalPortal'])
    assert all(c.get_collision_enabled() == u.CollisionEnabled.NO_COLLISION for c in portal_primitives)
    real_tracks = list(real.get_tracks())
    assert len(real_tracks) == 1 and isinstance(real_tracks[0], u.MovieSceneVisibilityTrack)
    assert one(track_audit(real_tracks[0])['sections'])['values'] == [False]
    cuts = one(sequence.get_tracks())
    assert isinstance(cuts, u.MovieSceneCameraCutTrack)
    for section, (name, first, last, width, _) in zip(cuts.get_sections(), SHOTS, strict=True):
        expected = sequence.get_binding_id(bindings[name])
        assert section.get_camera_binding_id().export_text() == expected.export_text()
        assert (section.get_start_frame(), section.get_end_frame()) == (first, last)
        lens = bindings[name].get_object_template().get_editor_property('CameraComponent')
        assert lens.projection_mode == u.CameraProjectionMode.ORTHOGRAPHIC and abs(lens.ortho_width - width) < .01
    return {'map': [controller.get_name(), player.get_name(), camera.get_name()], 'collision_free': collision,
            'director': audit_graph(director), 'camera_cuts': track_audit(cuts),
            'bindings': {name: [track_audit(track) for track in b.get_tracks()] for name, b in bindings.items()}}


def main():
    mode = arg('catrunStage2Arrival')
    if mode in {'revise', 'revision_cold'}:
        import stage2_arrival_revision
        from types import SimpleNamespace
        stage2_arrival_revision.run(SimpleNamespace(**globals()), mode)
        return
    if mode in {'migrate', 'cold'}:
        import stage2_arrival_shots
        from types import SimpleNamespace
        stage2_arrival_shots.run(SimpleNamespace(**globals()), mode)
        return
    assert mode in {'probe', 'author', 'polish', 'audit'}, 'Pass -catrunStage2Arrival=probe|author|polish|audit'
    REPORT['mode'] = mode
    REPORT['cvars'] = {name: u.SystemLibrary.get_console_variable_int_value(name) for name in CVARS}
    assert all(value == 0 for value in REPORT['cvars'].values()), REPORT['cvars']
    assert not ED.get_game_world() and not dirty(), ('Fresh process required', dirty())
    REPORT['before_hashes'] = owned_hashes()
    REPORT['protected_hashes'] = protected_hashes()
    persist('preflight')

    if ED.get_editor_world().get_path_name().split('.')[0] != MAP:
        assert LEVEL.load_level(MAP)
    world = ED.get_editor_world()
    assert world.get_path_name().split('.')[0] == MAP
    actors = actors_in(world)
    pawn, camera, lens = pawn_and_camera(actors)
    original = snapshot(actors)
    REPORT['preserved_actors'] = len(original)
    REPORT['preserved_actor_sha256'] = hashlib.sha256(json.dumps(original, sort_keys=True).encode()).hexdigest()
    if mode in {'probe', 'author'}:
        REPORT['geometry_and_clips'] = probe(world, actors, pawn, camera, lens)
        persist('probed')
    if mode == 'author':
        assert not any(file_for(p).exists() or AS.does_asset_exist(p) for p in PACKAGES[:-1]), 'Only a new Arrival scope can be authored'
        backup()
        portal = copy_portal()
        sequence = author_sequence(pawn, lens, portal, REPORT['geometry_and_clips']['motion'])
        director = author_director(DIRECTOR, HANDOFF, BLEND)
        place(world, camera, sequence, director)
        assert snapshot(actors_in(world)) == original, 'Unrelated actor identity or placement changed'
        REPORT['structure'] = audit(world, sequence, director, portal, camera)
        assert dirty() <= set(PACKAGES), dirty()
        for package, obj in ((PORTAL, portal), (SEQUENCE, sequence), (DIRECTOR, director)):
            assert AS.save_loaded_asset(obj, False), package
            REPORT['saved'].append(package)
            persist('saved_asset')
        assert LEVEL.save_current_level()
        REPORT['saved'].append(MAP)
    if mode == 'polish':
        backup()
        sequence = asset(SEQUENCE)
        polish_camera(sequence)
        REPORT['structure'] = audit(world, sequence, asset(DIRECTOR), asset(PORTAL), camera)
        assert snapshot(actors_in(world)) == original
        assert dirty() <= {SEQUENCE}, dirty()
        assert AS.save_loaded_asset(sequence, False)
        REPORT['saved'].append(SEQUENCE)
        # Persist comment GUIDs supplied by UE on cold load of the initial BP.
        assert AS.save_loaded_asset(asset(DIRECTOR), False)
        REPORT['saved'].append(DIRECTOR)
    if mode == 'audit':
        baseline = json.loads(Path(arg('catrunStage2ArrivalBaseline')).read_text(encoding='utf-8'))
        assert baseline['completed'] and baseline['mode'] in {'author', 'polish'} and baseline['process_id'] != os.getpid()
        for key in ('protected_hashes', 'preserved_actors', 'preserved_actor_sha256'):
            assert baseline[key] == REPORT[key], key
        assert REPORT['before_hashes'] == baseline['after_hashes']
        REPORT['structure'] = audit(world, asset(SEQUENCE), asset(DIRECTOR), asset(PORTAL), camera)
        assert REPORT['structure'] == baseline['structure'], 'Cold load changed authored structure'
    REPORT['after_hashes'] = owned_hashes()
    assert REPORT['protected_hashes'] == protected_hashes(), 'Unrelated content bytes changed'
    if mode not in {'author', 'polish'}:
        assert REPORT['before_hashes'] == REPORT['after_hashes'], 'Read-only run changed asset bytes'
    assert not dirty(), ('Unexpected dirty packages at completion', dirty())
    REPORT['completed'] = True
    persist('complete')
    u.log('CATRUN_STAGE2_ARRIVAL_OK ' + str(OUT / 'report.json'))


try:
    main()
except Exception:
    REPORT['error'] = traceback.format_exc()
    persist('failed')
    u.log_error('CATRUN_STAGE2_ARRIVAL_FAILED ' + str(OUT / 'report.json'))
    raise
