import unreal,time,json,traceback
from pathlib import Path
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world();assert levels.load_level('/Game/Maps/Stage1')
state={'start':time.monotonic()}
def tick(delta):
    if time.monotonic()-state['start']<3 or not editor.get_game_world():return
    try:
        rows=[]
        for s in unreal.ObjectIterator(unreal.EnhancedInputLocalPlayerSubsystem):
            if s.get_world()!=editor.get_game_world():continue
            rows.append({'subsystem':s.get_path_name(),'contexts':{p:str(s.has_mapping_context(unreal.load_asset(p))) for p in ['/Game/Input/Contexts/IMC_Default','/Game/Input/Contexts/IMC_CatInteraction']},'bell_keys':[str(k.export_text()) for k in s.query_keys_mapped_to_action(unreal.load_asset('/Game/Input/Actions/IA_Bell'))]})
        (Path(unreal.Paths.project_saved_dir())/'Prototype20261104/CanonicalMaps/active-contexts-before.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
        print('ACTIVE_CONTEXTS_BEFORE',rows)
    except Exception:print(traceback.format_exc())
    finally:unreal.unregister_slate_post_tick_callback(state['handle']);levels.editor_request_end_play()
state['handle']=unreal.register_slate_post_tick_callback(tick);levels.editor_request_begin_play()
