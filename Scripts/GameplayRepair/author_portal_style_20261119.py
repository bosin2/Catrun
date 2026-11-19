"""Author and cold-audit the shared cinematic portal surfaces and orbit cards.

Run in a fresh UE editor process with -catrunPortalStyle=author. Use
-catrunPortalStyle=energy to tune installed shared emissive defaults only. Use
-catrunPortalStyle=cold -catrunPortalStyleBaseline="<author report>" in a
separate process to read the saved assets and evaluate the arrival sequence.
"""

import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import traceback

import unreal as u
from editor_toolset.toolsets.actor import ActorTools


ROOT = Path(u.Paths.project_dir()).resolve()
sys.path[:0] = [str(ROOT / 'Scripts/GameplayRepair'), str(ROOT / 'Scripts/Menu')]
import portal_style_shader_20261119 as style
import stage2_arrival_shots as arrival
from menu_graph import compile_bp


STAGE1 = '/Game/Cinematics/Stage1/Portal/'
SHARED = STAGE1 + 'Followup20261112/'
STAGE2 = '/Game/Cinematics/Stage2/Arrival/'
BLUEPRINTS = (STAGE1 + 'BP_Stage1PortalPresentation', STAGE2 + 'BP_Stage2ArrivalPortal')
SEQUENCE = STAGE2 + 'LS_Stage2_PortalArrival'
MATERIALS = {
    style.SURFACE: STAGE1 + style.SURFACE,
    style.CORE: SHARED + style.CORE,
    style.HALO: SHARED + style.HALO,
}
SPARK_MATERIAL = SHARED + style.SPARK
SPARK_MESH = SHARED + 'SM_PortalOrbitSparks'
SPARK_COMPONENT = 'PortalOrbitSparks'
SITE_COMPONENTS = {'Surface': style.SURFACE, 'PortalDepthCore': style.CORE, 'PortalAetherHalo': style.HALO}
PIVOT = (0., 0., 90.)
OWNED = (SPARK_MATERIAL, SPARK_MESH, *MATERIALS.values(), *BLUEPRINTS, SEQUENCE)
ORIGINAL_COLOR_HINTS = {
    style.SURFACE: 'float3(.002,.004,.016)',
    style.CORE: 'float3(.0015,.0025,.009)',
    style.HALO: 'float band=exp(-pow((r-.81)/.055,2.));',
}
ORIGINAL_ALPHA_HINTS = {style.SURFACE: '.31+.19*body', style.HALO: 'smoothstep(.94,1.,r)'}
AS = u.EditorAssetLibrary
EDIT = u.MaterialEditingLibrary
ACTORS = u.get_editor_subsystem(u.EditorActorSubsystem)
FLOAT1 = u.CustomMaterialOutputType.CMOT_FLOAT1
FLOAT3 = u.CustomMaterialOutputType.CMOT_FLOAT3
EMISSIVE = u.MaterialProperty.MP_EMISSIVE_COLOR
ALPHA = u.MaterialProperty.MP_OPACITY
MASK = u.MaterialProperty.MP_OPACITY_MASK
WPO = u.MaterialProperty.MP_WORLD_POSITION_OFFSET


def argument(name):
    match = re.search(r'(?:^|\s)-' + name + r'=(?:"([^"]+)"|(\S+))',
                      u.SystemLibrary.get_command_line(), re.I)
    return (match.group(1) or match.group(2)) if match else None


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def content_hashes():
    content = ROOT / 'Content'
    return {path.relative_to(ROOT).as_posix(): digest(path)
            for path in sorted(content.rglob('*')) if path.is_file()}


def package_file(package):
    return 'Content/' + package.removeprefix('/Game/') + '.uasset'


def loaded_asset(package):
    obj = AS.load_asset(package)
    assert obj and obj.get_path_name().split('.')[0] == package, package
    return obj


def new_asset(package, asset_class, factory=None):
    assert not AS.does_asset_exist(package), package
    folder, name = package.rsplit('/', 1)
    asset = u.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, asset_class, factory)
    assert asset and asset.get_path_name().split('.')[0] == package, package
    return asset


def dirty_project():
    return {item.get_path_name().split('.')[0] for item in
            (*u.EditorLoadingAndSavingUtils.get_dirty_map_packages(),
             *u.EditorLoadingAndSavingUtils.get_dirty_content_packages())
            if item.get_path_name().startswith('/Game/')}


