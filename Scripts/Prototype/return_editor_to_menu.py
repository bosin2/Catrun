import unreal
_menu_editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
_menu_levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
_menu_return={}
def _return_editor_menu(delta):
    if not _menu_editor.get_game_world():
        unreal.unregister_slate_post_tick_callback(_menu_return['handle'])
        assert _menu_levels.load_level('/Game/Maps/MainMenu')
        print('EDITOR_MAINMENU_READY')
_menu_return['handle']=unreal.register_slate_post_tick_callback(_return_editor_menu)
_menu_levels.editor_request_end_play()
