"""Edit and cold-audit the two existing Designer widgets and their chapter photos.

CATRUN_CONTINUE_MODE: probe, author, or audit. Run author after checking the
offscreen candidate photos. CATRUN_CONTINUE_VIEWS can select the three candidates
in Tutorial, Stage1, Stage2 order (defaults: Window,Fireplace,Gargoyle).
"""

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys

import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT / 'Scripts/Menu'))
from menu_graph import BP, add, compile_bp, properties, ui, widgets
from author_chapter_selection import (CHAPTERS, FONT_PATH, SELECTOR, asset, brush, digest,
                                     graph_snapshot, rect)

AS = u.EditorAssetLibrary
SETTINGS = '/Game/UI/Settings/WBP_Setting'
OUT = ROOT / 'Saved/ContinueFollowup'
CAPTURES = Path(os.environ.get('CATRUN_CONTINUE_OUTPUT', str(OUT / 'Captures')))
THUMBNAILS = '/Game/UI/Continue/Thumbnails'
PHOTO_SIZE = (1280, 720)
CARD_WIDTH, CARD_HEIGHT = 384, 308
CARD_GAP = 34
PANEL_WIDTH, PANEL_HEIGHT = 1264, 500
IMAGE_WIDTH = CARD_WIDTH - 2
IMAGE_HEIGHT = IMAGE_WIDTH * 9 / 16
FRAME_HEIGHT = IMAGE_HEIGHT + 2
FONT = asset(FONT_PATH)
FILL = u.HorizontalAlignment.H_ALIGN_FILL
CENTER = u.HorizontalAlignment.H_ALIGN_CENTER
LEFT = u.HorizontalAlignment.H_ALIGN_LEFT
VCENTER = u.VerticalAlignment.V_ALIGN_CENTER
VTOP = u.VerticalAlignment.V_ALIGN_TOP
PASSIVE = u.SlateVisibility.HIT_TEST_INVISIBLE
WHITE = u.LinearColor(1, 1, 1, 1)


def path_for(package):
    return ROOT / 'Content' / (package.removeprefix('/Game/') + '.uasset')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding='utf8')


def tree_state(bp):
    return {g.get_name(): digest(graph_snapshot(g)) for g in BP.list_graphs(bp)}


def ensure(bp, cls, name, parent):
    widget = widgets(bp).get(name)
    if widget:
        assert isinstance(widget, cls) and widget.get_parent() == parent, name
        return widget
    return add(bp, cls, name, parent)


def move(bp, widget, parent, index=-1):
    if widget.get_parent() != parent or (index >= 0 and parent.get_child_index(widget) != index):
        ui('MoveWidget', bp, widget, parent, index)
    assert widget.get_parent() == parent, widget.get_name()
    return widget


def remove(bp, name):
    widget = widgets(bp).get(name)
    if widget:
        ui('RemoveWidget', bp, widget)
        assert name not in widgets(bp)


def slot(widget, **values):
    properties(widget.get_editor_property('slot'), **values)


def anchored(widget, minimum, maximum, offsets, z=0):
    slot(widget, auto_size=False, z_order=z, layout_data=u.AnchorData(
        anchors=u.Anchors(minimum=u.Vector2D(*minimum), maximum=u.Vector2D(*maximum)),
        offsets=u.Margin(*offsets), alignment=u.Vector2D(0, 0)))


def font(size):
    return u.SlateFontInfo(font_object=FONT, typeface_font_name='Default', size=size)


def patch_settings(bp):
    tree = widgets(bp)
    status = tree['SettingsStatus']
    status_box = tree['SettingsStatusHeight']
    status_box.clear_height_override()
    status_box.set_min_desired_height(28)
    slot(status_box, padding=u.Margin(0, 9, 0, 7), horizontal_alignment=FILL)
    slot(status, horizontal_alignment=FILL, vertical_alignment=VCENTER)
    properties(status, auto_wrap_text=True, wrapping_policy=u.TextWrappingPolicy.ALLOW_PER_CHARACTER_WRAPPING,
               margin=u.Margin(0), font=font(19), visibility=PASSIVE)

    footer = tree['FooterWrap']
    # The outer row alone responds to viewport width. The travel group has two
    # short labels and always reports their combined width on its first prepass.
    properties(footer, explicit_wrap_size=False, inner_slot_padding=u.Vector2D(18, 7))
    properties(tree['GameplayActions'], explicit_wrap_size=True, wrap_size=320.,
               inner_slot_padding=u.Vector2D(18, 0))
    slot(footer, padding=u.Margin(0, 2, 0, 0), horizontal_alignment=FILL)

    # The category's own header already explains the session-only setting.
    # Keep this template member for existing Designer names, but use the header
    # as the only location for that explanation.
    properties(tree['DeveloperSessionHint'], visibility=u.SlateVisibility.COLLAPSED)
    properties(tree['NoArmorCaptureRowLabel'], auto_wrap_text=True,
               wrapping_policy=u.TextWrappingPolicy.ALLOW_PER_CHARACTER_WRAPPING)
    row = tree['NoArmorCaptureRowHeight']
    row.clear_height_override()
    row.set_min_desired_height(52)
    properties(tree['SettingsBodyScroll'], clipping=u.WidgetClipping.CLIP_TO_BOUNDS)


