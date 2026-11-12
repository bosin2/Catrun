"""Import captured map PNGs, author the minimap UI and connect the six saved maps.

Run in Unreal Python with -catrunMinimapAuthor or -catrunMinimapAuditOnly and
-catrunMinimapManifest=<path>. The manifest contains a maps dictionary keyed by
level short name, with image (PNG path), center (XY), size (width/height), and yaw.
The audit mode reads saved assets in a fresh editor commandlet.
"""

from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import struct
import sys
import traceback
import unreal as u


ROOT = Path(u.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts/Menu'))
from menu_graph import BP, add, compile_bp, properties, ui, widgets
from minimap_geometry import MAP_NAMES

FOLDER = '/Game/UI/Minimap'
OWNER_TAG = 'CatrunMinimapAuthor'
OWNER_VALUE = 'CatrunMinimapV1'
AS = u.EditorAssetLibrary
EDIT = u.MaterialEditingLibrary
ASSETS = u.AssetToolsHelpers.get_asset_tools()
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
EDITOR = u.get_editor_subsystem(u.UnrealEditorSubsystem)
ACTORS = u.get_editor_subsystem(u.EditorActorSubsystem)
OUT = ROOT / 'Saved/GameplayRepair20261112/Minimap' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
REPORT = {'complete': False, 'maps': {}, 'saved_assets': [], 'saved_maps': []}
NEW_ASSETS = []


def dirty():
    packages = list(u.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    packages += list(u.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    return {package.get_name() for package in packages}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_manifest():
    command = u.SystemLibrary.get_command_line()
    audit = '-catrunminimapauditonly' in command.lower().split()
    assert audit != ('-catrunminimapauthor' in command.lower().split()), 'Choose author or audit mode'
    arg = re.search(r'(?:^|\s)-catrunMinimapManifest=(?:"([^"]+)"|(\S+))', command, re.I)
    assert arg, 'Missing -catrunMinimapManifest'
    path = Path(arg.group(1) or arg.group(2)).resolve()
    data = json.loads(path.read_text(encoding='utf-8'))['maps']
    assert set(data) == set(MAP_NAMES), list(data)
    for name in MAP_NAMES:
        row = data[name]
        row['image'] = (path.parent / row['image']).resolve()
        with row['image'].open('rb') as stream:
            header = stream.read(24)
        assert header[:8] == b'\x89PNG\r\n\x1a\n' and header[12:16] == b'IHDR', row['image']
        width, height = struct.unpack('>II', header[16:24])
        assert width == height and width > 0, (name, width, height)
        assert len(row['center']) == len(row['size']) == 2, (name, row)
        assert all(math.isfinite(value) for value in (*row['center'], *row['size'], row['yaw'])), (name, row)
        assert row['size'][0] == row['size'][1] > 0, (name, row)
        row['pixels'] = width
        row['image_sha256'] = digest(row['image'])
    REPORT.update(audit_only=audit, manifest=str(path))
    return audit, data


def owned_asset(name, audit, create):
    path = f'{FOLDER}/{name}'
    if AS.does_asset_exist(path):
        asset = AS.load_asset(path)
        assert asset and AS.get_metadata_tag(asset, OWNER_TAG) == OWNER_VALUE, path
        return asset
    assert not audit, path
    asset = create()
    assert asset and asset.get_path_name().split('.')[0] == path, path
    AS.set_metadata_tag(asset, OWNER_TAG, OWNER_VALUE)
    NEW_ASSETS.append(asset)
    return asset


def import_background(name, row):
    # Interchange takes the package name from the PNG stem.
    source = OUT / f'{name}.png'
    shutil.copy2(row['image'], source)
    task = u.AssetImportTask()
    properties(task, filename=str(source), destination_path=FOLDER, destination_name=name,
               automated=True, replace_existing=False, save=False)
    ASSETS.import_asset_tasks([task])
    paths = task.get_editor_property('imported_object_paths')
    assert len(paths) == 1, paths
    texture = AS.load_asset(paths[0])
    assert isinstance(texture, u.Texture2D), paths
    properties(texture, compression_settings=u.TextureCompressionSettings.TC_EDITOR_ICON,
               lod_group=u.TextureGroup.TEXTUREGROUP_UI, mip_gen_settings=u.TextureMipGenSettings.TMGS_NO_MIPMAPS,
               address_x=u.TextureAddress.TA_CLAMP, address_y=u.TextureAddress.TA_CLAMP, never_stream=True)
    AS.set_metadata_tag(texture, 'CatrunMinimapImageSHA256', row['image_sha256'])
    return texture


def backgrounds(rows, audit):
    by_hash = {}
    result = {}
    for map_name in MAP_NAMES:
        row = rows[map_name]
        sha = row['image_sha256']
        if sha not in by_hash:
            name = 'T_Minimap_' + map_name
            by_hash[sha] = owned_asset(name, audit, lambda: import_background(name, row))
        texture = by_hash[sha]
        assert isinstance(texture, u.Texture2D) and AS.get_metadata_tag(texture, 'CatrunMinimapImageSHA256') == sha
        assert texture.blueprint_get_size_x() == texture.blueprint_get_size_y() == row['pixels'], map_name
        result[map_name] = texture
    return result


def marker_material():
    material = ASSETS.create_asset('M_MinimapMarker', FOLDER, u.Material, u.MaterialFactoryNew())
    properties(material, material_domain=u.MaterialDomain.MD_UI, blend_mode=u.BlendMode.BLEND_TRANSLUCENT)
    uv = EDIT.create_material_expression(material, u.MaterialExpressionTextureCoordinate, -600, 50)
    core = EDIT.create_material_expression(material, u.MaterialExpressionScalarParameter, -600, 220)
    glow = EDIT.create_material_expression(material, u.MaterialExpressionScalarParameter, -600, 380)
    tint = EDIT.create_material_expression(material, u.MaterialExpressionVectorParameter, -300, -180)
    opacity = EDIT.create_material_expression(material, u.MaterialExpressionCustom, -290, 100)
    properties(core, parameter_name='CoreRadius', default_value=.33)
    properties(glow, parameter_name='GlowOpacity', default_value=.78)
    properties(tint, parameter_name='DotColor', default_value=u.LinearColor(1., 1., 1., 1.))
    inputs = []
    for key in ('UV', 'CoreRadius', 'GlowOpacity'):
        item = u.CustomInput()
        item.set_editor_property('input_name', key)
        inputs.append(item)
    properties(opacity, inputs=inputs, output_type=u.CustomMaterialOutputType.CMOT_FLOAT1,
               description='Circular core and soft radial glow', code='''
float radius = length((UV - 0.5) * 2.0);
float edge = clamp(CoreRadius, 0.01, 0.8);
float core = 1.0 - smoothstep(edge, edge + 0.14, radius);
float glow = 1.0 - smoothstep(edge, 1.0, radius);
return saturate(core + glow * glow * GlowOpacity);
''')
    for source, input_name in ((uv, 'UV'), (core, 'CoreRadius'), (glow, 'GlowOpacity')):
        assert EDIT.connect_material_expressions(source, '', opacity, input_name), input_name
    assert EDIT.connect_material_property(tint, '', u.MaterialProperty.MP_EMISSIVE_COLOR)
    assert EDIT.connect_material_property(opacity, '', u.MaterialProperty.MP_OPACITY)
    EDIT.recompile_material(material)
    return material


def marker_instance(name, parent, tint):
    material = ASSETS.create_asset(name, FOLDER, u.MaterialInstanceConstant, u.MaterialInstanceConstantFactoryNew())
    EDIT.set_material_instance_parent(material, parent)
    EDIT.set_material_instance_vector_parameter_value(material, 'DotColor', tint)
    return material


def marker_size_text(size):
    return f'(X={size:.6f},Y={size:.6f})'


def marker_widget(name, material, size):
    bp = ui('CreateWidgetBlueprint', FOLDER, name, u.UserWidget.static_class())
    image = add(bp, u.Image, 'Dot', None)
    image.set_brush_from_material(material)
    brush = image.get_editor_property('brush')
    # Slate's single-precision brush vector is a distinct reflected struct.
    brush_size = brush.get_editor_property('image_size')
    assert brush_size.import_text(marker_size_text(size)), name
    brush.set_editor_property('image_size', brush_size)
    properties(image, brush=brush, visibility=u.SlateVisibility.HIT_TEST_INVISIBLE)
    compile_bp(bp)
    return bp


def canvas_slot(widget, anchors, offsets, alignment=(0, 0), order=0):
    properties(widget.get_editor_property('slot'), z_order=order, auto_size=False,
               layout_data=u.AnchorData(
                   anchors=u.Anchors(minimum=u.Vector2D(*anchors[0]), maximum=u.Vector2D(*anchors[1])),
                   offsets=u.Margin(*offsets), alignment=u.Vector2D(*alignment)))


def panel_widget(base_class, player, enemy):
    bp = ui('CreateWidgetBlueprint', FOLDER, 'WBP_Minimap', base_class)
    root = add(bp, u.CanvasPanel, 'MinimapRoot', None)
    frame = add(bp, u.Border, 'MinimapFrame', root)
    properties(frame, padding=u.Margin(1.5, 1.5, 1.5, 1.5), brush_color=u.LinearColor(.24, .25, .23, .9),
               horizontal_alignment=u.HorizontalAlignment.H_ALIGN_FILL, vertical_alignment=u.VerticalAlignment.V_ALIGN_FILL)
    canvas_slot(frame, ((1, 0), (1, 0)), (-24, 24, 172, 172), alignment=(1, 0))
    surface = add(bp, u.CanvasPanel, 'MapSurface', frame)
    image = add(bp, u.Image, 'MapBackground', surface, variable=True)
    layer = add(bp, u.CanvasPanel, 'MarkerLayer', surface, variable=True)
    properties(layer, clipping=u.WidgetClipping.CLIP_TO_BOUNDS)
    for order, widget in enumerate((image, layer)):
        canvas_slot(widget, ((0, 0), (1, 1)), (0, 0, 0, 0), order=order)
    compile_bp(bp)
    defaults = u.get_default_object(bp.generated_class())
    properties(defaults, player_marker_class=player.generated_class(), enemy_marker_class=enemy.generated_class(),
               is_focusable=False, visibility=u.SlateVisibility.HIT_TEST_INVISIBLE)
    return bp


def presenter_blueprint(base_class, widget):
    bp = BP.create(FOLDER, 'BP_MinimapPresenter', base_class)
    compile_bp(bp)
    properties(u.get_default_object(bp.generated_class()), widget_class=widget.generated_class())
    return bp


def presentation(audit):
    widget_class = u.load_class(None, '/Script/Catrun.CatrunMinimapWidget')
    presenter_class = u.load_class(None, '/Script/Catrun.CatrunMinimapPresenter')
    assert widget_class and presenter_class
    material = owned_asset('M_MinimapMarker', audit, marker_material)
    assert material.get_editor_property('material_domain') == u.MaterialDomain.MD_UI
    marker_bps = []
    for kind, color, size in (('Player', (.06, 1., .26), 20.), ('Enemy', (1., .04, .035), 16.)):
        material_name = f'MI_MinimapMarker_{kind}'
        marker_name = f'WBP_MinimapMarker_{kind}'
        tint = u.LinearColor(*color, 1.)
        instance = owned_asset(material_name, audit, lambda: marker_instance(material_name, material, tint))
        saved_tint = EDIT.get_material_instance_vector_parameter_value(instance, 'DotColor')
        assert all(math.isclose(getattr(saved_tint, channel), getattr(tint, channel), abs_tol=.0001)
                   for channel in ('r', 'g', 'b', 'a')), material_name
        marker = owned_asset(marker_name, audit, lambda: marker_widget(marker_name, instance, size))
        image = widgets(marker)['Dot']
        brush = image.get_editor_property('brush')
        assert brush.get_editor_property('resource_object') == instance
        brush_size = brush.get_editor_property('image_size').export_text()
        assert brush_size == marker_size_text(size), (marker_name, brush_size)
        marker_bps.append(marker)
    panel = owned_asset('WBP_Minimap', audit, lambda: panel_widget(widget_class, *marker_bps))
    tree = widgets(panel)
    assert tree['MapBackground'].get_parent() == tree['MarkerLayer'].get_parent() == tree['MapSurface']
    defaults = u.get_default_object(panel.generated_class())
    assert defaults.get_editor_property('player_marker_class') == marker_bps[0].generated_class()
    assert defaults.get_editor_property('enemy_marker_class') == marker_bps[1].generated_class()
    presenter = owned_asset('BP_MinimapPresenter', audit, lambda: presenter_blueprint(presenter_class, panel))
    assert u.get_default_object(presenter.generated_class()).get_editor_property('widget_class') == panel.generated_class()
    REPORT['widget'] = panel.get_path_name()
    return presenter_class, presenter.generated_class(), panel.generated_class()


def write_or_audit_level(name, row, texture, presenter_base, presenter_class, widget_class, audit):
    path = '/Game/Maps/' + name
    assert LEVEL.load_level(path), path
    world = EDITOR.get_editor_world()
    assert world and world.get_path_name().split('.')[0] == path and not EDITOR.get_game_world(), path
    assert not dirty(), dirty()
    # Loading a level can reinstance newly saved Blueprint classes. Resolve the
    # current generated classes after the load instead of retaining stale ones.
    presenter_class = AS.load_asset(FOLDER + '/BP_MinimapPresenter').generated_class()
    widget_class = AS.load_asset(FOLDER + '/WBP_Minimap').generated_class()
    assert u.get_default_object(presenter_class).get_editor_property('widget_class') == widget_class
    actors = u.GameplayStatics.get_all_actors_of_class(world, presenter_base)
    assert len(actors) <= 1, (path, len(actors))
    if actors:
        actor = actors[0]
        assert str(actor.get_class().get_path_name()) == str(presenter_class.get_path_name()), actor
        assert OWNER_VALUE in {str(tag) for tag in actor.get_editor_property('tags')}, actor
    else:
        assert not audit, f'Missing minimap presenter in {path}'
        actor = ACTORS.spawn_actor_from_class(presenter_class, u.Vector(), u.Rotator())
        assert actor, path
        actor.set_actor_label('Minimap Presenter')
        properties(actor, tags=[u.Name(OWNER_VALUE)], background_texture=texture,
                   map_center=u.Vector2D(*row['center']), map_size=u.Vector2D(*row['size']),
                   capture_yaw_degrees=row['yaw'])

    center = actor.get_editor_property('map_center')
    size = actor.get_editor_property('map_size')
    yaw = actor.get_editor_property('capture_yaw_degrees')
    assert [center.x, center.y] == row['center'] and [size.x, size.y] == row['size'] and yaw == row['yaw'], actor
    actual_widget = actor.get_editor_property('widget_class')
    assert actual_widget == widget_class, {
        'actor': actor.get_path_name(),
        'actual_widget': actual_widget.get_path_name() if actual_widget else None,
        'expected_widget': widget_class.get_path_name(),
        'default_widget': str(u.get_default_object(actor.get_class()).get_editor_property('widget_class')),
    }
    assert actor.get_editor_property('background_texture') == texture, actor
    if not actors:
        assert dirty() == {path}, dirty()
        assert LEVEL.save_current_level(), path
        REPORT['saved_maps'].append(path)
    assert not dirty(), dirty()
    REPORT['maps'][name] = {
        'presenter': actor.get_path_name(), 'texture': texture.get_path_name(), 'center': row['center'],
        'size': row['size'], 'yaw': yaw, 'image_sha256': row['image_sha256'],
        'map_sha256': digest(ROOT / 'Content/Maps' / f'{name}.umap'),
    }


def main():
    audit, rows = read_manifest()
    assert not dirty(), dirty()
    if not audit:
        backup = OUT / 'Before'
        backup.mkdir()
        for name in MAP_NAMES:
            shutil.copy2(ROOT / 'Content/Maps' / f'{name}.umap', backup)

    textures = backgrounds(rows, audit)
    classes = presentation(audit)
    assert dirty() <= {asset.get_path_name().split('.')[0] for asset in NEW_ASSETS}, dirty()
    for asset in NEW_ASSETS:
        assert AS.save_loaded_asset(asset, False), asset
        REPORT['saved_assets'].append(asset.get_path_name())
    assert not dirty(), dirty()
    for name in MAP_NAMES:
        write_or_audit_level(name, rows[name], textures[name], *classes, audit)
    REPORT['complete'] = True


OUT.mkdir(parents=True)
try:
    main()
except Exception:
    REPORT['error'] = traceback.format_exc()
    raise
finally:
    path = OUT / 'report.json'
    path.write_text(json.dumps(REPORT, ensure_ascii=False, indent=2), encoding='utf-8')
    u.log(f'CATRUN_MINIMAP_REPORT {path}')
