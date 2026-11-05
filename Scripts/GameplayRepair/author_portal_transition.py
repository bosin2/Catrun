"""Root-owned portal asset author/audit. No PIE, playback, capture or game ticking.

The user rejected the former native cinematic clock. This script authors a real
Blueprint director and an ordinary, editable LevelSequence: character transforms,
poses, cameras, blue light and fade are sequence tracks. Native adapters only own
resource leases, collision queries and asynchronous durable I/O.

Run in an isolated, fresh UE Python commandlet with -catrunPortalAuthor or
-catrunPortalAuditOnly -catrunPortalBaseline=<author report.json>, and
-catrunGeometryIsolated. Four startup CVars below must all already be zero.
"""
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import traceback

import unreal as u
from editor_toolset.toolsets.actor import ActorTools
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
from editor_toolset.toolsets.object import ObjectTools
from toolset_registry.helpers import compile_blueprint

ROOT = Path(u.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts/Menu'))
from menu_graph import Graph, add, audit as widget_audit, literal, pin, properties, ui, widgets, wire

COMMAND = u.SystemLibrary.get_command_line()
AUDIT = '-catrunportalauditonly' in COMMAND.lower()
RESUME_MAPS = '-catrunportalresumemaps' in COMMAND.lower()
OUT = ROOT / 'Saved/GameplayRepair20261105/PortalTransition' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
MAPS = ('/Game/Maps/Stage1', '/Game/Maps/SoundTest_Stage1')
BASE = '/Game/Cinematics/Stage1/Portal'
SEQUENCE = BASE + '/LS_Stage1_PortalExit'
PRESENTATION = BASE + '/BP_Stage1PortalPresentation'
DIRECTOR = BASE + '/BP_Stage1PortalExit'
OVERLAY = BASE + '/WBP_ExitTransition'
SURFACE = BASE + '/M_Stage1PortalBlue'
OWNED = (SEQUENCE, PRESENTATION, DIRECTOR, OVERLAY, SURFACE)
FRAME = '/Game/Environment/Stage2/Architecture/PortalFrame'
CLIPS = ('/Game/Characters/BlackCat/Final/Animations/AN_BlackCat_Walk',
         '/Game/Characters/BlackCat/Final/Animations/Cinematics/AN_BlackCat_PortalInspect',
         '/Game/Characters/BlackCat/Final/Animations/Cinematics/AN_BlackCat_PortalJumpIn')
CVARS = ('Editor.AsyncStaticMeshCompilation', 'Editor.AsyncSkinnedAssetCompilation',
         'p.EnableDeferredPhysicsCreation', 'p.Chaos.EnableAsyncInitBody')
AS = u.EditorAssetLibrary
ED = u.get_editor_subsystem(u.UnrealEditorSubsystem)
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
ACTORS = u.get_editor_subsystem(u.EditorActorSubsystem)
NONE = u.DrawDebugTrace.NONE
DISPLAY = u.MovieSceneTimeUnit.DISPLAY_RATE
TICKS = u.MovieSceneTimeUnit.TICK_RESOLUTION
LINEAR = u.MovieSceneKeyInterpolation.LINEAR
REPORT = {'audit_only': AUDIT, 'process_id': os.getpid(), 'completed': False,
          'runtime_or_visual_verified': False, 'backups': [], 'saved': [], 'maps': {}, 'errors': [],
          'limits': ['Saved asset structure and sampled static collision only.',
                     'No sequence playback, viewport/capture, PIE or user input was performed.',
                     'Shot composition, acting and live save/travel require the user\'s later manual verification.']}

# Editable first authoring choices; there is no C++ marker or duration contract.
FPS, TICK_RATE = 30, 24000
WALK_END, INSPECT_END, JUMP_LIFT, JUMP_CROSS, JUMP_END, FADE_END = 72, 192, 209.5, 222, 228, 244
TRIGGER = (101., -80., 25.2)
# Start curve at the deepest qualified edge so its initial-value ease never
# pulls a cat backward. Sequencer blends from its actual captured arrival.
START = (101., -115., 25.2)
INSPECT = (101., -250., 25.2)
ENTRY = (101., -315., 39.2)
PLANE_Y = INSPECT[1] + (ENTRY[1] - INSPECT[1]) * ((JUMP_CROSS - JUMP_LIFT) / (JUMP_END - JUMP_LIFT))
PORTAL = (101., PLANE_Y, -.8)
EXTENT = (30., 35., 80.)
PORTAL_TAG = 'CatrunAuthoredStage1Portal'
DIRECTOR_TAG = 'CatrunAuthoredStage1Exit'


def persist(phase=None):
    if phase:
        REPORT['phase'] = phase
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'report.json').write_text(json.dumps(REPORT, ensure_ascii=False, indent=2), encoding='utf-8')


def v(p):
    return [float(p.x), float(p.y), float(p.z)]


def path(o):
    return o.get_path_name() if o else None


def dirty():
    return sorted(p.get_name() for p in list(u.EditorLoadingAndSavingUtils.get_dirty_map_packages())
                  + list(u.EditorLoadingAndSavingUtils.get_dirty_content_packages()))


def file_for(package):
    assert package.startswith('/Game/')
    return ROOT / ('Content/' + package[6:] + ('.umap' if package in MAPS else '.uasset'))


def digest(filename):
    return hashlib.sha256(filename.read_bytes()).hexdigest()


def hashes():
    return {p: digest(file_for(p)) if file_for(p).exists() else None for p in (*MAPS, *OWNED)}


def protected_hashes():
    owned = {file_for(p).resolve() for p in (*MAPS, *OWNED)}
    return {str(p.relative_to(ROOT)).replace('\\', '/'): digest(p)
            for p in sorted((ROOT / 'Content').rglob('*'))
            if p.is_file() and p.suffix in ('.uasset', '.umap') and p.resolve() not in owned}


def backup():
    for package in (*MAPS, *OWNED):
        source = file_for(package)
        row = {'package': package, 'existed': source.exists()}
        if source.exists():
            target = OUT / 'Before' / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            row.update(file=str(target), sha256=digest(target))
            assert row['sha256'] == digest(source)
        REPORT['backups'].append(row)
    persist('backed_up_before_any_asset_mutation')


def load(package):
    assert not dirty(), ('Refuse dirty-world switch', dirty())
    assert LEVEL.load_level(package)
    world = ED.get_editor_world()
    assert world and world.get_path_name().split('.')[0] == package
    assert not ED.get_game_world()
    return world, list(u.GameplayStatics.get_all_actors_of_class(world, u.Actor))


def asset(package):
    result = AS.load_asset(package)
    assert result, ('Missing required source asset', package)
    return result


def new_asset(package, cls, factory):
    assert not AS.does_asset_exist(package), ('Refuse overwrite/rebuild existing portal asset', package)
    folder, name = package.rsplit('/', 1)
    result = u.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, cls, factory)
    assert result
    return result


def strict(bp):
    compile_blueprint(bp, True)
    assert bp.get_editor_property('status') == u.BlueprintStatus.BS_UP_TO_DATE


def components(bp):
    sds = u.get_engine_subsystem(u.SubobjectDataSubsystem)
    lib = u.SubobjectDataBlueprintFunctionLibrary
    return [lib.get_associated_object(lib.get_data(h)) for h in sds.k2_gather_subobject_data_for_blueprint(bp)]


def component_named(owner, name):
    values = components(owner) if isinstance(owner, u.Blueprint) else owner.get_components_by_class(u.ActorComponent)
    found = {c.get_path_name(): c for c in values if c and c.get_name().removesuffix('_GEN_VARIABLE') == name}
    assert len(found) == 1, (name, list(found))
    return next(iter(found.values()))


