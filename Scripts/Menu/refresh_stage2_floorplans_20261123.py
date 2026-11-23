"""Refresh only the floorplan textures currently linked by the two Stage2 presenters.

Run as an Unreal Python commandlet with CATRUN_STAGE2_FLOORPLAN_MODE set to
export (default), import, or audit. Between export and import, run this script
with ordinary Python and the positional argument render. After the cold audit,
run it with the positional argument verify to compare the texture source pixels.
"""

import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Saved/StageRevision20261123/Floorplans'
GEOMETRY = OUT / 'geometry.json'
RENDER = OUT / 'render_report.json'
MAPS = ('Stage2', 'SoundTest_Stage2')
TEXTURE_FOLDER = '/Game/UI/Minimap'
TEXTURE_OWNER = 'CatrunFloorplan20261112'
SOURCE_HASH = 'CatrunFloorplanSHA256'
TEXTURE_SETTINGS = ('compression_settings', 'lod_group', 'mip_gen_settings',
                    'address_x', 'address_y', 'never_stream', 'sRGB')


def file_sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def data_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def write_json(path, payload, compact=False):
    with path.open('w', encoding='utf8') as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=None if compact else 2,
                  separators=(',', ':') if compact else None)


def read_json(path):
    return json.loads(path.read_text(encoding='utf8'))


def texture_package(object_path):
    package, name = object_path.rsplit('.', 1)
    folder, asset = package.rsplit('/', 1)
    assert folder == TEXTURE_FOLDER and name == asset and name.startswith('T_Floorplan_'), object_path
    return package


def package_asset(package):
    return ROOT / 'Content' / (package.removeprefix('/Game/') + '.uasset')


def package_hashes():
    content = ROOT / 'Content'
    suffixes = {'.uasset', '.umap', '.uexp', '.ubulk', '.uptnl'}
    return {path.relative_to(ROOT).as_posix(): file_sha(path)
            for folder in ('UI/Minimap', 'Maps', '__ExternalActors__/Maps', '__ExternalObjects__/Maps')
            for path in (content / folder).rglob('*') if path.is_file() and path.suffix in suffixes}


def target_files(hashes, packages):
    stems = {package_asset(name).relative_to(ROOT).with_suffix('').as_posix() for name in packages}
    return {path: sha for path, sha in hashes.items() if Path(path).with_suffix('').as_posix() in stems}


def require_clean(u):
    io = u.EditorLoadingAndSavingUtils
    dirty = list(io.get_dirty_content_packages()) + list(io.get_dirty_map_packages())
    assert not dirty, [p.get_name() for p in dirty]


def capture_frame(presenter):
    center = presenter.get_editor_property('map_center')
    size = presenter.get_editor_property('map_size')
    yaw = float(presenter.get_editor_property('capture_yaw_degrees'))
    frame = {'center': [float(center.x), float(center.y)], 'size': [float(size.x), float(size.y)], 'yaw': yaw}
    assert all(map(math.isfinite, (*frame['center'], *frame['size'], yaw))) and min(frame['size']) > 0., frame
    assert abs(yaw) < .0001, ('Existing renderer requires yaw zero', frame)
    return frame


def frame_fit(frame, geometry_frame):
    limits = [[axis - size / 2 for axis, size in zip(frame['center'], frame['size'])],
              [axis + size / 2 for axis, size in zip(frame['center'], frame['size'])]]
    low, high = geometry_frame['geometry_bounds_xy']
    margins = [extent - limit for extent, limit in zip(low, limits[0])]
    margins.extend(limit - extent for extent, limit in zip(high, limits[1]))
    return {'capture_bounds_xy': limits, 'margins_xy_low_high': margins, 'fits': min(margins) >= 0.}


def inspect_texture(u, texture):
    assert isinstance(texture, u.Texture2D), texture
    package = texture_package(texture.get_path_name())
    assets = u.EditorAssetLibrary
    assert assets.get_metadata_tag(texture, 'CatrunAuthor') == TEXTURE_OWNER, package
    # A commandlet can see a 32x32 resource placeholder while the loaded texture compiles.
    u.CatrunAuthoringLibrary.finish_asset_compilation()
    return {'path': texture.get_path_name(), 'owner': TEXTURE_OWNER,
            'source_sha256': assets.get_metadata_tag(texture, SOURCE_HASH),
            'settings': {name: str(texture.get_editor_property(name)) for name in TEXTURE_SETTINGS},
            'size': [texture.blueprint_get_size_x(), texture.blueprint_get_size_y()]}


