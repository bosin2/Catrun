import unreal,json,hashlib
from pathlib import Path
root=Path(unreal.Paths.project_dir()).resolve();out=root/'Saved/Prototype20261104/CanonicalMaps'
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert not editor.get_game_world();assert levels.load_level('/Game/Maps/MainMenu')
state={'world':editor.get_editor_world().get_path_name(),'pie':bool(editor.get_game_world()),'dirty_maps':[p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],'dirty_content':[p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]}
state['disk_config']=(root/'Config/DefaultGame.ini').read_text(encoding='utf8')
flow=unreal.get_default_object(unreal.load_class(None,'/Script/Catrun.CatrunLevelFlowSettings'))
state['cached_route']=[r.export_text() for r in flow.get_editor_property('Stages')]
state['canonical_hashes']={name:hashlib.sha256((root/('Content/Maps/'+name+'.umap')).read_bytes()).hexdigest() for name in ['Tutorial','Stage1','Stage2']}
(out/'handback.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf8')
print('HANDBACK',json.dumps({k:v for k,v in state.items() if k!='disk_config'}))