def author_surface():
    mat = new_asset(SURFACE, u.Material, u.MaterialFactoryNew())
    mat.set_editor_property('blend_mode', u.BlendMode.BLEND_MASKED)
    mat.set_editor_property('shading_model', u.MaterialShadingModel.MSM_UNLIT)
    mat.set_editor_property('two_sided', True)
    edit = u.MaterialEditingLibrary
    uv = edit.create_material_expression(mat, u.MaterialExpressionTextureCoordinate, -500, 0)
    time = edit.create_material_expression(mat, u.MaterialExpressionTime, -500, 200)
    color = edit.create_material_expression(mat, u.MaterialExpressionCustom, -200, 0)
    color.set_editor_property('output_type', u.CustomMaterialOutputType.CMOT_FLOAT3)
    color.set_editor_property('code', 'float2 p=(UV-.5)*2; float r=length(p); float edge=pow(saturate(r),5); '
        'float flow=.75+.25*sin(atan2(p.y,p.x)*9-T*1.8+r*19); '
        'return float3(.004,.012,.04)+float3(.025,.35,1.5)*edge*flow;')
    inputs = []
    for name in ('UV', 'T'):
        inp = u.CustomInput(); inp.set_editor_property('input_name', name); inputs.append(inp)
    color.set_editor_property('inputs', inputs)
    mask = edit.create_material_expression(mat, u.MaterialExpressionCustom, -200, 300)
    mask.set_editor_property('output_type', u.CustomMaterialOutputType.CMOT_FLOAT1)
    mask.set_editor_property('code', 'float2 p=(UV-.5)*2; return 1-dot(p,p);')
    inp = u.CustomInput(); inp.set_editor_property('input_name', 'UV'); mask.set_editor_property('inputs', [inp])
    mat.set_editor_property('opacity_mask_clip_value', .01)
    assert edit.connect_material_expressions(uv, '', color, 'UV')
    assert edit.connect_material_expressions(time, '', color, 'T')
    assert edit.connect_material_expressions(uv, '', mask, 'UV')
    assert edit.connect_material_property(color, '', u.MaterialProperty.MP_EMISSIVE_COLOR)
    assert edit.connect_material_property(mask, '', u.MaterialProperty.MP_OPACITY_MASK)
    edit.layout_material_expressions(mat); edit.recompile_material(mat)
    return mat


def author_presentation(material):
    folder, name = PRESENTATION.rsplit('/', 1)
    bp = BP.create(folder, name, u.Actor.static_class())
    for name, cls in (('Stone', u.StaticMeshComponent), ('Runes', u.StaticMeshComponent),
                      ('Surface', u.StaticMeshComponent), ('BlueLight', u.PointLightComponent)):
        ActorTools.add_component(bp, cls.static_class(), name)
    # Reacquire all component templates after structural compiles.
    for name, mesh_name, material_name in (
            ('Stone', 'SM_PortalFrame_Stone', 'MI_PortalFrame_Stone'),
            ('Runes', 'SM_PortalFrame_Runes', 'MI_PortalFrame_Runes_Blue')):
        c = component_named(bp, name)
        c.set_static_mesh(asset(FRAME + '/Meshes/' + mesh_name))
        c.set_material(0, asset(FRAME + '/Materials/' + material_name))
        c.set_editor_property('relative_scale3d', u.Vector(.75, .75, .75))
        c.set_editor_property('generate_overlap_events', False)
        c.set_collision_profile_name('BlockAll' if name == 'Stone' else 'NoCollision')
        c.set_editor_property('mobility', u.ComponentMobility.STATIC)
    surface = component_named(bp, 'Surface')
    surface.set_static_mesh(asset('/Engine/BasicShapes/Plane')); surface.set_material(0, material)
    surface.set_collision_profile_name('NoCollision'); surface.set_editor_property('generate_overlap_events', False)
    surface.set_editor_property('cast_shadow', False)
    surface.set_editor_property('relative_location', u.Vector(0, 0, 90))
    surface.set_editor_property('relative_rotation', u.Rotator(pitch=0, yaw=0, roll=90))
    surface.set_editor_property('relative_scale3d', u.Vector(1.05, 1.8, 1))
    light = component_named(bp, 'BlueLight')
    light.set_editor_property('relative_location', u.Vector(0, -40, 65))
    light.set_editor_property('mobility', u.ComponentMobility.MOVABLE)
    light.set_light_color(u.LinearColor(.035, .25, 1., 1.))
    light.set_intensity(0.); light.set_attenuation_radius(210.)
    light.set_editor_property('cast_shadows', False)
    strict(bp)
    return bp


def author_widget():
    folder, name = OVERLAY.rsplit('/', 1)
    bp = ui('CreateWidgetBlueprint', folder, name, u.UserWidget.static_class())
    root = add(bp, u.CanvasPanel, 'TransitionCanvas', None)
    text = add(bp, u.TextBlock, 'TransitionStatus', root, True)
    font_asset = asset('/Game/Environment/Font/HSBombaram3_0_Regular_Font')
    properties(text, text=u.Text(''), font=u.SlateFontInfo(font_object=font_asset, size=22),
               color_and_opacity=u.SlateColor(specified_color=u.LinearColor(.8, .9, 1., 1.)))
    slot = text.get_editor_property('slot')
    properties(slot, layout_data=u.AnchorData(anchors=u.Anchors(minimum=u.Vector2D(1, 1), maximum=u.Vector2D(1, 1)),
        offsets=u.Margin(-56, -48, 360, 40), alignment=u.Vector2D(1, 1)))
    spinner = add(bp, u.Throbber, 'SavingSpinner', root, True)
    properties(spinner, visibility=u.SlateVisibility.COLLAPSED, number_of_pieces=3)
    properties(spinner.get_editor_property('slot'), layout_data=u.AnchorData(
        anchors=u.Anchors(minimum=u.Vector2D(1, 1), maximum=u.Vector2D(1, 1)),
        offsets=u.Margin(-430, -48, 64, 36), alignment=u.Vector2D(1, 1)))
    strict(bp)
    graph = BP.add_function_graph(bp, 'UpdateStatus')
    BP.add_function_param(graph, 'bSavePending', 'bool', True)
    BP.add_function_param(graph, 'Status', 'text', True)
    q = Graph(graph, 320, 0)
    event = q.e.find_graph_entry_pin().get_owning_node()
    label = q.fn('/Script/UMG.TextBlock:SetText', target=q.ref('TransitionStatus'), InText=(event, 'Status'))
    branch = q.branch((event, 'bSavePending'))
    show = q.fn('/Script/UMG.Widget:SetVisibility', target=q.ref('SavingSpinner'), InVisibility='HitTestInvisible')
    hide = q.fn('/Script/UMG.Widget:SetVisibility', target=q.ref('SavingSpinner'), InVisibility='Collapsed')
    wire(event, 'then', label, 'execute'); q.chain(label, branch)
    wire(branch, 'then', show, 'execute'); wire(branch, 'else', hide, 'execute')
    q.comment('Saving spinner follows actual native asynchronous I/O pending state only.')
    strict(bp)
    return bp


def key(channel, frame, value):
    whole = math.floor(frame)
    channel.add_key(u.FrameNumber(whole), value, frame - whole, DISPLAY, LINEAR)


def transform_track(binding, defaults, keys=None):
    section = binding.add_track(u.MovieScene3DTransformTrack).add_section()
    section.set_range(0, FADE_END)
    section.set_completion_mode(u.MovieSceneCompletionMode.KEEP_STATE)
    channels = section.get_channels_by_type(u.MovieSceneScriptingDoubleChannel)
    assert len(channels) >= 9
    for channel, value in zip(channels, defaults):
        channel.set_default(value)
    for index, entries in (keys or {}).items():
        for frame, value in entries:
            key(channels[index], frame, value)
    return section


