"""Apply after native build with -EnablePlugins=UMGToolSet. -catrunHudAudit reads saved packages."""

from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys

import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts/Menu'))
from menu_graph import BP, Graph, add, compile_bp, editor, entry, properties, ui, widgets
from rework_minimap_20261112 import canvas_slot

AS = u.EditorAssetLibrary
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
ED = u.get_editor_subsystem(u.UnrealEditorSubsystem)
ACTORS = u.get_editor_subsystem(u.EditorActorSubsystem)
ART = ROOT / 'Scripts/Menu/Artwork/GameplayStatus'
FOLDER = '/Game/UI/Gameplay'
PANEL = '/Game/UI/Minimap/WBP_Minimap_Floorplan'
SETTINGS = '/Game/UI/Settings/WBP_Setting'
FONT = '/Game/Environment/Font/HSBombaram3_0_Regular_Font'
OWNER_KEY, OWNER = 'CatrunGameplayHUD', 'GameplayExpansion20261124'
MARKERS = {'Exit': 19, 'ClosedDoor': 14, 'OpenDoor': 14, 'FixedOpening': 12, 'CatHole': 16, 'Candle': 19}
ENUM = {'Exit': 'EXIT', 'ClosedDoor': 'CLOSED_DOOR', 'OpenDoor': 'OPEN_DOOR',
        'FixedOpening': 'FIXED_OPENING', 'CatHole': 'CAT_HOLE'}
MAPS = ('Tutorial', 'Stage1', 'Stage2')
HOLES = {'Tutorial': ['Tutorial'], 'Stage1': ['Banquet', 'SmallRoom'], 'Stage2': ['06', '13']}
AUDIT = bool(globals().get('CATRUN_HUD_AUDIT', False)) or '-catrunhudaudit' in u.SystemLibrary.get_command_line().lower()
OUT = ROOT / 'Saved/GameplayExpansion20261124/HUD' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
SAVED = []


def save(asset):
    assert not AUDIT and AS.save_loaded_asset(asset, False), asset
    SAVED.append(asset.get_path_name().split('.')[0])


def owned(name, make):
    path = FOLDER + '/' + name
    if AS.does_asset_exist(path):
        obj = AS.load_asset(path)
        assert AS.get_metadata_tag(obj, OWNER_KEY) == OWNER, ('Existing unrelated asset', path)
        return obj
    assert not AUDIT, path
    obj = make()
    assert obj and obj.get_path_name().split('.')[0] == path, path
    AS.set_metadata_tag(obj, OWNER_KEY, OWNER)
    save(obj)
    return obj


def texture(kind):
    source = ART / (kind + '.png')
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    name = 'T_Gameplay_' + kind

    def create():
        task = properties(u.AssetImportTask(), filename=str(source), destination_path=FOLDER,
                          destination_name=name, automated=True, replace_existing=False, save=False)
        u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        paths = task.get_editor_property('imported_object_paths')
        assert len(paths) == 1, paths
        obj = AS.load_asset(paths[0])
        properties(obj, compression_settings=u.TextureCompressionSettings.TC_EDITOR_ICON,
                   lod_group=u.TextureGroup.TEXTUREGROUP_UI, mip_gen_settings=u.TextureMipGenSettings.TMGS_NO_MIPMAPS,
                   address_x=u.TextureAddress.TA_CLAMP, address_y=u.TextureAddress.TA_CLAMP, never_stream=True)
        AS.set_metadata_tag(obj, 'SourcePngSHA256', digest)
        return obj

    obj = owned(name, create)
    assert AS.get_metadata_tag(obj, 'SourcePngSHA256') == digest, name
    return obj


def brush_size(image, texture_asset, size):
    image.set_brush_from_texture(texture_asset, False)
    brush = image.get_editor_property('brush')
    value = brush.get_editor_property('image_size')
    assert value.import_text(f'(X={size:.6f},Y={size:.6f})')
    brush.set_editor_property('image_size', value)
    properties(image, brush=brush, visibility=u.SlateVisibility.HIT_TEST_INVISIBLE)


