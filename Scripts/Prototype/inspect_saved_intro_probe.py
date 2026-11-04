import unreal,time
print('PROBE', {k:v for k,v in probe.items() if k not in ['handle','samples']})
print('SAMPLES',len(probe.get('samples',[])),probe.get('samples',[])[-1:])
print('WORLD',unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world())