def author_sequence(cat, portal):
    seq = new_asset(SEQUENCE, u.LevelSequence, u.LevelSequenceFactoryNew())
    seq.set_display_rate(u.FrameRate(FPS, 1)); seq.set_tick_resolution_directly(u.FrameRate(TICK_RATE, 1))
    seq.set_playback_start(0); seq.set_playback_end(FADE_END)
    cat_binding = seq.add_possessable(cat); cat_binding.tag_binding('CatrunCat')
    portal_binding = seq.add_possessable(portal); portal_binding.tag_binding('CatrunPortal')
    # The character's actor transform is intentionally authored in Sequencer.
    # Root review/native adapter resolves arrival-offset binding before Play.
    cat_transform = transform_track(cat_binding, [*START, 0., 0., -90., 1., 1., 1.], {
        1: [(0, START[1]), (WALK_END, INSPECT[1] + 8), (WALK_END + 19.2, INSPECT[1]),
            (JUMP_LIFT, INSPECT[1]), (JUMP_END, ENTRY[1]), (FADE_END, ENTRY[1])],
        2: [(0, START[2]), (JUMP_LIFT, INSPECT[2])] +
           [(JUMP_LIFT + (JUMP_END-JUMP_LIFT)*i/24,
             INSPECT[2]+14*math.sin(math.pi*.5*i/24)) for i in range(1, 25)] + [(FADE_END, ENTRY[2])]})
    u.MovieSceneSectionEasingExtensions.set_ease_in_duration(cat_transform, 19200)
    track = cat_binding.add_track(u.MovieSceneSkeletalAnimationTrack)
    for first, last, clip, rate, offset in ((0, WALK_END, CLIPS[0], 1., 0),
            (WALK_END, INSPECT_END, CLIPS[1], 1., 0), (INSPECT_END, JUMP_END, CLIPS[2], 1., 0),
            (JUMP_END, FADE_END, CLIPS[2], 0., 28799)):
        section = track.add_section(); section.set_range(first, last)
        params = u.MovieSceneSkeletalAnimationParams()
        params.set_editor_property('animation', asset(clip))
        params.set_editor_property('play_rate', u.MovieSceneTimeWarpExtensions.make_time_warp(rate))
        params.set_editor_property('force_custom_mode', True); params.set_editor_property('skip_anim_notifiers', True)
        params.set_editor_property('first_loop_start_frame_offset', u.FrameNumber(offset))
        section.set_editor_property('params', params)
        section.set_completion_mode(u.MovieSceneCompletionMode.RESTORE_STATE)
    cameras = []
    for name, location, rotation, fov, movement in (
        ('Front_BackwardTracking', (101., -175., 42.), (-7., 90., 0.), 55., {1: [(0, -175.), (WALK_END, -285.)]}),
        ('Face_BlueInspection', (108., -285., 37.), (-5., 101.3, 0.), 42., None),
        ('Rear_PortalJump', (101., -5., 105.), (-1., -90., 0.), 75., None)):
        binding = seq.add_spawnable_from_class(u.CameraActor.static_class())
        binding.set_name(name)
        template = binding.get_object_template(); assert template
        camera = template.get_editor_property('CameraComponent'); assert camera
        camera.set_field_of_view(fov)
        spawn_tracks = binding.find_tracks_by_type(u.MovieSceneSpawnTrack)
        assert len(spawn_tracks) == 1
        spawn = spawn_tracks[0].get_sections()[0]; spawn.set_range(0, FADE_END)
        spawn.get_channels_by_type(u.MovieSceneScriptingBoolChannel)[0].set_default(True)
        spawn.set_completion_mode(u.MovieSceneCompletionMode.RESTORE_STATE)
        pitch, yaw, roll = rotation
        transform_track(binding, [*location, roll, pitch, yaw, 1., 1., 1.], movement)
        cameras.append(binding)
    cuts = seq.add_track(u.MovieSceneCameraCutTrack)
    for first, last, camera in zip((0, WALK_END, INSPECT_END), (WALK_END, INSPECT_END, FADE_END), cameras):
        section = cuts.add_section(); section.set_range(first, last)
        section.set_camera_binding_id(seq.get_binding_id(camera))
        section.set_completion_mode(u.MovieSceneCompletionMode.KEEP_STATE)
    light_binding = seq.add_possessable(component_named(portal, 'BlueLight')); light_binding.set_parent(portal_binding)
    light_track = light_binding.add_track(u.MovieSceneFloatTrack)
    light_track.set_property_name_and_path('Intensity', 'Intensity')
    light_section = light_track.add_section(); light_section.set_range(0, FADE_END)
    channel = light_section.get_channels_by_type(u.MovieSceneScriptingFloatChannel)[0]
    channel.set_default(0.)
    for frame, value in ((0, 0.), (45, 0.), (WALK_END, 650.), (WALK_END + 30, 1200.), (FADE_END, 1200.)):
        key(channel, frame, value)
    light_section.set_completion_mode(u.MovieSceneCompletionMode.RESTORE_STATE)
    fade = seq.add_track(u.MovieSceneFadeTrack).add_section(); fade.set_range(JUMP_END, FADE_END)
    fade.set_completion_mode(u.MovieSceneCompletionMode.KEEP_STATE)
    channel = fade.get_channels_by_type(u.MovieSceneScriptingFloatChannel)[0]
    channel.set_default(0.); key(channel, JUMP_END, 0.); key(channel, FADE_END - 1, 1.)
    return seq


def action(q, search, predicate, declaring_class=None):
    """Resolve the installed editor's real action ID; never guess a K2 node ID."""
    candidates = sorted(set(BP.find_node_types(q.g, search)))
    matches = [name for name in candidates if predicate(re.sub(r'[^a-z0-9]', '', name.lower()))]
    assert len(matches) == 1, ('Ambiguous/missing editor action', search, candidates, matches)
    return q.placed(BP.create_node(q.g, matches[0], u.IntPoint(q.x, q.y), declaring_class))


def call_event(q, name):
    return q.fn(DIRECTOR + '.' + DIRECTOR.rsplit('/', 1)[1] + '_C:' + name)