def vector(value):
    return [value.x, value.y, value.z]


def components(blueprint):
    system = u.get_engine_subsystem(u.SubobjectDataSubsystem)
    library = u.SubobjectDataBlueprintFunctionLibrary
    objects = [library.get_associated_object(library.get_data(handle))
               for handle in system.k2_gather_subobject_data_for_blueprint(blueprint)]
    return {obj.get_name().removesuffix('_GEN_VARIABLE'): obj for obj in objects
            if isinstance(obj, u.ActorComponent)}


def component_state(component):
    row = {'class': component.get_class().get_name()}
    if isinstance(component, u.SceneComponent):
        transform = component.get_relative_transform()
        rotation = transform.rotation.rotator()
        row.update(location=vector(transform.translation), scale=vector(transform.scale3d),
                   rotation=[rotation.roll, rotation.pitch, rotation.yaw],
                   mobility=str(component.get_editor_property('mobility')),
                   hidden=component.get_editor_property('hidden_in_game'))
    if isinstance(component, u.StaticMeshComponent):
        row.update(mesh=component.get_editor_property('static_mesh').get_path_name(),
                   materials=[component.get_material(i).get_path_name()
                              for i in range(component.get_num_materials())],
                   collision=str(component.get_collision_enabled()),
                   overlaps=component.get_editor_property('generate_overlap_events'),
                   navigation=component.get_editor_property('can_ever_affect_navigation'),
                   shadow=component.get_editor_property('cast_shadow'))
    return row


def protected_components(blueprint):
    return {name: component_state(item) for name, item in sorted(components(blueprint).items())
            if name != SPARK_COMPONENT}


def custom_input_names(node):
    return tuple(str(item.get_editor_property('input_name')) for item in node.get_editor_property('inputs'))


def material_output(material, kind):
    return EDIT.get_material_property_input_node(material, kind)


def new_expression(material, kind, x, y):
    node = EDIT.create_material_expression(material, kind, x, y)
    assert node, (material.get_name(), kind)
    return node


def connect(source, target, input_name=''):
    assert EDIT.connect_material_expressions(source, '', target, input_name), (
        source.get_name(), target.get_name(), input_name,
    )


def set_custom(node, code, inputs):
    node.modify()
    custom_inputs = []
    for name in inputs:
        item = u.CustomInput()
        item.set_editor_property('input_name', name)
        custom_inputs.append(item)
    node.set_editor_property('inputs', custom_inputs)
    node.set_editor_property('code', code)
    for name, source in inputs.items():
        connect(source, node, name)


def new_custom(material, x, y, description, code, output_type, inputs):
    node = new_expression(material, u.MaterialExpressionCustom, x, y)
    node.set_editor_property('description', description)
    node.set_editor_property('output_type', output_type)
    set_custom(node, code, inputs)
    return node


def new_parameters(material, names):
    result = {}
    for index, name in enumerate(dict.fromkeys(names)):
        initial = style.PARAMETERS[name]
        is_color = isinstance(initial, tuple)
        cls = u.MaterialExpressionVectorParameter if is_color else u.MaterialExpressionScalarParameter
        node = new_expression(material, cls, -820, 120 + 120 * index)
        node.set_editor_property('parameter_name', name)
        node.set_editor_property('group', 'Portal Energy')
        node.set_editor_property('default_value', u.LinearColor(*initial) if is_color else initial)
        result[name] = node
    return result


def register_output(node, kind):
    assert EDIT.connect_material_property(node, '', kind), (node.get_name(), str(kind))


def opacity_spec(name):
    if name == style.SURFACE:
        return style.SURFACE_OPACITY, ('UV', 'T', 'PortalFlowSpeed', 'PortalBodyOpacity')
    if name == style.HALO:
        return style.HALO_OPACITY, ('UV',)
    return style.DEPTH_MASK, ('UV',)


def check_node(material, output, code, names):
    node = material_output(material, output)
    assert isinstance(node, u.MaterialExpressionCustom), (material.get_name(), str(output))
    assert node.get_editor_property('code') == code and custom_input_names(node) == names, (
        material.get_name(), str(output), custom_input_names(node),
    )
    return node