def marker(kind, icon):
    name = 'WBP_Landmark_' + kind

    def create():
        bp = ui('CreateWidgetBlueprint', FOLDER, name, u.UserWidget.static_class())
        brush_size(add(bp, u.Image, 'Icon', None), icon, MARKERS[kind])
        compile_bp(bp)
        return bp

    bp = owned(name, create)
    assert widgets(bp)['Icon'].get_editor_property('brush').get_editor_property('resource_object') == icon
    return bp.generated_class()


def floorplan_material():
    name = 'M_Gameplay_Floorplan'

    def create():
        edit = u.MaterialEditingLibrary
        mat = u.AssetToolsHelpers.get_asset_tools().create_asset(name, FOLDER, u.Material, u.MaterialFactoryNew())
        properties(mat, material_domain=u.MaterialDomain.MD_UI, blend_mode=u.BlendMode.BLEND_TRANSLUCENT)
        image = edit.create_material_expression(mat, u.MaterialExpressionTextureSampleParameter2D, -670, 80)
        properties(image, parameter_name='Floorplan', texture=AS.load_asset('/Game/UI/Minimap/T_Floorplan_Stage1'))
        neutral = edit.create_material_expression(mat, u.MaterialExpressionDesaturation, -400, -70)
        tint = edit.create_material_expression(mat, u.MaterialExpressionVectorParameter, -400, -270)
        properties(tint, parameter_name='WarmGray', default_value=u.LinearColor(.84, .78, .72, 1.))
        multiply = edit.create_material_expression(mat, u.MaterialExpressionMultiply, -180, -100)
        assert edit.connect_material_expressions(image, '', neutral, '')
        assert edit.connect_material_expressions(neutral, '', multiply, 'A')
        assert edit.connect_material_expressions(tint, '', multiply, 'B')
        assert edit.connect_material_property(multiply, '', u.MaterialProperty.MP_EMISSIVE_COLOR)
        assert edit.connect_material_property(image, 'A', u.MaterialProperty.MP_OPACITY)
        errors = edit.recompile_material(mat)
        assert not errors, errors
        return mat

    return owned(name, create)


def minimap(textures):
    panel = AS.load_asset(PANEL)
    default = u.get_default_object(panel.generated_class())
    markers = {name: marker(name, textures[name]) for name in MARKERS}
    classes = {getattr(u.CatrunMapLandmark, key): markers[name] for name, key in ENUM.items()}
    material = floorplan_material()
    if (dict(default.get_editor_property('landmark_marker_classes')) != classes
            or default.get_editor_property('candle_marker_class') != markers['Candle']
            or default.get_editor_property('floorplan_material') != material):
        assert not AUDIT
        panel.modify()
        properties(default, landmark_marker_classes=classes, candle_marker_class=markers['Candle'], floorplan_material=material)
        save(panel)
    assert default.get_editor_property('player_marker_class').get_name() == 'WBP_MinimapMarker_Cat_C'
    assert default.get_editor_property('armor_marker_class').get_name() == 'WBP_MinimapMarker_Armor_C'


def text(bp, name, value, parent, size, variable=False):
    block = add(bp, u.TextBlock, name, parent, variable)
    ink = u.SlateColor(specified_color=u.LinearColor(.92, .88, .81, 1.))
    font = u.SlateFontInfo(font_object=AS.load_asset(FONT), typeface_font_name='Default', size=size)
    properties(block, text=u.Text(value), font=font, color_and_opacity=ink,
               shadow_color_and_opacity=u.LinearColor(.025, .021, .020, .8), shadow_offset=u.Vector2D(0, 1),
               visibility=u.SlateVisibility.HIT_TEST_INVISIBLE)
    return block


def at(w, x, y, width, height):
    canvas_slot(w, (0, 0), (0, 0), (x, y, width, height))
    return w