def author_director(overlay):
    folder, name = DIRECTOR.rsplit('/', 1)
    bp = BP.create(folder, name, u.CatrunStageExit.static_class())
    for name, cls in (('CinematicActor', u.LevelSequenceActor), ('PortalPresentation', u.Actor),
                      ('Cat', u.Pawn), ('SequencePlayer', u.LevelSequencePlayer),
                      ('OwningController', u.PlayerController)):
        BP.add_object_variable(bp, name, cls.static_class())
    BP.add_object_variable(bp, 'TransitionOverlay', overlay.generated_class())
    for name, typ in (('Playing', 'bool'), ('WaitingForSave', 'bool'), ('TravelPending', 'bool'), ('OwnPresentation', 'bool'),
                      ('PreviousPosition', 'Vector'), ('ArrivalPosition', 'Vector'),
                      ('CinematicTimeout', 'float'), ('SaveTimeout', 'float'), ('TravelTimeout', 'float')):
        BP.add_variable(bp, name, typ)
    for name in ('CinematicActor', 'PortalPresentation', 'CinematicTimeout', 'SaveTimeout', 'TravelTimeout'):
        BP.set_variable_instance_editable(bp, name, True)
    strict(bp)
    cdo = u.get_default_object(bp.generated_class())
    for name, value in (('CinematicTimeout', 20.), ('SaveTimeout', 8.), ('TravelTimeout', 3.)):
        cdo.set_editor_property(name, value)
    cdo.set_editor_property('bRequireCenterInside', True)
    cdo.set_editor_property('bUseExitTransition', True)
    cdo.set_editor_property('InteriorDirectionLocal', u.Vector(0, -1, 0))
    cdo.set_editor_property('MinimumInteriorDepth', 0.)
    tick = cdo.get_editor_property('primary_actor_tick')
    tick.set_editor_property('tick_group', u.TickingGroup.TG_POST_UPDATE_WORK)
    cdo.set_editor_property('primary_actor_tick', tick)
    graph = BP.get_graph(bp, 'EventGraph')
    events = {}
    for i, name in enumerate(('BeginPortalPresentation', 'SequenceFinished', 'ExitCheckpointSaveFinished',
                              'ExitTravelFailed', 'AbortPortal', 'CinematicExpired', 'SaveExpired',
                              'TravelExpired', 'ReceiveTick', 'ReceiveEndPlay')):
        events[name] = BP.add_event(bp, name, u.IntPoint(0, i * 900))
    strict(bp)  # custom events become callable before authoring their call sites
    native = '/Script/Catrun.CatrunExitTransitionComponent:'
    player = '/Script/MovieScene.MovieSceneSequencePlayer:'
    actor = '/Script/Engine.Actor:'
    system = '/Script/Engine.KismetSystemLibrary:'
    gameplay = '/Script/Engine.GameplayStatics:'

    def adapter(q, fn, **pins):
        return q.fn(native + fn, target=q.ref('ExitTransition'), **pins)

    def seq(q, fn, **pins):
        return q.fn(player + fn, target=q.ref('SequencePlayer'), **pins)

    def timer(q, function, timeout):
        return q.fn(system + 'K2_SetTimer', FunctionName=function, Time=q.ref(timeout), bLooping='false')

    def clear_timer(q, function):
        return q.fn(system + 'K2_ClearTimer', FunctionName=function)

    def update(q, pending, status):
        return q.fn(OVERLAY + '.WBP_ExitTransition_C:UpdateStatus', target=q.ref('TransitionOverlay'),
                    bSavePending=pending, Status=status)

    def release_before_despawn(q):
        valid = q.fn(system + 'IsValid', Object=q.ref('SequencePlayer'))
        first = q.branch((valid, 'ReturnValue'))
        camera = q.fn('/Script/LevelSequence.LevelSequencePlayer:GetActiveCameraComponent', target=q.ref('SequencePlayer'))
        valid_camera = q.fn(system + 'IsValid', Object=(camera, 'ReturnValue'))
        has_camera = q.branch((valid_camera, 'ReturnValue'))
        wire(first, 'then', has_camera, 'execute')
        owner = q.fn('/Script/Engine.ActorComponent:GetOwner', target=(camera, 'ReturnValue'))
        remember = adapter(q, 'RememberOwnedViewTarget', ViewTarget=(owner, 'ReturnValue'))
        wire(has_camera, 'then', remember, 'execute')
        release = adapter(q, 'ReleaseExitLease', bRestoreStart='true')
        q.chain(remember, release)
        wire(has_camera, 'else', release, 'execute')
        wire(first, 'else', release, 'execute')
        return first, release

    # Qualification -> acquire low-level lease -> real binding / ordinary Play.
    event = events['BeginPortalPresentation']; q = Graph(graph, 350, 0)
    valid = q.fn(system + 'IsValid', Object=q.ref('CinematicActor'))
    gate = q.branch((valid, 'ReturnValue')); wire(event, 'then', gate, 'execute')
    acquire = adapter(q, 'AcquireExitLease', Pawn=(event, 'Pawn'))
    wire(gate, 'then', acquire, 'execute')
    accepted = q.branch((acquire, 'ReturnValue')); q.chain(acquire, accepted)
    cat = q.set('Cat', source=(event, 'Pawn'))
    wire(accepted, 'then', cat, 'execute')
    location = q.fn(actor + 'K2_GetActorLocation', target=q.ref('Cat'))
    initial = q.set('ArrivalPosition', source=(location, 'ReturnValue'))
    previous = q.set('PreviousPosition', source=(location, 'ReturnValue'))
    controller = q.fn(gameplay + 'GetPlayerController', PlayerIndex='0')
    cache_pc = q.set('OwningController', source=(controller, 'ReturnValue'))
    get_player = q.fn('/Script/LevelSequence.LevelSequenceActor:GetSequencePlayer', target=q.ref('CinematicActor'))
    cache_player = q.set('SequencePlayer', source=(get_player, 'ReturnValue'))
    reset = q.fn('/Script/LevelSequence.LevelSequenceActor:ResetBindings', target=q.ref('CinematicActor'))
    bind_cat = q.fn('/Script/LevelSequence.LevelSequenceActor:AddBindingByTag', target=q.ref('CinematicActor'),
                    BindingTag='CatrunCat', Actor=q.ref('Cat'), bAllowBindingsFromAsset='false')
    bind_portal = q.fn('/Script/LevelSequence.LevelSequenceActor:AddBindingByTag', target=q.ref('CinematicActor'),
                       BindingTag='CatrunPortal', Actor=q.ref('PortalPresentation'), bAllowBindingsFromAsset='false')
    bind_finish = action(q, 'OnFinished', lambda s: s == 'sequencerplayerbindeventtoonfinished',
                         u.MovieSceneSequencePlayer.static_class())
    wire(*q.ref('SequencePlayer'), bind_finish, 'self')
    wire(events['SequenceFinished'], 'OutputDelegate', bind_finish, 'Delegate')
    active = q.set('Playing', value='true')
    own = q.set('OwnPresentation', value='true')
    watch = timer(q, 'CinematicExpired', 'CinematicTimeout')
    play = seq(q, 'Play')
    q.chain(cat, initial, previous, cache_pc, cache_player, reset, bind_cat, bind_portal, bind_finish, active, own, watch, play)
    # Invalid configuration/acquisition never starts the sequence; no disabled-input residue.
    failed = call_event(q, 'AbortPortal'); wire(gate, 'else', failed, 'execute'); wire(accepted, 'else', failed, 'execute')
    q.comment('Blueprint owns qualification response, resources, binding and normal Sequence Play. No native cinematic clock.')

    # The sequence itself fades to black and pauses at its final evaluated frame.
    event = events['SequenceFinished']; q = Graph(graph, 350, 900)
    gate = q.branch(q.ref('Playing')); wire(event, 'then', gate, 'execute')
    last_location = q.fn(actor + 'K2_GetActorLocation', target=q.ref('Cat'))
    final_check = adapter(q, 'ValidateExitMotion', From=q.ref('PreviousPosition'),
                          To=(last_location, 'ReturnValue'), bGrounded='false')
    final_clear = q.branch((final_check, 'ReturnValue')); wire(gate, 'then', final_clear, 'execute')
    failed_final = call_event(q, 'AbortPortal'); wire(final_clear, 'else', failed_final, 'execute')
    inactive = q.set('Playing', value='false'); wire(final_clear, 'then', inactive, 'execute')
    clear = clear_timer(q, 'CinematicExpired')
    create = action(q, 'CreateWidget', lambda s: s.endswith('createwidget'))
    literal(create, 'Class', overlay.generated_class().get_path_name())
    wire(*q.ref('OwningController'), create, 'OwningPlayer')
    cache = q.set('TransitionOverlay', source=(create, 'ReturnValue'))
    visibility = q.fn('/Script/UMG.Widget:SetVisibility', target=q.ref('TransitionOverlay'), InVisibility='HitTestInvisible')
    viewport = q.fn('/Script/UMG.UserWidget:AddToViewport', target=q.ref('TransitionOverlay'), ZOrder='500')
    neutral = update(q, 'false', '장면 전환 중…')
    waiting = q.set('WaitingForSave', value='true')
    watch = timer(q, 'SaveExpired', 'SaveTimeout')
    request = adapter(q, 'RequestExitCheckpointSave')
    q.chain(inactive, clear, create, cache, visibility, viewport, neutral, waiting, watch, request)
    accepted = q.branch((request, 'ReturnValue')); q.chain(request, accepted)
    pending = adapter(q, 'IsCheckpointSavePending')
    pending_gate = q.branch((pending, 'ReturnValue')); wire(accepted, 'then', pending_gate, 'execute')
    saving = update(q, 'true', '저장 중…'); wire(pending_gate, 'then', saving, 'execute')
    failure = call_event(q, 'AbortPortal'); wire(accepted, 'else', failure, 'execute')
    q.comment('OnFinished fires with PauseAtEnd. Final pose/camera/black remain while actual checkpoint I/O runs.')

    event = events['ExitCheckpointSaveFinished']; q = Graph(graph, 350, 1800)
    gate = q.branch(q.ref('WaitingForSave')); wire(event, 'then', gate, 'execute')
    waiting = q.set('WaitingForSave', value='false'); wire(gate, 'then', waiting, 'execute')
    clear = clear_timer(q, 'SaveExpired')
    status = update(q, 'false', (event, 'Status'))
    success = q.branch((event, 'bSuccess')); q.chain(waiting, clear, status, success)
    pending = q.set('TravelPending', value='true'); wire(success, 'then', pending, 'execute')
    watch = timer(q, 'TravelExpired', 'TravelTimeout')
    commit = adapter(q, 'CommitExitTravel'); q.chain(pending, watch, commit)
    committed = q.branch((commit, 'ReturnValue')); q.chain(commit, committed)
    failure = call_event(q, 'AbortPortal'); wire(success, 'else', failure, 'execute'); wire(committed, 'else', failure, 'execute')
    q.comment('Only successful actual save completion authorizes owner-matched travel; destination arrival owns next checkpoint.')

    # Late timers/callbacks cannot replay a canceled or completed Blueprint run.
    for i, (event_name, flag) in enumerate((('CinematicExpired', 'Playing'), ('SaveExpired', 'WaitingForSave'),
                                          ('TravelExpired', 'TravelPending'))):
        q = Graph(graph, 350, 4500 + i * 900)
        gate = q.branch(q.ref(flag)); wire(events[event_name], 'then', gate, 'execute')
        abort = call_event(q, 'AbortPortal'); wire(gate, 'then', abort, 'execute')
    q = Graph(graph, 350, 2700)
    abort = call_event(q, 'AbortPortal'); wire(events['ExitTravelFailed'], 'then', abort, 'execute')

    # Actor tick contains no timeline/elapsed choreography. Queries only while playing.
    event = events['ReceiveTick']; q = Graph(graph, 350, 7200)
    gate = q.branch(q.ref('Playing')); wire(event, 'then', gate, 'execute')
    camera = q.fn('/Script/LevelSequence.LevelSequencePlayer:GetActiveCameraComponent', target=q.ref('SequencePlayer'))
    view = q.fn('/Script/Engine.ActorComponent:GetOwner', target=(camera, 'ReturnValue'))
    remember = adapter(q, 'RememberOwnedViewTarget', ViewTarget=(view, 'ReturnValue'))
    camera_valid = q.fn(system + 'IsValid', Object=(camera, 'ReturnValue'))
    camera_gate = q.branch((camera_valid, 'ReturnValue'))
    wire(gate, 'then', camera_gate, 'execute'); wire(camera_gate, 'then', remember, 'execute')
    location = q.fn(actor + 'K2_GetActorLocation', target=q.ref('Cat'))
    difference = q.fn('/Script/Engine.KismetMathLibrary:Subtract_VectorVector', A=(location, 'ReturnValue'), B=q.ref('ArrivalPosition'))
    axes = q.fn('/Script/Engine.KismetMathLibrary:BreakVector', InVec=(difference, 'ReturnValue'))
    grounded = q.fn('/Script/Engine.KismetMathLibrary:LessEqual_DoubleDouble', A=(axes, 'Z'), B='2')
    validate = adapter(q, 'ValidateExitMotion', From=q.ref('PreviousPosition'), To=(location, 'ReturnValue'), bGrounded=(grounded, 'ReturnValue'))
    clear = q.branch((validate, 'ReturnValue')); q.chain(remember, clear)
    wire(camera_gate, 'else', clear, 'execute')
    previous = q.set('PreviousPosition', source=(location, 'ReturnValue')); wire(clear, 'then', previous, 'execute')
    abort = call_event(q, 'AbortPortal'); wire(clear, 'else', abort, 'execute')
    q.comment('PostUpdateWork guard checks previous to current sequenced capsule; no native or BP second movement clock.')

    # Stop only this sequence, remove only this overlay, release only this lease.
    event = events['AbortPortal']; q = Graph(graph, 350, 3600)
    inactive = q.set('Playing', value='false'); wire(event, 'then', inactive, 'execute')
    waiting = q.set('WaitingForSave', value='false'); travel = q.set('TravelPending', value='false')
    clear1 = clear_timer(q, 'CinematicExpired'); clear2 = clear_timer(q, 'SaveExpired'); clear3 = clear_timer(q, 'TravelExpired')
    q.chain(inactive, waiting, travel, clear1, clear2, clear3)
    release_start, release = release_before_despawn(q)
    q.chain(clear3, release_start)
    valid = q.fn(system + 'IsValid', Object=q.ref('SequencePlayer')); gate = q.branch((valid, 'ReturnValue'))
    q.chain(release, gate)
    stop = seq(q, 'Stop'); wire(gate, 'then', stop, 'execute')
    overlay_valid = q.fn(system + 'IsValid', Object=q.ref('TransitionOverlay'))
    overlay_gate = q.branch((overlay_valid, 'ReturnValue'))
    wire(stop, 'then', overlay_gate, 'execute'); wire(gate, 'else', overlay_gate, 'execute')
    remove = q.fn('/Script/UMG.Widget:RemoveFromParent', target=q.ref('TransitionOverlay'))
    wire(overlay_gate, 'then', remove, 'execute')
    owns = q.branch(q.ref('OwnPresentation'))
    wire(remove, 'then', owns, 'execute'); wire(overlay_gate, 'else', owns, 'execute')
    pcm = q.fn(gameplay + 'GetPlayerCameraManager', PlayerIndex='0')
    fade = q.fn('/Script/Engine.PlayerCameraManager:StopCameraFade', target=(pcm, 'ReturnValue'))
    wire(owns, 'then', fade, 'execute')
    disown = q.set('OwnPresentation', value='false'); q.chain(fade, disown)
    notice_text = q.fn('/Script/Engine.KismetTextLibrary:Conv_StringToText',
                       InString='이동을 마치지 못했어요. 문에서 나왔다가 다시 시도해 주세요.')
    notice = q.fn('/Script/Catrun.CatrunNoticeLibrary:ShowBottomNotice',
                  Text=(notice_text, 'ReturnValue'), Duration='3')
    q.chain(disown, notice); wire(owns, 'else', notice, 'execute')
    q.comment('Abort is explicit Blueprint cleanup; native adapter provides collision-safe recovery and balanced owned resource release.')

    # World destruction must not restore pawn/camera into a dying world or cancel accepted travel.
    event = events['ReceiveEndPlay']; q = Graph(graph, 350, 8100)
    inactive = q.set('Playing', value='false'); wire(event, 'then', inactive, 'execute')
    waiting = q.set('WaitingForSave', value='false')
    clears = [clear_timer(q, name) for name in ('CinematicExpired', 'SaveExpired', 'TravelExpired')]
    q.chain(inactive, waiting, *clears)
    destroyed = q.fn('/Script/Engine.KismetMathLibrary:EqualEqual_ByteByte', A=(event, 'EndPlayReason'), B='0')
    removed = q.fn('/Script/Engine.KismetMathLibrary:EqualEqual_ByteByte', A=(event, 'EndPlayReason'), B='3')
    live_reason = q.fn('/Script/Engine.KismetMathLibrary:BooleanOR', A=(destroyed, 'ReturnValue'), B=(removed, 'ReturnValue'))
    live_end = q.branch((live_reason, 'ReturnValue')); q.chain(clears[-1], live_end)
    release_start, release = release_before_despawn(q)
    wire(live_end, 'then', release_start, 'execute')
    valid = q.fn(system + 'IsValid', Object=q.ref('SequencePlayer')); gate = q.branch((valid, 'ReturnValue'))
    wire(live_end, 'else', gate, 'execute'); q.chain(release, gate)
    stop = seq(q, 'Stop'); wire(gate, 'then', stop, 'execute')
    valid_overlay = q.fn(system + 'IsValid', Object=q.ref('TransitionOverlay'))
    overlay_gate = q.branch((valid_overlay, 'ReturnValue'))
    wire(stop, 'then', overlay_gate, 'execute'); wire(gate, 'else', overlay_gate, 'execute')
    remove = q.fn('/Script/UMG.Widget:RemoveFromParent', target=q.ref('TransitionOverlay'))
    wire(overlay_gate, 'then', remove, 'execute')
    changing_level = q.fn('/Script/Engine.KismetMathLibrary:EqualEqual_ByteByte',
                         A=(event, 'EndPlayReason'), B='1')  # EEndPlayReason::LevelTransition
    accepted_teardown = q.fn('/Script/Engine.KismetMathLibrary:BooleanAND',
                            A=q.ref('TravelPending'), B=(changing_level, 'ReturnValue'))
    travel = q.branch((accepted_teardown, 'ReturnValue'))
    wire(remove, 'then', travel, 'execute'); wire(overlay_gate, 'else', travel, 'execute')
    own = q.branch(q.ref('OwnPresentation')); wire(travel, 'else', own, 'execute')
    pcm = q.fn(gameplay + 'GetPlayerCameraManager', PlayerIndex='0')
    fade = q.fn('/Script/Engine.PlayerCameraManager:StopCameraFade', target=(pcm, 'ReturnValue'))
    wire(own, 'then', fade, 'execute')
    q.comment('EndPlay stops owned presentation and overlay; component EndPlay owns lease teardown. Accepted travel keeps blackout.')
    strict(bp)
    return bp