def patch_shared(material, name):
    color = material_output(material, EMISSIVE)
    opacity = material_output(material, MASK if name == style.CORE else ALPHA)
    assert all(isinstance(node, u.MaterialExpressionCustom) for node in (color, opacity)), name
    opacity_code, opacity_names = opacity_spec(name)
    if color.get_editor_property('code') == style.COLOR_CODE[name]:
        return False
    assert ORIGINAL_COLOR_HINTS[name] in color.get_editor_property('code'), (name, 'unexpected color graph')
    assert custom_input_names(color) == ('UV', 'T'), (name, 'unexpected color inputs')
    if name == style.CORE:
        assert opacity.get_editor_property('code') == style.DEPTH_MASK, (name, 'depth mask')
    else:
        assert ORIGINAL_ALPHA_HINTS[name] in opacity.get_editor_property('code'), (name, 'original alpha')
    nodes = EDIT.get_inputs_for_material_expression(material, color)
    uv, = (node for node in nodes if isinstance(node, u.MaterialExpressionTextureCoordinate))
    time, = (node for node in nodes if isinstance(node, u.MaterialExpressionTime))
    material.modify()
    source = {'UV': uv, 'T': time}
    wanted = style.COLOR_PARAMETERS[name] + tuple(k for k in opacity_names if k in style.PARAMETERS)
    source.update(new_parameters(material, wanted))
    color.set_editor_property('description', 'Saturated portal currents')
    set_custom(color, style.COLOR_CODE[name], {k: source[k] for k in ('UV', 'T', *style.COLOR_PARAMETERS[name])})
    if name != style.CORE:
        opacity.set_editor_property('description', 'Portal transparency')
        set_custom(opacity, opacity_code, {k: source[k] for k in opacity_names})
    return True


def parameter_defaults(material, names, expected_energy=None):
    row = {}
    for key in names:
        expected = expected_energy if key == 'PortalEnergy' and expected_energy is not None else style.PARAMETERS[key]
        if isinstance(expected, tuple):
            rgba = EDIT.get_material_default_vector_parameter_value(material, key)
            actual = (rgba.r, rgba.g, rgba.b, rgba.a)
            assert all(abs(a - b) < 1e-5 for a, b in zip(actual, expected)), (key, actual)
        else:
            actual = EDIT.get_material_default_scalar_parameter_value(material, key)
            assert abs(actual - expected) < 1e-5, (key, actual)
        row[key] = actual
    return row


def shared_state(material, name, expected_energy=None):
    modes = {style.SURFACE: u.BlendMode.BLEND_TRANSLUCENT,
             style.CORE: u.BlendMode.BLEND_MASKED, style.HALO: u.BlendMode.BLEND_ADDITIVE}
    assert material.get_editor_property('blend_mode') == modes[name], name
    assert material.get_editor_property('shading_model') == u.MaterialShadingModel.MSM_UNLIT, name
    assert material.get_editor_property('two_sided'), name
    code, opacity_names = opacity_spec(name)
    color_names = ('UV', 'T', *style.COLOR_PARAMETERS[name])
    check_node(material, EMISSIVE, style.COLOR_CODE[name], color_names)
    check_node(material, MASK if name == style.CORE else ALPHA, code, opacity_names)
    wanted = dict.fromkeys(k for k in (*color_names, *opacity_names) if k in style.PARAMETERS)
    parameters = parameter_defaults(material, wanted, expected_energy)
    return {'blend': str(modes[name]), 'parameters': parameters,
            'mask_clip': material.get_editor_property('opacity_mask_clip_value') if name == style.CORE else None}


def tune_shared_energy(material, name):
    current = EDIT.get_material_default_scalar_parameter_value(material, 'PortalEnergy')
    target = style.PARAMETERS['PortalEnergy']
    if abs(current - target) < 1e-5:
        shared_state(material, name)
        return False
    assert abs(current - 1.) < 1e-5, (name, 'unexpected existing PortalEnergy default', current)
    shared_state(material, name, expected_energy=1.)
    color = material_output(material, EMISSIVE)
    parameter, = (node for node in EDIT.get_inputs_for_material_expression(material, color)
                  if isinstance(node, u.MaterialExpressionScalarParameter)
                  and str(node.get_editor_property('parameter_name')) == 'PortalEnergy')
    assert abs(parameter.get_editor_property('default_value') - 1.) < 1e-5, name
    material.modify()
    parameter.modify()
    parameter.set_editor_property('default_value', target)
    return True


