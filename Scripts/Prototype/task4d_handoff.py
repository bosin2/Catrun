"""Read-only final lease handback inventory, no retained world/actor wrappers."""
import unreal,gc,json,types
from pathlib import Path
gc.collect();ed=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
callbacks=[x.__code__.co_filename for x in gc.get_objects() if isinstance(x,types.FunctionType) and x.__name__=='tick' and 'task4d' in x.__code__.co_filename.lower()]
result={'world':ed.get_editor_world().get_path_name(),'pie':bool(ed.get_game_world()),'dirty':[x.get_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]+[x.get_name() for x in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],'retained_task_tick_callbacks':callbacks}
assert result['world']=='/Game/Maps/MainMenu.MainMenu' and not result['pie'] and not result['dirty'] and not callbacks
(Path(unreal.Paths.project_saved_dir())/'Prototype20261104/Task4d/handoff.json').write_text(json.dumps(result,indent=2),encoding='utf8');print('TASK4D_HANDOFF',result)
