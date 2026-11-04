import unreal
if 'probe' in globals() and probe.get('handle'):
    unreal.unregister_slate_post_tick_callback(probe['handle'])
    probe.pop('handle',None)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
print('CALLBACK_CANCELLED')