def patch_chapter(bp, textures):
    tree = widgets(bp)
    root = tree['ChapterCanvas']
    bounds, panel = tree['ChapterPanelBounds'], tree['ChapterPanel']
    host = ensure(bp, u.Border, 'ChapterPanelHost', root)
    anchored(host, (.045, .05), (.955, .95), (0, 0, 0, 0), 1)
    properties(host, background=brush(WHITE, u.SlateBrushDrawType.NO_DRAW_TYPE), padding=u.Margin(0),
               horizontal_alignment=CENTER, vertical_alignment=VCENTER,
               visibility=u.SlateVisibility.SELF_HIT_TEST_INVISIBLE)
    move(bp, bounds, host)
    bounds.set_width_override(PANEL_WIDTH)
    bounds.set_height_override(PANEL_HEIGHT)
    remove(bp, 'ChapterViewportFit')
    properties(tree['ChapterScrim'], brush_color=u.LinearColor(.014, .012, .016, .86))

    heading = tree['ChapterHeading']
    anchored(heading, (0, 0), (1, 0), (12, 2, 12, 54))
    properties(heading, font=font(42), justification=u.TextJustify.LEFT)
    anchored(tree['ChapterRule'], (0, 0), (1, 0), (12, 67, 12, 1))

    scroll = ensure(bp, u.ScrollBox, 'ChapterCardScroll', panel)
    anchored(scroll, (0, 0), (1, 1), (0, 94, 0, 74))
    properties(scroll, clipping=u.WidgetClipping.CLIP_TO_BOUNDS,
               scrollbar_thickness=u.Vector2D(4, 4), scrollbar_padding=u.Margin(6, 0, 0, 0),
               consume_mouse_wheel=u.ConsumeMouseWheel.WHEN_SCROLLING_POSSIBLE)
    grid = ensure(bp, u.WrapBox, 'ChapterCardGrid', scroll)
    properties(grid, explicit_wrap_size=False, horizontal_alignment=CENTER,
               inner_slot_padding=u.Vector2D(CARD_GAP, 24))

    for index, (stage, _) in enumerate(CHAPTERS):
        card_bounds = tree[stage + 'Bounds']
        move(bp, card_bounds, grid, index)
        card_bounds.set_width_override(CARD_WIDTH)
        card_bounds.set_height_override(CARD_HEIGHT)
        # The old horizontal slots had left padding that MoveWidget can copy.
        # The WrapBox's inner spacing owns the full gap after reparenting.
        slot(card_bounds, padding=u.Margin(0), horizontal_alignment=FILL, vertical_alignment=VTOP,
             fill_span_when_less_than=float(CARD_WIDTH))

        # Keep the per-card artwork geometry and aspect intact even when the
        # viewport is narrower than a single full-size card.
        card = tree[stage + 'Card']
        if not widgets(bp).get(stage + 'CardFit'):
            move(bp, card, panel)
        fit = ensure(bp, u.ScaleBox, stage + 'CardFit', card_bounds)
        properties(fit, stretch=u.Stretch.SCALE_TO_FIT, stretch_direction=u.StretchDirection.DOWN_ONLY)
        design = ensure(bp, u.SizeBox, stage + 'CardComposition', fit)
        design.set_width_override(CARD_WIDTH)
        design.set_height_override(CARD_HEIGHT)
        slot(design, horizontal_alignment=CENTER, vertical_alignment=VTOP)
        move(bp, card, design)
        button = tree[stage + 'Button']
        button.set_cursor(u.MouseCursor.HAND)
        rect(tree[stage + 'Frame'], 0, 0, CARD_WIDTH, FRAME_HEIGHT)
        preview = tree[stage + 'Image']
        preview.set_brush_from_texture(textures[stage], False)
        rect(preview, 1, 1, IMAGE_WIDTH, IMAGE_HEIGHT)
        title = tree[stage + 'Name']
        rect(title, 1, FRAME_HEIGHT + 13, CARD_WIDTH - 2, 45)
        properties(title, font=font(34), justification=u.TextJustify.LEFT)
        locked = tree[stage + 'Locked']
        rect(locked, 1, FRAME_HEIGHT + 58, CARD_WIDTH - 2, 31, z=2)
        properties(locked, font=font(19), justification=u.TextJustify.LEFT)
        rect(tree[stage + 'Underline'], 1, FRAME_HEIGHT + 55, CARD_WIDTH - 2, 1, z=3)
        remove(bp, stage + 'MissingPreview')
    remove(bp, 'ChapterCards')

    anchored(tree['ChapterFooterRule'], (0, 1), (1, 1), (12, -62, 12, 1))
    rect(tree['ChapterBack'], 12, -54, 104, 48, anchor=(0, 1))
    tree['ChapterBack'].set_cursor(u.MouseCursor.HAND)
    rect(tree['ChapterBackLabel'], 12, -47, 104, 36, anchor=(0, 1), z=1)
    rect(tree['ChapterBackUnderline'], 12, -14, 48, 1, anchor=(0, 1), z=2)
    status = tree['ChapterStatus']
    anchored(status, (0, 1), (1, 1), (132, -51, 12, 47), 1)
    properties(status, auto_wrap_text=True, font=font(20))