def collect_maps(u, editor, levels, export_geometry):
    from minimap_geometry import capture_plan
    from export_minimap_floorplans import footprint

    presenter_class = u.load_class(None, '/Script/Catrun.CatrunMinimapPresenter')
    assert presenter_class
    cache = {}
    rows = {}
    for name in MAPS:
        assert levels.load_level('/Game/Maps/' + name), name
        world = editor.get_editor_world()
        assert world.get_path_name() == f'/Game/Maps/{name}.{name}', world.get_path_name()
        presenters = u.GameplayStatics.get_all_actors_of_class(world, presenter_class)
        assert len(presenters) == 1, (name, len(presenters))
        presenter = presenters[0]
        texture = inspect_texture(u, presenter.get_editor_property('background_texture'))
        frame = capture_frame(presenter)
        calculated, floors, walls = capture_plan(world)
        groups = [('floor', floors), ('wall', walls)]
        pieces = [(role, actor) for role, group in groups for actor in group]
        # Recheck the exact architecture selection and transforms before save, without exporting another LOD dump.
        signature = []
        wall_labels = []
        for role, actor in pieces:
            component = actor.static_mesh_component
            label = actor.get_actor_label()
            signature.append([role, actor.get_path_name(), label,
                              component.get_editor_property('static_mesh').get_path_name(),
                              component.get_world_transform().export_text()])
            if role == 'wall':
                wall_labels.append(label)
        altar = sorted(label for label in wall_labels if label.startswith('S2_Layout_Room4_Altar'))
        assert len(altar) == 6, (name, 'Expected the sealed Room4 altar in the floorplan wall selection', altar)
        row = {'frame': frame, 'actual_geometry_frame': calculated, 'frame_fit': frame_fit(frame, calculated),
               'texture': texture, 'presenter': presenter.get_path_name(),
               'widget': presenter.get_editor_property('widget_class').get_path_name(),
               'architecture_sha256': data_sha(signature), 'altar_wall_labels': altar,
               'floor_count': len(floors), 'wall_count': len(walls)}
        assert texture['size'] == [1024, 1024], (name, texture)
        if export_geometry:
            geometry = [footprint(actor, role, cache) for role, actor in pieces]
            row.update(geometry=geometry, geometry_sha256=data_sha({'frame': frame, 'geometry': geometry}),
                       actual_mesh_count=sum(a['method'] == 'lod0_projected_triangle_union' for a in geometry),
                       bounds_approximation_count=sum(a['method'] == 'transformed_local_bounds_approximation' for a in geometry))
        rows[name] = row
        require_clean(u)
        print('CATRUN_STAGE2_FLOORPLAN_FRAME', name, json.dumps({k: row[k] for k in
              ('frame', 'actual_geometry_frame', 'frame_fit', 'texture', 'altar_wall_labels')}))
    return rows


def validate_texture_links(u, rows):
    registry = u.AssetRegistryHelpers.get_asset_registry()
    options = u.AssetRegistryDependencyOptions(include_soft_package_references=True, include_hard_package_references=True)
    references = {}
    for path in {row['texture']['path'] for row in rows.values()}:
        package = texture_package(path)
        expected = {f'/Game/Maps/{name}' for name, row in rows.items() if row['texture']['path'] == path}
        actual = set(map(str, registry.get_referencers(u.Name(package), options)))
        assert actual == expected, (package, 'Unapproved or missing texture referencers', sorted(actual), sorted(expected))
        references[package] = sorted(actual)
    return references


def render_floorplans():
    from render_minimap_floorplans import render, SIZE

    source = read_json(GEOMETRY)
    assert source['completed'] and set(source['maps']) == set(MAPS)
    report = {'completed': False, 'source_sha256': file_sha(GEOMETRY), 'size': [SIZE, SIZE], 'maps': {}}
    for name in MAPS:
        row = source['maps'][name]
        assert row['frame_fit']['fits'], (name, 'New geometry exceeds the saved capture frame', row['frame_fit'])
        _, result = render(name, row, OUT)
        report['maps'][name] = result
        print('CATRUN_STAGE2_FLOORPLAN_RENDER', name, result['sha256'], result['opaque_bounds_px'])
    report['completed'] = True
    write_json(RENDER, report)


