"""Update only the saved floorplan widget, or cold-audit it with -catrunMinimapHoldAudit."""

import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import zlib

import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts/Menu'))

from menu_graph import add, compile_bp, properties, ui, widgets


FOLDER = '/Game/UI/Minimap'
PANEL_NAME = 'WBP_Minimap_Floorplan'
PANEL_PATH = f'{FOLDER}/{PANEL_NAME}'
PANEL_OBJECT_PATH = f'{PANEL_PATH}.{PANEL_NAME}'
OWNER_TAG = 'CatrunMinimapAuthor'
OWNER = 'CatrunMinimapFloorplan'
FRAME_FOLDER = FOLDER + '/Textures'
FRAME_NAME = 'T_Minimap_FloorplanFrame'
FRAME_PATH = f'{FRAME_FOLDER}/{FRAME_NAME}'
FRAME_OWNER = 'CatrunMinimapFloorplanFrame'
FRAME_HASH_TAG = 'CatrunMinimapFrameSHA256'
MARKER_CLASSES = {
    'player_marker_class': 'Cat',
    'armor_marker_class': 'Armor',
    'candle_marker_class': 'Candle',
}
PANEL_DEFAULTS = {'hold_size_multiplier': 1.25, 'neighborhood_coverage': 1.80}
FRAME_PADDING = 10.0
MAP_OPACITY = 0.82
BACKDROP_NAME = 'MinimapBackdrop'
BACKDROP_COLOR = (0.018, 0.025, 0.036, 0.30)
BACKDROP_ORDER = -1
SURFACE_SLOT = ((0, 0, 1, 1), (0, 0, 0, 0), (0, 0))
FRAME_SIDE = 64
FRAME_SLICE = 8
FRAME_RIM_WIDTH = 2
FRAME_CORNER_RADIUS = 5
FRAME_FILL_OPACITY = 0.10
FRAME_FILL_COLOR = (22, 29, 40)
FRAME_RIM_COLOR = (163, 184, 208)
AS = u.EditorAssetLibrary


def png_chunk(kind, payload):
    return (struct.pack('>I', len(payload)) + kind + payload
            + struct.pack('>I', zlib.crc32(kind + payload)))


def rgba_png(side, scanlines):
    header = struct.pack('>IIBBBBB', side, side, 8, 6, 0, 0, 0)
    return (b'\x89PNG\r\n\x1a\n' + png_chunk(b'IHDR', header)
            + png_chunk(b'IDAT', zlib.compress(scanlines, 9)) + png_chunk(b'IEND', b''))


def frame_inset(x, y):
    half = FRAME_SIDE / 2
    radius = FRAME_CORNER_RADIUS
    qx = abs(x - half) - half + radius
    qy = abs(y - half) - half + radius
    return radius - math.hypot(max(qx, 0), max(qy, 0)) - min(max(qx, qy), 0)


def frame_png():
    """Build rounded corners and fixed-width edges for Slate's 9-slice brush."""
    samples = 4
    scanlines = bytearray()
    for y in range(FRAME_SIDE):
        scanlines.append(0)  # PNG filter None
        for x in range(FRAME_SIDE):
            rim = fill = bevel = 0
            for sy in range(samples):
                for sx in range(samples):
                    inset = frame_inset(x + (sx + .5) / samples, y + (sy + .5) / samples)
                    if 0 <= inset < FRAME_RIM_WIDTH:
                        rim += 1
                        bevel += inset / FRAME_RIM_WIDTH
                    elif inset >= FRAME_RIM_WIDTH:
                        fill += FRAME_FILL_OPACITY
            coverage = rim + fill
            if rim:
                # Shade the outer bevel and add a broad, static reflection near the upper-left corner.
                glint = max(0, 1 - abs(x + y * .7 - FRAME_SIDE * .28) / (FRAME_SIDE * .20))
                light = .60 + .34 * bevel / rim + .13 * (1 - y / FRAME_SIDE) + .14 * glint * glint
                color = tuple(round(min(255, (channel * light * rim + base * fill) / coverage))
                              for channel, base in zip(FRAME_RIM_COLOR, FRAME_FILL_COLOR))
            else:
                color = FRAME_FILL_COLOR
            scanlines.extend((*color, round(255 * coverage / (samples * samples))))
    return rgba_png(FRAME_SIDE, scanlines)