def verify_designer(settings, chapter, textures):
    sw, cw = widgets(settings), widgets(chapter)
    status, status_box = sw['SettingsStatus'], sw['SettingsStatusHeight']
    assert status.get_parent() == status_box and status.get_editor_property('auto_wrap_text')
    assert status_box.get_editor_property('min_desired_height') == 28
    assert not status_box.get_editor_property('override_height_override')
    assert sw['DeveloperSessionHint'].get_editor_property('visibility') == u.SlateVisibility.COLLAPSED
    assert sw['GameplayActions'].get_editor_property('explicit_wrap_size')
    assert [sw['FooterWrap'].get_child_at(i).get_name() for i in range(sw['FooterWrap'].get_children_count())] == [
        'DefaultsButton', 'GameplayActions', 'ApplyButton', 'CloseButton']
    assert 'ChapterViewportFit' not in cw and 'ChapterCards' not in cw
    grid = cw['ChapterCardGrid']
    assert isinstance(grid, u.WrapBox) and grid.get_parent() == cw['ChapterCardScroll']
    assert grid.get_children_count() == len(CHAPTERS)
    assert not grid.get_editor_property('explicit_wrap_size')
    assert grid.get_editor_property('inner_slot_padding').x == CARD_GAP
    for index, (stage, _) in enumerate(CHAPTERS):
        assert grid.get_child_at(index) == cw[stage + 'Bounds']
        padding = cw[stage + 'Bounds'].get_editor_property('slot').get_editor_property('padding')
        assert not any((padding.left, padding.top, padding.right, padding.bottom)), stage
        photo = cw[stage + 'Image']
        layout = photo.get_editor_property('slot').get_editor_property('layout_data').get_editor_property('offsets')
        assert abs(layout.right / layout.bottom - 16 / 9) < .0001
        assert photo.get_editor_property('brush').get_editor_property('resource_object') == textures[stage]
        assert cw[stage + 'Name'].get_editor_property('font').get_editor_property('font_object') == FONT
        assert cw[stage + 'Underline'].get_editor_property('visibility') == u.SlateVisibility.HIDDEN


def selected_photos():
    manifest = json.loads((CAPTURES / 'manifest.json').read_text(encoding='utf8'))
    choices = os.environ.get('CATRUN_CONTINUE_VIEWS', 'Window,Fireplace,Gargoyle').split(',')
    assert len(choices) == len(CHAPTERS)
    result = {}
    for (stage, _), choice in zip(CHAPTERS, choices):
        record = manifest[stage]['views'][choice]
        source = Path(record['image'])
        data = source.read_bytes()
        assert data.startswith(b'\x89PNG\r\n\x1a\n') and struct.unpack('>II', data[16:24]) == PHOTO_SIZE, source
        assert sha(source) == record['sha256'], source
        assert sha(ROOT / 'Content/Maps' / f'{stage}.umap') == manifest[stage]['source_sha256'], stage
        result[stage] = (choice, source, record['sha256'])
    return result