def compile_materials(changed, report):
    report['shader_errors'] = {name: [str(error) for error in EDIT.recompile_material(material)]
                               for name, material in changed.items()}
    assert not any(report['shader_errors'].values()), report['shader_errors']


def local_to_world(material, source, x, y):
    transform = new_expression(material, u.MaterialExpressionTransform, x, y)
    transform.set_editor_property('transform_source_type', u.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_LOCAL)
    transform.set_editor_property('transform_type', u.MaterialVectorCoordTransform.TRANSFORM_WORLD)
    connect(source, transform)
    return transform


SPARK_PARAM_NAMES = ('SparkCyan', 'SparkViolet', 'SparkIntensity', 'OrbitSpeed', 'SparkSize')
SPARK_OFFSET_INPUTS = ('UV', 'T', 'OrbitSpeed')
SPARK_ALPHA_INPUTS = ('UV', 'T', 'OrbitSpeed', 'SparkSize', 'ScaleX')
SPARK_COLOR_INPUTS = ('UV', 'SparkCyan', 'SparkViolet', 'SparkIntensity')


def make_spark_material():
    material = new_asset(SPARK_MATERIAL, u.Material, u.MaterialFactoryNew())
    material.set_editor_property('blend_mode', u.BlendMode.BLEND_ADDITIVE)
    material.set_editor_property('shading_model', u.MaterialShadingModel.MSM_UNLIT)
    material.set_editor_property('two_sided', True)
    material.set_editor_property('max_world_position_offset_displacement', 220.)
    source = new_parameters(material, SPARK_PARAM_NAMES)
    source['UV'] = new_expression(material, u.MaterialExpressionTextureCoordinate, -820, -140)
    source['T'] = new_expression(material, u.MaterialExpressionTime, -820, -10)
    offset = new_custom(material, -490, -150, 'Local orbit', style.SPARK_OFFSET, FLOAT3,
                        {k: source[k] for k in SPARK_OFFSET_INPUTS})
    register_output(local_to_world(material, offset, -205, -150), WPO)
    unit = new_expression(material, u.MaterialExpressionConstant3Vector, -820, 840)
    unit.set_editor_property('constant', u.LinearColor(1., 0., 0., 1.))
    world_x = local_to_world(material, unit, -615, 840)
    scale = new_custom(material, -420, 840, 'Component scale', 'return length(WorldX);',
                       FLOAT1, {'WorldX': world_x})
    source['ScaleX'] = new_expression(material, u.MaterialExpressionVertexInterpolator, -205, 840)
    connect(scale, source['ScaleX'])
    register_output(new_custom(material, 5, 190, 'Spark life and closure', style.SPARK_OPACITY, FLOAT1,
                               {k: source[k] for k in SPARK_ALPHA_INPUTS}), ALPHA)
    register_output(new_custom(material, 5, 0, 'Spark colors', style.SPARK_COLOR, FLOAT3,
                               {k: source[k] for k in SPARK_COLOR_INPUTS}), EMISSIVE)
    return material


def spark_material_state(material):
    assert material.get_editor_property('blend_mode') == u.BlendMode.BLEND_ADDITIVE
    assert material.get_editor_property('shading_model') == u.MaterialShadingModel.MSM_UNLIT
    assert material.get_editor_property('two_sided')
    assert material.get_editor_property('max_world_position_offset_displacement') == 220.
    check_node(material, EMISSIVE, style.SPARK_COLOR, SPARK_COLOR_INPUTS)
    check_node(material, ALPHA, style.SPARK_OPACITY, SPARK_ALPHA_INPUTS)
    transform = material_output(material, WPO)
    assert isinstance(transform, u.MaterialExpressionTransform)
    assert transform.get_editor_property('transform_source_type') == u.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_LOCAL
    assert transform.get_editor_property('transform_type') == u.MaterialVectorCoordTransform.TRANSFORM_WORLD
    offset, = EDIT.get_inputs_for_material_expression(material, transform)
    assert offset.get_editor_property('code') == style.SPARK_OFFSET and custom_input_names(offset) == SPARK_OFFSET_INPUTS
    return parameter_defaults(material, SPARK_PARAM_NAMES)


