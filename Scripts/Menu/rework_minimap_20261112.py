"""Author the floorplan panel and its three markers inside Unreal Python.

Import author_presentation from the map author. This module owns only its seven
new UI packages. The caller supplies map textures and presenter assignments.
"""

import hashlib
from pathlib import Path
import struct
import zlib

import unreal as u

from menu_graph import add, compile_bp, properties, ui, widgets


FOLDER = '/Game/UI/Minimap'
PANEL_NAME = 'WBP_Minimap_Floorplan'
OWNER_TAG = 'CatrunMinimapAuthor'
OWNER = 'CatrunMinimapFloorplan'
MARKER_HASH_TAG = 'CatrunMinimapMarkerSHA256'
AS = u.EditorAssetLibrary

# Closed outlines and inset fills on a 48-unit square. The silhouettes remain
# distinguishable when the compact map is scaled down or colors overlap.
MARKERS = (
    ('Cat', 20, (150, 244, 125),
     ((5, 9), (10, 7), (18, 14), (30, 14), (38, 7), (43, 9), (43, 29),
      (39, 36), (32, 41), (16, 41), (9, 36), (5, 29)),
     ((9, 12), (17, 18), (31, 18), (39, 12), (39, 28), (36, 33),
      (30, 37), (18, 37), (12, 33), (9, 28))),
    ('Armor', 18, (255, 108, 95),
     ((24, 5), (42, 11), (42, 27), (38, 35), (24, 44), (10, 35), (6, 27), (6, 11)),
     ((24, 10), (37, 15), (37, 26), (34, 32), (24, 39), (14, 32), (11, 26), (11, 15))),
    ('Candle', 18, (255, 192, 93),
     ((26, 3), (29, 13), (37, 22), (41, 30), (40, 37), (35, 43), (24, 46),
      (14, 43), (8, 37), (7, 29), (10, 21), (17, 13), (17, 24), (22, 17)),
     ((26, 12), (29, 20), (34, 25), (37, 31), (36, 36), (32, 40), (24, 42),
      (16, 40), (12, 35), (11, 30), (15, 22), (15, 30), (22, 26))),
)
MARKER_INSET = max(marker[1] for marker in MARKERS) / 2


def inside_polygon(x, y, polygon):
    inside = False
    ax, ay = polygon[-1]
    for bx, by in polygon:
        if (ay > y) != (by > y) and x < ax + (bx - ax) * (y - ay) / (by - ay):
            inside = not inside
        ax, ay = bx, by
    return inside


def png_chunk(kind, payload):
    return (struct.pack('>I', len(payload)) + kind + payload
            + struct.pack('>I', zlib.crc32(kind + payload)))


def marker_png(color, outline, fill):
    side, samples = 64, 4
    units_per_pixel = 48 / side
    stroke = (15, 19, 25)
    scanlines = bytearray()
    for y in range(side):
        scanlines.append(0)  # PNG filter None
        for x in range(side):
            filled = stroked = 0
            for sy in range(samples):
                for sx in range(samples):
                    px = (x + (sx + .5) / samples) * units_per_pixel
                    py = (y + (sy + .5) / samples) * units_per_pixel
                    if inside_polygon(px, py, fill):
                        filled += 1
                    elif inside_polygon(px, py, outline):
                        stroked += 1
            covered = filled + stroked
            if covered:
                scanlines.extend(round((a * filled + b * stroked) / covered)
                                 for a, b in zip(color, stroke))
            else:
                scanlines.extend(stroke)
            scanlines.append(round(255 * covered / (samples * samples)))
    header = struct.pack('>IIBBBBB', side, side, 8, 6, 0, 0, 0)
    return (b'\x89PNG\r\n\x1a\n' + png_chunk(b'IHDR', header)
            + png_chunk(b'IDAT', zlib.compress(scanlines, 9)) + png_chunk(b'IEND', b''))