def import_frame(png, digest):
    source = ROOT / 'Saved/MinimapRepair20261116/FrameSource' / f'{FRAME_NAME}.png'
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(png)
    task = properties(u.AssetImportTask(), filename=str(source), destination_path=FRAME_FOLDER,
                      destination_name=FRAME_NAME, automated=True, replace_existing=False, save=False)
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    paths = list(task.get_editor_property('imported_object_paths'))
    assert len(paths) == 1 and paths[0].split('.')[0] == FRAME_PATH, paths
    texture = AS.load_asset(paths[0])
    assert isinstance(texture, u.Texture2D), paths
    properties(texture, compression_settings=u.TextureCompressionSettings.TC_EDITOR_ICON,
               lod_group=u.TextureGroup.TEXTUREGROUP_UI, mip_gen_settings=u.TextureMipGenSettings.TMGS_NO_MIPMAPS,
               address_x=u.TextureAddress.TA_CLAMP, address_y=u.TextureAddress.TA_CLAMP, never_stream=True)
    AS.set_metadata_tag(texture, OWNER_TAG, FRAME_OWNER)
    AS.set_metadata_tag(texture, FRAME_HASH_TAG, digest)
    return texture


def color_values(color):
    return (color.r, color.g, color.b, color.a)


def near(actual, expected):
    return math.isclose(actual, expected, abs_tol=0.00001)


def ensure_frame_texture(audit, pending):
    png = frame_png()
    digest = hashlib.sha256(png).hexdigest()
    if AS.does_asset_exist(FRAME_PATH):
        texture = AS.load_asset(FRAME_PATH)
    else:
        assert not audit, f'Missing minimap frame texture {FRAME_PATH}'
        texture = import_frame(png, digest)
        pending.append(texture)
    assert isinstance(texture, u.Texture2D) and AS.get_metadata_tag(texture, OWNER_TAG) == FRAME_OWNER, FRAME_PATH
    assert AS.get_metadata_tag(texture, FRAME_HASH_TAG) == digest, FRAME_PATH
    # A commandlet can read a placeholder size until the loaded texture is compiled.
    u.CatrunAuthoringLibrary.finish_asset_compilation()
    size = (texture.blueprint_get_size_x(), texture.blueprint_get_size_y())
    assert size == (FRAME_SIDE, FRAME_SIDE), (FRAME_PATH, size)
    for name, expected in (
        ('compression_settings', u.TextureCompressionSettings.TC_EDITOR_ICON),
        ('lod_group', u.TextureGroup.TEXTUREGROUP_UI),
        ('mip_gen_settings', u.TextureMipGenSettings.TMGS_NO_MIPMAPS),
        ('address_x', u.TextureAddress.TA_CLAMP),
        ('address_y', u.TextureAddress.TA_CLAMP),
        ('never_stream', True),
    ):
        assert texture.get_editor_property(name) == expected, name
    return texture


def slot_values(widget):
    slot = widget.get_editor_property('slot')
    anchors, offsets, alignment = slot.get_anchors(), slot.get_offsets(), slot.get_alignment()
    return ((anchors.minimum.x, anchors.minimum.y, anchors.maximum.x, anchors.maximum.y),
            (offsets.left, offsets.top, offsets.right, offsets.bottom),
            (alignment.x, alignment.y), slot.get_z_order(), slot.get_auto_size())