def graph_audit(bp):
    rows = []
    for graph in BP.list_graphs(bp):
        rows.append({'graph': graph.get_name(), 'nodes': [
            {'name': n.node.get_name(), 'type': n.type_id,
             'inputs': [{'name': p.name, 'value': str(p.value), 'links': str(p.connected_pins)} for p in n.input_pins],
             'outputs': [{'name': p.name, 'links': str(p.connected_pins)} for p in n.output_pins]}
            for n in BP.get_node_infos(BP.find_nodes(graph))]})
    return rows


def asset_audit():
    seq, presentation, director, overlay, material = [asset(p) for p in OWNED]
    assert seq.get_display_rate().numerator == FPS and seq.get_tick_resolution().numerator == TICK_RATE
    assert seq.get_playback_start() == 0 and seq.get_playback_end() == FADE_END
    result = {'sequence': {'bindings': [], 'global_tracks': []}, 'blueprints': {}}

    def track_row(track):
        row = {'class': track.get_class().get_name(), 'sections': []}
        for section in track.get_sections():
            s = {'start': section.get_start_frame(), 'end': section.get_end_frame(),
                 'completion': str(section.get_completion_mode()), 'channels': []}
            if isinstance(section, u.MovieSceneSkeletalAnimationSection):
                p = section.get_editor_property('params')
                s['animation'] = path(p.get_editor_property('animation'))
                s['params'] = {'time_warp': p.get_editor_property('play_rate').export_text(),
                    'first_loop_offset': p.get_editor_property('first_loop_start_frame_offset').value,
                    'force_custom_mode': p.get_editor_property('force_custom_mode'),
                    'skip_anim_notifiers': p.get_editor_property('skip_anim_notifiers')}
            if isinstance(section, u.MovieSceneCameraCutSection):
                s['camera'] = section.get_camera_binding_id().export_text()
            for channel in section.get_all_channels():
                keys = channel.get_keys()
                s['channels'].append({'name': str(channel.get_editor_property('channel_name')),
                    'default': str(channel.get_default()),
                    'keys': [{'frame': k.get_time(TICKS).export_text(), 'value': str(k.get_value())} for k in keys]})
            row['sections'].append(s)
        return row

    bindings = list(seq.get_bindings())
    cats = [b for b in bindings if 'CatrunCat' in [str(t) for t in b.get_binding_tags()]]
    portals = [b for b in bindings if 'CatrunPortal' in [str(t) for t in b.get_binding_tags()]]
    assert len(cats) == len(portals) == 1
    cat_tracks = cats[0].get_tracks()
    assert len([t for t in cat_tracks if isinstance(t, u.MovieScene3DTransformTrack)]) == 1
    anim_tracks = [t for t in cat_tracks if isinstance(t, u.MovieSceneSkeletalAnimationTrack)]
    assert len(anim_tracks) == 1 and len(anim_tracks[0].get_sections()) == 4
    for binding in bindings:
        result['sequence']['bindings'].append({'name': binding.get_name(), 'id': binding.get_id().export_text(),
            'tags': [str(t) for t in binding.get_binding_tags()], 'parent': binding.get_parent().get_id().export_text(),
            'template': path(binding.get_object_template()), 'tracks': [track_row(t) for t in binding.get_tracks()]})
    result['sequence']['global_tracks'] = [track_row(t) for t in seq.get_tracks()]
    globals_types = [r['class'] for r in result['sequence']['global_tracks']]
    assert 'MovieSceneCameraCutTrack' in globals_types and 'MovieSceneFadeTrack' in globals_types
    for bp in (presentation, director, overlay):
        assert bp.get_editor_property('status') == u.BlueprintStatus.BS_UP_TO_DATE
        result['blueprints'][path(bp)] = {'status': str(bp.get_editor_property('status')), 'graphs': graph_audit(bp)}
    result['widget'] = widget_audit(overlay)
    # Struct repr contains a process-local address. Export the actual reflected
    # value so fresh-process comparison still detects font and GUID changes.
    overlay_widgets = widgets(overlay)
    for row in result['widget']['widgets']:
        if 'font' in row:
            row['font'] = overlay_widgets[row['name']].get_editor_property('font').export_text()
    text = json.dumps(result['blueprints'][path(director)], ensure_ascii=False)
    assert 'SetPlaybackPosition' not in text and 'BeginTransition' not in text
    for token in ('Play', 'SequenceFinished', 'RequestExitCheckpointSave', 'CommitExitTravel', 'AbortPortal', 'ValidateExitMotion'):
        assert token in text, ('Missing Blueprint lifecycle node', token)
    result['presentation'] = {c.get_name(): str(ObjectTools.get_properties(c, [])) for c in components(presentation) if c}
    assert component_named(presentation, 'Surface').get_collision_enabled() == u.CollisionEnabled.NO_COLLISION
    assert component_named(presentation, 'Runes').get_collision_enabled() == u.CollisionEnabled.NO_COLLISION
    assert material.get_editor_property('two_sided')
    return result


