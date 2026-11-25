"""Root calls render() offline, then assign() inside editor, then saves level.

Uses measured post-extension bounds rather than the pending layout.py contract.
All generated assets are isolated to a new Stage3 folder.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'Saved/Stage3GateHallRevision20261125'


def render(report_path=None):
    from PIL import Image, ImageDraw
    report = json.loads(Path(report_path or OUT / 'applied_unsaved.json').read_text(encoding='utf-8'))
    assert report['success']
    rows = report['measured_structural_bounds']
    floors = [row for row in rows if 'SoundFloor' in row['tags']]
    lo = [min(row['min'][i] for row in floors) for i in (0, 1)]
    hi = [max(row['max'][i] for row in floors) for i in (0, 1)]
    size = [hi[i] - lo[i] for i in (0, 1)]
    center = [(hi[i] + lo[i]) / 2 for i in (0, 1)]
    width, height = round(1680 * size[0] / size[1]), 1680
    im = Image.new('RGBA', (width, height)); draw = ImageDraw.Draw(im)
    for tag, color in [('SoundFloor', (155, 151, 142, 255)), ('SoundWall', (44, 43, 47, 255))]:
        for row in rows:
            if tag not in row['tags']:
                continue
            p = [(row['min'][i] - lo[i]) / size[i] * (width if i == 0 else height) for i in (0, 1)]
            q = [(row['max'][i] - lo[i]) / size[i] * (width if i == 0 else height) for i in (0, 1)]
            draw.rectangle((*p, *q), fill=color)
    # Doors/cat holes remain passable openings in a top-down diagram, despite
    # their frame AABBs spanning the aperture. Gate moved; D0/D1/D2/H1-H3 did not.
    portals = [('h', 250, -500, 60), ('v', 150, -650, 140),
               ('h', 100, -1800, 140), ('h', 600, -1800, 60),
               ('h', 1100, -1800, 60), ('h', -250, -2300, 140),
               ('h', -250, -4550, 600)]
    for orientation, x, y, span in portals:
        a, b = ((x - span / 2, y - 16), (x + span / 2, y + 16)) if orientation == 'h' else ((x - 16, y - span / 2), (x + 16, y + span / 2))
        p = [(a[i] - lo[i]) / size[i] * (width if i == 0 else height) for i in (0, 1)]
        q = [(b[i] - lo[i]) / size[i] * (width if i == 0 else height) for i in (0, 1)]
        draw.rectangle((*p, *q), fill=(155, 151, 142, 255))
    OUT.mkdir(parents=True, exist_ok=True)
    im.save(OUT / 'T_Floorplan_Stage3_GateExtended.png')
    settings = {'center': center, 'size': size, 'yaw': -90, 'pixels': [width, height]}
    (OUT / 'minimap_projection.json').write_text(json.dumps(settings, indent=2), encoding='utf-8')
    return settings


def assign():
    import unreal as u
    settings = json.loads((OUT / 'minimap_projection.json').read_text())
    ea = u.EditorAssetLibrary
    dest = '/Game/Environment/Stage3/GateHallRevision_20261125/Minimap'
    path = dest + '/T_Floorplan_Stage3_GateExtended'
    if ea.does_asset_exist(path):
        assert ea.get_metadata_tag(ea.load_asset(path), 'GateHallRevisionOwner') == 'Stage3GateHallExtension20261125'
    task = u.AssetImportTask()
    task.set_editor_properties({'filename': str(OUT / 'T_Floorplan_Stage3_GateExtended.png'),
                                'destination_path': dest, 'destination_name': path.rsplit('/', 1)[-1],
                                'automated': True, 'replace_existing': True, 'save': False})
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    texture = ea.load_asset(path); assert texture
    ea.set_metadata_tag(texture, 'GateHallRevisionOwner', 'Stage3GateHallExtension20261125')
    assert ea.save_loaded_asset(texture)
    editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    assert editor.get_editor_world().get_path_name() == '/Game/Maps/Stage3.Stage3' and not editor.get_game_world()
    found = []
    for actor in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors():
        if actor.get_class().get_name() == 'CatrunMinimapPresenter':
            actor.set_editor_properties({'BackgroundTexture': texture, 'MapCenter': u.Vector2D(*settings['center']),
                                         'MapSize': u.Vector2D(*settings['size']), 'CaptureYawDegrees': settings['yaw']})
            found.append(actor.get_path_name())
    assert len(found) == 1, found
    return {'presenter': found[0], 'texture': path, 'projection': settings, 'level_saved': False}