def status(textures):
    def create():
        bp = ui('CreateWidgetBlueprint', FOLDER, 'WBP_PlayerStatus',
                u.load_class(None, '/Script/Catrun.CatrunPlayerStatusWidget'))
        root = add(bp, u.CanvasPanel, 'ReadoutRoot', None)
        card = add(bp, u.Border, 'StatusContent', root)
        properties(card, brush_color=u.LinearColor(.027, .024, .026, .73), padding=u.Margin(0),
                   horizontal_alignment=u.HorizontalAlignment.H_ALIGN_FILL, vertical_alignment=u.VerticalAlignment.V_ALIGN_FILL)
        canvas_slot(card, (0, 1), (0, 1), (24, -24, 280, 139), alignment=(0, 1))
        layout = add(bp, u.CanvasPanel, 'StatusLayout', card)
        for index, (role, title, bar_name, value_name) in enumerate((
                ('Stamina', '기력', 'StaminaBar', 'StaminaText'), ('Bell', '방울', 'BellProgress', 'BellRemainingText'))):
            y = 9 + 40 * index
            icon = at(add(bp, u.Image, role + 'Icon', layout), 12, y + 1, 25, 25)
            brush_size(icon, textures[role], 25)
            at(text(bp, role + 'Title', title, layout, 16), 47, y, 55, 23)
            value = at(text(bp, value_name, '100' if not index else '준비', layout, 16, True), 194, y, 72, 23)
            properties(value, justification=u.TextJustify.RIGHT)
            bar = at(add(bp, u.ProgressBar, bar_name, layout, True), 48, y + 25, 217, 5)
            style = bar.get_editor_property('widget_style')
            for field, tint in [('background_image', u.LinearColor(.16, .14, .13, .95)),
                                ('fill_image', u.LinearColor(1, 1, 1, 1))]:
                brush = style.get_editor_property(field)
                brush.set_editor_property('tint_color', u.SlateColor(specified_color=tint))
                style.set_editor_property(field, brush)
            properties(bar, widget_style=style, percent=1.)
        at(text(bp, 'BellReasonText', '', layout, 14, True), 100, 51, 92, 21)
        at(text(bp, 'ClockText', '남은 시간   10:00', layout, 16, True), 16, 88, 249, 49)
        compile_bp(bp)
        properties(u.get_default_object(bp.generated_class()), is_focusable=False, visibility=u.SlateVisibility.HIT_TEST_INVISIBLE)
        return bp

    bp = owned('WBP_PlayerStatus', create)
    tree = widgets(bp)
    assert all(isinstance(tree[n], u.ProgressBar) for n in ('StaminaBar', 'BellProgress'))
    assert all(isinstance(tree[n], u.TextBlock) for n in ('StaminaText', 'BellRemainingText', 'BellReasonText', 'ClockText'))
    assert not u.get_default_object(bp.generated_class()).get_editor_property('is_focusable')


def settings_dialog():
    bp = AS.load_asset(SETTINGS)
    tree = widgets(bp)
    graph = BP.get_graph(bp, 'ConfirmSettingsRestart')
    assert graph
    calls = BP.get_node_infos(BP.find_nodes(graph))
    assert sum(str(i.type_id).endswith('|RestartFromSettings') or str(i.type_id).endswith('.RestartFromSettings') for i in calls) == 1, [
        str(i.type_id) for i in calls]
    if 'RestartConfirmPanel' not in tree:
        assert not AUDIT and any(i.node.get_class().get_name() == 'K2Node_IfThenElse' for i in calls)
        bp.modify()
        # The original bound OnClicked keeps calling this same wrapper. Replace only its old two-click gate.
        q = Graph(graph)
        start = entry(q)
        editor(graph).remove_nodes([n for n in BP.find_nodes(graph) if n != start])
        q.chain(start, q.fn('/Script/Catrun.CatrunSettingsWidget.RestartFromSettings'))
        properties(tree['RestartButtonText'], text=u.Text('스테이지 처음부터 다시 시작'))
        modal = add(bp, u.Border, 'RestartConfirmPanel', tree['CanvasPanel_29'], True)
        canvas_slot(modal, (0, 0), (1, 1), (0, 0, 0, 0), order=20)
        properties(modal, visibility=u.SlateVisibility.COLLAPSED, brush_color=u.LinearColor(.016, .014, .017, .94),
                   horizontal_alignment=u.HorizontalAlignment.H_ALIGN_CENTER, vertical_alignment=u.VerticalAlignment.V_ALIGN_CENTER)
        width = add(bp, u.SizeBox, 'ResetDialogWidth', modal)
        width.set_width_override(430)
        stack = add(bp, u.VerticalBox, 'ResetDialogStack', width)
        text(bp, 'ResetTitle', '스테이지 처음부터 다시 시작', stack, 27)
        explanation = text(bp, 'ResetDetail', '현재 스테이지의 퍼즐 진행과 남은 시간을 초기화합니다. 해금한 구역은 유지됩니다.', stack, 19)
        properties(explanation, auto_wrap_text=True)
        properties(explanation.get_editor_property('slot'), padding=u.Margin(0, 14, 0, 23))
        row = add(bp, u.HorizontalBox, 'ResetActions', stack)
        for name, label in [('RestartCancel', '취소'), ('RestartAccept', '초기화하고 다시 시작')]:
            button = add(bp, u.Button, name, row, True)
            properties(button, is_focusable=True, background_color=u.LinearColor(.24, .21, .18, 1.))
            child = text(bp, name + 'Label', label, button, 18)
            properties(child, margin=u.Margin(12, 5, 12, 5))
            properties(button.get_editor_property('slot'), padding=u.Margin(0, 0, 12, 0))
        compile_bp(bp)
        save(bp)
    tree = widgets(bp)
    assert str(tree['RestartButtonText'].get_text()) == '스테이지 처음부터 다시 시작'
    assert all(name in tree for name in ('RestartConfirmPanel', 'RestartAccept', 'RestartCancel'))
    assert not any(n.get_class().get_name() == 'K2Node_IfThenElse' for n in BP.find_nodes(graph))