def make_spark_mesh(material):
    mesh = new_asset(SPARK_MESH, u.StaticMesh)
    description = u.StaticMesh.create_static_mesh_description(mesh)
    group = description.create_polygon_group()
    description.set_polygon_group_material_slot_name(group, mesh.add_material(material))
    for card in style.spark_cards():
        corners = []
        for xyz, uv in card:
            vertex = description.create_vertex()
            description.set_vertex_position(vertex, u.Vector(*xyz))
            corner = description.create_vertex_instance(vertex)
            description.set_vertex_instance_uv(corner, u.Vector2D(*uv), 0)
            corners.append(corner)
        description.create_triangle(group, [corners[0], corners[1], corners[2]])
        description.create_triangle(group, [corners[0], corners[2], corners[3]])
    mesh.build_from_static_mesh_descriptions([description], False, False)
    return mesh


def spark_mesh_state(mesh, material):
    description = mesh.get_static_mesh_description(0)
    assert description.get_vertex_count() == style.COUNT * 4
    count = mesh.get_num_triangles(0)
    vertices = mesh.get_num_vertices(0)
    slots = mesh.get_num_sections(0)
    assert (count, vertices, slots) == (style.COUNT * 2, style.COUNT * 4, 1), (count, vertices, slots)
    assert mesh.get_material(0) == material
    bounds = vector(mesh.get_bounds().box_extent)
    assert 45 < bounds[0] < 65 and 11 < bounds[1] < 16 and 70 < bounds[2] < 105, bounds
    return {'cards': style.COUNT, 'vertices': vertices, 'triangles': count, 'slots': slots, 'extent': bounds}


def add_spark_component(blueprint, mesh, material):
    if SPARK_COMPONENT in components(blueprint):
        return False
    blueprint.modify()
    ActorTools.add_component(blueprint, u.StaticMeshComponent.static_class(), SPARK_COMPONENT)
    component = components(blueprint)[SPARK_COMPONENT]
    component.modify()
    component.set_editor_property('relative_location', u.Vector(*PIVOT))
    component.set_editor_property('mobility', u.ComponentMobility.MOVABLE)
    component.set_collision_profile_name('NoCollision')
    component.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
    component.set_editor_property('generate_overlap_events', False)
    component.set_editor_property('can_ever_affect_navigation', False)
    component.set_editor_property('cast_shadow', False)
    assert component.set_static_mesh(mesh)
    component.set_material(0, material)
    compile_bp(blueprint)
    return True


def spark_component_state(component, mesh, material):
    row = component_state(component)
    assert row['mesh'] == mesh.get_path_name() and row['materials'] == [material.get_path_name()], row
    assert row['location'] == list(PIVOT) and row['scale'] == [1., 1., 1.], row
    assert row['collision'] == str(u.CollisionEnabled.NO_COLLISION), row
    assert row['mobility'] == str(u.ComponentMobility.MOVABLE), row
    assert not any(row[k] for k in ('hidden', 'overlaps', 'navigation', 'shadow')), row
    return row


def key_pairs(channel):
    return [(arrival.frameof(k), k.get_value()) for k in channel.get_keys()]


def portal_window(sequence):
    bindings = arrival.bindings(sequence)
    assert sequence.get_playback_start() == 0 and sequence.get_playback_end() == arrival.END
    parent = bindings['ArrivalPortal']
    spawn, = arrival.section(parent, u.MovieSceneSpawnTrack).get_channels_by_type(u.MovieSceneScriptingBoolChannel)
    assert key_pairs(spawn) == [(0, True), (arrival.PORTAL_END, False)]
    for name in SITE_COMPONENTS:
        binding = bindings[name]
        assert arrival.guid(binding.get_parent()) == arrival.guid(parent)
        track = arrival.section(binding, u.MovieScene3DTransformTrack)
        channels = track.get_channels_by_type(u.MovieSceneScriptingDoubleChannel)
        for channel, base in zip(channels[6:8], arrival.PLANES[name]):
            assert all(
                f == step and abs(value - base * scale) < 1e-5
                for (f, value), (step, scale) in zip(key_pairs(channel),
                                                     [(0, 1.), (62, 1.), (72, .8), (86, .02)], strict=True)
            ), name
        hidden, = arrival.section(binding, u.MovieSceneVisibilityTrack).get_channels_by_type(u.MovieSceneScriptingBoolChannel)
        assert key_pairs(hidden) == [(0, True), (87, False)]
    return bindings, parent