def stable_snapshot(actors, exclude):
    """Same-process guard for all unrelated saved actor/component configuration."""
    result = {}
    for actor in actors:
        if actor.get_name() in exclude:
            continue
        transform = actor.get_actor_transform()
        row = {'class': path(actor.get_class()), 'label': actor.get_actor_label(),
               'transform': {'location': v(transform.translation), 'scale': v(transform.scale3d),
                             'rotation': [float(getattr(transform.rotation, n)) for n in ('x', 'y', 'z', 'w')]},
               'tags': [str(t) for t in actor.tags],
               'properties': str(ObjectTools.get_properties(actor, [])), 'components': {}}
        for component in actor.get_components_by_class(u.ActorComponent):
            row['components'][component.get_name()] = str(ObjectTools.get_properties(component, []))
        result[actor.get_name()] = row
    return result


def find_cat(actors):
    candidates = [a for a in actors if isinstance(a, u.Character) and a.get_name() == 'BP_Cat_C_0']
    assert len(candidates) == 1, ('Expected one saved cat', [path(a) for a in candidates])
    cat = candidates[0]
    capsule = cat.get_component_by_class(u.CapsuleComponent)
    assert abs(capsule.get_scaled_capsule_radius() - 20) < .01
    assert abs(capsule.get_scaled_capsule_half_height() - 24) < .01
    assert all(abs(x - 1) < .001 for x in v(cat.get_actor_scale3d())), 'Sequence preserves current unit actor scale'
    return cat


def verify_clips(cat):
    mesh = cat.get_component_by_class(u.SkeletalMeshComponent).get_skeletal_mesh_asset()
    skeleton = mesh.get_editor_property('skeleton')
    result = []
    for package in CLIPS:
        clip = asset(package)
        assert clip.get_editor_property('skeleton') == skeleton
        assert not clip.get_editor_property('enable_root_motion')
        length = clip.get_editor_property('sequence_length')
        zero = u.AnimationLibrary.extract_root_track_transform(clip, 0.)
        largest_translation, largest_rotation = 0., 0.
        for sample in range(math.ceil(length * 60) + 1):
            pose = u.AnimationLibrary.extract_root_track_transform(clip, min(sample / 60., length))
            delta = pose.translation - zero.translation
            largest_translation = max(largest_translation, math.sqrt(delta.x**2 + delta.y**2 + delta.z**2))
            dot = sum(getattr(pose.rotation, k) * getattr(zero.rotation, k) for k in ('x', 'y', 'z', 'w'))
            largest_rotation = max(largest_rotation, 1 - abs(dot))
        assert largest_translation <= .05 and largest_rotation <= .001, ('Root-moving source clip', package)
        result.append({'asset': package, 'length': length, 'skeleton': path(skeleton),
                       'max_root_translation': largest_translation, 'max_quaternion_delta': largest_rotation})
    return result


def authored_position(frame, arrival=START):
    if frame <= WALK_END:
        target_y = START[1] + (INSPECT[1] + 8 - START[1]) * frame / WALK_END
    elif frame < WALK_END + 19.2:
        target_y = INSPECT[1] + 8 * (1 - (frame - WALK_END) / 19.2)
    elif frame <= JUMP_LIFT:
        target_y = INSPECT[1]
    else:
        fraction = min(1., (frame - JUMP_LIFT) / (JUMP_END - JUMP_LIFT))
        target_y = INSPECT[1] + (ENTRY[1] - INSPECT[1]) * fraction
    z = INSPECT[2] if frame <= JUMP_LIFT else INSPECT[2] + 14 * math.sin(
        math.pi * .5 * min(1., (frame - JUMP_LIFT) / (JUMP_END - JUMP_LIFT)))
    if frame >= 24:
        return u.Vector(101, target_y, z)
    alpha = max(0., frame / 24.)
    weight = 4*alpha**3 if alpha < .5 else 1 - ((-2*alpha+2)**3)/2
    return u.Vector(arrival[0] * (1-weight) + 101*weight,
                    arrival[1] * (1-weight) + target_y*weight,
                    arrival[2] * (1-weight) + z*weight)


