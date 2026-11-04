import unreal,json
from pathlib import Path
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
print('ON_SOUND',unreal.CatrunArmor.on_sound_heard.__doc__)
print('CALL',unreal.Object.call_method.__doc__)
print('SINGLE', [n for n in dir(unreal.AnimSingleNodeInstance) if any(x in n for x in ['asset','time','rate'])])
print('FLOW',[n for n in dir(unreal.CatrunLevelFlowLibrary) if 'start' in n or 'intro' in n])
levels=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem);assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world();assert levels.load_level('/Game/Maps/Stage2')
rows=[]
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
 if isinstance(a,unreal.CatrunArmor):rows.append({'name':a.get_name(),'label':a.get_actor_label(),'pos':str(a.get_actor_location()),'rot':str(a.get_actor_rotation()),'door':str(a.get_editor_property('DoorOpenAnim'))})
print('STAGE2_ARMORS',rows)
