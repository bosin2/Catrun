"""Connect the audited architectural diagrams and BP presentation to six maps.

Run after export_minimap_floorplans.py + render_minimap_floorplans.py.
-catrunUsabilityAudit validates in a separate process without saving.
"""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import unreal as u

ROOT = Path(u.Paths.project_dir()).resolve()
sys.path.insert(0, str(ROOT/'Scripts/Menu'))
from menu_graph import properties, compile_bp
from minimap_geometry import MAP_NAMES, capture_plan
from rework_minimap_20261112 import author_presentation, PANEL_NAME

OUT = ROOT/'Saved/GameplayRepair20261112/BasketUsability'
FLOORS = OUT/'Floorplans'
FOLDER = '/Game/UI/Minimap'
AS = u.EditorAssetLibrary
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
ED = u.get_editor_subsystem(u.UnrealEditorSubsystem)
AUDIT = '-catrunusabilityaudit' in u.SystemLibrary.get_command_line().lower()
OWNER = 'CatrunFloorplan20261112'


def main():
    report = {'completed':False, 'audit_only':AUDIT, 'maps':{}}
    rows = json.loads((FLOORS/'render_report.json').read_text(encoding='utf8'))
    assert rows['completed'] and set(rows['maps']) == set(MAP_NAMES)
    assert not ED.get_game_world()
    assert not u.EditorLoadingAndSavingUtils.get_dirty_map_packages()
    assert not u.EditorLoadingAndSavingUtils.get_dirty_content_packages()
    panel_class = author_presentation(AUDIT, FLOORS/'MarkerSources')
    by_hash, textures = {}, {}
    for name in MAP_NAMES:
        row = rows['maps'][name]
        sha = row['sha256']
        if sha not in by_hash:
            asset_name = 'T_Floorplan_'+name
            path = FOLDER+'/'+asset_name
            if not AS.does_asset_exist(path):
                assert not AUDIT
                source = FLOORS/(asset_name+'.png')
                shutil.copy2(row['image'],source)
                task = u.AssetImportTask()
                properties(task, filename=str(source), destination_path=FOLDER, destination_name=asset_name,
                           automated=True, replace_existing=False, save=False)
                u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
                imported = list(task.get_editor_property('imported_object_paths'))
                assert len(imported)==1 and imported[0].split('.')[0]==path, imported
                tex = AS.load_asset(path)
                properties(tex, compression_settings=u.TextureCompressionSettings.TC_EDITOR_ICON,
                           lod_group=u.TextureGroup.TEXTUREGROUP_UI, mip_gen_settings=u.TextureMipGenSettings.TMGS_NO_MIPMAPS,
                           address_x=u.TextureAddress.TA_CLAMP, address_y=u.TextureAddress.TA_CLAMP, never_stream=True)
                AS.set_metadata_tag(tex,'CatrunAuthor',OWNER)
                AS.set_metadata_tag(tex,'CatrunFloorplanSHA256',sha)
                assert AS.save_loaded_asset(tex,False)
            tex=AS.load_asset(path)
            assert AS.get_metadata_tag(tex,'CatrunAuthor')==OWNER
            assert AS.get_metadata_tag(tex,'CatrunFloorplanSHA256')==sha
            assert tex.blueprint_get_size_x()==tex.blueprint_get_size_y()==1024
            by_hash[sha]=tex.get_path_name()
        textures[name]=by_hash[sha]
    presenter_bp=AS.load_asset(FOLDER+'/BP_MinimapPresenter')
    if not AUDIT:
        properties(u.get_default_object(presenter_bp.generated_class()),widget_class=panel_class)
        compile_bp(presenter_bp)
        assert AS.save_loaded_asset(presenter_bp,False)
    assert u.get_default_object(presenter_bp.generated_class()).get_editor_property('widget_class')==panel_class
    try:
        for name in MAP_NAMES:
            assert LEVEL.load_level('/Game/Maps/'+name)
            world=ED.get_editor_world()
            panel_class=AS.load_asset(FOLDER+'/'+PANEL_NAME).generated_class()
            actors=u.GameplayStatics.get_all_actors_of_class(world,u.load_class(None,'/Script/Catrun.CatrunMinimapPresenter'))
            assert len(actors)==1,(name,len(actors))
            actor=actors[0]
            frame,_,_=capture_plan(world)
            assert all(frame[k]==rows['maps'][name]['frame'][k] for k in ('center','size','yaw')),(name,'architecture/frame changed')
            texture=AS.load_asset(textures[name])
            if not AUDIT:
                backup=OUT/'Before'/('Minimap_'+name+'.umap')
                backup.parent.mkdir(parents=True,exist_ok=True)
                if not backup.exists():shutil.copy2(ROOT/'Content/Maps'/(name+'.umap'),backup)
                properties(actor,widget_class=panel_class,background_texture=texture)
                assert LEVEL.save_current_level()
            assert actor.get_editor_property('widget_class')==panel_class
            assert actor.get_editor_property('background_texture')==texture
            center=actor.get_editor_property('map_center');size=actor.get_editor_property('map_size')
            assert [center.x,center.y]==frame['center'] and [size.x,size.y]==frame['size']
            assert actor.get_editor_property('capture_yaw_degrees')==frame['yaw']
            report['maps'][name]={'texture':texture.get_path_name(),'widget':panel_class.get_path_name(),
                'center':frame['center'],'size':frame['size'],'yaw':frame['yaw'],
                'map_sha256':hashlib.sha256((ROOT/'Content/Maps'/(name+'.umap')).read_bytes()).hexdigest()}
        report['completed']=True
    finally:
        (OUT/('minimap_audit.json' if AUDIT else 'minimap_apply.json')).write_text(json.dumps(report,indent=2),encoding='utf8')
    print('CATRUN_FLOORPLAN_MAPS',report['completed'])


main()