def add_arrival_tracks(sequence, blueprint):
    bindings, parent = portal_window(sequence)
    if SPARK_COMPONENT in bindings:
        return False
    sequence.modify()
    actor = ACTORS.spawn_actor_from_class(blueprint.generated_class(), u.Vector(), u.Rotator(), transient=True)
    assert actor
    try:
        component = actor.get_editor_property(SPARK_COMPONENT)
        binding = arrival.component_binding(sequence, parent, component, SPARK_COMPONENT)
        rows = [(frame, [*PIVOT, 0., 0., 0., scale, 1., scale])
                for frame, scale in ((0, 1.), (62, 1.), (72, .8), (86, .02))]
        arrival.set_transforms(binding, rows, arrival.PORTAL_END)
        visibility = binding.add_track(u.MovieSceneVisibilityTrack)
        visibility.set_property_name_and_path('bHiddenInGame', 'bHiddenInGame')
        section = visibility.add_section()
        section.set_range(0, arrival.PORTAL_END)
        section.set_completion_mode(u.MovieSceneCompletionMode.RESTORE_STATE)
        channel, = section.get_channels_by_type(u.MovieSceneScriptingBoolChannel)
        channel.set_default(True)
        for frame, visible in ((0, True), (87, False)):
            channel.add_key(u.FrameNumber(frame), visible)
    finally:
        assert ACTORS.destroy_actor(actor)
    return True


def cut_state(sequence):
    track, = sequence.get_tracks()
    return [{'start': part.get_start_frame(), 'end': part.get_end_frame(),
             'camera': part.get_camera_binding_id().export_text(),
             'completion': str(part.get_completion_mode())} for part in track.get_sections()]


def prior_sequence_state(sequence):
    return {'bindings': {k: v for k, v in arrival.signature(sequence).items() if k != SPARK_COMPONENT},
            'cut_track': cut_state(sequence)}


def cold_structure(snapshot):
    """Compare the cat's section values independently of editor enumeration order."""
    normalized = json.loads(json.dumps(snapshot))
    tracks = normalized['previous_arrival']['bindings']['CosmeticCat']['tracks']
    animation, = (track for track in tracks if track['type'] == 'MovieSceneSkeletalAnimationTrack')
    animation['sections'].sort(key=lambda section: (*section['span'], section['clip']))
    return normalized


def arrival_state(sequence, blueprint):
    bindings, parent = portal_window(sequence)
    template = parent.get_object_template()
    assert template and template.get_class() == blueprint.generated_class()
    for name, material in SITE_COMPONENTS.items():
        component = template.get_editor_property(name)
        if component:
            assert component.get_material(0).get_path_name().split('.')[0] == MATERIALS[material], name
    child = bindings[SPARK_COMPONENT]
    assert arrival.guid(child.get_parent()) == arrival.guid(parent)
    transforms = arrival.section(child, u.MovieScene3DTransformTrack)
    channels = transforms.get_channels_by_type(u.MovieSceneScriptingDoubleChannel)
    for channel in (channels[6], channels[8]):
        assert all(f == wanted and abs(value - scale) < 1e-5
                   for (f, value), (wanted, scale) in zip(
                       key_pairs(channel), [(0, 1.), (62, 1.), (72, .8), (86, .02)], strict=True))
    visibility = arrival.section(child, u.MovieSceneVisibilityTrack)
    visible, = visibility.get_channels_by_type(u.MovieSceneScriptingBoolChannel)
    assert key_pairs(visible) == [(0, True), (87, False)]
    assert all(part.get_end_frame() == arrival.PORTAL_END for part in (transforms, visibility))
    return arrival.signature(sequence)[SPARK_COMPONENT]


