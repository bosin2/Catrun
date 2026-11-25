"""Stage3 wall articulation, military furnishing and fixture-led illumination.

Import is inert. The director calls apply() in the Stage3 editor writer slot,
inspects the returned bounds/light report, then saves the level separately.
Existing puzzle, enemy, camera, warehouse and acoustic actors are not rebuilt.
"""
import json
import math
from pathlib import Path

import unreal as u

MAP = '/Game/Maps/Stage3.Stage3'
PREFIX = 'S3_Gothic_'
OWNER = 'Stage3GothicDressing20261125'
DEST = '/Game/Environment/Stage3/GothicRevision_20261125'
LIGHTING_DEFAULTS = {
    'point_intensity_scale': .55, 'candle_intensity_scale': .75,
    'gate_pier_intensity_scale': .65,
    'wall_temperature': 3200., 'candle_temperature': 2900.,
    'source_radius': 16., 'gate_source_radius': 20., 'soft_source_radius': 25.,
    'key_intensity': .18, 'key_source_angle': 2.5, 'fill_intensity': .55, 'sky_intensity': .30,
    'exposure_bias': 0., 'bloom_intensity': .12,
}

# Wallside placements are world-space centimetres. Only the new floor furniture
# receives collision; ornament, lighting fixtures and floor overlays do not.
# The original warehouse seven obstacles are deliberately absent from this list.
FURNITURE = [
    ('LobbyBench', 'SM_S3_GuardBench', (-335, 370, 0), 90, 'Lobby'),
    ('LobbyCabinet', 'SM_S3_EquipmentCabinet', (625, 320, 0), 90, 'Lobby'),
    ('LowerStrategy', 'SM_S3_StrategyTable', (-315, 1120, 0), 90, 'LowerHall'),
    ('LowerBench', 'SM_S3_GuardBench', (235, 1280, 0), 90, 'LowerHall'),
    ('ExhibitionShield', 'SM_S3_ShieldRack', (-1040, 2110, 0), 0, 'Exhibition'),
    ('WarehouseMaintenance', 'SM_S3_MaintenanceBench', (760, 1410, 0), 0, 'Warehouse'),
]

# Surface mount yaw: local +Y points into the room (west=-90, east=90,
# south=0, north=180). Position is the fixture's wall anchor, not its flame.
SCONCES = [
    ('Entrance', (35, 95, 145), -90, 14, 290),
    ('Entrance', (265, 95, 145), 90, 14, 290),
    ('Lobby', (-365, 315, 158), -90, 24, 380),
    ('Lobby', (665, 410, 158), 90, 24, 380),
    ('Lobby', (-365, 680, 158), -90, 24, 380),
    ('LowerHall', (-365, 1020, 160), -90, 28, 410),
    ('LowerHall', (280, 1160, 160), 90, 28, 410),
    ('LowerHall', (-365, 1510, 160), -90, 28, 410),
    ('Exhibition', (-1115, 1540, 165), -90, 26, 360),
    ('Exhibition', (-1115, 1840, 165), -90, 26, 360),
    ('Exhibition', (-1115, 2230, 165), -90, 40, 600),
    ('Warehouse', (1165, 1020, 165), 90, 20, 380),
    ('Warehouse', (1165, 1370, 165), 90, 20, 380),
    ('Warehouse', (650, 815, 165), 0, 20, 380),
    ('CentralCorridor', (320, 1778, 165), 180, 24, 340),
    ('CentralCorridor', (820, 1778, 165), 180, 24, 340),
    ('CentralCorridor', (1165, 1660, 165), 90, 22, 320),
    ('CatBypass', (850, 1915, 180), 180, 10, 250),
    ('MainEntry', (285, 1830, 180), 0, 12, 270),
    ('ControlRoom', (100, 2515, 170), 180, 30, 390),
    ('ControlRoom', (600, 2515, 170), 180, 30, 390),
    ('ControlRoom', (915, 2170, 170), 90, 30, 390),
    ('UpperCorridor', (-365, 2400, 165), -90, 22, 320),
    ('UpperCorridor', (-365, 2720, 165), -90, 22, 320),
    ('GateHall', (-965, 3170, 185), -90, 70, 490),
    ('GateHall', (465, 3170, 185), 90, 70, 490),
    ('GateHall', (-965, 3620, 185), -90, 65, 490),
    ('GateHall', (465, 3620, 185), 90, 65, 490),
    ('GateHall', (-610, 3910, 185), 180, 60, 500),
    ('GateHall', (110, 3910, 185), 180, 60, 500),
]
CANDLESTANDS = [
    ('LowerHall', (-325, 1400, 0), 22, 340),
    ('GateHall', (-640, 3830, 0), 22, 430),
    ('GateHall', (140, 3830, 0), 22, 430),
]
BANNERS = [
    ('Lobby', (665, 305, 280), 90),
    ('LowerHall', (-365, 1235, 285), -90),
    ('Exhibition', (-1115, 2340, 285), -90),
    ('CentralCorridor', (475, 1778, 285), 180),
    ('UpperCorridor', (-365, 2550, 285), -90),
    ('GateHall', (-965, 3400, 285), -90),
    ('GateHall', (465, 3400, 285), 90),
]