def texture_inputs(current, old, rendered):
    assert old['completed'] and rendered['completed'] and rendered['size'] == [1024, 1024]
    assert set(old['maps']) == set(rendered['maps']) == set(MAPS)
    assert rendered['source_sha256'] == file_sha(GEOMETRY), 'Render and geometry export differ'
    inputs = {}
    for name in MAPS:
        live, previous, image = current[name], old['maps'][name], rendered['maps'][name]
        for key in ('frame', 'frame_fit', 'presenter', 'widget', 'architecture_sha256'):
            assert live[key] == previous[key], (name, 'Map changed after export', key)
        assert live['frame_fit']['fits'], (name, live['frame_fit'])
        assert all(live['texture'][key] == previous['texture'][key] for key in ('path', 'settings', 'owner', 'size')), name
        assert image['frame'] == live['frame'] and image['geometry_sha256'] == previous['geometry_sha256'], name
        assert image['clipped_actors'] == [], (name, image['clipped_actors'])
        source = OUT / f'Minimap_{name}.png'
        assert Path(image['image']).resolve() == source.resolve() and file_sha(source) == image['sha256'], name
        with source.open('rb') as stream:
            header = stream.read(24)
        assert header[:16] == b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR' and struct.unpack('>II', header[16:24]) == (1024, 1024), name
        package = texture_package(live['texture']['path'])
        expected = {'source': source, 'sha256': image['sha256'], 'before': previous['texture'], 'live': live['texture']}
        if package in inputs:
            assert inputs[package]['sha256'] == expected['sha256'], (package, 'Shared texture has different rendered maps')
        else:
            inputs[package] = expected
    return inputs


def assign(obj, **values):
    for k, v in values.items():
        obj.set_editor_property(k, v)
    return obj


def install_textures(u, inputs, original, current_hashes):
    assets = u.EditorAssetLibrary
    pending = {name: row for name, row in inputs.items() if row['live']['source_sha256'] != row['sha256']}
    if not pending:
        return [], None
    originals = target_files(current_hashes, pending)
    expected_files = target_files(original['package_hashes'], pending)
    assert originals and originals == expected_files, 'Target packages changed after export'
    assert all(entry['live']['source_sha256'] == entry['before']['source_sha256'] for entry in pending.values())
    backup = Path(tempfile.mkdtemp(prefix='BeforeTexture-', dir=OUT))
    for path, sha in originals.items():
        destination = backup / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / path, destination)
        assert file_sha(destination) == sha, destination
    print('CATRUN_STAGE2_FLOORPLAN_BACKUP', str(backup))
    tasks = {}
    sources = backup / 'ImportSources'
    sources.mkdir()
    for package, row in pending.items():
        name = package.rsplit('/', 1)[1]
        staged = sources / (name + '.png')
        shutil.copy2(row['source'], staged)
        assert file_sha(staged) == row['sha256'], staged
        tasks[package] = assign(u.AssetImportTask(), filename=str(staged), destination_path=TEXTURE_FOLDER,
                                destination_name=name, automated=True, replace_existing=True,
                                replace_existing_settings=False, save=False)
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks(list(tasks.values()))
    textures = {}
    for package, task in tasks.items():
        row = pending[package]
        assert list(task.get_editor_property('imported_object_paths')) == [row['before']['path']], package
        texture = assets.load_asset(package)
        actual = inspect_texture(u, texture)
        assert all(actual[k] == row['before'][k] for k in ('path', 'owner', 'settings', 'size')), (package, actual)
        assets.set_metadata_tag(texture, SOURCE_HASH, row['sha256'])
        textures[package] = texture
    io = u.EditorLoadingAndSavingUtils
    assert not io.get_dirty_map_packages()
    assert {p.get_name() for p in io.get_dirty_content_packages()} <= set(pending), 'Import dirtied an unrelated package'
    assert package_hashes() == current_hashes, 'Package changed before scoped save'
    for package, texture in textures.items():
        assert assets.save_loaded_asset(texture, False), package
    return sorted(pending), str(backup)


def export_cold_texture(u, texture, package):
    directory = OUT / 'ColdTextureSources'
    directory.mkdir(exist_ok=True)
    path = directory / (package.rsplit('/', 1)[1] + '.png')
    task = assign(u.AssetExportTask(), object=texture, filename=str(path), automated=True, prompt=False,
                  replace_identical=True, exporter=u.TextureExporterPNG())
    assert u.Exporter.run_asset_export_task(task) and path.is_file(), (package, task.errors)
    return {'path': str(path), 'file_sha256': file_sha(path)}