def author_map(stage):
    package = '/Game/Maps/' + stage
    assert LEVEL.load_level(package)
    world = ED.get_editor_world()
    assert world.get_path_name().split('.')[0] == package and not ED.get_game_world()
    actors = list(ACTORS.get_all_level_actors())
    by = {actor.get_actor_label(): actor for actor in actors}
    [presenter] = [a for a in actors if isinstance(a, u.CatrunMinimapPresenter)]
    center = presenter.get_editor_property('MapCenter')
    size = presenter.get_editor_property('MapSize')
    yaw = math.radians(presenter.get_editor_property('CaptureYawDegrees'))
    changed = False
    sources = []

    def tag(actor, value):
        nonlocal changed
        if not actor.actor_has_tag(value):
            assert not AUDIT, (stage, actor.get_actor_label(), value)
            actor.modify()
            actor.set_editor_property('tags', list(actor.tags) + [u.Name(value)])
            changed = True

    def record(actor, kind, point):
        dx, dy = point.x - center.x, point.y - center.y
        uv = [.5 + (-math.sin(yaw)*dx + math.cos(yaw)*dy)/size.x,
              .5 - (math.cos(yaw)*dx + math.sin(yaw)*dy)/size.y]
        assert min(uv) >= 0. and max(uv) <= 1., (stage, actor.get_actor_label(), uv)
        sources.append({'label': actor.get_actor_label(), 'kind': kind, 'class': actor.get_class().get_path_name(),
                        'xyz': [round(getattr(point, axis), 2) for axis in 'xyz'], 'capture_uv': uv})

    zones = [a for a in actors if isinstance(a, u.CatrunNoBellZone)]
    for suffix in HOLES[stage]:
        zone = by['NoBell_CatHole_' + suffix]
        assert zone in zones
        tag(zone, 'CatrunMapCatHole')
        record(zone, 'CatHole', zone.get_editor_property('Box').get_world_location())
    if stage == 'Tutorial':
        exit_actor = by['BP_Tutorial_ExitToStage1']
        assert exit_actor.get_class().get_name() == 'BP_LevelExit_C'
        [box] = exit_actor.get_components_by_class(u.BoxComponent)
        assert box.get_name() == 'CollisionComp'
        tag(exit_actor, 'CatrunMapExit')
        record(exit_actor, 'Exit', box.get_world_location())
    else:
        [exit_actor] = [a for a in actors if isinstance(a, u.CatrunStageExit)]
        record(exit_actor, 'Exit', exit_actor.get_editor_property('Trigger').get_world_location())

    fixed = {'Tutorial': ['SM_Tutorial_Annex_DoorFrame_East', 'Door_Tutorial_Corridor'],
             'Stage1': ['S1_DoorFrame_ExitToStage2'],
             'Stage2': ['S2_Gate_' + n + '_Frame' for n in ('00', '03', '04', '07')]}[stage]
    for name in fixed:
        actor = by[name]
        if isinstance(actor, u.CatrunDoor):
            assert actor.get_editor_property('bStartOpen')
            point = actor.get_component_by_class(u.BoxComponent).get_world_location()
        else:
            assert isinstance(actor, u.StaticMeshActor) and actor.static_mesh_component.get_editor_property('static_mesh')
            point = actor.get_actor_bounds(False)[0]
        tag(actor, 'CatrunMapFixedOpening')
        record(actor, 'FixedOpening', point)
    if stage == 'Stage1':
        # Lower hall has a swung leaf and no frame actor. Use the measured wall opening from
        # the original align_check_doors probe. The leaf hinge lies 74 cm north of this opening.
        leaf = by['S1_Door_LowerHall_East_Open']
        opening = u.Vector(1050., 2330., 0.)
        assert leaf.actor_has_tag('OpenDoor_VisualBlockout') and (leaf.get_actor_location() - opening).length() < 115
        name = 'MapAnchor_S1_LowerHallEastOpening'
        anchor = by.get(name)
        if not anchor:
            assert not AUDIT
            anchor = ACTORS.spawn_actor_from_class(u.TargetPoint, opening, u.Rotator())
            anchor.set_actor_label(name)
        assert isinstance(anchor, u.TargetPoint) and (anchor.get_actor_location() - opening).length() < .1
        tag(anchor, 'CatrunMapFixedOpening')
        record(anchor, 'FixedOpening', opening)
    if stage == 'Stage2':
        [puzzle] = [a for a in actors if isinstance(a, u.CatrunStatuePuzzle)]
        gates = {str(link.get_editor_property('PuzzleId')): link.get_editor_property('Gate')
                 for link in puzzle.get_editor_property('Links')}
        assert set(gates) == {'A', 'B', 'C'}
        for puzzle_id, gate in gates.items():
            record(gate, 'Puzzle ' + puzzle_id, gate.get_actor_bounds(False)[0])
    for actor in actors:
        if isinstance(actor, u.CatrunDoor) and not actor.actor_has_tag('CatrunMapFixedOpening'):
            record(actor, 'SwingDoor', actor.get_component_by_class(u.BoxComponent).get_world_location())
    if changed:
        assert LEVEL.save_current_level()
        SAVED.append(package)
    return sources