def _vec(v):
    return [v.x, v.y, v.z]


def reference_light_targets():
    """Absolute targets from fixed baseline candela; repeated apply never compounds."""
    result = {}
    for index, (zone, pos, yaw, intensity, radius) in enumerate(SCONCES):
        grand = zone == 'GateHall'
        angle = math.radians(yaw)
        offset = 50 if grand else 32
        result[PREFIX + f'{zone}_SconceLight{index}'] = {
            'zone': zone, 'fixture': PREFIX + f'{zone}_Sconce{index}',
            'location': (pos[0] - math.sin(angle) * offset,
                         pos[1] + math.cos(angle) * offset, pos[2] + (87 if grand else 46)),
            'intensity': intensity * LIGHTING_DEFAULTS['point_intensity_scale'] * (
                LIGHTING_DEFAULTS['gate_pier_intensity_scale'] if grand and pos[1] > 3850 else 1.),
            'attenuation_radius': radius, 'temperature': LIGHTING_DEFAULTS['wall_temperature'],
            'source_radius': LIGHTING_DEFAULTS['gate_source_radius' if grand else 'source_radius'],
            'soft_source_radius': LIGHTING_DEFAULTS['soft_source_radius'],
        }
    for index, (zone, pos, intensity, radius) in enumerate(CANDLESTANDS):
        result[PREFIX + f'{zone}_CandelabrumLight{index}'] = {
            'zone': zone, 'fixture': PREFIX + f'{zone}_Candelabrum{index}',
            'location': (pos[0], pos[1], pos[2] + 133),
            'intensity': intensity * LIGHTING_DEFAULTS['candle_intensity_scale'],
            'attenuation_radius': radius, 'temperature': LIGHTING_DEFAULTS['candle_temperature'],
            'source_radius': LIGHTING_DEFAULTS['gate_source_radius' if zone == 'GateHall' else 'source_radius'],
            'soft_source_radius': LIGHTING_DEFAULTS['soft_source_radius'],
        }
    return result


def _canonical(material_name):
    return material_name.removesuffix('_Occlusion').removesuffix('_DeviceReadability')


def _role(name, stone_role):
    name = _canonical(name)
    if name in ('M_S3_limestone', 'M_S3_dressed_stone'):
        return stone_role
    return {'M_S3_flagstone': 'Floor', 'M_S3_dark_stone': 'FloorDiamond',
            'M_S3_mid_stone': 'FloorDiamond', 'M_S3_iron': 'BlackIron',
            'M_S3_brass': 'Brass', 'M_S3_wood': 'Wood',
            'M_S3_cloth': 'Banner', 'M_S3_guard_pennon': 'Banner',
            'M_S3_grand_pennon': 'Banner'}.get(name)


def _bundle_cadence(faces):
    """Select alternate eligible wall modules in physical, continuous runs.

    Typical 200 cm modules produce a 400 cm rhythm. A gap of more than 1 cm
    starts a fresh run, so doorways never inherit cadence from the far side.
    Rounded plane coordinates absorb submillimetre FBX bounds noise only.
    Entrance keeps its shallow mouldings but gets no full-height bundles.
    """
    runs = {}
    eligible = [face for face in faces if face['length'] >= 100
                and not 1800 <= face['center_y'] <= 1950]
    for face in eligible:
        key = (face['horizontal'], round(face['fixed'], 1), face['sign'])
        runs.setdefault(key, []).append(face)
    selected = set()
    continuous_runs = 0
    for faces_on_plane in runs.values():
        last_end = None
        ordinal = 0
        for face in sorted(faces_on_plane, key=lambda item: (item['lo'], item['index'])):
            if last_end is None or face['lo'] - last_end > 1.:
                ordinal = 0
                continuous_runs += 1
            if ordinal % 2 == 0 and face['zone'] != 'Entrance':
                selected.add(face['index'])
            last_end = face['lo'] + face['length']
            ordinal += 1
    return selected, {'eligible_bundle_groups': len(eligible),
                      'selected_bundle_groups': len(selected),
                      'omitted_bundle_groups': len(eligible) - len(selected),
                      'removed_mesh_actors': (len(eligible) - len(selected)) * 5,
                      'continuous_wall_runs': continuous_runs,
                      'target_rhythm_cm': 400, 'entrance_full_height_bundles': 0}