def geometry(world, cat, director):
    """Real saved-world capsule queries, including every qualified XY corner."""
    ignore = [cat, director]
    capsule = cat.get_component_by_class(u.CapsuleComponent)
    radius, half = capsule.get_scaled_capsule_radius(), capsule.get_scaled_capsule_half_height()
    pawn, block = u.CollisionChannel.ECC_PAWN, u.CollisionResponseType.ECR_BLOCK
    channels = [getattr(u.CollisionChannel, 'ECC_' + n) for n in
                ('WORLD_STATIC', 'WORLD_DYNAMIC', 'PAWN', 'PHYSICS_BODY', 'VEHICLE', 'DESTRUCTIBLE')]
    assert str(capsule.get_collision_profile_name()) == 'Pawn' and capsule.get_collision_object_type() == pawn \
        and all(capsule.get_collision_response_to_channel(c) == block for c in channels), \
        'Pawn-profile query differs from actual capsule; native custom-response query required'
    assert abs(capsule.get_up_vector().z) >= .99, 'Ground support requires an upright capsule'
    movement = cat.get_component_by_class(u.CharacterMovementComponent)
    step = max(0., movement.get_editor_property('max_step_height'))
    tolerance = director.get_component_by_class(u.CatrunExitTransitionComponent).get_editor_property('GroundTolerance')
    walkable_z = movement.get_walkable_floor_z()
    object_types = [getattr(u.ObjectTypeQuery, 'OBJECT_TYPE_QUERY' + str(i)) for i in range(1, 7)]
    count = 0
    floors, support_centers, grounded_deltas = [], [], []
    support_count = 0

    def hit_row(hit):
        def encode(value):
            if isinstance(value, u.Vector):
                return v(value)
            if isinstance(value, u.Object):
                return path(value)
            return value if value is None or isinstance(value, (str, int, float, bool)) else str(value)
        return {k: encode(value) for k, value in hit.to_dict().items()} if hit else None

    def fail(reason, context, **details):
        REPORT['geometry_failure'] = dict(context, reason=reason, **details)
        persist('geometry_failure')
        raise AssertionError(REPORT['geometry_failure'])

    def supported(point, context):
        # Match CatrunGround::FindSupport and ExitTransition::FindGround:
        # sweep the actual capsule within the movement step window, not rays
        # against decorative triangles or a fixed global floor elevation.
        nonlocal count, support_count
        top, bottom = point + u.Vector(0, 0, step), point - u.Vector(0, 0, step + tolerance)
        hit = u.SystemLibrary.capsule_trace_single_by_profile(world, top, bottom, radius, half,
                                                              'Pawn', False, ignore, NONE, False)
        count += 1
        detail = {'reference': v(point), 'probe_start': v(top), 'probe_end': v(bottom), 'hit': hit_row(hit)}
        if not hit:
            fail('Missing capsule ground support', context, **detail)
        data = hit.to_dict()
        if not data['blocking_hit'] or data['initial_overlap'] or isinstance(data['hit_actor'], u.Pawn) \
                or data['impact_normal'].z < max(.65, walkable_z):
            fail('Invalid blocking/walkable ground support', context, **detail)
        contact, center = data['impact_point'], data['location']
        if math.hypot(contact.x-center.x, contact.y-center.y) > max(0., radius-.15) \
                or center.z < bottom.z-.01 or center.z > top.z+.01:
            fail('Capsule ground support outside center/range limits', context, **detail)
        delta = abs(center.z + 2. - point.z)
        if delta > tolerance:
            fail('Grounded capsule does not follow support height', context,
                 support_center_z=center.z+2., height_delta=delta, tolerance=tolerance, **detail)
        support_count += 1
        floors.append(contact.z); support_centers.append(center.z+2.); grounded_deltas.append(delta)

    def fits(point, context):
        nonlocal count
        overlaps = u.SystemLibrary.capsule_overlap_components(world, point, radius, half,
                                                              object_types, u.PrimitiveComponent, ignore) or []
        count += 1
        blockers = [c for c in overlaps if c.get_collision_response_to_channel(pawn) == block
                    and capsule.get_collision_response_to_channel(c.get_collision_object_type()) == block]
        if blockers:
            fail('Capsule overlaps blocking geometry', context, reference=v(point),
                 blockers=[{'component': path(c), 'actor': path(c.get_owner())} for c in blockers])

    paths = []
    for x in (TRIGGER[0]-EXTENT[0], TRIGGER[0], TRIGGER[0]+EXTENT[0]):
        for y in (TRIGGER[1]-EXTENT[1], TRIGGER[1]):
            start = (x, y, INSPECT[2]); points = [(frame/2, authored_position(frame/2, start)) for frame in range(0, 49)]
            paths.append(('arrival:'+str(start), points))
    # Later path is common to every initial-value blend. Sub-display samples also
    # cover the authored airborne arc; all draws are disabled.
    paths.append(('centerline', [(frame/2, authored_position(frame/2)) for frame in range(48, int(JUMP_END*2)+1)]))
    for name, points in paths:
        last = points[0][1]
        for frame, point in points:
            context = {'world': path(world), 'path': name, 'frame': frame}
            # The saved BP keeps its grounded guard for the first 2 cm of lift.
            # Airborne motion then needs clearance, while abort recovery returns
            # to the supported/collision-free captured arrival checked above.
            if frame <= JUMP_LIFT or point.z - INSPECT[2] <= 2.:
                supported(point, context)
            fits(point, context)
            hit = u.SystemLibrary.capsule_trace_single_by_profile(world, last, point, radius, half,
                                                                  'Pawn', False, ignore, NONE, False)
            count += 1
            if hit:
                fail('Blocked sequenced capsule path', context, start=v(last), end=v(point), hit=hit_row(hit))
            last = point
    assert abs(authored_position(JUMP_CROSS).y - PLANE_Y) < .001
    return {'query_count': count, 'floor_min': min(floors), 'floor_max': max(floors),
            'support_query_count': support_count, 'support_center_min': min(support_centers),
            'support_center_max': max(support_centers), 'max_grounded_height_delta': max(grounded_deltas),
            'ground_policy': {'probe_up': step, 'probe_down': step+tolerance, 'tolerance': tolerance,
                              'walkable_normal_z': max(.65, walkable_z), 'capsule_profile': 'Pawn',
                              'lift_frame': JUMP_LIFT, 'bp_grounded_lift_height': 2.,
                              'recovery': 'supported and clear captured arrival; no airborne floor requirement'},
            'qualified_xy_corners': [[x, y] for x in (TRIGGER[0]-EXTENT[0], TRIGGER[0]+EXTENT[0])
                                     for y in (TRIGGER[1]-EXTENT[1], TRIGGER[1])],
            'frame_scale': .75, 'portal_plane_y': PLANE_Y, 'cross_position': v(authored_position(JUMP_CROSS)),
            'approach_from_actual_initial_value': True, 'query_clear': True}


def configure_map(world, actors, presentation_bp, director_bp, sequence, existing_portal=None):
    originals = [a for a in actors if isinstance(a, u.CatrunStageExit)]
    assert len(originals) == 1, ('Expected one old Stage1 exit', [path(a) for a in originals])
    old = originals[0]
    assert old.get_class() == u.CatrunStageExit.static_class(), 'Do not replace an existing custom exit Blueprint'
    portal = existing_portal or ACTORS.spawn_actor_from_class(presentation_bp.generated_class(), u.Vector(*PORTAL), u.Rotator(yaw=180))
    portal.set_actor_label('Stage1 Portal — Blue Stone Arch'); portal.set_editor_property('tags', [u.Name(PORTAL_TAG)])
    director = ACTORS.spawn_actor_from_class(director_bp.generated_class(), u.Vector(*TRIGGER), u.Rotator())
    director.set_actor_label('Stage1 Portal Exit — Blueprint Director')
    director.set_editor_property('tags', list(old.tags) + [u.Name(DIRECTOR_TAG)])
    director.get_editor_property('Trigger').set_box_extent(u.Vector(*EXTENT), False)
    cinematic = ACTORS.spawn_actor_from_class(u.LevelSequenceActor.static_class(), u.Vector(), u.Rotator())
    cinematic.set_actor_label('Stage1 Portal Exit — Editable Sequence')
    cinematic.set_editor_property('tags', [u.Name('CatrunAuthoredStage1Sequence')])
    cinematic.set_editor_property('level_sequence_asset', sequence)
    playback = cinematic.get_editor_property('playback_settings')
    playback.set_editor_property('auto_play', False); playback.set_editor_property('pause_at_end', True)
    cinematic.set_editor_property('playback_settings', playback)
    director.set_editor_property('CinematicActor', cinematic)
    director.set_editor_property('PortalPresentation', portal)
    assert ACTORS.destroy_actor(old)
    return director, portal, cinematic