def panel_tree(panel):
    tree = widgets(panel)
    root, frame, surface, image, layer = (tree[name] for name in
        ('MinimapRoot', 'MinimapFrame', 'MapSurface', 'MapBackground', 'MarkerLayer'))
    assert isinstance(root, u.CanvasPanel) and isinstance(frame, u.Border)
    assert isinstance(surface, u.CanvasPanel) and isinstance(image, u.Image) and isinstance(layer, u.CanvasPanel)
    assert frame.get_parent() == root and surface.get_parent() == frame
    assert image.get_parent() == layer.get_parent() == surface
    assert slot_values(frame) == ((1, 0, 1, 0), (-24, 24, 240, 240), (1, 0), 0, False)
    for order, child in enumerate((image, layer)):
        assert slot_values(child) == (*SURFACE_SLOT, order, False), child
    backdrop = tree.get(BACKDROP_NAME)
    if backdrop:
        audit_backdrop(backdrop, surface)
    hint = tree.get('MapToggleHint')
    assert not hint or isinstance(hint, u.TextBlock) and hint.get_parent() == surface
    return frame, surface, image, layer, backdrop, hint


def add_backdrop(panel, surface):
    backdrop = add(panel, u.Border, BACKDROP_NAME, surface)
    brush = u.SlateBrush(draw_as=u.SlateBrushDrawType.BOX, margin=u.Margin(0),
                         tint_color=u.SlateColor(specified_color=u.LinearColor(1., 1., 1., 1.)))
    properties(backdrop, background=brush, brush_color=u.LinearColor(*BACKDROP_COLOR), padding=u.Margin(0),
               visibility=u.SlateVisibility.HIT_TEST_INVISIBLE)
    slot = backdrop.get_editor_property('slot')
    properties(slot, z_order=BACKDROP_ORDER, auto_size=False,
               layout_data=u.AnchorData(anchors=u.Anchors(minimum=u.Vector2D(0, 0), maximum=u.Vector2D(1, 1)),
                                         offsets=u.Margin(0), alignment=u.Vector2D(0, 0)))


def audit_backdrop(backdrop, surface):
    assert isinstance(backdrop, u.Border) and backdrop.get_parent() == surface, backdrop
    assert slot_values(backdrop) == (*SURFACE_SLOT, BACKDROP_ORDER, False), backdrop
    assert backdrop.get_editor_property('visibility') == u.SlateVisibility.HIT_TEST_INVISIBLE, backdrop
    assert near(backdrop.get_editor_property('render_opacity'), 1.), backdrop
    transform = backdrop.get_editor_property('render_transform')
    assert (transform.translation.x, transform.translation.y, transform.scale.x, transform.scale.y,
            transform.shear.x, transform.shear.y, transform.angle) == (0, 0, 1, 1, 0, 0, 0), backdrop
    brush = backdrop.get_editor_property('background')
    tint = brush.get_editor_property('tint_color')
    assert brush.get_editor_property('resource_object') is None, backdrop
    assert brush.get_editor_property('draw_as') == u.SlateBrushDrawType.BOX, backdrop
    assert tint.get_editor_property('color_use_rule') == u.SlateColorStylingMode.USE_COLOR_SPECIFIED, backdrop
    assert color_values(tint.get_editor_property('specified_color')) == (1., 1., 1., 1.), backdrop
    color = color_values(backdrop.get_editor_property('brush_color'))
    assert all(near(actual, expected) for actual, expected in zip(color, BACKDROP_COLOR)), color


def audit_marker_classes(defaults):
    for prop, kind in MARKER_CLASSES.items():
        name = f'WBP_MinimapMarker_{kind}'
        marker_class = defaults.get_editor_property(prop)
        assert marker_class and marker_class.get_path_name() == f'{FOLDER}/{name}.{name}_C', prop
    assert not defaults.get_editor_property('is_focusable')
    assert defaults.get_editor_property('visibility') == u.SlateVisibility.HIT_TEST_INVISIBLE