def owned_asset(name, audit, created, create):
    path = f'{FOLDER}/{name}'
    if AS.does_asset_exist(path):
        asset = AS.load_asset(path)
        assert asset and AS.get_metadata_tag(asset, OWNER_TAG) == OWNER, path
        return asset
    assert not audit, f'Missing floorplan UI asset {path}'
    asset = create()
    assert asset and asset.get_path_name().split('.')[0] == path, path
    AS.set_metadata_tag(asset, OWNER_TAG, OWNER)
    created.append(asset)
    return asset


def import_marker(name, png, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    source = output_dir / f'{name}.png'
    source.write_bytes(png)
    task = properties(u.AssetImportTask(), filename=str(source), destination_path=FOLDER,
                      destination_name=name, automated=True, replace_existing=False, save=False)
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    paths = task.get_editor_property('imported_object_paths')
    assert len(paths) == 1, paths
    texture = AS.load_asset(paths[0])
    assert isinstance(texture, u.Texture2D), paths
    properties(texture, compression_settings=u.TextureCompressionSettings.TC_EDITOR_ICON,
               lod_group=u.TextureGroup.TEXTUREGROUP_UI, mip_gen_settings=u.TextureMipGenSettings.TMGS_NO_MIPMAPS,
               address_x=u.TextureAddress.TA_CLAMP, address_y=u.TextureAddress.TA_CLAMP, never_stream=True)
    AS.set_metadata_tag(texture, MARKER_HASH_TAG, hashlib.sha256(png).hexdigest())
    return texture


def marker_size_text(size):
    return f'(X={size:.6f},Y={size:.6f})'


def marker_widget(name, texture, size):
    bp = ui('CreateWidgetBlueprint', FOLDER, name, u.UserWidget.static_class())
    icon = add(bp, u.Image, 'Icon', None)
    icon.set_brush_from_texture(texture, False)
    brush = icon.get_editor_property('brush')
    brush_size = brush.get_editor_property('image_size')
    assert brush_size.import_text(marker_size_text(size)), name
    brush.set_editor_property('image_size', brush_size)
    properties(icon, brush=brush, visibility=u.SlateVisibility.HIT_TEST_INVISIBLE)
    compile_bp(bp)
    return bp


def canvas_slot(widget, minimum, maximum, offsets, alignment=(0, 0), order=0, auto_size=False):
    slot = widget.get_editor_property('slot')
    properties(slot, z_order=order, auto_size=auto_size,
               layout_data=u.AnchorData(anchors=u.Anchors(minimum=u.Vector2D(*minimum), maximum=u.Vector2D(*maximum)),
                                        offsets=u.Margin(*offsets), alignment=u.Vector2D(*alignment)))


def panel_widget(base_class, marker_bps):
    bp = ui('CreateWidgetBlueprint', FOLDER, PANEL_NAME, base_class)
    root = add(bp, u.CanvasPanel, 'MinimapRoot', None)
    frame = add(bp, u.Border, 'MinimapFrame', root, variable=True)
    outline = u.SlateBrushOutlineSettings(corner_radii=u.Vector4(4., 4., 4., 4.), width=1.,
                                          rounding_type=u.SlateBrushRoundingType.FIXED_RADIUS,
                                          color=u.SlateColor(specified_color=u.LinearColor(.14, .17, .21, .85)))
    brush = u.SlateBrush(draw_as=u.SlateBrushDrawType.ROUNDED_BOX, outline_settings=outline,
                         tint_color=u.SlateColor(specified_color=u.LinearColor(.012, .016, .024, .84)))
    frame.set_brush(brush)
    properties(frame, padding=u.Margin(MARKER_INSET, MARKER_INSET, MARKER_INSET, MARKER_INSET),
               horizontal_alignment=u.HorizontalAlignment.H_ALIGN_FILL,
               vertical_alignment=u.VerticalAlignment.V_ALIGN_FILL)
    canvas_slot(frame, (1, 0), (1, 0), (-24, 24, 240, 240), alignment=(1, 0))

    surface = add(bp, u.CanvasPanel, 'MapSurface', frame)
    image = add(bp, u.Image, 'MapBackground', surface, variable=True)
    layer = add(bp, u.CanvasPanel, 'MarkerLayer', surface, variable=True)
    properties(layer, clipping=u.WidgetClipping.INHERIT)
    for order, widget in enumerate((image, layer)):
        canvas_slot(widget, (0, 0), (1, 1), (0, 0, 0, 0), order=order)

    compile_bp(bp)
    defaults = u.get_default_object(bp.generated_class())
    properties(defaults, player_marker_class=marker_bps['Cat'].generated_class(),
               armor_marker_class=marker_bps['Armor'].generated_class(),
               candle_marker_class=marker_bps['Candle'].generated_class(),
               expanded_map_viewport_fraction=.76, expanded_map_max_size=700.,
               is_focusable=False, visibility=u.SlateVisibility.HIT_TEST_INVISIBLE)
    return bp


def audit_panel_tree(panel):
    tree = widgets(panel)
    frame = tree['MinimapFrame']
    layer = tree['MarkerLayer']
    assert tree['MapBackground'].get_parent() == layer.get_parent() == tree['MapSurface']
    assert tree['MapSurface'].get_parent() == frame
    assert 'MapToggleHint' not in tree
    assert layer.get_editor_property('clipping') == u.WidgetClipping.INHERIT
    padding = frame.get_editor_property('padding')
    assert padding.left == padding.top == padding.right == padding.bottom == MARKER_INSET
    frame_offsets = frame.get_editor_property('slot').get_offsets()
    assert frame_offsets.right == frame_offsets.bottom > 2 * MARKER_INSET
    for child in (tree['MapBackground'], layer):
        slot = child.get_editor_property('slot')
        anchors = slot.get_anchors()
        offsets = slot.get_offsets()
        assert anchors.minimum.x == anchors.minimum.y == 0
        assert anchors.maximum.x == anchors.maximum.y == 1
        assert offsets.left == offsets.top == offsets.right == offsets.bottom == 0


def author_presentation(audit=False, output_dir=None):
    """Verify or create the new panel and markers, then return its generated class."""
    if output_dir is None:
        output_dir = Path(u.Paths.project_dir()).resolve() / 'Saved/GameplayRepair20261112/Minimap/FloorplanUI'
    else:
        output_dir = Path(output_dir)
    created = []
    marker_bps = {}
    for kind, size, color, outline, fill in MARKERS:
        name = f'T_MinimapMarker_{kind}'
        png = marker_png(color, outline, fill)
        texture = owned_asset(name, audit, created, lambda: import_marker(name, png, output_dir))
        assert AS.get_metadata_tag(texture, MARKER_HASH_TAG) == hashlib.sha256(png).hexdigest(), texture
        widget_name = f'WBP_MinimapMarker_{kind}'
        marker = owned_asset(widget_name, audit, created, lambda: marker_widget(widget_name, texture, size))
        brush = widgets(marker)['Icon'].get_editor_property('brush')
        assert brush.get_editor_property('resource_object') == texture, marker
        assert brush.get_editor_property('image_size').export_text() == marker_size_text(size), marker
        marker_bps[kind] = marker

    base_class = u.load_class(None, '/Script/Catrun.CatrunMinimapWidget')
    assert base_class
    panel = owned_asset(PANEL_NAME, audit, created, lambda: panel_widget(base_class, marker_bps))
    audit_panel_tree(panel)
    defaults = u.get_default_object(panel.generated_class())
    for field, kind in (('player_marker_class', 'Cat'), ('armor_marker_class', 'Armor'),
                        ('candle_marker_class', 'Candle')):
        assert defaults.get_editor_property(field) == marker_bps[kind].generated_class(), field
    for asset in created:
        assert AS.save_loaded_asset(asset, False), asset
    return panel.generated_class()