def evaluate_arrival(world, sequence, mesh, material):
    bindings, parent = portal_window(sequence)
    child = bindings[SPARK_COMPONENT]
    player, holder = u.LevelSequencePlayer.create_level_sequence_player(
        world, sequence, u.MovieSceneSequencePlaybackSettings(),
    )
    assert player and holder
    rows = {}
    try:
        player.play()
        player.pause()
        position = u.MovieSceneSequencePlaybackParams()
        position.set_editor_property('position_type', u.MovieScenePositionType.FRAME)
        position.set_editor_property('update_method', u.UpdatePositionMethod.SCRUB)
        for frame in (1, 62, 72, 86, 87, 90, arrival.PORTAL_END):
            position.set_editor_property('frame', u.FrameTime(u.FrameNumber(frame), 0.))
            player.set_playback_position(position)
            actors = player.get_bound_objects(sequence.get_binding_id(parent))
            components_at_frame = player.get_bound_objects(sequence.get_binding_id(child))
            if frame == arrival.PORTAL_END:
                assert not actors and not components_at_frame, (frame, actors, components_at_frame)
                rows[str(frame)] = {'spawned': False}
                continue
            actor, = actors
            component, = components_at_frame
            assert actor.get_editor_property(SPARK_COMPONENT) == component and component.get_owner() == actor
            assert component.get_material(0) == material and component.get_editor_property('static_mesh') == mesh
            assert component.get_collision_enabled() == u.CollisionEnabled.NO_COLLISION
            for name, original in SITE_COMPONENTS.items():
                layer = actor.get_editor_property(name)
                assert layer and layer.get_material(0).get_path_name().split('.')[0] == MATERIALS[original], name
            scale = vector(component.get_relative_transform().scale3d)
            hidden = component.get_editor_property('hidden_in_game')
            plane = actor.get_editor_property('Surface')
            plane_scale = plane.get_relative_transform().scale3d
            assert abs(scale[0] - plane_scale.x / arrival.PLANES['Surface'][0]) < 0.005, (frame, scale, plane_scale)
            assert abs(scale[2] - plane_scale.y / arrival.PLANES['Surface'][1]) < 0.005, (frame, scale, plane_scale)
            assert bool(hidden) == (frame >= 87) == bool(plane.get_editor_property('hidden_in_game')), frame
            rows[str(frame)] = {'spawned': True, 'scale': scale, 'hidden': hidden}
    finally:
        player.stop()
        assert ACTORS.destroy_actor(holder)
    return rows


def portal_state(blueprint, mesh, material):
    items = components(blueprint)
    for name, source in SITE_COMPONENTS.items():
        assert items[name].get_material(0).get_path_name().split('.')[0] == MATERIALS[source], name
    return spark_component_state(items[SPARK_COMPONENT], mesh, material)