def layout_changes(frame, surface, image, layer, texture):
    brush = frame.get_editor_property('background')
    tint = brush.get_editor_property('tint_color')
    white = (1., 1., 1., 1.)
    padding = frame.get_editor_property('padding')
    image_tint = image.get_editor_property('color_and_opacity')
    expected = [
        (frame, 'brush_color', color_values(frame.get_editor_property('brush_color')) == white,
         u.LinearColor(*white)),
        (frame, 'padding', padding.left == padding.top == padding.right == padding.bottom == FRAME_PADDING,
         u.Margin(FRAME_PADDING, FRAME_PADDING, FRAME_PADDING, FRAME_PADDING)),
        (surface, 'clipping', surface.get_editor_property('clipping') == u.WidgetClipping.CLIP_TO_BOUNDS_ALWAYS,
         u.WidgetClipping.CLIP_TO_BOUNDS_ALWAYS),
        (layer, 'clipping', layer.get_editor_property('clipping') == u.WidgetClipping.INHERIT,
         u.WidgetClipping.INHERIT),
        (image, 'color_and_opacity', near(image_tint.a, MAP_OPACITY),
         u.LinearColor(image_tint.r, image_tint.g, image_tint.b, MAP_OPACITY)),
    ]
    changes = [(widget, name, value) for widget, name, matches, value in expected if not matches]
    margin = brush.get_editor_property('margin')
    slice_margin = FRAME_SLICE / FRAME_SIDE
    size = brush.get_editor_property('image_size')
    expected_size = f'(X={FRAME_SIDE:.6f},Y={FRAME_SIDE:.6f})'
    if (brush.get_editor_property('resource_object') != texture
            or brush.get_editor_property('draw_as') != u.SlateBrushDrawType.BOX
            or not margin.left == margin.top == margin.right == margin.bottom == slice_margin
            or size.export_text() != expected_size
            or brush.get_editor_property('tiling') != u.SlateBrushTileType.NO_TILE
            or brush.get_editor_property('mirroring') != u.SlateBrushMirrorType.NO_MIRROR
            or tint.get_editor_property('color_use_rule') != u.SlateColorStylingMode.USE_COLOR_SPECIFIED
            or color_values(tint.get_editor_property('specified_color')) != white):
        brush = u.SlateBrush(draw_as=u.SlateBrushDrawType.BOX,
                             tint_color=u.SlateColor(specified_color=u.LinearColor(*white)))
        assert size.import_text(expected_size), expected_size
        brush.set_editor_property('image_size', size)
        brush.set_editor_property('margin', u.Margin(slice_margin, slice_margin, slice_margin, slice_margin))
        brush.set_editor_property('resource_object', texture)
        changes.append((frame, 'background', brush))
    return changes


def update_panel(panel, texture, audit):
    assert panel and panel.get_path_name() == PANEL_OBJECT_PATH, PANEL_OBJECT_PATH
    assert AS.get_metadata_tag(panel, OWNER_TAG) == OWNER, PANEL_PATH
    frame, surface, image, layer, backdrop, hint = panel_tree(panel)
    defaults = u.get_default_object(panel.generated_class())
    audit_marker_classes(defaults)
    changes = layout_changes(frame, surface, image, layer, texture)
    defaults_match = all(near(defaults.get_editor_property(k), v) for k, v in PANEL_DEFAULTS.items())
    changed = bool(hint or changes or not backdrop or not defaults_match)
    if changed:
        assert not audit, ('Minimap panel needs migration', bool(hint), bool(backdrop),
                           [name for _, name, _ in changes], defaults_match)
        panel.modify()
        if hint:
            ui('RemoveWidget', panel, hint)
        if not backdrop:
            add_backdrop(panel, surface)
        for widget, name, value in changes:
            widget.modify()
            properties(widget, **{name: value})
        compile_bp(panel)
        defaults = u.get_default_object(panel.generated_class())
        defaults.modify()
        properties(defaults, **PANEL_DEFAULTS)
    frame, surface, image, layer, backdrop, hint = panel_tree(panel)
    assert backdrop and not hint and not layout_changes(frame, surface, image, layer, texture)
    audit_marker_classes(defaults)
    for name, value in PANEL_DEFAULTS.items():
        assert near(defaults.get_editor_property(name), value), name
    return changed