def apply():
    """Mutate the loaded Stage3 editor world, return QA data; never save a map.

    Reapplying removes only actors carrying BOTH our label prefix and owner tag.
    Source meshes/materials are never modified. All original gameplay transforms
    remain byte-for-byte untouched. New solid furniture needs traversal QA.
    """
    editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    assert editor.get_editor_world().get_path_name() == MAP, 'Load Stage3 editor world first'
    assert not editor.get_game_world(), 'End PIE before dressing'
    actorsystem = u.get_editor_subsystem(u.EditorActorSubsystem)
    root = Path(u.Paths.project_dir()).resolve()
    imports = json.loads((root / 'Saved/Stage3Integration20261125/import_report.json').read_text(encoding='utf8'))
    calibration = json.loads((root / 'Saved/Stage3MaterialCorrection20261125/Materials/application_report.json').read_text(encoding='utf8'))
    assert imports.get('success') and calibration.get('success')
    actors = list(actorsystem.get_all_level_actors())
    labels = {a.get_actor_label(): a for a in actors}
    original_transforms = {a.get_path_name(): a.get_actor_transform().export_text()
                           for a in actors if OWNER not in map(str, a.tags)}
    report = {'map': MAP, 'placements': [], 'lights': [], 'ambient_before': [],
              'hidden_original_visuals': [], 'material_preserved_slots': [],
              'new_solid_bounds': [], 'packages_saved': False,
              'traversal_qa': 'pending real player traversal of new wallside furniture',
              'visual_qa': 'pending actual yaw45 player camera Lit/BaseColor/DetailLighting'}
    meshes = {}
    needed = {row[1] for row in FURNITURE} | {
        'SM_S3_WallPilaster', 'SM_S3_GrandPillar_Base', 'SM_S3_GrandPillar_Capital',
        'SM_S3_Wall_50', 'SM_S3_WallSconce', 'SM_S3_GrandWallLantern',
        'SM_S3_FloorCandelabrum', 'SM_S3_GuardBanner', 'SM_S3_BannerHanger',
        'SM_S3_Floor_GateAxis', 'SM_S3_Floor_GateThreshold', 'SM_S3_Floor_GateBorder'}
    for name in needed:
        meshes[name] = u.load_object(None, imports['meshes'][name]['path'])
        assert meshes[name], name
    # Resolve materials from current calibrated actor/component bindings, rather
    # than applying uncorrected imported mesh defaults to the new architecture.
    materials = {}
    for row in calibration['assignments']:
        material = None
        existing = labels.get(row['actor'])
        if existing:
            for comp in existing.get_components_by_class(u.MeshComponent):
                if comp.get_name() == row['component']:
                    candidate = comp.get_material(row['slot'])
                    if candidate and '/ColorCorrection_20261125/' in candidate.get_path_name():
                        material = candidate
        material = material or u.load_object(None, row['assigned_material'])
        assert material, row['assigned_material']
        source_name = row['source_material'].rsplit('.', 1)[-1]
        key = (_canonical(source_name), row['role'])
        # Occlusion-aware parents are important for the actual yaw45 camera.
        if key not in materials or '_Occlusion' in source_name:
            materials[key] = material
    for actor in actors:
        if OWNER in map(str, actor.tags):
            assert actor.get_actor_label().startswith(PREFIX), 'Owned actor was renamed outside our namespace'
            assert actorsystem.destroy_actor(actor)
    # Mechanism modules share S3_Gothic_ but have a different owner tag.
    actors = [a for a in actorsystem.get_all_level_actors()]
    surviving_labels = {a.get_actor_label() for a in actors}

    def spawn(cls, name, pos, yaw=0, zone='Architecture'):
        assert PREFIX + name not in surviving_labels, 'Refusing to replace another module actor: ' + name
        actor = actorsystem.spawn_actor_from_class(cls, u.Vector(*pos), u.Rotator(yaw=yaw))
        assert actor, name
        actor.set_actor_label(PREFIX + name)
        actor.set_folder_path('Stage3/GothicRevision/' + zone)
        actor.tags = [u.Name(OWNER)]
        surviving_labels.add(PREFIX + name)
        return actor

    def static(name, meshname, pos, yaw=0, scale=(1, 1, 1),
               zone='Architecture', stone_role='Pillar', solid=False, minimum=False):
        actor = spawn(u.StaticMeshActor, name, (0, 0, 0) if minimum else pos, yaw, zone)
        comp = actor.static_mesh_component
        comp.set_static_mesh(meshes[meshname])
        actor.set_actor_scale3d(u.Vector(*scale))
        comp.set_collision_profile_name('BlockAll' if solid else 'NoCollision')
        if not solid:
            comp.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
        if minimum:
            center, extent = actor.get_actor_bounds(False)
            actor.set_actor_location(u.Vector(*pos) - (center - extent), False, True)
        bindings = []
        for index, slot in enumerate(meshes[meshname].get_editor_property('static_materials')):
            source = slot.get_editor_property('material_interface')
            if not source:
                continue
            role = _role(source.get_name(), stone_role)
            if role:
                selected = materials.get((_canonical(source.get_name()), role))
                assert selected, (name, source.get_name(), role)
                comp.set_material(index, selected)
                bindings.append([index, selected.get_path_name(), role])
            else:
                # Preserve detailed plan/parchment, leather, mortar and emissive
                # flame/wax. These were explicitly outside calibrated roles.
                report['material_preserved_slots'].append([name, index, source.get_path_name()])
        center, extent = actor.get_actor_bounds(False)
        bounds = [_vec(center - extent), _vec(center + extent)]
        report['placements'].append({'label': actor.get_actor_label(), 'mesh': meshname,
            'zone': zone, 'location': _vec(actor.get_actor_location()), 'yaw': yaw,
            'scale': list(scale), 'bounds': bounds, 'solid': solid, 'materials': bindings})
        if solid:
            report['new_solid_bounds'].append({'label': actor.get_actor_label(), 'bounds': bounds})
        return actor

    # Work against actual solid wall pieces, never frame/opening bounds. Put the
    # small articulated bases/caps on occupied sides only. Cat passage remains
    # minimally ornamented and all projection stays at its upper wall line.
    import sys
    layoutpath = str(root / 'Scripts/Stage3')
    if layoutpath not in sys.path:
        sys.path.insert(0, layoutpath)
    import layout
    occupied = layout.cells()

    def inside(x, y):
        return (math.floor(x / 50) * 50, math.floor(y / 50) * 50) in occupied

    wall_faces = []
    for wall in actors:
        if not wall.get_actor_label().startswith('S3_Wall_'):
            continue
        center, ext = wall.get_actor_bounds(False)
        horizontal = ext.x >= ext.y
        lo = center.x - ext.x if horizontal else center.y - ext.y
        length = 2 * (ext.x if horizontal else ext.y)
        if length < 70:
            continue
        for sign in (-1, 1):
            fixed = (center.y + sign * ext.y) if horizontal else (center.x + sign * ext.x)
            sample_x = center.x if horizontal else fixed + sign * 40
            sample_y = fixed + sign * 40 if horizontal else center.y
            if not inside(sample_x, sample_y):
                continue
            zone = next((name for name, (x0, y0, x1, y1) in (*layout.ROOMS.items(), *layout.CONNECTORS.items())
                         if x0 <= sample_x < x1 and y0 <= sample_y < y1), 'Architecture')
            wall_faces.append({'index': len(wall_faces) + 1, 'horizontal': horizontal,
                               'fixed': fixed, 'sign': sign, 'lo': lo, 'length': length,
                               'center_y': center.y, 'zone': zone})
    selected_bundles, report['architecture_cadence'] = _bundle_cadence(wall_faces)
    for face in wall_faces:
        wallindex = face['index']
        horizontal, fixed, sign = face['horizontal'], face['fixed'], face['sign']
        lo, length = face['lo'], face['length']
        x, y = (lo, fixed if sign > 0 else fixed - 5) if horizontal else (fixed if sign > 0 else fixed - 5, lo)
        dims = (length, 5) if horizontal else (5, length)
        # Reuse dressed wall geometry in a shallow strip: an upper crown,
        # middle string course and low plinth establish a masonry hierarchy.
        for suffix, z, height in [('Plinth', 0, 14), ('String', 255, 7), ('Cornice', 283, 17)]:
            static(f'Wall{wallindex}_{suffix}', 'SM_S3_Wall_50', (x, y, z),
                   scale=(dims[0] / 50, dims[1] / 30, height / 300), minimum=True)
        if wallindex not in selected_bundles:
            continue
        anchor = lo + length * .5
        # Three slender profiles form one wall-bound bundle. Their total
        # visible projection is 13 cm, considerably below furniture depth.
        for j, tangent in enumerate((-12, 0, 12)):
            point = (anchor + tangent, fixed, 0) if horizontal else (fixed, anchor + tangent, 0)
            yaw = (0 if sign > 0 else 180) if horizontal else (-90 if sign > 0 else 90)
            static(f'Wall{wallindex}_Bundle{j}', 'SM_S3_WallPilaster', point, yaw,
                   scale=(.48, .66 if j == 1 else .48, .92 if j else .90))
        for suffix, meshname, z, height in [
            ('Base', 'SM_S3_GrandPillar_Base', 0, 23),
            ('Capital', 'SM_S3_GrandPillar_Capital', 264, 20)]:
            point = (anchor, fixed + sign * 4, z) if horizontal else (fixed + sign * 4, anchor, z)
            static(f'Wall{wallindex}_{suffix}', meshname, point,
                   scale=((.36, .16, height / (40 if suffix == 'Base' else 60)) if horizontal else
                          (.16, .36, height / (40 if suffix == 'Base' else 60))))

    for name, meshname, pos, yaw, zone in FURNITURE:
        static(name, meshname, pos, yaw, zone=zone, solid=True)
    for i, (zone, pos, yaw) in enumerate(BANNERS):
        static(f'{zone}_Banner{i}', 'SM_S3_GuardBanner', pos, yaw, zone=zone)
        static(f'{zone}_BannerHanger{i}', 'SM_S3_BannerHanger', pos, yaw, zone=zone)

    # Explicit floor overlay replaces the four generic rectangular runner pieces.
    # 200x250 source axis rotated 90 => a 250-wide, 200-long world-space segment.
    for i, y in enumerate((3000, 3200, 3400, 3600)):
        static(f'GateAxis{i}', 'SM_S3_Floor_GateAxis', (-375, y, -4.8), 90,
               zone='GateHall', minimum=True)
    static('GateThreshold', 'SM_S3_Floor_GateThreshold', (-550, 3800, -4.7), 90,
           zone='GateHall', minimum=True)
    for side, x in [('Left', -400), ('Right', -125)]:
        for i, y in enumerate((3000, 3200, 3400, 3600)):
            static(f'GateBorder{side}{i}', 'SM_S3_Floor_GateBorder', (x, y, -4.6), 90,
                   zone='GateHall', minimum=True)
    for label, actor in labels.items():
        if label.startswith('S3_Runner') or label.startswith('S3_Lantern'):
            comp = actor.get_component_by_class(u.StaticMeshComponent)
            if comp:
                report['hidden_original_visuals'].append(label)
                comp.set_visibility(False, True)
                comp.set_hidden_in_game(True, True)

    # Existing broad lights are dimmed, not destroyed. Duplicate directionals
    # cannot flatten the scene; local illumination is paired with real fixtures.
    for actor in actors:
        if actor.get_actor_label().startswith(PREFIX):
            continue
        label = actor.get_actor_label()
        light = actor.get_component_by_class(u.LightComponent)
        if isinstance(light, u.DirectionalLightComponent):
            report['ambient_before'].append([label, 'Directional', light.get_editor_property('intensity')])
            desired = (LIGHTING_DEFAULTS['key_intensity'] if label == 'S3_KeyLight' else
                       LIGHTING_DEFAULTS['fill_intensity'] if label == 'S3_FillLight' else 0.)
            light.set_intensity(desired)
            light.set_light_color(u.LinearColor(1, 1, 1, 1))
            light.set_editor_property('use_temperature', False)
            if label == 'S3_KeyLight':
                light.set_editor_property('light_source_angle', LIGHTING_DEFAULTS['key_source_angle'])
            elif label == 'S3_FillLight':
                light.set_cast_shadows(False)
        elif isinstance(light, u.PointLightComponent) and label.startswith('S3_LocalLight'):
            report['ambient_before'].append([label, 'Point', light.get_editor_property('intensity')])
            light.set_intensity(0.)
        sky = actor.get_component_by_class(u.SkyLightComponent)
        if sky:
            report['ambient_before'].append([label, 'Sky', sky.get_editor_property('intensity')])
            sky.set_intensity(LIGHTING_DEFAULTS['sky_intensity'])
            sky.set_light_color(u.LinearColor(1, 1, 1, 1))
            neutral = u.load_object(None, '/Engine/EditorMaterials/AssetViewer/T_GreyAmbient.T_GreyAmbient')
            assert neutral
            sky.set_editor_property('source_type', u.SkyLightSourceType.SLS_SPECIFIED_CUBEMAP)
            sky.set_cubemap(neutral)
        if isinstance(actor, u.PostProcessVolume) and label == 'S3_Exposure':
            settings = actor.get_editor_property('settings')
            for prop, value in {
                'override_auto_exposure_method': True,
                'auto_exposure_method': u.AutoExposureMethod.AEM_MANUAL,
                'override_auto_exposure_apply_physical_camera_exposure': True,
                'auto_exposure_apply_physical_camera_exposure': False,
                'override_auto_exposure_bias': True, 'auto_exposure_bias': LIGHTING_DEFAULTS['exposure_bias'],
                'override_bloom_intensity': True, 'bloom_intensity': LIGHTING_DEFAULTS['bloom_intensity'],
            }.items():
                settings.set_editor_property(prop, value)
            actor.set_editor_property('settings', settings)

    light_targets = reference_light_targets()

    def local(name, zone, pos, intensity, radius, temperature):
        intensity = light_targets[PREFIX + name]['intensity']
        actor = spawn(u.PointLight, name, pos, zone='Lighting/' + zone)
        comp = actor.point_light_component
        comp.set_mobility(u.ComponentMobility.MOVABLE)
        comp.set_editor_property('intensity_units', u.LightUnits.CANDELAS)
        comp.set_intensity(float(intensity))
        comp.set_light_color(u.LinearColor(1, 1, 1, 1))
        comp.set_editor_property('use_temperature', True)
        comp.set_editor_property('temperature', float(temperature))
        comp.set_attenuation_radius(float(radius))
        comp.set_editor_property('source_radius', LIGHTING_DEFAULTS['gate_source_radius' if zone == 'GateHall' else 'source_radius'])
        comp.set_editor_property('soft_source_radius', LIGHTING_DEFAULTS['soft_source_radius'])
        comp.set_cast_shadows(True)
        report['lights'].append({'label': actor.get_actor_label(), 'zone': zone,
            'location': list(pos), 'candela': intensity, 'radius': radius,
            'kelvin': temperature, 'shadows': True,
            'source_radius': comp.get_editor_property('source_radius'),
            'soft_source_radius': comp.get_editor_property('soft_source_radius')})

    for i, (zone, pos, yaw, intensity, radius) in enumerate(SCONCES):
        grand = zone == 'GateHall'
        fixture = static(f'{zone}_Sconce{i}', 'SM_S3_GrandWallLantern' if grand else 'SM_S3_WallSconce',
                         pos, yaw, zone='Lighting/' + zone)
        fixture.static_mesh_component.set_cast_shadow(False)
        rad = math.radians(yaw)
        offset = 50 if grand else 32
        flame = (pos[0] - math.sin(rad) * offset,
                 pos[1] + math.cos(rad) * offset, pos[2] + (87 if grand else 46))
        local(f'{zone}_SconceLight{i}', zone, flame, intensity, radius, LIGHTING_DEFAULTS['wall_temperature'])
    for i, (zone, pos, intensity, radius) in enumerate(CANDLESTANDS):
        fixture = static(f'{zone}_Candelabrum{i}', 'SM_S3_FloorCandelabrum', pos,
                         zone='Lighting/' + zone)
        fixture.static_mesh_component.set_cast_shadow(False)
        local(f'{zone}_CandelabrumLight{i}', zone, (pos[0], pos[1], pos[2] + 133),
              intensity, radius, LIGHTING_DEFAULTS['candle_temperature'])

    for actor in actorsystem.get_all_level_actors():
        if actor.get_path_name() in original_transforms:
            assert actor.get_actor_transform().export_text() == original_transforms[actor.get_path_name()], actor.get_actor_label()
    report['original_transforms_unchanged'] = True
    report['zones_with_fixtures'] = sorted({row['zone'] for row in report['lights']})
    report['success'] = True
    return report
