"""Import the three actual-map offscreen captures without altering their pixels."""
import hashlib
import json
from pathlib import Path
import struct
import shutil
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
SOURCE = ROOT / 'Saved/ChaptersFlow20261112/Captures/manifest.json'
DATA = json.loads(SOURCE.read_text(encoding='utf8'))
FOLDER = '/Game/UI/Continue/Thumbnails'
AS = u.EditorAssetLibrary
assert not u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
report = {}
for stage in ('Tutorial', 'Stage1', 'Stage2'):
    source = Path(DATA['chapters'][stage])
    content = source.read_bytes()
    assert content[:8] == b'\x89PNG\r\n\x1a\n'
    width, height = struct.unpack('>II', content[16:24])
    assert (width, height) == (1280, 720), (stage, width, height)
    name = 'T_Chapter_' + stage
    destination = FOLDER + '/' + name
    if AS.does_asset_exist(destination):
        texture = AS.load_asset(destination)
        assert AS.get_metadata_tag(texture, 'CatrunCaptureSHA256') == hashlib.sha256(content).hexdigest()
    else:
        # Interchange derives the texture package name from the source basename.
        staged = SOURCE.parent / 'ImportSources' / (name + '.png')
        staged.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, staged)
        assert staged.read_bytes() == content
        task = u.AssetImportTask()
        for prop, value in dict(filename=str(staged), destination_path=FOLDER,
                                destination_name=name, automated=True, replace_existing=False,
                                save=False).items():
            task.set_editor_property(prop, value)
        u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        texture = AS.load_asset(destination)
        assert isinstance(texture, u.Texture2D), (stage, task.get_editor_property('imported_object_paths'))
        texture.set_editor_property('compression_settings', u.TextureCompressionSettings.TC_EDITOR_ICON)
        texture.set_editor_property('lod_group', u.TextureGroup.TEXTUREGROUP_UI)
        texture.set_editor_property('mip_gen_settings', u.TextureMipGenSettings.TMGS_NO_MIPMAPS)
        texture.set_editor_property('sRGB', True)
        AS.set_metadata_tag(texture, 'CatrunCaptureSHA256', hashlib.sha256(content).hexdigest())
        assert AS.save_loaded_asset(texture, False)
    report[stage] = dict(source=str(source), texture=texture.get_path_name(), size=[width, height],
                         sha256=hashlib.sha256(content).hexdigest())
(SOURCE.parent / 'thumbnail_import.json').write_text(json.dumps(report, indent=2), encoding='utf8')
print('CATRUN_CHAPTER_THUMBNAILS_IMPORTED')