def main():
    assert u.load_class(None, '/Script/UMGToolSet.UMGToolSet'), 'Launch with -EnablePlugins=UMGToolSet'
    assert not ED.get_game_world()
    # Switching maps must not discard a live map being edited by another process or user.
    assert not u.EditorLoadingAndSavingUtils.get_dirty_map_packages()
    ui_targets = {PANEL, SETTINGS, FOLDER + '/WBP_PlayerStatus', FOLDER + '/M_Gameplay_Floorplan'}
    ui_targets.update(FOLDER + '/WBP_Landmark_' + kind for kind in MARKERS)
    ui_targets.update(FOLDER + '/T_Gameplay_' + kind for kind in (*MARKERS, 'Stamina', 'Bell'))
    dirty_targets = ui_targets.intersection(
        pkg.get_path_name() for pkg in u.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    assert not dirty_targets, ('HUD target packages have pending editor changes', sorted(dirty_targets))
    original_world = ED.get_editor_world().get_path_name().split('.')[0]
    OUT.mkdir(parents=True)
    if not AUDIT:
        for package in (PANEL, SETTINGS, *('/Game/Maps/' + s for s in MAPS)):
            path = Path('Content') / package.removeprefix('/Game/')
            src = ROOT / path.with_suffix('.umap' if '/Maps/' in package else '.uasset')
            dest = OUT / 'Before' / src.relative_to(ROOT)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
    textures = {name: texture(name) for name in (*MARKERS, 'Stamina', 'Bell')}
    minimap(textures)
    status(textures)
    settings_dialog()
    maps = {stage: author_map(stage) for stage in MAPS}
    if original_world.startswith('/Game/') and original_world != '/Game/Maps/Stage2':
        assert LEVEL.load_level(original_world)
    report = {'audit': AUDIT, 'maps': maps, 'saved_packages': SAVED}
    (OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    u.log('CATRUN_HUD_OK ' + str(OUT / 'report.json'))


if __name__ == '__main__':
    main()
