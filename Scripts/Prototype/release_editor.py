import unreal
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert not editor.get_game_world(), 'PIE still running'
dirty=unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()+unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
print('DIRTY_PACKAGES', [x.get_name() for x in dirty])
if dirty:
    raise RuntimeError('Do not close with unreviewed unsaved packages')
unreal.SystemLibrary.execute_console_command(editor.get_editor_world(),'QUIT_EDITOR')
