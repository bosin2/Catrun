"""Migrate the owned floorplan widget, or audit it with -catrunMinimapHoldAudit."""

import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import zlib

import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts/Menu'))

from menu_graph import compile_bp, properties, ui, widgets


FOLDER = '/Game/UI/Minimap'
PANEL_NAME = 'WBP_Minimap_Floorplan'
PANEL_PATH = f'{FOLDER}/{PANEL_NAME}'
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
PANEL_DEFAULTS = {'hold_size_multiplier': 1.25, 'neighborhood_coverage': 1.30}
FRAME_PADDING = 10.0
MAP_OPACITY = 0.68
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
    assert texture.blueprint_get_size_x() == texture.blueprint_get_size_y() == FRAME_SIDE, FRAME_PATH
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
        assert slot_values(child) == ((0, 0, 1, 1), (0, 0, 0, 0), (0, 0), order, False), child
    hint = tree.get('MapToggleHint')
    assert not hint or isinstance(hint, u.TextBlock) and hint.get_parent() == surface
    return frame, surface, image, layer, hint


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
    assert panel and AS.get_metadata_tag(panel, OWNER_TAG) == OWNER, PANEL_PATH
    frame, surface, image, layer, hint = panel_tree(panel)
    defaults = u.get_default_object(panel.generated_class())
    audit_marker_classes(defaults)
    changes = layout_changes(frame, surface, image, layer, texture)
    defaults_match = all(near(defaults.get_editor_property(k), v) for k, v in PANEL_DEFAULTS.items())
    changed = bool(hint or changes or not defaults_match)
    if changed:
        assert not audit, ('Minimap panel needs migration', bool(hint),
                           [name for _, name, _ in changes], defaults_match)
        panel.modify()
        if hint:
            ui('RemoveWidget', panel, hint)
        for widget, name, value in changes:
            widget.modify()
            properties(widget, **{name: value})
        compile_bp(panel)
        defaults = u.get_default_object(panel.generated_class())
        defaults.modify()
        properties(defaults, **PANEL_DEFAULTS)
    frame, surface, image, layer, hint = panel_tree(panel)
    assert not hint and not layout_changes(frame, surface, image, layer, texture)
    audit_marker_classes(defaults)
    for name, value in PANEL_DEFAULTS.items():
        assert near(defaults.get_editor_property(name), value), name
    return changed


def dirty_packages():
    saving = u.EditorLoadingAndSavingUtils
    packages = list(saving.get_dirty_content_packages()) + list(saving.get_dirty_map_packages())
    return {package.get_name() for package in packages}


def main(audit_flag='-catrunminimapholdaudit'):
    audit = audit_flag in u.SystemLibrary.get_command_line().lower().split()
    assert not u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
    before = dirty_packages()
    assert not before.intersection({PANEL_PATH, FRAME_PATH}), before
    panel = AS.load_asset(PANEL_PATH)
    assert panel and AS.get_metadata_tag(panel, OWNER_TAG) == OWNER, PANEL_PATH
    # Validate shape and marker classes before importing the frame.
    panel_tree(panel)
    audit_marker_classes(u.get_default_object(panel.generated_class()))
    pending = []
    texture = ensure_frame_texture(audit, pending)
    if update_panel(panel, texture, audit):
        pending.append(panel)
    assert dirty_packages() <= before | {asset.get_path_name().split('.')[0] for asset in pending}
    saved = []
    for asset in pending:
        assert AS.save_loaded_asset(asset, False), asset
        saved.append(asset.get_path_name())
    assert dirty_packages() == before, dirty_packages()
    print('CATRUN_MINIMAP_HOLD', json.dumps({
        'mode': 'audit' if audit else 'author',
        'panel': panel.get_path_name(), 'frame_texture': texture.get_path_name(),
        'widget_defaults': PANEL_DEFAULTS, 'frame_padding': FRAME_PADDING, 'map_opacity': MAP_OPACITY,
        'rim_width': FRAME_RIM_WIDTH, 'slice_margin': FRAME_SLICE / FRAME_SIDE,
        'frame_fill_opacity': FRAME_FILL_OPACITY,
        'frame_png_sha256': AS.get_metadata_tag(texture, FRAME_HASH_TAG), 'saved_assets': saved,
    }, separators=(',', ':')))


if __name__ == '__main__':
    main()