def run(mode, baseline=None):
    assert mode in ('author', 'energy', 'cold'), mode
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    out = ROOT / 'Saved/PresentationFix20261119/PortalStyle' / stamp
    out.mkdir(parents=True)
    report_file = out / 'report.json'
    report = {'mode': mode, 'pid': os.getpid(), 'completed': False, 'saved': []}
    before = {}

    def persist(phase):
        report['phase'] = phase
        report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    try:
        assert not dirty_project(), dirty_project()
        assert not u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world(), 'Stop PIE before authoring.'
        before = content_hashes()
        report['before_hashes'] = before
        report['source_hashes'] = {path.name: digest(path) for path in
                                   (Path(__file__), Path(style.__file__), Path(arrival.__file__))}
        persist('hashes')
        if mode == 'cold':
            assert baseline, 'A successful author report path is required.'
            prior = json.loads(Path(baseline).read_text(encoding='utf-8'))
            assert prior['completed'] and prior['mode'] in ('author', 'energy') and prior['pid'] != os.getpid()
            assert before == prior['after_hashes'], 'Content changed since the author run.'
            for source in (Path(style.__file__).name, Path(arrival.__file__).name):
                assert report['source_hashes'][source] == prior['source_hashes'][source], source
            report['audit_driver_differs_from_author'] = (
                report['source_hashes'][Path(__file__).name] != prior['source_hashes'][Path(__file__).name]
            )
        else:
            backups = {}
            for package in MATERIALS.values() if mode == 'energy' else OWNED:
                relative = package_file(package)
                if relative in before:
                    destination = out / 'Before' / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(ROOT / relative, destination)
                    assert digest(destination) == before[relative], relative
                    backups[package] = str(destination)
            report['backups'] = backups
            persist('backed_up')

        world = u.EditorLoadingAndSavingUtils.new_blank_map(False)
        assert world and not world.get_path_name().startswith('/Game/')
        materials = {name: loaded_asset(package) for name, package in MATERIALS.items()}
        blueprints = {package: loaded_asset(package) for package in BLUEPRINTS}
        sequence = loaded_asset(SEQUENCE)
        portal_window(sequence)
        before_sequence = prior_sequence_state(sequence)
        before_components = {package: protected_components(bp) for package, bp in blueprints.items()}
        old_clip = materials[style.CORE].get_editor_property('opacity_mask_clip_value')
        changed = {}

        if mode == 'author':
            persist('material_graphs')
            for name, material in materials.items():
                if patch_shared(material, name):
                    changed[MATERIALS[name]] = material
            if not AS.does_asset_exist(SPARK_MATERIAL):
                changed[SPARK_MATERIAL] = make_spark_material()
            spark = changed[SPARK_MATERIAL] if SPARK_MATERIAL in changed else loaded_asset(SPARK_MATERIAL)
            compile_materials(changed, report)
            persist('spark_mesh')
            if not AS.does_asset_exist(SPARK_MESH):
                changed[SPARK_MESH] = make_spark_mesh(spark)
            mesh = changed[SPARK_MESH] if SPARK_MESH in changed else loaded_asset(SPARK_MESH)
            persist('spark_components')
            for package, bp in blueprints.items():
                if add_spark_component(bp, mesh, spark):
                    changed[package] = bp
            persist('arrival_binding')
            if add_arrival_tracks(sequence, blueprints[BLUEPRINTS[1]]):
                changed[SEQUENCE] = sequence
        else:
            spark, mesh = loaded_asset(SPARK_MATERIAL), loaded_asset(SPARK_MESH)
            if mode == 'energy':
                assert SPARK_COMPONENT in arrival.bindings(sequence), 'Portal style must already be installed.'
                persist('shared_energy_defaults')
                for name, material in materials.items():
                    if tune_shared_energy(material, name):
                        changed[MATERIALS[name]] = material
                compile_materials(changed, report)

        persist('verify_structure')
        assert prior_sequence_state(sequence) == before_sequence, 'Existing arrival bindings or cuts changed.'
        assert {package: protected_components(bp) for package, bp in blueprints.items()} == before_components
        states = {name: shared_state(material, name) for name, material in materials.items()}
        assert states[style.CORE]['mask_clip'] == old_clip
        report['structure'] = {
            'shared': states,
            'spark_material': spark_material_state(spark),
            'spark_mesh': spark_mesh_state(mesh, spark),
            'components': {package: portal_state(bp, mesh, spark) for package, bp in blueprints.items()},
            'previous_components': before_components,
            'previous_arrival': before_sequence,
            'spark_binding': arrival_state(sequence, blueprints[BLUEPRINTS[1]]),
        }
        persist('verify_arrival_playback')
        report['arrival_playback'] = evaluate_arrival(world, sequence, mesh, spark)
        assert dirty_project() <= set(changed), dirty_project()
        if mode == 'cold':
            assert cold_structure(report['structure']) == cold_structure(prior['structure']), 'Cold structure differs.'
            assert report['arrival_playback'] == prior['arrival_playback'], 'Cold arrival evaluation differs.'
        else:
            persist('save')
            for package in OWNED:
                if package in changed:
                    assert AS.save_loaded_asset(changed[package], False), package
                    report['saved'].append(package)
                    persist('save')
        assert not dirty_project(), dirty_project()
        report['completed'] = True
    except Exception:
        report['error'] = traceback.format_exc()
        raise
    finally:
        report['after_hashes'] = content_hashes()
        actual = {path for path in before.keys() | report['after_hashes'].keys()
                  if before.get(path) != report['after_hashes'].get(path)} if before else set()
        expected = {package_file(pkg) for pkg in report['saved']}
        report['changed'] = sorted(actual)
        report['unexpected'] = sorted(actual - expected)
        report['completed'] = report['completed'] and actual == expected
        persist('complete')
        print('CATRUN_PORTAL_STYLE_20261119', report['completed'], str(report_file))
        assert actual == expected, {'changed': sorted(actual), 'expected': sorted(expected)}


if __name__ == '__main__':
    run(argument('catrunPortalStyle'), argument('catrunPortalStyleBaseline'))