def dirty_packages():
    saving = u.EditorLoadingAndSavingUtils
    packages = list(saving.get_dirty_content_packages()) + list(saving.get_dirty_map_packages())
    return {package.get_name() for package in packages}


def file_hash(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def package_hashes():
    content = ROOT / 'Content'
    owned = content / 'UI/Minimap' / PANEL_NAME
    suffixes = {'.uasset', '.umap', '.uexp', '.ubulk', '.uptnl'}
    protected, panel_files = {}, {}
    for folder in ('UI/Minimap', 'Maps', '__ExternalActors__/Maps', '__ExternalObjects__/Maps'):
        for path in (content / folder).rglob('*'):
            if path.is_file() and path.suffix in suffixes:
                files = panel_files if path.with_suffix('') == owned else protected
                files[path] = file_hash(path)
    assert owned.with_suffix('.uasset') in panel_files, owned
    return protected, panel_files


def backup_panel(panel_files):
    destination = ROOT / 'Saved/PresentationFix20261119/MinimapPanelBackups'
    destination.mkdir(parents=True, exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix='Before-', dir=destination))
    for path, sha in panel_files.items():
        copy = backup / path.name
        shutil.copy2(path, copy)
        assert file_hash(copy) == sha, copy
    return backup


def main(audit_flag='-catrunminimapholdaudit'):
    audit = audit_flag in u.SystemLibrary.get_command_line().lower().split()
    assert not u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
    before = dirty_packages()
    assert not before.intersection({PANEL_PATH, FRAME_PATH}), before
    protected, panel_files = package_hashes()
    panel = AS.load_asset(PANEL_PATH)
    texture = ensure_frame_texture(True, [])
    changed = update_panel(panel, texture, audit)
    assert dirty_packages() <= before | ({PANEL_PATH} if changed else set()), dirty_packages()
    saved = []
    backup = None
    if changed:
        assert package_hashes() == (protected, panel_files), 'Minimap package files changed before save'
        backup = backup_panel(panel_files)
        print('CATRUN_MINIMAP_PANEL_BACKUP', str(backup))
        assert AS.save_loaded_asset(panel, False), panel
        saved.append(panel.get_path_name())
    assert dirty_packages() == before, dirty_packages()
    protected_after, panel_files_after = package_hashes()
    assert protected_after == protected, sorted(str(path) for path in protected.keys() | protected_after.keys()
                                                if protected.get(path) != protected_after.get(path))
    if not changed:
        assert panel_files_after == panel_files, 'Minimap panel changed during read-only validation'
    frame, _, image, layer, backdrop, _ = panel_tree(panel)
    defaults = u.get_default_object(panel.generated_class())
    print('CATRUN_MINIMAP_HOLD', json.dumps({
        'mode': 'audit' if audit else 'author',
        'panel': panel.get_path_name(), 'frame_texture': texture.get_path_name(),
        'widget_defaults': {name: defaults.get_editor_property(name) for name in PANEL_DEFAULTS},
        'frame_slot': slot_values(frame), 'frame_padding': frame.get_editor_property('padding').left,
        'map_opacity': image.get_editor_property('color_and_opacity').a,
        'map_slot': slot_values(image), 'marker_slot': slot_values(layer),
        'backdrop': {'name': backdrop.get_name(), 'parent': backdrop.get_parent().get_name(),
                     'slot': slot_values(backdrop), 'color': color_values(backdrop.get_editor_property('brush_color'))},
        'rim_width': FRAME_RIM_WIDTH, 'slice_margin': FRAME_SLICE / FRAME_SIDE,
        'frame_fill_opacity': FRAME_FILL_OPACITY,
        'frame_png_sha256': AS.get_metadata_tag(texture, FRAME_HASH_TAG), 'saved_assets': saved,
        'protected_file_count': len(protected), 'backup': str(backup) if backup else None,
        'panel_sha256_before': {path.name: sha for path, sha in panel_files.items()},
        'panel_sha256_after': {path.name: sha for path, sha in panel_files_after.items()},
    }, separators=(',', ':')))


if __name__ == '__main__':
    main()