def map_audit(world, actors):
    def tagged(tag):
        found = [a for a in actors if tag in [str(t) for t in a.tags]]
        assert len(found) == 1, (tag, [path(a) for a in found])
        return found[0]

    def require_transform(obj, location, quaternion):
        transform = obj.get_world_transform() if isinstance(obj, u.SceneComponent) else obj.get_actor_transform()
        actual_rotation = [float(getattr(transform.rotation, k)) for k in ('x', 'y', 'z', 'w')]
        actual = {'location': v(transform.translation), 'scale': v(transform.scale3d),
                  'quaternion': actual_rotation}
        # q and -q encode the same rotation; preserve numeric validation without
        # accepting a rotated/scaled actor for the fixed world-space path queries.
        rotation_error = min(sum((a-sign*b)**2 for a, b in zip(actual_rotation, quaternion))
                             for sign in (-1., 1.))
        assert all(abs(a-b) < .01 for a, b in zip(actual['location'], location)) \
            and all(abs(a-1.) < .001 for a in actual['scale']) and rotation_error < 1.e-8, \
            ('Authored object transform changed', path(obj), actual,
             {'location': list(location), 'scale': [1., 1., 1.], 'quaternion': list(quaternion)})

    director = tagged(DIRECTOR_TAG); portal = tagged(PORTAL_TAG); cinematic = tagged('CatrunAuthoredStage1Sequence')
    assert director.get_class() == asset(DIRECTOR).generated_class()
    assert portal.get_class() == asset(PRESENTATION).generated_class()
    assert cinematic.get_class() == u.LevelSequenceActor.static_class()
    assert director.get_editor_property('CinematicActor') == cinematic
    assert director.get_editor_property('PortalPresentation') == portal
    assert director.get_editor_property('bRequireCenterInside') and director.get_editor_property('bUseExitTransition')
    assert v(director.get_editor_property('InteriorDirectionLocal')) == [0., -1., 0.]
    assert abs(director.get_editor_property('MinimumInteriorDepth')) < .001
    require_transform(director, TRIGGER, (0., 0., 0., 1.))
    require_transform(director.get_editor_property('Trigger'), TRIGGER, (0., 0., 0., 1.))
    require_transform(portal, PORTAL, (0., 0., 1., 0.))
    require_transform(cinematic, (0., 0., 0.), (0., 0., 0., 1.))
    assert v(director.get_editor_property('Trigger').get_unscaled_box_extent()) == list(EXTENT)
    assert path(cinematic.get_editor_property('level_sequence_asset')) == SEQUENCE + '.LS_Stage1_PortalExit'
    playback = cinematic.get_editor_property('playback_settings')
    assert playback.get_editor_property('pause_at_end') and not playback.get_editor_property('auto_play')
    cat = find_cat(actors)
    return {'director': path(director), 'portal': path(portal), 'sequence_actor': path(cinematic),
            'trigger': v(director.get_actor_location()), 'extent': list(EXTENT),
            'geometry': geometry(world, cat, director), 'clips': verify_clips(cat)}


def main():
    assert '-catrungeometryisolated' in COMMAND.lower()
    assert AUDIT or '-catrunportalauthor' in COMMAND.lower()
    assert not ED.get_game_world() and not dirty(), ('Fresh isolated editor required', dirty())
    REPORT['cvars'] = {name: u.SystemLibrary.get_console_variable_int_value(name) for name in CVARS}
    assert all(value == 0 for value in REPORT['cvars'].values()), REPORT['cvars']
    REPORT['before_hashes'] = hashes()
    REPORT['protected_hashes'] = protected_hashes()
    persist('preflight')
    if AUDIT:
        match = re.search(r'-catrunPortalBaseline=(?:"([^"]+)"|(\S+))', COMMAND, re.I)
        assert match, 'Fresh audit requires the completed author report'
        baseline = json.loads(Path(match.group(1) or match.group(2)).read_text(encoding='utf-8'))
        assert baseline['completed'] and not baseline['audit_only'] and baseline['process_id'] != os.getpid()
        assert baseline['after_hashes'] == REPORT['before_hashes'], 'Asset bytes changed since author report'
        assert baseline['protected_hashes'] == REPORT['protected_hashes'], 'Unrelated package bytes changed'
        REPORT['asset_structure'] = asset_audit()
        assert REPORT['asset_structure'] == baseline['asset_structure'], 'Fresh loaded asset structure differs'
        for package in MAPS:
            world, actors = load(package)
            REPORT['maps'][package] = map_audit(world, actors)
            assert REPORT['maps'][package] == baseline['maps'][package]['authored'], ('Cold map mismatch', package)
            persist('audited:'+package)
        assert REPORT['before_hashes'] == hashes() and REPORT['protected_hashes'] == protected_hashes()
        assert not dirty(), ('Read-only audit dirtied packages', dirty())
    else:
        assert all(AS.does_asset_exist(p) == RESUME_MAPS for p in OWNED), 'Use explicit resume-maps only when all dedicated assets were already saved'
        backup()
        world, actors = load(MAPS[0])
        cat = find_cat(actors); REPORT['source_clips'] = verify_clips(cat)
        if RESUME_MAPS:
            sequence, presentation, director, overlay, material = [asset(p) for p in OWNED]
            portal = None
        else:
            material = author_surface(); presentation = author_presentation(material); overlay = author_widget()
            portal = ACTORS.spawn_actor_from_class(presentation.generated_class(), u.Vector(*PORTAL), u.Rotator(yaw=180))
            sequence = author_sequence(cat, portal)
            director = author_director(overlay)
        # Save only the five dedicated assets, after strict BP compilation and complete graph audit.
        REPORT['asset_structure'] = asset_audit()
        assert set(dirty()) <= set(OWNED) | {MAPS[0]}, ('Unexpected package mutation', dirty())
        if not RESUME_MAPS:
            for package in OWNED:
                assert AS.save_loaded_asset(asset(package), False)
                REPORT['saved'].append(package)
        for index, package in enumerate(MAPS):
            if index:
                world, actors = load(package)
            old_exits = [a for a in actors if isinstance(a, u.CatrunStageExit)]
            assert len(old_exits) == 1
            owned_tags = {DIRECTOR_TAG, PORTAL_TAG, 'CatrunAuthoredStage1Sequence'}
            owned_actors = [a for a in actors if owned_tags.intersection(str(t) for t in a.tags)]
            if RESUME_MAPS and owned_actors:
                # A previous run may have saved Stage1 before its mirror failed.
                # Reuse only our exact, complete, linked actor trio. Never delete
                # actors by broad class/tag or recreate an already saved director.
                assert len(owned_actors) == 3 and old_exits[0] in owned_actors, \
                    ('Incomplete or ambiguous previously authored portal', package, [path(a) for a in owned_actors])
                authored = map_audit(world, actors)
                before = stable_snapshot(actors, {a.get_name() for a in owned_actors})
                REPORT['maps'][package] = {'preserved_actor_count': len(before),
                    'preserved_snapshot_sha256': hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest(),
                    'authored': authored, 'reused_saved_map': True}
                assert not dirty(), ('Reused map audit must not mutate packages', dirty())
                persist('reused:'+package)
                continue
            before = stable_snapshot(actors, {old_exits[0].get_name()})
            new_director, new_portal, cinematic = configure_map(world, actors, presentation, director, sequence,
                                                               portal if index == 0 else None)
            after_actors = list(u.GameplayStatics.get_all_actors_of_class(world, u.Actor))
            after = stable_snapshot(after_actors, {new_director.get_name(), new_portal.get_name(), cinematic.get_name()})
            if before != after:
                REPORT['preservation_failure'] = {'package': package, 'before': before, 'after': after}
                persist('preservation_failure')
                raise AssertionError(('Unrelated actor/components changed', package))
            REPORT['maps'][package] = {'preserved_actor_count': len(before),
                'preserved_snapshot_sha256': hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest(),
                'authored': map_audit(world, after_actors)}
            assert set(dirty()) <= {package}, ('Unexpected dirty packages before map save', dirty())
            assert LEVEL.save_current_level()
            REPORT['saved'].append(package)
            assert not dirty()
            persist('saved:'+package)
        assert REPORT['protected_hashes'] == protected_hashes(), 'Unrelated source package bytes changed'
        REPORT['after_hashes'] = hashes()
    REPORT['completed'] = True
    REPORT['dirty_after'] = dirty()
    persist('audit_complete' if AUDIT else 'author_complete')
    print('CATRUN_PORTAL_AUDITED' if AUDIT else 'CATRUN_PORTAL_AUTHORED', str(OUT / 'report.json'))


try:
    main()
except Exception:
    REPORT['errors'].append(traceback.format_exc())
    REPORT['dirty_on_abort'] = dirty()
    persist('aborted_without_broad_save')
    print('CATRUN_PORTAL_ABORTED', str(OUT / 'report.json'))
    raise