def run_unreal():
    import unreal as u

    mode = os.environ.get('CATRUN_STAGE2_FLOORPLAN_MODE', 'export').lower()
    assert mode in ('export', 'import', 'audit'), mode
    editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
    assert not editor.get_game_world(), 'Requires an editor world outside PIE'
    require_clean(u)
    OUT.mkdir(parents=True, exist_ok=True)
    before = package_hashes()
    rows = collect_maps(u, editor, levels, mode == 'export')
    links = validate_texture_links(u, rows)
    assert package_hashes() == before, 'Reading Stage2 unexpectedly changed packages'
    if mode == 'export':
        write_json(GEOMETRY, {'schema_version': 1, 'completed': True, 'maps': rows,
                             'texture_referencers': links, 'package_hashes': before}, compact=True)
        print('CATRUN_STAGE2_FLOORPLAN_GEOMETRY', str(GEOMETRY))
        return

    original, rendered = read_json(GEOMETRY), read_json(RENDER)
    assert links == original['texture_referencers'], links
    inputs = texture_inputs(rows, original, rendered)
    saved, backup = install_textures(u, inputs, original, before) if mode == 'import' else ([], None)
    details = {}
    for package, row in inputs.items():
        texture = u.EditorAssetLibrary.load_asset(package)
        actual = inspect_texture(u, texture)
        assert actual['source_sha256'] == row['sha256'], (package, actual['source_sha256'], row['sha256'])
        details[package] = {'texture': actual, 'rendered_png': str(row['source'])}
        if mode == 'audit':
            details[package]['cold_texture_source'] = export_cold_texture(u, texture, package)
    require_clean(u)
    after = package_hashes()
    changed = {path for path in before.keys() | after.keys() if before.get(path) != after.get(path)}
    allowed = set(target_files(before | after, saved))
    assert changed <= allowed, (mode, sorted(changed - allowed))
    assert all(package_asset(package).relative_to(ROOT).as_posix() in changed for package in saved), saved
    report = {'completed': True, 'mode': mode, 'maps': rows, 'textures': details, 'saved_packages': saved,
              'texture_referencers': links, 'backup': backup, 'changed_files': sorted(changed),
              'target_sha256_before': target_files(before, inputs), 'target_sha256_after': target_files(after, inputs),
              'protected_file_count': len(before) - len(allowed)}
    path = OUT / (f'{mode}_report.json' if mode == 'audit' or saved else 'import_noop_report.json')
    write_json(path, report)
    print('CATRUN_STAGE2_FLOORPLAN', mode, saved, str(path))


def verify_cold():
    from PIL import Image, ImageChops

    report = read_json(OUT / 'audit_report.json')
    assert report['completed'] and not report['saved_packages'] and not report['changed_files']
    assert report['target_sha256_before'] == report['target_sha256_after']
    proof = {}
    for package, row in report['textures'].items():
        saved = Path(row['cold_texture_source']['path'])
        rendered = Path(row['rendered_png'])
        assert file_sha(saved) == row['cold_texture_source']['file_sha256']
        assert file_sha(rendered) == row['texture']['source_sha256']
        with Image.open(saved) as actual_png, Image.open(rendered) as expected_png:
            actual, expected = (image.convert('RGBA') for image in (actual_png, expected_png))
        assert actual.size == expected.size, package
        alpha = expected.getchannel('A')
        assert actual.getchannel('A').tobytes() == alpha.tobytes(), (package, 'Alpha differs')
        # Transparent texels may gain an RGB bleed during import. Compare every visible RGB channel.
        mask = alpha.point(lambda value: 255 if value else 0)
        difference = ImageChops.difference(actual.convert('RGB'), expected.convert('RGB'))
        assert not ImageChops.multiply(difference, Image.merge('RGB', (mask,) * 3)).getbbox(), (package, 'Visible pixels differ')
        proof[package] = {'size': list(actual.size), 'alpha_matches': True, 'visible_rgb_matches': True}
    write_json(OUT / 'pixel_proof.json', proof)
    print('CATRUN_STAGE2_FLOORPLAN_PIXELS', proof)


if __name__ == '__main__':
    sys.path.insert(0, str(ROOT / 'Scripts/Menu'))
    if sys.argv[1:] == ['render']:
        render_floorplans()
    elif sys.argv[1:] == ['verify']:
        verify_cold()
    else:
        run_unreal()