def import_photos(packages, choices, backup):
    tasks, textures = {}, {}
    sources = backup / 'ImportSources'
    sources.mkdir()
    for stage, package in packages.items():
        current = asset(package)
        if AS.get_metadata_tag(current, 'CatrunCaptureSHA256') == choices[stage][2]:
            assert isinstance(current, u.Texture2D)
            assert (current.blueprint_get_size_x(), current.blueprint_get_size_y()) == PHOTO_SIZE
            textures[stage] = current
            continue
        name = package.rsplit('/', 1)[1]
        staged = sources / (name + '.png')
        shutil.copy2(choices[stage][1], staged)
        task = u.AssetImportTask()
        properties(task, filename=str(staged), destination_path=THUMBNAILS, destination_name=name,
                   automated=True, replace_existing=True, replace_existing_settings=False, save=False)
        tasks[stage] = task
    if tasks:
        u.AssetToolsHelpers.get_asset_tools().import_asset_tasks(list(tasks.values()))
    for stage, task in tasks.items():
        package = packages[stage]
        imported = list(task.get_editor_property('imported_object_paths'))
        assert imported == [package + '.' + package.rsplit('/', 1)[1]], (stage, imported)
        texture = asset(package)
        assert isinstance(texture, u.Texture2D)
        properties(texture, compression_settings=u.TextureCompressionSettings.TC_EDITOR_ICON,
                   lod_group=u.TextureGroup.TEXTUREGROUP_UI,
                   mip_gen_settings=u.TextureMipGenSettings.TMGS_NO_MIPMAPS, sRGB=True)
        assert (texture.blueprint_get_size_x(), texture.blueprint_get_size_y()) == PHOTO_SIZE
        AS.set_metadata_tag(texture, 'CatrunCaptureSHA256', choices[stage][2])
        textures[stage] = texture
    return textures


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    mode = os.environ.get('CATRUN_CONTINUE_MODE', 'probe')
    assert mode in ('probe', 'author', 'audit'), mode
    assert not u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
    io = u.EditorLoadingAndSavingUtils
    assert not io.get_dirty_map_packages() and not io.get_dirty_content_packages()
    packages = {stage: THUMBNAILS + '/T_Chapter_' + stage for stage, _ in CHAPTERS}
    assets = (SETTINGS, SELECTOR, *packages.values())
    before = {package: sha(path_for(package)) for package in assets}
    settings, chapter = asset(SETTINGS), asset(SELECTOR)
    graphs = {SETTINGS: tree_state(settings), SELECTOR: tree_state(chapter)}
    if mode == 'probe':
        for bp, name in ((settings, 'settings'), (chapter, 'chapter')):
            write('probe_' + name + '.json', {row.widget.get_name(): dict(
                kind=row.widget.get_class().get_name(), parent=row.parent.get_name() if row.parent else None,
                visibility=str(row.widget.get_editor_property('visibility'))) for row in ui('GetWidgets', bp).widgets})
        return
    if mode == 'audit':
        report = json.loads((OUT / 'author.json').read_text(encoding='utf8'))
        textures = {stage: asset(package) for stage, package in packages.items()}
        assert graphs == report['graphs']
        for stage, texture in textures.items():
            assert AS.get_metadata_tag(texture, 'CatrunCaptureSHA256') == report['photos'][stage]['sha256']
        verify_designer(settings, chapter, textures)
        for bp in (settings, chapter):
            compile_bp(bp)
        assert before == {package: sha(path_for(package)) for package in assets} == report['after']
        write('audit.json', dict(graphs=graphs, photos=report['photos'], saved_sha256=before))
        print('CATRUN_CONTINUE_COLD_AUDIT_OK')
        return

    choices = selected_photos()
    chapter_tree = widgets(chapter)
    old_card_padding = {stage: str(chapter_tree[stage + 'Bounds'].get_editor_property('slot')
                                  .get_editor_property('padding')) for stage, _ in CHAPTERS}
    backup = OUT / 'Backups' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    for package in assets:
        path = path_for(package)
        target = backup / path.relative_to(ROOT / 'Content')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        assert sha(target) == before[package]
    textures = import_photos(packages, choices, backup)
    patch_settings(settings)
    patch_chapter(chapter, textures)
    for bp in (settings, chapter):
        compile_bp(bp)
    assert graphs == {SETTINGS: tree_state(settings), SELECTOR: tree_state(chapter)}
    verify_designer(settings, chapter, textures)
    for obj in (*textures.values(), settings, chapter):
        assert AS.save_loaded_asset(obj, True), obj.get_path_name()
    assert not io.get_dirty_map_packages() and not io.get_dirty_content_packages()
    write('author.json', dict(backup=str(backup), before=before, graphs=graphs, old_card_padding=old_card_padding,
                            after={package: sha(path_for(package)) for package in assets},
                            photos={stage: dict(view=view, source=str(path), sha256=photo_sha)
                                    for stage, (view, path, photo_sha) in choices.items()}))
    print('CATRUN_CONTINUE_AUTHOR_OK')


if __name__ == '__main__':
    main()
